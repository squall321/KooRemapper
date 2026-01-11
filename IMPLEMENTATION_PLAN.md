# KooRemapper - 구현 계획서

## 프로젝트 개요

LS-DYNA k-file 포맷의 정렬 육면체 격자(굽혀진 형상)를 분석하고,
비정렬 격자를 동일한 굽힘 변환으로 매핑하는 **크로스플랫폼 C++ CLI 프로그램**

### 지원 플랫폼
- **Windows** (MSVC, MinGW)
- **Linux** (GCC, Clang)
- **macOS** (Clang, Apple Silicon 포함)

### 프로그램 특성
- **CLI (Command Line Interface)** 기반
- 외부 라이브러리 의존성 최소화 (순수 C++ 표준 라이브러리 사용)
- CMake 기반 크로스플랫폼 빌드 시스템

---

## Phase 1: 프로젝트 기본 구조 설정

### 1.1 디렉토리 구조 생성
```
KooRemapper/
├── src/
│   ├── core/           # 핵심 데이터 구조
│   ├── parser/         # K-file 파서
│   ├── grid/           # 격자 분석 및 생성
│   ├── mapper/         # 매핑 기능
│   ├── generator/      # 예제 메시 생성기
│   ├── cli/            # CLI 인터페이스
│   └── main.cpp
├── include/
│   ├── core/
│   ├── parser/
│   ├── grid/
│   ├── mapper/
│   ├── generator/
│   └── cli/
├── tests/              # 테스트 파일
├── examples/           # 예제 k-file (자동 생성)
│   ├── flat_grid.k
│   ├── teardrop_bent.k
│   ├── arc_bent.k
│   ├── s_curve_bent.k
│   └── unstructured_flat.k
├── scripts/            # 빌드 스크립트
│   ├── build_windows.bat
│   ├── build_linux.sh
│   ├── build_macos.sh
│   └── generate_examples.sh
├── CMakeLists.txt
├── CMakePresets.json   # CMake 프리셋 (크로스플랫폼)
└── README.md
```

### 1.2 CMakeLists.txt 작성 (크로스플랫폼)
- C++17 표준 사용
- 외부 라이브러리 없이 순수 C++ 표준 라이브러리만 사용
- 플랫폼별 컴파일러 옵션 설정

```cmake
cmake_minimum_required(VERSION 3.16)
project(KooRemapper VERSION 1.0.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

# 크로스플랫폼 컴파일러 설정
if(MSVC)
    add_compile_options(/W4 /WX /utf-8)
    add_definitions(-D_CRT_SECURE_NO_WARNINGS)
else()
    add_compile_options(-Wall -Wextra -Wpedantic -Werror)
endif()

# 플랫폼별 정의
if(WIN32)
    add_definitions(-DPLATFORM_WINDOWS)
elseif(APPLE)
    add_definitions(-DPLATFORM_MACOS)
else()
    add_definitions(-DPLATFORM_LINUX)
endif()
```

### 1.3 CMakePresets.json (멀티플랫폼 빌드 프리셋)
```json
{
  "version": 3,
  "configurePresets": [
    {
      "name": "windows-release",
      "generator": "Visual Studio 17 2022",
      "binaryDir": "${sourceDir}/build/windows",
      "cacheVariables": { "CMAKE_BUILD_TYPE": "Release" }
    },
    {
      "name": "linux-release",
      "generator": "Unix Makefiles",
      "binaryDir": "${sourceDir}/build/linux",
      "cacheVariables": { "CMAKE_BUILD_TYPE": "Release" }
    },
    {
      "name": "macos-release",
      "generator": "Unix Makefiles",
      "binaryDir": "${sourceDir}/build/macos",
      "cacheVariables": { "CMAKE_BUILD_TYPE": "Release" }
    }
  ]
}
```

### 1.4 플랫폼 추상화 레이어
**파일**: `include/core/Platform.h`
```cpp
#pragma once

// 플랫폼별 경로 구분자
#ifdef PLATFORM_WINDOWS
    #define PATH_SEPARATOR '\\'
    #define PATH_SEPARATOR_STR "\\"
#else
    #define PATH_SEPARATOR '/'
    #define PATH_SEPARATOR_STR "/"
#endif

// 플랫폼별 줄바꿈
#ifdef PLATFORM_WINDOWS
    #define LINE_ENDING "\r\n"
#else
    #define LINE_ENDING "\n"
#endif

namespace Platform {
    std::string getExecutablePath();
    std::string normalizePath(const std::string& path);
    bool fileExists(const std::string& path);
    bool createDirectory(const std::string& path);
}
```

---

## Phase 2: 핵심 데이터 구조 (Core Classes)

### 2.1 Vector3D 클래스
**파일**: `include/core/Vector3D.h`, `src/core/Vector3D.cpp`
```cpp
class Vector3D {
    double x, y, z;
    // 연산자 오버로딩: +, -, *, /, dot, cross
    // 노름, 정규화
};
```

### 2.2 Node 클래스
**파일**: `include/core/Node.h`, `src/core/Node.cpp`
```cpp
class Node {
    int id;
    Vector3D position;
    // 추후 매핑된 위치 저장용
    Vector3D mappedPosition;
};
```

### 2.3 Element 클래스 (8절점 육면체)
**파일**: `include/core/Element.h`, `src/core/Element.cpp`
```cpp
class Element {
    int id;
    int nodeIds[8];      // 8개 절점 ID
    int partId;

    // 격자 인덱스 (나중에 계산)
    int i, j, k;         // 구조격자 내 위치
    bool indexAssigned;
};
```

### 2.4 Mesh 클래스
**파일**: `include/core/Mesh.h`, `src/core/Mesh.cpp`
```cpp
class Mesh {
    std::map<int, Node> nodes;
    std::map<int, Element> elements;

    // 메시 통계
    int nodeCount, elementCount;
    Vector3D boundingBoxMin, boundingBoxMax;
};
```

---

## Phase 3: K-File 파서 구현

### 3.1 KFileReader 클래스
**파일**: `include/parser/KFileReader.h`, `src/parser/KFileReader.cpp`

#### 3.1.1 파싱할 키워드
- `*NODE` : 절점 데이터
- `*ELEMENT_SOLID` : 육면체 요소 데이터
- `*PART` : 파트 정보 (선택적)
- `*END` : 파일 끝

#### 3.1.2 구현 메서드
```cpp
class KFileReader {
    bool readFile(const std::string& filename);
    bool parseNodeSection(std::ifstream& file);
    bool parseElementSection(std::ifstream& file);
    Mesh getMesh();
private:
    Mesh mesh;
    std::string currentKeyword;
    bool isKeywordLine(const std::string& line);
    std::vector<std::string> tokenize(const std::string& line);
};
```

