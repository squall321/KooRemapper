# IGA (Isogeometric Analysis) 가이드

KooRemapper v1.3.1 기준 | LS-DYNA R12+ 전용

---

## 1. 개요

### 1.1 IGA란 무엇인가

IGA(Isogeometric Analysis, 등기하해석)는 CAD와 CAE를 통합하는 수치해석 방법론이다. 기존 유한요소법(FEM)이 Lagrange 다항식 기반의 형상 함수를 사용하는 반면, IGA는 NURBS(Non-Uniform Rational B-Spline)를 형상 함수로 직접 사용한다.

**FEM과 IGA의 주요 차이점:**

| 항목 | FEM (HEX8/TET4) | IGA (NURBS) |
|------|-----------------|-------------|
| 형상 함수 | Lagrange 다항식 | NURBS 기저함수 |
| 형상 표현 | 근사 (절점 보간) | 정확 (CAD와 동일) |
| 연속성 | C0 (요소 경계) | Cp-1 (p차 기준) |
| 제어점 | 해석 자유도와 일치 | CAD 제어점 역할 |
| 메시 세분화 | h-refinement (분할) | k-refinement (차수+세분화 동시) |
| 곡면 품질 | 메시에 의존 | NURBS로 항상 보장 |

IGA는 특히 얇은 쉘, 유체-구조 연성(FSI), 접촉 해석에서 FEM 대비 높은 정밀도를 보인다.

### 1.2 LS-DYNA에서의 IGA

LS-DYNA는 R12 버전부터 IGA solid 해석을 지원한다. KooRemapper가 활용하는 핵심 방식은 **Trimmed NURBS Volume**으로, 다음과 같은 구조를 가진다:

- `*IGA_DEV_VOLUME_XYZ` + `TETMSH=-1` 옵션
- 기존 FE tet/hex mesh를 내부 형상으로 사용 (trimming 경계)
- NURBS 직육면체 박스(trivariate B-spline patch)가 FE mesh를 완전히 감싸는 구조
- LS-DYNA가 FE mesh의 면을 trim 경계로 인식하여 NURBS 적분점을 내부에만 배치

이 방식의 장점은 기존 FE mesh를 그대로 활용하면서 NURBS의 고차 연속성 및 수렴성을 얻을 수 있다는 점이다.

### 1.3 KooRemapper가 자동화하는 것

KooRemapper의 `iga` 명령은 다음 과정을 완전 자동화한다:

1. **Bounding Box 계산**: 대상 FE 파트의 모든 절점 좌표에서 최소/최대값 탐색
2. **Offset 확장**: YAML 설정에 따른 bbox 확장 (고정값 / 비율 스케일 / 자동)
3. **NURBS 제어점 생성**: `nr×ns×nt` 직육면체 제어점 배치 (차수에 따라 자동 결정)
4. **파라미터 출력**: `*PARAMETER_LOCAL`로 모든 값 기록 (LS-DYNA 참조 가능)
5. **재질 복사**: 원본 FE 파트의 MAT 카드를 새 MID로 복사
6. **IGA 키워드 생성**: `*IGA_DEV_STABILIZATION`, `*PART`, `*SECTION_IGA_SOLID`, `*IGA_DEV_VOLUME_XYZ`, `*IGA_SOLID`, `*IGA_3D_NURBS_XYZ`, `*IGA_REFINE_SOLID`
7. **파일 분리 출력**: 파트별 `_iga_pN.k` 파일 생성
8. **메인 파일에 *INCLUDE 삽입**: FE mesh와 IGA 정의를 연결

---

## 2. 작동 원리

### 2.1 Trimmed NURBS Volume 개념

```
                   NURBS 박스 (IGA_3D_NURBS_XYZ)
        ┌─────────────────────────────────┐
        │  offset                         │
        │  ┌─────────────────────────┐    │
        │  │  FE Solid Part          │    │
        │  │  (TET4/HEX8 mesh)       │    │
        │  │                         │    │
        │  └─────────────────────────┘    │
        │                  offset         │
        └─────────────────────────────────┘
```

- **FE mesh**: 원본 LS-DYNA FE solid 파트 (trim 경계 역할)
- **NURBS 박스**: FE mesh bbox를 offset만큼 확장한 직육면체
- **TETMSH=-1**: LS-DYNA에 FE mesh의 외면을 trim 경계로 사용하라는 지시
- **적분점**: NURBS 박스 내부 + FE mesh 내부 영역에만 배치됨

### 2.2 생성 흐름

```
FE K-파일 로드
    ↓
대상 PID 절점 좌표 수집 (added elements 포함)
    ↓
BBox 계산: xmin/xmax/ymin/ymax/zmin/zmax
    ↓
Offset 계산 (bbox_scale or fixed offset or auto)
    ↓
새 ID 할당: newId = ++maxPartId_
새 MID 할당: newMid = ++maxMaterialId_
    ↓
원본 MAT 블록 추출 + MID 교체
    ↓
generateIGAContent() → *PARAMETER_LOCAL + 카드 직렬화
    ↓
igaFiles_ 목록에 추가
    ↓
writeOutput() 호출 시:
  - 메인 K파일: FE mesh 전체 + *INCLUDE _iga_pN.k
  - _iga_pN.k: IGA 정의 + *END
```

### 2.3 ID 할당 규칙

