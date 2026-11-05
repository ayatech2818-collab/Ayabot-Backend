
"""add knowledge documents and chunks

Revision ID: f34b8a6bd62e
Revises: bec07f0ce13e
Create Date: 2026-11-05 11:36:32.315723
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector


revision: str = "f34b8a6bd62e"
down_revision: Union[str, Sequence[str], None] = "bec07f0ce13e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # pgvector is installed in the extensions schema.
    # Make its type available while creating the tables.
    op.execute("SET LOCAL search_path TO public, extensions")

    op.create_table(
        "ayabot_knowledge_documents",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("product_id", sa.UUID(), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("file_name", sa.String(255), nullable=False),
        sa.Column("file_path", sa.Text(), nullable=False),
        sa.Column("mime_type", sa.String(100), nullable=False),
        sa.Column("file_size", sa.BigInteger(), nullable=False),
        sa.Column(
            "status",
            sa.String(30),
            server_default=sa.text("'pending'"),
            nullable=False,
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["public.ayabot_products.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        schema="public",
    )

    op.create_index(
        "ix_public_ayabot_knowledge_documents_product_id",
        "ayabot_knowledge_documents",
        ["product_id"],
        unique=False,
        schema="public",
    )

    op.create_table(
        "ayabot_knowledge_chunks",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("document_id", sa.UUID(), nullable=False),
        sa.Column("product_id", sa.UUID(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(768), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["public.ayabot_knowledge_documents.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["public.ayabot_products.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        schema="public",
    )

    op.create_index(
        "ix_public_ayabot_knowledge_chunks_document_id",
        "ayabot_knowledge_chunks",
        ["document_id"],
        unique=False,
        schema="public",
    )

    op.create_index(
        "ix_public_ayabot_knowledge_chunks_product_id",
        "ayabot_knowledge_chunks",
        ["product_id"],
        unique=False,
        schema="public",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_public_ayabot_knowledge_chunks_product_id",
        table_name="ayabot_knowledge_chunks",
        schema="public",
    )

    op.drop_index(
        "ix_public_ayabot_knowledge_chunks_document_id",
        table_name="ayabot_knowledge_chunks",
        schema="public",
    )

    op.drop_table("ayabot_knowledge_chunks", schema="public")

    op.drop_index(
        "ix_public_ayabot_knowledge_documents_product_id",
        table_name="ayabot_knowledge_documents",
        schema="public",
    )

    op.drop_table("ayabot_knowledge_documents", schema="public")
