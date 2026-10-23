# 결정 노트 — 실행기(launcher) 설정 (10-23)

- **(10-23) 요청서의 사실 주장은 다 맞았다.** 줄 번호는 `559f582` 그대로(±1줄). getenv 는 `KOOREMAPPER_GMSH`·`PATH`(meshfix)·
  `KOO_MAP_DEBUG`·`KOO_TETGEN_DEBUG` 넷뿐. `omp_set_num_threads`·`num_threads(` 없음 — OpenMP 는 `ElementAnalyzer`·`MeshRemapper`
  두 곳이고 스레드 수는 런타임 기본(`OMP_NUM_THREADS` 가 정한다). `std::thread` 없음. gmsh 는 `popen`/`system` 으로 절대 경로를 부른다.
- **(10-23) 바이너리 종료 코드는 0 과 1 뿐이다.** run 함수의 리터럴 반환 `return 0` 79 · `return 1` 669 · `std::exit(1)` 1.
  계산된 반환(`mapRc`·`frc`·`prc`·`rc`·`rebind::run`·`previewReferences`·`runHelp`)은 모두 이 값을 전파한다. `main` 이
  `std::exception` 을 잡아 1 로 바꾼다. 그 밖은 신호 죽음(abort −6 · segv −11)과 로더 실패(127)다. 125 는 안 나온다.
  (`scratchpad/tools/rc_audit.py` — 람다 안의 return 은 사람이 걸렀다.)
- **(10-23) 이 박스의 API 프로세스 환경에는 `KOORM_` 말고도 토큰·API 키 이름이 섞여 있다**(이름만 셌다 — 값은 보지 않았다).
  터미널 세션에서 띄운 인스턴스라 그 환경을 통째로 물려받았고, 지금 job 자식도 전부 물려받는다. K5 가 겹 방어로 값을 한다.
  stdin 은 `/dev/null`(요청서 실측과 같다).
- **(10-23) K6 은 실행기 명령 줄을 그대로 적는다.** `_env_snapshot` docstring 은 「호스트 절대 경로는 담지 않는다」인데, 그 까닭은
  gmsh 경로가 stdout 에 이미 있고 번들에서 접어야 해서였다. 실행기 명령은 사용자 데이터가 아니고 다른 데 남지 않는다. 다만 번들의
  `_redact_deep` 는 저장소·홈·`/workspace` 경로와 토큰 꼴만 지우므로 **실행기 인자에 비밀을 넣으면 DB 와 번들에 남는다** — 답신에 적는다.
- **(10-23) 시험 행은 running 으로 넣는다.** 시험 DB 는 떠 있는 API 의 DB 다. queued 로 넣으면 그 워커가 1초 안에 집어 가 실행기 없이
  돌린다. `_execute` 는 상태를 보지 않으므로 running 으로 넣고 직접 부른다. V9 는 `_loop` 를 돌리되 클레임만 메모리 큐로 바꾼다.
- **(10-23) V2·V3 의 산출 비교는 `$ Date:` 줄을 뺀 내용 해시로 한다.** 처음엔 등록 sha 를 그대로 맞춰 generate 가 갈렸다.
  같은 op 를 실행기 없이 두 폴더에서 돌려 diff 하니 다른 것은 generate · map 산출의 `$ Date:` 한 줄뿐이었다(database · matdb ·
  meshfix 는 바이트까지 같다). 실행기 탓이 아니다. 등록 sha 가 디스크와 같은지는 따로 본다.
- **(10-23) 가짜 바이너리는 시험 op(`database`)일 때만 돈다.** 출력 등록의 `inspect_kfile` 이 `info` 다음에 `modelmeta` 도 부른다.
  처음 판은 `info` 만 곧장 끝내서 `modelmeta` 가 60초를 돌았고(V4 · V6 시간 초과), 그 호출이 등록 뒤에 slow_out.k 를 늘려
  V7(b) 가 거짓으로 실패했다. 코드 결함이 아니라 시험 장치 결함이었다.
- **(10-23) 시험이 옛 동작을 잡는지 쟀다.** 옛 `_run_blocking`(실행기가 있어도 바로 SIGKILL)을 끼우는 임시 플러그인으로
  V7(a) · K2 · V7(b) 셋이 모두 실패한다 — V7(b) 는 「등록한 뒤에 파일이 바뀌었다」. 원격 흉내 실행기(PDEATHSIG 없음)라야
  이 차이가 보인다 — `childwrap.py` 는 실행기가 죽으면 자식도 죽어서 옛 동작에서도 우연히 통과할 수 있다.
- **(10-23) K7 은 설정과 무관하게 돈다.** 폴더가 남을 때만 움직이고, 그 경우는 지금껏 조용히 지나갔다. 이름은 적지 않고 개수만.
- **(10-23) K4 정리는 한꺼번에 부른다(gather) · 하나 15초 상한 · `--reap` 에도 허용 목록 환경.** 하나씩이면 고아 8개에 최대 80초 큐가 선다.
  시험용 정리 실행기는 종료 코드를 환경이 아니라 고정 인자로 받는다 — 환경은 허용 목록이 거른다(처음 판이 그것에 걸렸다).
- **(10-23) 열린 결정 셋은 사용자에게 올린다.** Q3(권장 A) · `.nfs*` 빼기 · 로컬 고아 틈. 답신에는 권장안과 「아직 넣지 않았다」로 적었다.
