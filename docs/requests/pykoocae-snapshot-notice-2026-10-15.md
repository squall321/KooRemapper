# 통지 — `KooRemapperStep.run()` 이 돌려주는 산출 목록이 **덮어쓴 파일을 못 셉니다**

**보내는 곳** DynaForge(KooRemapper) · 덱 편집 계약 담당
**받는 곳** pyKooCAE / SIF 소유자
**날짜** 2026-10-15
**기준** pyKooCAE `04760dc` · KooRemapper `13d4b80`. 아래 `파일:줄` 은 이 판 기준입니다.
**성격** **통지입니다.** 고칠지·어떻게 고칠지는 그쪽에서 정하십시오. 저희가 바라는 것은 없습니다.
**급하지 않습니다** — 지금 돌아가는 체인은 **안 걸립니다**(§3). 첫 소비자가 생길 때 걸립니다.

**한 줄** `run()` 은 산출을 **파일 이름의 차집합**으로 셉니다. 그래서 op 이 **이미 있는 이름에
덮어쓰면** 그 파일을 쓰고도 `[]`(산출 없음) 이 돌아옵니다. 저희 op 46개 중 **16개**가 그 모양입니다.

---

## 1. 무엇이 있나

`Runner/KooRemapperStep.py` —

```python
127    @staticmethod
128    def _snapshot(workdir: Path) -> set[str]:
129        return {p.relative_to(workdir).as_posix() for p in workdir.rglob("*") if p.is_file()}
...
152        before = self._snapshot(wd)
       proc = self._invoke(wd, call_argv)
...
158        after = self._snapshot(wd)
159        return sorted(after - before)
```

`set[str]` 이므로 비교하는 것은 **이름뿐**입니다. 내용도 시각도 보지 않습니다.

문서도 "created" 로 적혀 있습니다 — 모듈 독스트링 `:5` "get back the **produced** files",
`:25` `# out == ["mapped.k", ...]  (**new files created** in the case dir)`, `run()` 독스트링
`:132` "Returns the relative paths of files **created**".

즉 **글자 그대로는 맞습니다.** 문제는 이 값을 "이 op 이 무엇을 냈나" 로 읽는 다음 사람입니다.

## 2. 왜 문제가 되나

KooRemapper op 은 **대개 덮어씁니다.** 체인에서 같은 작업 폴더에 같은 이름으로 다시 쓰는 것이
정상 경로입니다(재시도 · 파라미터 쓸기 · 같은 덱을 단계마다 고치는 누적 설계).
그때 `run()` 은 `[]` 를 돌려줍니다 — **일은 했는데 안 한 것처럼 보입니다.**

`[]` 를 "실패" 로 읽으면 멀쩡한 스텝이 실패가 되고, "할 일 없음" 으로 읽으면 **고친 덱이
조용히 다음 스텝으로 안 넘어갑니다.** 둘 다 로그에 아무 흔적이 없습니다.

## 3. 지금 돌아가는 체인은 안 걸립니다 — 확인했습니다

`CumulativeScenarioRunner._run_remap_step`(`:2256`~`:2378`) 은 이 함수를 **안 씁니다.**

- 매번 **새 폴더**를 만듭니다 — `run_dir = Output/Run_<run_id>` · `os.makedirs(out_dir)` (`:2295-2297`)
- 입력을 `input.k` 로 복사하고 산출 이름을 `Remap_dti.k` 로 **못박습니다** (`:2307-2308`)
- 판정은 **그 한 파일의 존재**입니다 — `if not os.path.isfile(out_path)` → `"output not produced"` (`:2363-2368`)

새 폴더라 묵은 파일이 없고, 이름 차집합을 쓰지 않습니다. **이 길은 옳습니다.**
`KooRemapperStep.run()` 은 리포 안에 **호출자가 없습니다**(`grep` 으로 확인 — 독스트링 예시뿐).
그래서 이것은 지금의 결함이 아니라 **첫 소비자가 밟을 함정**이고, 계약서(독스트링)가
"created" 라고 적혀 있어 **그럴듯하게 틀립니다.** 그 점만 알려 드립니다.

## 4. 실측 — op 46개 중 16개가 `[]` 가 됩니다

저희 예제 매트릭스(카탈로그 `example_folder` + 선언 픽스처)로 각 op 을 한 번 돌리고,
**그쪽과 똑같이** 이름 차집합을 센 값과, **실제로 쓰인 파일**(내용이 바뀌거나 mtime 이 움직인 것)을
나란히 셌습니다.

- 덜 세는 op **17개** · 그중 **0 으로 세는 op 16개**

| op | 새 이름 | 실제로 쓴 것 | 차집합이 놓친 파일 |
|---|---|---|---|
| ale | 0 | 1 | `ale_minimal.k` |
| cnrb2solid | 0 | 1 | `bolt_simple_solid.k` |
| convert | 0 | 1 | `tet10_result.k` |
| disconnect | 0 | 1 | `disconnect_czm_result.k` |
| elform | 0 | 1 | `elform_case_a_result.k` |
| hfdamp | 0 | 1 | `box_hfdamp.k` |
| load | 0 | 1 | `mesh_loaded.k` |
| map | 0 | 1 | `arc30_mapped.k` |
| matdb | 0 | 1 | `test_matdb_result.k` |
| merge | 0 | 1 | `merged_output.k` |
| prestress | 0 | **2** | `arc30_test_prestress.dynain`, `arc30_test_prestress.k` |
| refine | 0 | 1 | `refine_hex_1to2_result.k` |
| shellmap | 0 | 1 | `arc_mapped.k` |
| tetremesh | 0 | 1 | `tet10_result.k` |
| unfold | 0 | 1 | `arc30_unfolded.k` |
| wrap | 0 | **2** | `cylinder_wrapped.dynain`, `cylinder_wrapped.k` |
| formstrain | 1 | 2 | `formstrain_result.k` |

