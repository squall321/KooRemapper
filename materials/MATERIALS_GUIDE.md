# LS-DYNA Material Database Guide

이 문서는 `materials/` 폴더의 물성 데이터 파일 구조와 자동화 활용 방법을 설명한다.

## 단위계

모든 데이터는 LS-DYNA 표준 **t / mm / s / K** 단위계 기준이다.

| 물리량 | 단위 | SI 변환 |
|--------|------|---------|
| 밀도 RHO | t/mm³ | g/cm³ × 1e-9 |
| 탄성계수 E | MPa | GPa × 1000 |
| 푸아송비 PR | - | - |
| 항복강도 SIGY | MPa | - |
| 비열 HC | mJ/(t·K) | J/(kg·K) × 1e6 |
| 열전도율 TC | mW/(mm·K) | W/(m·K) (수치 동일) |
| 열팽창계수 ALPHA | 1/K | ppm/K × 1e-6 |

---

## 파일 목록

```
materials/
├── material_db.json          ← 핵심 DB (기계+열+CTE+카드 전부)
├── name_mapping.yaml         ← 이름 매핑 (original ↔ tag)
├── mat_elastic.k             ← MAT_ELASTIC 카드 (24개)
├── mat_rigid.k               ← MAT_RIGID 카드 (2개)
├── mat_plasticity.k          ← MAT_024 카드 (1개, M-Film)
├── mat_rubber.k              ← MAT_MOONEY-RIVLIN 카드 (2개)
├── mat_viscoelastic.k        ← MAT_VISCOELASTIC 카드 (1개)
├── mat_thermal.k             ← MAT_THERMAL_ISOTROPIC 카드 (32개)
├── mat_thermal_expansion.k   ← MAT_ADD_THERMAL_EXPANSION 카드 (32개)
├── 00_summary.txt            ← 전체 물성 요약 테이블
└── thermal_summary.txt       ← 열물성 요약 테이블 (SI + LS-DYNA)
```

---

## 1. material_db.json — 핵심 데이터베이스

### 최상위 구조

```json
{
  "_meta": { ... },
  "materials": { "MID": { ... }, ... },
  "part_material_map": { "PID": { ... }, ... },
  "category_index": { "metal": [...], ... },
  "custom_materials": { ... },
  "supported_mat_types": { ... }
}
```

### 1.1 materials (MID 기준, 32개)

각 재료 엔트리의 필드:

```json
{
  "name": "Mobile.STS304",           // 원래 이름 (k파일 기준)
  "tag": "STS304_Stainless",         // 직관적 태그 이름
  "description": "STS304 stainless steel",
  "category": "metal",               // metal|polymer|glass|composite|rubber
  "mat_type": "MAT_ELASTIC",         // 원본(primary) 물성 타입
  "mat_type_id": 1,                  // LS-DYNA type number
  "mechanical": {                    // 기계물성 (수치)
    "RHO": 7.9e-09,
    "E": 190000.0,
    "PR": 0.3,
    ...
    "rho_g_cm3": 7.9,               // SI 참조용
    "E_GPa": 190.0                  // SI 참조용
  },
  "thermal": {                       // 열물성
    "Cp_SI": 500,                   // J/(kg·K) - SI 참조용
    "k_SI": 16.2,                   // W/(m·K) - SI 참조용
    "HC": 500000000.0,              // LS-DYNA 단위
    "TC": 16.2,                     // LS-DYNA 단위
    "ALPHA": 1.73e-05,              // CTE [1/K]
    "ALPHA_ppm_K": 17.3             // CTE [ppm/K] 참조용
  },
  "cards_structural": {              // 구조 물성 카드 (다중 variant)
    "MAT_ELASTIC": "...",           // 원본 카드 (verbatim)
    "MAT_RIGID": "...",             // 자동생성 rigid variant
    "MAT_PIECEWISE_LINEAR_PLASTICITY": "..."  // 금속만
  },
  "card_thermal": "...",             // *MAT_THERMAL_ISOTROPIC 카드
  "card_thermal_expansion": "..."    // *MAT_ADD_THERMAL_EXPANSION 카드
}
```

