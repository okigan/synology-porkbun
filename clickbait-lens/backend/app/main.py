from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import router
from .config import get_settings
from .db import SessionLocal, init_db
from .seed import seed

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    init_db()
    if settings.seed_on_startup:
        with SessionLocal() as session:
            created = seed(session)
        if created:
            log.info("Seeded %s demo authors", created)
    log.info("Analyzer=%s search_provider=%s", settings.analyzer, settings.search_provider)
    yield


app = FastAPI(
    title="Clickbait Lens API",
    version="0.1.0",
    description=(
        "Headline-integrity analysis and author prediction-accuracy tracking. "
        "The default analyzer is rule-based and runs with no API keys; "
        "verification hits a live search provider."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().allow_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/healthz", tags=["meta"])
def healthz() -> dict:
    settings = get_settings()
    return {
        "status": "ok",
        "analyzer": settings.analyzer,
        "search_provider": settings.search_provider,
    }
