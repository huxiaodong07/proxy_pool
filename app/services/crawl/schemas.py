from dataclasses import dataclass


@dataclass(slots=True)
class ProxyCandidate:
    ip: str
    port: int
    protocol: str = "http"
    source: str | None = None
    country: str | None = None
    anonymity: str | None = None
