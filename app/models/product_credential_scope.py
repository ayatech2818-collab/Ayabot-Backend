import uuid

from sqlalchemy import ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AyabotProductCredentialScope(Base):
    __tablename__ = "ayabot_product_credential_scopes"
    __table_args__ = {"schema": "public"}

    credential_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "public.ayabot_product_credentials.id",
            ondelete="CASCADE",
        ),
        primary_key=True,
    )

    scope_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "public.ayabot_scopes.id",
            ondelete="RESTRICT",
        ),
        primary_key=True,
    )