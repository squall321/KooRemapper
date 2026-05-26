#include "core/ShellMesh.h"
#include <algorithm>

// Knowledge graph (lat.md):
//   @lat: [[modules/core]]

namespace KooRemapper {

void ShellMesh::buildConnectivity() {
    edgeToElements_.clear();

    for (const auto& [elemId, elem] : elements_) {
        for (int e = 0; e < ShellElement::NUM_EDGES; ++e) {
            auto edgeKey = elem.getEdgeKey(e);
            edgeToElements_[edgeKey].push_back(elemId);
        }
    }

    computeNodeNormals();
}

void ShellMesh::computeNodeNormals() {
    nodeNormals_.clear();

    // Accumulate area-weighted element normals at each node
    for (const auto& [elemId, elem] : elements_) {
        Vector3D elemNormal = getElementNormal(elemId);
        double area = getElementArea(elemId);

        for (int i = 0; i < ShellElement::NUM_NODES; ++i) {
            nodeNormals_[elem.nodeIds[i]] += elemNormal * area;
        }
    }

    // Normalize to unit vectors
    for (auto& [nodeId, normal] : nodeNormals_) {
        double mag = normal.magnitude();
        if (mag > 1e-15) {
            normal = normal / mag;
        }
    }
}

Vector3D ShellMesh::getNodeNormal(int nodeId) const {
    auto it = nodeNormals_.find(nodeId);
    if (it != nodeNormals_.end()) {
        return it->second;
    }
    return Vector3D(0, 0, 1);
}

std::vector<int> ShellMesh::getNeighbors(int elemId) const {
    auto it = elements_.find(elemId);
    if (it == elements_.end()) return {};

    const auto& elem = it->second;
    std::vector<int> neighbors;

    for (int e = 0; e < ShellElement::NUM_EDGES; ++e) {
        auto edgeKey = elem.getEdgeKey(e);
        auto edgeIt = edgeToElements_.find(edgeKey);
        if (edgeIt != edgeToElements_.end()) {
            for (int neighborId : edgeIt->second) {
                if (neighborId != elemId) {
                    neighbors.push_back(neighborId);
                }
            }
        }
    }

    return neighbors;
}

int ShellMesh::getNeighborAcrossEdge(int elemId, int edgeIdx) const {
    auto it = elements_.find(elemId);
    if (it == elements_.end()) return -1;

    auto edgeKey = it->second.getEdgeKey(edgeIdx);
    auto edgeIt = edgeToElements_.find(edgeKey);
    if (edgeIt == edgeToElements_.end()) return -1;

    for (int neighborId : edgeIt->second) {
        if (neighborId != elemId) {
            return neighborId;
        }
    }
    return -1;
}

Vector3D ShellMesh::getElementNormal(int elemId) const {
    auto it = elements_.find(elemId);
    if (it == elements_.end()) return Vector3D(0, 0, 1);

    const auto& elem = it->second;
    const Node* n0 = getNode(elem.nodeIds[0]);
    const Node* n1 = getNode(elem.nodeIds[1]);
    const Node* n2 = getNode(elem.nodeIds[2]);
    const Node* n3 = getNode(elem.nodeIds[3]);

    if (!n0 || !n1 || !n2 || !n3) return Vector3D(0, 0, 1);

    // Average of two triangle normals for better accuracy on non-planar quads
    Vector3D d1 = n2->position - n0->position;
    Vector3D d2 = n3->position - n1->position;
    Vector3D normal = d1.cross(d2);

    double mag = normal.magnitude();
    if (mag > 1e-15) {
        return normal / mag;
    }
    return Vector3D(0, 0, 1);
}

Vector3D ShellMesh::getElementCentroid(int elemId) const {
    auto it = elements_.find(elemId);
    if (it == elements_.end()) return Vector3D();

    const auto& elem = it->second;
    Vector3D centroid;
    int count = 0;

    for (int i = 0; i < ShellElement::NUM_NODES; ++i) {
        const Node* node = getNode(elem.nodeIds[i]);
        if (node) {
            centroid += node->position;
            ++count;
        }
    }

    if (count > 0) centroid /= static_cast<double>(count);
    return centroid;
}

double ShellMesh::getElementArea(int elemId) const {
    auto it = elements_.find(elemId);
    if (it == elements_.end()) return 0.0;

    const auto& elem = it->second;
    const Node* n0 = getNode(elem.nodeIds[0]);
    const Node* n1 = getNode(elem.nodeIds[1]);
    const Node* n2 = getNode(elem.nodeIds[2]);
    const Node* n3 = getNode(elem.nodeIds[3]);

    if (!n0 || !n1 || !n2 || !n3) return 0.0;

    // Area = 0.5 * |d1 x d2| where d1=n2-n0, d2=n3-n1 (diagonal cross)
    Vector3D d1 = n2->position - n0->position;
    Vector3D d2 = n3->position - n1->position;
    return 0.5 * d1.cross(d2).magnitude();
}

std::vector<int> ShellMesh::getBoundaryElements() const {
    std::vector<int> boundary;
    for (const auto& [elemId, elem] : elements_) {
        int neighborCount = 0;
        for (int e = 0; e < ShellElement::NUM_EDGES; ++e) {
            if (getNeighborAcrossEdge(elemId, e) >= 0) {
                ++neighborCount;
            }
        }
        if (neighborCount < ShellElement::NUM_EDGES) {
            boundary.push_back(elemId);
        }
    }
    return boundary;
}

bool ShellMesh::validate(std::string& errorMessage) const {
    for (const auto& [elemId, elem] : elements_) {
        for (int i = 0; i < ShellElement::NUM_NODES; ++i) {
            if (!hasNode(elem.nodeIds[i])) {
                errorMessage = "Shell element " + std::to_string(elemId) +
                    " references non-existent node " + std::to_string(elem.nodeIds[i]);
                return false;
            }
        }
    }
    return true;
}

} // namespace KooRemapper