#### cards_structural — 다중 variant 규칙

| 원본 mat_type | 제공 variant | 비고 |
|---|---|---|
| MAT_ELASTIC | `MAT_ELASTIC` + `MAT_RIGID` | 전체 32개 중 24개 |
| MAT_ELASTIC (금속) | + `MAT_PIECEWISE_LINEAR_PLASTICITY` | SIGY 추정값 포함 (8개 금속) |
| MAT_RIGID | `MAT_RIGID` + `MAT_ELASTIC` | MID 21, 46 |
| MAT_024 | `MAT_024` + `MAT_ELASTIC` + `MAT_RIGID` | MID 38 (M-Film) |
| MAT_MOONEY-RIVLIN | `MAT_MOONEY-RIVLIN` + `MAT_ELASTIC` + `MAT_RIGID` | MID 45, 47. MAT_ELASTIC는 E=6(A+B) 선형화 |
| MAT_VISCOELASTIC | `MAT_VISCOELASTIC` + `MAT_ELASTIC_instantaneous` + `MAT_ELASTIC_longterm` + `MAT_RIGID` | MID 43. 순간(G0) / 장기(GI) 탄성 근사 |

#### card_thermal_expansion

`*MAT_ADD_THERMAL_EXPANSION` 카드이며, **PID 기반 키워드**이다.
DB에는 MID 값을 PID 필드에 넣어 저장해놨으므로, 실제 사용 시 PID로 치환해야 한다.

```
*MAT_ADD_THERMAL_EXPANSION
$      PID      LCID      MULT
         2         01.7300E-05
```

- `LCID=0` → 상수 CTE
- `MULT` = ALPHA 값 (1/K)

#### 특수 플래그

일부 재료에 `flags` 배열이 있다:
- `"mass_scaled"` — MID 6 (Ground): RHO ×1000 질량 스케일링
- `"corrected"` — MID 41 (Epoxy): RHO, E 값 수정됨

### 1.2 part_material_map (PID→MID 매핑, 22개)

```json
"part_material_map": {
  "19": {
    "part_name": "UTG",
    "MID": 15,      // 구조 물성 ID
    "TMID": 15      // 열물성 ID
  }
}
```

실제 모델에서 사용 중인 파트만 포함. MID로 `materials` 섹션을 참조하면 모든 물성에 접근 가능.

### 1.3 category_index

카테고리별 MID 목록. 빠른 필터링용.

```json
"category_index": {
  "metal": [2, 3, 4, 6, 11, 13, 18, 19, 21, 38, 46],
  "polymer": [1, 5, 7, 8, 9, 10, 12, 14, 16, 17, 20, 22, 39, 41, 42, 43],
  "glass": [15],
  "composite": [44],
  "rubber": [40, 45, 47],
  "custom": []
}
```

### 1.4 custom_materials

사용자 정의 재료 추가용 슬롯. `_example_MID` 키에 템플릿이 있다.

### 1.5 supported_mat_types (11종)

DB가 지원하는 MAT 타입의 필드 정의. 파서/생성기 구현 시 참조용.

```
MAT_ELASTIC (001), MAT_RIGID (020), MAT_PIECEWISE_LINEAR_PLASTICITY (024),
MAT_MOONEY-RIVLIN_RUBBER (027), MAT_VISCOELASTIC (006),
MAT_ELASTIC_PLASTIC_THERMAL (004), MAT_THERMAL_ISOTROPIC (T01),
MAT_THERMAL_ORTHOTROPIC (T02), MAT_JOHNSON_COOK (015),
MAT_OGDEN_RUBBER (077), MAT_BLATZ-KO_RUBBER (007)
```

---

## 2. name_mapping.yaml — 이름 매핑

원래 k파일 이름(`original`)과 직관적 태그(`tag`)의 대응표.
카테고리별로 그룹화되어 있다.

```yaml
metals:
  - MID: 2
    original: Mobile.STS304
    tag: STS304_Stainless
    note: "STS304 austenitic stainless steel"

polymers:
  - MID: 5
    original: PC_QF1035
    tag: PC_Polycarbonate
    note: "Polycarbonate QF1035 grade"
```

