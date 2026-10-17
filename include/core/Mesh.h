#pragma once

#include "core/Node.h"
#include "core/Element.h"
#include "core/Vector3D.h"
#include <map>
#include <set>
#include <unordered_map>
#include <vector>
#include <string>
#include <utility>
#include <algorithm>

// Knowledge graph (lat.md):
//   @lat: [[modules/core]]

namespace KooRemapper {

/**
 * Material data (linear elastic)
 */
struct MaterialData {
    int id;
    double E;       // Young's modulus
    double nu;      // Poisson's ratio
    double density; // Mass density (optional)
    double sigy;    // Yield stress (MAT_024 SIGY field, 0 = not available)
    std::string name;

    MaterialData() : id(0), E(0), nu(0), density(0), sigy(0) {}
    MaterialData(int id, double E, double nu, double density = 0, const std::string& name = "")
        : id(id), E(E), nu(nu), density(density), sigy(0), name(name) {}
    
    bool isValid() const { return E > 0 && nu > 0 && nu < 0.5; }
};

/**
 * Part definition
 */
struct Part {
    int id;
    int sectionId;   // Section ID (SECID)
    int materialId;  // Material ID (MID)
    std::string name;

    Part() : id(0), sectionId(0), materialId(0) {}
    Part(int id, const std::string& name = "") : id(id), sectionId(0), materialId(0), name(name) {}
    Part(int id, int secId, int matId, const std::string& name = "") 
        : id(id), sectionId(secId), materialId(matId), name(name) {}
};

/**
 * Mesh statistics structure
 */
struct MeshStats {
    int nodeCount;
    int elementCount;
    Vector3D boundingBoxMin;
    Vector3D boundingBoxMax;
    Vector3D dimensions;        // boundingBoxMax - boundingBoxMin
    Vector3D centroid;          // Center of bounding box

    // Grid dimensions (for structured meshes)
    int dimI, dimJ, dimK;
    bool isStructured;

    MeshStats()
        : nodeCount(0), elementCount(0)
        , dimI(0), dimJ(0), dimK(0)
        , isStructured(false) {}
};

/**
 * Shell section data (from *SECTION_SHELL)
 */
/**
 * 두 bbox 와 고아 절점 수를 **함께** 담는다.
 *
 * 왜 한 구조체인가 (2026-10-10). 이 자리의 결함은 늘 **기준을 뒤섞는 것**이었다 —
 * 현장 보고가 "기기 두께 14.55mm 인데 bbox 가 67.50mm" 로 왔고, 그 67.50 은 하류 도구가
 * `*NODE` **전체**에서 뽑은 값이었다(KooRemapper 는 `calculateBoundingBox()` 에서 고아를
 * 이미 뺀다). 낙하판을 그 bbox 로 놓으면 기기에서 53mm 밖에 생겨 **충돌이 아예 없다.**
 *
 * 기준을 따로 물으면 호출자가 라벨을 틀릴 수 있으므로, **이름에 기준을 박아 함께** 준다.
 */
struct BBoxReport {
    Vector3D usedMin, usedMax;   // 요소가 **쓰는** 절점만 — `calculateBoundingBox()` 와 같은 값
    Vector3D allMin, allMax;     // `*NODE` **전체** (고아 포함)
    size_t orphanNodes = 0;      // 요소가 쓰지 않는 절점 수
    bool hasElements = false;    // 요소가 없으면 두 bbox 가 같다(구분할 것이 없다)
};

struct SectionShellData {
    int id;
    double thickness;
    SectionShellData() : id(0), thickness(0.0) {}
    SectionShellData(int id, double t) : id(id), thickness(t) {}
};

/**
 * Mesh class containing nodes and elements
 */
class Mesh {
public:
    std::map<int, Node> nodes;              // Node ID -> Node
    std::map<int, Element> elements;        // Element ID -> Element
    std::map<int, Part> parts;              // Part ID -> Part
    std::map<int, MaterialData> materials;  // Material ID -> MaterialData
    std::map<int, SectionShellData> shellSections;  // Section ID -> Shell section data
    // Part ID -> *SECTION_SOLID ELFORM. 리더가 고차 카드를 가르고 코너를 제자리에 놓는 데 쓴다.
    // 2026-10-17 전에는 리더가 절점 칸의 앞 8개만 담아 TET10(ELFORM 16) 의 중간절점이 코너 자리로 들어왔다 —
    // 단면 면적이 0.12(참값 0.32)로 조용히 틀려 그림 op 이 이 값으로 **거절**했다. 지금은 코너를 제자리에 놓고
    // 코너 차례를 매뉴얼이 적지 않은 ELFORM(25·26·27·28)과 칸이 모자란 카드만 거절한다(`figure::secondOrderSolidPids`).
    std::map<int, int> partSolidElform;
    // ★2차 솔리드의 **덱 순서 전체 절점**(2026-10-17) — EID → N1..Nn(ELFORM 이 정한 n 칸, 못 읽은 칸은 0).
    // **2차 요소만** 담는다 — `Element` 에 벡터를 두면 1차 덱도 요소마다 24바이트가 는다(실사용 덱은 요소 수백만).
    // `Element::nodeIds` 는 위상 표가 기대하는 **코너 자리**만 담는다 — TET10(ELFORM 16·17)은 `[n1,n2,n3,n4,n4,n4,n4,n4]`
    // · 20·27·64절점 육면체는 앞 8칸 그대로. 절점 **참조**(고아 · 소속 · 쓰기)는 여기를 보고, **기하**는 코너를 본다.
    std::unordered_map<int, std::vector<int>> solidAllNodes;
    // 절점 칸이 모자란 2차 요소 수 — PID → 수. 매뉴얼 Card 2 는 N1..N10 열 칸 한 장이다(노드를 8+2 로 쪼갠 덱은 둘째 줄이
    // 다음 요소의 Card 1 로 읽힌다 — LS-DYNA 도 그렇게 읽는다). 그 파트는 기하를 믿을 수 없다.
    std::map<int, int> partIncompleteSolids;
    std::string name_;                      // Mesh name

