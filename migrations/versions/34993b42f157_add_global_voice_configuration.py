"""add global voice configuration

Revision ID: 34993b42f157
Revises: cb894a351568
Create Date: 2026-11-14 12:13:58.872345

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '34993b42f157'
down_revision: Union[str, Sequence[str], None] = 'cb894a351568'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None



def upgrade() -> None:
    op.create_table(
        "ayabot_voice_config",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "config_key",
            sa.String(length=20),
            server_default=sa.text("'global'"),
            nullable=False,
        ),
        sa.Column(
            "config_version",
            sa.Integer(),
            server_default=sa.text("1"),
            nullable=False,
        ),
        sa.Column("gemini_model", sa.String(length=150), nullable=False),
        sa.Column("system_instruction", sa.Text(), nullable=False),
        sa.Column(
            "voice_name",
            sa.String(length=100),
            server_default=sa.text("'Aoede'"),
            nullable=False,
        ),
        sa.Column(
            "response_modalities",
            postgresql.JSONB(),
            server_default=sa.text(
                '\'{"modalities": ["AUDIO"]}\'::jsonb'
            ),
            nullable=False,
        ),
        sa.Column(
            "language_settings",
            postgresql.JSONB(),
            server_default=sa.text(
                '\'{"supported_languages": ["English", "Malayalam", "Hindi", "Arabic"]}\'::jsonb'
            ),
            nullable=False,
        ),
        sa.Column(
            "audio_settings",
            postgresql.JSONB(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "is_enabled",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column("updated_by", sa.UUID(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "config_key = 'global'",
            name="ck_ayabot_voice_config_global_key",
        ),
        sa.CheckConstraint(
            "config_version >= 1",
            name="ck_ayabot_voice_config_version",
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"],
            ["public.ayabot_admins.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "config_key",
            name="uq_ayabot_voice_config_key",
        ),
        schema="public",
    )

    op.create_index(
        "ix_public_ayabot_voice_config_updated_by",
        "ayabot_voice_config",
        ["updated_by"],
        unique=False,
        schema="public",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_public_ayabot_voice_config_updated_by",
        table_name="ayabot_voice_config",
        schema="public",
    )

    op.drop_table(
        "ayabot_voice_config",
        schema="public",
    )

    # ### end Alembic commands ###