IGA 파트는 FE 파트와 다른 PID, SECID, MID를 사용해야 한다 (LS-DYNA 요건).

- **PID = SECID = newId**: 하나의 IGA 파트에 PID와 SECID를 동일하게 설정 (단일 연속 NURBS 패치이므로)
- **newId**: 현재 모델의 `maxPartId_`에 +1
- **newMid**: 현재 모델의 `maxMaterialId_`에 +1 (FE 파트 MID와 반드시 달라야 함)

---

## 3. YAML 문법

### 3.1 독립 실행 모드 (standalone iga command)

```
KooRemapper iga config.yaml
```

YAML 최상위 필드:

```yaml
base_model: block_2x2x1.k    # 입력 K-파일 (필수)
output: result                # 출력 prefix (필수, 확장자 없이)

targets:
  - target_pid: 1
    element_size: 4.0
    # ... 추가 파라미터
```

### 3.2 assemble 모드 (assemble 명령 내 operation)

```yaml
base_model: model.k
output: result

operations:
  - type: iga
    targets:
      - target_pid: 1
        element_size: 4.0
      - target_pid: 2
        element_size: 3.0
        element_size_r: 2.0
```

### 3.3 target 필드 전체 목록

| 필드 | 타입 | 기본값 | 설명 |
|------|------|--------|------|
| `target_pid` | int | 필수 | 대상 FE 파트 PID (단일) |
| `target_pids` | list | - | 동일 설정을 여러 PID에 일괄 적용 (예: `[1, 2, 3]`) |
| `element_size` | float | 1.0 | NURBS 박스의 균일 복셀 크기 (rr=rs=rt) |
| `element_size_r` | float | 0.0 | r(x)방향 복셀 크기 (0이면 element_size 사용) |
| `element_size_s` | float | 0.0 | s(y)방향 복셀 크기 (0이면 element_size 사용) |
| `element_size_t` | float | 0.0 | t(z)방향 복셀 크기 (0이면 element_size 사용) |
| `offset` | float | -1.0 | bbox 고정 확장량 (-1이면 auto = element_size 사용) |
| `bbox_scale` | float | 0.0 | 균일 bbox 스케일 (0=비활성; 1.5 = 각 측면 +25% 확장) |
| `bbox_scale_r` | float | 0.0 | r(x)방향 bbox 스케일 (0이면 bbox_scale 사용) |
| `bbox_scale_s` | float | 0.0 | s(y)방향 bbox 스케일 |
| `bbox_scale_t` | float | 0.0 | t(z)방향 bbox 스케일 |
| `ir` | int | 0 | 적분 방식 (0=reduced Gauss, 1=full Gauss) |
| `styp` | int | 4 | IGA_DEV_STABILIZATION의 LCP 안정화 타입 |
| `tollg` | float | 1.0e-3 | LCP 안정화 임계값 |
| `pr` | int | 1 | r(x)방향 NURBS 다항식 차수 (1=선형, 2=2차, 3=3차) |
| `ps` | int | 1 | s(y)방향 NURBS 다항식 차수 |
| `pt` | int | 1 | t(z)방향 NURBS 다항식 차수 |
| `nisr` | int | 1 | r방향 적분점 수 |
| `niss` | int | 1 | s방향 적분점 수 |
| `nist` | int | 1 | t방향 적분점 수 |

---

## 4. bbox 확장(offset) 계산 방법

NURBS 박스는 FE 파트의 bounding box보다 반드시 커야 한다 (FE mesh가 박스 안에 완전히 포함되어야 함). Offset은 각 축 방향으로 bbox를 얼마나 확장할지를 결정한다.

### 4.1 우선순위 (높은 순서)

```
1순위: bbox_scale_r/s/t (축별 스케일)
2순위: bbox_scale (균일 스케일)
3순위: offset >= 0 (고정 확장량)
4순위: auto = element_size (기본, offset=-1일 때)
```

각 축에 대해 독립적으로 계산된다.

### 4.2 수식

**bbox_scale 또는 bbox_scale_r/s/t 사용 시:**

```
off_axis = (scale - 1.0) / 2.0 × len_axis
```

여기서 `len_axis`는 해당 축 방향의 bbox 길이 (xmax-xmin, ymax-ymin, zmax-zmin).

예) bbox_scale=1.5, lenR=20.0:
```
offR = (1.5 - 1.0) / 2.0 × 20.0 = 5.0
```
결과: rxminn = xmin - 5.0, rxmaxx = xmax + 5.0

**고정 offset 사용 시 (offset >= 0):**

```
offR = offS = offT = offset (지정값 그대로)
```

**자동(auto) 사용 시 (offset = -1, 기본값):**

```
offR = rr (element_size_r 또는 element_size)
offS = rs (element_size_s 또는 element_size)
offT = rt (element_size_t 또는 element_size)
```

### 4.3 확장된 bbox 파라미터

계산된 확장 bbox는 `*PARAMETER_LOCAL`에 사전 계산된 값으로 저장된다
(LS-DYNA의 `*PARAMETER_EXPRESSION_LOCAL` 호환성 문제를 피하기 위함):

```
rxminn = xmin - offR    (NURBS 박스 x 최솟값)
rxmaxx = xmax + offR    (NURBS 박스 x 최댓값)
ryminn = ymin - offS    (NURBS 박스 y 최솟값)
rymaxx = ymax + offS    (NURBS 박스 y 최댓값)
rzminn = zmin - offT    (NURBS 박스 z 최솟값)
rzmaxx = zmax + offT    (NURBS 박스 z 최댓값)
```

