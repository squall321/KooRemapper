> StepForge 쪽에서 전달하는 관측 기록이다(원본: StepForge `docs/NOTE-2026-09-26-gmsh-runaway.md`, 커밋 444e45a).
> 받는 쪽 판단에 맡긴다 — StepForge 는 KooRemapper 코드를 고치지 않았다. 2026-09-28 재확인: 멈춘 `gmsh -parse_and_exit` 프로세스 0개, 디스크 42%.

# 전달용 메모 — gmsh `-parse_and_exit` 가 멈춘 채 디스크를 채운다(2026-09-25 실측)

받는 쪽: DynaForge / KooRemapper 담당. 보내는 쪽: StepForge(이 리포는 아무것도 안 고쳤다 — 관측만 했다).

## 무슨 일이 있었나

2026-09-25 20:2x, 개발 박스(`/dev/nvme0n1p2`, 1.6TB)의 **여유 공간이 0** 이 되어 모든 작업이 멈췄다.
원인은 **KooRemapper 의 gmsh 프로세스 6쌍**이었다. 전부 이 꼴이다.

```
sh -c -- '/home/koopark/claude/KooRemapper/dist/gmsh/gmsh' '/tmp/tmpXXXXXXXX/data/mf_out__mf.geo' \
         -v 3 -parse_and_exit > '/tmp/tmpXXXXXXXX/data/mf_out__mf.log' 2>&1
```

- 시작 뒤 **7~8시간** 살아 있었다(`ps -o etime`: 08:41:34 · 08:27:44 · 08:21:26 · 08:16:50 · 08:06:06 · 07:25:43).
- `-parse_and_exit` 는 **즉시 끝나는** 옵션이다. 즉 그 시간 동안 산출물이 없었다.
- 각 프로세스가 리다이렉트 대상 로그를 **156~160GB** 까지 키웠다. 그 파일들은 이미 unlink 된 상태라
  `du`·`ls` 로는 **보이지 않고** 프로세스가 열어 둔 fd 로만 공간을 붙들고 있었다(합계 약 1.8TB).
- `kill -9` 로 6쌍을 끊자 **911GB 가 즉시 반환**됐다(사용률 100% → 41%).

## 왜 알려야 하나

- 같은 입력(`mf_out__mf.geo`)이 다시 들어오면 같은 일이 난다. 우리 쪽에서는 그 `.geo` 를 만들 수 없어
  **재현 조건을 특정하지 못했다** — 그쪽 로그·입력 보존 경로가 있으면 거기서 봐야 한다.
- 로그를 파일로 리다이렉트하는 호출은 **상한이 없으면 디스크를 채운다**. 이 리포가 같은 부류에서 배운 것은
  "포기는 시계가 아니라 작업량으로 한다"(D-276)와 "쌍 하나의 비용에 상한이 없으면 멎는다"(D-276)다.
  gmsh 쪽에는 ① 실행 시간 상한(`timeout`), ② 로그 크기 상한(`head -c` 파이프 또는 `ulimit -f`),
  ③ 부모가 죽을 때 자식까지 끊는 것(`start_new_session` + `killpg`, 이 리포의 잡 규약)이 필요해 보인다.

## 다음에 같은 증상을 만나면(어느 리포든)

`du` 로 디렉터리를 뒤지지 말고 **지워진 파일을 붙들고 있는 프로세스**를 먼저 본다.

```bash
lsof -nP | awk '/deleted/ && $7 > 1073741824 {printf "%s %s %.1fG %s\n", $1, $2, $7/1073741824, $NF}' | sort -k3 -h | tail
```

그리고 `pkill -f` 는 쓰지 않는다(자기 셸의 `bash -c` 래퍼를 물어 세션을 죽인다) — **PID 로만** 끊는다.
덧붙여 `apptainer cache clean -f` 가 이 박스에서 90GB 를 더 돌려줬다(다시 빌드하면 채워지는 파생물이다).
