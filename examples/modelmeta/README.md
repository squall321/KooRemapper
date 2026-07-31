# modelmeta — K파일 구조화 메타 추출 예제

K파일에서 파트별 기하 메트릭·재료·접촉 connectivity를 `<output>_modelmeta.json`으로
추출한다. **읽기 전용** — 모델을 수정하지 않는다. AI Data Hub의 SIM 레코드 메타
자동 채움(파트 목록·연결도·재료 연계)의 소스로 설계됐다.

## 실행

```bash
bash run.sh
```

## 출력 구조

| 블록 | 내용 |
|------|------|
| `model` | 노드/요소/파트 수, 전체 bbox |
| `parts[]` | pid, title, elem_class(solid/shell/mixed), n_elems, bbox, **area_ext**(외부 자유표면적), **volume**, **proj.x/y/z**(정사영 면적), material |
| `parts[].material` | mid + kfile(카드 키워드·제목·E/nu/rho/sigy) + db(번들 DB 매칭: name/category/E_GPa/rho + **match_basis**) |
| `connectivity` | contact_edges(파트쌍 + 접촉 타입/제목/fs), single_surface(스코프), geometric_edges(detect 시), unresolved_sides |

## 규약 (JSON `conventions`에도 기록)

- 솔리드 파트 — 자유면(공유 1회 면) 합 = 외부 표면적. 정사영 = `sum(area·|n·축|)/2`
  (닫힌 표면 왕복 상쇄). 부피 = 면-중심 피라미드 분해(와인딩 무관).
- 쉘 파트 — 요소면 단측 면적, 정사영 /2 없음, 부피 0.
- 검증: 3.0×1.5×0.5 박스에서 부피 2.25 / 표면적 13.5 / 정사영 0.75·1.5·4.5
  이론값과 기계 정밀도 일치 확인.

## connectivity 해석 규칙

- SSID/MSID의 SSTYP/MSTYP: PID(3)·SET_PART(2)·SET_NODE(4)·SET_SEGMENT(0)을
  파트 ID 목록으로 환원(노드 기반 셋은 노드→소유 파트로).
- SINGLE_SURFACE류·master 없는 접촉은 파트쌍으로 폭발시키지 않고 스코프로 기록.
- 미해결 사이드(누락 SET)는 `unresolved_sides`로 카운트.

## 재료 DB 매칭 (match_basis로 신뢰도 보고)

1. `name-mat` — *MAT_..._TITLE 제목과 DB name/tag 매칭 (완전일치 무제한, 부분일치는 4자 이상)
2. `name-part` — 파트 제목과 매칭 (같은 규칙)
3. `mid` — MID 일치 (기본 off — 모델 로컬 MID가 DB 번호와 우연 충돌하므로 `db_mid_fallback: true`로만)
