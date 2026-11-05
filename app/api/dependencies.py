
from typing import Annotated
from uuid import UUID

from dataclasses import dataclass

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, APIKeyHeader
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import verify_supabase_access_token
from app.db.dependencies import get_db
from app.models.admin import AyabotAdmin

from app.models.product import AyabotProduct
from app.models.product_credential import AyabotProductCredential
from app.services.product_credential_service import authenticate_product_api_key

from datetime import datetime, timedelta, timezone


oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/api/v1/auth/token"
)

product_api_key_scheme = APIKeyHeader(
    name="X-API-Key",
    auto_error=False,
)

@dataclass(frozen=True)
class ProductAuthContext:
    credential: AyabotProductCredential
    product: AyabotProduct


def get_current_admin(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Annotated[Session, Depends(get_db)],
) -> AyabotAdmin:

    try:
        claims = verify_supabase_access_token(token)
        auth_user_id = UUID(claims["sub"])

    except (jwt.InvalidTokenError, ValueError, KeyError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None

    admin = db.scalar(
        select(AyabotAdmin).where(
            AyabotAdmin.auth_user_id == auth_user_id
        )
    )

    if admin is None or not admin.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to access AYABOT administration",
        )

    return admin


def get_current_product(
    api_key: Annotated[
        str | None,
        Depends(product_api_key_scheme),
    ],
    db: Annotated[Session, Depends(get_db)],
) -> ProductAuthContext:

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )

    result = authenticate_product_api_key(db, api_key)

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )

    credential = result["credential"]
    product = result["product"]

    # Update last_used_at at most once every 5 minutes
    now = datetime.now(timezone.utc)
    last_used = credential.last_used_at

    if last_used is not None and last_used.tzinfo is None:
        last_used = last_used.replace(tzinfo=timezone.utc)

    if last_used is None or now - last_used >= timedelta(minutes=5):
        try:
            credential.last_used_at = now
            db.commit()
        except Exception:
            db.rollback()

    return ProductAuthContext(
        credential=credential,
        product=product,
    )