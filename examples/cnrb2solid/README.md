# cnrb2solid 예제

CNRB(강체 볼트)를 O-grid HEX8 솔리드 실린더로 변환합니다.

## 빠른 시작

```bash
# 기본 변환 (볼트 헤드 없음)
KooRemapper cnrb2solid basic.yaml

# 볼트 헤드(플랜지) 포함
KooRemapper cnrb2solid with_head.yaml

# 모든 옵션 확인
KooRemapper cnrb2solid cnrb2solid_full.yaml
```

## 예제 파일

| 파일 | 설명 |
|------|------|
| `basic.yaml` | 최소 설정, 헤드 없음 |
| `with_head.yaml` | `head_offset_r`, `head_thickness` 옵션 사용 |
| `cnrb2solid_full.yaml` | 전체 옵션 + 각 항목 설명 |
| `assemble_bolts.yaml` | assemble 파이프라인에서 사용하는 예제 |
| `bolt_simple.k` | 입력 예제 모델 (R=3mm, Z=0/5/10, 8노드/레벨) |

## YAML 최소 구성

```yaml
model: bolt_simple.k
output: bolt_solid.k

E:   200000.0   # Young's modulus [MPa]
PR:  0.3
RHO: 7.85e-9   # [t/mm³]
```

## assemble 파이프라인 사용

```yaml
# assemble config에 포함
base_model: my_model.k
output: my_model_solid

operations:
  - type: cnrb2solid
    E:   200000.0
    PR:  0.3
    RHO: 7.85e-9
    # head_offset_r: 1.5   # 헤드 반경 오프셋 (없으면 헤드 미생성)
    # head_thickness: 2.0
```

## 주요 옵션

| 옵션 | 기본값 | 설명 |
|------|--------|------|
| `radius_scale` | 0.999 | 링 노드 반경 = 볼트홀 R × scale (살짝 안쪽) |
| `num_circum_nodes` | 0 (자동) | 원주 노드 수, 0이면 자동 감지 (4의 배수) |
| `inner_radius_ratio` | 0.3 | 코어 사각형 반변 / R 비율 |
| `axis_direction` | auto | 실린더 축 방향: auto / x / y / z |
| `z_tolerance` | 0.1 | Z-레벨 그룹핑 허용 오차 [mm] |
| `r_tolerance` | 0.5 | 반경 클러스터링 허용 오차 [mm] (스텝 볼트용) |
| `head_offset_r` | 0.0 | 볼트 헤드 반경 오프셋. 0이면 헤드 미생성 |
| `head_thickness` | 2.0 | 볼트 헤드 두께 [mm] |
| `head_position` | auto | 헤드 위치: auto / top / bottom / none |

전체 옵션 및 설명은 [cnrb2solid_full.yaml](cnrb2solid_full.yaml) 참고.
