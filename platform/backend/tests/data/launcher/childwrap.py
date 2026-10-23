#!/usr/bin/env python3
# 시험용 실행기(별도 프로세스판) — 신호를 넘기고, 자식이 끝난 모양을 그대로 흉내 낸다.
import ctypes, os, resource, signal, subprocess, sys
a = sys.argv[1:]
head = a[:a.index("--")] if "--" in a else a
if "--reap" in head:
    sys.exit(0)
if "--" not in a:
    print("[launcher] no '--'", file=sys.stderr)
    sys.exit(125)
libc = ctypes.CDLL(None)
def die_with_parent():
    libc.prctl(1, signal.SIGKILL)   # PR_SET_PDEATHSIG — 실행기가 죽으면 직계 자식도 죽는다(L7 의 일부만 흉내 낸다)
p = subprocess.Popen(a[a.index("--") + 1:], start_new_session=True, preexec_fn=die_with_parent)
def fwd(sig, _):
    try:
        os.killpg(p.pid, sig)
    except ProcessLookupError:
        pass
for s in (signal.SIGTERM, signal.SIGINT):
    signal.signal(s, fwd)
rc = p.wait()
if rc < 0:
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    if -rc != signal.SIGKILL:
        signal.signal(-rc, signal.SIG_DFL)
    os.kill(os.getpid(), -rc)
sys.exit(rc)