---

## 5. NURBS 파라미터 의미

### 5.1 다항식 차수 (pr, ps, pt)

NURBS B-spline의 차수(degree)를 각 방향별로 지정한다.

| 값 | 의미 | 용도 |
|----|------|------|
| 1 | 선형 (C0 연속) | 단순 형상, 빠른 계산 |
| 2 | 2차 (C1 연속) | 응력 구배 표현, 얇은 부품 |
| 3 | 3차 (C2 연속) | 고정밀 해석, 복잡한 응력분포 |

**실용 가이드:**
- 얇은 평판 (두께 방향): `pt=1` 또는 `pt=2`로 시작
- 평면 방향: `pr=2`, `ps=2`로 수렴성 향상
- 계산 비용: 차수가 높을수록 비례하여 증가

차수 p와 요소 크기 h의 관계: 동일한 h-refined mesh에서 차수를 높이면 수렴 속도가 향상된다 (p-refinement 효과).

### 5.2 k-refinement와 요소 크기 (rr, rs, rt)

`rr/rs/rt`는 `*IGA_REFINE_SOLID`에서 사용하는 목표 요소 크기이다. k-refinement는 차수를 높이면서 동시에 knot을 삽입하는 IGA 고유의 세분화 방식이다.

```
*IGA_REFINE_SOLID
  rid    rtyp=2      ← 균일 refinement
  hrtyp=2  rr  rs  rt  ← h-refinement 요소 크기 목표
  itr=2  its=2  itt=2  ← 각 방향 minimum 분할 수
```

`rtyp=2`: 균일(uniform) refinement
`hrtyp=2`: h-type (요소 크기 기반) refinement
`itr/its/itt=2`: 각 방향 최소 2분할 보장

### 5.3 적분점 수 (nisr, niss, nist)

각 방향의 Gauss 적분점 수를 지정한다.

| 값 | 의미 |
|----|------|
| 1 | 기본 (reduced integration에서 충분) |
| 2 | 정밀 (고차 NURBS에서 권장) |

`nisr/niss/nist`는 `*IGA_SOLID` 카드에 직접 기록된다.

### 5.4 적분 방식 (ir)

| 값 | 명칭 | 특성 |
|----|------|------|
| 0 | Reduced Gauss | 빠름, 대부분의 경우 충분, 기본값 |
| 1 | Full Gauss | 정밀, volumetric locking 억제에 유리 |

`ir=0`이 기본이며, 대부분의 고체 해석에 적합하다. 비압축성 재료(고무 등)나 높은 포아송비에서는 `ir=1` 권장.

### 5.5 LCP 안정화 (styp, tollg)

`*IGA_DEV_STABILIZATION`은 IGA trimmed volume 경계에서의 LCP(Linear Complementarity Problem) 안정화를 제어한다.

| 파라미터 | 기본값 | 의미 |
|----------|--------|------|
| `styp=4` | 4 | 안정화 타입 (LS-DYNA 내부 정의) |
| `tollg=1e-3` | 1.0e-3 | 적분점 제거 임계값 (NURBS 박스 경계 근처 처리) |

`tollg`를 너무 크게 하면 필요한 적분점이 제거되어 정밀도 저하, 너무 작으면 경계 불안정 발생 가능.

---

## 6. 생성 파일 구조

### 6.1 메인 파일 (`<output>.k`)

원본 FE mesh를 완전히 보존하며, IGA 파트는 파트 정의 자체는 그대로 둔다 (FE tetmesh로 사용). 파일 끝에 `*INCLUDE`로 IGA 파일을 참조한다.

```
*KEYWORD
*TITLE
  (원본 제목)
*NODE
  (원본 절점 전체)
*ELEMENT_SOLID
  (원본 요소 전체 - IGA의 fepid로 사용됨)
*PART
  (원본 FE 파트 정의들)
*SECTION_SOLID
  (원본 섹션)
*MAT_ELASTIC (또는 원본 재질)
  (원본 재질 - MID 1)
*INCLUDE
 <output>_iga_p1.k
*INCLUDE
 <output>_iga_p2.k    (다중 파트의 경우)
*END
```

### 6.2 IGA 파일 (`<output>_iga_pN.k`)

파트별로 별도 파일이 생성된다. 파일명 형식: `<output_basename>_iga_p<PID>.k`

파일 전체 구조 (iga_single_result_iga_p1.k 예시):

```
*KEYWORD
$ IGA solid wrapper for FE part 1
$ Generated by KooRemapper
$---+----1----+----2----+----3----+----4----+----5----+----6----+----7----+----8
*PARAMETER_LOCAL
  (모든 파라미터 - 아래 6.3절 참조)
*MAT_ELASTIC (또는 원본 재질 타입)
  (MID = newMid로 복사)
*IGA_DEV_STABILIZATION
*PART
*SECTION_IGA_SOLID
*IGA_DEV_VOLUME_XYZ
*IGA_SOLID
*IGA_3D_NURBS_XYZ
*IGA_REFINE_SOLID
*END
```

---

## 7. 생성 카드 상세 해설

### 7.1 *PARAMETER_LOCAL

