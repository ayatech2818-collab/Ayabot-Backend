import hashlib
import secrets
from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.product import AyabotProduct
from app.models.product_credential import AyabotProductCredential
from app.schemas.product_credential import CredentialCreate


def generate_api_key() -> str:
    return f"ayb_{secrets.token_urlsafe(32)}"


def hash_api_key(api_key: str) -> str:
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()


def create_product_credential(
    db: Session,
    product_id: UUID,
    credential_data: CredentialCreate,
):
    product = db.get(AyabotProduct, product_id)

    if product is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found",
        )

    if not product.is_active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot create credentials for an inactive product",
        )

    api_key = generate_api_key()

    credential = AyabotProductCredential(
        product_id=product_id,
        name=credential_data.name,
        key_prefix=api_key[:12],
        key_hash=hash_api_key(api_key),
        expires_at=credential_data.expires_at,
    )

    try:
        db.add(credential)
        db.commit()
        db.refresh(credential)
    except Exception:
        db.rollback()
        raise

    return credential, api_key

def get_product_credentials(
    db: Session,
    product_id: UUID,
    include_inactive: bool = False,
):
    product = db.get(AyabotProduct, product_id)

    if product is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found",
        )

    query = select(AyabotProductCredential).where(
        AyabotProductCredential.product_id == product_id
    )

    if not include_inactive:
        query = query.where(
            AyabotProductCredential.is_active.is_(True)
        )

    query = query.order_by(
        AyabotProductCredential.created_at.desc()
    )

    return db.scalars(query).all()


def revoke_product_credential(
    db: Session,
    product_id: UUID,
    credential_id: UUID,
):
    credential = db.scalar(
        select(AyabotProductCredential).where(
            AyabotProductCredential.id == credential_id,
            AyabotProductCredential.product_id == product_id,
        )
    )

    if credential is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Credential not found",
        )

    if not credential.is_active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Credential is already revoked",
        )

    credential.is_active = False
    credential.revoked_at = datetime.now(timezone.utc)

    try:
        db.commit()
        db.refresh(credential)
    except Exception:
        db.rollback()
        raise

    return credential

def authenticate_product_api_key(
    db: Session,
    api_key: str,
):
    # 1. Basic API key validation
    if not api_key.startswith("ayb_") or len(api_key) > 200:
        return None

    # 2. Hash the incoming API key
    key_hash = hash_api_key(api_key)

    # 3. Find credential using its hash
    credential = db.scalar(
        select(AyabotProductCredential).where(
            AyabotProductCredential.key_hash == key_hash
        )
    )

    if credential is None:
        return None

    # 4. Check whether credential is active
    if not credential.is_active or credential.revoked_at is not None:
        return None

    # 5. Check expiration
    now = datetime.now(timezone.utc)

    if credential.expires_at is not None:
        expires_at = credential.expires_at

        # Handle timezone-naive database timestamps
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)

        if expires_at <= now:
            return None

    # 6. Get associated product
    product = db.get(AyabotProduct, credential.product_id)

    if product is None or not product.is_active:
        return None

    # 7. Return authenticated credential and product
    return {
        "credential": credential,
        "product": product,
    }