from __future__ import annotations

import ipaddress
from datetime import datetime, timezone

import requests
from sqlalchemy import select, tuple_
from sqlalchemy.orm import Session

from app.db.models import Proxy, ProxyStatus
from app.services.crawl.schemas import ProxyCandidate
from app.services.crawl.sources import CrawlSource


class CrawlService:
    def fetch_source(self, source: CrawlSource, *, timeout_s: float = 10.0) -> str:
        response = requests.get(source.url, timeout=timeout_s)
        response.raise_for_status()
        return response.text

    def collect_from_source(self, source: CrawlSource) -> list[ProxyCandidate]:
        raw = self.fetch_source(source)
        return source.parser.parse(raw, source=source.name)

    def normalize_candidates(self, candidates: list[ProxyCandidate]) -> list[ProxyCandidate]:
        dedup: dict[tuple[str, int, str], ProxyCandidate] = {}
        for candidate in candidates:
            try:
                ipaddress.ip_address(candidate.ip)
            except ValueError:
                continue
            if not (1 <= candidate.port <= 65535):
                continue
            protocol = candidate.protocol.lower()
            key = (candidate.ip, candidate.port, protocol)
            dedup[key] = ProxyCandidate(
                ip=candidate.ip,
                port=candidate.port,
                protocol=protocol,
                source=candidate.source,
                country=candidate.country,
                anonymity=candidate.anonymity,
            )
        return list(dedup.values())

    def persist_candidates(self, db: Session, candidates: list[ProxyCandidate]) -> int:
        if not candidates:
            return 0

        normalized = self.normalize_candidates(candidates)
        if not normalized:
            return 0

        keys = [(c.ip, c.port, c.protocol) for c in normalized]
        stmt = select(Proxy.ip, Proxy.port, Proxy.protocol).where(tuple_(Proxy.ip, Proxy.port, Proxy.protocol).in_(keys))
        existing = set(db.execute(stmt).all())

        now = datetime.now(timezone.utc)
        to_insert = [
            Proxy(
                ip=c.ip,
                port=c.port,
                protocol=c.protocol,
                source=c.source,
                country=c.country,
                anonymity=c.anonymity,
                status=ProxyStatus.NEW,
                first_seen_at=now,
                last_seen_at=now,
            )
            for c in normalized
            if (c.ip, c.port, c.protocol) not in existing
        ]
        if not to_insert:
            return 0
        db.add_all(to_insert)
        db.commit()
        return len(to_insert)
