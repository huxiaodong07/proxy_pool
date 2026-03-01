from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.db.models import CheckType, Proxy, ProxyCheck, ProxyStatus, ProxyTag
from app.services.verify import VerifyService


def make_db():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Session = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    Base.metadata.create_all(engine)
    return Session


def test_verify_proxy_success(monkeypatch) -> None:
    service = VerifyService()
    Session = make_db()

    with Session() as db:
        proxy = Proxy(ip="1.1.1.1", port=8080, protocol="http", status=ProxyStatus.NEW)
        db.add(proxy)
        db.commit()
        db.refresh(proxy)

        monkeypatch.setattr(service, "probe_proxy", lambda p: (True, 123.0, "ok"))
        ok = service.verify_proxy(db, proxy)

        db.refresh(proxy)
        check = db.query(ProxyCheck).one()

    assert ok is True
    assert proxy.status == ProxyStatus.ACTIVE
    assert proxy.fail_count == 0
    assert proxy.latency_ms == 123.0
    assert check.check_type == CheckType.CONNECTIVITY
    assert check.result == "ok"


def test_verify_proxy_failure_to_inactive(monkeypatch) -> None:
    service = VerifyService()
    Session = make_db()

    with Session() as db:
        proxy = Proxy(ip="1.1.1.1", port=8080, protocol="http", status=ProxyStatus.SUSPECT, fail_count=2)
        db.add(proxy)
        db.commit()
        db.refresh(proxy)

        monkeypatch.setattr(service, "probe_proxy", lambda p: (False, None, "timeout"))
        ok = service.verify_proxy(db, proxy)

        db.refresh(proxy)

    assert ok is False
    assert proxy.status == ProxyStatus.INACTIVE
    assert proxy.fail_count == 3


def test_verify_batch_counts(monkeypatch) -> None:
    service = VerifyService()
    Session = make_db()

    with Session() as db:
        db.add_all(
            [
                Proxy(ip="1.1.1.1", port=80, protocol="http", status=ProxyStatus.NEW),
                Proxy(ip="2.2.2.2", port=80, protocol="http", status=ProxyStatus.NEW),
                Proxy(ip="3.3.3.3", port=80, protocol="http", status=ProxyStatus.INACTIVE),
            ]
        )
        db.commit()

        calls = iter([(True, 10.0, "ok"), (False, None, "timeout")])
        monkeypatch.setattr(service, "probe_proxy", lambda p: next(calls))

        result = service.verify_batch(db, limit=10)

    assert result == {"checked": 2, "ok": 1, "failed": 1}


def test_verify_streaming_and_ai_batch_writes_tags(monkeypatch) -> None:
    service = VerifyService()
    Session = make_db()

    with Session() as db:
        db.add(Proxy(ip="4.4.4.4", port=8080, protocol="http", status=ProxyStatus.ACTIVE))
        db.commit()

        monkeypatch.setattr(service, "probe_target", lambda proxy, url: "ok")
        streaming = service.verify_streaming_batch(db, target="netflix", limit=10)
        ai = service.verify_ai_batch(db, target="openai", limit=10)

        tags = {(row.tag_key, row.tag_value) for row in db.query(ProxyTag).all()}
        check_types = {row.check_type for row in db.query(ProxyCheck).all()}

    assert streaming["ok"] == 1
    assert ai["ok"] == 1
    assert ("streaming_netflix", "ok") in tags
    assert ("ai_openai", "ok") in tags
    assert CheckType.STREAMING in check_types
    assert CheckType.AI in check_types
