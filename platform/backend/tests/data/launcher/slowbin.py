#!/usr/bin/env python3
# 시험용 느린 바이너리 — 진행률을 찍으며 slow_out.k 에 줄을 덧붙이고, 신호를 받거나 정한 시간이 될 때까지 돈다
import os, sys, time
# 앞의 선택지는 시험이 만든 래퍼가 붙인다. --tag 는 남은 프로세스를 시험마다 가려내는 표식(뜻 없음),
# --mark 는 시작·끝 시각을 적을 폴더, --hold 는 도는 초. 그 뒤가 앱이 준 argv 다.
opts, args = {}, sys.argv[1:]
while args[:1] and args[0] in ("--tag", "--mark", "--hold"):
    opts[args[0]] = args[1]
    args = args[2:]
if args[:1] != ["database"]:       # 시험이 내는 op 만 돈다. 출력 등록이 부르는 검사(info · modelmeta)는
    sys.exit(1)                   # 곧장 끝낸다 — 돌면 등록 뒤에 slow_out.k 를 또 늘린다
mark = opts.get("--mark")
if mark:
    open(os.path.join(mark, "%d.start" % os.getpid()), "w").write(repr(time.time()))
end = time.time() + float(opts.get("--hold", 60))
i = 0
with open("slow_out.k", "a") as fh:
    while time.time() < end:
        i += 1
        fh.write("$ tick %d\n" % i)
        fh.flush()
        print("%d%%" % min(i, 99), flush=True)
        time.sleep(0.05)
if mark:
    open(os.path.join(mark, "%d.end" % os.getpid()), "w").write(repr(time.time()))
