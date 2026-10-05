#pragma once

#include <array>
#include <vector>
#include <utility>

// Knowledge graph (lat.md):
//   @lat: [[modules/core]]

namespace KooRemapper {

/**
 * Element type enumeration
 */
enum class ElementType {
    HEX8,       // 8-node hexahedron
    HEX20,      // 20-node hexahedron
    TET4,       // 4-node tetrahedron
    TET10,      // 10-node tetrahedron
    PENTA6,     // 6-node pentahedron (wedge/prism), stored as degenerate HEX8: n3=n4, n7=n8
    QUAD4,      // 4-node shell (quad)
    UNKNOWN
};

/**
 * 요소 위상(면·모서리)의 **단일 정본**.
 *
 * 왜 한 곳인가 (실측 2026-10-05). 같은 지식이 리포에 **네 벌**로 흩어져 서로 달랐다 —
 *   ① 아래 `Element` 의 고정 **육면체** 표 (소비자 11곳)
 *   ② `src/commands/surfview.cpp` 의 `facesFor()` — 종류별, 맞다
 *   ③ `src/commands/section.cpp` 의 `edgesFor()` — 종류별 모서리, 맞다
 *   ④ `src/assembly/ModelAssembler.cpp` 의 손으로 적은 사면체 면 표 — 종류별, 맞다
 * ①이 **틀린다.** TET4 는 LS-DYNA 관례로 `[n0,n1,n2,n3,n3,n3,n3,n3]` 로 저장되므로 육면체 표를
 * 쓰면 면 0 `{0,3,7,4}` → `[n0,n3,n3,n3]`(선), 면 3 `{3,2,6,7}` → `[n3,n2,n3,n3]`(선),
 * 면 4 `{0,1,2,3}` → **네 꼭짓점을 모두 지나는 사변형**(사면체에 없는 면)이 되고, 옛
 * `isFaceDegenerate`(= `fn[0]==fn[1] && fn[2]==fn[3]`)는 **그 셋을 모두 통과시켰다.**
 * 그래서 TET4 한 개가 자유면 **5개**(가짜 3개)를 내고 **진짜 면 둘이 빠졌다**
 * (실측: `extract-surface` 가 `1 2 3 4`/`1 2 4 4`/`1 4 4 4`/`2 3 4 4`/`4 3 4 4` 를 냈다).
 *
 * 감김도 ①만 어긋났다. 단위 육면체로 재면 ①은 6면 중 **3면(f0·f3·f4)이 안쪽**이고 ②는 6면 모두
 * 바깥이다. 두 표의 **면 집합은 같다.** 그러므로 ②의 감김(바깥 일관)으로 모은다 — ①의 감김에
 * 기대는 소비자는 있을 수 없다(일관되지 않으므로).
 *
 * 삼각형 면은 `n == 3` 이고 `v[3]` 은 쓰지 않는다. 절점 ID 로 바꿀 때는 LS-DYNA 관례대로
 * 마지막을 반복해(`[a,b,c,c]`) 축퇴 사변형으로 적는다 — 그것이 덱에서 TRIA3 다.
 *
 * ⚠ **여기 소관이 아닌 것** — '마주보는 면 **쌍**'(`ModelAssembler` 의 `FacePairDef`,
 * `merge.cpp` 의 `facePairs`)은 이 표로 바꾸면 **안 된다.** 그쪽은 `botLocal[i]` 와
 * `topLocal[i]` 가 **모서리로 대응**해야 하는 구조이고(압출 방향 판정), 바깥 감김으로 바꾸면
 * 아래·위 면의 순회 방향이 서로 반대가 되어 그 대응이 깨진다. 표가 비슷해 보여도 다른 지식이다.
 */
namespace topo {

struct Face {
    int n;        // 실제 절점 수 — 3(삼각형) 또는 4(사변형)
    int v[4];     // 국소 절점 인덱스. n == 3 이면 v[3] 은 의미 없다
};

// 종류별 면 표. **바깥 감김으로 일관**된다(단위 도형으로 검증했다).
inline const std::vector<Face>& facesOf(ElementType t) {
    // ★육면체 표는 **옛 순서와 각 면의 시작 꼭짓점을 그대로 두고 순회 방향만** 뒤집었다
    //   (면 0·3·4). 둘 다 지켜야 하는 이유가 실측으로 각각 있다.
    //   ① **순서** — `getFaceAxis`/`getFaceDirection`/`getOppositeFace` 와
    //      `StructuredGridIndexer` 가 면 인덱스를 **산술**한다(`axis = fi/2`,
    //      `dir = fi%2`). 순서가 (i-,i+,j-,j+,k-,k+) 라는 규약이 코드에 박혀 있어서
    //      순서를 바꾸면 격자 좌표 전파가 **조용히** 틀린다.
    //   ② **시작 꼭짓점** — `modelmeta` 의 부피는 사변형을 `v0-v2` 대각으로 쪼갠다.
    //      시작점을 돌리면 대각이 바뀌고, 면이 평면이 아닐 때 값이 달라진다
    //      (실측 `examples/bendtwist/bendtwist_bent.k` 31200.37 → 31995.26, +2.55%).
    //      시작점을 두고 뒤집으면 `v0`·`v2` 가 그대로이므로 대각이 보존된다.
    static const std::vector<Face> hex = {
        {4, {0, 4, 7, 3}},   // i-  (옛 {0,3,7,4} 를 시작점 고정 역순 — 대각 0-7 보존)
        {4, {1, 2, 6, 5}},   // i+  (이미 바깥)
        {4, {0, 1, 5, 4}},   // j-  (이미 바깥)
        {4, {3, 7, 6, 2}},   // j+  (옛 {3,2,6,7} 역순 — 대각 3-6 보존)
        {4, {0, 3, 2, 1}},   // k-  (옛 {0,1,2,3} 역순 — 대각 0-2 보존)
        {4, {4, 5, 6, 7}}};  // k+  (이미 바깥)
    static const std::vector<Face> tet = {
        {3, {0, 2, 1, 0}}, {3, {0, 1, 3, 0}}, {3, {1, 2, 3, 0}}, {3, {2, 0, 3, 0}}};
    // PENTA6 는 축퇴 육면체로 저장된다(n2 == n3, n6 == n7) — 유일 코너는 0,1,2,4,5,6 이다.
    // 사변형의 대각도 옛 육면체 경로와 맞췄다(0-6 · 1-6 · 0-5) — 같은 이유 ②다.
    static const std::vector<Face> wedge = {
        {3, {0, 2, 1, 0}}, {3, {4, 5, 6, 0}},
        {4, {0, 1, 5, 4}}, {4, {1, 2, 6, 5}}, {4, {0, 4, 6, 2}}};
    static const std::vector<Face> quad = {{4, {0, 1, 2, 3}}};
    static const std::vector<Face> none = {};
    switch (t) {
        case ElementType::TET4:   return tet;
        case ElementType::TET10:  return tet;      // 코너만 쓴다 — 중간절점은 그림에 쓰지 않는다
        case ElementType::PENTA6: return wedge;
        case ElementType::QUAD4:  return quad;
        case ElementType::HEX8:   return hex;
        case ElementType::HEX20:  return hex;      // 코너가 앞 8칸이다
        case ElementType::UNKNOWN: return none;
    }
    return hex;
}

// 종류별 모서리 표. 평면 절단은 면이 아니라 **모서리**∩평면으로 푼다(1차 방정식이다).
inline const std::vector<std::pair<int, int>>& edgesOf(ElementType t) {
    static const std::vector<std::pair<int, int>> hex = {
        {0,1},{1,2},{2,3},{3,0},{4,5},{5,6},{6,7},{7,4},{0,4},{1,5},{2,6},{3,7}};
    static const std::vector<std::pair<int, int>> tet = {
        {0,1},{1,2},{2,0},{0,3},{1,3},{2,3}};
    static const std::vector<std::pair<int, int>> wedge = {
        {0,1},{1,2},{2,0},{4,5},{5,6},{6,4},{0,4},{1,5},{2,6}};
    static const std::vector<std::pair<int, int>> quad = {{0,1},{1,2},{2,3},{3,0}};
    static const std::vector<std::pair<int, int>> none = {};
    switch (t) {
        case ElementType::TET4:   return tet;
        case ElementType::TET10:  return tet;
        case ElementType::PENTA6: return wedge;
        case ElementType::QUAD4:  return quad;
        case ElementType::HEX8:   return hex;
        case ElementType::HEX20:  return hex;
        case ElementType::UNKNOWN: return none;
    }
    return hex;
}

}  // namespace topo

/**
 * Element class representing an 8-node hexahedral element
 *
 * Node numbering convention (LS-DYNA):
 *
 *        7 -------- 6
 *       /|         /|
 *      / |        / |
 *     4 -------- 5  |
 *     |  |       |  |
 *     |  3 ------|- 2
 *     | /        | /
 *     |/         |/
 *     0 -------- 1
 *
 * Face definitions:
 *   Face 0 (i-): nodes 0,3,7,4
 *   Face 1 (i+): nodes 1,2,6,5
 *   Face 2 (j-): nodes 0,1,5,4
 *   Face 3 (j+): nodes 3,2,6,7
 *   Face 4 (k-): nodes 0,1,2,3
 *   Face 5 (k+): nodes 4,5,6,7
 */
class Element {
public:
    static constexpr int NUM_NODES = 8;
    static constexpr int NUM_FACES = 6;
    static constexpr int NODES_PER_FACE = 4;

