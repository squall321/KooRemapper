# Offset Operation Regression Test Suite

## 목적

Offset operation의 향상 사항을 구현하는 동안 기존 기능이 손상되지 않도록 보호합니다.

## 테스트 구조

```
tests/offset/
├── regression/           # 테스트 YAML 파일
│   ├── 01_solid_tied.yaml
│   ├── 02_tshell_multi.yaml
│   ├── 03_shell_offset.yaml
│   ├── 04_czm_mode.yaml
│   ├── 05_contact_mode.yaml
│   ├── 06_dual_prestress.yaml
│   ├── 07_normal_direction.yaml
│   └── 08_multi_layer_solid.yaml
├── baseline/             # 기준 메트릭 (JSON)
│   ├── 01_solid_tied_metrics.json
│   └── ...
├── results/              # 테스트 실행 결과 (임시)
└── run_regression.ps1    # 자동화 스크립트
```

## 테스트 케이스

### 01_solid_tied.yaml
- **기능**: 기본 solid offset (tied connection)
- **검증**: 600 HEX8 elements 생성
- **핵심**: Surface extraction + tied node sharing

### 02_tshell_multi.yaml
- **기능**: Multi-layer TSHELL extrusion
- **검증**: 1200 TSHELL elements (2 layers)
- **핵심**: TSHELL element creation + top/bottom nodes

### 03_shell_offset.yaml
- **기능**: Shell element offset
- **검증**: 600 QUAD4 shell elements
- **핵심**: Shell element creation at offset position

### 04_czm_mode.yaml
- **기능**: CZM connection mode
- **검증**: 600 HEX8 + 600 cohesive elements
- **핵심**: Cohesive element generation (ELFORM 20)

### 05_contact_mode.yaml
- **기능**: Contact connection mode
- **검증**: 600 HEX8 with separate nodes
- **핵심**: Node duplication + contact template

### 06_dual_prestress.yaml
- **기능**: Dual offset prestress mode
- **검증**: .k file + .dynain file with initial stress
- **핵심**: Full 3D strain calculation + prestress output

### 07_normal_direction.yaml
- **기능**: +normal offset direction
- **검증**: 600 HEX8 following surface normals
- **핵심**: Normal vector calculation

### 08_multi_layer_solid.yaml
- **기능**: Multi-layer solid offset (3 layers)
- **검증**: 1800 HEX8 elements
- **핵심**: Layer stacking logic

## 실행 방법

### 1. 초기 베이스라인 생성

```powershell
# 현재 구현의 출력을 기준으로 설정
powershell -ExecutionPolicy Bypass -File tests\offset\run_regression.ps1 -UpdateBaseline
```

이 명령은 각 테스트를 실행하고 결과를 `baseline/` 디렉토리에 저장합니다.

### 2. 회귀 테스트 실행

```powershell
# 기준과 비교하여 변화 감지
powershell -ExecutionPolicy Bypass -File tests\offset\run_regression.ps1
```

### 3. 상세 출력 모드

```powershell
# 각 테스트의 stdout/stderr 출력 표시
powershell -ExecutionPolicy Bypass -File tests\offset\run_regression.ps1 -Verbose
```

## 검증 메트릭

각 테스트는 다음 메트릭을 추출하고 비교합니다:

### 출력 기반 메트릭
- `solid_elements`: 생성된 solid element 수
- `shell_elements`: 생성된 shell element 수
- `cohesive_elements`: 생성된 cohesive element 수
- `nodes_created`: 생성된 node 수
- `new_parts`: 생성된 part 수

### 파일 기반 메트릭
- `has_dynain`: .dynain 파일 존재 여부
- `has_initial_stress`: *INITIAL_STRESS_SOLID 키워드 존재
- `k_solid_sections`: .k 파일 내 *ELEMENT_SOLID 섹션 수
- `k_shell_sections`: .k 파일 내 *ELEMENT_SHELL 섹션 수
- `k_tshell_sections`: .k 파일 내 *ELEMENT_TSHELL 섹션 수
- `has_czm_material`: *MAT_COHESIVE_MIXED_MODE 존재
- `has_contact_template`: Contact 정의 템플릿 주석 존재

## 테스트 실패 시 대응

테스트가 실패하면:

1. **의도된 변경인가?**
   - 향상 사항으로 인해 출력이 개선되었다면 베이스라인 업데이트:
     ```powershell
     powershell -ExecutionPolicy Bypass -File tests\offset\run_regression.ps1 -UpdateBaseline
     ```

2. **버그인가?**
   - `results/` 디렉토리의 stdout/stderr 확인
   - 생성된 .k 파일 검사
   - 코드 수정 후 다시 테스트

3. **메트릭 차이 분석**
   - 스크립트 출력에서 어떤 메트릭이 변경되었는지 확인
   - 예:
     ```
     ~ solid_elements : 600 → 580  (20개 감소 - 버그!)
     + has_dynain : true             (새 기능 추가 - 정상)
     ```

## CI/CD 통합

향후 GitHub Actions 또는 다른 CI 시스템에서 다음과 같이 실행:

```yaml
- name: Run Offset Regression Tests
  run: |
    cmake --build build --config Release
    powershell -ExecutionPolicy Bypass -File tests\offset\run_regression.ps1
```

## 테스트 추가

새로운 offset 기능을 추가할 때:

1. `tests/offset/regression/` 에 새 YAML 테스트 추가
2. 파일명은 `09_feature_name.yaml` 형식 사용
3. 베이스라인 업데이트: `-UpdateBaseline`
4. 문서 업데이트 (이 README의 테스트 케이스 섹션)

## 주의사항

- **베이스라인은 정확한 기준 시점에서 생성**: 모든 기존 기능이 올바르게 작동하는 상태에서 `-UpdateBaseline` 실행
- **부동소수점 비교**: 현재 메트릭은 정수 기반이므로 안정적. 향후 부동소수점 메트릭 추가 시 tolerance 고려
- **Arc30 모델 의존성**: 모든 테스트는 `examples/arc30/arc30_flat.k` 사용. 이 파일 변경 시 베이스라인 갱신 필요
- **출력 파일 위치**: 테스트 출력은 `tests/offset/regression/regression/` 에 생성됨 (YAML의 `output:` 경로)

## 향상 사항 구현 워크플로우

Phase 1-10 구현 시:

```bash
# 1. 회귀 테스트 통과 확인
powershell -ExecutionPolicy Bypass -File tests\offset\run_regression.ps1

# 2. 새 기능 구현 (예: Phase 1 - Material validation)

# 3. 빌드
cmake --build build --config Release

# 4. 회귀 테스트 재실행 (기존 기능 보호 확인)
powershell -ExecutionPolicy Bypass -File tests\offset\run_regression.ps1

# 5. 새 기능 테스트 추가 (예: 09_material_validation.yaml)

# 6. 베이스라인 업데이트 (새 기능 포함)
powershell -ExecutionPolicy Bypass -File tests\offset\run_regression.ps1 -UpdateBaseline

# 7. 커밋
git add tests/offset/
git commit -m "feat: Add Phase 1 material validation with regression tests"
```

이 프로세스를 통해 기존 기능을 손상시키지 않으면서 점진적으로 향상 사항을 추가할 수 있습니다.
