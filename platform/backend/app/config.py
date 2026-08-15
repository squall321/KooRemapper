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
    allow_signup: bool = True  # public /auth/signup enabled
    # HEAX Portal 게이트웨이 SSO 공유 시크릿 — HEAXHub gateway_shared_secret 와
    # 동일 값. 비우면 /auth/sso 비활성(404).
    heax_gateway_secret: str = ""

    # --- rate limiting (in-memory sliding window) ---
    ratelimit_enabled: bool = True
    ratelimit_login_per_min: int = 10
    ratelimit_signup_per_min: int = 5
    ratelimit_token_per_min: int = 20
    ratelimit_upload_per_min: int = 60

    # --- storage / binary ---
    # Where uploaded/generated session files live (host path, bind-mounted).
    storage_dir: Path = _PLATFORM_ROOT / "storage"
    # The KooRemapper binary the runner executes (copied by CMake POST_BUILD).
    kooremapper_bin: Path = _PLATFORM_ROOT / "backend" / "bin" / "KooRemapper"
    # Per-job wall-clock timeout (seconds).
    job_timeout_sec: int = 1800
    # Concurrent runner workers.
    worker_concurrency: int = 4
    # Max single-file upload size (MB).
    max_upload_mb: int = 512

    # --- AI Data Hub (시뮬레이션 리포트 등재 대상) ---
    # 비우면 publish-datahub 비활성(400). 기본은 호스트 네트워크 공유 인스턴스.
    datahub_url: str = "http://127.0.0.1:8001"

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
        # Treat empty/"." (pydantic coerces "" → Path(".")) as "not configured".
        p = self.serve_frontend_dist
        if p is None or str(p) in ("", "."):
            return None
        return p

    def model_post_init(self, _ctx) -> None:
        # In production, refuse to run with the dev placeholder secrets.
        if not self.is_development:
            insecure = []
            if self.jwt_secret == "dev-insecure-change-me":
                insecure.append("KOORM_JWT_SECRET")
            if "koorm:koorm@" in self.database_url:
                insecure.append("KOORM_DATABASE_URL (default password)")
            if insecure:
                raise RuntimeError(
                    "Refusing to start in production with default secrets: "
                    + ", ".join(insecure)
                )

    def __repr__(self) -> str:  # never leak secrets in logs/tracebacks
        return (
            f"Settings(app_env={self.app_env!r}, api_port={self.api_port}, "
            f"jwt_secret=***, database_url=***, storage_dir={self.storage_dir})"
        )

    __str__ = __repr__


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
