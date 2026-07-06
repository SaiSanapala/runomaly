from __future__ import annotations

import os
import shutil
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_investigator.db")
os.environ.setdefault("SNAPSHOTS_DIR", str(Path(".test_snapshots").resolve()))
os.environ.setdefault("SAMPLE_DATA_DIR", str(Path("sample_data").resolve()))
os.environ.setdefault("PREFECT_API_MODE", "offline")

import pytest
from fastapi.testclient import TestClient

from backend.app.db.base import Base
from backend.app.db.session import SessionLocal, engine
from backend.app.main import app
from backend.app.services.bootstrap import seed_defaults


@pytest.fixture(autouse=True)
def reset_database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    snapshot_dir = Path(os.environ["SNAPSHOTS_DIR"])
    if snapshot_dir.exists():
        shutil.rmtree(snapshot_dir)
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    with SessionLocal() as db:
        seed_defaults(db)
    yield


@pytest.fixture
def db():
    with SessionLocal() as session:
        yield session


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client