### 3.2 KFileWriter 클래스
**파일**: `include/parser/KFileWriter.h`, `src/parser/KFileWriter.cpp`
```cpp
class KFileWriter {
    bool writeFile(const std::string& filename, const Mesh& mesh);
    void writeNodeSection(std::ofstream& file, const Mesh& mesh);
    void writeElementSection(std::ofstream& file, const Mesh& mesh);
};
```

---

## Phase 4: 요소 연결성 분석 (Connectivity Analysis)

### 4.1 ConnectivityAnalyzer 클래스
**파일**: `include/grid/ConnectivityAnalyzer.h`, `src/grid/ConnectivityAnalyzer.cpp`

#### 4.1.1 면 공유 분석
```cpp
struct Face {
    int nodeIds[4];  // 정렬된 4개 노드 ID
    int elementId;
    int localFaceIndex;  // 0-5 (육면체의 6면)
};

class ConnectivityAnalyzer {
    // 요소간 인접 관계 구축
    std::map<int, std::vector<int>> elementNeighbors;  // 요소 ID -> 인접 요소 ID들

    void buildFaceMap(const Mesh& mesh);
    void findNeighbors(const Mesh& mesh);

    // 면 해시 생성 (4개 노드 ID를 정렬하여 고유 키 생성)
    std::string getFaceHash(int n1, int n2, int n3, int n4);
};
```

#### 4.1.2 육면체 면 정의 (로컬 인덱스 기준)
```
Face 0 (i-): nodes 0,3,7,4
Face 1 (i+): nodes 1,2,6,5
Face 2 (j-): nodes 0,1,5,4
Face 3 (j+): nodes 3,2,6,7
Face 4 (k-): nodes 0,1,2,3
Face 5 (k+): nodes 4,5,6,7
```

---

## Phase 5: 구조격자 인덱스 유도 (i,j,k Assignment)

### 5.1 StructuredGridIndexer 클래스
**파일**: `include/grid/StructuredGridIndexer.h`, `src/grid/StructuredGridIndexer.cpp`

#### 5.1.1 알고리즘 개요
1. **시작 요소 선택**: 코너에 위치한 요소 (3개 면만 인접 요소가 있는 요소)
2. **BFS/Flood Fill**: 연결성을 따라 i,j,k 전파
3. **축 크기 결정**: 각 방향의 최대 인덱스 파악

#### 5.1.2 구현
```cpp
class StructuredGridIndexer {
    int dimI, dimJ, dimK;  // 각 축의 요소 개수

    // 코너 요소 찾기 (인접 요소가 3개인 요소)
    int findCornerElement(const Mesh& mesh, const ConnectivityAnalyzer& ca);

    // 시작 요소에서 초기 i,j,k 방향 결정
    void determineInitialDirections(const Mesh& mesh, int startElem,
                                    const ConnectivityAnalyzer& ca);

    // BFS로 전체 격자 인덱싱
    void propagateIndices(Mesh& mesh, const ConnectivityAnalyzer& ca);

    // 축 재정렬: dimK < dimJ < dimI 되도록
    void reorderAxes(Mesh& mesh);
};
```

#### 5.1.3 상세 알고리즘
```
1. 코너 요소 탐색:
   - 모든 요소에 대해 인접 요소 개수 계산
   - 인접 요소가 정확히 3개인 요소 = 코너

2. 초기 방향 설정:
   - 코너 요소를 (0,0,0)으로 설정
   - 3개 인접 요소를 각각 i+, j+, k+ 방향으로 잠정 할당

3. BFS 전파:
   Queue에 시작 요소 추가
   While Queue not empty:
       현재 요소 = Queue.pop()
       For each 인접 요소:
           If 아직 인덱스 미할당:
               공유 면 방향에 따라 인덱스 계산
               Queue에 추가

4. 축 재정렬:
   - 최종 dimI, dimJ, dimK 비교
   - dimK가 가장 작고, dimI가 가장 크도록 축 스왑
```

---

## Phase 6: 경계면 및 엣지 계산

### 6.1 BoundaryExtractor 클래스
**파일**: `include/grid/BoundaryExtractor.h`, `src/grid/BoundaryExtractor.cpp`

#### 6.1.1 6개 경계면 식별
```cpp
class BoundaryExtractor {
    // 각 경계면의 요소들
    std::vector<Element*> faceI0;   // i=0 면
    std::vector<Element*> faceIM;   // i=dimI-1 면
    std::vector<Element*> faceJ0;   // j=0 면
    std::vector<Element*> faceJN;   // j=dimJ-1 면
    std::vector<Element*> faceK0;   // k=0 면
    std::vector<Element*> faceKP;   // k=dimK-1 면

    void extractBoundaryFaces(const Mesh& mesh);
};
```

### 6.2 EdgeCalculator 클래스
**파일**: `include/grid/EdgeCalculator.h`, `src/grid/EdgeCalculator.cpp`

#### 6.2.1 8개 엣지 정의
```
굽혀진 육면체의 12개 엣지 중 주요 8개:
- Edge 1: (i=0, j=0) 방향 k축 엣지
- Edge 2: (i=M, j=0) 방향 k축 엣지
- Edge 3: (i=0, j=N) 방향 k축 엣지
- Edge 4: (i=M, j=N) 방향 k축 엣지
- Edge 5: (j=0, k=0) 방향 i축 엣지
- Edge 6: (j=N, k=0) 방향 i축 엣지
- Edge 7: (j=0, k=P) 방향 i축 엣지
- Edge 8: (j=N, k=P) 방향 i축 엣지
```

#### 6.2.2 구현
```cpp
struct EdgeInfo {
    double totalLength;
    std::vector<double> segmentLengths;
    Vector3D startPoint;
    Vector3D endPoint;
    std::vector<Vector3D> intermediatePoints;
};

class EdgeCalculator {
    EdgeInfo edges[12];  // 12개 엣지 정보

    void calculateAllEdges(const Mesh& mesh);
    EdgeInfo calculateEdge(const Mesh& mesh,
                          int fixedAxis1, int fixedValue1,
                          int fixedAxis2, int fixedValue2,
                          int varyingAxis);

    // 중립면 계산
    double getNeutralAxisPosition(int axis);

    // 변형률 계산: (외부 엣지 - 내부 엣지) / 중립 엣지
    double calculateStrain(int edgeIndex);
};
```

---

## Phase 7: 중립면 정돈 격자 생성

### 7.1 NeutralGridGenerator 클래스
**파일**: `include/grid/NeutralGridGenerator.h`, `src/grid/NeutralGridGenerator.cpp`