★**정직하게 적습니다** — 이 수가 이렇게 큰 것은 저희 예제 폴더가 **기대 산출물을 입력과 함께
담아 두기** 때문입니다(예: `examples/tet10/` 에 `two_tets.k` 와 `tet10_result.k` 가 같이 있습니다).
실제 체인 폴더는 내용이 다릅니다. 그러나 **판정식은 똑같습니다** — 이미 있는 이름에 쓰면 `[]` 입니다.
그리고 체인이 같은 폴더에 **다시 돌리는 순간** 모든 op 이 그 상태가 됩니다.

재현 —
```
# KooRemapper 리포에서
python3 tools/regress/test_keyword_card.py build/dev/bin/KooRemapper   # 같은 매트릭스를 씀
```

## 5. ★저희도 **오늘** 같은 함정을 밟았습니다 — 그 근거를 함께 보냅니다

저희 쪽 관문 `tools/regress/test_keyword_card.py` 를 세우면서 산출 덱을 sha256 으로만
가렸습니다. 결과 —

- **7개 op**(`cnrb2solid`·`convert`·`refine`·`elform`·`matdb`·`hfdamp`·`ale`)이
  "산출 덱 0장" 으로 나왔습니다. op 은 멀쩡히 돌아 파일을 썼습니다 — 내용이 같아서 가려졌습니다.
- ★그 그늘에 **진짜 결함 하나가 숨어 있었습니다.** `prestress` 가 `dynain` 옆에 쓰는 동반 `.k`
  (사용자가 LS-DYNA 에 그대로 던지는 덱)에 `*KEYWORD` 가 없었습니다. sha256 만 보는 동안
  그 파일은 "안 건드린 입력" 으로 넘어가 **관문에 한 번도 걸리지 않았습니다.**
  mtime 수법으로 바꾸자마자 드러났습니다(커밋 `13d4b80`).

**저희가 쓴 방법** — 돌리기 **전에** 작업 폴더의 모든 파일 mtime 을 한 값으로 못박고,
돌린 **뒤에** 그 값이 아닌 것을 "쓰였다" 로 봅니다. 이 수법은 저희가 지어낸 것이 아니라
같은 리포의 다른 관문이 이미 쓰던 것입니다 —
`tools/regress/test_newline_matrix.py:74`(`BASE_T = 946684800`)·`:259`·`:280`.

```python
BASE_T = 946684800                     # 2000-01-01 UTC
for p in workdir.rglob("*"):
    if p.is_file():
        os.utime(p, (BASE_T, BASE_T))  # 돌리기 전
...
touched = int(p.stat().st_mtime) != BASE_T      # 돌린 뒤
```

## 6. 고르실 수 있는 셋 — 정하는 것은 그쪽입니다

| | 방법 | 값 | 비용·한계 |
|---|---|---|---|
| ① | **mtime 못박기** (위 그대로) | 내용이 같아도 쓰인 것을 센다. 쌉니다(`stat` 만) | 작업 폴더 파일에 `utime` 을 건다. 아주 짧은 op 과 거친 타임스탬프 파일시스템에서 이론적으로 놓칠 수 있다 |
| ② | **내용 해시**(`before`/`after` 를 `{이름: sha256}` 로) | `utime` 을 안 건다. 확실하다 | 큰 파일에서 비싸다(덱이 수백 MB 면 두 번 읽는다) |
| ③ | **둘 다** — mtime 이 움직였거나 해시가 달라졌으면 쓰였다 | 어느 한쪽의 구멍을 다른 쪽이 막는다 | 코드가 몇 줄 더 늘어난다 |
| ④ | **그대로 두고 계약서를 고친다** | 코드 변경 0 | `run()` 이 **완전한 산출 목록이 아니라는 것**을 독스트링·예시(`:5`·`:25`·`:132`)에 적어야 한다. "created" 는 지금 그 뜻으로 읽히지 않습니다 |

저희가 쓴 것은 ①입니다(관문이라 큰 덱을 두 번 읽기 싫었습니다). 체인이라면 ③ 이 안전할 것
같지만 **저희가 정할 일이 아닙니다.** ④만 고르셔도 저희는 아무 문제가 없습니다 — 저희는 이
함수를 부르지 않습니다.

## 7. 묻는 것 · 묻지 않는 것

**묻는 것은 하나뿐입니다** — 어느 쪽으로 가실지 한 줄만 알려 주십시오. 저희 쪽 문서
(`docs/requests/deck-contract-plan2-2026-09-24.md` §6 pyKooCAE 행 ③)를 그 답으로 닫습니다.

**묻지 않는 것** — 일정, 우선순위, 다른 스텝. 그리고 ④(계약서만 고치기)도 **똑같이 유효한
답**입니다. 이 통지는 "고쳐 주십시오" 가 아니라 "이런 것이 있습니다" 입니다.

**덧** — 같은 문서 §6 pyKooCAE 행의 ①(`SmartTwinPreprocessor.sif` 재굽기)은 **닫혔습니다.**
저희 답신 `docs/requests/deck-contract-reply2-2026-09-25.md:241` 이 다시 구운 것을 적고 있습니다
(안 바이너리 `168cc9d4` · GLIBC_2.34). 그 줄은 09-24 시점 기록이라 하루 뒤에 낡았습니다.
②(부분충격 `impact_report.sh`)는 포털이 2026-09-17 에 이미
`pyKooCAE/docs/REQUEST-drop-impact-result-return.md` 로 보냈습니다 — 저희가 겹쳐 묻지 않습니다.
