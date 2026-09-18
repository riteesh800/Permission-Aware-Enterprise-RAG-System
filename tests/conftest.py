from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

TMP = Path(tempfile.mkdtemp())
os.environ["DATABASE_URL"] = f"sqlite:///{(TMP / 'test.db').as_posix()}"
os.environ["JWT_SECRET"] = "test-jwt-secret-must-be-32-chars-min"
os.environ["SESSION_SECRET"] = "test-session-secret-must-be-32-ch"
os.environ["EMBEDDING_PROVIDER"] = "hash"
os.environ["LLM_PROVIDER"] = "extractive"
os.environ["STORAGE_PATH"] = str(TMP / "uploads")
os.environ["ENVIRONMENT"] = "test"
os.environ["COOKIE_SECURE"] = "false"
os.environ["CORS_ORIGINS"] = "http://testserver"

from app.config import get_settings  # noqa: E402

get_settings.cache_clear()

from app import database as dbmod  # noqa: E402
from app.database import Base, reset_engine  # noqa: E402
from app import models  # noqa: E402, F401
from app.main import create_app  # noqa: E402
from app.seed import seed  # noqa: E402
from app.security.ratelimit import limiter  # noqa: E402
from app.security.throttle import login_throttle  # noqa: E402



@pytest.fixture()
def app():
    reset_engine()
    Base.metadata.drop_all(bind=dbmod.engine)
    Base.metadata.create_all(bind=dbmod.engine)
    db = dbmod.SessionLocal()
    try:
        seed(db)
    finally:
        db.close()
    return create_app()


@pytest.fixture(autouse=True)
def _seeded_app(app):
    limiter._events.clear()
    login_throttle._failures.clear()
    return app


@pytest.fixture()
def client(app):
    with TestClient(app) as test_client:
        yield test_client


def login(client: TestClient, identifier: str, password: str = "DevPassw0rd!x") -> dict:
    response = client.post("/api/auth/login", json={"identifier": identifier, "password": password})
    assert response.status_code == 200, response.text
    csrf = client.cookies.get("csrf_token")
    assert csrf
    return {"X-CSRF-Token": csrf}


def login_session(app, identifier: str, password: str = "DevPassw0rd!x") -> tuple[TestClient, dict]:
    isolated = TestClient(app)
    headers = login(isolated, identifier, password)
    return isolated, headers
