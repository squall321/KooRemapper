# 게이트웨이가 서명해 보낸 '이 사람의 소속' 을 검증한다 — 리포트 소속 단위 읽기 공유의 판정 근거
"""소속 헤더는 두 장이다(포털 요청서 platform/docs/REQUEST-postprocess-operation.md §8, 2026-09-18 개정).

    X-Heax-User-Affiliation: CAEG            소속 id(퍼센트 인코딩)
    X-Heax-Aff-Proof:        v1.<exp>.<hmac> "게이트웨이가 이 사람에게 찍었다" 는 증명

⚠ 헤더 하나만 믿으면 **권한 상승**이다. 사용자는 게이트웨이를 거치지 않고 자기 kr_ PAT 로
앱 MCP·REST 에 직접 붙어 소속 헤더를 스스로 적을 수 있고, HEAXHub Caddy 가 지워 주는 위조 헤더는
X-Heax-User-Email·X-Heax-User-Name 둘뿐이다. 그래서 서명을 검증한다.

서명은 지금 인증된 사용자(PAT 주인)의 이메일에 묶인다 — 증명을 가로채도 남의 호출에는 못 쓴다.
키는 새로 만들지 않고 SSO 가 이미 쓰는 settings.heax_gateway_secret 을 쓴다.
시크릿이 없으면 항상 '소속 없음' 이다(SSO 와 같은 '닫히는' 자세).

빈 문자열은 '소속 없음' 이며, 소속 없는 사람끼리 서로의 리포트를 읽는 길이 되면 안 되므로
호출부는 빈 값을 매칭에 쓰지 않는다(shared/visibility.py 가 team·department 에서 지키는 규칙과 같다).
"""
from __future__ import annotations

import hashlib
import hmac
import time
from typing import Mapping
from urllib.parse import unquote

AFFILIATION_HEADER = "x-heax-user-affiliation"
PROOF_HEADER = "x-heax-aff-proof"


def verified_affiliation(headers: Mapping[str, str], user_email: str, secret: str) -> str:
    """게이트웨이가 이 사람에게 찍은 소속 id. 하나라도 안 맞으면 "" (= 소속 없음)."""
    if not secret or not user_email:
        return ""
    raw = headers.get(AFFILIATION_HEADER) or headers.get(AFFILIATION_HEADER.title()) or ""
    proof = headers.get(PROOF_HEADER) or headers.get(PROOF_HEADER.title()) or ""
    aff = unquote(raw)                      # 서명 대상은 푼 값이다(소속 id 에 한글이 올 수 있다)
    if not aff or not proof:
        return ""
    try:
        ver, exp, sig = proof.split(".")
        exp_i = int(exp)
    except ValueError:
        return ""
    if ver != "v1" or exp_i < time.time():  # 만료된 증명은 받지 않는다
        return ""
    msg = f"v1|{user_email.strip().lower()}|{aff}|{exp_i}"
    want = hmac.new(secret.encode(), msg.encode(), hashlib.sha256).hexdigest()
    return aff if hmac.compare_digest(sig, want) else ""
