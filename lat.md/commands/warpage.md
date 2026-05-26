# warpage — warpage correction (§21)

Source: [ModelAssembler.cpp](../../src/assembly/ModelAssembler.cpp), [WarpageGrid.cpp](../../src/assembly/WarpageGrid.cpp)
Manual: [`KooRemapper_Manual.md`#21-warpage--워피지-보정](../../docs/KooRemapper_Manual.md#21-warpage--워피지-보정)


## Synopsis

```
KooRemapper warpage <args>
```

## What it does

Applies an out-of-plane warpage field (typically from molding simulation) and recomputes stress.

## Key references

- [[modules/assembly#Module: src/assembly/]]

## From the manual

_Excerpted from [`KooRemapper_Manual.md`](../../docs/KooRemapper_Manual.md) §21. warpage — 워피지 보정._

<!-- BEGIN MANUAL EXCERPT -->



### 용도
측정 데이터(.dat 파일)로부터 면외 변형(warpage)을 메시에 적용합니다.
곡률 기반 응력 계산 또는 직접 변위 모드를 지원합니다.

### 사용법

```bash
KooRemapper.exe warpage <config.yaml>
```

### YAML 형식

```yaml
model: base.k
output: warped
target_pid: 1
dat_file: warpage.dat      # 변형 데이터 파일
plane: xy                  # 투영 평면
deflection_axis: z         # 변형 축
unit: mm                   # 단위
mask_value: -9999          # 무효 데이터 마커
noise_threshold: 0.001     # 노이즈 임계값
morph_factor: 1.0          # 변형 배율
mode: curvature            # curvature | raw
finite_strain: false       # 유한 변형률 사용
outside_behavior: clamp    # 경계 외 처리
debug: false
debug_prefix: debug_
data_bbox:                 # 데이터 바운딩 박스 (선택)
  x_min: 0
  x_max: 100
  y_min: 0
  y_max: 100
material:
  E: 210000
  nu: 0.3
```

### 파라미터


**표 22-1. offset 모드 — tied/czm/contact 세 가지 인터페이스 연결 방법과 생성 키워드.**

| 파라미터 | 설명 | 기본값 |
|----------|------|--------|
| `dat_file` | 워피지 측정 데이터 파일 | — |
| `plane` | 투영 평면 (xy/yz/zx) | `xy` |
| `deflection_axis` | 변형 방향 축 | `z` |
| `mode` | curvature(곡률 응력) / raw(직접 변위) | `curvature` |
| `morph_factor` | 변형 배율 | `1.0` |
| `mask_value` | 무효 데이터 값 | — |
| `noise_threshold` | 노이즈 필터 임계값 | `0.001` |
| `finite_strain` | 유한 변형률 사용 여부 | `false` |
| `outside_behavior` | 경계 외 처리 (clamp/zero) | `clamp` |
| `data_bbox` | 데이터 영역 제한 | 자동 |

### 동작
1. .dat 파일에서 격자 데이터 로드
2. 바이리니어 보간으로 각 노드 위치의 변형량 계산
3. curvature 모드: 유한 차분으로 곡률 계산 → 굽힘 응력
4. raw 모드: 직접 노드 변위만 적용

---

<!-- END MANUAL EXCERPT -->