IGA 파일의 모든 수치값을 파라미터로 선언한다. 파라미터명 앞의 `I`는 정수(Integer), `R`은 실수(Real)를 의미한다.

**전체 파라미터 목록:**

| 파라미터명 | 타입 | 의미 |
|-----------|------|------|
| `Iid` | int | 이 IGA 파트의 PID = SECID |
| `Imid` | int | IGA 파트용 새 MID (FE와 다름) |
| `Ifepid` | int | 원본 FE 파트 PID (trim 경계) |
| `Rxmin` | real | FE bbox X 최솟값 |
| `Rxmax` | real | FE bbox X 최댓값 |
| `Rymin` | real | FE bbox Y 최솟값 |
| `Rymax` | real | FE bbox Y 최댓값 |
| `Rzmin` | real | FE bbox Z 최솟값 |
| `Rzmax` | real | FE bbox Z 최댓값 |
| `Rrr` | real | r방향 NURBS refinement 요소 크기 |
| `Rrs` | real | s방향 NURBS refinement 요소 크기 |
| `Rrt` | real | t방향 NURBS refinement 요소 크기 |
| `Rofr` | real | r방향 bbox 확장량 (offset) |
| `Rofs` | real | s방향 bbox 확장량 |
| `Roft` | real | t방향 bbox 확장량 |
| `Iir` | int | 적분 방식 (0=reduced, 1=full) |
| `Istyp` | int | LCP 안정화 타입 |
| `Rtollg` | real | LCP 임계값 |
| `Rrxminn` | real | NURBS 박스 X 최솟값 (= Rxmin - Rofr) |
| `Rrxmaxx` | real | NURBS 박스 X 최댓값 (= Rxmax + Rofr) |
| `Rryminn` | real | NURBS 박스 Y 최솟값 |
| `Rrymaxx` | real | NURBS 박스 Y 최댓값 |
| `Rrzminn` | real | NURBS 박스 Z 최솟값 |
| `Rrzmaxx` | real | NURBS 박스 Z 최댓값 |

**파라미터 참조 방식**: LS-DYNA 카드에서 `&id`, `&mid`, `&rxminn` 등으로 참조.

**형식 (10-char 고정폭 필드):**

```
Iid                3     ← 타입(I/R) + 이름(최대 9자)을 10자로 패딩, 값 10자 우측정렬
Rxmin              0
Rrxminn           -4
```

### 7.2 재질 카드 (*MAT_*)

원본 FE 파트의 MAT 카드를 그대로 복사하되, MID 필드를 `newMid`로 교체한다.

```
*MAT_ELASTIC
$#     mid        ro         e        pr        da        db  not used
         2  7.85E-09    210000       0.3
```

- `mid=2`: 새로 할당된 MID (원본 FE의 MID=1과 다름)
- 나머지 필드: 원본과 동일

원본 MAT를 찾지 못한 경우 경고 주석 + 더미 `*MAT_ELASTIC` (모든 값 0.0) 삽입.

### 7.3 *IGA_DEV_STABILIZATION

LCP 안정화 설정. Trimmed volume의 경계 처리를 위한 개발자 옵션.

```
*IGA_DEV_STABILIZATION
$#      sid      styp                                   tollg
       &id     &styp                                  &tollg
```

| 필드 | 파라미터 | 의미 |
|------|----------|------|
| SID | `&id` | Set ID (이 IGA 파트 ID와 동일) |
| STYP | `&styp` | 안정화 타입 (기본: 4) |
| TOLLG | `&tollg` | 적분점 제거 임계값 (기본: 1.0e-3) |

필드 3~5 (A1~A3)는 공백으로 둔다.

### 7.4 *PART

IGA 파트 정의. `pid`, `secid`, `mid` 모두 파라미터 참조.

```
*PART
$#
IGA_Part_1
$#     pid     secid       mid     eosid      hgid      grav    adpopt      tmid
      &id      &id     &mid
```

- 제목 행: `IGA_Part_<fepid>` (원본 FE PID 번호 포함)
- `pid = secid = &id`: 동일한 ID 공유 (NURBS patch 1개이므로)
- `mid = &mid`: IGA 전용 재질 ID (FE와 반드시 다름)
- `eosid, hgid, grav, adpopt, tmid`: 미입력 (기본값 사용)

### 7.5 *SECTION_IGA_SOLID

IGA solid 섹션 정의.

```
*SECTION_IGA_SOLID
$#   secid    elform        ir
      &id        0      &ir
```

| 필드 | 값 | 의미 |
|------|-----|------|
| SECID | `&id` | 섹션 ID (PID와 동일) |
| ELFORM | 0 | 요소 정식화 자동 (LS-DYNA가 선택) |
| IR | `&ir` | 적분 방식 (0=reduced, 1=full) |

### 7.6 *IGA_DEV_VOLUME_XYZ

Trimmed NURBS volume 정의 (핵심 카드).

```
*IGA_DEV_VOLUME_XYZ
$#     vid   patchid       pid      esid      fsid    TETMSH      MYTP
      &id      &id                                  -1
$#     PID of existing FEA solid with tetmesh
   &fepid
$#   brid1     brid2     brid3     brid4     brid5     brid6     brid7     brid8
(빈 행)
```

