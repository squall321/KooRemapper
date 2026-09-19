# 게이트웨이 소속 증명 검증 — 서명·이메일 결속·만료·시크릿 미설정을 못으로 박는다
"""요청서 platform/docs/REQUEST-postprocess-operation.md §8(2026-09-18 개정).

헤더 하나만 믿으면 권한 상승이다 — 사용자가 게이트웨이를 거치지 않고 자기 PAT 로 직접 붙어
소속 헤더를 스스로 적을 수 있다. 그래서 HMAC 증명을 검증하고, 아래를 전부 빨갛게 잡아야 한다.
"""
import hashlib
import hmac
import time

from app.shared.affiliation import verified_affiliation

SECRET = "test-gateway-secret"
EMAIL = "kim@heax.local"


def sign(email: str, aff: str, exp: int, secret: str = SECRET) -> str:
    msg = f"v1|{email.strip().lower()}|{aff}|{exp}"
    return "v1.%d.%s" % (exp, hmac.new(secret.encode(), msg.encode(), hashlib.sha256).hexdigest())


def headers(aff: str, proof: str) -> dict:
    return {"x-heax-user-affiliation": aff, "x-heax-aff-proof": proof}


def test_valid_proof_returns_affiliation():
    exp = int(time.time()) + 60
    assert verified_affiliation(headers("CAEG", sign(EMAIL, "CAEG", exp)), EMAIL, SECRET) == "CAEG"


def test_percent_encoded_id_is_unquoted_before_verify():
    # 소속 id 에 한글이 올 수 있고 헤더는 latin-1 만 담는다 — 서명 대상은 푼 값이다
    exp = int(time.time()) + 60
    aff = "설계1팀"
    from urllib.parse import quote
    h = headers(quote(aff), sign(EMAIL, aff, exp))
    assert verified_affiliation(h, EMAIL, SECRET) == aff


def test_no_proof_is_no_affiliation():
    assert verified_affiliation({"x-heax-user-affiliation": "CAEG"}, EMAIL, SECRET) == ""


def test_proof_not_bound_to_caller_is_rejected():
    # 남의 호출에서 훔친 증명은 못 쓴다(이메일을 서명에 넣은 이유)
    exp = int(time.time()) + 60
    stolen = sign("lee@heax.local", "CAEG", exp)
    assert verified_affiliation(headers("CAEG", stolen), EMAIL, SECRET) == ""


def test_expired_proof_is_rejected():
    exp = int(time.time()) - 1
    assert verified_affiliation(headers("CAEG", sign(EMAIL, "CAEG", exp)), EMAIL, SECRET) == ""


def test_wrong_secret_is_rejected():
    exp = int(time.time()) + 60
    other = sign(EMAIL, "CAEG", exp, secret="someone-elses-secret")
    assert verified_affiliation(headers("CAEG", other), EMAIL, SECRET) == ""


def test_affiliation_swapped_after_signing_is_rejected():
    exp = int(time.time()) + 60
    proof = sign(EMAIL, "CAEG", exp)
    assert verified_affiliation(headers("EXEC", proof), EMAIL, SECRET) == ""


def test_missing_secret_closes():
    exp = int(time.time()) + 60
    assert verified_affiliation(headers("CAEG", sign(EMAIL, "CAEG", exp)), EMAIL, "") == ""


def test_bad_version_is_rejected():
    exp = int(time.time()) + 60
    proof = sign(EMAIL, "CAEG", exp).replace("v1.", "v2.", 1)
    assert verified_affiliation(headers("CAEG", proof), EMAIL, SECRET) == ""


def test_malformed_proof_is_rejected():
    for bad in ("", "v1", "v1.notanint.deadbeef", "junk"):
        assert verified_affiliation(headers("CAEG", bad), EMAIL, SECRET) == ""