#### 7.1.1 중립 격자 개념
- 굽힘이 없는 직교 격자
- 각 축의 평균 크기를 사용
- 모든 요소가 동일한 크기의 정육면체/직육면체

#### 7.1.2 구현
```cpp
class NeutralGridGenerator {
    double avgSizeI, avgSizeJ, avgSizeK;  // 평균 요소 크기

    // 중립 크기 계산
    void calculateNeutralSizes(const Mesh& bentMesh,
                               const EdgeCalculator& ec);

    // 정돈된 격자 생성
    Mesh generateNeutralGrid(int dimI, int dimJ, int dimK);

    // 중립 격자의 노드 좌표 계산
    Vector3D getNeutralNodePosition(int i, int j, int k);
};
```

---

## Phase 8: 곡면 매개변수화 (Parametric Mapping)

### 8.1 ParametricMapper 클래스
**파일**: `include/mapper/ParametricMapper.h`, `src/mapper/ParametricMapper.cpp`

#### 8.1.1 매핑 함수 정의
굽혀진 격자를 매개변수 공간 (u,v,w) ∈ [0,1]³ 로 매핑
```cpp
class ParametricMapper {
    // 굽혀진 메시의 경계 정보
    const Mesh* bentMesh;
    int dimI, dimJ, dimK;

    // 매개변수 -> 물리 좌표 변환
    Vector3D paramToPhysical(double u, double v, double w);

    // Trilinear 보간 (8개 코너 사용)
    Vector3D trilinearInterp(double u, double v, double w);

    // Transfinite 보간 (12개 엣지 + 6개 면 사용)
    Vector3D transfiniteInterp(double u, double v, double w);
};
```

#### 8.1.2 Transfinite Interpolation 상세
```
P(u,v,w) =
  // 면 기여
  + (1-u)·F_i0(v,w) + u·F_iM(v,w)
  + (1-v)·F_j0(u,w) + v·F_jN(u,w)
  + (1-w)·F_k0(u,v) + w·F_kP(u,v)

  // 엣지 보정
  - (1-u)(1-v)·E_00w(w) - u(1-v)·E_M0w(w) - ...

  // 코너 보정
  + (1-u)(1-v)(1-w)·C_000 + ...
```

### 8.2 EdgeInterpolator 클래스
**파일**: `include/mapper/EdgeInterpolator.h`, `src/mapper/EdgeInterpolator.cpp`
```cpp
class EdgeInterpolator {
    std::vector<Vector3D> edgePoints;
    std::vector<double> arcLengths;

    // 엣지를 따라 보간
    Vector3D interpolate(double t);  // t ∈ [0,1]

    // 호 길이 기반 매개변수화
    void buildArcLengthParam(const std::vector<Vector3D>& points);
};
```

### 8.3 FaceInterpolator 클래스
**파일**: `include/mapper/FaceInterpolator.h`, `src/mapper/FaceInterpolator.cpp`
```cpp
class FaceInterpolator {
    // 면의 4개 경계 엣지
    EdgeInterpolator edges[4];

    // Coons patch 보간
    Vector3D interpolate(double s, double t);  // s,t ∈ [0,1]
};
```

---

## Phase 9: 비정렬 격자 처리

### 9.1 UnstructuredMeshAnalyzer 클래스
**파일**: `include/mapper/UnstructuredMeshAnalyzer.h`, `src/mapper/UnstructuredMeshAnalyzer.cpp`

#### 9.1.1 기능
```cpp
class UnstructuredMeshAnalyzer {
    // 바운딩 박스 계산
    void calculateBoundingBox(const Mesh& mesh);

    // 중립 격자와의 스케일 비교
    double getScaleFactor(const Mesh& unstructured,
                          const NeutralGridGenerator& neutral);

    // 정규화된 좌표 계산 (0~1 범위로 변환)
    Vector3D normalizeCoordinate(const Vector3D& pos);
};
```

---

## Phase 10: 최종 매핑 엔진

### 10.1 MeshRemapper 클래스
**파일**: `include/mapper/MeshRemapper.h`, `src/mapper/MeshRemapper.cpp`

#### 10.1.1 메인 매핑 알고리즘
```cpp
class MeshRemapper {
    const Mesh* bentStructured;      // 굽혀진 정렬 격자 (입력 1)
    const Mesh* flatUnstructured;    // 펴진 비정렬 격자 (입력 2)
    Mesh bentUnstructured;           // 굽혀진 비정렬 격자 (출력)

    ParametricMapper paramMapper;
    UnstructuredMeshAnalyzer unstructAnalyzer;

    // 메인 매핑 함수
    bool performMapping();

    // 단계별 처리
    void step1_AnalyzeBentMesh();
    void step2_BuildParametricSpace();
    void step3_NormalizeFlatMesh();
    void step4_MapNodes();
    void step5_ValidateResult();
};
```

#### 10.1.2 노드 매핑 상세
```cpp
void MeshRemapper::step4_MapNodes() {
    for (auto& [id, node] : flatUnstructured->nodes) {
        // 1. 펴진 좌표를 정규화 (0~1)
        Vector3D normalized = unstructAnalyzer.normalizeCoordinate(
            node.position);

        // 2. 정규화된 좌표를 굽혀진 공간으로 변환
        Vector3D mappedPos = paramMapper.paramToPhysical(
            normalized.x, normalized.y, normalized.z);

        // 3. 결과 저장
        bentUnstructured.nodes[id].position = mappedPos;
    }
}
```

---

## Phase 11: 유틸리티 클래스들

### 11.1 Logger 클래스
**파일**: `include/util/Logger.h`, `src/util/Logger.cpp`
```cpp
class Logger {
    static void info(const std::string& msg);
    static void warning(const std::string& msg);
    static void error(const std::string& msg);
    static void debug(const std::string& msg);
};
```

### 11.2 Timer 클래스
**파일**: `include/util/Timer.h`, `src/util/Timer.cpp`
```cpp
class Timer {
    void start();
    void stop();
    double getElapsedSeconds();
};
```

### 11.3 Validator 클래스
**파일**: `include/util/Validator.h`, `src/util/Validator.cpp`
```cpp
class Validator {
    // 메시 유효성 검사
    bool validateMesh(const Mesh& mesh);

    // 요소 품질 검사 (Jacobian 등)
    bool checkElementQuality(const Element& elem, const Mesh& mesh);

    // 결과 검증
    bool validateMapping(const Mesh& original, const Mesh& mapped);
};
```

---

## Phase 12: CLI 인터페이스 및 메인 프로그램

### 12.1 ArgumentParser 클래스
**파일**: `include/cli/ArgumentParser.h`, `src/cli/ArgumentParser.cpp`

