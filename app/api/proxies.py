from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import Select, asc, desc, exists, select
from sqlalchemy.orm import Session

from app.api.deps import get_api_key, get_db
from app.core.cache import cache
from app.db.models import ApiKey, Proxy, ProxyStatus, ProxyTag

router = APIRouter(prefix="/api/v1/proxies", tags=["proxies"])


class ProxyOut(BaseModel):
    ip: str
    port: int
    protocol: str
    country: str | None
    anonymity: str | None
    latency_ms: float | None
    success_rate: float | None
    status: str
    last_checked_at: datetime | None

    @classmethod
    def from_model(cls, proxy: Proxy) -> "ProxyOut":
        return cls(
            ip=proxy.ip,
            port=proxy.port,
            protocol=proxy.protocol,
            country=proxy.country,
            anonymity=proxy.anonymity,
            latency_ms=proxy.latency_ms,
            success_rate=proxy.success_rate,
            status=proxy.status.value,
            last_checked_at=proxy.last_checked_at,
        )


def apply_filters(
    stmt: Select[tuple[Proxy]],
    *,
    protocol: str | None,
    country: str | None,
    status: ProxyStatus | None,
    min_success_rate: float | None,
    streaming_netflix: str | None,
    ai_openai: str | None,
) -> Select[tuple[Proxy]]:
    if protocol:
        stmt = stmt.where(Proxy.protocol == protocol.lower())
    if country:
        stmt = stmt.where(Proxy.country == country.upper())
    if status:
        stmt = stmt.where(Proxy.status == status)
    if min_success_rate is not None:
        stmt = stmt.where(Proxy.success_rate >= min_success_rate)
    if streaming_netflix:
        stmt = stmt.where(
            exists(
                select(ProxyTag.id).where(
                    ProxyTag.proxy_id == Proxy.id,
                    ProxyTag.tag_key == "streaming_netflix",
                    ProxyTag.tag_value == streaming_netflix,
                )
            )
        )
    if ai_openai:
        stmt = stmt.where(
            exists(
                select(ProxyTag.id).where(
                    ProxyTag.proxy_id == Proxy.id,
                    ProxyTag.tag_key == "ai_openai",
                    ProxyTag.tag_value == ai_openai,
                )
            )
        )
    return stmt


def _cache_key(name: str, **kwargs: Any) -> str:
    parts = [name]
    for k, v in sorted(kwargs.items()):
        parts.append(f"{k}={v}")
    return "proxy_api:" + "|".join(parts)


@router.get("/random", response_model=ProxyOut)
def get_random_proxy(
    protocol: str | None = Query(default=None),
    country: str | None = Query(default=None),
    status: ProxyStatus = Query(default=ProxyStatus.ACTIVE),
    min_success_rate: float | None = Query(default=None, ge=0, le=1),
    streaming_netflix: str | None = Query(default=None),
    ai_openai: str | None = Query(default=None),
    db: Session = Depends(get_db),
    _: ApiKey = Depends(get_api_key),
) -> ProxyOut:
    key = _cache_key(
        "random",
        protocol=protocol,
        country=country,
        status=status.value,
        min_success_rate=min_success_rate,
        streaming_netflix=streaming_netflix,
        ai_openai=ai_openai,
    )

    def producer() -> dict:
        stmt = select(Proxy)
        stmt2 = apply_filters(
            stmt,
            protocol=protocol,
            country=country,
            status=status,
            min_success_rate=min_success_rate,
            streaming_netflix=streaming_netflix,
            ai_openai=ai_openai,
        ).order_by(Proxy.success_rate.desc().nullslast(), Proxy.latency_ms.asc().nullslast())

        proxy = db.scalar(stmt2.limit(1))
        if proxy is None:
            raise HTTPException(status_code=404, detail="No proxy matched filters")
        return ProxyOut.from_model(proxy).model_dump(mode="json")

    data = cache.remember_json(key, ttl_s=10, producer=producer)
    return ProxyOut.model_validate(data)


@router.get("/list", response_model=list[ProxyOut])
def list_proxies(
    protocol: str | None = Query(default=None),
    country: str | None = Query(default=None),
    status: ProxyStatus = Query(default=ProxyStatus.ACTIVE),
    min_success_rate: float | None = Query(default=None, ge=0, le=1),
    streaming_netflix: str | None = Query(default=None),
    ai_openai: str | None = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    order_by: Literal["success_rate", "latency_ms", "last_checked_at"] = Query(default="success_rate"),
    order: Literal["asc", "desc"] = Query(default="desc"),
    db: Session = Depends(get_db),
    _: ApiKey = Depends(get_api_key),
) -> list[ProxyOut]:
    key = _cache_key(
        "list",
        protocol=protocol,
        country=country,
        status=status.value,
        min_success_rate=min_success_rate,
        streaming_netflix=streaming_netflix,
        ai_openai=ai_openai,
        offset=offset,
        limit=limit,
        order_by=order_by,
        order=order,
    )

    def producer() -> list[dict]:
        stmt = select(Proxy)
        stmt2 = apply_filters(
            stmt,
            protocol=protocol,
            country=country,
            status=status,
            min_success_rate=min_success_rate,
            streaming_netflix=streaming_netflix,
            ai_openai=ai_openai,
        )

        order_col = {
            "success_rate": Proxy.success_rate,
            "latency_ms": Proxy.latency_ms,
            "last_checked_at": Proxy.last_checked_at,
        }[order_by]
        stmt2 = stmt2.order_by(asc(order_col).nullslast() if order == "asc" else desc(order_col).nullslast())

        proxies = list(db.scalars(stmt2.offset(offset).limit(limit)))
        return [ProxyOut.from_model(item).model_dump(mode="json") for item in proxies]

    data = cache.remember_json(key, ttl_s=10, producer=producer)
    return [ProxyOut.model_validate(item) for item in data]
