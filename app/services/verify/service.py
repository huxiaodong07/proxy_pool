from __future__ import annotations

import time
from datetime import datetime, timezone

import requests
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import CheckType, Proxy, ProxyCheck, ProxyStatus, ProxyTag


class VerifyService:
    def probe_proxy(self, proxy: Proxy, *, timeout_s: float = 8.0) -> tuple[bool, float | None, str]:
        proxy_url = f"{proxy.protocol}://{proxy.ip}:{proxy.port}"
        started = time.perf_counter()
        try:
            requests.get(
                "https://httpbin.org/ip",
                timeout=timeout_s,
                proxies={"http": proxy_url, "https": proxy_url},
            ).raise_for_status()
            latency_ms = (time.perf_counter() - started) * 1000
            return True, latency_ms, "ok"
        except requests.Timeout:
            return False, None, "timeout"
        except requests.RequestException as exc:
            return False, None, f"error:{exc.__class__.__name__}"

    def probe_target(self, proxy: Proxy, *, url: str, timeout_s: float = 10.0) -> str:
        proxy_url = f"{proxy.protocol}://{proxy.ip}:{proxy.port}"
        try:
            response = requests.get(url, timeout=timeout_s, proxies={"http": proxy_url, "https": proxy_url})
            if response.status_code == 200:
                return "ok"
            if response.status_code in {401, 403, 451}:
                return "blocked"
            return "partial"
        except requests.Timeout:
            return "timeout"
        except requests.RequestException:
            return "error"

    def _upsert_tag(self, db: Session, *, proxy_id: int, tag_key: str, tag_value: str) -> None:
        row = db.scalar(select(ProxyTag).where(ProxyTag.proxy_id == proxy_id, ProxyTag.tag_key == tag_key))
        now = datetime.now(timezone.utc)
        if row is None:
            db.add(ProxyTag(proxy_id=proxy_id, tag_key=tag_key, tag_value=tag_value, updated_at=now))
        else:
            row.tag_value = tag_value
            row.updated_at = now

    def verify_proxy(self, db: Session, proxy: Proxy) -> bool:
        ok, latency_ms, reason = self.probe_proxy(proxy)
        now = datetime.now(timezone.utc)

        proxy.last_checked_at = now
        if ok:
            proxy.status = ProxyStatus.ACTIVE
            proxy.latency_ms = latency_ms
            proxy.fail_count = 0
        else:
            proxy.fail_count += 1
            if proxy.fail_count >= 3:
                proxy.status = ProxyStatus.INACTIVE
            else:
                proxy.status = ProxyStatus.SUSPECT

        db.add(
            ProxyCheck(
                proxy_id=proxy.id,
                check_type=CheckType.CONNECTIVITY,
                target="https://httpbin.org/ip",
                result="ok" if ok else reason,
                response_time_ms=latency_ms,
                raw_meta=None,
                checked_at=now,
            )
        )
        db.commit()
        return ok

    def verify_batch(self, db: Session, *, limit: int = 100) -> dict[str, int]:
        stmt = (
            select(Proxy)
            .where(Proxy.status.in_([ProxyStatus.NEW, ProxyStatus.SUSPECT, ProxyStatus.ACTIVE]))
            .order_by(Proxy.last_checked_at.asc().nullsfirst())
            .limit(limit)
        )
        proxies = list(db.scalars(stmt))

        checked = 0
        ok_count = 0
        failed_count = 0
        for proxy in proxies:
            checked += 1
            if self.verify_proxy(db, proxy):
                ok_count += 1
            else:
                failed_count += 1

        return {"checked": checked, "ok": ok_count, "failed": failed_count}

    def verify_streaming_batch(self, db: Session, *, target: str = "netflix", limit: int = 100) -> dict[str, int]:
        target_url = {
            "netflix": "https://www.netflix.com/title/81215567",
            "youtube": "https://www.youtube.com/premium",
        }.get(target, "https://www.netflix.com")

        proxies = list(db.scalars(select(Proxy).where(Proxy.status == ProxyStatus.ACTIVE).limit(limit)))
        ok_count = 0
        blocked_count = 0
        for proxy in proxies:
            result = self.probe_target(proxy, url=target_url)
            now = datetime.now(timezone.utc)
            db.add(
                ProxyCheck(
                    proxy_id=proxy.id,
                    check_type=CheckType.STREAMING,
                    target=target,
                    result=result,
                    response_time_ms=None,
                    raw_meta=None,
                    checked_at=now,
                )
            )
            self._upsert_tag(db, proxy_id=proxy.id, tag_key=f"streaming_{target}", tag_value=result)
            if result == "ok":
                ok_count += 1
            elif result == "blocked":
                blocked_count += 1
        db.commit()
        return {"checked": len(proxies), "ok": ok_count, "blocked": blocked_count}

    def verify_ai_batch(self, db: Session, *, target: str = "openai", limit: int = 100) -> dict[str, int]:
        target_url = {
            "openai": "https://chat.openai.com/",
            "claude": "https://claude.ai/",
            "gemini": "https://gemini.google.com/",
        }.get(target, "https://chat.openai.com/")

        proxies = list(db.scalars(select(Proxy).where(Proxy.status == ProxyStatus.ACTIVE).limit(limit)))
        ok_count = 0
        blocked_count = 0
        for proxy in proxies:
            result = self.probe_target(proxy, url=target_url)
            now = datetime.now(timezone.utc)
            db.add(
                ProxyCheck(
                    proxy_id=proxy.id,
                    check_type=CheckType.AI,
                    target=target,
                    result=result,
                    response_time_ms=None,
                    raw_meta=None,
                    checked_at=now,
                )
            )
            self._upsert_tag(db, proxy_id=proxy.id, tag_key=f"ai_{target}", tag_value=result)
            if result == "ok":
                ok_count += 1
            elif result == "blocked":
                blocked_count += 1
        db.commit()
        return {"checked": len(proxies), "ok": ok_count, "blocked": blocked_count}
