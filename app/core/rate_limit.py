from __future__ import annotations

import time
from collections import defaultdict

from app.core.redis_client import RedisClient


class RateLimiter:
    def __init__(self) -> None:
        self._redis = RedisClient()
        self._local_counts: dict[str, tuple[int, int]] = defaultdict(lambda: (0, 0))

    def check(self, *, key: str, limit: int, window_s: int = 1) -> bool:
        redis_count = self._redis.incr(f"rl:{key}", expire_s=window_s)
        if redis_count is not None:
            return redis_count <= limit

        now_bucket = int(time.time()) // window_s
        count, bucket = self._local_counts[key]
        if bucket != now_bucket:
            count = 0
        count += 1
        self._local_counts[key] = (count, now_bucket)
        return count <= limit


rate_limiter = RateLimiter()
