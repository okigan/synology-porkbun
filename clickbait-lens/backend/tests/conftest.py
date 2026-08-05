from __future__ import annotations

import os
import tempfile
from collections.abc import Iterator
from pathlib import Path

import pytest

# Point the app at a throwaway database and the offline search provider before
# anything imports the settings singleton.
_TMP = Path(tempfile.mkdtemp(prefix="clickbait-lens-tests-"))
os.environ.setdefault("CBL_DATABASE_URL", f"sqlite+pysqlite:///{_TMP / 'test.db'}")
os.environ.setdefault("CBL_SEARCH_PROVIDER", "fixture")
os.environ.setdefault("CBL_SEED_ON_STARTUP", "false")
os.environ.setdefault("CBL_ANALYZER", "heuristic")

from app.db import SessionLocal, engine, init_db  # noqa: E402
from app.models import Base  # noqa: E402


@pytest.fixture
def session() -> Iterator:
    Base.metadata.drop_all(engine)
    init_db()
    with SessionLocal() as s:
        yield s


@pytest.fixture
def client(session) -> Iterator:
    from fastapi.testclient import TestClient

    from app.db import get_session
    from app.main import app

    app.dependency_overrides[get_session] = lambda: session
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
