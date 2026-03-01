from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, Enum as SqlEnum, Float, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def enum_values(enum_cls: type[Enum]) -> list[str]:
    return [item.value for item in enum_cls]


class ProxyStatus(str, Enum):
    NEW = "new"
    ACTIVE = "active"
    SUSPECT = "suspect"
    INACTIVE = "inactive"


class CheckType(str, Enum):
    CONNECTIVITY = "connectivity"
    STREAMING = "streaming"
    AI = "ai"


class Proxy(Base):
    __tablename__ = "proxies"
    __table_args__ = (UniqueConstraint("ip", "port", "protocol", name="uq_proxy_ip_port_protocol"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ip: Mapped[str] = mapped_column(String(64), nullable=False)
    port: Mapped[int] = mapped_column(Integer, nullable=False)
    protocol: Mapped[str] = mapped_column(String(16), nullable=False)
    country: Mapped[str | None] = mapped_column(String(32), nullable=True)
    anonymity: Mapped[str | None] = mapped_column(String(32), nullable=True)
    source: Mapped[str | None] = mapped_column(String(128), nullable=True)

    status: Mapped[ProxyStatus] = mapped_column(
        SqlEnum(ProxyStatus, name="proxy_status_enum", values_callable=enum_values),
        default=ProxyStatus.NEW,
        nullable=False,
    )
    latency_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    success_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    fail_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ProxyCheck(Base):
    __tablename__ = "proxy_checks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    proxy_id: Mapped[int] = mapped_column(ForeignKey("proxies.id", ondelete="CASCADE"), nullable=False, index=True)
    check_type: Mapped[CheckType] = mapped_column(
        SqlEnum(CheckType, name="check_type_enum", values_callable=enum_values), nullable=False
    )
    target: Mapped[str] = mapped_column(String(64), nullable=False)
    result: Mapped[str] = mapped_column(String(32), nullable=False)
    response_time_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    raw_meta: Mapped[str | None] = mapped_column(Text, nullable=True)
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ProxyTag(Base):
    __tablename__ = "proxy_tags"
    __table_args__ = (UniqueConstraint("proxy_id", "tag_key", name="uq_proxy_tag_proxy_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    proxy_id: Mapped[int] = mapped_column(ForeignKey("proxies.id", ondelete="CASCADE"), nullable=False, index=True)
    tag_key: Mapped[str] = mapped_column(String(64), nullable=False)
    tag_value: Mapped[str] = mapped_column(String(32), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ApiKey(Base):
    __tablename__ = "api_keys"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    key_hash: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    owner: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="active", nullable=False)
    qps_limit: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    daily_quota: Mapped[int] = mapped_column(Integer, default=10000, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