    int id;                         // Element ID (from k-file)
    int partId;                     // Part ID
    std::array<int, NUM_NODES> nodeIds;  // Node IDs (8 nodes for hexahedron)
    ElementType type;               // Element type

    // Structured grid indices (computed later)
    int i, j, k;                    // Position in structured grid
    bool indexAssigned;             // Flag indicating if i,j,k have been assigned

    // Constructors
    Element()
        : id(0), partId(1), nodeIds{}, type(ElementType::HEX8), i(-1), j(-1), k(-1), indexAssigned(false) {}

    Element(int id, int partId, const std::array<int, NUM_NODES>& nodes)
        : id(id), partId(partId), nodeIds(nodes), type(ElementType::HEX8), i(-1), j(-1), k(-1), indexAssigned(false) {}

    // Copy and move
    Element(const Element& other) = default;
    Element& operator=(const Element& other) = default;
    Element(Element&& other) noexcept = default;
    Element& operator=(Element&& other) noexcept = default;

    // Set structured grid index
    void setGridIndex(int i_, int j_, int k_) {
        i = i_;
        j = j_;
        k = k_;
        indexAssigned = true;
    }

    // ★위상 표를 고를 때 쓰는 **실효 종류**.
    //
    // 왜 필요한가 (실측 2026-10-05). 쐐기 표는 PENTA6 가 `n2 == n3 && n6 == n7` 로
    // **정규화된** 꼴만 맞다. 그런데 리더는 쐐기를 8가지 축퇴 패턴으로 알아보면서
    // **k축 둘만 정규화**하고(`detectAndNormalizePenta6`) 나머지 여섯은 재정렬 없이
    // PENTA6 로만 표시한다(`*ELEMENT_SOLID` 연결 `1 2 3 4 1 2 5 6` 같은 꼴).
    // 그 꼴에 쐐기 표를 쓰면 요소의 면이 아닌 **대각 절단면**이 나와 부피가
    // 0.5 → 0.2222 (-55.6%) 로 틀어졌다.
    //
    // 육면체 표는 그 경우에도 **맞다** — 축퇴한 꼭짓점이 삼각형으로 흡수되고 선으로
    // 찌그러진 면은 `isFaceDegenerate` 가 걸러낸다(실측 부피 0.5 = 참값).
    // 그러므로 정규화되지 않은 쐐기는 육면체 표로 떨군다.
    ElementType topoType() const {
        if (type == ElementType::PENTA6 &&
            !(nodeIds[2] == nodeIds[3] && nodeIds[6] == nodeIds[7])) {
            return ElementType::HEX8;
        }
        return type;
    }

