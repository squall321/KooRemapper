# KooRemapper 개발 이력

## v1.4.0 (2026-03-29) — 모듈 아키텍처 리팩토링

### 내부 구조 개선
- `src/main.cpp` 분리: ~12,000줄 → 1,970줄 (CLI 디스패처만 유지)
- 모든 커맨드 구현을 `src/commands/` 하위 독립 파일로 추출

| 파일 | 커맨드 |
|------|--------|
| `modal.cpp` | modal (고유진동수 해석) |
| `relax.cpp` | relax (Dynamic Relaxation) |
| `implicit.cpp` | implicit/explicit 변환 |
| `database.cpp` | database 카드 생성 |
| `matdb.cpp` | matdb (재질 DB 교체) |
| `stabilize.cpp` | stabilize (명시적 솔버 안정화) |
| `ale.cpp` | ale (ALE 유체/폭발 변환) |
| `matswap.cpp` | matswap (재질 번들 교체) |
| `optimize.cpp` | optimize (고무 재질 최적화) |
| `contact_helpers.cpp` | ct_* 컨택 헬퍼 함수군 |
| `contact.cpp` | contact (컨택 분석/생성/수정) |
| `load_boundary.cpp` | load, boundary, rbe |
| `standalone_ops.cpp` | wrap, update, restack, bend, indent, formstrain, convert, refine, elform, disconnect, iga, warpage, offset |
| `core_ops.cpp` | map, shellmap, generate, strain, unfold, prestress, info, generate-box, generate-var |
| `squeeze_assemble.cpp` | squeeze, assemble |
| `kw_util.h` | 공통 K-파일 헬퍼 (kw_trim, kw_upper, kw_setField 등) |

- 52개 테스트 전수 통과

---

## v1.3.2 (2026-03) — squeeze strain_mode + relax 통합

### 신기능
- **squeeze `strain_mode`**: `*INITIAL_STRAIN_SOLID` 출력 (응력 계산 없이 변형률 직접 부여)
- **assemble `relax`**: assemble 내 Dynamic Relaxation 카드 자동 삽입
- **16개 커맨드 help 텍스트** 추가 (이전 미문서화 커맨드)
- squeeze 가이드 문서 (`docs/squeeze_guide.docx`)

---

## v1.3.1 (2026-02) — IGA 개선 + restack CZM

### 신기능
- **IGA**: 버그 수정 + `target_pids` 리스트 지원
- **restack**: CZM / czm_auto 모드, SET_SEGMENT 기반 tied contact
- **target_pids**: 다중 PID를 한 번에 처리

---

## v1.3.0 (2026-01) — assemble 대규모 확장

### 신기능
- **generate 오퍼레이션**: assemble 내 박스 메시 생성
- **control 오퍼레이션**: CONTROL_* 카드 직접 수정
- **database 오퍼레이션**: DATABASE_BINARY_* 카드 삽입
- **update 오퍼레이션**: dynain 파일로 노드 위치 업데이트
- **offset 양방향**: `+normal` / `-normal` 동시 지원
- UTF-8 콘솔 출력 (Windows 한국어 지원)

---

## v1.2.0 (2025-12) — 스탠드얼론 커맨드 + 안정화

### 신기능
- **stabilize**: 12단계 명시적 솔버 안정화 (`tssfac`, `IHQ`, `pinball`, `ERODE` 등)
- **matdb**: JSON DB 기반 재질 교체 (구조 + 열 재질)
- **swelling**: 열팽창 카드 자동 생성
- **11개 스탠드얼론 커맨드**: wrap, bend, indent, formstrain, convert, refine, elform, disconnect, iga, warpage, offset (assemble 전용 → 독립 실행 가능)
- **optimize**: 고무 재질 해석 파라미터 자동 최적화
- **load / boundary / rbe**: 경계 조건 생성

### 개선
- `matswap`: YAML 기반 번들 교체 + PID 단위 적용
- `contact`: 자동 감지, 생성, 수정 통합

---

## v1.1.0 (2025-11) — offset + IGA + 고급 맵핑

### 신기능
- **offset**: 쉘 면에서 솔리드 레이어 생성
  - 로컬 법선 벡터 (`use_local_normals`)
  - 가변 두께 (`thickness_formula`)
  - 영역 선택 (`bbox_*`, `node_id_*`, `element_id_*`)
  - CZM (응집 요소) 자동 삽입
