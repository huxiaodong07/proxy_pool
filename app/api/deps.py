from __future__ import annotations

from collections.abc import Generator

from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.rate_limit import rate_limiter
from app.core.security import hash_api_key
from app.db.models import ApiKey
from app.db.session import SessionLocal


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_api_key(
    request: Request,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    db: Session = Depends(get_db),
) -> ApiKey:
    if not x_api_key:
        raise HTTPException(status_code=401, detail="Missing API key")

    key_hash = hash_api_key(x_api_key)
    api_key = db.scalar(select(ApiKey).where(ApiKey.key_hash == key_hash, ApiKey.status == "active"))
    if api_key is None:
        raise HTTPException(status_code=401, detail="Invalid API key")

    client = request.client.host if request.client else "unknown"
    rl_key = f"{api_key.key_hash[:12]}:{client}"
    if not rate_limiter.check(key=rl_key, limit=api_key.qps_limit, window_s=1):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")

    return api_key
