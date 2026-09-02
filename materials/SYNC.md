# 물성 갱신 — 레이크에서 사용 집합으로

`material_db.json` 은 **정리된 사용 집합**이다(해석 덱에 실제로 꽂히는 것). MaterialTwin 은
**데이터 레이크**다(출처·측정법·불확실도까지 쌓는 곳). 지금까지 레이크 → 사용 집합 방향의
길이 없어서, 4월 이후 쌓인 것이 해석에 닿지 못했다. 이 문서가 그 길이다.

## 쓰는 법

```bash
# ① 대조 — 무엇이 다른지 본다(아무것도 바꾸지 않는다)
python3 scripts/material_sync.py
python3 scripts/material_sync.py --json /tmp/sync.json     # 전체 결과 저장

# ② 반영 — 갱신분을 오버레이에 적는다
python3 scripts/material_sync.py --apply

# ③ 재생성 — 오버레이가 material_db.json 에 들어간다
python3 scripts/build_material_db.py
```

## 왜 오버레이인가

`material_db.json` 은 `materials/**/*.k` 에서 **통째로 재생성되는 생성물**이다. JSON 을
직접 고치면 다음 재생성에서 조용히 사라진다. 그래서 갱신은 `material_overrides.yaml` 에
두고 빌더가 마지막에 얹는다(`apply_overrides`). `.k` 원본은 상류(KooDynaAdvanced)와
바이트 동일하게 유지한다.

**카드 텍스트도 함께 고친다.** 한 항목이 `mechanical.RHO` 와 `cards_structural` 원문에
같은 값을 두 번 들고 있다 — 한쪽만 고치면 DB 가 스스로 모순된다. 되쓰기는
`material_cards.CARD_FIELDS`(칸 배치 정본, 빌더도 같은 표를 읽는다)를 쓴다.

## 규율

- **기본은 보고서다.** 값을 바꾸는 것은 `--apply` 로만.
- **짝을 추측으로 짓지 않는다.** 이름 정확 → 정규화 → 별칭(사람이 적은 것). 정규화 후보가
  여럿이면 고르지 않는다. 못 지은 것은 목록으로 낸다.
- **차이가 50% 넘으면 제안에서 뺀다.** 교정이 아니라 짝을 잘못 지은 것일 때가 많다 —
  실측: `NBR Cushion Rubber`(1.3 g/cc)가 같은 이름의 **스펀지** 데이터시트(0.15 g/cc)와
  짝지어졌다. 확인한 뒤에는 `--include-large` 로 넣는다.
- **환산 뒤 범위 밖이면 버린다.** 레이크는 SI, 사용 집합은 t/mm/s 다. 단위를 잘못 읽은
  값이 조용히 들어가는 것이 이 판에서 가장 흔한 사고다.
- **근거가 약하면 제안하지 않는다.** `quality_tier` 는 1 측정 → 5 추정이고 **작을수록
  좋다**. 3보다 나쁜 근거로는 갱신을 제안하지 않는다.
- **파생값은 되쓰지 않는다.** MOONEY·VISCOELASTIC 의 `E`·`PR` 은 카드에 칸이 없다
  (A·B, BULK·G0 에서 계산한 것이다). 없는 칸에 쓰려 하면 거절한다.

## 알려진 것 (2026-09-02 실측)

- 사용 집합 525종 · 레이크에서 비교 가능한 것 1,243종 · **이름으로 지어진 짝 69종**.
  나머지 456종은 레이크에 없다(`Mobile.STS304`·`AL7003H` 같은 사내/약칭 이름) —
  별칭 파일에 사람이 적어야 붙는다.
- 판정 — 일치 155칸 · 차이 44칸 · 차이(근거약함) 27칸 · 차이(큼·짝 확인) 22칸 · 빈칸 8칸.
- **배포본 `material_db.json` 이 자기 소스와 어긋나 있다.** 지금 `.k` 로 다시 만들면
  타입이 달라진다(MAT_ELASTIC 143→137 · PIECEWISE 132→140 · RIGID 2→0). 4월 생성 이후
  `.k` 가 바뀌었는데 DB 를 다시 굽지 않은 것으로 보인다 — **재생성 전에 확인할 것.**
- **파싱 구멍을 메웠다.** `MAT_PLASTIC_KINEMATIC`(102)·`SAMP-1`(18)·
  `HYPERELASTIC_RUBBER`(14)·`ORTHOTROPIC_ELASTIC`(6) = 525 중 **140종(27%)** 의
  `mechanical` 이 통째로 비어 있었다(카드에는 값이 멀쩡히 있는데도). 이제 525/525 가 찬다.

## 회귀

```bash
/home/koopark/claude/StepForge/.venv/bin/pytest scripts/test_material_sync.py -q   # 13개
```