    // Grid dimensions (for structured meshes)
    int dimI, dimJ, dimK;
    bool gridDimensionsSet;

    // Constructors
    Mesh() : dimI(0), dimJ(0), dimK(0), gridDimensionsSet(false) {}

    // Copy and move
    Mesh(const Mesh& other) = default;
    Mesh& operator=(const Mesh& other) = default;
    Mesh(Mesh&& other) noexcept = default;
    Mesh& operator=(Mesh&& other) noexcept = default;

    // Node operations
    void addNode(const Node& node) {
        nodes[node.id] = node;
    }

    // TC/RC 를 함께 받는 갈래. 리더가 이것을 쓴다(구속을 버리지 않기 위해).
    void addNode(int id, double x, double y, double z, int tc, int rc) {
        Node n(id, x, y, z);
        n.tc = tc;
        n.rc = rc;
        addNode(n);
    }

    void addNode(int id, double x, double y, double z) {
        nodes[id] = Node(id, x, y, z);
    }

    Node* getNode(int id) {
        auto it = nodes.find(id);
        return (it != nodes.end()) ? &it->second : nullptr;
    }

    const Node* getNode(int id) const {
        auto it = nodes.find(id);
        return (it != nodes.end()) ? &it->second : nullptr;
    }

    bool hasNode(int id) const {
        return nodes.find(id) != nodes.end();
    }

    // Element operations
    void addElement(const Element& elem) {
        elements[elem.id] = elem;
    }

    void addElement(int id, int partId, const std::array<int, 8>& nodeIds) {
        elements[id] = Element(id, partId, nodeIds);
    }

    Element* getElement(int id) {
        auto it = elements.find(id);
        return (it != elements.end()) ? &it->second : nullptr;
    }

    const Element* getElement(int id) const {
        auto it = elements.find(id);
        return (it != elements.end()) ? &it->second : nullptr;
    }

    bool hasElement(int id) const {
        return elements.find(id) != elements.end();
    }

    // Get element by grid index
    Element* getElementByIndex(int i, int j, int k) {
        for (auto& [id, elem] : elements) {
            if (elem.indexAssigned && elem.i == i && elem.j == j && elem.k == k) {
                return &elem;
            }
        }
        return nullptr;
    }

    const Element* getElementByIndex(int i, int j, int k) const {
        for (const auto& [id, elem] : elements) {
            if (elem.indexAssigned && elem.i == i && elem.j == j && elem.k == k) {
                return &elem;
            }
        }
        return nullptr;
    }

    // Count operations
    size_t getNodeCount() const { return nodes.size(); }
    size_t getElementCount() const { return elements.size(); }
    size_t getPartCount() const { return parts.size(); }

    // Max ID queries (std::map is sorted, rbegin gives max key)
    int getMaxNodeId() const {
        return nodes.empty() ? 0 : nodes.rbegin()->first;
    }
    int getMaxElementId() const {
        return elements.empty() ? 0 : elements.rbegin()->first;
    }

    // Accessors for collections
    const std::map<int, Node>& getNodes() const { return nodes; }
    const std::map<int, Element>& getElements() const { return elements; }
    const std::map<int, Part>& getParts() const { return parts; }

    // Name operations
    void setName(const std::string& name) { name_ = name; }
    const std::string& getName() const { return name_; }

