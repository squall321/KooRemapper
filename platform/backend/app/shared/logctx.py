# 로그 한 줄에 시각과 상관자를 넣는다 — 사용자가 본 실패를 서버 줄과 맞추기 위해
"""왜 이 모듈이 있나 (2026-09-29, 진단 체계).

실패했을 때 사용자가 넘긴 것과 서버 로그를 맞출 방법이 **아예 없었다.**

  · `app/main.py` 가 `logging.basicConfig(level=INFO)` 뿐이라 로그 줄에 **시각이 없었다.**
    "14:30 에 실패했다" 를 로그와 맞출 수가 없다.
  · 사용자가 본 에러와 서버 줄을 잇는 id 가 없었다.

그래서 두 가지를 한다 — 포맷에 `asctime` 과 상관자를 넣고, 요청마다 상관자를 만든다(또는 들어온
`X-Request-Id` 를 그대로 쓴다). 잡 구간에서는 상관자가 **잡 id** 다. 그러면 잡 기록과 로그 줄이
같은 문자열로 만난다.

⚠ uvicorn 자신의 로거(`uvicorn.access` 등)는 `propagate=False` 로 **자기 핸들러**를 쓰므로 이
포맷이 닿지 않는다. 그 줄에 시각을 넣으려면 `--log-config` 를 줘야 하는데, 그 명령줄은 `api.def`
의 `%runscript` 에 있고 그것은 **SIF 에 구워진다**(재빌드가 필요하다). 그래서 대신 요청 한 줄을
**우리가** 찍는다(미들웨어). 그것이 상관자를 들고 있으니 어차피 그쪽이 정본이다.

⚠ `/api/health` 는 찍지 않는다. 감독자가 **분당** 폴링해서 `koorm_api.out` 의 health 줄이 1,461개다
(2026-09-29 실측). 감독자 로그가 59% 심장박동이던 것과 같은 병이고(P1-10 ②), 읽을 수 없는 로그는
번들에 넣어도 쓸모가 없다.
"""
from __future__ import annotations

import contextvars
import logging
import re
import uuid

# 상관자가 없을 때의 표시. 빈 문자열로 두면 `[]` 가 되어 grep 하기 나쁘다.
NONE = "-"

_corr: contextvars.ContextVar[str] = contextvars.ContextVar("koorm_corr", default=NONE)

# 바깥에서 들어온 값을 그대로 쓰지 않는다 — 로그 줄에 개행이나 제어문자가 섞이면 한 줄이
# 여러 줄로 갈라져 grep 이 어긋난다(로그 주입).
_SAFE = re.compile(r"[^A-Za-z0-9._-]")


def new_correlator() -> str:
    return uuid.uuid4().hex[:16]


def sanitize(raw: str) -> str:
    """바깥에서 받은 상관자를 안전하게 줄인다. 쓸 게 남지 않으면 새로 만든다."""
    cleaned = _SAFE.sub("", raw or "")[:64]
    return cleaned or new_correlator()


def set_correlator(value: str):
    """토큰을 돌려준다 — 끝나면 `reset_correlator` 로 되돌린다."""
    return _corr.set(value)


def reset_correlator(token) -> None:
    _corr.reset(token)


def get_correlator() -> str:
    return _corr.get()


class CorrelatorFilter(logging.Filter):
    """모든 레코드에 `corr` 를 붙인다. 없으면 `-`."""

    def filter(self, record: logging.LogRecord) -> bool:  # noqa: A003
        record.corr = _corr.get()
        return True


class HealthNoiseFilter(logging.Filter):
    """`/api/health` 접근 줄을 접는다 — 감독자가 분당 폴링한다."""

    def filter(self, record: logging.LogRecord) -> bool:  # noqa: A003
        try:
            return "/api/health" not in record.getMessage()
        except Exception:
            return True


FORMAT = "%(asctime)s %(levelname)s %(name)s [%(corr)s] %(message)s"


def setup_logging(level: int = logging.INFO) -> None:
    """루트 로거에 시각+상관자 포맷을 세운다. `basicConfig` 를 대신한다.

    ⚠ `force=True` 다. uvicorn 이 먼저 핸들러를 붙이는 경우가 있어, 그대로 두면 우리 포맷이
    무시되고 시각 없는 줄이 계속 나온다.
    """
    logging.basicConfig(level=level, format=FORMAT, force=True)
    f = CorrelatorFilter()
    for h in logging.getLogger().handlers:
        h.addFilter(f)
    # uvicorn 의 접근 로거는 자기 핸들러를 쓰므로 포맷은 못 바꾼다. 소음만 접는다.
    logging.getLogger("uvicorn.access").addFilter(HealthNoiseFilter())
