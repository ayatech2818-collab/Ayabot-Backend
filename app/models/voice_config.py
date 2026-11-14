
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AyabotVoiceConfig(Base):
    __tablename__ = "ayabot_voice_config"

    __table_args__ = (
        CheckConstraint(
            "config_key = 'global'",
            name="ck_ayabot_voice_config_global_key",
        ),
        CheckConstraint(
            "config_version >= 1",
            name="ck_ayabot_voice_config_version",
        ),
        UniqueConstraint(
            "config_key",
            name="uq_ayabot_voice_config_key",
        ),
        {"schema": "public"},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )

    config_key: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="global",
        server_default=text("'global'"),
    )

    config_version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        server_default=text("1"),
    )

    gemini_model: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )

    system_instruction: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    voice_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        default="Aoede",
        server_default=text("'Aoede'"),
    )

    response_modalities: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=lambda: {"modalities": ["AUDIO"]},
        server_default=text("""'{"modalities": ["AUDIO"]}'::jsonb"""),
    )

    language_settings: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=lambda: {
            "supported_languages": [
                "English",
                "Malayalam",
                "Hindi",
                "Arabic",
            ]
        },
        server_default=text(
            """'{"supported_languages": ["English", "Malayalam", "Hindi", "Arabic"]}'::jsonb"""
        ),
    )

    audio_settings: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )

    is_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("true"),
    )

    updated_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "public.ayabot_admins.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
