"""init core tables

Revision ID: 202603010915
Revises: 
Create Date: 2026-03-01 09:15:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "202603010915"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


proxy_status_enum = sa.Enum("new", "active", "suspect", "inactive", name="proxy_status_enum")
check_type_enum = sa.Enum("connectivity", "streaming", "ai", name="check_type_enum")


def upgrade() -> None:
    proxy_status_enum.create(op.get_bind(), checkfirst=True)
    check_type_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "proxies",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("ip", sa.String(length=64), nullable=False),
        sa.Column("port", sa.Integer(), nullable=False),
        sa.Column("protocol", sa.String(length=16), nullable=False),
        sa.Column("country", sa.String(length=32), nullable=True),
        sa.Column("anonymity", sa.String(length=32), nullable=True),
        sa.Column("source", sa.String(length=128), nullable=True),
        sa.Column("status", proxy_status_enum, nullable=False, server_default="new"),
        sa.Column("latency_ms", sa.Float(), nullable=True),
        sa.Column("success_rate", sa.Float(), nullable=True),
        sa.Column("fail_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("ip", "port", "protocol", name="uq_proxy_ip_port_protocol"),
    )
    op.create_index("ix_proxies_status", "proxies", ["status"])
    op.create_index("ix_proxies_last_checked_at", "proxies", ["last_checked_at"])
    op.create_index("ix_proxies_country", "proxies", ["country"])

    op.create_table(
        "proxy_checks",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("proxy_id", sa.Integer(), sa.ForeignKey("proxies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("check_type", check_type_enum, nullable=False),
        sa.Column("target", sa.String(length=64), nullable=False),
        sa.Column("result", sa.String(length=32), nullable=False),
        sa.Column("response_time_ms", sa.Float(), nullable=True),
        sa.Column("raw_meta", sa.Text(), nullable=True),
        sa.Column("checked_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_proxy_checks_proxy_id", "proxy_checks", ["proxy_id"])

    op.create_table(
        "api_keys",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("key_hash", sa.String(length=128), nullable=False, unique=True),
        sa.Column("owner", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="active"),
        sa.Column("qps_limit", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("daily_quota", sa.Integer(), nullable=False, server_default="10000"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )


def downgrade() -> None:
    op.drop_table("api_keys")
    op.drop_index("ix_proxy_checks_proxy_id", table_name="proxy_checks")
    op.drop_table("proxy_checks")

    op.drop_index("ix_proxies_country", table_name="proxies")
    op.drop_index("ix_proxies_last_checked_at", table_name="proxies")
    op.drop_index("ix_proxies_status", table_name="proxies")
    op.drop_table("proxies")

    check_type_enum.drop(op.get_bind(), checkfirst=True)
    proxy_status_enum.drop(op.get_bind(), checkfirst=True)
