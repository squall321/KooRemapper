#!/usr/bin/env python3
# 후처리 예약 · 반입(7-1)과 stcx 제출 설정 점검 — 값은 출력하지 않고 「어느 칸이 비었나 · 백엔드에 닿나」 만 본다
"""dev(또는 cae00) DynaForge 의 stcx · KooSlurm 설정 점검 (2026-11-12, 포털 낙하 파이프라인 2번).

  python3 platform/infra/scripts/check-postprocess.py                 # 칸 · 닿음만 본다(토큰을 받지 않는다)
  python3 platform/infra/scripts/check-postprocess.py --email a@b.c   # + 이 사람 명의로 위임 창구에서 토큰을 받아 본다

무엇을 보나.
  · 후처리 예약 · 반입(7-1)에 필요한 칸 — KOORM_STCX_BACKEND_URL · KOORM_KOOSLURM_SSO_SECRET.
    stcx 제출(전각도 낙하)에는 여기에 KOORM_GATEWAY_PAT · KOORM_STCX_WORK_ROOT · KOORM_STCX_LSTC_IP 가 더 든다.
  · 위임 창구 `<KOORM_STCX_BACKEND_URL>/api/auth/sso` 에 **비밀 없이** 한 번 — 거절(401/403/400)이면 창구가 있다.
    200 이면 비밀 없이 토큰을 주는 것이라 위험으로 알린다.
  · --email 을 주면 그 사람 명의로 토큰을 실제로 받는다(토큰이 발급된다 — 그래서 명시할 때만). 토큰은 출력하지 않는다.
  · KOORM_GATEWAY_PAT 가 있으면 게이트웨이(KOORM_GATEWAY_MCP, 기본 :9110/mcp)에 initialize 한 번.

값은 어디에도 출력하지 않는다 — 칸 이름과 「있음 / 비었음」, HTTP 상태만. 설정 파일은 platform/.env(앱이 읽는 것과 같은 것)이고
같은 이름의 환경변수가 있으면 그것이 이긴다(앱과 같다).
"""
import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

ENV_FILE = Path(__file__).resolve().parents[2] / ".env"
RESERVE = ("KOORM_STCX_BACKEND_URL", "KOORM_KOOSLURM_SSO_SECRET")
SUBMIT = ("KOORM_GATEWAY_PAT", "KOORM_STCX_WORK_ROOT", "KOORM_STCX_LSTC_IP")
SSO_PATH = "/api/auth/sso"            # app/runner/kooslurm_client.py 와 같다
# 클라이언트 이름도 앱과 같아야 한다 — KooSlurm 은 허용 목록으로 거른다(다르면 맞는 비밀이어도 400 「알 수 없는 클라이언트」).
SSO_CLIENT = "dynaforge"
_TOKEN = re.compile(r"\b(kst|kr|hx)_[A-Za-z0-9_\-]{8,}")


def load_env(path: Path) -> dict:
    out = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            s = line.strip()
            if not s or s.startswith("#") or "=" not in s:
                continue
            k, v = s.split("=", 1)
            v = v.strip()
            if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
                v = v[1:-1]
            out[k.strip()] = v
    for k in RESERVE + SUBMIT + ("KOORM_GATEWAY_MCP",):
        if os.environ.get(k):
            out[k] = os.environ[k]
    return out


def post(url: str, headers: dict, body: bytes = b"", timeout: float = 10.0):
    """→ (HTTP 상태 또는 None, 짧은 까닭). 본문은 옮기지 않는다(토큰이 섞일 수 있다)."""
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read(65536)
    except urllib.error.HTTPError as e:
        return e.code, e.read(4096)        # 거절 까닭 — 찍을 때 _reason 이 토큰을 가린다
    except (urllib.error.URLError, OSError, ValueError) as e:
        return None, _TOKEN.sub("<token>", str(getattr(e, "reason", e)))[:120]


