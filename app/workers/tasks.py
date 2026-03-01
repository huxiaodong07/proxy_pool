from datetime import datetime, timezone

from app.core.metrics import TASK_RUN_COUNT
from app.db.session import SessionLocal
from app.services.crawl import CrawlService, DEFAULT_SOURCES
from app.services.verify import VerifyService
from app.workers.celery_app import celery_app


@celery_app.task(name="proxy_pool.ping")
def ping() -> dict[str, str]:
    TASK_RUN_COUNT.labels(task="ping", result="ok").inc()
    return {"message": "pong", "timestamp": datetime.now(timezone.utc).isoformat()}


@celery_app.task(name="proxy_pool.crawl_sources")
def crawl_sources() -> dict[str, int]:
    crawler = CrawlService()
    total_candidates = 0
    total_inserted = 0

    with SessionLocal() as db:
        for source in DEFAULT_SOURCES:
            try:
                candidates = crawler.collect_from_source(source)
                total_candidates += len(candidates)
                total_inserted += crawler.persist_candidates(db, candidates)
            except Exception:
                TASK_RUN_COUNT.labels(task="crawl_sources", result="error").inc()
                continue

    TASK_RUN_COUNT.labels(task="crawl_sources", result="ok").inc()
    return {"sources": len(DEFAULT_SOURCES), "candidates": total_candidates, "inserted": total_inserted}


@celery_app.task(name="proxy_pool.verify_connectivity")
def verify_connectivity(limit: int = 100) -> dict[str, int]:
    verifier = VerifyService()

    with SessionLocal() as db:
        result = verifier.verify_batch(db, limit=limit)
    TASK_RUN_COUNT.labels(task="verify_connectivity", result="ok").inc()
    return result


@celery_app.task(name="proxy_pool.verify_streaming")
def verify_streaming(limit: int = 100, target: str = "netflix") -> dict[str, int]:
    verifier = VerifyService()
    with SessionLocal() as db:
        result = verifier.verify_streaming_batch(db, target=target, limit=limit)
    TASK_RUN_COUNT.labels(task="verify_streaming", result="ok").inc()
    return result


@celery_app.task(name="proxy_pool.verify_ai")
def verify_ai(limit: int = 100, target: str = "openai") -> dict[str, int]:
    verifier = VerifyService()
    with SessionLocal() as db:
        result = verifier.verify_ai_batch(db, target=target, limit=limit)
    TASK_RUN_COUNT.labels(task="verify_ai", result="ok").inc()
    return result