### 필드

| 필드 | 설명 |
|------|------|
| `MID` | 재료 ID (material_db.json의 키와 동일) |
| `original` | 원래 k파일에서의 이름 |
| `tag` | 새로 부여한 직관적 이름 |
| `note` | 재료 설명 (한 줄) |

### 카테고리

`metals`, `polymers`, `glass`, `composites`, `rubber` — 총 5개 그룹.

---

## 3. K파일 (.k) — LS-DYNA 키워드 카드

각 파일은 `*KEYWORD` ~ `*END` 사이에 해당 타입의 MAT 카드를 모아놓은 것이다.
`*INCLUDE`로 직접 모델에 삽입할 수 있다.

### 구조 물성

| 파일 | 키워드 | 재료 수 | 비고 |
|------|--------|---------|------|
| `mat_elastic.k` | `*MAT_ELASTIC_TITLE` | 24 | MID 1~22, 39~42, 44 |
| `mat_rigid.k` | `*MAT_RIGID_TITLE` | 2 | MID 21, 46 (3-card format) |
| `mat_plasticity.k` | `*MAT_PIECEWISE_LINEAR_PLASTICITY` | 1 | MID 38 (응력-변형률 곡선 포함) |
| `mat_rubber.k` | `*MAT_MOONEY-RIVLIN_RUBBER` | 2 | MID 45, 47 (Card 2: SGL/SW/ST 포함) |
| `mat_viscoelastic.k` | `*MAT_VISCOELASTIC` | 1 | MID 43 (G0/GI/BETA) |

### 열물성

| 파일 | 키워드 | 재료 수 | 비고 |
|------|--------|---------|------|
| `mat_thermal.k` | `*MAT_THERMAL_ISOTROPIC_TITLE` | 32 | TMID = MID, HC/TC 필드 |
| `mat_thermal_expansion.k` | `*MAT_ADD_THERMAL_EXPANSION` | 32 | PID=MID 기준, LCID=0(상수) |

### 카드 포맷

모든 카드는 **10-char fixed-width field** 형식이다.

```
*MAT_ELASTIC_TITLE
$HWCOLOR MATERIAL         2      43        ← HyperMesh 색상 (원본 보존)
Mobile.STS304::CAE_Hinge-Edge_JG2_x_t_Fem::[2]  ← 타이틀
$      MID       RHO         E        PR        DA        DB         K
         27.9000E-09  190000.0       0.3       0.0       0.0       0.0
```

- `$HWCOLOR`, `$HMNAME` 라인은 HyperMesh 메타데이터 (원본 카드에만 있음)
- 자동생성 variant (MAT_RIGID 등)에는 이 헤더가 없음
- 타이틀 라인은 `$#`으로 시작하면 안 됨 (주석 처리됨)

---

## 4. 자동화 활용 가이드

### 4.1 재료 조회 (Python)

```python
import json

with open('materials/material_db.json') as f:
    db = json.load(f)

# MID로 조회
mat = db['materials']['2']
print(mat['tag'])        # "STS304_Stainless"
print(mat['mechanical']['E'])  # 190000.0
print(mat['thermal']['ALPHA']) # 1.73e-05

# PID→재료 조회
part = db['part_material_map']['19']  # UTG
mid = str(part['MID'])                # 15
mat = db['materials'][mid]
print(mat['tag'])  # "UTG_SodaLime"

# 카테고리별 필터
metals = db['category_index']['metal']  # [2, 3, 4, 6, ...]
```

### 4.2 구조 물성 카드 선택

```python
mat = db['materials']['2']

# 원본 타입 확인
print(mat['mat_type'])  # "MAT_ELASTIC"

# variant 목록
print(list(mat['cards_structural'].keys()))
# ['MAT_ELASTIC', 'MAT_RIGID', 'MAT_PIECEWISE_LINEAR_PLASTICITY']

# 특정 variant 카드 가져오기
rigid_card = mat['cards_structural']['MAT_RIGID']
print(rigid_card)
# → *MAT_RIGID_TITLE
#   Mobile.STS304
#   ...
```