```cpp
struct ProgramOptions {
    std::string bentMeshFile;        // 굽혀진 정렬 격자 (필수)
    std::string flatMeshFile;        // 펴진 비정렬 격자 (필수)
    std::string outputFile;          // 출력 파일 (필수)
    std::string neutralOutputFile;   // 중립 격자 출력 (선택)
    bool verbose;                    // 상세 출력
    bool showHelp;                   // 도움말 표시
    bool showVersion;                // 버전 표시
    bool validateOnly;               // 검증만 수행
    bool generateNeutral;            // 중립 격자 생성
};

class ArgumentParser {
public:
    bool parse(int argc, char* argv[]);
    ProgramOptions getOptions() const;
    void printUsage() const;
    void printVersion() const;
    std::string getErrorMessage() const;

private:
    ProgramOptions options;
    std::string errorMessage;
    bool validateOptions();
};
```

### 12.2 CLI 출력 포맷터
**파일**: `include/cli/ConsoleOutput.h`, `src/cli/ConsoleOutput.cpp`

```cpp
class ConsoleOutput {
public:
    // 크로스플랫폼 콘솔 출력
    static void printHeader();
    static void printProgress(const std::string& stage, int percent);
    static void printSuccess(const std::string& message);
    static void printError(const std::string& message);
    static void printWarning(const std::string& message);
    static void printInfo(const std::string& message);
    static void printStats(const MeshStats& stats);

    // 진행 표시 (크로스플랫폼)
    static void showProgressBar(int current, int total);

private:
    static bool supportsAnsiColors();
    static void setConsoleColor(int color);
    static void resetConsoleColor();
};
```

### 12.3 main.cpp (CLI 진입점)
```cpp
#include "cli/ArgumentParser.h"
#include "cli/ConsoleOutput.h"
#include "core/Platform.h"
// ... 기타 헤더

int main(int argc, char* argv[]) {
    // 1. 인자 파싱
    ArgumentParser parser;
    if (!parser.parse(argc, argv)) {
        ConsoleOutput::printError(parser.getErrorMessage());
        parser.printUsage();
        return 1;
    }

    ProgramOptions opts = parser.getOptions();

    if (opts.showHelp) {
        parser.printUsage();
        return 0;
    }

    if (opts.showVersion) {
        parser.printVersion();
        return 0;
    }

    // 2. 헤더 출력
    ConsoleOutput::printHeader();

    try {
        // 3. 파일 읽기
        ConsoleOutput::printInfo("Loading bent structured mesh: " + opts.bentMeshFile);
        KFileReader reader;
        Mesh bentStructured = reader.readFile(opts.bentMeshFile);
        ConsoleOutput::printSuccess("Loaded " + std::to_string(bentStructured.getNodeCount())
                                    + " nodes, " + std::to_string(bentStructured.getElementCount())
                                    + " elements");

        ConsoleOutput::printInfo("Loading flat unstructured mesh: " + opts.flatMeshFile);
        Mesh flatUnstructured = reader.readFile(opts.flatMeshFile);
        ConsoleOutput::printSuccess("Loaded " + std::to_string(flatUnstructured.getNodeCount())
                                    + " nodes, " + std::to_string(flatUnstructured.getElementCount())
                                    + " elements");

        // 4. 굽혀진 메시 분석
        ConsoleOutput::printInfo("Analyzing connectivity...");
        ConnectivityAnalyzer ca;
        ca.buildConnectivity(bentStructured);

        ConsoleOutput::printInfo("Assigning grid indices (i,j,k)...");
        StructuredGridIndexer indexer;
        indexer.assignIndices(bentStructured, ca);
        ConsoleOutput::printSuccess("Grid dimensions: "
                                    + std::to_string(indexer.getDimI()) + " x "
                                    + std::to_string(indexer.getDimJ()) + " x "
                                    + std::to_string(indexer.getDimK()));

        ConsoleOutput::printInfo("Calculating edge lengths...");
        EdgeCalculator edgeCalc;
        edgeCalc.calculateAllEdges(bentStructured);

        // 5. 중립 격자 생성 (선택적)
        if (opts.generateNeutral) {
            ConsoleOutput::printInfo("Generating neutral grid...");
            NeutralGridGenerator neutralGen;
            Mesh neutralMesh = neutralGen.generate(bentStructured, edgeCalc);

            KFileWriter writer;
            writer.writeFile(opts.neutralOutputFile, neutralMesh);
            ConsoleOutput::printSuccess("Neutral grid saved to: " + opts.neutralOutputFile);
        }

        // 6. 매핑 수행
        ConsoleOutput::printInfo("Performing mapping...");
        MeshRemapper remapper;
        remapper.setBentMesh(&bentStructured);
        remapper.setFlatMesh(&flatUnstructured);
        remapper.setProgressCallback([](int percent) {
            ConsoleOutput::showProgressBar(percent, 100);
        });

        if (!remapper.performMapping()) {
            ConsoleOutput::printError("Mapping failed: " + remapper.getErrorMessage());
            return 1;
        }

        // 7. 결과 검증
        ConsoleOutput::printInfo("Validating result...");
        Validator validator;
        if (!validator.validateMapping(flatUnstructured, remapper.getResult())) {
            ConsoleOutput::printWarning("Validation warnings: " + validator.getWarnings());
        }

        // 8. 결과 출력
        ConsoleOutput::printInfo("Writing output file: " + opts.outputFile);
        KFileWriter writer;
        writer.writeFile(opts.outputFile, remapper.getResult());

        ConsoleOutput::printSuccess("Mapping completed successfully!");
        ConsoleOutput::printStats(remapper.getStats());

        return 0;

    } catch (const std::exception& e) {
        ConsoleOutput::printError(std::string("Fatal error: ") + e.what());
        return 1;
    }
}
```

### 12.4 CLI 사용법

```
KooRemapper - Structured to Unstructured Mesh Mapper v1.0.0

Usage:
  KooRemapper [options] <bent_mesh.k> <flat_mesh.k> <output.k>

Required Arguments:
  bent_mesh.k       Bent structured hexahedral mesh (reference)
  flat_mesh.k       Flat unstructured mesh to be mapped
  output.k          Output file for mapped mesh

Options:
  -h, --help        Show this help message
  -v, --version     Show version information
  --verbose         Enable verbose output
  --validate-only   Only validate input files, don't perform mapping
  --neutral <file>  Also generate and save neutral grid to <file>

Examples:
  KooRemapper bent.k flat.k output.k
  KooRemapper --verbose bent.k flat.k output.k
  KooRemapper --neutral neutral.k bent.k flat.k output.k

Cross-Platform Support:
  Windows:  KooRemapper.exe bent.k flat.k output.k
  Linux:    ./KooRemapper bent.k flat.k output.k
  macOS:    ./KooRemapper bent.k flat.k output.k
```

