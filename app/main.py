from fastapi import FastAPI

from app.api.health import router as health_router
from app.api.proxies import router as proxies_router
from app.core.config import settings
from app.core.metrics import metrics_middleware, router as metrics_router

app = FastAPI(title=settings.app_name)
app.middleware("http")(metrics_middleware)
app.include_router(health_router)
app.include_router(metrics_router)
app.include_router(proxies_router)
