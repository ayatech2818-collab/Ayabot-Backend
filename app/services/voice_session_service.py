
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.voice_session_ticket import AyabotVoiceSessionTicket


from app.models.product import AyabotProduct
from app.models.product_credential import AyabotProductCredential

def create_voice_session_ticket(
    db: Session,
    product_id: UUID,
    credential_id: UUID,
) -> dict:
    settings = get_settings()

    # Generate a cryptographically secure random ticket.
    raw_ticket = secrets.token_urlsafe(32)

    # Store only its SHA-256 hash.
    token_hash = hashlib.sha256(
        raw_ticket.encode("utf-8")
    ).hexdigest()

    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(
        seconds=settings.voice_session_ttl_seconds
    )

    ticket = AyabotVoiceSessionTicket(
        token_hash=token_hash,
        product_id=product_id,
        credential_id=credential_id,
        expires_at=expires_at,
    )

    try:
        db.add(ticket)
        db.commit()
    except Exception:
        db.rollback()
        raise

    return {
        "ticket": raw_ticket,
        "expires_at": expires_at,
        "expires_in": settings.voice_session_ttl_seconds,
    }



def consume_voice_session_ticket(
    db: Session,
    raw_ticket: str,
) -> AyabotVoiceSessionTicket:
    token_hash = hashlib.sha256(
        raw_ticket.encode("utf-8")
    ).hexdigest()

    now = datetime.now(timezone.utc)

    statement = (
        update(AyabotVoiceSessionTicket)
        .where(
            AyabotVoiceSessionTicket.token_hash == token_hash,
            AyabotVoiceSessionTicket.consumed_at.is_(None),
            AyabotVoiceSessionTicket.expires_at > now,
        )
        .values(consumed_at=now)
        .returning(AyabotVoiceSessionTicket.id)
    )

    try:
        ticket_id = db.execute(statement).scalar_one_or_none()

        if ticket_id is None:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid, expired, or already used voice ticket",
            )

        db.commit()

        ticket = db.scalar(
            select(AyabotVoiceSessionTicket).where(
                AyabotVoiceSessionTicket.id == ticket_id
            )
        )

        if ticket is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid voice ticket",
            )

        credential = db.get(
            AyabotProductCredential,
            ticket.credential_id,
        )

        product = db.get(
            AyabotProduct,
            ticket.product_id,
        )

        if (
            credential is None
            or not credential.is_active
            or credential.revoked_at is not None
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Product credential is no longer active",
            )

        if (
            credential.product_id != ticket.product_id
            or product is None
            or not product.is_active
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Product is no longer authorized",
            )

        if credential.expires_at is not None:
            credential_expiry = credential.expires_at

            if credential_expiry.tzinfo is None:
                credential_expiry = credential_expiry.replace(
                    tzinfo=timezone.utc
                )

            if credential_expiry <= now:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Product credential has expired",
                )

        return ticket

    except HTTPException:
        raise
    except Exception:
        db.rollback()
        raise

