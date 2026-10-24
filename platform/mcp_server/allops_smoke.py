# 카탈로그 예제가 있는 op 을 살아 있는 플랫폼에서 하나씩 끝까지 부르는 전수 스모크 — 스모크가 안 부른 op 은 플랫폼에서 안 잰 것이다
"""KooRemapper 플랫폼 op 전수 스모크 (2026-10-24).

왜 이것이 따로 있나.

  2026-10-24 — 관문이 전부 초록이고 덱 op 스모크가 21/21 이었는데, 플랫폼에서 `type` 을 준 contact create 가 **늘** 실패했다
  (「YAML has no contact actions」). argbuild 는 잡 인자(JSONB — 키 순서를 잃는다)를 받아 `type` 부터 쓰는데 contact 파서는
  `- action` 으로 시작하는 항목만 알아봤다. `deckops_smoke.py` 는 새 덱 op 여섯만 불러 contact 를 한 번도 안 불렀다.

  그래서 카탈로그(`kooremapper_core/catalog_data.json`)의 `example` 이 있는 op 을 **전부** 플랫폼으로 부른다 — 예제 폴더를
  회귀(`tools/regress/test_newline_matrix.py`)와 같은 규칙으로 스테이징하고(선언된 픽스처 · 사전 단계 포함), 그 파일을 세션에
  올리고, 예제 인자 그대로 잡을 던진다. 판정은 「잡이 succeeded 이고, 파일을 내는 op 이면 산출물이 왔나」 다 — 내용은 각 op 의
  회귀가 본다. 통과하려면 바이너리 · 카탈로그 · API · MCP 프로세스가 모두 최신이어야 한다.

  빼는 것 — `stcx_fullangle_drop`(외부 클러스터에 진짜 잡을 낸다). 콘솔만 쓰는 op(info · neutralaxis)은 산출물을 보지 않는다.

  `smoke.py` 와 같은 전제(api+mcp+postgres 가 떠 있어야 한다)이고, 닿지 않으면 **건너뛴다**(rc=0).

실행:
    mcp_server/venv/bin/python mcp_server/allops_smoke.py
"""
import asyncio
import json
import os
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import smoke as S
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools" / "regress"))
import test_newline_matrix as nlm  # noqa: E402  — 스테이징 규칙을 베끼지 않는다

SKIP = {"stcx_fullangle_drop": "외부 클러스터에 진짜 잡을 낸다"}
CONSOLE_ONLY = {"info", "neutralaxis"}           # 산출 파일이 없는 op — succeeded 만 본다
BINARY = REPO / "platform" / "backend" / "bin" / "KooRemapper"   # 사전 단계(PREP)는 플랫폼과 같은 바이너리로
STAGE_ROOT = REPO / "build" / "scratch" / "allops"               # MCP 가 읽을 수 있는 자리(upload_local_path)

OK = []
SKIPPED = []


def chk(name, cond, detail=""):
    print("  %-62s %s" % (name, "OK" if cond else "FAIL"))
    OK.append(bool(cond))
    if not cond and detail:
        print("      %s" % str(detail)[:500])


# 예제가 **다른 op 의 산출**을 입력으로 쓰는 경우 — 같은 세션에서 그 op 의 예제를 플랫폼으로 먼저 돌린다(산출이 다음 잡의 입력이
# 되는 길까지 잰다). refshell 은 foldsurface 예제가 쓰는 fold_curve.csv 를 받는다.
PLATFORM_CHAIN = {"refshell": "foldsurface"}


def chain_prep(name, d, ops):
    """사슬 입력을 로컬에서 만든다(플랫폼과 같은 바이너리) — modelmeta 는 cclip 의 gen_board.yaml 로 만든 clip_board.k 를 받는다
    (`examples/modelmeta/run.sh` 와 같다). 그 밖의 op 은 할 일이 없다 — (True, None)."""
    env = dict(os.environ)
    if name == "modelmeta":
        shutil.copy2(REPO / "examples" / "cclip" / "gen_board.yaml", d / "gen_board.yaml")
        rc, out = nlm.run_op(str(BINARY), str(d), ["generate", "box", "gen_board.yaml"], env)
        return rc == 0 and (d / "clip_board.k").exists(), out[-200:]
    return True, None


def stage(op, ops):
    """예제를 STAGE_ROOT/<op> 에 스테이징한다 — 실패하면 (None, 까닭)."""
    folder = nlm.resolve_folder(op.get("example_folder"))
    args = (op.get("example") or {}).get("args")
    if not isinstance(args, dict):
        return None, "예제 인자가 없다"
    d = STAGE_ROOT / op["name"]
    shutil.rmtree(d, ignore_errors=True)
    d.mkdir(parents=True)
    if folder and os.path.isdir(folder):
        why = nlm.stage(op["name"], folder, str(d))
        if why:
            return None, why
    if op["name"] in nlm.PREP:
        argv, _ = nlm.PREP[op["name"]]
        rc, out = nlm.run_op(str(BINARY), str(d), argv, dict(os.environ))
        if rc != 0:
            return None, "사전 단계 실패: " + out[-200:]
    ok, why = chain_prep(op["name"], d, ops)
    if not ok:
        return None, "사슬 사전 단계 실패: %s" % why
    return d, None


