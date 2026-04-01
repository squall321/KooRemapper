# hfdamp 예제

고주파 노이즈 댐핑 (`*DAMPING_FREQUENCY_RANGE_DEFORM`) 자동 삽입.

## 동작 원리

```
요소 시간 간격:  dt_e = TSSFAC × L_char / c_wave
                 (L_char: 최소 엣지 길이, c_wave: P파 속도)

댐핑 주파수 대역:
  FLOW  = 1 / (2 × dt_target)   ← 이 이상의 주파수를 댐핑
  FHIGH = FLOW × fhigh_ratio
```

dt_target 이하의 요소가 생성하는 고주파 성분이 CDAMP 비율로 감쇠됩니다.

## 빠른 시작

```bash
# 전 파트에 적용 (global)
KooRemapper hfdamp basic.yaml

# 소형 요소가 있는 파트만 자동 선택 (selective)
KooRemapper hfdamp selective.yaml

# 모든 옵션 확인
KooRemapper hfdamp hfdamp_full.yaml
```

## 예제 파일

| 파일 | 설명 |
|------|------|
| `basic.yaml` | 전 파트 global 댐핑, 최소 옵션 |
| `selective.yaml` | 요소 dt 계산 → 해당 파트만 SET_PART 생성 |
| `hfdamp_full.yaml` | 전체 옵션 + 물리 설명 |
| `assemble_hfdamp.yaml` | assemble 파이프라인 예제 |

## YAML 최소 구성

```yaml
model: input.k
output: output.k
dt_target: 3.0e-8   # FLOW = 1/(2×dt_target) 이상의 주파수 댐핑
```

## 주요 옵션

| 옵션 | 기본값 | 설명 |
|------|--------|------|
| `dt_target` | (필수) | 댐핑 타겟 dt [모델 시간 단위] |
| `cdamp` | 0.99 | 임계 감쇠 비율 (0 < cdamp ≤ 1) |
| `fhigh_ratio` | 100.0 | FHIGH = FLOW × ratio (권장 10~300) |
| `mode` | global | `global`: 전파트 / `selective`: 소형 요소 파트만 |
| `tssfac` | 0.9 | 요소 dt 추정 안전계수 (selective 전용) |

## assemble 파이프라인

```yaml
operations:
  - type: hfdamp
    dt_target: 3.0e-8
    cdamp: 0.99
    fhigh_ratio: 100.0
    mode: selective
```

## dt_target 선택 가이드 (t/mm/s 단위계, 철강 E=200GPa)

| 최소 요소 크기 | 권장 dt_target |
|--------------|---------------|
| ~1 mm        | 2.0e-7        |
| ~0.5 mm      | 1.0e-7        |
| ~0.1 mm      | 2.0e-8        |
| ~0.05 mm     | 1.0e-8        |

전체 옵션 설명: [hfdamp_full.yaml](hfdamp_full.yaml)