---

## Phase 13: 구현 순서 (세부 단계)

### Stage 1: 기본 인프라 및 크로스플랫폼 설정 (Phase 1-2)
1. 프로젝트 디렉토리 구조 생성
2. CMakeLists.txt 작성 (크로스플랫폼 설정 포함)
3. CMakePresets.json 작성 (Windows/Linux/macOS 프리셋)
4. Platform.h 플랫폼 추상화 레이어 구현
5. Platform.cpp 플랫폼별 구현 (조건부 컴파일)
6. 빌드 스크립트 작성 (build_windows.bat, build_linux.sh, build_macos.sh)
7. Vector3D 클래스 구현
8. Node 클래스 구현
9. Element 클래스 구현
10. Mesh 클래스 구현
11. 기본 단위 테스트 작성
12. 크로스플랫폼 빌드 테스트 (CI 설정 선택적)

### Stage 2: 파서 (Phase 3)
13. K-file 포맷 분석 및 문서화
14. KFileReader 기본 구조 구현
15. 크로스플랫폼 파일 경로 처리 (슬래시/백슬래시)
16. NODE 섹션 파싱 구현
17. ELEMENT_SOLID 섹션 파싱 구현
18. 줄바꿈 처리 (CRLF/LF 호환)
19. KFileWriter 구현
20. 파서 테스트 (예제 파일로 읽고 쓰기)

### Stage 3: 연결성 분석 (Phase 4)
21. Face 구조체 및 해시 함수 구현
22. 면 공유 맵 구축 구현
23. 요소 인접 관계 계산 구현
24. 연결성 분석 테스트

### Stage 4: 격자 인덱싱 (Phase 5)
25. 코너 요소 탐지 알고리즘 구현
26. 초기 방향 결정 로직 구현
27. BFS 인덱스 전파 구현
28. 축 재정렬 로직 구현 (z축 최소, x축 최대)
29. 인덱싱 테스트

### Stage 5: 경계 및 엣지 (Phase 6)
30. 경계면 추출 구현 (i=0, i=M, j=0, j=N, k=0, k=P)
31. 12개 엣지 포인트 수집 구현
32. 엣지 길이 계산 구현
33. 중립면 위치 계산 구현
34. 변형률 계산 구현

### Stage 6: 중립 격자 (Phase 7)
35. 평균 요소 크기 계산 구현
36. 중립 격자 노드 생성 구현
37. 중립 격자 요소 생성 구현
38. 중립 격자 K-file 출력 테스트

### Stage 7: 매개변수 매핑 (Phase 8)
39. EdgeInterpolator 구현
40. 호 길이 매개변수화 구현
41. FaceInterpolator 구현 (Coons Patch)
42. ParametricMapper trilinear 보간 구현
43. ParametricMapper transfinite 보간 구현
44. 매개변수 매핑 테스트

### Stage 8: 비정렬 격자 처리 (Phase 9)
45. 바운딩 박스 계산 구현
46. 스케일 팩터 계산 구현
47. 좌표 정규화 구현

### Stage 9: 최종 매핑 (Phase 10)
48. MeshRemapper 기본 구조 구현
49. 분석 단계 구현
50. 노드 매핑 구현
51. 요소 복사 구현
52. 결과 검증 구현

### Stage 10: 유틸리티 (Phase 11)
53. Logger 구현 (크로스플랫폼 콘솔 출력)
54. Timer 구현 (std::chrono 사용)
55. Validator 구현

### Stage 11: CLI 인터페이스 (Phase 12)
56. ArgumentParser 구현
57. ConsoleOutput 구현 (ANSI 색상 지원 + Windows 호환)
58. 진행률 표시 기능 구현
59. main.cpp 구현
60. CLI 도움말 및 버전 정보 구현

### Stage 12: 예제 메시 생성기 (Phase 17)
61. ExampleMeshGenerator 기본 구조 구현
62. generateFlatGrid() - 평평한 정렬 격자 생성
63. TeardropParams 구조체 및 변환 함수 구현
64. TeardropCenterLine (Bezier 곡선) 구현
65. generateTeardropBent() - 물방울 형상 변환
66. generateArcBent() - 원호 굽힘 변환
67. generateSBent() - S자 굽힘 변환
68. UnstructuredParams 및 generateUnstructuredFlat() 구현
69. 구멍/노이즈 추가 기능 구현
70. --generate-example CLI 옵션 통합

### Stage 13: 테스트 및 마무리
71. 단위 테스트 완성 (각 모듈별)
72. 통합 테스트 작성
73. Windows에서 빌드 및 테스트
74. Linux에서 빌드 및 테스트
75. macOS에서 빌드 및 테스트
76. 예제 K-file 자동 생성 스크립트
77. README.md 작성
78. CHANGELOG.md 작성
79. 배포 패키지 생성 (플랫폼별 바이너리)

---

## Phase 14: 수학적 세부사항

### 14.1 Transfinite Interpolation 공식

3D Transfinite Interpolation (Gordon-Hall 방법):

```
P(u,v,w) = P_faces - P_edges + P_corners

P_faces = (1-u)·S₁(v,w) + u·S₂(v,w)
        + (1-v)·S₃(u,w) + v·S₄(u,w)
        + (1-w)·S₅(u,v) + w·S₆(u,v)

P_edges = (1-u)(1-v)·C₁(w) + u(1-v)·C₂(w) + (1-u)v·C₃(w) + uv·C₄(w)
        + (1-u)(1-w)·C₅(v) + u(1-w)·C₆(v) + (1-u)w·C₇(v) + uw·C₈(v)
        + (1-v)(1-w)·C₉(u) + v(1-w)·C₁₀(u) + (1-v)w·C₁₁(u) + vw·C₁₂(u)

P_corners = (1-u)(1-v)(1-w)·P₀₀₀ + u(1-v)(1-w)·P₁₀₀ + ...
            (8개 코너 항)
```

### 14.2 Jacobian 기반 품질 검사

```cpp
double calculateJacobian(const Element& elem, const Mesh& mesh) {
    // 요소 중심에서의 Jacobian 계산
    // J = |∂x/∂ξ  ∂x/∂η  ∂x/∂ζ|
    //     |∂y/∂ξ  ∂y/∂η  ∂y/∂ζ|
    //     |∂z/∂ξ  ∂z/∂η  ∂z/∂ζ|

    // 양수: 유효한 요소
    // 음수: 뒤집힌 요소 (오류)
}
```

