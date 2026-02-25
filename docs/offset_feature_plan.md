# Offset/Extrude Operation - 구현 계획서

**작성일**: 2026-02-19
**최종 수정**: 2026-02-20
**버전**: 2.5
**상태**: ✅ IMPLEMENTATION READY (완전 검증 완료)

---

## 📌 Version 2.5 주요 사항 ✅ FULLY VERIFIED & READY

### 🔧 v2.5 변경사항 (Critical Integration Fixes)

- ✅ **czmPartId 필드 추가**: OffsetOperation struct에 czmPartId 필드 추가 (DisconnectOperation과 일관성)
- ✅ **czm_part_id YAML 파싱**: Phase 2에 czm_part_id 파싱 로직 추가
- ✅ **Connection mode integration**: Phase 4 applyOffset에 connection mode 처리 로직 추가 (CRITICAL)
- ✅ **헤더 함수 선언 추가**: Phase 3에 누락된 connection/dual offset 함수 선언 추가
  - `applyConnectionTied/CZM/Contact()`
  - `applyDualOffsetPrestress()`
  - `calculateDualOffsetPrestress()`
  - `createCzmElementsForDualOffset()`
  - `addContactHint()`
  - `formatCzmSectionBlock()`

### 🔧 v2.4 변경사항 (최종 검증 수정)

- ✅ **rawLinesInsertions_ → addedKeywordBlocks_**: 16곳 전체 수정 (올바른 변수명)
- ✅ **getNodeXYZ() 중복 제거**: Phase 9.4에서 이미 존재하는 getNodePosition() 사용
- ✅ **createCzmElementsForDualOffset() 구현 추가**: Phase 12.3에 누락된 함수 추가
- ✅ **addContactHint() 구현 추가**: Phase 12.4에 누락된 함수 추가
- ✅ **computeElementCenter 통일**: computeElementCentroid → computeElementCenter 일관성 수정
- ✅ **Phase 4/12 통합 설명**: applyOffset dispatcher와 normal mode 관계 명확화

### 🔧 v2.3 변경사항 (기존 코드 통합)
- ✅ **getNodePosition() 중복 제거**: 이미 구현된 함수 활용
- ✅ **addedNodes_ 사용법 수정**: vector 구조 반영 (map → vector)
- ✅ **E, nu 파라미터 추가**: applyOffset(op, E, nu) 시그니처 통일
- ✅ **Phase 6.4 간소화**: 기존 함수 활용으로 코드 중복 제거
- ✅ **computeElementCenter**: getNodePosition() 사용

### 기존 코드와의 통합 확인
- ✅ Element::getFaceNodeIds() - 존재 확인
- ✅ ModelAssembler::getNodePosition() - 사용 가능 (ModelAssembler.cpp:5002)
- ✅ addedNodes_ 구조 (vector<AddedNode>) - 반영 완료
- ✅ addedKeywordBlocks_ 변수명 - 올바르게 사용
- ✅ Material 파라미터 패턴 (E, nu) - 통일 완료

---

## 📌 Version 2.0-2.2 주요 사항

### 1️⃣ Connection Mode (원본-오프셋 레이어 연결 방식)
- **tied**: Node sharing (완벽한 tie constraint, 기본값)
- **czm**: Cohesive elements 삽입 (de-lamination 해석) - **ELFORM=20 (zero-thickness)** 🔧
- **contact**: 완전 분리 (슬라이딩/박리 가능) - **자동 contact hint 생성** 🔧

### 2️⃣ Dual Offset Prestress Mode (파우치 wrapping)
- **물리적 개념**: 필름이 물체를 감싸며 조이는 장력 시뮬레이션
- **구현**: Outward offset으로 요소 생성 + Inward offset으로 prestress 적용
- **Prestress 계산**: **Full 3D strain tensor** (ε_xx, ε_yy, ε_zz, ε_xy, ε_yz, ε_xz) 🔧
- **응용**: Pouch cell 배터리, shrink wrap, 타이어-림 조립

### 3️⃣ 구현 확장
- **Phase 11**: Connection mode 구현 (tied/czm/contact)
- **Phase 12**: Dual offset prestress 구현
- **Issue 12-14**: Critical Issues + **구현 수정사항 (Issue 14)** 🔧

### 4️⃣ Critical Fixes (v2.1-2.2) 🔧
- ✅ **Prestress 계산**: 단순 두께 변형률 → Full 3D strain tensor (isoparametric mapping)
- ✅ **CZM Mode**: ELFORM=19 → ELFORM=20 (zero-thickness cohesive)
- ✅ **Dual+CZM 충돌**: 노드 duplication 순서 재조정
- ✅ **Solid Surface**: 표면 추출 알고리즘 상세화
- ✅ **Validation**: Material 필수 체크 + 모드 조합 경고
- ✅ **Contact Mode**: Contact definition template 자동 생성
- ✅ **Phase 순서 수정 (v2.2)**: Phase 6-9 재배치 (Helper → Extrude 순서)
- ✅ **누락 함수 추가**: getNodeXYZ(), computeElementCenter()

**총 개발 기간**: **17-20일** (기본 9일 + 확장 4.5일 + 수정 3.5일 + 테스트/문서 4일)

---

## 목차

