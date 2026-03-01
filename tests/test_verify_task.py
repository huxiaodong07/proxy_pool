from app.workers.tasks import verify_ai, verify_connectivity, verify_streaming


def test_verify_connectivity_task(monkeypatch) -> None:
    class DummyVerify:
        def verify_batch(self, db, limit=100):
            return {"checked": limit, "ok": 2, "failed": 1}

    monkeypatch.setattr("app.workers.tasks.VerifyService", lambda: DummyVerify())

    result = verify_connectivity(limit=3)
    assert result == {"checked": 3, "ok": 2, "failed": 1}


def test_verify_streaming_task(monkeypatch) -> None:
    class DummyVerify:
        def verify_streaming_batch(self, db, target="netflix", limit=100):
            return {"checked": limit, "ok": 1, "blocked": 0}

    monkeypatch.setattr("app.workers.tasks.VerifyService", lambda: DummyVerify())

    result = verify_streaming(limit=5, target="netflix")
    assert result == {"checked": 5, "ok": 1, "blocked": 0}


def test_verify_ai_task(monkeypatch) -> None:
    class DummyVerify:
        def verify_ai_batch(self, db, target="openai", limit=100):
            return {"checked": limit, "ok": 1, "blocked": 0}

    monkeypatch.setattr("app.workers.tasks.VerifyService", lambda: DummyVerify())

    result = verify_ai(limit=7, target="openai")
    assert result == {"checked": 7, "ok": 1, "blocked": 0}