---

## Phase 15: 에러 처리 및 엣지 케이스

### 15.1 예상되는 문제 상황
1. **비일관적 연결성**: 일부 요소가 격자와 연결되지 않음
2. **다중 코너**: 여러 개의 코너 요소 후보
3. **불완전한 격자**: 일부 위치에 요소 누락
4. **스케일 불일치**: 펴진 격자와 굽힌 격자 크기 차이
5. **음수 Jacobian**: 매핑 후 뒤집힌 요소 발생

### 15.2 해결 방안
```cpp
class ErrorHandler {
    void handleDisconnectedElements(Mesh& mesh);
    void handleMultipleCorners(const std::vector<int>& corners);
    void handleIncompleteGrid(Mesh& mesh);
    void handleScaleMismatch(double factor);
    void handleNegativeJacobian(Element& elem);
};
```

---

## 부록 A: K-File 포맷 참조

### NODE 섹션
```
*NODE
$     nid              x              y              z
        1   0.000000E+00   0.000000E+00   0.000000E+00
        2   1.000000E+00   0.000000E+00   0.000000E+00
```

### ELEMENT_SOLID 섹션
```
*ELEMENT_SOLID
$    eid    pid     n1     n2     n3     n4     n5     n6     n7     n8
       1      1      1      2      3      4      5      6      7      8
```

---

## Phase 17: 예제 메시 생성기 (Example Generator)

### 17.1 ExampleMeshGenerator 클래스
**파일**: `include/generator/ExampleMeshGenerator.h`, `src/generator/ExampleMeshGenerator.cpp`

```cpp
class ExampleMeshGenerator {
public:
    // 기본 직육면체 격자 생성
    static Mesh generateFlatGrid(int dimI, int dimJ, int dimK,
                                  double sizeX, double sizeY, double sizeZ);

    // 물방울 형태 굽힘 변환
    static Mesh generateTeardropBent(int dimI, int dimJ, int dimK,
                                      double length, double width, double thickness,
                                      const TeardropParams& params);

    // 원호 굽힘 (단순)
    static Mesh generateArcBent(int dimI, int dimJ, int dimK,
                                 double bendAngle, double bendRadius);

    // S자 굽힘
    static Mesh generateSBent(int dimI, int dimJ, int dimK,
                               double amplitude, double wavelength);

    // 비정렬 격자 생성 (구멍, 불규칙 등)
    static Mesh generateUnstructuredFlat(int approxElements,
                                          double sizeX, double sizeY, double sizeZ,
                                          const UnstructuredParams& params);
};
```

### 17.2 물방울(Teardrop) 변환 함수

물방울 형상은 한쪽이 둥글고 반대쪽이 뾰족한 형태입니다.

```cpp
struct TeardropParams {
    double headRadius;      // 둥근 머리 부분 반경
    double tailSharpness;   // 꼬리 부분 뾰족함 (0~1)
    double bendIntensity;   // 굽힘 강도
    double twistAngle;      // 비틀림 각도 (선택적)
    Vector3D bendAxis;      // 굽힘 축 방향
};

// 물방울 변환 수학 함수
Vector3D teardropTransform(const Vector3D& flatPos,
                           double normalizedX,  // 0~1 (길이 방향)
                           const TeardropParams& params) {
    // 1. 길이 방향(x)에 따른 단면 스케일 계산
    //    - x=0 (머리): 원형 단면
    //    - x=1 (꼬리): 점으로 수렴
    double t = normalizedX;
    double scale = calculateTeardropRadius(t, params);

    // 2. 굽힘 곡률 계산 (물방울 중심선)
    //    머리 부분: 큰 곡률반경 (완만)
    //    꼬리 부분: 작은 곡률반경 (급격)
    double curvature = calculateTeardropCurvature(t, params);

    // 3. 좌표 변환
    Vector3D result;
    // ... 변환 로직
    return result;
}

// 물방울 반경 함수 (단면 크기)
double calculateTeardropRadius(double t, const TeardropParams& params) {
    // 카디오이드(심장형) 기반 공식
    // r(t) = headRadius * (1 - t^tailSharpness)
    // 또는 더 복잡한 Bezier 기반 공식
    double r = params.headRadius * pow(1.0 - t, params.tailSharpness);
    return std::max(r, 0.001);  // 최소 반경 보장
}

// 물방울 중심선 곡률
double calculateTeardropCurvature(double t, const TeardropParams& params) {
    // 머리 부분 (t=0): 완만한 곡률
    // 꼬리 부분 (t=1): 급격한 곡률
    return params.bendIntensity * (1.0 + t * 2.0);
}
```

### 17.3 물방울 형상 상세 변환

```cpp
Mesh ExampleMeshGenerator::generateTeardropBent(
    int dimI, int dimJ, int dimK,
    double length, double width, double thickness,
    const TeardropParams& params)
{
    // 1. 먼저 평평한 격자 생성
    Mesh flatMesh = generateFlatGrid(dimI, dimJ, dimK,
                                      length, width, thickness);

    // 2. 각 노드에 물방울 변환 적용
    Mesh bentMesh;
    bentMesh.elements = flatMesh.elements;  // 요소 연결성은 동일

    for (auto& [id, node] : flatMesh.nodes) {
        // 정규화된 좌표 (0~1)
        double u = node.position.x / length;
        double v = (node.position.y / width) + 0.5;   // -0.5~0.5 -> 0~1
        double w = (node.position.z / thickness) + 0.5;

        // 물방울 변환
        Vector3D newPos = applyTeardropTransform(u, v, w, params, length);

        Node newNode;
        newNode.id = id;
        newNode.position = newPos;
        bentMesh.nodes[id] = newNode;
    }

    return bentMesh;
}

Vector3D applyTeardropTransform(double u, double v, double w,
                                 const TeardropParams& params,
                                 double length) {
    // u: 길이 방향 (0=머리, 1=꼬리)
    // v: 폭 방향 (-0.5~0.5 정규화됨)
    // w: 두께 방향 (-0.5~0.5 정규화됨)

    // 1. 물방울 중심선 계산 (3D 곡선)
    //    Bezier 또는 Catmull-Rom 스플라인 사용
    Vector3D centerLine = calculateTeardropCenterLine(u, params, length);

    // 2. 해당 위치에서의 단면 좌표계 (Frenet-Serret frame)
    Vector3D tangent = calculateTeardropTangent(u, params);
    Vector3D normal = calculateTeardropNormal(u, params);
    Vector3D binormal = tangent.cross(normal).normalized();

    // 3. 단면 스케일 (물방울 형상)
    double radius = calculateTeardropRadius(u, params);

    // 4. 단면 내 오프셋
    double localY = (v - 0.5) * radius * 2.0;  // 폭 방향
    double localZ = (w - 0.5) * radius * 2.0;  // 두께 방향

    // 5. 최종 위치 = 중심선 + 로컬 오프셋
    Vector3D result = centerLine
                    + normal * localY
                    + binormal * localZ;

    return result;
}
```