def needed_files(args, d):
    """예제 인자가 이름으로 가리키는 스테이징 파일과, 그 덱의 `*INCLUDE` 가 가리키는 파일(끝까지) — 업로드는 분당 60 한도다."""
    names = {p.name for p in d.iterdir() if p.is_file()}
    want = set()

    def walk(v):
        if isinstance(v, dict):
            for x in v.values():
                walk(x)
        elif isinstance(v, list):
            for x in v:
                walk(x)
        elif isinstance(v, str) and os.path.basename(v) in names:
            want.add(os.path.basename(v))
    walk(args)
    todo = list(want)
    while todo:
        f = todo.pop()
        if not f.lower().endswith(nlm.DECK_EXT):
            continue
        lines = (d / f).read_text(encoding="utf-8", errors="replace").splitlines()
        for i, line in enumerate(lines):
            if not line.strip().upper().startswith("*INCLUDE"):
                continue
            for nxt in lines[i + 1:i + 4]:          # 이름 카드 — 주석 뒤 첫 줄
                t = nxt.strip()
                if not t or t.startswith("$"):
                    continue
                b = os.path.basename(t.split()[0])
                if b in names and b not in want:
                    want.add(b)
                    todo.append(b)
                break
    return sorted(want)


async def upload(s, sid, path):
    """올린다 — 한도(분당 60)에 걸리면 알려 준 초만큼 기다렸다 다시."""
    res = None
    for _ in range(6):
        res = await s.call_tool("upload_local_path", {"session_id": sid, "path": str(path)})
        text = res.content[0].text if res.isError and res.content else ""
        if res.isError and "요청이 너무 많습니다" in text:
            m = re.search(r"(\d+)초 후", text)
            await asyncio.sleep((int(m.group(1)) if m else 10) + 1)
            continue
        return res
    return res


async def main():
    ops = json.load(open(nlm.CATALOG, encoding="utf-8"))["operations"]
    pat, tid = S._mint_token()
    if not pat:
        print("SKIP — 토큰을 못 만들었다(플랫폼이 떠 있지 않다)")
        return 0
    try:
        async with streamablehttp_client(S.MCP_URL, headers={"Authorization": f"Bearer {pat}"}) as (r, w, _):
            async with ClientSession(r, w) as s:
                await s.initialize()
                for op in ops:
                    name = op["name"]
                    if name in SKIP:
                        SKIPPED.append((name, SKIP[name]))
                        continue
                    d, why = stage(op, ops)
                    if d is None:
                        SKIPPED.append((name, why))
                        continue
                    sess = S._data(await s.call_tool("create_session", {"name": f"allops_{name}"}))
                    sid = sess.get("id") if isinstance(sess, dict) else None
                    if not sid:
                        chk(f"{name}: 세션 생성", False, sess)
                        continue
                    try:
                        bad_up = []
                        for fn in needed_files(op["example"]["args"], d):
                            res = await upload(s, sid, d / fn)
                            got = None if res.isError else S._data(res)
                            if res.isError or not isinstance(got, dict) or got.get("filename") != fn:
                                bad_up.append((fn, res.content[0].text[:160] if res.isError else got))
                        if bad_up:
                            chk(f"{name}: 입력 {len(bad_up)}개를 그 이름으로 올리지 못했다", False, bad_up[:3])
                            continue
                        if name in PLATFORM_CHAIN:
                            pre = next(o for o in ops if o["name"] == PLATFORM_CHAIN[name])
                            pj = S._data(await s.call_tool("run_operation", {
                                "session_id": sid, "operation": pre["name"], "args": pre["example"]["args"]}))
                            pst = None
                            for _ in range(300):
                                pl = S._data(await s.call_tool("get_job", {"job_id": pj.get("id")}))
                                pst = pl.get("status") if isinstance(pl, dict) else None
                                if pst in ("succeeded", "failed", "cancelled"):
                                    break
                                await asyncio.sleep(1)
                            if pst != "succeeded":
                                chk(f"{name}: 사슬 앞 op({pre['name']})이 succeeded", False, pl)
                                continue
                        job = S._data(await s.call_tool("run_operation", {
                            "session_id": sid, "operation": name, "args": op["example"]["args"]}))
                        jid = job.get("id") if isinstance(job, dict) else None
                        if not jid:
                            chk(f"{name}: 잡이 생겼다", False, job)
                            continue
                        st, last = None, None
                        for _ in range(600):
                            last = S._data(await s.call_tool("get_job", {"job_id": jid}))
                            st = last.get("status") if isinstance(last, dict) else str(last)
                            if st in ("succeeded", "failed", "cancelled"):
                                break
                            await asyncio.sleep(1)
                        err = (last or {}).get("error_summary") if isinstance(last, dict) else None
                        if name in CONSOLE_ONLY:
                            chk(f"{name}: {st}", st == "succeeded", err or last)
                        else:
                            outs = await s.call_tool("get_job_outputs", {"job_id": jid})
                            chk(f"{name}: {st} · 산출물 {len(outs.content)}",
                                st == "succeeded" and len(outs.content) >= 1, err or last)
                    finally:
                        await s.call_tool("delete_session", {"session_id": sid})
    finally:
        if tid:
            S._revoke_token(tid)
        shutil.rmtree(STAGE_ROOT, ignore_errors=True)
    for n, why in SKIPPED:
        print("  %-62s 건너뜀(%s)" % (n, why))
    bad = OK.count(False)
    print("\n=== 플랫폼 op 전수: %s (%d/%d · 건너뜀 %d) ===" %
          ("PASS" if bad == 0 else "FAIL", len(OK) - bad, len(OK), len(SKIPPED)))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
