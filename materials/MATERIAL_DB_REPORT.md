# KooRemapper 재료 데이터베이스 정리 현황 레포트

`materials/material_db.json` 기준 (생성 2026-04-20, 생성기 `scripts/build_material_db.py`).

## 1. 개요
여러 출처(국제 규격·재료 DB·벤더 데이터시트·논문)에서 모은 재료 물성을 **LS-DYNA 키워드
카드 형태**로 정리한 통합 데이터베이스다. 각 재료는 기계·열·감쇠 물성과, 그 물성을 그대로
담은 *MAT 카드(여러 모델 변형 포함)를 함께 가진다.

- **총 재료 수: 525종**
- **카테고리: 11개**
- **단위계: t / mm / s / K → MPa** (밀도 t/mm³, 비열 mJ/(t·K) 등 `_meta`에 전부 문서화)
- 원칙: `card_structural` 은 **원본 LS-DYNA 키워드 텍스트를 그대로** 보존.

## 2. 수집 규모 — 카테고리별

| 카테고리 | 재료 수 |
|---|---:|
| metal (금속) | 171 |
| polymer (폴리머) | 106 |
| pcb (기판/프리프레그) | 81 |
| rubber (고무) | 45 |
| tape (접착 테이프/OCA/PSA) | 34 |
| ceramic (세라믹) | 22 |
| semiconductor (반도체/EMC) | 18 |
| display (디스플레이) | 18 |
| glass (유리) | 17 |
| magnet (자석) | 12 |
| composite (복합재) | 1 |
| **합계** | **525** |

## 3. 재료 모델 분포 (native mat_type)

| 모델 | 수 | 성격 |
|---|---:|---|
| MAT_PIECEWISE_LINEAR_PLASTICITY | 132 | 소성 |
| MAT_PLASTIC_KINEMATIC | 102 | 소성 |
| MAT_VISCOELASTIC | 92 | 점탄성 |
| MAT_SAMP-1 | 18 | 폴리머 소성 |
| MAT_MOONEY-RIVLIN_RUBBER | 16 | 초탄성(고무) |
| MAT_HYPERELASTIC_RUBBER | 14 | 초탄성(고무) |
| MAT_ORTHOTROPIC_ELASTIC | 6 | 직교 탄성 |
| MAT_ELASTIC | 143 | 탄성 |
| MAT_RIGID | 2 | 강체 |

소성+점탄성+초탄성 등 **비탄성 모델이 380종**으로 다수. 탄성 143종은 취성/선형 재료
(유리·세라믹·디스플레이·자석) + 일부 선형근사 항목.

## 4. 데이터 완성도

| 항목 | 채움 |
|---|---|
| 기계 물성(mechanical) | 385 / 525 |
| 열 물성(thermal) | **525 / 525** |
| 감쇠(damping) | 397 / 525 |
| 구조 카드(≥1 변형) | 525 / 525 |
| 구조 카드 다변형(≥2 mat_type) | 385 / 525 (변형 수 분포 1→140, 2→137, 3→156, 5→92) |
| 열팽창 카드(*MAT_ADD_THERMAL_EXPANSION) | 525 / 525 |
| 감쇠 카드 | 397 / 525 |
| 열 카드 풀블록(*MAT_THERMAL_ISOTROPIC) | 32 / 525 |
| 설명(description) | 32 / 525 |

대부분의 재료가 **하나의 물성으로 여러 모델 카드**(예: 탄성/소성/강체, 점탄성/탄성근사)를
동시에 제공해 용도에 맞게 골라 쓸 수 있다.

## 5. 출처 — "여러 웹에서 모아서"
주석·설명 텍스트에 인용된 출처 마커 빈도 (키워드명 오염 제외).

| 출처 | 인용 | 비고 |
|---|---:|---|
| ASTM 규격 | 154 | 금속/플라스틱 기계·열 물성 표준 |
| 벤더 TDS(Technical Data) | 104 | 제조사 데이터시트 |
| ASM Handbook | 19 | 금속 표준 물성 |
| JIS | 15 | 일본 산업규격 |
| MatWeb | 10 | 온라인 재료 DB |
| 3M | 9 | OCA/VHB/PSA 테이프 |
| ISO | 4 | 국제규격 |
| PMC 논문 | 2 | OCA/PSA 점탄성 특성 논문 |
| Nitto | 1 | 고전단 PSA |

추가로 재료 *이름*에 벤더가 직접 드러나는 항목이 많다 — PCB 프리프레그(Panasonic
Megtron, Hitachi MCL, Isola 370HR 등), 테이프(3M 8171/4905/5952, Nitto 5000),
디스플레이/유리(Gorilla Glass, Dragontrail) 등. 즉 **국제규격(ASTM/ISO/JIS) +
재료 DB(MatWeb/ASM) + 벤더 데이터시트 + 학술 논문**을 교차 수집해 구성했다.

## 6. 빌드 파이프라인
```
materials/*.k (9개 소스) + name_mapping.yaml
        │   mat_elastic.k  mat_plasticity.k  mat_rigid.k  mat_rubber.k
        │   mat_tape.k  mat_viscoelastic.k  mat_thermal.k
        │   mat_thermal_expansion.k  rubber.k
        ▼   scripts/build_material_db.py  (MAT 블록 파싱·자동 분류)
materials/material_db.json   (525종, 카드 텍스트 보존)
```
원본은 모델별로 손질된 LS-DYNA .k 파일이고, 빌드 스크립트가 이를 파싱해 단일 JSON DB로
합친다. KooRemapper의 `matdb` 오퍼레이션이 이 DB로 모델 부품 재료를 이름/부품명 기준으로
치환한다.

## 7. 산출물
- `all_materials.k` — 전 525종 *MAT 키워드 단일 k파일 (소성/점탄성 우선, 탄성은 그것뿐일 때만).
- `export_all_materials.py` — 위 덤프 생성기(`--thermal`, `--native` 옵션).
- `smartphone_stack.k` + `matdb_smartphone.yaml` → `smartphone_stack_mapped.k` — 대표 매핑 예제
  (소성 금속 4 + 점탄성 접착/PCB/폼 5).

## 8. 남은 보강 여지
- `description` 32/525 — 출처가 주로 카드 주석에 산재. 구조화된 source/doi 필드 추가 시 추적성↑.
- 폴리머/고무/테이프 일부가 "…Linear" 선형 근사만 보유 → 탄성 137종. 소성/점탄성 데이터 보강 여지.
- composite 1종(CFRP)뿐 — 복합재 확장 필요.
- 열 카드 풀블록 32/525(열 물성 수치는 525 전부 보유) — *MAT_THERMAL_ISOTROPIC 카드화 확대 여지.