### 17.4 물방울 중심선 (Bezier Curve)

```cpp
// 3차 Bezier 곡선으로 물방울 중심선 정의
class TeardropCenterLine {
    Vector3D P0, P1, P2, P3;  // 제어점

public:
    TeardropCenterLine(double length, const TeardropParams& params) {
        // P0: 시작점 (머리 중심)
        P0 = Vector3D(0, 0, 0);

        // P1: 머리 부분 제어점 (완만한 시작)
        P1 = Vector3D(length * 0.3, params.headRadius * 0.5, 0);

        // P2: 꼬리 부분 제어점 (급격한 굽힘)
        P2 = Vector3D(length * 0.7, params.headRadius * params.bendIntensity, 0);

        // P3: 끝점 (꼬리 끝)
        P3 = Vector3D(length, 0, 0);
    }

    Vector3D evaluate(double t) const {
        double t2 = t * t;
        double t3 = t2 * t;
        double mt = 1.0 - t;
        double mt2 = mt * mt;
        double mt3 = mt2 * mt;

        return P0 * mt3
             + P1 * (3.0 * mt2 * t)
             + P2 * (3.0 * mt * t2)
             + P3 * t3;
    }

    Vector3D tangent(double t) const {
        double t2 = t * t;
        double mt = 1.0 - t;
        double mt2 = mt * mt;

        Vector3D deriv = (P1 - P0) * (3.0 * mt2)
                       + (P2 - P1) * (6.0 * mt * t)
                       + (P3 - P2) * (3.0 * t2);
        return deriv.normalized();
    }
};
```

### 17.5 비정렬 격자 생성 (테스트용)

```cpp
struct UnstructuredParams {
    bool addHoles;           // 구멍 추가 여부
    int numHoles;            // 구멍 개수
    double holeRadius;       // 구멍 반경
    bool irregularBoundary;  // 불규칙 경계
    double noiseAmplitude;   // 노드 위치 노이즈
};

Mesh ExampleMeshGenerator::generateUnstructuredFlat(
    int approxElements,
    double sizeX, double sizeY, double sizeZ,
    const UnstructuredParams& params)
{
    Mesh mesh;

    // 1. 기본 정렬 격자 생성
    int nx = static_cast<int>(cbrt(approxElements * sizeX / sizeY / sizeZ));
    int ny = static_cast<int>(nx * sizeY / sizeX);
    int nz = static_cast<int>(nx * sizeZ / sizeX);

    mesh = generateFlatGrid(nx, ny, nz, sizeX, sizeY, sizeZ);

    // 2. 노드에 약간의 노이즈 추가 (불규칙성)
    if (params.noiseAmplitude > 0) {
        std::mt19937 rng(42);  // 재현 가능한 랜덤
        std::uniform_real_distribution<double> dist(-1.0, 1.0);

        double dx = sizeX / nx * params.noiseAmplitude;
        double dy = sizeY / ny * params.noiseAmplitude;
        double dz = sizeZ / nz * params.noiseAmplitude;

        for (auto& [id, node] : mesh.nodes) {
            // 경계 노드는 유지
            if (!isOnBoundary(node, sizeX, sizeY, sizeZ)) {
                node.position.x += dist(rng) * dx;
                node.position.y += dist(rng) * dy;
                node.position.z += dist(rng) * dz;
            }
        }
    }

    // 3. 구멍 추가 (해당 위치 요소 제거)
    if (params.addHoles) {
        addHolesToMesh(mesh, params.numHoles, params.holeRadius,
                       sizeX, sizeY, sizeZ);
    }

    return mesh;
}
```

### 17.6 예제 파일 생성 CLI 옵션

```
KooRemapper --generate-example <type> <output.k> [options]

Example Types:
  flat              Flat structured grid
  teardrop          Teardrop-bent structured grid
  arc               Arc-bent structured grid
  s-curve           S-curve bent structured grid
  unstructured      Unstructured flat grid (with optional holes)

Options:
  --dims <I> <J> <K>      Grid dimensions (default: 20 10 3)
  --size <X> <Y> <Z>      Physical size (default: 100 50 15)
  --bend-angle <deg>      Bend angle for arc (default: 90)
  --sharpness <0-1>       Teardrop tail sharpness (default: 0.7)
  --noise <0-1>           Node position noise for unstructured (default: 0.1)
  --holes <N>             Number of holes for unstructured (default: 0)

Examples:
  KooRemapper --generate-example teardrop bent_teardrop.k --dims 30 15 4
  KooRemapper --generate-example flat flat_grid.k --dims 30 15 4
  KooRemapper --generate-example unstructured unstr.k --dims 30 15 4 --noise 0.2 --holes 3
```

### 17.7 예제 생성 시각화 (ASCII)

```
물방울(Teardrop) 형상 단면도:

      머리 (t=0)                      꼬리 (t=1)
    ___________                           /
   /           \                         /
  |      O      |  →  →  →  →  →  →  → •
   \___________/                         \
                                          \

상단 뷰:
  ==========================================
  ||                                      /
  ||    [넓은 머리]      [점점 좁아짐]   •
  ||                                      \
  ==========================================

3D 격자가 이 형상을 따라 변형됨
```

---

## 부록 B: 테스트 케이스

### B.1 단순 직육면체 (10x5x2)
- 100개 요소
- 굽힘 없음
- **생성 명령**: `KooRemapper --generate-example flat flat_10x5x2.k --dims 10 5 2`

### B.2 단순 굽힘 (10x5x2, 90도 굽힘)
- z축 주위로 90도 굽힘
- 외부 엣지가 내부보다 긴 것 확인
- **생성 명령**: `KooRemapper --generate-example arc arc_90deg.k --dims 10 5 2 --bend-angle 90`

### B.3 복합 굽힘 (20x10x3, S자 굽힘)
- 양방향 굽힘
- 매핑 정확도 검증
- **생성 명령**: `KooRemapper --generate-example s-curve scurve.k --dims 20 10 3`

### B.4 물방울 형상 (30x15x4)
- 한쪽이 둥글고 반대쪽이 뾰족한 형태
- 실제 사용 사례와 유사
- **생성 명령**: `KooRemapper --generate-example teardrop teardrop.k --dims 30 15 4 --sharpness 0.7`

