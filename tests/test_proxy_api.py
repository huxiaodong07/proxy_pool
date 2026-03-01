from collections.abc import Generator
from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import get_db
from app.core.security import hash_api_key
from app.db.base import Base
from app.db.models import ApiKey, Proxy, ProxyStatus, ProxyTag
from app.main import app


def make_client_with_seed(api_key_raw: str = "test-key", qps_limit: int = 100) -> tuple[TestClient, dict[str, str]]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    Base.metadata.create_all(bind=engine)

    with TestingSessionLocal() as db:
        db.add(
            ApiKey(
                key_hash=hash_api_key(api_key_raw),
                owner="test",
                status="active",
                qps_limit=qps_limit,
                daily_quota=100,
            )
        )
        p1 = Proxy(
            ip="1.1.1.1",
            port=80,
            protocol="http",
            country="US",
            status=ProxyStatus.ACTIVE,
            success_rate=0.90,
            latency_ms=120,
            last_checked_at=datetime.now(timezone.utc),
        )
        p2 = Proxy(
            ip="2.2.2.2",
            port=443,
            protocol="https",
            country="US",
            status=ProxyStatus.ACTIVE,
            success_rate=0.95,
            latency_ms=80,
            last_checked_at=datetime.now(timezone.utc),
        )
        p3 = Proxy(
            ip="3.3.3.3",
            port=8080,
            protocol="http",
            country="DE",
            status=ProxyStatus.SUSPECT,
            success_rate=0.60,
            latency_ms=300,
        )
        db.add_all([p1, p2, p3])
        db.flush()
        db.add_all(
            [
                ProxyTag(proxy_id=p2.id, tag_key="streaming_netflix", tag_value="ok"),
                ProxyTag(proxy_id=p2.id, tag_key="ai_openai", tag_value="ok"),
            ]
        )
        db.commit()

    def override_get_db() -> Generator[Session, None, None]:
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app), {"X-API-Key": api_key_raw}


def test_random_proxy_default_active() -> None:
    client, headers = make_client_with_seed(api_key_raw="key-default")
    response = client.get("/api/v1/proxies/random", headers=headers)

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "active"


def test_random_proxy_filtered() -> None:
    client, headers = make_client_with_seed(api_key_raw="key-filter")
    response = client.get("/api/v1/proxies/random?protocol=https&country=us", headers=headers)

    assert response.status_code == 200
    data = response.json()
    assert data["protocol"] == "https"
    assert data["country"] == "US"


def test_list_proxy_with_filter_and_order() -> None:
    client, headers = make_client_with_seed(api_key_raw="key-list")
    response = client.get("/api/v1/proxies/list?country=us&order_by=latency_ms&order=asc", headers=headers)

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0]["ip"] == "2.2.2.2"


def test_random_proxy_not_found() -> None:
    client, headers = make_client_with_seed(api_key_raw="key-not-found")
    response = client.get("/api/v1/proxies/random?country=JP", headers=headers)

    assert response.status_code == 404
    assert response.json()["detail"] == "No proxy matched filters"


def test_proxy_api_requires_api_key() -> None:
    client, _ = make_client_with_seed(api_key_raw="key-auth")
    response = client.get("/api/v1/proxies/random")
    assert response.status_code == 401


def test_proxy_api_rate_limit() -> None:
    client, headers = make_client_with_seed(api_key_raw="key-rate", qps_limit=1)
    first = client.get("/api/v1/proxies/random", headers=headers)
    second = client.get("/api/v1/proxies/random", headers=headers)

    assert first.status_code == 200
    assert second.status_code == 429


def test_proxy_api_filter_by_tags() -> None:
    client, headers = make_client_with_seed(api_key_raw="key-tags")
    response = client.get("/api/v1/proxies/list?streaming_netflix=ok&ai_openai=ok", headers=headers)

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["ip"] == "2.2.2.2"
