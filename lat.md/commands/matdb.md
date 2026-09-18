# matdb — material DB lookup + replacement (§24)

Source: [matdb.cpp](../../src/commands/matdb.cpp)
Manual: [`KooRemapper_Manual.md`#24-matdb--재료-db-교체](../../docs/KooRemapper_Manual.md#24-matdb--재료-db-교체)


## Synopsis

```
KooRemapper matdb <args>
```

## What it does

Uses `materials/material_db.json` to replace `*MAT_*` cards. Auto-matches by title→name/tag substring (case-insensitive) or direct MID. Supports structural card type selection (MAT_ELASTIC/024/RIGID/…), optional thermal insertion (`*MAT_THERMAL_ISOTROPIC` + `*MAT_ADD_THERMAL_EXPANSION` with TMID linkage). `match: "*"` is catch-all.

## Key references

- [[lsdyna/mat#LS-DYNA MAT cards in KooRemapper]]
- [[modules/commands#Module: src/commands/]] (stripQuotes)

## From the manual

_Excerpted from [`KooRemapper_Manual.md`](../../docs/KooRemapper_Manual.md) §24. matdb — 재료 DB 교체._

<!-- BEGIN MANUAL EXCERPT -->



### 용도
JSON 재료 데이터베이스(`material_db.json`)를 기반으로 모델의 `*MAT` 카드를 일괄 교체합니다.
파트 이름 자동 매칭 또는 직접 MID 지정을 지원합니다.

### 사용법

```bash
KooRemapper.exe matdb <config.yaml>
```

### YAML 형식

```yaml
model: model.k
output: result.k
database: materials/material_db.json   # YAML 폴더 기준 (§3.1(a) 와 같음). 생략하면 번들 DB
mat_type: MAT_ELASTIC     # 구조 카드 유형 — 생략 시 기본값
thermal: false            # 열 재료 삽입 여부
damping_preset: smartphone_drop   # 선택. smartphone_drop | smartphone_drop_aggressive | quasi_static | off

materials:                # 개별 규칙 (선택)
  - match: "steel*"       # 파트 이름 패턴 매칭
    mat_type: MAT_024     # 규칙별 오버라이드
  - mid: 5                # 직접 MID 지정
    thermal: true
  - match: "*"            # catch-all 자동 매칭
```

> **`mat_type` 기본값은 `MAT_ELASTIC` 입니다**(확인 — 키를 생략하고 돌리면 `*MAT_ELASTIC_TITLE` 이 나옵니다).
> 예전 판이 `MAT_024` 를 기본으로 적었던 것은 틀렸습니다. `MAT_024` 를 쓰려면 명시해야 합니다.

#### `database` 경로 규칙 (2026-09-18 실행 확인)

`model`·`output` 은 [§3.1(a)](#31-yaml-공통-규칙-모든-op) 대로 **YAML 파일이 있는 폴더** 기준입니다.
**`database` 도 이제 같은 규칙을 쓰며**, 여기에 번들 DB 폴백이 한 단계 더 붙습니다. 값을 위에서부터 순서대로 판정합니다.

**표 24-1. matdb `database` 키 해석 순서 — 다섯 갈래와 각 갈래의 결과.**

| # | `database` 값 | 찾는 자리 | 없을 때 |
|---|---|---|---|
| 1 | **키 생략** | 작업 폴더 `materials/material_db.json` → 실행 파일 옆 `materials/` → `<exe>/../materials/` | `[ERROR] … Cannot load database from: materials/material_db.json`, 종료 코드 1 |
| 2 | **절대 경로** (`/`·`\` 시작, `X:` 드라이브) | 적은 자리 그대로 | **번들 폴백 없이** 종료 코드 1 |
| 3 | **상대 경로** (폴더가 붙었든 홑이름이든) | **YAML 폴더 기준** — `cfg/m.yaml` 의 `sub/d.json` → `cfg/sub/d.json` | 4 번으로 |
| 4 | 3 이 빗나갔고 값이 **홑이름**(`/`·`\` 없음) | 같은 **파일 이름**을 1 번의 번들 자리에서 찾는다 | 5 번으로 |
| 5 | 그래도 없음 | — | **3 에서 푼 경로**를 찍고 종료 코드 1 |

- 4 번은 `database: material_db.json` 처럼 **번들 DB 이름만 적던 예전 사용법을 보존**하려고 둔 단계입니다.
  폴백이 일어나면 그 사실을 로그로 남깁니다 — `[matdb] WARNING: '<YAML폴더>/material_db.json' not found - using bundled '<번들경로>'`.
- **폴더가 붙은 상대 경로는 4 번을 거치지 않습니다.** `database: nope/material_db.json` 처럼 오타가 난 경로를
  조용히 다른 DB 로 바꿔치기하지 않고 `[ERROR] [matdb] ERROR: Cannot load database from: <YAML폴더>/nope/material_db.json` 으로 죽습니다.
  예전에는 이 값이 작업 폴더 기준으로 풀려 종종 rc=0 으로 **엉뚱한 DB** 를 읽었습니다.
- **어느 파일을 실제로 읽었는지 항상 로그에 남습니다** — `[matdb] Loaded 525 materials from <실제 경로>`.
  예전 문구는 경로 없는 `… from DB` 였으므로, 이 줄을 정규식으로 긁는 외부 도구가 있다면 손봐야 합니다.
- SIF 안에서는 실행 파일이 `/opt/kooremapper/bin/KooRemapper` 라서 1 번의 `<exe>/../materials/` 가
  `/opt/kooremapper/materials/material_db.json` 으로 걸립니다 — **키를 생략하는 편이 가장 이식성 있습니다**.
- `modelmeta` 의 `material_db` 키는 1·3 번만 있고 **4 번 번들 폴백이 없습니다** — [§43.5](#435-modelmeta--파트별-메타-json-추출) 참조.

### 감쇠 프리셋 (`damping_preset`)

`*DAMPING_PART_MASS_SET` 의 α 를 일괄 재조정합니다. **아래 4개 값만** 받으며(대소문자 무시), 그 밖의 값은
`[ERROR] matdb: unsupported damping_preset 'light' (allowed: smartphone_drop, smartphone_drop_aggressive, quasi_static, off)` 와 함께
**종료 코드 1** 입니다. 키를 아예 빼면 검사하지 않습니다(예전 동작 그대로).

**표 24-2. matdb damping_preset 허용값 — 프리셋별 α 스케일·하한과 미매칭 파트 적용 여부.**

| 값 | α 스케일 | α 하한 | 미매칭 파트에도 적용 |
|---|---|---|---|
| `smartphone_drop` | 15 | 150 | O |
| `smartphone_drop_aggressive` | 20 | 300 | O |
| `quasi_static` | 5 | 50 | X |
| `off` | (재조정 없음) | — | — |

`off` 는 프리셋이 아니라 **"감쇠 세기는 그대로 두고 묵은 `*DAMPING_PART_*` 카드만 지우는"** 관용구입니다(재실행 시 중복 방지).
`damping_alpha_scale`·`damping_alpha_floor` 등을 명시하면 프리셋 값을 덮어씁니다.

> **예전 문서의 `light`/`moderate`/`heavy`/`custom` 은 없는 값입니다** — 지금은 종료 코드 1 입니다.
> 이 검증은 단독 `matdb` 와 `assemble` 의 `- type: matdb` 양쪽에 걸립니다.

### 매칭 규칙
- `match`: 파트 title과 DB의 name/tag 부분 문자열 매칭 (대소문자 무시)
- `mid`: 직접 재료 ID 지정
- `match: "*"`: 모든 미매칭 재료에 자동 매칭 시도

### 열 재료 삽입 (`thermal: true`)
- `*MAT_THERMAL_ISOTROPIC` + `*MAT_ADD_THERMAL_EXPANSION` 자동 삽입
- TMID 링크 자동 연결

---

<!-- END MANUAL EXCERPT -->