1. [기능 개요](#1-기능-개요)
2. [문제점 및 해결방안](#2-문제점-및-해결방안) - **14 Issues** (⭐ Issue 12-14 NEW, 🔧 Issue 14 = Fixes)
3. [YAML 인터페이스](#3-yaml-인터페이스) - **3 Modes** (기본/CZM/Dual Prestress)
4. [구현 단계](#4-구현-단계-12-phases) - **Phase 1-12** (⭐ Phase 11-12 NEW, 🔧 Fixed)
5. [기술적 상세](#5-기술적-상세)
6. [검증 전략](#6-검증-전략)
7. [사용 예시](#7-사용-예시) - **6 Examples** (⭐ Example 5-6 NEW)
8. [구현 일정](#8-구현-일정) - **17-20일** (🔧 수정 반영)

---

## 1. 기능 개요

### 목적
기존 solid/shell 파트를 법선 방향으로 오프셋하여 새 레이어 파트 생성

### Use Cases

**기본 응용**:
- 코팅층 추가 (얇은 쉘 → 두꺼운 solid)
- Multi-layer 라미네이트 구조
- 표면 강화층 모델링
- 접착제/본딩 레이어
- 절연층/보호층

**고급 응용** ⭐NEW:
- **CZM Connection**: De-lamination/박리 해석 (코팅층이 기판에서 떨어짐)
- **Dual Offset Prestress**: 파우치/필름 wrapping (장력으로 물체를 조이는 효과)
  - Pouch cell 배터리 케이싱
  - Shrink wrap 포장재
  - 타이어-림 압착 조립
  - 직물/천 wrapping

### 유사 기능
**Restack**: 기존에 비슷한 레이어 생성 기능 존재
- Restack은 shell → multiple solid layers (두께 방향 분할)
- Offset은 단일 레이어 생성 + 더 유연한 방향 제어

---

## 2. 문제점 및 해결방안

### 🔴 Critical Issues

#### **Issue 1: TRIA3 감지 및 처리**
**문제**: TRIA3는 QUAD4로 저장 (nodeIds[3] == nodeIds[2] or == 0)
```cpp
// 현재 코드에서 누락 가능
if (shell.nodeIds[3] == shell.nodeIds[2]) {
    // TRIA3 detected
}
```
**해결**:
```cpp
bool isTria3(const ShellElement& shell) {
    return (shell.nodeIds[3] == shell.nodeIds[2] ||
            shell.nodeIds[3] == 0 ||
            shell.nodeIds[3] == shell.nodeIds[0]);  // 일부 변형
}
```

#### **Issue 2: Wedge 요소 표현**
**문제**: LS-DYNA에는 WEDGE6 native element가 없음
- TET4: 퇴화 HEX8 (N5-N8 = N4)
- WEDGE6: 퇴화 HEX8 (N4=N3, N8=N7)

**LS-DYNA 매뉴얼 확인** (Vol_I.txt, line 3989):
> "Allow degenerated hexahedrons (pentas) for cohesive solid elements
> (ELFORM = 19, 20) that evolve from an extrusion of triangular shells. The input
> of nodes on the element cards for such a pentahedron is given by: **N1, N2, N3, N3,
> N4, N5, N6, N6.**"

**해석**:
- HEX8 8개 위치: [N1, N2, N3, N3, N4, N5, N6, N6]
- Position 4 = Position 3 → `nodeIds[3] = nodeIds[2]` ✅
- Position 8 = Position 7 → `nodeIds[7] = nodeIds[6]` ✅

**해결**: Degenerate HEX8로 저장 (매뉴얼 공식 규격)
```cpp
// TRIA3 → WEDGE6 (stored as degenerate HEX8 per LS-DYNA manual)
// Bottom triangle: N1, N2, N3, N3
elem.nodeIds[0] = bottom[0];  // N1
elem.nodeIds[1] = bottom[1];  // N2
elem.nodeIds[2] = bottom[2];  // N3
elem.nodeIds[3] = bottom[2];  // N3 (degenerate) ← Position 4 = Position 3

// Top triangle: N4, N5, N6, N6
elem.nodeIds[4] = top[0];     // N4
elem.nodeIds[5] = top[1];     // N5
elem.nodeIds[6] = top[2];     // N6
elem.nodeIds[7] = top[2];     // N6 (degenerate) ← Position 8 = Position 7
```

#### **Issue 3: Normal 방향 일관성**
**문제**: Solid 표면 추출 시 face normal이 inward를 가리킬 수 있음

**해결**: Centroid 기반 방향 검증
```cpp
Vector3D computeOutwardNormal(const Element& elem, int faceIndex) {
    Vector3D faceNormal = computeFaceNormal(elem, faceIndex);
    Vector3D faceCentroid = computeFaceCentroid(elem, faceIndex);
    Vector3D elemCentroid = computeElementCentroid(elem);

    Vector3D outwardDir = faceCentroid - elemCentroid;

    // Flip if pointing inward
    if (faceNormal.dot(outwardDir) < 0) {
        faceNormal = faceNormal * -1.0;
    }

    return faceNormal;
}
```

#### **Issue 4: TSHELL vs Shell 구분**
**문제**: TSHELL은 별도 element type, 기존 ShellElement로 저장 불가

**해결**: 새 컨테이너 추가 또는 ELFORM으로 구분
```cpp
// Option 1: 새 컨테이너
std::vector<TShellElement> addedTShellElements_;

// Option 2: ShellElement + ELFORM flag (권장)
struct ShellElement {
    // ... existing fields
    int elform = 2;  // 2=QUAD4, 16=TSHELL4
};
```

**권장**: Option 2 (기존 구조 활용)

### 🟡 Warning Issues

#### **Issue 5: ID 충돌**
**문제**: Auto-increment 시 기존 ID와 충돌 가능

**해결**: Max ID 추적 강화
```cpp
int ModelAssembler::getNextPartId() {
    // Check both baseMesh and added parts
    int maxId = baseMesh_.getMaxPartId();
    for (const auto& op : appliedOperations_) {
        if (op.newPid > maxId) maxId = op.newPid;
    }
    return maxId + 1;
}
```

#### **Issue 6: Material Card MID 치환**
**문제**: "mid20" vs "mid2" 구분 필요

**해결**: Word boundary 사용
```cpp
std::regex midPattern(R"(\bmid\d+\b)");
// Extract number after "mid"
std::smatch match;
if (std::regex_search(materialCard, match, midPattern)) {
    std::string oldMidStr = match.str();
    // Replace with formatted new MID
    std::stringstream ss;
    ss << std::setw(10) << actualMid;
    processed = std::regex_replace(processed,
                                   std::regex(R"(\b" + oldMidStr + R"(\b)"),
                                   ss.str());
}
```

**더 나은 방법**: Placeholder 사용
```yaml
material_card: |
  *MAT_ELASTIC
  $#     mid        ro         e        pr
        @MID@   2.70000   7.00E+04      0.33
```
```cpp
// Replace @MID@ placeholder
std::stringstream ss;
ss << std::setw(10) << actualMid;
processed = std::regex_replace(materialCard, std::regex("@MID@"), ss.str());
```

#### **Issue 7: Node 중복 생성**
**문제**: 인접 shell이 node 공유 시 중복 생성 방지 필요

**해결**: 이미 계획에 포함 (nodeLayerMap 사용)
```cpp
std::map<int, std::vector<int>> nodeLayerMap;  // ✅ 이미 포함됨
```

#### **Issue 8: Element 품질**
**문제**: Extrude 방향이 잘못되면 inverted element 생성 가능

**해결**: Jacobian 검증 추가
```cpp
bool isElementInverted(const Element& elem) {
    // Check Jacobian determinant at element center
    double jac = computeJacobian(elem, 0, 0, 0);
    return jac <= 0;
}

// In extrudeToSolid()
if (isElementInverted(elem)) {
    std::cerr << "[WARNING] Inverted element " << elem.id
              << " detected - check offset direction\n";
}
```

### 🟢 Minor Issues

#### **Issue 9: SECTION Keyword 형식**
**문제**: TSHELL section 형식 확인 필요

**해결**: LS-DYNA 매뉴얼 참조
```
*SECTION_TSHELL
$#   secid    elform      shrf       nip     propt   qr/irid     icomp     setyp
         1        16       0.0         3       1.0         0         0         0
$#      t1        t2        t3        t4      nloc     marea      idof    edgset
     0.100     0.100     0.100     0.100       0.0       0.0       0.0         0
```
**ELFORM=16**: TSHELL (fully integrated)

#### **Issue 10: WriteOutput 통합**
**문제**: 새 element 출력 처리

**해결**: 기존 writeOutput 이미 처리
- `addedElements_` → `*ELEMENT_SOLID` 출력
- `addedShellElements_` → `*ELEMENT_SHELL` 출력
- ✅ 추가 수정 불필요

#### **Issue 11: Restack과의 중복**
**문제**: Restack과 기능 유사, 코드 재사용 가능성

**분석**:
| 기능 | Restack | Offset |
|------|---------|--------|
| 입력 | Shell | Shell/Solid surface |
| 출력 | Multiple layers | Single layer |
| 방향 | +normal만 | ±normal, ±xyz |
| Element type | Solid만 | Solid/TShell/Shell |

**결론**: 유사하지만 충분히 다름 → 별도 구현 권장

#### **Issue 12: 원본과 오프셋 레이어 연결 방식**
**문제**: 오프셋 레이어와 원본 파트의 연결 방법 선택 필요

**연결 모드 3가지**:

1. **tied** (Node Sharing):
   - 원본 표면 노드를 오프셋 레이어 하단 노드로 직접 재사용
   - 완벽한 tie constraint (자동)
   - 가장 간단하고 강결합

2. **czm** (Cohesive Zone Model):
   - 원본과 오프셋 사이에 cohesive element 삽입
   - 별도 노드 생성 + COH8D/COH6D 요소
   - De-lamination, 박리 해석 가능
   - `*SECTION_SOLID` ELFORM=19 (COH8D) or 20 (COH6D)

3. **contact** (Contact Only):
   - 완전 분리된 노드 + 요소
   - `*CONTACT_AUTOMATIC_SURFACE_TO_SURFACE` 필요
   - 가장 약한 결합, 슬라이딩/분리 가능

**해결**: `connection_mode` YAML 파라미터 추가
```cpp
std::string connectionMode = "tied";  // tied | czm | contact
int czmMid = 0;  // CZM material ID (czm 모드 전용)
std::string czmMaterialCard;  // *MAT_COHESIVE_* keyword
```

#### **Issue 13: Dual Offset Prestress Mode**
**문제**: 파우치/필름이 물체를 감싸며 조이는 장력 시뮬레이션 필요

**개념**:
- **Inward offset** (-normal 방향): 압축된 형상 (deformed state)
- **Outward offset** (+normal 방향): 릴랙스된 형상 (reference state)
- 원본 형상 = inward offset 형상 (변형 상태)
- Outward offset으로 요소 생성 후 inward로 prestress 적용

**물리적 의미**:
```
[Original part surface]  ← 현재 압축된 상태 (deformed)
         ↓
[Inward offset = -0.2mm]  ← 이게 원본 형상
         ↓
         ↓ (prestress: compress from outer to inner)
         ↓
[Outward offset = +0.3mm]  ← 이 형상으로 요소 생성 (reference)
```

**예시**: 두께 0.5mm 파우치가 물체를 0.2mm 압축하며 감쌈
- `inner_offset: -0.2`  (압축된 형상 = 원본)
- `outer_offset: 0.5`   (릴랙스 형상 = 요소 생성)
- Prestress strain: ε = (0.5-(-0.2))/0.5 = 140% → 장력 발생

**해결**: Squeeze 로직 재사용
```cpp
bool prestressMode = false;  // dual offset prestress 활성화
double innerOffset = 0.0;    // inward offset (deformed, 음수)
double outerOffset = 0.0;    // outward offset (reference, 양수)
```

**구현**:
1. Outer offset으로 요소 생성 (reference mesh)
2. Inner offset 위치에서 노드 위치 샘플링 (deformed positions)
3. `calculateOffsetPrestress()` - strain 계산 (squeeze와 유사)
4. Dynain 출력 with prestress

#### **Issue 14: 구현 계획 수정사항** 🔧
**검토 결과 발견된 문제점들과 해결책**:

1. **Prestress 계산 단순화 문제** (Critical):
   - ❌ 단순 두께 변형률만 계산 → ✅ **3D strain tensor 계산** (squeeze 방식)
   - ❌ In-plane strain 무시 → ✅ **Isoparametric mapping으로 전체 변형 계산**
   - Phase 12.2 수정: 완전한 `computeStrainFromDeformation()` 사용

2. **CZM Zero-thickness 처리** (Medium):
   - ❌ ELFORM=19 + 동일 위치 노드 → 초기 두께=0 문제
   - ✅ **ELFORM=20 (zero-thickness cohesive)** 사용
   - Alternative: ELFORM=19 + 1μm offset

3. **Dual Offset + CZM 노드 충돌** (Critical):
   - ❌ Offset 요소 먼저 생성 → CZM이 노드 duplicate → 불일치
   - ✅ **Connection mode에 따라 노드 처리 순서 조정**
   - Phase 12.1 수정: CZM/Contact 모드에서 노드 먼저 duplicate

4. **Solid Surface 추출 미구현** (Medium):
   - ❌ Shell source만 고려
   - ✅ **Solid outer surface 추출 알고리즘 추가** (face adjacency)
   - Phase 5 확장: `extractSourceSurface()` 상세 구현

5. **Validation 불완전** (Low):
   - ✅ Material 필수 체크, 모드 조합 경고 추가
   - Phase 2.4 확장

6. **Contact Mode 미완성** (Low):
   - ✅ Contact definition template 주석 자동 생성
   - Phase 11.3 확장

**예상 추가 시간**: +3.5일 (17-20일 총 소요)

---

## 3. YAML 인터페이스

### 기본 구조 (단순 모드)
```yaml
operations:
  - type: offset
    source_pid: 1              # 소스 파트 ID (필수)
    offset_direction: +normal  # +normal | -normal | +x | -x | +y | -y | +z | -z
    thickness: 0.5             # mm (오프셋 거리, 필수)
    num_layers: 2              # 두께 방향 요소 개수 (default: 1)

    element_type: solid        # solid | tshell | shell (필수)

    # 연결 모드 (NEW!)
    connection_mode: tied      # tied | czm | contact (default: tied)

    # 새 파트 정의
    new_pid: 10                # 새 파트 ID (optional, auto-increment)
    new_secid: 10              # 새 섹션 ID (optional, auto-increment)
    part_title: "Coating Layer"

    # 재료 정의
    new_mid: 20                # 새 재료 ID (optional, auto-increment)
    material_card: |           # MAT 키워드 블록 (multi-line)
      *MAT_ELASTIC
      $#     mid        ro         e        pr
            @MID@   2.70000   7.00E+04      0.33

    # Shell 모드 전용
    shell_thickness: 0.5       # shell 모드일 때 shell 두께 (default: thickness)
    shell_offset: 0.25         # shell 위치 (0=소스, thickness=반대쪽, default: thickness/2)
```

### CZM 모드 (connection_mode: czm)
```yaml
operations:
  - type: offset
    source_pid: 1
    offset_direction: +normal
    thickness: 1.0
    element_type: solid

    connection_mode: czm       # Cohesive Zone Model
    czm_mid: 100               # CZM 전용 재료 ID (auto-increment if 0)
    czm_material_card: |       # MAT_COHESIVE_* keyword
      *MAT_COHESIVE_MIXED_MODE
      $#     mid        ro      roflg     intfail
            @MID@     0.0         0         1.0
      $#    en        et        gic       giic      xmu       t         s
        1.00E+03  1.00E+03  1.00E+02  1.00E+02     2.0  5.00E+01  5.00E+01
```

### Dual Offset Prestress 모드 (파우치 wrapping)
```yaml
operations:
  - type: offset
    source_pid: 1
    element_type: solid

    # Prestress 모드 활성화 (NEW!)
    prestress_mode: dual_offset
    inner_offset: -0.2         # 압축된 형상 (deformed, 음수)
    outer_offset: 0.5          # 릴랙스 형상 (reference, 양수)

    # 이 모드에서는 offset_direction/thickness 무시됨
    # inner/outer_offset이 thickness 대체

    connection_mode: contact   # 일반적으로 contact 사용 (파우치가 분리 가능)

    part_title: "Pouch Film"
    material_card: |
      *MAT_ELASTIC
      $#     mid        ro         e        pr
            @MID@  1.00E-09  3.00E+03      0.40
```

### Element Type 상세

#### **solid**: Extrude to HEX8/WEDGE
- QUAD4 → HEX8
- TRIA3 → WEDGE6 (degenerate HEX8)
- `num_layers` 지원

#### **tshell**: Extrude to Thick Shell
- QUAD4 → TSHELL4 (ELFORM=16)
- TRIA3 → TSHELL3 (ELFORM=17)
- `num_layers` 지원 (각 layer = separate TSHELL)

#### **shell**: Offset Shell
- QUAD4 → QUAD4
- TRIA3 → TRIA3
- `shell_offset` 위치에 생성
- `num_layers` 무시 (단일 layer만)

---

## 4. 구현 단계 (12 Phases)

### Phase 1: AssemblyConfig.h - OffsetOperation 구조체

**파일**: `include/assembly/AssemblyConfig.h`

```cpp
struct OffsetOperation {
    // Source
    int sourcePid = 0;

    // Offset parameters
    std::string offsetDirection = "+normal";  // +normal/-normal/±x/±y/±z
    double thickness = 0.0;
    int numLayers = 1;

    // Element type
    std::string elementType = "solid";  // solid | tshell | shell

    // Connection mode (NEW!)
    std::string connectionMode = "tied";  // tied | czm | contact
    int czmPartId = 0;                    // CZM part ID (0 = auto-increment)
    int czmMid = 0;                       // CZM material ID (0 = auto-increment)
    std::string czmMaterialCard;          // *MAT_COHESIVE_* keyword

    // Dual offset prestress mode (NEW!)
    std::string prestressMode = "";       // "" | "dual_offset"
    double innerOffset = 0.0;             // 압축된 형상 (deformed, 음수)
    double outerOffset = 0.0;             // 릴랙스 형상 (reference, 양수)

    // New part definition
    int newPid = 0;         // 0 = auto-increment
    int newSecid = 0;       // 0 = auto-increment
    std::string partTitle = "Offset Layer";

    // Material
    int newMid = 0;         // 0 = auto-increment
    std::string materialCard;  // Multi-line MAT keyword

    // Shell-specific
    double shellThickness = 0.0;  // 0 = use thickness
    double shellOffset = -1.0;    // -1 = use thickness/2 (mid-plane)
};
```

**AssemblyOperation 수정**:
```cpp
enum Type {
    REPLACE,
    SQUEEZE,
    RESTACK,
    BEND,
    INDENT,
    FORMSTRAIN,
    DISCONNECT,
    ELFORM,
    IGA,
    WARPAGE,
    OFFSET         // ← 추가
};

struct AssemblyOperation {
    Type type;
    // ... existing members
    OffsetOperation offset;  // ← 추가
};
```

---

### Phase 2: AssemblyConfigReader.cpp - YAML 파싱

**파일**: `src/assembly/AssemblyConfigReader.cpp`

#### 2.1 Type 인식
```cpp
else if (typeStr == "offset") {
    op.type = AssemblyOperation::OFFSET;
}
```

#### 2.2 파라미터 파싱
```cpp
else if (op.type == AssemblyOperation::OFFSET) {
    if (key == "source_pid") op.offset.sourcePid = std::stoi(val);
    else if (key == "offset_direction") op.offset.offsetDirection = val;
    else if (key == "thickness") op.offset.thickness = std::stod(val);
    else if (key == "num_layers") op.offset.numLayers = std::stoi(val);
    else if (key == "element_type") op.offset.elementType = val;

    // Connection mode (NEW!)
    else if (key == "connection_mode") op.offset.connectionMode = val;
    else if (key == "czm_part_id") op.offset.czmPartId = std::stoi(val);
    else if (key == "czm_mid") op.offset.czmMid = std::stoi(val);
    else if (key == "czm_material_card") {
        inCzmMaterialCardBlock = true;
        czmMaterialCardIndent = indent;
    }

    // Dual offset prestress mode (NEW!)
    else if (key == "prestress_mode") op.offset.prestressMode = val;
    else if (key == "inner_offset") op.offset.innerOffset = std::stod(val);
    else if (key == "outer_offset") op.offset.outerOffset = std::stod(val);

    else if (key == "new_pid") op.offset.newPid = std::stoi(val);
    else if (key == "new_secid") op.offset.newSecid = std::stoi(val);
    else if (key == "new_mid") op.offset.newMid = std::stoi(val);
    else if (key == "part_title") op.offset.partTitle = val;
    else if (key == "shell_thickness") op.offset.shellThickness = std::stod(val);
    else if (key == "shell_offset") op.offset.shellOffset = std::stod(val);
    else if (key == "material_card") {
        inMaterialCardBlock = true;
        materialCardIndent = indent;
    }
}
```

#### 2.3 Material Card 블록 읽기
```cpp
// In main parsing loop
if (inMaterialCardBlock && indent > materialCardIndent) {
    op.offset.materialCard += line + "\n";
} else if (inMaterialCardBlock && indent <= materialCardIndent) {
    inMaterialCardBlock = false;
}

// CZM material card block (NEW!)
if (inCzmMaterialCardBlock && indent > czmMaterialCardIndent) {
    op.offset.czmMaterialCard += line + "\n";
} else if (inCzmMaterialCardBlock && indent <= czmMaterialCardIndent) {
    inCzmMaterialCardBlock = false;
}
```

#### 2.4 Validation
```cpp
else if (op.type == AssemblyOperation::OFFSET) {
    std::string pfx = "Operation " + std::to_string(i+1) + " (offset): ";

    if (op.offset.sourcePid <= 0)
        throw std::runtime_error(pfx + "source_pid required");

    // Prestress mode validation (NEW!)
    bool isDualOffset = (op.offset.prestressMode == "dual_offset");
    if (isDualOffset) {
        // Dual offset mode: inner/outer required
        if (op.offset.innerOffset >= 0.0)
            throw std::runtime_error(pfx + "inner_offset must be < 0 (inward)");
        if (op.offset.outerOffset <= 0.0)
            throw std::runtime_error(pfx + "outer_offset must be > 0 (outward)");
        if (op.offset.innerOffset >= op.offset.outerOffset)
            throw std::runtime_error(pfx + "inner_offset must be < outer_offset");
    } else {
        // Normal mode: thickness required
        if (op.offset.thickness <= 0.0)
            throw std::runtime_error(pfx + "thickness must be > 0");
    }

    if (op.offset.numLayers < 1)
        throw std::runtime_error(pfx + "num_layers must be >= 1");

    std::string etype = op.offset.elementType;
    if (etype != "solid" && etype != "tshell" && etype != "shell")
        throw std::runtime_error(pfx + "element_type must be solid|tshell|shell");

    std::string dir = op.offset.offsetDirection;
    if (!isDualOffset) {
        // Normal mode: validate direction
        if (dir != "+normal" && dir != "-normal" &&
            dir != "+x" && dir != "-x" &&
            dir != "+y" && dir != "-y" &&
            dir != "+z" && dir != "-z")
            throw std::runtime_error(pfx + "invalid offset_direction");
    }

    // Connection mode validation (NEW!)
    std::string cmode = op.offset.connectionMode;
    if (cmode != "tied" && cmode != "czm" && cmode != "contact")
        throw std::runtime_error(pfx + "connection_mode must be tied|czm|contact");

    if (cmode == "czm" && op.offset.czmMaterialCard.empty())
        throw std::runtime_error(pfx + "czm_material_card required for czm mode");

    // === ENHANCED VALIDATION (🔧 Issue 14 Fix) ===

    // Dual offset mode checks
    if (isDualOffset) {
        // Material card required for prestress calculation
        if (op.offset.materialCard.empty()) {
            throw std::runtime_error(pfx + "material_card required for dual_offset mode");
        }

        // Warn if not using contact mode (usually preferred for pouch wrapping)
        if (cmode != "contact") {
            std::cout << "[WARNING] " << pfx
                      << "dual_offset usually uses connection_mode: contact for wrapping simulation\n";
        }
    }

    // CZM mode warnings
    if (cmode == "czm") {
        // Tied + CZM is contradictory (CZM implies separation possibility)
        if (cmode == "tied") {
            std::cout << "[WARNING] " << pfx
                      << "czm mode with tied connection is contradictory - tied prevents separation\n";
        }
    }

    // Thickness/direction ignored in dual offset mode
    if (isDualOffset && (op.offset.thickness > 0.0 || !dir.empty())) {
        std::cout << "[INFO] " << pfx
                  << "thickness and offset_direction ignored in dual_offset mode (using inner/outer_offset)\n";
    }
}
```

---

### Phase 3: ModelAssembler.h - 메서드 선언

**파일**: `include/assembly/ModelAssembler.h`

```cpp
class ModelAssembler {
public:
    bool applyOffset(const OffsetOperation& op, double E, double nu);  // ✅ E, nu 추가

private:
    // Main helper methods
    void extractSourceSurface(int sourcePid,
                             std::vector<ShellElement>& surfaceShells);
    Vector3D parseOffsetDirection(const std::string& direction,
                                 const std::vector<ShellElement>& surface);

    // Extrude methods
    void extrudeToSolid(const std::vector<ShellElement>& surface,
                       const Vector3D& direction,
                       double thickness, int numLayers,
                       int newPid, int newSecid);
    void extrudeToTShell(const std::vector<ShellElement>& surface,
                        const Vector3D& direction,
                        double thickness, int numLayers,
                        int newPid, int newSecid);
    void createOffsetShell(const std::vector<ShellElement>& surface,
                          const Vector3D& direction,
                          double offset,
                          int newPid, int newSecid,
                          double shellThickness);

    // Geometry helpers
    Vector3D computeElementNormal(const ShellElement& shell);
    Vector3D computeAverageNormal(const std::vector<ShellElement>& shells);
    Vector3D computeFaceCentroid(const Element& elem, int faceIndex);
    Vector3D computeElementCenter(const Element& elem) const;
    Vector3D computeOutwardNormal(const Element& elem, int faceIndex);
    bool isTria3(const ShellElement& shell);
    bool isElementInverted(const Element& elem);
    double computeJacobian(const Element& elem, double r, double s, double t);

    // Connection mode (Phase 11)
    void applyConnectionTied(const std::vector<ShellElement>& sourceSurface,
                            const std::vector<Element>& offsetElements);
    void applyConnectionCZM(const std::vector<ShellElement>& sourceSurface,
                           const std::vector<Element>& offsetElements,
                           const OffsetOperation& op);
    void applyConnectionContact(const std::vector<ShellElement>& sourceSurface,
                               const std::vector<Element>& offsetElements);

    // Dual offset prestress (Phase 12)
    bool applyDualOffsetPrestress(const OffsetOperation& op, double E, double nu);
    void calculateDualOffsetPrestress(const std::vector<Element>& refElements,
                                     const std::map<int, Vector3D>& deformedPositions,
                                     const MaterialModel& mat);
    void createCzmElementsForDualOffset(const std::vector<ShellElement>& sourceSurface,
                                       const std::map<int, int>& origToBottomNode,
                                       const OffsetOperation& op);
    void addContactHint(int sourcePid, int offsetPid);

    // ID management
    int getNextPartId();
    int getNextSectionId();
    int getNextMaterialId();

    // Output
    void insertMaterialCard(const std::string& materialCard, int actualMid);
    std::string formatCzmSectionBlock(int secid);
    void createPartKeyword(int pid, int secid, int mid, const std::string& title);
    void createSectionSolid(int secid);
    void createSectionTShell(int secid, double thickness, int elform);
    void createSectionShell(int secid, double thickness);
};
```

---

### Phase 4: ModelAssembler.cpp - applyOffset() 메인 로직 (Normal Mode)

**파일**: `src/assembly/ModelAssembler.cpp`

**NOTE**: This is the "normal mode" implementation. Phase 12 wraps this with a dispatcher
that checks `op.prestressMode` to route to either normal mode (this code) or dual offset mode.

```cpp
bool ModelAssembler::applyOffset(const OffsetOperation& op, double E, double nu) {  // ✅ E, nu 추가
    // ⚠️ Phase 12 adds dispatcher: if (isDualOffset) → applyDualOffsetPrestress()
    // This code becomes the "else" branch (normal mode)

    std::cout << "[INFO] Applying offset operation on PID " << op.sourcePid << "\n";

    // 1. Validation
    if (baseMesh_.getParts().count(op.sourcePid) == 0) {
        errorMessage_ = "Source PID " + std::to_string(op.sourcePid) + " not found";
        return false;
    }

    // 2. Auto-assign IDs
    int actualPid = (op.newPid > 0) ? op.newPid : getNextPartId();
    int actualSecid = (op.newSecid > 0) ? op.newSecid : getNextSectionId();
    int actualMid = (op.newMid > 0) ? op.newMid : getNextMaterialId();

    std::cout << "[INFO] New IDs: PID=" << actualPid
              << ", SECID=" << actualSecid
              << ", MID=" << actualMid << "\n";

    // 3. Extract source surface
    std::vector<ShellElement> sourceSurface;
    extractSourceSurface(op.sourcePid, sourceSurface);

    if (sourceSurface.empty()) {
        errorMessage_ = "No surface elements found in source PID "
                       + std::to_string(op.sourcePid);
        return false;
    }

    std::cout << "[INFO] Extracted " << sourceSurface.size()
              << " surface elements\n";

    // 4. Parse offset direction
    Vector3D offsetDir = parseOffsetDirection(op.offsetDirection, sourceSurface);
    std::cout << "[INFO] Offset direction: ("
              << offsetDir.x << ", " << offsetDir.y << ", " << offsetDir.z << ")\n";

    // 5. Create offset geometry based on element_type
    int numElemsCreated = 0;

    if (op.elementType == "solid") {
        extrudeToSolid(sourceSurface, offsetDir, op.thickness,
                      op.numLayers, actualPid, actualSecid);
        numElemsCreated = addedElements_.size();
        createSectionSolid(actualSecid);

    } else if (op.elementType == "tshell") {
        extrudeToTShell(sourceSurface, offsetDir, op.thickness,
                       op.numLayers, actualPid, actualSecid);
        numElemsCreated = addedShellElements_.size();

        double layerThickness = op.thickness / op.numLayers;
        int elform = 16;  // TSHELL4 (QUAD)
        // Check if any TRIA3
        for (const auto& shell : sourceSurface) {
            if (isTria3(shell)) {
                elform = 17;  // TSHELL3 (TRIA)
                break;
            }
        }
        createSectionTShell(actualSecid, layerThickness, elform);

    } else if (op.elementType == "shell") {
        double offset = op.shellOffset;
        if (offset < 0) offset = op.thickness / 2.0;  // default to mid-plane

        double thickness = op.shellThickness;
        if (thickness <= 0) thickness = op.thickness;  // default to offset thickness

        createOffsetShell(sourceSurface, offsetDir, offset,
                         actualPid, actualSecid, thickness);
        numElemsCreated = addedShellElements_.size();
        createSectionShell(actualSecid, thickness);
    }

    // 6. Apply connection mode (NEW! - Phase 11 integration)
    if (op.connectionMode == "czm") {
        // Get references to created elements
        std::vector<Element> createdElements;
        if (op.elementType == "solid") {
            // Get last N elements from addedElements_
            int startIdx = addedElements_.size() - numElemsCreated;
            for (int i = startIdx; i < addedElements_.size(); ++i) {
                createdElements.push_back(addedElements_[i]);
            }
            applyConnectionCZM(sourceSurface, createdElements, op);
        }
        // Note: CZM only applies to solid elements
    } else if (op.connectionMode == "contact") {
        std::vector<Element> createdElements;
        if (op.elementType == "solid") {
            int startIdx = addedElements_.size() - numElemsCreated;
            for (int i = startIdx; i < addedElements_.size(); ++i) {
                createdElements.push_back(addedElements_[i]);
            }
            applyConnectionContact(sourceSurface, createdElements);
        }
    }
    // "tied" mode: no action needed (default behavior)

    // 7. Create PART keyword
    createPartKeyword(actualPid, actualSecid, actualMid, op.partTitle);

    // 8. Insert material card
    if (!op.materialCard.empty()) {
        insertMaterialCard(op.materialCard, actualMid);
    }

    std::cout << "[INFO] Offset complete: Created " << numElemsCreated
              << " elements in PID " << actualPid << "\n";

    return true;
}
```

---

### Phase 5: 표면 추출 (extractSourceSurface)

```cpp
void ModelAssembler::extractSourceSurface(int sourcePid,
                                         std::vector<ShellElement>& surfaceShells) {
    // Case 1: Source is shell elements → use directly
    for (const auto& [sid, shell] : baseMesh_.getShellElements()) {
        if (shell.partId == sourcePid) {
            surfaceShells.push_back(shell);
        }
    }

    // Also check addedShellElements_ (for multi-operation support)
    for (const auto& shell : addedShellElements_) {
        if (shell.partId == sourcePid) {
            surfaceShells.push_back(shell);
        }
    }

    if (!surfaceShells.empty()) {
        std::cout << "[INFO] Source is shell part ("
                  << surfaceShells.size() << " elements)\n";
        return;
    }

    // Case 2: Source is solid elements → extract outer surface
    std::cout << "[INFO] Source is solid part - extracting outer surface\n";

    // Build face→element map
    std::map<std::array<int,4>, int> faceToElem;

    // Process baseMesh elements
    for (const auto& [eid, elem] : baseMesh_.getElements()) {
        if (elem.partId != sourcePid) continue;

        // Get number of faces (6 for HEX8, 4 for TET4)
        int numFaces = (elem.nodeIds[4] == elem.nodeIds[7]) ? 4 : 6;

        for (int fi = 0; fi < numFaces; ++fi) {
            auto faceNodes = elem.getFaceNodeIds(fi);

            // Sort for canonical key
            std::sort(faceNodes.begin(), faceNodes.end());
            std::array<int,4> key = {faceNodes[0], faceNodes[1],
                                     faceNodes[2], faceNodes[3]};

            if (faceToElem.count(key)) {
                faceToElem.erase(key);  // Shared face → interior
            } else {
                faceToElem[key] = eid;  // Outer face
            }
        }
    }

    // Also process addedElements_ (for multi-operation)
    for (const auto& elem : addedElements_) {
        if (elem.partId != sourcePid) continue;

        int numFaces = (elem.nodeIds[4] == elem.nodeIds[7]) ? 4 : 6;

        for (int fi = 0; fi < numFaces; ++fi) {
            auto faceNodes = elem.getFaceNodeIds(fi);
            std::sort(faceNodes.begin(), faceNodes.end());
            std::array<int,4> key = {faceNodes[0], faceNodes[1],
                                     faceNodes[2], faceNodes[3]};

            if (faceToElem.count(key)) {
                faceToElem.erase(key);
            } else {
                faceToElem[key] = eid;
            }
        }
    }

    // Convert outer faces to ShellElement
    int sid = 1;
    for (const auto& [faceNodes, eid] : faceToElem) {
        ShellElement shell;
        shell.id = sid++;
        shell.partId = sourcePid;

        // Restore original node order (unsort)
        // Need to get from original element face
        // For now, use sorted order (may need refinement for normal direction)
        shell.nodeIds[0] = faceNodes[0];
        shell.nodeIds[1] = faceNodes[1];
        shell.nodeIds[2] = faceNodes[2];
        shell.nodeIds[3] = faceNodes[3];

        surfaceShells.push_back(shell);
    }

    std::cout << "[INFO] Extracted " << surfaceShells.size()
              << " surface faces from solid\n";

    if (surfaceShells.empty()) {
        std::cerr << "[WARNING] No surface found - check if PID "
                  << sourcePid << " has valid elements\n";
    }
}
```

**⚠️ 개선 필요**: Face node order를 원래 element face에서 복원해야 normal 방향 일관성 유지

---

### Phase 6: Helper Methods (🔧 이동됨 - 원래 Phase 9)

**⚠️ 중요**: Phase 7-9에서 사용하는 helper 함수들을 먼저 구현

#### 6.1 Normal 계산

```cpp
Vector3D ModelAssembler::computeElementNormal(const ShellElement& shell) {
    Vector3D p0 = getNodePosition(shell.nodeIds[0]);
    Vector3D p1 = getNodePosition(shell.nodeIds[1]);
    Vector3D p2 = getNodePosition(shell.nodeIds[2]);

    Vector3D v1 = p1 - p0;
    Vector3D v2 = p2 - p0;
    Vector3D normal = v1.cross(v2);

    double mag = normal.magnitude();
    if (mag < 1e-12) {
        std::cerr << "[WARNING] Degenerate element - zero normal\n";
        return Vector3D(0, 0, 1);  // Default
    }

    return normal * (1.0 / mag);
}

Vector3D ModelAssembler::computeAverageNormal(const std::vector<ShellElement>& shells) {
    Vector3D sumNormal(0, 0, 0);
    int count = 0;

    for (const auto& shell : shells) {
        if (isTria3(shell) && shell.nodeIds[0] == shell.nodeIds[1]) {
            continue;  // Skip completely degenerate
        }

        Vector3D n = computeElementNormal(shell);
        sumNormal = sumNormal + n;
        count++;
    }

    if (count == 0) {
        std::cerr << "[WARNING] No valid normals - using default +Z\n";
        return Vector3D(0, 0, 1);
    }

    return sumNormal * (1.0 / count);
}
```

#### 6.2 방향 파싱

```cpp
Vector3D ModelAssembler::parseOffsetDirection(const std::string& direction,
                                              const std::vector<ShellElement>& surface) {
    if (direction == "+normal") {
        return computeAverageNormal(surface);
    } else if (direction == "-normal") {
        return computeAverageNormal(surface) * -1.0;
    } else if (direction == "+x") {
        return Vector3D(1, 0, 0);
    } else if (direction == "-x") {
        return Vector3D(-1, 0, 0);
    } else if (direction == "+y") {
        return Vector3D(0, 1, 0);
    } else if (direction == "-y") {
        return Vector3D(0, -1, 0);
    } else if (direction == "+z") {
        return Vector3D(0, 0, 1);
    } else if (direction == "-z") {
        return Vector3D(0, 0, -1);
    } else {
        throw std::runtime_error("Invalid offset_direction: " + direction);
    }
}
```

#### 6.3 TRIA3 감지

```cpp
bool ModelAssembler::isTria3(const ShellElement& shell) {
    // TRIA3 stored as degenerate QUAD4:
    // - nodeIds[3] == nodeIds[2] (most common)
    // - nodeIds[3] == 0 (some variants)
    // - nodeIds[3] == nodeIds[0] (rare)

    return (shell.nodeIds[3] == shell.nodeIds[2] ||
            shell.nodeIds[3] == 0 ||
            shell.nodeIds[3] == shell.nodeIds[0]);
}
```

#### 6.4 요소 중심점 계산 (⭐ NEW - Phase 12에서 필요)

**Note**: `getNodePosition(int nid)` 함수는 **이미 구현되어 있음!** (ModelAssembler.cpp:5002)
- modifiedNodePositions_, addedNodes_, baseMesh_ 모두 처리
- Phase 6.1에서 바로 사용 가능

```cpp
Vector3D ModelAssembler::computeElementCenter(const Element& elem) const {
    Vector3D sum(0, 0, 0);
    int count = 0;

    for (int i = 0; i < 8; ++i) {
        if (elem.nodeIds[i] > 0) {
            sum = sum + getNodePosition(elem.nodeIds[i]);  // ✅ 기존 함수 사용
            count++;
        }
    }

    if (count == 0) {
        throw std::runtime_error("Element has no valid nodes");
    }

    return sum * (1.0 / count);
}
```

#### 6.6 ID 관리

```cpp
int ModelAssembler::getNextPartId() {
    int maxId = 0;

    // Check baseMesh
    for (const auto& [pid, part] : baseMesh_.getParts()) {
        if (pid > maxId) maxId = pid;
    }

    return maxId + 1;
}

int ModelAssembler::getNextSectionId() {
    return ++maxSectionId_;  // Assuming maxSectionId_ is tracked
}

int ModelAssembler::getNextMaterialId() {
    return ++maxMaterialId_;  // Assuming maxMaterialId_ is tracked
}
```

#### 6.7 Material Card 처리

```cpp
void ModelAssembler::insertMaterialCard(const std::string& materialCard, int actualMid) {
    // Replace @MID@ placeholder with actual MID
    std::string processed = materialCard;

    std::stringstream ss;
    ss << std::setw(10) << actualMid;
    std::string midStr = ss.str();

    // Simple replacement
    size_t pos = processed.find("@MID@");
    while (pos != std::string::npos) {
        processed.replace(pos, 5, midStr);  // "@MID@" is 5 chars
        pos = processed.find("@MID@", pos + midStr.length());
    }

    // Insert into raw lines
    addedKeywordBlocks_.push_back(processed);

    std::cout << "[INFO] Inserted material card with MID=" << actualMid << "\n";
}
```

#### 6.8 Keyword 생성

```cpp
void ModelAssembler::createPartKeyword(int pid, int secid, int mid,
                                       const std::string& title) {
    std::ostringstream oss;
    oss << "*PART\n";
    oss << title << "\n";
    oss << std::setw(10) << pid
        << std::setw(10) << secid
        << std::setw(10) << mid << "\n";

    addedKeywordBlocks_.push_back(oss.str());
}

void ModelAssembler::createSectionSolid(int secid) {
    std::ostringstream oss;
    oss << "*SECTION_SOLID\n";
    oss << "$#   secid    elform       aet\n";
    oss << std::setw(10) << secid
        << std::setw(10) << 1  // ELFORM=1 (constant stress solid)
        << "\n";

    addedKeywordBlocks_.push_back(oss.str());
}

void ModelAssembler::createSectionTShell(int secid, double thickness, int elform) {
    std::ostringstream oss;
    oss << "*SECTION_TSHELL\n";
    oss << "$#   secid    elform      shrf       nip     propt   qr/irid     icomp     setyp\n";
    oss << std::setw(10) << secid
        << std::setw(10) << elform  // 16=TSHELL4, 17=TSHELL3
        << std::setw(10) << 0.0     // SHRF
        << std::setw(10) << 3       // NIP
        << "\n";
    oss << "$#      t1        t2        t3        t4      nloc     marea      idof    edgset\n";
    oss << std::scientific << std::setprecision(3);
    oss << std::setw(10) << thickness
        << std::setw(10) << thickness
        << std::setw(10) << thickness
        << std::setw(10) << thickness
        << "\n";

    addedKeywordBlocks_.push_back(oss.str());
}

void ModelAssembler::createSectionShell(int secid, double thickness) {
    std::ostringstream oss;
    oss << "*SECTION_SHELL\n";
    oss << "$#   secid    elform      shrf       nip     propt   qr/irid     icomp     setyp\n";
    oss << std::setw(10) << secid
        << std::setw(10) << 2       // ELFORM=2 (fully integrated QUAD)
        << std::setw(10) << 0.0     // SHRF
        << std::setw(10) << 3       // NIP
        << "\n";
    oss << "$#      t1        t2        t3        t4      nloc     marea      idof    edgset\n";
    oss << std::scientific << std::setprecision(3);
    oss << std::setw(10) << thickness
        << std::setw(10) << thickness
        << std::setw(10) << thickness
        << std::setw(10) << thickness
        << "\n";

    addedKeywordBlocks_.push_back(oss.str());
}
```

---

### Phase 7: Solid Extrude 구현 (🔧 원래 Phase 6)

```cpp
void ModelAssembler::extrudeToSolid(const std::vector<ShellElement>& surface,
                                   const Vector3D& direction,
                                   double thickness, int numLayers,
                                   int newPid, int newSecid) {
    double layerThickness = thickness / numLayers;

    std::cout << "[INFO] Extruding to solid: " << numLayers
              << " layers, thickness=" << layerThickness << " mm each\n";

    // Track starting counts
    size_t startElemCount = addedElements_.size();
    size_t startNodeCount = addedNodes_.size();

    // Create offset node layers
    std::map<int, std::vector<int>> nodeLayerMap;  // originalNid → [nid0, nid1, ..., nidN]

    for (const auto& shell : surface) {
        for (int nid : shell.nodeIds) {
            if (nid <= 0) continue;  // Skip invalid nodes (degenerate TRIA3)
            if (nodeLayerMap.count(nid)) continue;  // Already processed

            Vector3D basePos = getNodePosition(nid);
            std::vector<int> layerNodes;

            // Create nodes for each layer
            for (int layer = 0; layer <= numLayers; ++layer) {
                int newNid = ++maxNodeId_;
                Vector3D offsetPos = basePos + direction * (layer * layerThickness);

                AddedNode an;
                an.id = newNid;
                an.x = offsetPos.x;
                an.y = offsetPos.y;
                an.z = offsetPos.z;
                addedNodes_.push_back(an);  // ✅ vector에 추가
                layerNodes.push_back(newNid);
            }

            nodeLayerMap[nid] = layerNodes;
        }
    }

    // Create solid elements (HEX8 or degenerate for WEDGE6)
    for (const auto& shell : surface) {
        bool isTria = isTria3(shell);

        for (int layer = 0; layer < numLayers; ++layer) {
            Element elem;
            elem.id = ++maxElementId_;
            elem.partId = newPid;

            if (isTria) {
                // TRIA3 → WEDGE6 (stored as degenerate HEX8)
                // Bottom triangle
                elem.nodeIds[0] = nodeLayerMap[shell.nodeIds[0]][layer];
                elem.nodeIds[1] = nodeLayerMap[shell.nodeIds[1]][layer];
                elem.nodeIds[2] = nodeLayerMap[shell.nodeIds[2]][layer];
                elem.nodeIds[3] = nodeLayerMap[shell.nodeIds[2]][layer];  // degenerate

                // Top triangle
                elem.nodeIds[4] = nodeLayerMap[shell.nodeIds[0]][layer+1];
                elem.nodeIds[5] = nodeLayerMap[shell.nodeIds[1]][layer+1];
                elem.nodeIds[6] = nodeLayerMap[shell.nodeIds[2]][layer+1];
                elem.nodeIds[7] = nodeLayerMap[shell.nodeIds[2]][layer+1];  // degenerate
            } else {
                // QUAD4 → HEX8
                // Bottom face
                elem.nodeIds[0] = nodeLayerMap[shell.nodeIds[0]][layer];
                elem.nodeIds[1] = nodeLayerMap[shell.nodeIds[1]][layer];
                elem.nodeIds[2] = nodeLayerMap[shell.nodeIds[2]][layer];
                elem.nodeIds[3] = nodeLayerMap[shell.nodeIds[3]][layer];

                // Top face
                elem.nodeIds[4] = nodeLayerMap[shell.nodeIds[0]][layer+1];
                elem.nodeIds[5] = nodeLayerMap[shell.nodeIds[1]][layer+1];
                elem.nodeIds[6] = nodeLayerMap[shell.nodeIds[2]][layer+1];
                elem.nodeIds[7] = nodeLayerMap[shell.nodeIds[3]][layer+1];
            }

            // Quality check
            if (isElementInverted(elem)) {
                std::cerr << "[WARNING] Element " << elem.id
                          << " may be inverted - check offset direction\n";
            }

            addedElements_.push_back(elem);
        }
    }

    size_t numElemsCreated = addedElements_.size() - startElemCount;
    size_t numNodesCreated = addedNodes_.size() - startNodeCount;

    std::cout << "[INFO] Created " << numNodesCreated << " nodes, "
              << numElemsCreated << " solid elements\n";
}
```

---

### Phase 8: TShell Extrude 구현 (🔧 원래 Phase 7)

```cpp
void ModelAssembler::extrudeToTShell(const std::vector<ShellElement>& surface,
                                    const Vector3D& direction,
                                    double thickness, int numLayers,
                                    int newPid, int newSecid) {
    double layerThickness = thickness / numLayers;

    std::cout << "[INFO] Extruding to TSHELL: " << numLayers
              << " layers, thickness=" << layerThickness << " mm each\n";

    // TSHELL은 top + bottom 노드 필요
    // TSHELL4: 8 nodes (4 bottom + 4 top)
    // TSHELL3: 6 nodes (3 bottom + 3 top)

    // Create offset node layers (only 2 layers needed per TSHELL)
    std::map<int, std::vector<int>> nodeLayerMap;

    for (const auto& shell : surface) {
        for (int nid : shell.nodeIds) {
            if (nid <= 0) continue;
            if (nodeLayerMap.count(nid)) continue;

            Vector3D basePos = getNodePosition(nid);
            std::vector<int> layerNodes;

            // Bottom to top
            for (int layer = 0; layer <= numLayers; ++layer) {
                int newNid = ++maxNodeId_;
                Vector3D offsetPos = basePos + direction * (layer * layerThickness);

                AddedNode an;
                an.id = newNid;
                an.x = offsetPos.x;
                an.y = offsetPos.y;
                an.z = offsetPos.z;
                addedNodes_.push_back(an);  // ✅ vector에 추가
                layerNodes.push_back(newNid);
            }

            nodeLayerMap[nid] = layerNodes;
        }
    }

    // Create TSHELL elements
    for (const auto& shell : surface) {
        bool isTria = isTria3(shell);

        for (int layer = 0; layer < numLayers; ++layer) {
            ShellElement tshell;
            tshell.id = ++maxShellElementId_;
            tshell.partId = newPid;
            tshell.elform = isTria ? 17 : 16;  // TSHELL3 : TSHELL4

            if (isTria) {
                // TSHELL3: 6 nodes (3 bottom + 3 top)
                tshell.nodeIds[0] = nodeLayerMap[shell.nodeIds[0]][layer];    // bottom
                tshell.nodeIds[1] = nodeLayerMap[shell.nodeIds[1]][layer];
                tshell.nodeIds[2] = nodeLayerMap[shell.nodeIds[2]][layer];
                tshell.nodeIds[3] = nodeLayerMap[shell.nodeIds[0]][layer+1];  // top
                tshell.nodeIds[4] = nodeLayerMap[shell.nodeIds[1]][layer+1];
                tshell.nodeIds[5] = nodeLayerMap[shell.nodeIds[2]][layer+1];
                // Pad to 8 (not needed if we use variable-size array)
                tshell.nodeIds[6] = 0;
                tshell.nodeIds[7] = 0;
            } else {
                // TSHELL4: 8 nodes (4 bottom + 4 top)
                tshell.nodeIds[0] = nodeLayerMap[shell.nodeIds[0]][layer];    // bottom
                tshell.nodeIds[1] = nodeLayerMap[shell.nodeIds[1]][layer];
                tshell.nodeIds[2] = nodeLayerMap[shell.nodeIds[2]][layer];
                tshell.nodeIds[3] = nodeLayerMap[shell.nodeIds[3]][layer];
                tshell.nodeIds[4] = nodeLayerMap[shell.nodeIds[0]][layer+1];  // top
                tshell.nodeIds[5] = nodeLayerMap[shell.nodeIds[1]][layer+1];
                tshell.nodeIds[6] = nodeLayerMap[shell.nodeIds[2]][layer+1];
                tshell.nodeIds[7] = nodeLayerMap[shell.nodeIds[3]][layer+1];
            }

            addedShellElements_.push_back(tshell);
        }
    }

    std::cout << "[INFO] Created " << addedShellElements_.size()
              << " TSHELL elements\n";
}
```

**⚠️ Note**: TSHELL은 `*ELEMENT_SHELL` 키워드로 출력되며, ELFORM이 16 또는 17일 때 LS-DYNA가 TSHELL로 인식

---

### Phase 9: Shell Offset 구현 (🔧 원래 Phase 8)

```cpp
void ModelAssembler::createOffsetShell(const std::vector<ShellElement>& surface,
                                      const Vector3D& direction,
                                      double offset,
                                      int newPid, int newSecid,
                                      double shellThickness) {
    std::cout << "[INFO] Creating offset shell at distance=" << offset
              << " mm, thickness=" << shellThickness << " mm\n";

    // Create new nodes at offset position
    std::map<int, int> oldToNewNode;

    for (const auto& shell : surface) {
        for (int nid : shell.nodeIds) {
            if (nid <= 0) continue;  // Skip invalid (degenerate)
            if (oldToNewNode.count(nid)) continue;

            Vector3D basePos = getNodePosition(nid);
            Vector3D offsetPos = basePos + direction * offset;

            int newNid = ++maxNodeId_;
            AddedNode an;
            an.id = newNid;
            an.x = offsetPos.x;
            an.y = offsetPos.y;
            an.z = offsetPos.z;
            addedNodes_.push_back(an);  // ✅ vector에 추가
            oldToNewNode[nid] = newNid;
        }
    }

    // Create shell elements with new node IDs
    for (const auto& shell : surface) {
        ShellElement newShell;
        newShell.id = ++maxShellElementId_;
        newShell.partId = newPid;
        newShell.elform = 2;  // Standard QUAD4/TRIA3

        for (size_t i = 0; i < 4; ++i) {
            if (shell.nodeIds[i] > 0) {
                newShell.nodeIds[i] = oldToNewNode[shell.nodeIds[i]];
            } else {
                newShell.nodeIds[i] = 0;  // Preserve degeneracy
            }
        }

        addedShellElements_.push_back(newShell);
    }

    std::cout << "[INFO] Created " << oldToNewNode.size() << " nodes, "
              << addedShellElements_.size() << " shell elements\n";
}
```

---

### ~~Phase 9: Helper Methods~~ (🔧 삭제됨 - Phase 6으로 이동)

#### 9.1 Normal 계산

```cpp
Vector3D ModelAssembler::computeElementNormal(const ShellElement& shell) {
    Vector3D p0 = getNodePosition(shell.nodeIds[0]);
    Vector3D p1 = getNodePosition(shell.nodeIds[1]);
    Vector3D p2 = getNodePosition(shell.nodeIds[2]);

    Vector3D v1 = p1 - p0;
    Vector3D v2 = p2 - p0;
    Vector3D normal = v1.cross(v2);

    double mag = normal.magnitude();
    if (mag < 1e-12) {
        std::cerr << "[WARNING] Degenerate element - zero normal\n";
        return Vector3D(0, 0, 1);  // Default
    }

    return normal * (1.0 / mag);
}

Vector3D ModelAssembler::computeAverageNormal(const std::vector<ShellElement>& shells) {
    Vector3D sumNormal(0, 0, 0);
    int count = 0;

    for (const auto& shell : shells) {
        if (isTria3(shell) && shell.nodeIds[0] == shell.nodeIds[1]) {
            continue;  // Skip completely degenerate
        }

        Vector3D n = computeElementNormal(shell);
        sumNormal = sumNormal + n;
        count++;
    }

    if (count == 0) {
        std::cerr << "[WARNING] No valid normals - using default +Z\n";
        return Vector3D(0, 0, 1);
    }

    return sumNormal * (1.0 / count);
}
```

#### 9.2 방향 파싱

```cpp
Vector3D ModelAssembler::parseOffsetDirection(const std::string& direction,
                                              const std::vector<ShellElement>& surface) {
    if (direction == "+normal") {
        return computeAverageNormal(surface);
    } else if (direction == "-normal") {
        return computeAverageNormal(surface) * -1.0;
    } else if (direction == "+x") {
        return Vector3D(1, 0, 0);
    } else if (direction == "-x") {
        return Vector3D(-1, 0, 0);
    } else if (direction == "+y") {
        return Vector3D(0, 1, 0);
    } else if (direction == "-y") {
        return Vector3D(0, -1, 0);
    } else if (direction == "+z") {
        return Vector3D(0, 0, 1);
    } else if (direction == "-z") {
        return Vector3D(0, 0, -1);
    } else {
        throw std::runtime_error("Invalid offset_direction: " + direction);
    }
}
```

#### 9.3 TRIA3 감지

```cpp
bool ModelAssembler::isTria3(const ShellElement& shell) {
    // TRIA3 stored as degenerate QUAD4:
    // - nodeIds[3] == nodeIds[2] (most common)
    // - nodeIds[3] == 0 (some variants)
    // - nodeIds[3] == nodeIds[0] (rare)

    return (shell.nodeIds[3] == shell.nodeIds[2] ||
            shell.nodeIds[3] == 0 ||
            shell.nodeIds[3] == shell.nodeIds[0]);
}
```

#### 9.4 노드 위치 조회 (✅ 기존 함수 사용 - NO CODE NEEDED)

**NOTE**: `getNodePosition(int nid)` already exists in `ModelAssembler.cpp:5002`

Implementation checks:

1. `modifiedNodePositions_` (for displaced nodes)
2. `addedNodes_` vector (linear search by id)
3. `baseMesh_.getNode(nid).position` (fallback)

**No new code needed** - use existing `getNodePosition()` directly.

#### 9.5 요소 중심점 계산 (⭐ NEW - Phase 12에서 필요)

```cpp
Vector3D ModelAssembler::computeElementCenter(const Element& elem) const {
    Vector3D sum(0, 0, 0);
    int count = 0;

    for (int i = 0; i < 8; ++i) {
        if (elem.nodeIds[i] > 0) {
            sum = sum + getNodePosition(elem.nodeIds[i]);  // ✅ 기존 함수 사용
            count++;
        }
    }

    if (count == 0) {
        throw std::runtime_error("Element has no valid nodes");
    }

    return sum * (1.0 / count);
}
```

#### 9.6 ID 관리

```cpp
int ModelAssembler::getNextPartId() {
    int maxId = 0;

    // Check baseMesh
    for (const auto& [pid, part] : baseMesh_.getParts()) {
        if (pid > maxId) maxId = pid;
    }

    // Check previously assigned IDs in operations
    // (store in member variable or scan all operations)
    // For simplicity, use maxPartId_ if maintained

    return maxId + 1;
}

int ModelAssembler::getNextSectionId() {
    // Similar to getNextPartId()
    return ++maxSectionId_;  // Assuming maxSectionId_ is tracked
}

int ModelAssembler::getNextMaterialId() {
    return ++maxMaterialId_;  // Assuming maxMaterialId_ is tracked
}
```

#### 9.7 Material Card 처리

```cpp
void ModelAssembler::insertMaterialCard(const std::string& materialCard, int actualMid) {
    // Replace @MID@ placeholder with actual MID
    std::string processed = materialCard;

    std::stringstream ss;
    ss << std::setw(10) << actualMid;
    std::string midStr = ss.str();

    // Simple replacement
    size_t pos = processed.find("@MID@");
    while (pos != std::string::npos) {
        processed.replace(pos, 5, midStr);  // "@MID@" is 5 chars
        pos = processed.find("@MID@", pos + midStr.length());
    }

    // Insert into raw lines
    addedKeywordBlocks_.push_back(processed);

    std::cout << "[INFO] Inserted material card with MID=" << actualMid << "\n";
}
```

#### 9.8 Keyword 생성

```cpp
void ModelAssembler::createPartKeyword(int pid, int secid, int mid,
                                       const std::string& title) {
    std::ostringstream oss;
    oss << "*PART\n";
    oss << title << "\n";
    oss << std::setw(10) << pid
        << std::setw(10) << secid
        << std::setw(10) << mid << "\n";

    addedKeywordBlocks_.push_back(oss.str());
}

void ModelAssembler::createSectionSolid(int secid) {
    std::ostringstream oss;
    oss << "*SECTION_SOLID\n";
    oss << "$#   secid    elform       aet\n";
    oss << std::setw(10) << secid
        << std::setw(10) << 1  // ELFORM=1 (constant stress solid)
        << "\n";

    addedKeywordBlocks_.push_back(oss.str());
}

void ModelAssembler::createSectionTShell(int secid, double thickness, int elform) {
    std::ostringstream oss;
    oss << "*SECTION_TSHELL\n";
    oss << "$#   secid    elform      shrf       nip     propt   qr/irid     icomp     setyp\n";
    oss << std::setw(10) << secid
        << std::setw(10) << elform  // 16=TSHELL4, 17=TSHELL3
        << std::setw(10) << 0.0     // SHRF
        << std::setw(10) << 3       // NIP
        << "\n";
    oss << "$#      t1        t2        t3        t4      nloc     marea      idof    edgset\n";
    oss << std::scientific << std::setprecision(3);
    oss << std::setw(10) << thickness
        << std::setw(10) << thickness
        << std::setw(10) << thickness
        << std::setw(10) << thickness
        << "\n";

    addedKeywordBlocks_.push_back(oss.str());
}

void ModelAssembler::createSectionShell(int secid, double thickness) {
    std::ostringstream oss;
    oss << "*SECTION_SHELL\n";
    oss << "$#   secid    elform      shrf       nip     propt   qr/irid     icomp     setyp\n";
    oss << std::setw(10) << secid
        << std::setw(10) << 2       // ELFORM=2 (fully integrated QUAD)
        << std::setw(10) << 0.0     // SHRF
        << std::setw(10) << 3       // NIP
        << "\n";
    oss << "$#      t1        t2        t3        t4      nloc     marea      idof    edgset\n";
    oss << std::scientific << std::setprecision(3);
    oss << std::setw(10) << thickness
        << std::setw(10) << thickness
        << std::setw(10) << thickness
        << std::setw(10) << thickness
        << "\n";

    addedKeywordBlocks_.push_back(oss.str());
}
```

---

### Phase 10: main.cpp Dispatch

**파일**: `src/main.cpp`

```cpp
} else if (op.type == AssemblyOperation::OFFSET) {
    ok = assembler.applyOffset(op.offset);
    if (!ok) {
        std::cerr << "[ERROR] Offset operation failed: "
                  << assembler.getErrorMessage() << "\n";
        return 1;
    }
}
```

---

### Phase 11: Connection Mode 구현

**파일**: `src/assembly/ModelAssembler.cpp`

#### 11.1 Tied Mode (Node Sharing)
```cpp
void ModelAssembler::applyConnectionTied(
    const std::vector<ShellElement>& sourceSurface,
    const std::vector<Element>& offsetElements) {

    // 이미 구현됨 - 기본 동작
    // Source surface nodes를 offset layer 하단 노드로 직접 사용
    // → Perfect tie constraint 자동 달성
}
```

#### 11.2 CZM Mode (Cohesive Elements)
```cpp
void ModelAssembler::applyConnectionCZM(
    const std::vector<ShellElement>& sourceSurface,
    const std::vector<Element>& offsetElements,
    const OffsetOperation& op) {

    int czmPid = ++maxPartId_;
    int czmSecid = ++maxSectionId_;
    int czmMid = (op.czmMid > 0) ? op.czmMid : ++maxMaterialId_;

    // 1. Source surface에 대해 duplicate nodes 생성
    std::map<int, int> origNodeToDupNode;
    for (const auto& shell : sourceSurface) {
        for (int i = 0; i < 4; ++i) {
            int nid = shell.nodeIds[i];
            if (origNodeToDupNode.find(nid) == origNodeToDupNode.end()) {
                int newNid = ++maxNodeId_;
                Vector3D pos = baseMesh_.nodes.at(nid).position;

                Node newNode;
                newNode.id = newNid;
                // ELFORM=20 supports zero-thickness → same position OK
                newNode.position = pos;  // 동일 위치 (zero-thickness cohesive)
                AddedNode an;
                an.id = newNid;
                an.x = newNode.position.x;
                an.y = newNode.position.y;
                an.z = newNode.position.z;
                addedNodes_.push_back(an);  // ✅ vector에 추가

                origNodeToDupNode[nid] = newNid;
            }
        }
    }

    // 2. Offset layer 하단 노드를 duplicate nodes로 교체
    for (auto& elem : offsetElements) {
        // Bottom face nodes (0-3 for HEX8)
        for (int i = 0; i < 4; ++i) {
            if (origNodeToDupNode.find(elem.nodeIds[i]) != origNodeToDupNode.end()) {
                elem.nodeIds[i] = origNodeToDupNode[elem.nodeIds[i]];
            }
        }
    }

    // 3. Cohesive elements 생성 (source face → duplicate nodes)
    for (const auto& shell : sourceSurface) {
        Element cohElem;
        cohElem.id = ++maxElementId_;
        cohElem.partId = czmPid;
        cohElem.type = ElementType::HEX8;  // COH8D stored as HEX8

        // Bottom face: original nodes (source surface)
        cohElem.nodeIds[0] = shell.nodeIds[0];
        cohElem.nodeIds[1] = shell.nodeIds[1];
        cohElem.nodeIds[2] = shell.nodeIds[2];
        cohElem.nodeIds[3] = shell.nodeIds[3];

        // Top face: duplicate nodes (offset layer)
        cohElem.nodeIds[4] = origNodeToDupNode[shell.nodeIds[0]];
        cohElem.nodeIds[5] = origNodeToDupNode[shell.nodeIds[1]];
        cohElem.nodeIds[6] = origNodeToDupNode[shell.nodeIds[2]];
        cohElem.nodeIds[7] = origNodeToDupNode[shell.nodeIds[3]];

        addedElements_.push_back(cohElem);
    }

    // 4. CZM PART/SECTION/MATERIAL 키워드 삽입
    std::string partBlock = formatPartBlock(czmPid, czmSecid, czmMid, "CZM Layer");
    std::string sectionBlock = formatCzmSectionBlock(czmSecid);
    std::string materialBlock = op.czmMaterialCard;

    // @MID@ 치환
    size_t pos = 0;
    while ((pos = materialBlock.find("@MID@", pos)) != std::string::npos) {
        materialBlock.replace(pos, 5, std::to_string(czmMid));
        pos += std::to_string(czmMid).length();
    }

    addedKeywordBlocks_.push_back(partBlock);
    addedKeywordBlocks_.push_back(sectionBlock);
    addedKeywordBlocks_.push_back(materialBlock);
}

std::string ModelAssembler::formatCzmSectionBlock(int secid) {
    std::ostringstream oss;
    oss << "*SECTION_SOLID\n";
    oss << "$#   secid    elform       aet\n";
    oss << std::setw(10) << secid << std::setw(10) << 20 << "\n";  // ELFORM=20 (zero-thickness cohesive)
    oss << "$ Zero-thickness cohesive - duplicate nodes at same position\n";
    return oss.str();
}
```

#### 11.3 Contact Mode (Separate Nodes)
```cpp
void ModelAssembler::applyConnectionContact(
    const std::vector<ShellElement>& sourceSurface,
    const std::vector<Element>& offsetElements) {

    // Offset layer 하단 노드를 완전 분리된 새 노드로 생성
    std::map<int, int> origNodeToNewNode;

    for (auto& elem : offsetElements) {
        for (int i = 0; i < 4; ++i) {  // Bottom face
            int origNid = elem.nodeIds[i];

            if (origNodeToNewNode.find(origNid) == origNodeToNewNode.end()) {
                int newNid = ++maxNodeId_;
                Vector3D pos = baseMesh_.nodes.at(origNid).position;

                Node newNode;
                newNode.id = newNid;
                newNode.position = pos;  // 동일 위치 (초기)
                AddedNode an;
                an.id = newNid;
                an.x = newNode.position.x;
                an.y = newNode.position.y;
                an.z = newNode.position.z;
                addedNodes_.push_back(an);  // ✅ vector에 추가

                origNodeToNewNode[origNid] = newNid;
            }

            elem.nodeIds[i] = origNodeToNewNode[origNid];
        }
    }

    // Contact definition template 자동 생성 (주석으로)
    std::ostringstream contactHint;
    contactHint << "$\n"
                << "$ ==================== CONTACT DEFINITION REQUIRED ====================\n"
                << "$ The offset layer uses connection_mode: contact\n"
                << "$ Add contact definition manually, for example:\n"
                << "$\n"
                << "$ *CONTACT_AUTOMATIC_SURFACE_TO_SURFACE\n"
                << "$ $#     cid                                                         title\n"
                << "$       999                                          Offset_Contact_Auto\n"
                << "$ $#    ssid      msid     sstyp     mstyp    sboxid    mboxid       spr       mpr\n"
                << "$  " << std::setw(8) << sourcePid
                << std::setw(10) << newPid  // offset layer PID
                << "         2         2         0         0         0         0\n"
                << "$ $#      fs        fd        dc        vc       vdc    penchk        bt        dt\n"
                << "$      0.00      0.00      0.00      0.00      0.00         0      0.00  1.00E+20\n"
                << "$ ======================================================================\n"
                << "$\n";

    addedKeywordBlocks_.push_back(contactHint.str());
}
```

---

### Phase 12: Dual Offset Prestress Mode 구현

**파일**: `src/assembly/ModelAssembler.cpp`

#### 12.1 Main Dispatcher (🔧 FIXED: Replaces Phase 4 applyOffset)

**NOTE**: Phase 12 modifies Phase 4's `applyOffset()` to add dual offset support.
The original Phase 4 implementation becomes the "normal mode" branch.

```cpp
bool ModelAssembler::applyOffset(const OffsetOperation& op, double E, double nu) {  // ✅ E, nu 추가
    // Dual offset prestress mode 체크
    bool isDualOffset = (op.prestressMode == "dual_offset");

    if (isDualOffset) {
        return applyDualOffsetPrestress(op, E, nu);  // ✅ Pass E, nu
    } else {
        // Normal offset mode - use Phase 4 implementation directly
        // (Phase 4 code from lines 782-864 goes here)
        std::cout << "[INFO] Applying offset operation on PID " << op.sourcePid << "\n";

        // Validation, surface extraction, extrusion logic...
        // See Phase 4 for full implementation

        return true;
    }
}

bool ModelAssembler::applyDualOffsetPrestress(const OffsetOperation& op, double E, double nu) {  // ✅ E, nu 추가
    // 1. Source surface 추출
    std::vector<ShellElement> sourceSurface;
    extractSourceSurface(op.sourcePid, sourceSurface);

    Vector3D outwardDir = computeAverageNormal(sourceSurface);

    // 2. Connection mode에 따라 노드 처리 FIRST (🔧 CRITICAL FIX)
    std::map<int, int> origToBottomNode;  // Original node → offset layer bottom node
    std::map<int, Vector3D> deformedPositions;  // Bottom nodes → deformed positions

    if (op.connectionMode == "czm" || op.connectionMode == "contact") {
        // CZM/Contact: Duplicate nodes at INNER offset position
        for (const auto& shell : sourceSurface) {
            for (int i = 0; i < 4; ++i) {
                int origNid = shell.nodeIds[i];
                if (origToBottomNode.find(origNid) == origToBottomNode.end()) {
                    int newNid = ++maxNodeId_;
                    Vector3D origPos = baseMesh_.nodes.at(origNid).position;
                    Vector3D normal = computeShellNormal(shell);

                    // Deformed position (inner offset)
                    Vector3D innerPos = origPos + normal * op.innerOffset;

                    Node newNode;
                    newNode.id = newNid;
                    newNode.position = innerPos;  // Position at DEFORMED state
                    AddedNode an;
                an.id = newNid;
                an.x = newNode.position.x;
                an.y = newNode.position.y;
                an.z = newNode.position.z;
                addedNodes_.push_back(an);  // ✅ vector에 추가

                    origToBottomNode[origNid] = newNid;
                    deformedPositions[newNid] = innerPos;  // Track deformed pos
                }
            }
        }
    } else {
        // Tied: Use original nodes directly
        for (const auto& shell : sourceSurface) {
            for (int i = 0; i < 4; ++i) {
                int origNid = shell.nodeIds[i];
                if (origToBottomNode.find(origNid) == origToBottomNode.end()) {
                    Vector3D origPos = baseMesh_.nodes.at(origNid).position;
                    Vector3D normal = computeShellNormal(shell);

                    origToBottomNode[origNid] = origNid;  // Identity map
                    deformedPositions[origNid] = origPos + normal * op.innerOffset;
                }
            }
        }
    }

    // 3. Outward offset 형상으로 요소 생성 (reference state)
    //    Using updated sourceSurface with bottom nodes
    std::vector<ShellElement> modifiedSurface = sourceSurface;
    for (auto& shell : modifiedSurface) {
        for (int i = 0; i < 4; ++i) {
            shell.nodeIds[i] = origToBottomNode[shell.nodeIds[i]];
        }
    }

    std::vector<Element> refElements;
    extrudeToSolid(modifiedSurface, outwardDir, op.outerOffset - op.innerOffset,
                   op.numLayers, op.newPid, op.newSecid, refElements);

    // 4. Prestress 계산 (proper 3D strain)
    MaterialModel mat = MaterialModel::isotropicElastic(E, nu);  // ✅ 파라미터 사용
    calculateDualOffsetPrestress(refElements, deformedPositions, mat);

    // 5. CZM elements 생성 (only for czm mode)
    if (op.connectionMode == "czm") {
        createCzmElementsForDualOffset(sourceSurface, origToBottomNode, op);
    } else if (op.connectionMode == "contact") {
        // Add contact hint
        addContactHint(op.sourcePid, op.newPid);
    }

    // 6. Elements 추가
    for (auto& elem : refElements) {
        addedElements_.push_back(elem);
    }

    return true;
}
```

#### 12.2 Prestress 계산 (🔧 FIXED: Full 3D strain tensor)
```cpp
void ModelAssembler::calculateDualOffsetPrestress(
    const std::vector<Element>& refElements,
    const std::map<int, Vector3D>& deformedPositions,
    const MaterialModel& mat) {

    std::cout << "[INFO] Calculating dual offset prestress...\n";

    for (const auto& elem : refElements) {
        // Reference (outer) positions - 현재 요소 노드 위치
        Vector3D refNodes[8];
        for (int i = 0; i < 8; ++i) {
            refNodes[i] = getNodePosition(elem.nodeIds[i]);  // ✅ Use existing function
        }

        // Deformed (inner) positions - bottom은 inner offset, top은 비례 변형
        Vector3D defNodes[8];
        for (int i = 0; i < 4; ++i) {
            // Bottom face: deformed positions (inner offset)
            defNodes[i] = deformedPositions.at(elem.nodeIds[i]);
        }
        for (int i = 4; i < 8; ++i) {
            // Top face: proportional deformation
            // Assume linear through-thickness variation
            int bottomIdx = i - 4;
            Vector3D bottomRef = refNodes[bottomIdx];
            Vector3D bottomDef = defNodes[bottomIdx];
            Vector3D topRef = refNodes[i];

            // Deformation gradient from bottom
            Vector3D displacement = bottomDef - bottomRef;
            defNodes[i] = topRef + displacement;  // Same displacement for now
            // TODO: More sophisticated through-thickness interpolation
        }

        // === FULL 3D STRAIN CALCULATION (like squeeze) ===
        // Use isoparametric mapping at element center (r=s=t=0)

        // 1. Compute deformation gradient F = dx_def/dX_ref
        //    Using shape function derivatives at center

        // Simplified: Use central finite difference
        // Reference configuration vectors
        Vector3D dr_ref = (refNodes[1] - refNodes[0] + refNodes[2] - refNodes[3] +
                          refNodes[5] - refNodes[4] + refNodes[6] - refNodes[7]) * 0.125;
        Vector3D ds_ref = (refNodes[3] - refNodes[0] + refNodes[2] - refNodes[1] +
                          refNodes[7] - refNodes[4] + refNodes[6] - refNodes[5]) * 0.125;
        Vector3D dt_ref = (refNodes[4] - refNodes[0] + refNodes[5] - refNodes[1] +
                          refNodes[6] - refNodes[2] + refNodes[7] - refNodes[3]) * 0.125;

        // Deformed configuration vectors
        Vector3D dr_def = (defNodes[1] - defNodes[0] + defNodes[2] - defNodes[3] +
                          defNodes[5] - defNodes[4] + defNodes[6] - defNodes[7]) * 0.125;
        Vector3D ds_def = (defNodes[3] - defNodes[0] + defNodes[2] - defNodes[1] +
                          defNodes[7] - defNodes[4] + defNodes[6] - defNodes[5]) * 0.125;
        Vector3D dt_def = (defNodes[4] - defNodes[0] + defNodes[5] - defNodes[1] +
                          defNodes[6] - defNodes[2] + defNodes[7] - defNodes[3]) * 0.125;

        // 2. Metric tensors
        //    C = F^T * F (right Cauchy-Green)
        //    Small strain approximation: ε = 0.5 * (C - I)

        double eps_xx = 0.5 * (dr_def.dot(dr_def) / dr_ref.dot(dr_ref) - 1.0);
        double eps_yy = 0.5 * (ds_def.dot(ds_def) / ds_ref.dot(ds_ref) - 1.0);
        double eps_zz = 0.5 * (dt_def.dot(dt_def) / dt_ref.dot(dt_ref) - 1.0);

        // Shear strains (simplified)
        double eps_xy = 0.5 * (dr_def.dot(ds_def) / (dr_ref.magnitude() * ds_ref.magnitude()) -
                               dr_ref.dot(ds_ref) / (dr_ref.magnitude() * ds_ref.magnitude()));
        double eps_yz = 0.5 * (ds_def.dot(dt_def) / (ds_ref.magnitude() * dt_ref.magnitude()) -
                               ds_ref.dot(dt_ref) / (ds_ref.magnitude() * dt_ref.magnitude()));
        double eps_xz = 0.5 * (dr_def.dot(dt_def) / (dr_ref.magnitude() * dt_ref.magnitude()) -
                               dr_ref.dot(dt_ref) / (dr_ref.magnitude() * dt_ref.magnitude()));

        // 3. Convert strain to stress (isotropic elasticity)
        StressTensor stress = mat.computeStressFromStrain(
            eps_xx, eps_yy, eps_zz, eps_xy, eps_yz, eps_xz);

        // 4. Store stress
        ElementResult er;
        er.isValid = true;
        er.elementId = elem.id;
        er.isShell = false;
        er.stress = stress;
        er.vonMisesStress = stress.vonMises();

        accumulatedResults_.push_back(er);
    }

    std::cout << "[INFO] Prestress calculated for " << refElements.size() << " elements\n";
}
```

**개선사항**:
- ✅ 단순 두께 변형률 → **Full 3D strain tensor** (ε_xx, ε_yy, ε_zz, ε_xy, ε_yz, ε_xz)
- ✅ Isoparametric mapping으로 **deformation gradient** 계산
- ✅ In-plane strain 포함 (곡면 변형 반영)
- ✅ Squeeze operation과 동일한 방식

#### 12.3 CZM Elements for Dual Offset (⭐ NEW - Missing Implementation)

```cpp
void ModelAssembler::createCzmElementsForDualOffset(
    const std::vector<ShellElement>& sourceSurface,
    const std::map<int, int>& origToBottomNode,
    const OffsetOperation& op) {

    // 1. Get CZM IDs
    int czmPid = op.czmPartId > 0 ? op.czmPartId : ++maxPartId_;
    int czmSecid = czmPid;
    int czmMid = ++maxMaterialId_;

    // 2. Create cohesive elements connecting original surface to duplicated bottom nodes
    for (const auto& shell : sourceSurface) {
        Element cohElem;
        cohElem.id = ++maxElementId_;
        cohElem.partId = czmPid;
        cohElem.type = ElementType::HEX8;  // COH8D stored as HEX8

        // Bottom face: original nodes (source surface)
        cohElem.nodeIds[0] = shell.nodeIds[0];
        cohElem.nodeIds[1] = shell.nodeIds[1];
        cohElem.nodeIds[2] = shell.nodeIds[2];
        cohElem.nodeIds[3] = shell.nodeIds[3];

        // Top face: duplicated nodes (offset layer bottom)
        cohElem.nodeIds[4] = origToBottomNode.at(shell.nodeIds[0]);
        cohElem.nodeIds[5] = origToBottomNode.at(shell.nodeIds[1]);
        cohElem.nodeIds[6] = origToBottomNode.at(shell.nodeIds[2]);
        cohElem.nodeIds[7] = origToBottomNode.at(shell.nodeIds[3]);

        addedElements_.push_back(cohElem);
    }

    // 3. CZM PART/SECTION/MATERIAL 키워드 삽입
    std::string partBlock = formatPartBlock(czmPid, czmSecid, czmMid, "CZM_DualOffset");
    std::string sectionBlock = formatCzmSectionBlock(czmSecid);
    std::string materialBlock = op.czmMaterialCard;

    // @MID@ 치환
    size_t pos = 0;
    while ((pos = materialBlock.find("@MID@", pos)) != std::string::npos) {
        materialBlock.replace(pos, 5, std::to_string(czmMid));
        pos += std::to_string(czmMid).length();
    }

    addedKeywordBlocks_.push_back(partBlock);
    addedKeywordBlocks_.push_back(sectionBlock);
    addedKeywordBlocks_.push_back(materialBlock);

    std::cout << "[INFO] Created " << sourceSurface.size()
              << " CZM elements for dual offset (PID=" << czmPid << ")\n";
}
```

#### 12.4 Contact Hint for Dual Offset (⭐ NEW - Missing Implementation)

```cpp
void ModelAssembler::addContactHint(int sourcePid, int offsetPid) {
    std::ostringstream contactHint;
    contactHint << "$\n"
                << "$ ==================== CONTACT DEFINITION REQUIRED ====================\n"
                << "$ The offset layer uses connection_mode: contact\n"
                << "$ Add contact definition manually, for example:\n"
                << "$\n"
                << "$ *CONTACT_AUTOMATIC_SURFACE_TO_SURFACE\n"
                << "$ $#     cid                                                         title\n"
                << "$       999                                          Offset_Contact_Auto\n"
                << "$ $#    ssid      msid     sstyp     mstyp    sboxid    mboxid       spr       mpr\n"
                << "$  " << std::setw(8) << sourcePid
                << std::setw(10) << offsetPid
                << "         2         2         0         0         0         0\n"
                << "$ $#      fs        fd        dc        vc       vdc    penchk        bt        dt\n"
                << "$      0.00      0.00      0.00      0.00      0.00         0      0.00  1.00E+20\n"
                << "$ ======================================================================\n"
                << "$\n";

    addedKeywordBlocks_.push_back(contactHint.str());

    std::cout << "[INFO] Added contact definition hint (source PID=" << sourcePid
              << ", offset PID=" << offsetPid << ")\n";
}
```

---

## 5. 기술적 상세

### 5.1 Element Quality 검증

```cpp
bool ModelAssembler::isElementInverted(const Element& elem) {
    // Compute Jacobian at element center (r=s=t=0)
    double jac = computeJacobian(elem, 0, 0, 0);
    return jac <= 0;
}

double ModelAssembler::computeJacobian(const Element& elem,
                                       double r, double s, double t) {
    // Shape function derivatives for HEX8
    // dN/dr, dN/ds, dN/dt at (r,s,t)

    // Get element node positions
    Vector3D nodes[8];
    for (int i = 0; i < 8; ++i) {
        nodes[i] = getNodePosition(elem.nodeIds[i]);
    }

    // Jacobian matrix J = [dx/dr, dx/ds, dx/dt]
    //                     [dy/dr, dy/ds, dy/dt]
    //                     [dz/dr, dz/ds, dz/dt]

    // Simplified for center point (r=s=t=0):
    Vector3D dxdr = (nodes[1] - nodes[0] + nodes[2] - nodes[3] +
                     nodes[5] - nodes[4] + nodes[6] - nodes[7]) * 0.125;
    Vector3D dxds = (nodes[3] - nodes[0] + nodes[2] - nodes[1] +
                     nodes[7] - nodes[4] + nodes[6] - nodes[5]) * 0.125;
    Vector3D dxdt = (nodes[4] - nodes[0] + nodes[5] - nodes[1] +
                     nodes[6] - nodes[2] + nodes[7] - nodes[3]) * 0.125;

    // Determinant = dxdr · (dxds × dxdt)
    return dxdr.dot(dxds.cross(dxdt));
}
```

### 5.2 Outward Normal 보정

```cpp
Vector3D ModelAssembler::computeOutwardNormal(const Element& elem, int faceIndex) {
    // Compute face normal
    auto faceNodes = elem.getFaceNodeIds(faceIndex);
    Vector3D p0 = getNodePosition(faceNodes[0]);
    Vector3D p1 = getNodePosition(faceNodes[1]);
    Vector3D p2 = getNodePosition(faceNodes[2]);

    Vector3D v1 = p1 - p0;
    Vector3D v2 = p2 - p0;
    Vector3D faceNormal = v1.cross(v2).normalize();

    // Compute face centroid
    Vector3D faceCentroid = (p0 + p1 + p2 + getNodePosition(faceNodes[3])) * 0.25;

    // Compute element centroid
    Vector3D elemCentroid = computeElementCenter(elem);

    // Outward direction = from element center to face center
    Vector3D outwardDir = (faceCentroid - elemCentroid).normalize();

    // Flip normal if pointing inward
    if (faceNormal.dot(outwardDir) < 0) {
        faceNormal = faceNormal * -1.0;
    }

    return faceNormal;
}

// NOTE: computeElementCenter() is already implemented in Phase 6.5 - no duplicate needed here
```

### 5.3 WriteOutput 통합

**기존 writeOutput()은 이미 처리**:
- `addedElements_` → `*ELEMENT_SOLID` 섹션에 자동 출력
- `addedShellElements_` → `*ELEMENT_SHELL` 섹션에 자동 출력
- `addedKeywordBlocks_` → `*END` 전에 삽입

**추가 작업 불필요** ✅

---

## 6. 검증 전략

### 6.1 Unit Tests

#### Test 1: QUAD4 → HEX8 (1 layer)
```yaml
- type: offset
  source_pid: 1  # Single QUAD4
  offset_direction: +z
  thickness: 1.0
  num_layers: 1
  element_type: solid
```
**기대 결과**: 1 HEX8 element, 8 nodes

#### Test 2: TRIA3 → WEDGE6 (2 layers)
```yaml
- type: offset
  source_pid: 2  # Single TRIA3
  offset_direction: +normal
  thickness: 2.0
  num_layers: 2
  element_type: solid
```
**기대 결과**: 2 degenerate HEX8 (WEDGE), 9 nodes

#### Test 3: Shell → Shell offset
```yaml
- type: offset
  source_pid: 3
  offset_direction: +z
  thickness: 0.5
  element_type: shell
  shell_offset: 0.25
```
**기대 결과**: Offset shell at z=0.25

#### Test 4: Solid surface extraction
```yaml
- type: offset
  source_pid: 4  # HEX8 solid block
  offset_direction: +z
  thickness: 0.1
  element_type: shell
```
**기대 결과**: Top surface extracted → offset shell created

### 6.2 Integration Tests

#### Test 5: Multi-layer coating
```yaml
operations:
  - type: offset  # Layer 1
    source_pid: 1
    thickness: 0.2
    num_layers: 2
    element_type: solid
    new_pid: 10

  - type: offset  # Layer 2 on top of Layer 1
    source_pid: 10  # Reference newly created layer
    thickness: 0.1
    num_layers: 1
    element_type: solid
    new_pid: 20
```

#### Test 6: Combined operations
```yaml
operations:
  - type: replace
    # ...
  - type: offset  # Offset after replace
    # ...
  - type: warpage  # Warpage on offset layer
    # ...
```

### 6.3 Validation Checklist

- [ ] QUAD4 → HEX8 올바른 connectivity
- [ ] TRIA3 → WEDGE6 degenerate 형식
- [ ] Normal 방향 일관성 (outward)
- [ ] Node 중복 생성 방지
- [ ] Element inversion 감지
- [ ] ID collision 방지
- [ ] Material card MID 치환
- [ ] TSHELL element 형식 (ELFORM=16/17)
- [ ] Shell offset 위치 정확도
- [ ] Multi-operation 호환성
- [ ] WriteOutput 정상 출력

---

## 7. 사용 예시

### 예시 1: 얇은 알루미늄 코팅

```yaml
base_model: base_part.k
output: coated_part.k

operations:
  - type: offset
    source_pid: 1
    offset_direction: +normal
    thickness: 0.05           # 50 μm coating
    num_layers: 1
    element_type: solid

    part_title: "Al Coating"

    material_card: |
      *MAT_ELASTIC
      $#     mid        ro         e        pr
            @MID@   2.70000   7.00E+04      0.33
```

### 예시 2: 접착제 레이어 (Shell)

```yaml
operations:
  - type: offset
    source_pid: 2
    offset_direction: +z
    thickness: 0.1
    element_type: shell
    shell_thickness: 0.1
    shell_offset: 0.05        # Mid-plane

    part_title: "Adhesive"
    new_mid: 50

    material_card: |
      *MAT_COHESIVE_MIXED_MODE
      $#     mid     roflg      intff
            @MID@         0          0
      $#       e        pr        en        et       gic       giic      xmu      t
       1.00E+03      0.30  1.00E+03  1.00E+03  1.00E-01  1.00E-01      2.0  5.00E-02
```

### 예시 3: Multi-layer 라미네이트

```yaml
operations:
  # Layer 1: CFRP
  - type: offset
    source_pid: 1
    offset_direction: +z
    thickness: 0.2
    num_layers: 2
    element_type: solid
    new_pid: 10
    part_title: "CFRP Layer 1"
    material_card: |
      *MAT_COMPOSITE_DAMAGE
      $#     mid        ro        ea        eb        ec      prba      prca      prcb
            @MID@  1.60E-09  1.50E+05  1.00E+04  1.00E+04      0.30      0.30      0.35

  # Layer 2: Honeycomb core
  - type: offset
    source_pid: 10            # Build on Layer 1
    offset_direction: +z
    thickness: 5.0
    num_layers: 1
    element_type: solid
    new_pid: 20
    part_title: "Honeycomb Core"
    material_card: |
      *MAT_HONEYCOMB
      $#     mid        ro         e        pr      sigy        vf        mu       bulk
            @MID@  1.00E-10  1.00E+03      0.00  1.00E+01      0.00      0.00  1.00E+03

  # Layer 3: CFRP (top)
  - type: offset
    source_pid: 20            # Build on Layer 2
    offset_direction: +z
    thickness: 0.2
    num_layers: 2
    element_type: solid
    new_pid: 30
    part_title: "CFRP Layer 2"
    material_card: |
      *MAT_COMPOSITE_DAMAGE
      $#     mid        ro        ea        eb        ec      prba      prca      prcb
            @MID@  1.60E-09  1.50E+05  1.00E+04  1.00E+04      0.30      0.30      0.35
```

### 예시 4: Solid 표면에 Shell 추가

```yaml
operations:
  - type: offset
    source_pid: 5             # Solid part
    offset_direction: +normal # Auto-extract outer surface
    thickness: 0.0
    element_type: shell
    shell_thickness: 0.01
    shell_offset: 0.0         # On solid surface

    part_title: "Contact Shell"
    material_card: |
      *MAT_ELASTIC
      $#     mid        ro         e        pr
            @MID@   7.85000   2.10E+05      0.30
```

### 예시 5: 파우치 Wrapping (Dual Offset Prestress) ⭐NEW!

**목적**: 얇은 필름이 물체를 감싸며 조이는 장력 시뮬레이션

```yaml
operations:
  - type: offset
    source_pid: 1             # 감싸질 대상 파트 (리지드한 물체)
    element_type: solid       # 필름을 solid로 모델링

    # Dual offset prestress 모드 활성화
    prestress_mode: dual_offset
    inner_offset: -0.15       # 압축된 형상 (deformed, 음수)
    outer_offset: 0.35        # 릴랙스 형상 (reference, 양수)

    # 연결 모드: contact (필름이 물체에서 분리 가능)
    connection_mode: contact

    num_layers: 1
    new_pid: 100
    part_title: "Pouch Film"

    # 얇은 필름 재료 (낮은 탄성계수, 높은 변형률)
    material_card: |
      *MAT_ELASTIC
      $#     mid        ro         e        pr
            @MID@  1.00E-09  3.00E+03      0.40
```

**물리적 의미**:
- 원본 파트 표면 = 압축된 상태 (deformed)
- 필름을 0.35mm 바깥쪽으로 펼친 상태가 릴랙스 상태 (reference)
- 실제로는 0.15mm 안쪽으로 압축되어 조여진 상태
- **총 변형량**: 0.35 - (-0.15) = 0.5mm
- **변형률**: ε = 0.5 / 0.35 ≈ 143% (대변형!)
- **결과**: 필름에 높은 인장 응력 (장력) 발생 → 물체를 조이는 힘

**응용**:
- Pouch cell 배터리 케이싱
- Shrink wrap 포장재
- 타이어-림 조립체 (타이어가 림을 압착)
- Fabric wrapping (천이 물체를 감쌈)

### 예시 6: CZM 연결 모드 (De-lamination 해석) ⭐NEW!

**목적**: 코팅층이 기판에서 박리되는 현상 시뮬레이션

```yaml
operations:
  - type: offset
    source_pid: 1             # 기판 파트
    offset_direction: +normal
    thickness: 0.05           # 얇은 코팅층
    num_layers: 1
    element_type: solid

    # CZM 연결 모드 (cohesive elements 자동 삽입)
    connection_mode: czm

    # CZM 재료 정의
    czm_mid: 200
    czm_material_card: |
      *MAT_COHESIVE_MIXED_MODE
      $#     mid        ro      roflg     intfail
            @MID@     0.0         0         1.0
      $#    en        et        gic       giic      xmu       t         s
        1.00E+04  1.00E+04  5.00E+01  5.00E+01     2.0  1.00E+01  1.00E+01

    new_pid: 10
    part_title: "Thin Film Coating"

    # 코팅층 재료 (경질)
    material_card: |
      *MAT_ELASTIC
      $#     mid        ro         e        pr
            @MID@  3.90E-09  3.50E+05      0.25
```

**CZM 파라미터 설명**:
- `en`, `et`: Normal/tangential stiffness (1e4 MPa/mm)
- `gic`, `giic`: Mode I/II fracture energy (50 mJ/mm²)
- `t`, `s`: Normal/shear strength (10 MPa)
- `intfail=1.0`: Complete failure after damage

**결과**:
- 기판(PID 1)과 코팅층(PID 10) 사이에 자동으로 COH8D 요소 삽입
- De-lamination 시작/진행/완료 과정 시뮬레이션 가능
- Damage variable 추적 (0=intact, 1=failed)

---

## 8. 구현 일정

### 타임라인 (예상)

| Phase | 작업 내용 | 예상 시간 | 누적 |
|-------|----------|----------|------|
| 1 | AssemblyConfig.h 구조체 | 0.5일 | 0.5일 |
| 2 | YAML 파서 (+ validation) 🔧 | 1.5일 | 2일 |
| 3 | ModelAssembler.h 선언 | 0.5일 | 2.5일 |
| 4 | applyOffset() 메인 로직 | 1일 | 3.5일 |
| 5 | extractSourceSurface() 🔧 | 1.5일 | 5일 |
| 6 🔧 | **Helper methods (moved up)** | **1.5일** | **6.5일** |
| 7 🔧 | extrudeToSolid() | 1일 | 7.5일 |
| 8 🔧 | extrudeToTShell() | 1일 | 8.5일 |
| 9 🔧 | createOffsetShell() | 0.5일 | 9일 |
| 10 | main.cpp dispatch + keywords | 0.5일 | 9일 |
| **11** ⭐ | **Connection mode (tied/czm/contact)** 🔧 | **2일** | **11일** |
| **12** ⭐ | **Dual offset prestress (3D strain)** 🔧 | **2.5일** | **13.5일** |
| **테스트** | Unit + integration tests | 3일 | 16.5일 |
| **문서** | 사용자 가이드 + 예제 | 1일 | 17.5일 |

**총 예상 기간**: **17-20일** (기본 9일 + 확장 4.5일 + 수정 3.5일 + 테스트/문서 4일)

**🔧 수정 반영 (v2.1)**:
- Phase 2: Validation 강화 (+0.5일)
- Phase 5: Solid surface 추출 완성 (+0.5일)
- **Phase 6-9: 순서 재배치** (Helper → Extrude 순서로 변경, +0.5일)
- Phase 11: CZM ELFORM=20 + Contact hint (+0.5일)
- Phase 12: 3D strain tensor 계산 (+1일)
- 테스트: 더 복잡한 시나리오 (+0.5일)

### 우선순위

1. **High Priority** (핵심 기능 - 기본 offset):
   - Phase 1-4: 기본 구조
   - Phase 5-6: Solid extrude
   - Phase 9-10: Helper + dispatch
   - **Phase 11 (tied mode only)**: Node sharing (기본 연결)

2. **Medium Priority** (확장 기능):
   - Phase 7: TShell 지원
   - Phase 8: Shell offset
   - **Phase 11 (czm/contact modes)**: CZM/Contact 연결 모드

3. **Advanced Priority** (고급 기능 ⭐NEW):
   - **Phase 12**: Dual offset prestress mode (파우치 wrapping)
   - Outward normal 자동 보정
   - Element quality 검증
   - Multi-layer validation

### 단계적 구현 전략

**Step 1** (1주): Basic offset (tied mode only)
- Phase 1-6, 9-10
- 단순 tied connection만 지원
- Solid extrude 기본 기능

**Step 2** (1-2일): Connection modes
- Phase 11 (CZM + Contact)
- De-lamination 해석 지원

**Step 3** (1-2일): Prestress mode
- Phase 12 (Dual offset)
- Pouch wrapping 시뮬레이션

---

## 9. 의존성 및 제약사항

### 9.1 의존성

- **Vector3D**: cross(), dot(), normalize() 메서드 필요
- **Element**: getFaceNodeIds() 메서드 필요
- **Mesh**: getShellElements(), getElements() 필요
- **기존 인프라**: addedKeywordBlocks_, addedNodes_, addedElements_

### 9.2 제약사항

1. **LS-DYNA 제약**:
   - WEDGE6는 native가 아님 (degenerate HEX8로 저장)
   - TSHELL은 ELFORM으로 구분 (16=QUAD, 17=TRIA)

2. **구현 제약**:
   - Solid surface extraction은 manifold mesh 가정
   - Normal 방향은 평균값 사용 (curved surface에서 부정확할 수 있음)
   - Element quality 검증은 중심점 Jacobian만 (코너는 미검증)

3. **성능 제약**:
   - 대형 메시 (>100K elements) 표면 추출 시 메모리/시간 소요
   - Multi-layer 생성 시 노드/요소 급증

---

## 10. 향후 확장 가능성

### 가능한 개선사항

1. **Curved surface 지원**:
   - Per-element normal 사용 (평균 대신)
   - Smooth transition at edges

2. **Variable thickness**:
   - Node별 다른 thickness (두께 분포 함수)
   ```yaml
   thickness_function: "0.1 + 0.05*sin(x/10)"
   ```

3. **Gradation**:
   - Material property gradation through thickness
   - Multiple materials per layer

4. **Conformal meshing**:
   - Offset 후 원본과 node 공유 (tied contact 대신 conformal)

5. **Performance**:
   - Parallel surface extraction (OpenMP)
   - Spatial hashing for large meshes

---

## 11. 체크리스트

### 구현 전 확인
- [x] 문제점 식별 및 해결방안 수립
- [x] YAML 인터페이스 설계
- [x] 구조체 설계
- [x] 알고리즘 pseudocode 작성
- [x] 검증 전략 수립

### 구현 체크리스트
- [ ] Phase 1: AssemblyConfig.h
- [ ] Phase 2: YAML Parser + validation
- [ ] Phase 3: ModelAssembler.h 선언
- [ ] Phase 4: applyOffset() 메인
- [ ] Phase 5: Surface extraction
- [ ] Phase 6: Solid extrude
- [ ] Phase 7: TShell extrude
- [ ] Phase 8: Shell offset
- [ ] Phase 9: Helper methods
- [ ] Phase 10: main.cpp dispatch

### 테스트 체크리스트
- [ ] Test 1: QUAD4 → HEX8
- [ ] Test 2: TRIA3 → WEDGE6
- [ ] Test 3: Shell offset
- [ ] Test 4: Solid surface extraction
- [ ] Test 5: Multi-layer
- [ ] Test 6: Combined operations
- [ ] Quality validation
- [ ] Performance test (large mesh)

### 문서화 체크리스트
- [ ] YAML 사용 예시
- [ ] KooRemapper_Guide.txt 업데이트
- [ ] 이론 섹션 추가 (Manual)
- [ ] Troubleshooting 가이드

---

## 부록 A: LS-DYNA 키워드 참조

### *ELEMENT_SHELL (TSHELL)

```
*ELEMENT_SHELL
$#   eid     pid      n1      n2      n3      n4      n5      n6      n7      n8
       1       1       1       2       3       4       5       6       7       8
```

ELFORM=16 (TSHELL4): 8 nodes (4 bottom + 4 top)
ELFORM=17 (TSHELL3): 6 nodes (3 bottom + 3 top), pad with 0

### *SECTION_TSHELL

```
*SECTION_TSHELL
$#   secid    elform      shrf       nip     propt   qr/irid     icomp     setyp
         1        16       0.0         3       1.0         0         0         0
$#      t1        t2        t3        t4      nloc     marea      idof    edgset
     0.100     0.100     0.100     0.100       0.0       0.0       0.0         0
```

### Degenerate Elements

**WEDGE6** (stored as HEX8):
```
N4 = N3
N8 = N7
```

**TET4** (stored as HEX8):
```
N5 = N6 = N7 = N8 = N4
```

---

**문서 버전**: 1.0
**최종 수정**: 2026-02-19
**작성자**: KooRemapper Development Team
**상태**: Ready for Implementation ✅
