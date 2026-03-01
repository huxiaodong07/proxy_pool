"""add proxy tags table

Revision ID: 202603011030
Revises: 202603010915
Create Date: 2026-03-01 10:30:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "202603011030"
down_revision: Union[str, None] = "202603010915"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "proxy_tags",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("proxy_id", sa.Integer(), sa.ForeignKey("proxies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tag_key", sa.String(length=64), nullable=False),
        sa.Column("tag_value", sa.String(length=32), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("proxy_id", "tag_key", name="uq_proxy_tag_proxy_key"),
    )
    op.create_index("ix_proxy_tags_proxy_id", "proxy_tags", ["proxy_id"])
    op.create_index("ix_proxy_tags_key_value", "proxy_tags", ["tag_key", "tag_value"])


def downgrade() -> None:
    op.drop_index("ix_proxy_tags_key_value", table_name="proxy_tags")
    op.drop_index("ix_proxy_tags_proxy_id", table_name="proxy_tags")
    op.drop_table("proxy_tags")
