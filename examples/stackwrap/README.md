# stackwrap 예제 — 접힘 적층을 EI 중립축 기준으로 감는다

`shellmap` 은 평면 덱의 `z=0` 을 중립면으로 보고 그 좌표를 법선 오프셋으로 쓴다. 적층의 **EI
중립축**이 `z=0` 이 아니면 그만큼 전부 어긋난다(현장 보고 §1-6). `stackwrap` 이 그것을 맞춘다 —
중립축을 재서 적층을 옮긴 뒤 같은 매핑 경로로 감는다.

```
KooRemapper stackwrap stackwrap.yaml
```

산출물 둘.

- `wrapped_neutral.k` — 중립면이 `z=0` 에 오도록 옮긴 평면 적층. **무엇을 매핑에 넣었는지**
  눈으로 볼 수 있게 남긴다.
- `wrapped.k` — 기준 셸에 감긴 적층.

## 픽스처를 어떻게 만들었나

`ref_shell.k` 는 반경 3, 접선 총회전 90° 원호를 폭 1.0 으로 쓴 QUAD4 기준 셸이다.

```
KooRemapper foldsurface f.yaml      # output: f / arc_length: 4.71238898038469
                                    # fold_angle: 90 / min_radius: 3 / points: 97
KooRemapper refshell r.yaml         # curve: f_curve.csv / output: ref_shell.k
                                    # width: 1.0 / thickness: 0.05 / divisions: 48
```

`flat_stack.k` 는 비대칭 3층(0.2 E=1000 / 0.3 E=70000 / 0.1 E=3000) 솔리드 적층이고, 치수를
그 셸의 전개(현 합 4.71217820413 × 폭 1.0)에 맞췄다 — 정합이 디테일을 늘이지 않도록.

EI 중립축은 `0.350465116279` 이고 기하 중심면은 `0.3` 이다. **둘이 다르다는 점이 이 예제의
요지다** — `KooRemapper neutralaxis flat_stack.k` 로 따로 확인할 수 있다.

## 부호 규약

`refshell` 의 감김 `(a,d,c,b)` 법선은 오목한 쪽을 향한다. 그래서 평면 덱의 **양수 z 가
오목한(곡률 중심) 쪽**으로 간다 — 감긴 절점의 반경은 `R - z` 다. `tools/regress/test_stackwrap.py`
가 이 규약을 닫힌식으로 못 박는다.
