
"""add previous file path to knowledge documents

Revision ID: 977b17b499cf
Revises: f34b8a6bd62e
Create Date: 2026-11-06 14:34:52.515686

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "977b17b499cf"
down_revision: Union[str, Sequence[str], None] = "f34b8a6bd62e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "ayabot_knowledge_documents",
        sa.Column("previous_file_path", sa.Text(), nullable=True),
        schema="public",
    )


def downgrade() -> None:
    op.drop_column(
        "ayabot_knowledge_documents",
        "previous_file_path",
        schema="public",
    )
