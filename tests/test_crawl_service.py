from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.db.models import Proxy
from app.services.crawl.parsers import CsvProxyParser, IpPortTextParser
from app.services.crawl.schemas import ProxyCandidate
from app.services.crawl.service import CrawlService


def test_ip_port_text_parser() -> None:
    parser = IpPortTextParser(protocol="https")
    raw = "good 1.1.1.1:443\ninvalid\n8.8.8.8:8080"

    items = parser.parse(raw, source="s1")

    assert len(items) == 2
    assert items[0].protocol == "https"
    assert items[0].source == "s1"


def test_csv_parser() -> None:
    parser = CsvProxyParser()
    raw = "1.1.1.1,80,http,US,elite\n#comment\n2.2.2.2,443,https"

    items = parser.parse(raw, source="csv")

    assert len(items) == 2
    assert items[0].country == "US"
    assert items[1].protocol == "https"


def test_normalize_and_persist_dedup() -> None:
    service = CrawlService()
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    TestingSession = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    Base.metadata.create_all(engine)

    candidates = [
        ProxyCandidate(ip="1.1.1.1", port=80, protocol="HTTP", source="a"),
        ProxyCandidate(ip="1.1.1.1", port=80, protocol="http", source="a"),
        ProxyCandidate(ip="999.1.1.1", port=80, protocol="http", source="a"),
        ProxyCandidate(ip="2.2.2.2", port=70000, protocol="http", source="a"),
    ]

    with TestingSession() as db:
        inserted = service.persist_candidates(db, candidates)
        inserted_again = service.persist_candidates(db, candidates)
        count = db.query(Proxy).count()

    assert inserted == 1
    assert inserted_again == 0
    assert count == 1
