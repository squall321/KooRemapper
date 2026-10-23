#include "grid/ConnectivityAnalyzer.h"
#include <algorithm>

// Knowledge graph (lat.md):
//   @lat: [[modules/grid]]

namespace KooRemapper {

namespace {

// Compare the decimal texts (std::to_string) of a and b the way strings
// compare, without building them: <0 if a's text sorts first, >0 if b's,
// 0 if a == b. When one text is a prefix of the other, shorterFirst decides.
int compareDecimalText(int a, int b, bool shorterFirst) {
    if (a == b) return 0;
    if ((a < 0) != (b < 0)) return a < 0 ? -1 : 1;  // '-' sorts before digits
    long long la = a, lb = b;
    unsigned long long ua = static_cast<unsigned long long>(la < 0 ? -la : la);
    unsigned long long ub = static_cast<unsigned long long>(lb < 0 ? -lb : lb);
    int da = 1, db = 1;
    for (unsigned long long t = ua; t >= 10; t /= 10) ++da;
    for (unsigned long long t = ub; t >= 10; t /= 10) ++db;
    // Leading min(da, db) digits, compared as numbers
    unsigned long long pa = ua, pb = ub;
    for (int d = da; d > db; --d) pa /= 10;
    for (int d = db; d > da; --d) pb /= 10;
    if (pa != pb) return pa < pb ? -1 : 1;
    return ((da < db) == shorterFirst) ? -1 : 1;
}

// Order of the former face key "n0_n1_n2_n3" (sorted node IDs as
// std::to_string joined by '_'), the order a std::map<std::string, ...>
// iterated faces in. Neighbor lists keep it because the indexer's BFS walks
// them in order. A shorter text in fields 0-2 is followed by '_', which sorts
// after every digit; in the last field it is followed by the end of the key.
bool faceKeyLess(const std::array<int, 4>& a, const std::array<int, 4>& b) {
    for (int f = 0; f < 4; ++f) {
        int c = compareDecimalText(a[f], b[f], f == 3);
        if (c != 0) return c < 0;
    }
    return false;
}

}  // namespace

ConnectivityAnalyzer::ConnectivityAnalyzer()
    : isStructured_(false)
{}

void ConnectivityAnalyzer::buildConnectivity(const Mesh& mesh) {
    elementNeighbors_.clear();
    faceEntries_.clear();
    boundaryFaces_.clear();
    errorMessage_.clear();
    isStructured_ = false;

    if (mesh.elements.empty()) {
        errorMessage_ = "Mesh has no elements";
        return;
    }

    // Build face map
    buildFaceMap(mesh);

    // Find neighbors using face map
    findNeighbors();

    // Validate structured grid
    validateStructuredGrid(mesh);
}

void ConnectivityAnalyzer::buildFaceMap(const Mesh& mesh) {
    faceEntries_.reserve(mesh.elements.size() * Element::NUM_FACES);
    for (const auto& [elemId, elem] : mesh.elements) {
        // Process each valid face (skips degenerate faces for PENTA6)
        std::vector<int> faceIndices = elem.getValidFaceIndices();
        if (faceIndices.empty()) continue;

        // Empty neighbor list for every element that has a face. Elements
        // arrive in ID order, so the end is the right insertion hint.
        auto& neighbors = elementNeighbors_.emplace_hint(
            elementNeighbors_.end(), elemId, std::vector<ElementNeighbor>())->second;
        neighbors.reserve(faceIndices.size());

        for (int faceIdx : faceIndices) {
            Face face(elem.getFaceNodeIds(faceIdx), elemId, faceIdx);
            faceEntries_.push_back({face.nodeIds, elemId, faceIdx, &neighbors});
        }
    }
}

void ConnectivityAnalyzer::findNeighbors() {
    // Bring equal node sets together. Within a group, entries keep the order
    // they were collected in (element ID, then local face index).
    std::sort(faceEntries_.begin(), faceEntries_.end(),
              [](const FaceEntry& a, const FaceEntry& b) {
                  if (a.nodeIds != b.nodeIds) return a.nodeIds < b.nodeIds;
                  if (a.elementId != b.elementId) return a.elementId < b.elementId;
                  return a.localFaceIndex < b.localFaceIndex;
              });

    // Find neighbors through shared faces
    for (size_t first = 0; first < faceEntries_.size(); ) {
        size_t last = first + 1;
        while (last < faceEntries_.size() &&
               faceEntries_[last].nodeIds == faceEntries_[first].nodeIds) {
            ++last;
        }
        const FaceEntry& f1 = faceEntries_[first];
        if (last - first == 2) {
            // Two elements share this face - they are neighbors
            const FaceEntry& f2 = faceEntries_[first + 1];
            f1.neighbors->push_back({f2.elementId, f1.localFaceIndex, f2.localFaceIndex, f1.nodeIds});
            f2.neighbors->push_back({f1.elementId, f2.localFaceIndex, f1.localFaceIndex, f1.nodeIds});
        }
        else if (last - first == 1) {
            // This is a boundary face
            Face boundaryFace;
            boundaryFace.nodeIds = f1.nodeIds;
            boundaryFace.elementId = f1.elementId;
            boundaryFace.localFaceIndex = f1.localFaceIndex;
            boundaryFaces_.push_back(boundaryFace);
        }
        // More than 2 elements sharing a face would indicate mesh errors
        first = last;
    }
    faceEntries_.clear();
    faceEntries_.shrink_to_fit();

    // Put both lists in the former face-key order (see faceKeyLess). Equal
    // keys only occur for a face an element shares with itself; the stable
    // sort keeps those two entries in the order they were added.
    for (auto& [elemId, neighbors] : elementNeighbors_) {
        std::stable_sort(neighbors.begin(), neighbors.end(),
                         [](const ElementNeighbor& a, const ElementNeighbor& b) {
                             return faceKeyLess(a.sharedNodes, b.sharedNodes);
                         });
    }
    std::sort(boundaryFaces_.begin(), boundaryFaces_.end(),
              [](const Face& a, const Face& b) { return faceKeyLess(a.nodeIds, b.nodeIds); });
}

void ConnectivityAnalyzer::validateStructuredGrid(const Mesh& mesh) {
    // Count elements by number of neighbors
    int cornerCount = 0;    // 3 neighbors
    int edgeCount = 0;      // 4 neighbors
    int faceCount = 0;      // 5 neighbors
    int interiorCount = 0;  // 6 neighbors

    for (const auto& [elemId, neighbors] : elementNeighbors_) {
        int n = static_cast<int>(neighbors.size());
        switch (n) {
            case 3: cornerCount++; break;
            case 4: edgeCount++; break;
            case 5: faceCount++; break;
            case 6: interiorCount++; break;
            default:
                // Invalid neighbor count for structured grid
                errorMessage_ = "Element " + std::to_string(elemId) +
                              " has " + std::to_string(n) + " neighbors (expected 3-6)";
                isStructured_ = false;
                return;
        }
    }

    // For a valid structured grid:
    // - Should have exactly 8 corner elements
    // - Number of edge, face, interior elements depends on dimensions
    if (cornerCount == 8) {
        isStructured_ = true;
    } else {
        errorMessage_ = "Expected 8 corner elements, found " + std::to_string(cornerCount);
        isStructured_ = false;
    }
}

std::vector<ElementNeighbor> ConnectivityAnalyzer::getNeighbors(int elementId) const {
    auto it = elementNeighbors_.find(elementId);
    if (it != elementNeighbors_.end()) {
        return it->second;
    }
    return {};
}

int ConnectivityAnalyzer::getNeighborCount(int elementId) const {
    auto it = elementNeighbors_.find(elementId);
    if (it != elementNeighbors_.end()) {
        return static_cast<int>(it->second.size());
    }
    return 0;
}

bool ConnectivityAnalyzer::areNeighbors(int elemId1, int elemId2) const {
    auto it = elementNeighbors_.find(elemId1);
    if (it != elementNeighbors_.end()) {
        for (const auto& neighbor : it->second) {
            if (neighbor.neighborElementId == elemId2) {
                return true;
            }
        }
    }
    return false;
}

int ConnectivityAnalyzer::getSharedFace(int elemId1, int elemId2) const {
    auto it = elementNeighbors_.find(elemId1);
    if (it != elementNeighbors_.end()) {
        for (const auto& neighbor : it->second) {
            if (neighbor.neighborElementId == elemId2) {
                return neighbor.throughFace;
            }
        }
    }
    return -1;
}

std::array<int, 4> ConnectivityAnalyzer::getSharedNodes(int elemId1, int elemId2) const {
    auto it = elementNeighbors_.find(elemId1);
    if (it != elementNeighbors_.end()) {
        for (const auto& neighbor : it->second) {
            if (neighbor.neighborElementId == elemId2) {
                return neighbor.sharedNodes;
            }
        }
    }
    return {0, 0, 0, 0};
}

std::vector<int> ConnectivityAnalyzer::findCornerElements() const {
    std::vector<int> corners;
    for (const auto& [elemId, neighbors] : elementNeighbors_) {
        if (neighbors.size() == 3) {
            corners.push_back(elemId);
        }
    }
    return corners;
}

std::vector<int> ConnectivityAnalyzer::findEdgeElements() const {
    std::vector<int> edges;
    for (const auto& [elemId, neighbors] : elementNeighbors_) {
        if (neighbors.size() == 4) {
            edges.push_back(elemId);
        }
    }
    return edges;
}

std::vector<int> ConnectivityAnalyzer::findFaceElements() const {
    std::vector<int> faces;
    for (const auto& [elemId, neighbors] : elementNeighbors_) {
        if (neighbors.size() == 5) {
            faces.push_back(elemId);
        }
    }
    return faces;
}

std::vector<int> ConnectivityAnalyzer::findInteriorElements() const {
    std::vector<int> interior;
    for (const auto& [elemId, neighbors] : elementNeighbors_) {
        if (neighbors.size() == 6) {
            interior.push_back(elemId);
        }
    }
    return interior;
}

std::vector<Face> ConnectivityAnalyzer::getBoundaryFaces() const {
    return boundaryFaces_;
}

} // namespace KooRemapper
