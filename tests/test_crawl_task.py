from app.services.crawl.schemas import ProxyCandidate
from app.workers.tasks import crawl_sources


def test_crawl_sources_task(monkeypatch) -> None:
    class DummyService:
        def collect_from_source(self, source):
            return [ProxyCandidate(ip="1.1.1.1", port=80, protocol="http", source=source.name)]

        def persist_candidates(self, db, candidates):
            return len(candidates)

    monkeypatch.setattr("app.workers.tasks.CrawlService", lambda: DummyService())

    result = crawl_sources()

    assert result["sources"] >= 2
    assert result["candidates"] == result["inserted"]
