
"""add voice session tickets

Revision ID: cb894a351568
Revises: 977b17b499cf
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "cb894a351568"
down_revision: Union[str, Sequence[str], None] = "977b17b499cf"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ayabot_voice_session_tickets",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("product_id", sa.UUID(), nullable=False),
        sa.Column("credential_id", sa.UUID(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["public.ayabot_products.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["credential_id"],
            ["public.ayabot_product_credentials.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        schema="public",
    )

    op.create_index(
        "ix_public_ayabot_voice_session_tickets_token_hash",
        "ayabot_voice_session_tickets",
        ["token_hash"],
        unique=True,
        schema="public",
    )

    op.create_index(
        "ix_public_ayabot_voice_session_tickets_product_id",
        "ayabot_voice_session_tickets",
        ["product_id"],
        unique=False,
        schema="public",
    )

    op.create_index(
        "ix_public_ayabot_voice_session_tickets_credential_id",
        "ayabot_voice_session_tickets",
        ["credential_id"],
        unique=False,
        schema="public",
    )


def downgrade() -> None:
    op.drop_table(
        "ayabot_voice_session_tickets",
        schema="public",
    )
