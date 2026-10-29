# 다른 서비스의 사용자 PAT 처럼 잠깐 맡는 비밀을 암호문으로만 두는 상자(Fernet)
"""왜 있나 — 후처리 예약(7-1)은 예약한 사용자 본인의 KooSlurm PAT(`kst_…`)로 그 사람의 잡 파일을
읽는다(사용자 결정 10-28). 잡은 며칠을 기다리므로 토큰을 그동안 들고 있어야 한다. 평문으로 두면
DB 덤프 · 진단 번들 · 로그 한 줄로 남의 클러스터 신원이 샌다. 그래서 **암호문만** 잡 행에 두고,
쓰는 순간에만 푼다. 잡이 끝나면(성공 · 실패 · 취소 · 기한) 암호문도 지운다 — 그것은 부르는 쪽 몫이다.

키는 `KOORM_TOKEN_KEY`, 없으면 `jwt_secret` 이다. 어느 쪽이든 HKDF 로 32바이트를 끌어내므로 아무
길이의 문자열을 줘도 된다. 키가 바뀌면 이미 맡은 토큰은 풀리지 않는다 — `unseal` 이 None 을 돌려주고,
부르는 쪽이 그 잡을 「토큰을 풀 수 없다」 로 분명히 닫는다(조용히 다른 신원으로 가지 않는다).
"""
from __future__ import annotations

import base64

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from app.config import settings

# 용도를 키에 섞는다 — 같은 jwt_secret 에서 끌어낸 다른 키와 겹치지 않게.
_INFO = b"koorm-tokenbox-v1"


def _fernet() -> Fernet:
    material = (settings.token_key or "").strip() or settings.jwt_secret
    key = HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=_INFO).derive(material.encode())
    return Fernet(base64.urlsafe_b64encode(key))


def seal(plain: str) -> str:
    """평문 → 암호문(문자열). 빈 값은 받지 않는다 — 부르는 쪽이 먼저 거른다."""
    return _fernet().encrypt(plain.encode()).decode()


def unseal(sealed: str) -> str | None:
    """암호문 → 평문. 못 풀면(키가 바뀜 · 깨짐) None."""
    try:
        return _fernet().decrypt(str(sealed).encode()).decode()
    except (InvalidToken, ValueError):
        return None
