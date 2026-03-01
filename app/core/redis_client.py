from __future__ import annotations

from redis import Redis
from redis.exceptions import RedisError

from app.core.config import settings


class RedisClient:
    def __init__(self) -> None:
        self._client = Redis.from_url(settings.redis_url, decode_responses=True)

    def get(self, key: str) -> str | None:
        try:
            return self._client.get(key)
        except RedisError:
            return None

    def setex(self, key: str, ttl_s: int, value: str) -> bool:
        try:
            return bool(self._client.setex(key, ttl_s, value))
        except RedisError:
            return False

    def incr(self, key: str, expire_s: int) -> int | None:
        try:
            count = self._client.incr(key)
            if count == 1:
                self._client.expire(key, expire_s)
            return int(count)
        except RedisError:
            return None