def _reason(body) -> str:
    """거절 본문의 까닭 한 줄(토큰 꼴은 가린다) — 비밀 불일치(401)와 사용자 · 클라이언트 거절(400)을 가르려고."""
    try:
        txt = body.decode("utf-8", "replace") if isinstance(body, bytes) else str(body)
        o = json.loads(txt) if txt.strip().startswith("{") else {}
        txt = str(o.get("error") or o.get("detail") or o.get("message") or txt)
    except ValueError:
        pass
    return _TOKEN.sub("<token>", txt.strip())[:160]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--email", help="이 사람 명의로 위임 창구에서 토큰을 받아 본다(토큰은 출력하지 않는다)")
    ap.add_argument("--env-file", default=str(ENV_FILE), help=argparse.SUPPRESS)
    a = ap.parse_args(argv)
    env = load_env(Path(a.env_file))
    bad = []

    print(f"[설정] {a.env_file}" + ("" if Path(a.env_file).exists() else "  (없다)"))
    for title, keys in (("후처리 예약 · 반입(7-1)", RESERVE), ("stcx 제출(전각도 — 위에 더해)", SUBMIT)):
        print(f"  {title}")
        for k in keys:
            have = bool(env.get(k, "").strip())
            print(f"    {k:28s} {'있음' if have else '비었음'}")
            if not have and keys is RESERVE:
                bad.append(k)

    url = env.get("KOORM_STCX_BACKEND_URL", "").strip().rstrip("/")
    if url:
        print(f"[위임 창구] POST …{SSO_PATH} (비밀 없이)")
        code, why = post(url + SSO_PATH, {"X-Heax-Client": SSO_CLIENT})
        if code is None:
            print(f"    닿지 않는다 — {why}")
            bad.append("위임 창구에 닿지 않음")
        elif code in (400, 401, 403):
            print(f"    HTTP {code} — 창구가 있고 비밀 없이는 거절한다(정상)")
        elif code == 404:
            print("    HTTP 404 — 창구가 없다(주소 · KooSlurm 판 확인)")
            bad.append("위임 창구 404")
        elif code == 200:
            print("    HTTP 200 — ⚠ 비밀 없이 토큰을 준다(위임 창구가 열려 있다 — KooSlurm 쪽에 알릴 것)")
        else:
            print(f"    HTTP {code} — 뜻을 모른다")
        secret = env.get("KOORM_KOOSLURM_SSO_SECRET", "").strip()
        if a.email:
            if not secret:
                print("    --email 을 줬지만 KOORM_KOOSLURM_SSO_SECRET 이 비었다 — 받아 보지 않는다")
            else:
                h = {"X-Heax-Gateway-Secret": secret, "X-Heax-User-Email": a.email,
                     "X-Hwax-Delegate-Email": a.email, "X-Heax-Client": SSO_CLIENT}
                code, body = post(url + SSO_PATH, h)
                tok = isinstance(body, bytes) and _TOKEN.search(body.decode("utf-8", "replace") or "")
                if code == 200 and tok:
                    try:
                        user = json.loads(body).get("username") or "?"
                    except ValueError:
                        user = "?"
                    print(f"    {a.email} 명의 토큰을 받았다(username={user}) — 비밀이 KooSlurm 과 맞는다")
                else:
                    why = body if not code else _reason(body)
                    print(f"    {a.email} 명의로 못 받았다 — HTTP {code}" + (f" ({why})" if why else "")
                          + (" · 비밀(HEAX_GATEWAY_SECRET)이 KooSlurm 과 다르다" if code == 401 else ""))
                    bad.append("위임 창구 토큰 받기 실패")

    pat = env.get("KOORM_GATEWAY_PAT", "").strip()
    if pat:
        gw = env.get("KOORM_GATEWAY_MCP", "").strip() or "http://127.0.0.1:9110/mcp"
        print("[게이트웨이] initialize (KOORM_GATEWAY_PAT)")
        body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                           "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                                      "clientInfo": {"name": "dynaforge-check", "version": "1"}}}).encode()
        code, why = post(gw, {"Authorization": f"Bearer {pat}", "Content-Type": "application/json",
                              "Accept": "application/json, text/event-stream"}, body)
        print(f"    {'HTTP %d' % code if code else '닿지 않는다 — ' + str(why)}"
              + (" — PAT 가 받아들여졌다" if code == 200 else " — PAT · 주소를 본다" if code else ""))

    print()
    if bad:
        print("후처리 예약 · 반입: 아직 — " + " · ".join(bad))
        return 1
    print("후처리 예약 · 반입: 설정 칸과 위임 창구가 갖춰졌다(--email 로 명의 확인을 해 볼 수 있다)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