| 필드 | 값 | 의미 |
|------|-----|------|
| VID | `&id` | Volume ID |
| PATCHID | `&id` | NURBS patch ID (`*IGA_3D_NURBS_XYZ`의 patchid) |
| PID | (빈칸) | 이 볼륨이 속할 IGA 파트 PID (다음 카드에서 지정) |
| ESID | (빈칸) | 외면 집합 ID (미사용) |
| FSID | (빈칸) | 내면 집합 ID (미사용) |
| TETMSH | -1 | FE mesh를 trim 경계로 사용 (핵심!) |
| MYTP | (빈칸) | 미사용 |

다음 카드 (Card 2):

| 필드 | 값 | 의미 |
|------|-----|------|
| FE PID | `&fepid` | trim 경계로 사용할 FE 파트 PID |

Card 3 (brid1~brid8): 빈 행 (boundary representation ID, 미사용).

### 7.7 *IGA_SOLID

IGA solid 패치-파트 연결 카드.

```
*IGA_SOLID
$#     sid       pid      nisr      niss      nist       rid
      &id      &id        1        1        1      &id
```

| 필드 | 값 | 의미 |
|------|-----|------|
| SID | `&id` | Solid set ID |
| PID | `&id` | 연결할 IGA 파트 PID |
| NISR | nisr | r방향 적분점 수 |
| NISS | niss | s방향 적분점 수 |
| NIST | nist | t방향 적분점 수 |
| RID | `&id` | `*IGA_REFINE_SOLID`의 RID 참조 |

### 7.8 *IGA_3D_NURBS_XYZ

NURBS 볼륨 패치 정의 (B-spline 제어점, knot 벡터).

```
*IGA_3D_NURBS_XYZ
$# patchid        nr        ns        nt        pr        ps        pt
      &id        2        2        2        1        1        1
$#    unir      unis      unit
        1        1        1
$#            rfirst               rlast
             &rxminn             &rxmaxx
$#            sfirst               slast
             &ryminn             &rymaxx
$#            tfirst               tlast
             &rzminn             &rzmaxx
$#                 x                   y                   z                 wgt
             &rxminn             &ryminn             &rzminn                 1.0
             &rxmaxx             &ryminn             &rzminn                 1.0
             &rxminn             &rymaxx             &rzminn                 1.0
             &rxmaxx             &rymaxx             &rzminn                 1.0
             &rxminn             &ryminn             &rzmaxx                 1.0
             &rxmaxx             &ryminn             &rzmaxx                 1.0
             &rxminn             &rymaxx             &rzmaxx                 1.0
             &rxmaxx             &rymaxx             &rzmaxx                 1.0
```

**Card 1 필드:**

| 필드 | 값 | 의미 |
|------|-----|------|
| PATCHID | `&id` | 이 패치의 ID (IGA_DEV_VOLUME_XYZ와 일치) |
| NR | max(2, pr+1) | r방향 제어점 수 (차수에 따라 자동 결정) |
| NS | max(2, ps+1) | s방향 제어점 수 |
| NT | max(2, pt+1) | t방향 제어점 수 |
| PR | pr | r방향 다항식 차수 |
| PS | ps | s방향 다항식 차수 |
| PT | pt | t방향 다항식 차수 |

> **중요**: B-spline의 차수 p에 대해 제어점 수는 최소 p+1개 이상이어야 한다. pr=1이면 nr=2, pr=2이면 nr=3으로 자동 설정된다.

**Card 2 (unir/unis/unit):**

`unir=unis=unit=1`: 균일(uniform) knot 분포 지시자.

**Card 3~5 (knot 범위):**

- rfirst/rlast: r방향 knot 범위 (= NURBS 박스 x 범위, 수치로 직접 출력)
- sfirst/slast: s방향 knot 범위 (= NURBS 박스 y 범위)
- tfirst/tlast: t방향 knot 범위 (= NURBS 박스 z 범위)

**Card 6+ (제어점):**

`nr×ns×nt`개 제어점, 등간격 배치, 루프 순서: k(z) → j(y) → i(x).

pr=ps=pt=1 (기본 선형) 예시:

```
i=0,j=0,k=0: (rxminn, ryminn, rzminn, 1.0)  ← 최솟점
i=1,j=0,k=0: (rxmaxx, ryminn, rzminn, 1.0)
i=0,j=1,k=0: (rxminn, rymaxx, rzminn, 1.0)
i=1,j=1,k=0: (rxmaxx, rymaxx, rzminn, 1.0)
i=0,j=0,k=1: (rxminn, ryminn, rzmaxx, 1.0)
i=1,j=0,k=1: (rxmaxx, ryminn, rzmaxx, 1.0)
i=0,j=1,k=1: (rxminn, rymaxx, rzmaxx, 1.0)
i=1,j=1,k=1: (rxmaxx, rymaxx, rzmaxx, 1.0)  ← 최댓점
```

pr=2인 경우 r방향 제어점이 3개(rxminn, 중간점, rxmaxx)로 증가:

- 총 nr×ns×nt = 3×2×2 = 12개 제어점 (nr=3, ns=2, nt=2)

가중치(wgt)=1.0: NURBS이지만 직육면체이므로 모든 제어점 가중치 동일.

### 7.9 *IGA_REFINE_SOLID

NURBS solid에 대한 k-refinement 지시.

```
*IGA_REFINE_SOLID
$      rid      rtyp
      &id        2
$    hrtyp        rr        rs        rt
        2      &rr      &rs      &rt
$      itr       its       itt
        2        2        2
```

