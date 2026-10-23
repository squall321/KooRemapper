#!/usr/bin/env python3
# 시험용 실행기(원격 흉내판) — 자식을 다른 그룹으로 띄우되 실행기가 죽어도 자식은 산다(원격 임대가 끊기 전의 원격 job)
import os, signal, subprocess, sys
a = sys.argv[1:]
if "--" not in a:
    sys.exit(0 if "--reap" in a else 125)
p = subprocess.Popen(a[a.index("--") + 1:], start_new_session=True)
def fwd(sig, _):
    try:
        os.killpg(p.pid, sig)
    except ProcessLookupError:
        pass
for s in (signal.SIGTERM, signal.SIGINT):
    signal.signal(s, fwd)
rc = p.wait()
if rc < 0:
    signal.signal(-rc, signal.SIG_DFL)
    os.kill(os.getpid(), -rc)
sys.exit(rc)