### 4.3 열해석 카드 세트 생성

하나의 재료에 대해 열해석에 필요한 전체 카드:

```python
mid = '15'  # Glass
mat = db['materials'][mid]

# 1) 구조 물성 (원본 또는 variant 선택)
print(mat['cards_structural']['MAT_ELASTIC'])

# 2) 열물성
print(mat['card_thermal'])

# 3) 열팽창 (PID 치환 필요)
card = mat['card_thermal_expansion']
# PID 필드를 실제 PID로 치환
actual_pid = 19  # UTG part
# ... 10-char field 치환 로직
```

### 4.4 전체 모델 열물성 일괄 삽입

```python
# 모든 파트에 대해 열팽창 카드 생성
for pid_str, pdata in db['part_material_map'].items():
    mid_str = str(pdata['MID'])
    mat = db['materials'][mid_str]
    alpha = mat['thermal']['ALPHA']
    pid = int(pid_str)
    # *MAT_ADD_THERMAL_EXPANSION 카드 생성
    print(f'*MAT_ADD_THERMAL_EXPANSION')
    print(f'$      PID      LCID      MULT')
    print(f'{pid:>10}{0:>10}{alpha:>10.4E}')
```

### 4.5 이름 매핑 활용 (YAML)

```python
import yaml

with open('materials/name_mapping.yaml') as f:
    mapping = yaml.safe_load(f)

# 이름 검색
for cat in ['metals', 'polymers', 'glass', 'composites', 'rubber']:
    for item in mapping.get(cat, []):
        if item['tag'] == 'STS304_Stainless':
            print(f"MID={item['MID']}, original={item['original']}")
```

### 4.6 새 재료 추가

`custom_materials` 섹션에 추가하거나 `materials`에 직접 추가:

```python
db['materials']['100'] = {
    "name": "NewSteel",
    "tag": "HighStrength_Steel",
    "description": "High strength steel for brackets",
    "category": "metal",
    "mat_type": "MAT_ELASTIC",
    "mat_type_id": 1,
    "mechanical": {
        "RHO": 7.85e-09,
        "E": 210000.0,
        "PR": 0.3,
        "rho_g_cm3": 7.85,
        "E_GPa": 210.0
    },
    "thermal": {
        "Cp_SI": 460,
        "k_SI": 45.0,
        "HC": 460000000.0,
        "TC": 45.0,
        "ALPHA": 1.2e-05,
        "ALPHA_ppm_K": 12.0
    },
    "cards_structural": {
        "MAT_ELASTIC": "*MAT_ELASTIC_TITLE\nNewSteel\n$      MID       RHO         E        PR        DA        DB         K\n       1007.8500E-09  210000.0       0.3       0.0       0.0       0.0"
    },
    "card_thermal": "...",
    "card_thermal_expansion": "..."
}
```

---

## 5. 주의사항

1. **MID = TMID** — 현재 모든 재료에서 구조 MID와 열 TMID가 동일
2. **MAT_ADD_THERMAL_EXPANSION은 PID 기반** — DB에는 MID 값으로 저장. 실제 출력 시 PID로 치환 필요
3. **원본 카드 보존** — `cards_structural`의 첫 번째 키 (= `mat_type`)가 원본 k파일에서 추출한 카드. `$HWCOLOR`/`$HMNAME` 헤더 포함
4. **MAT_024 SIGY 추정값** — 금속 8종의 SIGY는 문헌 추정치. 실험 데이터가 있으면 교체 권장
5. **Mooney-Rivlin → MAT_ELASTIC 변환** — E = 6(A+B), 소변형 근사. 대변형에서는 Mooney-Rivlin 원본 사용
6. **Viscoelastic → MAT_ELASTIC 변환** — `instantaneous` (G0 기반)과 `longterm` (GI 기반) 두 가지 제공
7. **질량 스케일링** — MID 6 (Ground)은 RHO ×1000. 열해석 시 실제 밀도 사용 주의
8. **10-char field** — 모든 카드 값은 10자리 고정폭. 파싱 시 `line[i*10:(i+1)*10]` 슬라이싱
