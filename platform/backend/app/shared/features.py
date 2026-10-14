# 기능 스위치 — **옵션이 없으면 있는 것으로 정한다**(명시가 추론을 이긴다)
"""포탈이 앱의 `.env` 를 내려 주는 자리가 이미 있다(HWAXPortal `setup_requests.yaml` —
`platform/.env` 에 값을 넣고 `start.sh` 가 컨테이너로 넘긴다). 그래서 스위치도 **환경변수
하나**다. 포탈에 새 프로토콜을 만들지 않는다.

규칙 셋 —

    ① 옵션을 명시하면 그 값이 이긴다       `KOORM_ONTOLOGY=1` · `=0`
    ② 비우면 **있는 것으로 정한다**         허브 주소·토큰이 둘 다 있으면 켜고, 없으면 끈다
    ③ 꺼지면 **없어진다**                   화면에서 사라지고 API 도 거절한다

★②가 요점이다. 옵션을 안 건드린 박스에서 기능이 조용히 꺼져 있으면 "왜 안 보이나" 를
아무 데서도 알 수 없다. 반대로 주소·토큰을 넣었는데도 스위치를 따로 켜야 하면 **두 번 설정
해야 하는 기능**이 되고, 둘째를 잊는다.

★③도 요점이다. 화면에서만 숨기고 API 가 계속 답하면 그것은 꺼진 것이 아니라 **숨긴 것**이다.
그리고 "꺼짐" 과 "고장" 을 **같은 모양으로 만들지 않는다** — 꺼짐은 사유를 말한다.
"""
from __future__ import annotations

from app.config import settings

_TRUE = {"1", "true", "yes", "on", "y"}
_FALSE = {"0", "false", "no", "off", "n"}


def ontology_state() -> dict:
    """과제·개정(온톨로지) 기능의 상태. `{"enabled", "source", "reason", "missing"}`.

    `source` 는 `option`(명시) 또는 `inferred`(있는 것으로 정함)다 — 화면과 포탈이
    "누가 이렇게 정했나" 를 말할 수 있어야 한다.
    """
    url = (settings.sp_core_url or "").strip()
    token = (settings.sp_core_token or "").strip()
    missing = [name for name, v in (("KOORM_SP_CORE_URL", url),
                                    ("KOORM_SP_CORE_TOKEN", token)) if not v]

    raw = (settings.ontology or "").strip().lower()
    if raw in _FALSE:
        return {"enabled": False, "source": "option", "missing": missing,
                "reason": "옵션에서 껐다(KOORM_ONTOLOGY=0)"}
    if raw in _TRUE:
        # 켜라고 했으면 켠다 — 허브가 없어도 개정 잇기는 돈다(과제 확인만 못 한다).
        return {"enabled": True, "source": "option", "missing": missing,
                "reason": ("옵션에서 켰다(KOORM_ONTOLOGY=1)" if not missing else
                           "옵션에서 켰다 — 다만 허브 설정이 없어 과제를 받지 못한다: "
                           + " · ".join(missing))}
    if raw:
        # 알 수 없는 값을 **조용히 꺼짐으로 접지 않는다** — 오타가 기능을 없애는 일이다.
        return {"enabled": bool(not missing), "source": "inferred", "missing": missing,
                "reason": f"KOORM_ONTOLOGY={raw!r} 를 못 읽었다(1/0 을 쓴다) — 있는 것으로 정했다"}
    if missing:
        return {"enabled": False, "source": "inferred", "missing": missing,
                "reason": "허브 설정이 없다 — " + " · ".join(missing)
                          + ". 포탈의 설정 항목을 보라(KOORM_ONTOLOGY=1 로 강제할 수도 있다)"}
    return {"enabled": True, "source": "inferred", "missing": [],
            "reason": "허브 주소·토큰이 있어 켰다"}


def ontology_enabled() -> bool:
    return bool(ontology_state()["enabled"])
