"""Application settings — loaded from environment / .env via pydantic-settings.

All KooRemapper-platform vars are prefixed `KOORM_` to avoid clashes with the
host environment. Defaults are dev-friendly; production overrides come from
infra/.env (rendered into the api instance by start.sh).
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# platform/backend/app/config.py -> platform/
_PLATFORM_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="KOORM_",
        env_file=(_PLATFORM_ROOT / ".env", _PLATFORM_ROOT / "backend" / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- app ---
    app_name: str = "KooRemapper Platform"
    app_env: str = "development"  # development | production
    api_port: int = 8700
    mcp_port: int = 8701

    # --- database ---
    # asyncpg DSN, e.g. postgresql+asyncpg://koorm:pw@127.0.0.1:5433/koorm
    database_url: str = "postgresql+asyncpg://koorm:koorm@127.0.0.1:5433/koorm"

    # --- auth ---
    jwt_secret: str = "dev-insecure-change-me"
    jwt_algorithm: str = "HS256"
    jwt_access_ttl_min: int = 720  # 12h
    pat_default_expires_days: int = 90

    # --- storage / binary ---
    # Where uploaded/generated session files live (host path, bind-mounted).
    storage_dir: Path = _PLATFORM_ROOT / "storage"
    # The KooRemapper binary the runner executes (copied by CMake POST_BUILD).
    kooremapper_bin: Path = _PLATFORM_ROOT / "backend" / "bin" / "KooRemapper"
    # Per-job wall-clock timeout (seconds).
    job_timeout_sec: int = 1800
    # Concurrent runner workers.
    worker_concurrency: int = 4

    # --- CORS ---
    cors_origins: str = "http://localhost:5273,http://127.0.0.1:5273"

    # --- frontend (combined deploy, optional) ---
    serve_frontend_dist: Path | None = None

    @property
    def is_development(self) -> bool:
        return self.app_env.lower() == "development"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def frontend_dist_path(self) -> Path | None:
        return self.serve_frontend_dist


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