- **IGA**: Isogeometric Analysis 요소 생성 (`*ELEMENT_SOLID_NURBS_PATCH`)
- **refine**: HEX8/QUAD4/TET4 요소 1:2, 1:3 세분화
- **convert**: TET10/HEX20/QUAD8/TRIA6 2차 요소 변환
- **disconnect**: full / czm / mefem 분리 모드

### 개선
- `assemble`: formstrain, warpage, indent(emboss), fillet 오퍼레이션 추가
- `prestress`: Green-Lagrange 기본 변형률 타입

---

## v1.0.0 (2025-10) — 초기 릴리즈

### 핵심 커맨드
- **map**: HEX8 구조 메시 아이소파라메트릭 맵핑
- **shellmap**: QUAD4 쉘 기반 솔리드 상세 메시 맵핑
- **unfold**: 굽은 구조 메시 → 평판 전개
- **prestress**: 변형 전/후 메시 비교 → 초기 응력/변형률 (dynain)
- **squeeze**: 간섭 끼워맞춤 압축 + 역변형률 dynain
- **assemble**: 모델 조립 (replace, squeeze, restack, bend, indent, formstrain)
- **generate / generate-var**: 예제 메시 / 가변밀도 메시 생성
- **strain**: 두 메시 간 변형률 계산
- **info**: 메시 파일 정보 출력
- **modal**: 고유진동수 해석 변환
- **implicit**: 명시적 → 암시적 솔버 변환 (8단계 스펙트럼)
- **ale**: ALE 유체/폭발물 변환 (14개 재질 프리셋)

---

## 커맨드 목록 (v1.4.0 기준, 총 28개)

| 커맨드 | 분류 | 설명 |
|--------|------|------|
| `map` | 맵핑 | HEX8 구조 메시 맵핑 |
| `shellmap` | 맵핑 | QUAD4 쉘 기반 맵핑 |
| `unfold` | 맵핑 | 굽은 메시 평판 전개 |
| `prestress` | 해석 | 초기 응력/변형률 생성 |
| `strain` | 해석 | 메시 간 변형률 계산 |
| `squeeze` | 조립 | 간섭 끼워맞춤 압축 |
| `assemble` | 조립 | 모델 조립 (전체 파이프라인) |
| `wrap` | 조립 | 감기 장력 프리스트레스 |
| `bend` | 조립 | 굽힘 응력 부여 |
| `indent` | 조립 | 압입/엠보스 응력 |
| `formstrain` | 조립 | 성형 변형률 부여 |
| `restack` | 조립 | 레이어 재적층 |
| `disconnect` | 조립 | 메시 분리 (czm/peri/mefem) |
| `offset` | 메시 | 솔리드 오프셋 레이어 생성 |
| `convert` | 메시 | 2차 요소 변환 (TET10 등) |
| `refine` | 메시 | 요소 세분화 (1:2, 1:3) |
| `elform` | 메시 | 요소 타입 변경 |
| `iga` | 메시 | IGA NURBS 요소 생성 |
| `warpage` | 메시 | 워피지 변형 적용 |
| `update` | 메시 | dynain 기반 위치 업데이트 |
| `implicit` | 솔버 | 명시적 → 암시적 변환 (8레벨) |
| `modal` | 솔버 | 고유진동수 해석 변환 |
| `relax` | 솔버 | Dynamic Relaxation 설정 |
| `ale` | 솔버 | ALE 유체/폭발 변환 |
| `stabilize` | 솔버 | 명시적 안정화 (12레벨) |
| `optimize` | 솔버 | 고무 해석 파라미터 최적화 |
| `matswap` | 재질 | 재질 번들 교체 |
| `matdb` | 재질 | JSON DB 재질 교체 |
| `contact` | 컨택 | 컨택 분석/생성/수정/변환 |
| `load` | 경계조건 | 하중 생성 |
| `boundary` | 경계조건 | 구속 조건 생성 |
| `rbe` | 경계조건 | RBE2/RBE3 생성 |
| `database` | 출력 | DATABASE_BINARY 카드 |
| `generate` | 유틸 | 예제 메시 생성 |
| `generate-var` | 유틸 | 가변밀도 메시 생성 |
| `info` | 유틸 | 메시 파일 정보 |