| 필드 | 값 | 의미 |
|------|-----|------|
| RID | `&id` | Refinement ID (`*IGA_SOLID`에서 참조) |
| RTYP | 2 | Refinement 타입: 2=균일(uniform) |
| HRTYP | 2 | h-refinement 타입: 2=요소 크기 기반 |
| RR | `&rr` | r방향 목표 요소 크기 |
| RS | `&rs` | s방향 목표 요소 크기 |
| RT | `&rt` | t방향 목표 요소 크기 |
| ITR | 2 | r방향 최소 refinement 반복 횟수 |
| ITS | 2 | s방향 최소 refinement 반복 횟수 |
| ITT | 2 | t방향 최소 refinement 반복 횟수 |

---

## 8. 예제 파일

### 8.1 block_2x2x1.k (기본 FE 베이스 모델)

20×10mm 평면 2×2 HEX8 메시, z방향 두 층(각 5mm):

```
*KEYWORD
*TITLE
2x2x1 HEX8 block - IGA upgrade example
*NODE
  nid 1~6:  z=0 면 (0,0,0) ~ (20,10,0)
  nid 7~12: z=5 면 (0,0,5) ~ (20,10,5)
  nid 13~18: z=10 면 (0,0,10) ~ (20,10,10)
*ELEMENT_SOLID
  eid=1,2: pid=1 (하부 레이어, z=0~5)
  eid=3,4: pid=2 (상부 레이어, z=5~10)
*PART
  pid=1: "Lower layer" (IGA upgrade target)
  pid=2: "Upper layer" (standard FE)
*SECTION_SOLID
  secid=1, elform=1 (LS-DYNA constant stress solid)
*MAT_ELASTIC
  mid=1, ro=7.85e-9 (강철 t/mm/s), E=210000 MPa, nu=0.3
*END
```

**형상 설명:**
- 전체 크기: x=0~20, y=0~10, z=0~10 (mm)
- PID 1 bbox: [0,20] × [0,10] × [0,5]
- PID 2 bbox: [0,20] × [0,10] × [5,10]
- 공유 절점: 7~12번 (z=5 평면)
- 재질: 강철 (AISI 4340 근사)

### 8.2 iga_single.yaml (최소 설정 예제)

```yaml
# 단일 파트 IGA - 최소 설정
base_model: block_2x2x1.k
output: iga_single_result

targets:
  - target_pid: 1
    element_size: 4.0
```

**결과 해석:**
- PID 1 bbox: x[0,20], y[0,10], z[0,5]
- auto offset = element_size = 4.0 (각 방향)
- NURBS 박스: x[-4,24], y[-4,14], z[-4,9]
- rr=rs=rt=4.0 (균일 복셀)
- 기본값: ir=0, styp=4, tollg=1e-3, pr=ps=pt=1, nisr=niss=nist=1

**생성 파일:**
- `iga_single_result.k`: 원본 FE + `*INCLUDE iga_single_result_iga_p1.k`
- `iga_single_result_iga_p1.k`: IGA 정의 (id=3, mid=2)

### 8.3 iga_multipart.yaml (다중 파트 예제)

```yaml
# 두 파트를 개별 IGA로 업그레이드
base_model: block_2x2x1.k
output: iga_multipart_result

targets:
  - target_pid: 1
    element_size: 4.0     # 균일 복셀 4mm
    ir: 0                 # reduced Gauss
    styp: 4
    tollg: 1.0e-3

  - target_pid: 2
    element_size: 3.0     # t방향 기본값
    element_size_r: 2.0   # r방향 더 촘촘 (2mm)
    element_size_s: 2.0   # s방향 더 촘촘 (2mm)
    ir: 1                 # full Gauss (정밀)
    pr: 2                 # r방향 2차
    ps: 2                 # s방향 2차
    pt: 1                 # t방향 1차 유지
```

**PID 2 결과:**
- rr=2.0, rs=2.0, rt=3.0 (축별 복셀)
- auto offset: offR=2.0, offS=2.0, offT=3.0
- PID 2 bbox: x[0,20], y[0,10], z[5,10]
- NURBS 박스: x[-2,22], y[-2,12], z[2,13]
- `*IGA_3D_NURBS_XYZ`의 pr=2, ps=2, pt=1 → nr=3, ns=3, nt=2 (자동)

**생성 파일:**
- `iga_multipart_result.k`
- `iga_multipart_result_iga_p1.k` (id=3, mid=2)
- `iga_multipart_result_iga_p2.k` (id=4, mid=3, nr=3×ns=3×nt=2)

### 8.4 iga_scale.yaml (bbox_scale 예제)

```yaml
# bbox_scale 기반 확장
base_model: block_2x2x1.k
output: iga_scale_result

targets:
  - target_pid: 1
    element_size: 4.0
    bbox_scale: 1.5         # 균일: 각 변 × 1.5 (양측 +25%)

  - target_pid: 2
    element_size: 3.0
    bbox_scale_r: 2.0       # r: +50% 양측
    bbox_scale_s: 1.3       # s: +15% 양측
    bbox_scale_t: 3.0       # t: +100% 양측
    ir: 1
```