    // 이 요소 종류의 실제 면 수 — 위상 정본(`topo::facesOf`)이 답한다.
    int getNumFaces() const { return static_cast<int>(topo::facesOf(topoType()).size()); }

    // 이 면의 실제 절점 수(3 또는 4). 삼각형 면을 사변형으로 착각하면 면적이 0 이 된다.
    int getFaceNodeCount(int faceIndex) const {
        const auto& F = topo::facesOf(topoType());
        if (faceIndex < 0 || faceIndex >= static_cast<int>(F.size())) return 0;
        return F[faceIndex].n;
    }

    // 면이 퇴화했나 — **유일 절점이 3개 미만**이면 면이 아니다.
    //
    // 옛 판정은 `fn[0]==fn[1] && fn[2]==fn[3]` 이었다. 육면체 표를 TET4 에 쓸 때 생기는 가짜 면
    // `[n0,n3,n3,n3]`·`[n3,n2,n3,n3]`(둘 다 **선**)을 **통과시켰다.** 위상 정본을 쓰면 그런 면이
    // 아예 생기지 않지만, 덱이 절점을 중복해 적는 경우는 여전히 있으므로 판정은 남긴다.
    bool isFaceDegenerate(int faceIndex) const {
        const auto& F = topo::facesOf(topoType());
        if (faceIndex < 0 || faceIndex >= static_cast<int>(F.size())) return true;
        const topo::Face& f = F[faceIndex];
        int uniq = 0;
        int seen[4] = {0, 0, 0, 0};
        for (int i = 0; i < f.n; ++i) {
            const int nid = nodeIds[f.v[i]];
            bool dup = false;
            for (int j = 0; j < uniq; ++j) if (seen[j] == nid) { dup = true; break; }
            if (!dup) seen[uniq++] = nid;
        }
        return uniq < 3;
    }