    // Part operations
    void addPart(const Part& part) { parts[part.id] = part; }
    void addPart(int id, const std::string& name = "") { parts[id] = Part(id, name); }
    void addPart(int id, int secId, int matId, const std::string& name = "") { 
        parts[id] = Part(id, secId, matId, name); 
    }
    
    // Material operations
    void addMaterial(const MaterialData& mat) { materials[mat.id] = mat; }
    void addMaterial(int id, double E, double nu, double density = 0) { 
        materials[id] = MaterialData(id, E, nu, density); 
    }
    
    const MaterialData* getMaterial(int id) const {
        auto it = materials.find(id);
        return (it != materials.end()) ? &it->second : nullptr;
    }
    
    /**
     * Get material for an element (via part -> material mapping)
     * Returns nullptr if not found
     */
    const MaterialData* getElementMaterial(const Element& elem) const {
        auto partIt = parts.find(elem.partId);
        if (partIt == parts.end()) return nullptr;
        
        auto matIt = materials.find(partIt->second.materialId);
        if (matIt == materials.end()) return nullptr;
        
        return &matIt->second;
    }
    
    size_t getMaterialCount() const { return materials.size(); }
    const std::map<int, MaterialData>& getMaterials() const { return materials; }
    const std::map<int, int>& getPartSolidElform() const { return partSolidElform; }
    const std::map<int, int>& getPartIncompleteSolids() const { return partIncompleteSolids; }
    // 그 요소의 덱 순서 전체 절점 — 2차 솔리드가 아니면 nullptr(그때는 `nodeIds` 가 전부다).
    const std::vector<int>* allNodesOf(int eid) const {
        auto it = solidAllNodes.find(eid);
        return it == solidAllNodes.end() ? nullptr : &it->second;
    }
    // 요소가 **참조하는** 절점마다 `f(nid)` — 2차 솔리드는 중간절점까지, 그 밖은 `nodeIds`(0 은 건너뛴다 · 축퇴는 겹친다).
    template <class F> void forEachElementNode(const Element& e, F&& f) const {
        if (const auto* all = allNodesOf(e.id)) { for (int n : *all) if (n > 0) f(n); return; }
        for (int n : e.nodeIds) if (n > 0) f(n);
    }

    // Get bounding box as pair
    std::pair<Vector3D, Vector3D> getBoundingBox() const {
        Vector3D minP, maxP;
        calculateBoundingBox(minP, maxP);
        return {minP, maxP};
    }

    /** 두 bbox 와 고아 수를 **한 번 순회로** 낸다.
     *
     * ⚠ 한 번만 도는 것이 중요하다 — 실사용 덱이 절점 13,366,933개(2.32GB)다. 참조 집합을
     * 두 번 만들면 그만큼 더 든다. `calculateBoundingBox()` 는 그대로 두었다(다른 호출자가
     * 많고 동작이 맞다) — 여기서 그 값을 `usedMin/Max` 로 함께 낸다. */
    BBoxReport bboxReport() const {
        BBoxReport r;
        if (nodes.empty()) return r;

        std::set<int> refNodes;
        for (const auto& [eid, elem] : elements)
            forEachElementNode(elem, [&](int nid) { refNodes.insert(nid); });   // 2차 솔리드는 중간절점까지
        r.hasElements = !refNodes.empty();

        bool firstAll = true, firstUsed = true;
        for (const auto& [id, node] : nodes) {
            const Vector3D& p = node.position;
            if (firstAll) { r.allMin = r.allMax = p; firstAll = false; }
            else {
                r.allMin.x = std::min(r.allMin.x, p.x); r.allMax.x = std::max(r.allMax.x, p.x);
                r.allMin.y = std::min(r.allMin.y, p.y); r.allMax.y = std::max(r.allMax.y, p.y);
                r.allMin.z = std::min(r.allMin.z, p.z); r.allMax.z = std::max(r.allMax.z, p.z);
            }
            if (!r.hasElements) continue;
            if (refNodes.count(id) == 0) { ++r.orphanNodes; continue; }
            if (firstUsed) { r.usedMin = r.usedMax = p; firstUsed = false; }
            else {
                r.usedMin.x = std::min(r.usedMin.x, p.x); r.usedMax.x = std::max(r.usedMax.x, p.x);
                r.usedMin.y = std::min(r.usedMin.y, p.y); r.usedMax.y = std::max(r.usedMax.y, p.y);
                r.usedMin.z = std::min(r.usedMin.z, p.z); r.usedMax.z = std::max(r.usedMax.z, p.z);
            }
        }
        // 요소가 없으면 `calculateBoundingBox()` 가 전체 절점으로 떨어진다 — 그 규약을 따른다.
        if (!r.hasElements) { r.usedMin = r.allMin; r.usedMax = r.allMax; }
        return r;
    }