**PID 1 계산:**
- lenR=20, lenS=10, lenT=5
- offR=(1.5-1)/2×20=5.0, offS=(1.5-1)/2×10=2.5, offT=(1.5-1)/2×5=1.25
- NURBS 박스: x[-5,25], y[-2.5,12.5], z[-1.25,6.25]

**PID 2 계산:**
- lenR=20, lenS=10, lenT=5 (z=5~10이므로 lenT=5)
- offR=(2.0-1)/2×20=10.0, offS=(1.3-1)/2×10=1.5, offT=(3.0-1)/2×5=5.0
- NURBS 박스: x[-10,30], y[-1.5,11.5], z[0,15]

### 8.5 iga_multipid.yaml (target_pids 일괄 적용 예제)

```yaml
# 여러 파트에 동일 설정 일괄 적용
base_model: block_2x2x1.k
output: iga_multipid_result

operations:
  - type: iga
    targets:
      - target_pids: [1, 2]    # PID 1과 2를 동일 설정으로
        element_size: 4.0
        ir: 0
        pr: 2
        ps: 2
        pt: 1
        bbox_scale: 1.4
```

`target_pids`에 PID 리스트를 지정하면 각 PID마다 bbox를 개별 계산하고 나머지 설정은 동일하게 적용한다. `target_pid`(단수)와 혼용 가능하다.

---

## 9. 주요 파라미터 선택 가이드

### 9.1 element_size 설정

```
권장: FE mesh 평균 요소 크기의 1~4배

얇은 판재 (두께 방향 HEX8 1층):
  element_size_t: 두께/2 ~ 두께×2 (두께 방향 NURBS 간격)
  element_size_r/s: 면내 HEX 크기의 2~4배

3D 솔리드:
  element_size: FE 요소 크기의 2~3배 (균일)
```

너무 작은 element_size → 과도한 NURBS refinement → 계산 비용 급증
너무 큰 element_size → 해상도 부족 → 응력 분포 불량

### 9.2 offset vs bbox_scale

**offset (고정값)**: 파트 크기와 무관하게 일정한 여유 확보할 때

```yaml
offset: 2.0    # 모든 방향 ±2mm
```

**bbox_scale (비율)**: 파트 크기 대비 일정 비율 여유를 원할 때

```yaml
bbox_scale: 1.2    # 파트 크기의 20% 여유
```

**auto (기본)**: offset=-1이면 element_size를 자동 적용

```yaml
# offset 미지정 = auto
element_size: 3.0    # offset도 3.0으로 자동
```

### 9.3 다항식 차수 선택

```
평판/쉘 유사 파트:
  pr: 2, ps: 2, pt: 1    (두께 방향은 선형)

3D 볼륨 고정밀:
  pr: 2, ps: 2, pt: 2    (전 방향 2차)

빠른 초기 계산:
  pr: 1, ps: 1, pt: 1    (선형, 기본값)
```

### 9.4 적분 방식 선택

```
일반 구조 해석:     ir: 0  (reduced, 기본)
비압축성 재료:      ir: 1  (full)
고차 NURBS (p≥3): ir: 1  권장
```

---

## 10. LS-DYNA 실행

### 10.1 실행 방법

IGA 파일은 단독 실행 불가 → 반드시 메인 K 파일로 실행:

```bash
# 단일 CPU
ls-dyna i=iga_single_result.k

# 병렬 (4 CPU)
ls-dyna i=iga_single_result.k ncpu=4

# MPP 버전
mpirun -np 4 ls-dyna_mpp i=iga_single_result.k
```

### 10.2 예상 Warning 메시지 (정상)

LS-DYNA 실행 시 다음 경고는 정상 동작이므로 무시:

| Warning 번호 | 내용 | 원인 |
|-------------|------|------|
| 11541 | Structured deck disabled | IGA 개발자 키워드 사용 시 정상 |
| 30128 | Massless node detected | NURBS 제어점은 질량 없음 (정상) |
| 30131 | Node not attached | NURBS 박스 내 미사용 절점 |

### 10.3 IGA 해석 결과 확인

- FE mesh 부분은 기존과 동일하게 d3plot에서 확인 가능
- IGA 파트 응력은 별도 IGA 결과 데이터베이스에 저장됨
- LS-PrePost에서 IGA 결과 확인: Results → IGA → ...

---

## 11. 알려진 제약사항

| 제약 | 내용 |
|------|------|
| Shell 파트 불가 | Solid 파트만 지원 (ELEMENT_SOLID) |
| 단일 NURBS 박스 | L형/C형/복잡한 형상은 단일 직육면체로 표현 불가 |
| FE mesh 포함 필요 | FE mesh가 NURBS 박스 안에 완전히 포함되어야 함 |
| LS-DYNA R12+ 필요 | `*IGA_DEV_*` 키워드는 R12 이상에서만 지원 |
| MID 공유 불가 | IGA 파트와 FE 파트는 반드시 다른 MID 사용 |
| FE mesh 타입 | TET4, HEX8 등 solid 요소 타입 가능 |
| offset > 0 필수 | NURBS 박스가 FE mesh와 정확히 일치하면 안 됨 |

---

## 12. 변경 이력

