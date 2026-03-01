from __future__ import annotations

import re
from abc import ABC, abstractmethod

from app.services.crawl.schemas import ProxyCandidate

IP_PORT_RE = re.compile(r"\b(?P<ip>(?:\d{1,3}\.){3}\d{1,3}):(?P<port>\d{2,5})\b")


class BaseParser(ABC):
    @abstractmethod
    def parse(self, raw: str, *, source: str) -> list[ProxyCandidate]:
        raise NotImplementedError


class IpPortTextParser(BaseParser):
    """Parse plain text containing entries like 1.2.3.4:8080."""

    def __init__(self, protocol: str = "http") -> None:
        self.protocol = protocol

    def parse(self, raw: str, *, source: str) -> list[ProxyCandidate]:
        items: list[ProxyCandidate] = []
        for match in IP_PORT_RE.finditer(raw):
            items.append(
                ProxyCandidate(
                    ip=match.group("ip"),
                    port=int(match.group("port")),
                    protocol=self.protocol,
                    source=source,
                )
            )
        return items


class CsvProxyParser(BaseParser):
    """Parse lines in format: ip,port,protocol,country,anonymity."""

    def parse(self, raw: str, *, source: str) -> list[ProxyCandidate]:
        items: list[ProxyCandidate] = []
        for line in raw.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = [part.strip() for part in line.split(",")]
            if len(parts) < 2:
                continue
            ip, port = parts[0], parts[1]
            protocol = parts[2] if len(parts) > 2 and parts[2] else "http"
            country = parts[3] if len(parts) > 3 and parts[3] else None
            anonymity = parts[4] if len(parts) > 4 and parts[4] else None
            if not port.isdigit():
                continue
            items.append(
                ProxyCandidate(
                    ip=ip,
                    port=int(port),
                    protocol=protocol.lower(),
                    source=source,
                    country=country,
                    anonymity=anonymity,
                )
            )
        return items