    // Set grid dimensions
    void setGridDimensions(int i, int j, int k) {
        dimI = i;
        dimJ = j;
        dimK = k;
        gridDimensionsSet = true;
    }

    // Calculate bounding box.
    //
    // When the mesh has elements, only nodes referenced by an element are
    // considered. This prevents far-outside orphan reference nodes (e.g.
    // dummy nodes for *CONSTRAINED_RIGID_BODIES, *BOUNDARY_PRESCRIBED_*,
    // *ELEMENT_MASS) from inflating the bbox — which would distort every
    // parametric ratio downstream in `map` and `shellmap`.
    //
    // For meshes with no elements (node-only meshes used in some unit
    // tests / generators), the bbox falls back to all nodes.
    void calculateBoundingBox(Vector3D& minPoint, Vector3D& maxPoint) const {
        if (nodes.empty()) {
            minPoint = Vector3D(0, 0, 0);
            maxPoint = Vector3D(0, 0, 0);
            return;
        }

        // Build the set of node IDs referenced by any element.
        std::set<int> refNodes;
        for (const auto& [eid, elem] : elements) {
            for (int i = 0; i < Element::NUM_NODES; ++i) {
                int nid = elem.nodeIds[i];
                if (nid > 0) refNodes.insert(nid);
            }
        }
        bool useRefOnly = !refNodes.empty();

        bool first = true;
        for (const auto& [id, node] : nodes) {
            if (useRefOnly && refNodes.count(id) == 0) continue;
            if (first) {
                minPoint = node.position;
                maxPoint = node.position;
                first = false;
            } else {
                minPoint.x = std::min(minPoint.x, node.position.x);
                minPoint.y = std::min(minPoint.y, node.position.y);
                minPoint.z = std::min(minPoint.z, node.position.z);
                maxPoint.x = std::max(maxPoint.x, node.position.x);
                maxPoint.y = std::max(maxPoint.y, node.position.y);
                maxPoint.z = std::max(maxPoint.z, node.position.z);
            }
        }
        // If elements existed but none referenced any node in `nodes`
        // (shouldn't happen for valid meshes but guard anyway), fall back.
        if (first) {
            minPoint = nodes.begin()->second.position;
            maxPoint = minPoint;
        }
    }

    // Get mesh statistics
    MeshStats getStats() const {
        MeshStats stats;
        stats.nodeCount = static_cast<int>(nodes.size());
        stats.elementCount = static_cast<int>(elements.size());

        calculateBoundingBox(stats.boundingBoxMin, stats.boundingBoxMax);
        stats.dimensions = stats.boundingBoxMax - stats.boundingBoxMin;
        stats.centroid = (stats.boundingBoxMin + stats.boundingBoxMax) * 0.5;

        stats.dimI = dimI;
        stats.dimJ = dimJ;
        stats.dimK = dimK;
        stats.isStructured = gridDimensionsSet;

        return stats;
    }

    // Clear all data
    void clear() {
        nodes.clear();
        elements.clear();
        parts.clear();
        materials.clear();
        partSolidElform.clear();
        solidAllNodes.clear();
        partIncompleteSolids.clear();
        name_.clear();
        dimI = dimJ = dimK = 0;
        gridDimensionsSet = false;
    }

    // Get all nodes of an element as vector
    std::vector<const Node*> getElementNodes(const Element& elem) const {
        std::vector<const Node*> result;
        result.reserve(Element::NUM_NODES);
        for (int i = 0; i < Element::NUM_NODES; ++i) {
            const Node* node = getNode(elem.nodeIds[i]);
            if (node) {
                result.push_back(node);
            }
        }
        return result;
    }

    // Calculate element centroid
    Vector3D getElementCentroid(const Element& elem) const {
        Vector3D centroid(0, 0, 0);
        int count = 0;
        for (int i = 0; i < Element::NUM_NODES; ++i) {
            const Node* node = getNode(elem.nodeIds[i]);
            if (node) {
                centroid += node->position;
                ++count;
            }
        }
        if (count > 0) {
            centroid /= static_cast<double>(count);
        }
        return centroid;
    }

    // Validate mesh integrity
    bool validate(std::string& errorMessage) const {
        // Check that all element nodes exist
        for (const auto& [elemId, elem] : elements) {
            for (int i = 0; i < Element::NUM_NODES; ++i) {
                if (!hasNode(elem.nodeIds[i])) {
                    errorMessage = "Element " + std::to_string(elemId) +
                                 " references non-existent node " +
                                 std::to_string(elem.nodeIds[i]);
                    return false;
                }
            }
        }
        return true;
    }
};

} // namespace KooRemapper
