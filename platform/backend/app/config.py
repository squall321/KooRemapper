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


# 안내 문구에 쓰는 **실제** 환경변수 이름. 문자열을 따로 적으면 접두사가 빠진 채 굳는다
# (실제로 그랬다 — 안내는 `MCP_PUBLIC_URL` 이라 했는데 읽히는 키는 KOORM_ 접두사가 붙은 쪽이다).
MCP_PUBLIC_URL_ENV = "KOORM_MCP_PUBLIC_URL"


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
    # 외부 클라이언트 안내용 MCP 공개 주소. **비우면 안내를 내지 않는다**(지어내지 않는다 — 요청서
    # REQUEST-deploy-fixes-20260919 ④). raw host:port 는 사외 PC 에서 안 닿고, X-Forwarded-Host 로
    # 만든 값은 실측 세 경로 중 둘이 틀렸다(포트 유실·내부 주소). 포털 경유면
    # https://<포털오리진:포트>/apps/kooremapper_mcp/mcp 가 정본이다.
    mcp_public_url: str = ""

    # --- database ---
    # asyncpg DSN, e.g. postgresql+asyncpg://koorm:pw@127.0.0.1:5436/koorm
    # 포트 5436 — 5433 은 Debian/Ubuntu 의 두 번째 시스템 PostgreSQL 클러스터가 쓴다.
    # 배정표: HWAXPortal/docs/PORT-MAP.md. 바꿀 때 platform/.env 의 POSTGRES_PORT 와 함께.
    database_url: str = "postgresql+asyncpg://koorm:koorm@127.0.0.1:5436/koorm"

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
    # 진단 번들이 서버 줄을 골라낼 API 인스턴스 로그 폴더. 비우면
    # `~/.apptainer/instances/logs/<host>/<user>` 를 훑는다 — 컨테이너에서 홈이 안 보이는 배치는
    # 이 값을 준다(KOORM_INSTANCE_LOG_DIR).
    instance_log_dir: str = ""
    # Per-job wall-clock timeout (seconds).
    job_timeout_sec: int = 1800
    # Concurrent runner workers.
    worker_concurrency: int = 4
    # job 자식 앞에 붙이는 실행기(launcher) 명령 한 줄. `shlex.split` 으로 나눈다. 비우면 지금처럼 바이너리를
    # 이 프로세스의 자식으로 바로 띄운다. 값이 있으면 `<실행기…> --job-id <id> --kind <연산> -- <바이너리> <argv…>`
    # 로 띄우고, 노드 선택 · 원격 실행 · 남은 프로세스 정리는 실행기가 한다(KOORM_JOB_LAUNCHER).
    # ⚠ 이 값은 잡마다 env_snapshot 에 그대로 남는다 — 실행기의 비밀은 인자가 아니라 파일로 준다.
    job_launcher: str = ""
    # 실행기를 쓸 때, 시간 초과에 SIGTERM 을 보낸 뒤 SIGKILL 까지 기다리는 초. 실행기가 원격 job 을 끝내고
    # 나올 틈이다 — 바로 죽이면 원격이 아직 쓰는 파일을 출력으로 등록한다(KOORM_JOB_TERM_GRACE_SEC).
    job_term_grace_sec: int = 5
    # Max single-file upload size (MB) — 전송(멀티파트) 상한. .gz 는 이 압축 크기에 걸린다.
    max_upload_mb: int = 512
    # 리포트 HTML 압축 해제 후 상한 (MB) — .gz 를 서버가 풀 때의 크기 가드(zip-bomb·메모리 보호).
    # 대용량(GB) 리포트는 .gz 로 올리면 전송은 작고 여기서만 크기를 본다. 필요 시 KOORM_MAX_REPORT_MB.
    max_report_mb: int = 2048

    # --- 레시피 샌드박스(docs/01-plan/features/recipes-1026.plan.md) ---
    # LLM 이 올린 분석 함수를 격리해서 돌릴 때의 상한. 이 박스는 earlyoom 이 가용 6% 아래면 남의
    # 프로세스를 죽이므로(box-earlyoom-collateral) 메모리 상한은 선택이 아니다.
    recipe_sandbox_mem_mb: int = 2048          # RLIMIT_AS — 가상 메모리 상한
    recipe_sandbox_fsize_mb: int = 32          # RLIMIT_FSIZE — 결과·로그 파일 하나당 상한
    recipe_selftest_timeout_sec: int = 60      # 제안 때 자기 시험(API 안에서 바로)
    recipe_run_timeout_sec: int = 180          # 실데이터 실행(플랫폼 잡)
    recipe_selftest_concurrency: int = 2       # API 안에서 동시에 도는 자기 시험 수
    recipe_result_cap_kb: int = 256            # DB 에 담는 결과 상한(넘으면 앞부분 + 산출 파일)
    recipe_stdout_cap_kb: int = 32             # 실행 기록에 담는 stdout 꼬리 상한
    # 등록된 레시피를 파일로 내보내는 자리(기동 때 여기서 읽어 들인다). 상대값이면 platform/ 기준.
    recipe_export_dir: str = "recipes"

    # --- stcx(356대 클러스터) 전각도 낙하 — 게이트웨이 MCP 경유 ---
    # **파일을 나른다.** cae00 `/data` 와 stcx `/data` 는 다른 저장소다 — 같은 경로를 보지
    # 않으므로 제출 전에 stcx 대시보드(:5010)의 청크 업로드로 덱을 올려야 한다.
    # 아래 넷 중 **하나라도 비면 이 작업은 꺼진 것**이고, 제출은 조용히 성공하지 않고
    # 명시적으로 실패한다. 경로·주소·IP 는 박스마다 다르므로 코드에 기본값을 박지 않는다.
    gateway_mcp: str = "http://127.0.0.1:9110/mcp"
    gateway_pat: str = ""
    # 반입 API 주소(터널). 예 `http://127.0.0.1:15010` — 끝의 `/` 는 있어도 없어도 된다.
    stcx_backend_url: str = ""
    # 헤드노드의 작업 루트. 잡마다 `<root>/<DynaForge job id>` 로 갈라 쓴다.
    stcx_work_root: str = ""
    # LS-DYNA 라이선스 서버 IPv4. 받는 쪽 스키마가 IPv4 꼴만 받는다.
    stcx_lstc_ip: str = ""
    # 외부 잡 상태를 다시 보기까지의 간격(초). 시간 단위 잡이라 짧게 두드리지 않는다.
    # 처음엔 자주, 그다음 늘린다 — _next_poll_delay 가 이 둘 사이를 지수로 오간다.
    stcx_poll_min_sec: int = 30
    stcx_poll_max_sec: int = 600

    # --- 후처리 예약(7-1) — KooSlurm 귀환 매니페스트를 기다려 리포트를 예약자 명의로 반입 ---
    # 주소는 위 `stcx_backend_url` 을 **같이 쓴다.** 덱 업로드(`/api/v2/files/upload/*`)와 잡 REST
    # (`/api/jobs/<id>/files/download`)는 같은 대시보드(backend_5010)에 있다 — 둘로 두면 어긋난다.
    # 예약자의 kst_ PAT 를 잡 동안 맡아 두는 암호화 키. 비면 jwt_secret 에서 끌어낸다(tokenbox).
    token_key: str = ""
    # 매니페스트를 기다리는 기한(일). 지나면 잡을 실패로 닫고 맡은 토큰을 지운다.
    postprocess_wait_days: int = 7
    # KooSlurm 호출 한 번의 상한(초). 리포트 내려받기에는 읽기 사이 간격으로 걸린다.
    kooslurm_timeout_sec: float = 30

    # --- SP 허브 코어 API (과제·개발모델 기준정보 수신) ---
    # **받기만 한다.** 과제의 정본은 허브다 — 우리 화면에서 고치면 다음 받기가 덮어쓰고
    # 그 사실은 고친 사람에게 안 보인다(SP `ontology/managed.py`).
    # 주소가 비면 수신은 **꺼진 것**이고, 조용히 성공하지 않고 명시적으로 실패한다.
    sp_core_url: str = ""          # 예 `https://<허브>/api` — 끝의 `/` 는 있어도 없어도 된다
    sp_core_token: str = ""        # `core:read` 범위 PAT. `.env` 에 둔다(§7 ④)
    # 받을 타입(쉼표). 기본은 **쓰는 것 셋**이다 — 공개 35종을 다 받지 않는다(KR-06). 공개 안 된
    # 타입이 끼어도 **거절하지 않고 건너뛰며 알린다**(응답 `skipped`). 비우면 공개된 것 전부.
    sp_core_types: str = "plm_project,plm_task,plm_model"
    # 한 쪽에 몇 건을 받나. 허브가 더 작게 줄 수 있다 — 그때는 허브가 준 `next` 를 따른다.
    sp_core_page_size: int = 500
    # 주기 수신 간격(초). **0 이면 주기 수신만 끈다**(기능 자체는 `ontology` 가 정한다).
    # 기본을 시간 단위로 두는 이유 — 주소·토큰을 넣은 사람이 **간격까지 또 설정해야 하면**
    # 그 둘째를 잊는다. 주소·토큰이 없으면 어차피 안 돈다(`plm_sync.enabled()`).
    sp_core_sync_sec: int = 3600
    # 과제·개정(온톨로지) 기능 스위치. **비우면 있는 것으로 정한다** — 주소·토큰이 둘 다
    # 있으면 켜고 없으면 끈다. 포탈이 옵션으로 `1`/`0` 을 내려 주면 그 값이 이긴다.
    # 판정은 `app/shared/features.py` 한 곳에서 한다(두 곳에서 하면 화면과 API 가 갈린다).
    ontology: str = ""

    # --- AI Data Hub (시뮬레이션 리포트 등재 대상) ---
    # 비우면 publish-datahub 비활성(400). 기본은 호스트 네트워크 공유 인스턴스.
    datahub_url: str = "http://127.0.0.1:8001"

    # --- ReportArchive pull 연동 ---
    # 목록 응답의 file_url 에 쓸 외부 베이스 URL. 비우면 요청의 base_url 을 쓴다.
    # 포탈 서브패스(/apps/kooremapper) 뒤라 내부 base 와 다르면 여기에 외부 URL 을 넣는다.
    analysis_public_base_url: str = ""
    # 이 DynaForge 인스턴스 식별자(예: "dynaforge-cae00"). 여러 DynaForge → 하나의
    # ReportArchive 로 모을 때 각 결과가 어느 인스턴스에서 왔는지 표시한다(provenance).
    # run_key 자체는 ULID 라 전역 유일하므로 여기 값은 표시·그룹핑용이고 dedup 엔 안 쓴다.
    # 한 번 정하면 안정적으로 유지한다(바꾸면 site 표시만 바뀌고 run_key 는 그대로).
    analysis_site_id: str = ""

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

    @property
    def recipe_export_path(self) -> Path:
        """등록된 레시피를 파일로 내보내는 절대 경로. 상대값이면 platform/ 기준으로 푼다."""
        p = Path(self.recipe_export_dir)
        return p if p.is_absolute() else (_PLATFORM_ROOT / p)

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
