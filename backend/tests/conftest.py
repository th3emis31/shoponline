import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy import create_engine

from app.config import settings
from app.db import Base, get_session
from app.main import app
from app.seed import seed


@pytest.fixture()
def db():
    # Default: fast in-memory SQLite. Set TEST_DATABASE_URL to run against PostgreSQL.
    url = os.environ.get("TEST_DATABASE_URL")
    if url:
        engine = create_engine(url)
        Base.metadata.drop_all(engine)
    else:
        engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    with Session() as session:
        seed(session)
    yield Session
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture()
def client(db):
    def override():
        with db() as session:
            yield session

    app.dependency_overrides[get_session] = override
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture()
def admin_token(monkeypatch):
    monkeypatch.setattr(settings, "admin_token", "test-token")
    return "test-token"
