from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel


class Settings(BaseModel):
    app_name: str = "Runomaly"
    database_url: str = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg://postgres:postgres@localhost:5432/investigator",
    )
    snapshots_dir: Path = Path(os.getenv("SNAPSHOTS_DIR", "snapshots")).resolve()
    sample_data_dir: Path = Path(os.getenv("SAMPLE_DATA_DIR", "sample_data")).resolve()
    git_commit: str = os.getenv("GIT_COMMIT", "local")
    replay_mode: str = os.getenv("REPLAY_MODE", "local")


@lru_cache
def get_settings() -> Settings:
    return Settings()
