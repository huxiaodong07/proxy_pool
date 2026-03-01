from __future__ import annotations

import json
from collections.abc import Callable

from app.core.redis_client import RedisClient


class Cache:
    def __init__(self) -> None:
        self._redis = RedisClient()
        self._local: dict[str, str] = {}

    def get_json(self, key: str) -> dict | list | None:
        raw = self._redis.get(key)
        if raw is None:
            raw = self._local.get(key)
        if raw is None:
            return None
        return json.loads(raw)

    def set_json(self, key: str, value: dict | list, ttl_s: int) -> None:
        raw = json.dumps(value, default=str)
        if not self._redis.setex(key, ttl_s, raw):
            self._local[key] = raw

    def remember_json(self, key: str, ttl_s: int, producer: Callable[[], dict | list]) -> dict | list:
        hit = self.get_json(key)
        if hit is not None:
            return hit
        value = producer()
        self.set_json(key, value, ttl_s)
        return value


cache = Cache()