    // ⚠ **육면체 전용** 면 표. 종류를 모르는 정적 함수이므로 육면체로만 쓸 수 있다 —
    // 종류별 면이 필요하면 `getFaceNodeIds()`(인스턴스)나 `topo::facesOf(type)` 를 쓰라.
    // (감김은 위상 정본과 같다. 옛 표는 6면 중 3면이 안쪽이었다.)
    static std::array<int, NODES_PER_FACE> getFaceLocalNodes(int faceIndex) {
        const auto& F = topo::facesOf(ElementType::HEX8);
        if (faceIndex >= 0 && faceIndex < static_cast<int>(F.size())) {
            const topo::Face& f = F[faceIndex];
            return {f.v[0], f.v[1], f.v[2], f.v[3]};
        }
        return {0, 0, 0, 0};
    }

    // 쓸 수 있는 면 인덱스 — 퇴화한 면은 뺀다.
    // ★인덱스는 **이 요소 종류의 면 표** 기준이다(사면체는 0..3). 파일에 적거나 호출 간에
    //   비교하려면 종류를 함께 기억해야 한다.
    std::vector<int> getValidFaceIndices() const {
        std::vector<int> faces;
        const int n = static_cast<int>(topo::facesOf(topoType()).size());
        faces.reserve(n);
        for (int fi = 0; fi < n; ++fi) {
            if (!isFaceDegenerate(fi)) faces.push_back(fi);
        }
        return faces;
    }

    // 면의 절점 ID — **종류별**이다. 삼각형 면은 마지막을 반복해(`[a,b,c,c]`) 돌려준다.
    // 그것이 LS-DYNA 의 축퇴 사변형이고 덱에서 TRIA3 로 읽힌다.
    std::array<int, NODES_PER_FACE> getFaceNodeIds(int faceIndex) const {
        const auto& F = topo::facesOf(topoType());
        if (faceIndex < 0 || faceIndex >= static_cast<int>(F.size())) return {0, 0, 0, 0};
        const topo::Face& f = F[faceIndex];
        if (f.n == 3) {
            return {nodeIds[f.v[0]], nodeIds[f.v[1]], nodeIds[f.v[2]], nodeIds[f.v[2]]};
        }
        return {
            nodeIds[f.v[0]],
            nodeIds[f.v[1]],
            nodeIds[f.v[2]],
            nodeIds[f.v[3]]
        };
    }

    // Get opposite face index
    static int getOppositeFace(int faceIndex) {
        // 0 <-> 1 (i- <-> i+)
        // 2 <-> 3 (j- <-> j+)
        // 4 <-> 5 (k- <-> k+)
        if (faceIndex % 2 == 0) {
            return faceIndex + 1;
        } else {
            return faceIndex - 1;
        }
    }

    // Get axis for face (0=i, 1=j, 2=k)
    static int getFaceAxis(int faceIndex) {
        return faceIndex / 2;
    }

    // Get direction for face (-1 for minus face, +1 for plus face)
    static int getFaceDirection(int faceIndex) {
        return (faceIndex % 2 == 0) ? -1 : 1;
    }

    // Check if element contains a node
    bool containsNode(int nodeId) const {
        for (int idx = 0; idx < NUM_NODES; ++idx) {
            if (nodeIds[idx] == nodeId) {
                return true;
            }
        }
        return false;
    }

    // Get edge node pairs (12 edges)
    static std::array<std::pair<int, int>, 12> getEdgeLocalNodes() {
        return {{
            // Bottom face edges (k-)
            {0, 1}, {1, 2}, {2, 3}, {3, 0},
            // Top face edges (k+)
            {4, 5}, {5, 6}, {6, 7}, {7, 4},
            // Vertical edges
            {0, 4}, {1, 5}, {2, 6}, {3, 7}
        }};
    }

    // Comparison operators (by ID)
    bool operator==(const Element& other) const {
        return id == other.id;
    }

    bool operator!=(const Element& other) const {
        return id != other.id;
    }

    bool operator<(const Element& other) const {
        return id < other.id;
    }
};

} // namespace KooRemapper
