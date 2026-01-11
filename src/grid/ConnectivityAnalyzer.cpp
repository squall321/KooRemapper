#include "grid/ConnectivityAnalyzer.h"
#include <algorithm>
#include <sstream>

namespace KooRemapper {

ConnectivityAnalyzer::ConnectivityAnalyzer()
    : isStructured_(false)
{}

void ConnectivityAnalyzer::buildConnectivity(const Mesh& mesh) {
    elementNeighbors_.clear();
    faceMap_.clear();
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
    for (const auto& [elemId, elem] : mesh.elements) {
        // Process each of the 6 faces
        for (int faceIdx = 0; faceIdx < Element::NUM_FACES; ++faceIdx) {
            std::array<int, 4> faceNodes = elem.getFaceNodeIds(faceIdx);

            Face face(faceNodes, elemId, faceIdx);
            std::string key = face.getKey();

            faceMap_[key].push_back({elemId, faceIdx});
        }
    }
}

void ConnectivityAnalyzer::findNeighbors() {
    // Initialize empty neighbor lists for all elements
    for (const auto& [key, facePairs] : faceMap_) {
        for (const auto& [elemId, faceIdx] : facePairs) {
            if (elementNeighbors_.find(elemId) == elementNeighbors_.end()) {
                elementNeighbors_[elemId] = std::vector<ElementNeighbor>();
            }
        }
    }

    // Find neighbors through shared faces
    for (const auto& [key, facePairs] : faceMap_) {
        if (facePairs.size() == 2) {
            // Two elements share this face - they are neighbors
            int elem1 = facePairs[0].first;
            int face1 = facePairs[0].second;
            int elem2 = facePairs[1].first;
            int face2 = facePairs[1].second;

            // Add neighbor relationship
            elementNeighbors_[elem1].push_back({elem2, face1, face2});
            elementNeighbors_[elem2].push_back({elem1, face2, face1});
        }
        else if (facePairs.size() == 1) {
            // This is a boundary face
            Face boundaryFace;
            // Parse key back to node IDs
            std::array<int, 4> nodeIds;
            std::stringstream ss(key);
            std::string token;
            int i = 0;
            while (std::getline(ss, token, '_') && i < 4) {
                nodeIds[i++] = std::stoi(token);
            }
            boundaryFace.nodeIds = nodeIds;
            boundaryFace.elementId = facePairs[0].first;
            boundaryFace.localFaceIndex = facePairs[0].second;
            boundaryFaces_.push_back(boundaryFace);
        }
        // More than 2 elements sharing a face would indicate mesh errors
    }
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
