# Shell Element Indent 구현 계획

## 목표
쉘(QUAD4) 요소에도 indent/emboss를 적용하고, `*INITIAL_STRESS_SHELL` 키워드로
적절한 벤딩 초기응력을 출력한다.

## 현재 상태 분석

### 쉘 요소 파싱 (KFileReader)
- `*ELEMENT_SHELL` → `parseElementShellSection()`: QUAD4를 읽되 nodeIds[4-7]=nodeIds[0-3]으로 중복 저장
- `ElementType` enum에 QUAD4 없음 → **전부 HEX8로 저장됨**
- `*SECTION_SHELL`은 skipToNextKeyword()로 건너뜀 (NIP/두께 정보 미보존)

### indent 기하형상 (이미 동작)
- 쉘은 두께=0 → tFrac=1.0 → 노드에 hSurface 직접 적용 → **기하형상은 이미 동작**
- bottomRatio 무시 (두께 없으므로 자연스러움)

### indent 응력 (미동작)
- d_neutral = nc - nMid → thickness=0이면 d_neutral≈0 → 응력=0 → **쉘 응력 미출력**
- `*INITIAL_STRESS_SHELL` 포맷 미구현

### dynain 출력
- `*INITIAL_STRESS_SOLID`만 지원

---

## *INITIAL_STRESS_SHELL 포맷 (LS-DYNA Vol_I, 28-95)

```
Card 1:  EID(10) NPLANE(8) NTHICK(8) NHISV(8) NTENSR(8) LARGE(8) NTHINT(8) NTHHSV(8)
Card 2 (×NPLANE×NTHICK):  T(10) SIGXX(10) SIGYY(10) SIGZZ(10) SIGXY(10) SIGYZ(10) SIGZX(10) EPS(10)

NPLANE = 1  (단일 면내 적분점)
NTHICK = 2  (상면+하면 2개 적분점, 선형 굽힘)
T = parametric coordinate (-1 ~ +1)
T=-1: 하면, T=+1: 상면
SIGij: GLOBAL 좌표계 응력
```

---

## 핵심 설계

### 쉘 벤딩 응력

쉘 두께 t에서 Kirchhoff 판이론:
```
d_neutral = ±(t/2)  (상면: +t/2, 하면: -t/2)

kappa_11, kappa_22, kappa_12 = indent 곡률 분해 (기존 로직 동일)

상면 (T=+1): eps = -(+t/2) * kappa → 역방향 → stress_top
하면 (T=-1): eps = -(-t/2) * kappa → 역방향 → stress_bot

순수 굽힘 → 상면/하면 응력 크기 동일, 부호 반대
```

### 쉘 두께 결정 (우선순위)
1. YAML `shell_thickness` 필드 (명시적)
2. K파일 `*SECTION_SHELL` → Part SECID → T1 두께 (자동)

---

## 변경 사항

### Phase 1: 쉘 요소 타입 구분 (~30줄)

**Element.h**
- `ElementType::QUAD4` 추가

**KFileReader.cpp** - `parseElementShellSection()`
- 파싱된 Element의 `type`을 `ElementType::QUAD4`로 설정

**ElementAnalyzer.h** - `ElementResult`
- `bool isShell = false;` 추가
- `double shellThickness = 0.0;` 추가
- `StressTensor stressTop;` 추가 (쉘 상면)
- `StressTensor stressBottom;` 추가 (쉘 하면)

### Phase 2: 쉘 두께 확보 (~40줄)

**AssemblyConfig.h** - `IndentOperation`
- `double shellThickness = 0.0;` 추가

**AssemblyConfigReader.cpp**
- `shell_thickness` YAML 키 파싱

**KFileReader.cpp** + **Mesh.h**
- `*SECTION_SHELL` 파싱: SECID + 두 번째 줄에서 T1 추출
- `struct SectionShellData { int id; double thickness; };`
- `std::map<int, SectionShellData> shellSections;`

### Phase 3: applyIndent() 쉘 응력 분기 (~80줄)

**ModelAssembler.cpp**

쉘 파트 감지:
```cpp
bool isShellPart = false;
for (auto& [eid, elem] : baseMesh_.getElements()) {
    if (elem.partId == op.targetPid && elem.type == ElementType::QUAD4) {
        isShellPart = true; break;
    }
}
```

쉘 두께 결정:
```cpp
double shellThk = op.shellThickness;
if (shellThk <= 0 && isShellPart) {
    // K파일 SECTION_SHELL에서 탐지
    auto partIt = baseMesh_.parts.find(op.targetPid);
    if (partIt != baseMesh_.parts.end()) {
        auto secIt = baseMesh_.shellSections.find(partIt->second.sectionId);
        if (secIt != baseMesh_.shellSections.end())
            shellThk = secIt->second.thickness;
    }
}
```

쉘 응력 계산:
```cpp
if (isShellPart && shellThk > 0) {
    // 곡률 계산은 솔리드와 동일 (hpp, kappa 분해)
    // 쉘 두께의 strainLimit cap:
    hppMax = strainLimit / (shellThk * 0.5);

    // 상면 (d_neutral = +shellThk/2)
    eps_top = -(shellThk/2) * kappa
    stress_top = fromStrain(eps_top * (-1), E, nu)

    // 하면 (d_neutral = -shellThk/2)
    eps_bot = +(shellThk/2) * kappa
    stress_bot = fromStrain(eps_bot * (-1), E, nu)

    er.isShell = true;
    er.shellThickness = shellThk;
    er.stressTop = stress_top;
    er.stressBottom = stress_bot;
}
```

### Phase 4: *INITIAL_STRESS_SHELL 출력 (~60줄)

**ModelAssembler.cpp** - `writeOutput()`

accumulatedResults_를 shell/solid로 분리 출력:
```cpp
// *INITIAL_STRESS_SOLID (기존 솔리드)
// *INITIAL_STRESS_SHELL (쉘)
for (auto& er : shellResults) {
    // Card 1: EID, NPLANE=1, NTHICK=2
    // Card 2: T=-1.0, stressBottom.xx/yy/zz/xy/yz/xz, eps=0
    // Card 3: T=+1.0, stressTop.xx/yy/zz/xy/yz/xz, eps=0
}
```

**DynainWriter.cpp**도 동일하게 수정 (별도 .dynain 파일 출력 시).

### Phase 5: 응력 병합 수정 (~15줄)

**writeOutput() merge 로직**
- 쉘 결과끼리 merge: stressTop += other.stressTop, stressBottom += other.stressBottom
- isShell 플래그 보존

### Phase 6: 테스트 + 예제

1. 쉘 메쉬 생성 (10×10 QUAD4, thickness=1.0)
2. indent 기하형상 테스트 (stress: false)
3. indent + 응력 테스트 (stress: true, shell_thickness: 1.0)
4. dynain 출력 포맷 검증 (NPLANE=1, NTHICK=2, T값, 응력 부호)
5. 기존 유닛 테스트 통과

---

## 구현 순서

```
Phase 1: ElementType::QUAD4 + isShell 필드              ~30줄
Phase 2: shell_thickness (YAML + SECTION_SHELL 파싱)    ~40줄
Phase 3: applyIndent() 쉘 응력 분기                      ~80줄
Phase 4: *INITIAL_STRESS_SHELL 출력                      ~60줄
Phase 5: 응력 병합 수정                                   ~15줄
Phase 6: 테스트 + 예제                                   검증
```

총 예상: ~225줄 수정/추가