### B.5 비정렬 격자 + 물방울 매핑 테스트
- 펴진 비정렬 격자 생성
- 물방울 형상으로 매핑
- **생성 명령**:
  ```bash
  KooRemapper --generate-example teardrop bent_ref.k --dims 30 15 4
  KooRemapper --generate-example unstructured flat_unstr.k --dims 30 15 4 --noise 0.15
  KooRemapper bent_ref.k flat_unstr.k output_bent_unstr.k
  ```

---

## Phase 16: 크로스플랫폼 세부 구현

### 16.1 Windows 특수 처리
```cpp
// src/core/Platform_Windows.cpp
#ifdef PLATFORM_WINDOWS
#include <windows.h>

namespace Platform {
    std::string getExecutablePath() {
        char buffer[MAX_PATH];
        GetModuleFileNameA(NULL, buffer, MAX_PATH);
        return std::string(buffer);
    }

    bool enableAnsiColors() {
        // Windows 10 1511 이상에서 ANSI 색상 지원
        HANDLE hOut = GetStdHandle(STD_OUTPUT_HANDLE);
        DWORD dwMode = 0;
        GetConsoleMode(hOut, &dwMode);
        dwMode |= ENABLE_VIRTUAL_TERMINAL_PROCESSING;
        return SetConsoleMode(hOut, dwMode);
    }
}
#endif
```

### 16.2 Linux/macOS 처리
```cpp
// src/core/Platform_Unix.cpp
#if defined(PLATFORM_LINUX) || defined(PLATFORM_MACOS)
#include <unistd.h>
#include <limits.h>
#include <sys/stat.h>

namespace Platform {
    std::string getExecutablePath() {
        char buffer[PATH_MAX];
        #ifdef PLATFORM_LINUX
        ssize_t len = readlink("/proc/self/exe", buffer, sizeof(buffer)-1);
        #else  // macOS
        uint32_t size = sizeof(buffer);
        _NSGetExecutablePath(buffer, &size);
        ssize_t len = strlen(buffer);
        #endif
        if (len != -1) {
            buffer[len] = '\0';
            return std::string(buffer);
        }
        return "";
    }

    bool enableAnsiColors() {
        // Unix 계열은 기본적으로 ANSI 지원
        return isatty(STDOUT_FILENO);
    }
}
#endif
```

### 16.3 파일 I/O 크로스플랫폼 처리
```cpp
// 줄바꿈 정규화
std::string normalizeLineEndings(const std::string& content) {
    std::string result;
    result.reserve(content.size());
    for (size_t i = 0; i < content.size(); ++i) {
        if (content[i] == '\r') {
            if (i + 1 < content.size() && content[i + 1] == '\n') {
                continue;  // CRLF -> LF
            }
            result += '\n';  // CR -> LF
        } else {
            result += content[i];
        }
    }
    return result;
}

// 경로 정규화
std::string normalizePath(const std::string& path) {
    std::string result = path;
    #ifdef PLATFORM_WINDOWS
    std::replace(result.begin(), result.end(), '/', '\\');
    #else
    std::replace(result.begin(), result.end(), '\\', '/');
    #endif
    return result;
}
```

---

## 부록 C: 빌드 스크립트

### C.1 Windows (build_windows.bat)
```batch
@echo off
echo Building KooRemapper for Windows...

if not exist build\windows mkdir build\windows
cd build\windows

cmake -G "Visual Studio 17 2022" -A x64 ..\..
cmake --build . --config Release

echo Build complete: build\windows\Release\KooRemapper.exe
pause
```

### C.2 Linux (build_linux.sh)
```bash
#!/bin/bash
echo "Building KooRemapper for Linux..."

mkdir -p build/linux
cd build/linux

cmake -DCMAKE_BUILD_TYPE=Release ../..
make -j$(nproc)

echo "Build complete: build/linux/KooRemapper"
```

### C.3 macOS (build_macos.sh)
```bash
#!/bin/bash
echo "Building KooRemapper for macOS..."

mkdir -p build/macos
cd build/macos

cmake -DCMAKE_BUILD_TYPE=Release ../..
make -j$(sysctl -n hw.ncpu)

echo "Build complete: build/macos/KooRemapper"
```

---

## 구현 완료 체크리스트

### 기본 인프라
- [ ] 1. 프로젝트 디렉토리 구조 생성
- [ ] 2. CMakeLists.txt (크로스플랫폼)
- [ ] 3. CMakePresets.json
- [ ] 4-5. Platform 추상화 레이어
- [ ] 6. 빌드 스크립트 (Windows/Linux/macOS)

### 핵심 클래스
- [ ] 7. Vector3D 클래스
- [ ] 8. Node 클래스
- [ ] 9. Element 클래스
- [ ] 10. Mesh 클래스

### K-File 파서
- [ ] 13-18. KFileReader (NODE, ELEMENT_SOLID)
- [ ] 19. KFileWriter

### 격자 분석
- [ ] 21-24. ConnectivityAnalyzer
- [ ] 25-29. StructuredGridIndexer
- [ ] 30-34. EdgeCalculator

### 격자 생성 및 매핑
- [ ] 35-38. NeutralGridGenerator
- [ ] 39-44. ParametricMapper (EdgeInterpolator, FaceInterpolator)
- [ ] 45-47. UnstructuredMeshAnalyzer
- [ ] 48-52. MeshRemapper

### 유틸리티 및 CLI
- [ ] 53. Logger
- [ ] 54. Timer
- [ ] 55. Validator
- [ ] 56-60. CLI 인터페이스

### 예제 메시 생성기
- [ ] 61-62. ExampleMeshGenerator 기본 구조 + generateFlatGrid
- [ ] 63-64. TeardropParams + TeardropCenterLine (Bezier)
- [ ] 65. generateTeardropBent() 물방울 형상 변환
- [ ] 66-67. generateArcBent() + generateSBent()
- [ ] 68-69. UnstructuredParams + 구멍/노이즈 기능
- [ ] 70. --generate-example CLI 옵션 통합

### 테스트 및 마무리
- [ ] 71-72. 단위/통합 테스트
- [ ] 73-75. 크로스플랫폼 빌드 검증
- [ ] 76. 예제 K-file 자동 생성 스크립트
- [ ] 77-78. 문서화 (README, CHANGELOG)
- [ ] 79. 배포 패키지

---

## 총 구현 단계: 79개

**예상 파일 수**: 약 45개 (헤더 + 소스)
**주요 클래스**: 17개 (ExampleMeshGenerator, TeardropCenterLine 추가)
**지원 플랫폼**: Windows, Linux, macOS
**예제 형상**: Flat, Teardrop, Arc, S-Curve, Unstructured