| 버전 | 내용 |
| ------ | ------ |
| v1.2.x | 초기 IGA 기능 구현 (단일 파트, `assemble` op 내 지원) |
| v1.3.0 | 다중 파트 지원, bbox_scale (균일/축별), 축별 element_size, standalone `iga` 명령 추가 |
| v1.3.1 | `target_pids` 리스트 지원 (여러 파트 일괄 적용), `nr=max(2,pr+1)` 자동 계산 (고차 B-spline 제어점 부족 버그 수정), `base_model:` YAML 키 추가, `IGA_DEV_STABILIZATION` field 정렬 수정, LS-DYNA R16.1에서 single/multipart 실행 검증 완료 |

---

## 부록 A. 전체 IGA 파일 예시 (iga_single_result_iga_p1.k)

```
*KEYWORD
$ IGA solid wrapper for FE part 1
$ Generated by KooRemapper
$---+----1----+----2----+----3----+----4----+----5----+----6----+----7----+----8
*PARAMETER_LOCAL
$    PRMR1      VAL1
Iid                3
Imid               2
Ifepid             1
Rxmin              0
Rxmax             20
Rymin              0
Rymax             10
Rzmin              0
Rzmax              5
Rrr                4
Rrs                4
Rrt                4
Rofr               4
Rofs               4
Roft               4
Iir                0
Istyp              4
Rtollg         0.001
Rrxminn           -4
Rrxmaxx           24
Rryminn           -4
Rrymaxx           14
Rrzminn           -4
Rrzmaxx            9
*MAT_ELASTIC
$#     mid        ro         e        pr        da        db  not used
         2  7.85E-09    210000       0.3
*IGA_DEV_STABILIZATION
$#      sid      styp                                   tollg
       &id     &styp                                  &tollg
*PART
$#
IGA_Part_1
$#     pid     secid       mid     eosid      hgid      grav    adpopt      tmid
      &id      &id     &mid
*SECTION_IGA_SOLID
$#   secid    elform        ir
      &id        0      &ir
*IGA_DEV_VOLUME_XYZ
$#     vid   patchid       pid      esid      fsid    TETMSH      MYTP
      &id      &id                                  -1
$#     PID of existing FEA solid with tetmesh
   &fepid
$#   brid1     brid2     brid3     brid4     brid5     brid6     brid7     brid8

*IGA_SOLID
$#     sid       pid      nisr      niss      nist       rid
      &id      &id        1        1        1      &id
*IGA_3D_NURBS_XYZ
$# patchid        nr        ns        nt        pr        ps        pt
      &id        2        2        2        1        1        1
$#    unir      unis      unit
        1        1        1
$#            rfirst               rlast
             &rxminn             &rxmaxx
$#            sfirst               slast
             &ryminn             &rymaxx
$#            tfirst               tlast
             &rzminn             &rzmaxx
$#                 x                   y                   z                 wgt
             &rxminn             &ryminn             &rzminn                 1.0
             &rxmaxx             &ryminn             &rzminn                 1.0
             &rxminn             &rymaxx             &rzminn                 1.0
             &rxmaxx             &rymaxx             &rzminn                 1.0
             &rxminn             &ryminn             &rzmaxx                 1.0
             &rxmaxx             &ryminn             &rzmaxx                 1.0
             &rxminn             &rymaxx             &rzmaxx                 1.0
             &rxmaxx             &rymaxx             &rzmaxx                 1.0
*IGA_REFINE_SOLID
$      rid      rtyp
      &id        2
$    hrtyp        rr        rs        rt
        2      &rr      &rs      &rt
$      itr       its       itt
        2        2        2
*END
```

---

## 부록 B. 자주 묻는 질문

**Q: IGA 파트와 FE 파트가 같은 공간을 공유해도 되나요?**
A: 네. IGA 파트(NURBS 박스)는 FE 파트와 물리적으로 겹칩니다. LS-DYNA가 `TETMSH=-1`과 `fepid`를 통해 FE mesh를 trim 경계로 사용하기 때문에, IGA와 FE 해석 영역은 동일한 형상을 공유합니다.

**Q: FE와 IGA 파트 간 접촉/구속은 어떻게 처리하나요?**
A: `*TETMSH=-1` 방식에서 LS-DYNA가 내부적으로 coupling을 처리합니다. 별도 `*CONSTRAINED_*` 카드 불필요.

**Q: 여러 번 assemble op를 거친 후 IGA를 적용해도 되나요?**
A: 네. `applyIGA()`는 `addedElements_`와 `modifiedNodePositions_`도 포함하여 bbox를 계산하므로, replace/restack 이후에 적용해도 정상 동작합니다.

**Q: offset을 0으로 설정하면 어떻게 되나요?**
A: `offset: 0.0` (0 이상의 값)으로 설정하면 NURBS 박스 = FE bbox (확장 없음). FE mesh 표면이 NURBS 박스와 정확히 일치하게 되어 경계 처리 문제가 발생할 수 있습니다. 최소 요소 크기의 10% 이상 offset 권장.

**Q: *MAT_024 같은 탄소성 재질도 지원하나요?**
A: 네. `extractMaterialBlock()`이 `*MAT_*` 키워드 종류와 무관하게 원본 카드를 복사합니다. MAT_ELASTIC, MAT_024, MAT_RIGID 등 모두 지원됩니다.

**Q: 생성된 IGA 파일을 수동으로 편집해도 되나요?**
A: `*PARAMETER_LOCAL`의 값을 수정하면 연결된 모든 카드에 자동 반영됩니다. 단, 파라미터명 형식(Iname, Rname, 10자 필드)을 유지해야 합니다.
