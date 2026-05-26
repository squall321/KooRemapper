#include "mapper/ShellUnfolder.h"
#include <queue>
#include <set>
#include <cmath>
#include <algorithm>

// Knowledge graph (lat.md):
//   @lat: [[modules/mapper]]

namespace KooRemapper {

bool ShellUnfolder::unfold(const ShellMesh& bentShell) {
    flatPositions_.clear();
    maxDistortion_ = 0.0;
    avgDistortion_ = 0.0;

    if (bentShell.getElementCount() == 0) return false;

    // Find a boundary element to start from
    auto boundary = bentShell.getBoundaryElements();
    int startElemId;
    if (!boundary.empty()) {
        startElemId = boundary[0];
    } else {
        // No boundary (closed surface) - use first element
        startElemId = bentShell.getElements().begin()->first;
    }

    const auto* startElem = bentShell.getElement(startElemId);
    if (!startElem) return false;

    // Place start element on XY plane
    placeStartElement(bentShell, *startElem);

    // BFS propagation
    std::set<int> processed;
    std::queue<int> queue;
    processed.insert(startElemId);
    queue.push(startElemId);

    while (!queue.empty()) {
        int currentId = queue.front();
        queue.pop();

        const auto* currentElem = bentShell.getElement(currentId);
        if (!currentElem) continue;

        // Check all 4 edges for neighbors
        for (int e = 0; e < ShellElement::NUM_EDGES; ++e) {
            int neighborId = bentShell.getNeighborAcrossEdge(currentId, e);
            if (neighborId < 0) continue;
            if (processed.count(neighborId)) continue;

            const auto* neighborElem = bentShell.getElement(neighborId);
            if (!neighborElem) continue;

            // Get shared edge nodes
            auto edgeNodes = currentElem->getEdgeNodes(e);
            int sharedN0 = edgeNodes[0];
            int sharedN1 = edgeNodes[1];

            // Both shared nodes should already have flat positions
            if (flatPositions_.find(sharedN0) == flatPositions_.end() ||
                flatPositions_.find(sharedN1) == flatPositions_.end()) {
                continue;
            }

            // Place the neighbor element
            placeNeighborElement(bentShell, *neighborElem, sharedN0, sharedN1);

            processed.insert(neighborId);
            queue.push(neighborId);
        }
    }

    // Compute distortion metrics
    double totalDistortion = 0.0;
    int elemCount = 0;
    for (const auto& [elemId, elem] : bentShell.getElements()) {
        if (processed.count(elemId)) {
            double dist = computeDistortion(bentShell, elem);
            totalDistortion += dist;
            maxDistortion_ = std::max(maxDistortion_, dist);
            elemCount++;
        }
    }
    if (elemCount > 0) {
        avgDistortion_ = totalDistortion / elemCount;
    }

    return true;
}

void ShellUnfolder::placeStartElement(const ShellMesh& mesh, const ShellElement& elem) {
    // Get bent node positions
    const Node* n0 = mesh.getNode(elem.nodeIds[0]);
    const Node* n1 = mesh.getNode(elem.nodeIds[1]);
    const Node* n2 = mesh.getNode(elem.nodeIds[2]);
    const Node* n3 = mesh.getNode(elem.nodeIds[3]);

    if (!n0 || !n1 || !n2 || !n3) return;

    // Edge lengths from bent mesh
    double d01 = n0->position.distanceTo(n1->position);
    double d12 = n1->position.distanceTo(n2->position);
    double d02 = n0->position.distanceTo(n2->position);  // diagonal
    double d03 = n0->position.distanceTo(n3->position);
    double d23 = n2->position.distanceTo(n3->position);

    // Place node 0 at origin
    flatPositions_[elem.nodeIds[0]] = Vector2D(0.0, 0.0);

    // Place node 1 along +X
    flatPositions_[elem.nodeIds[1]] = Vector2D(d01, 0.0);

    // Place node 2 using triangle (n0, n1, n2) with known distances
    Vector2D p2 = triangulate(
        flatPositions_[elem.nodeIds[0]],
        flatPositions_[elem.nodeIds[1]],
        d02, d12);
    flatPositions_[elem.nodeIds[2]] = p2;

    // Place node 3 using triangle (n0, n2, n3) - but we need it on the correct side
    // Use distances d03 (n0-n3) and d23 (n2-n3)
    Vector2D p3 = triangulate(
        flatPositions_[elem.nodeIds[0]],
        flatPositions_[elem.nodeIds[2]],
        d03, d23);

    // Check if p3 is on the correct side (should form a proper quad)
    // For a proper quad, n3 should be on the opposite side of diagonal n0-n2 from n1
    Vector2D diagDir = flatPositions_[elem.nodeIds[2]] - flatPositions_[elem.nodeIds[0]];
    Vector2D toN1 = flatPositions_[elem.nodeIds[1]] - flatPositions_[elem.nodeIds[0]];
    Vector2D toP3 = p3 - flatPositions_[elem.nodeIds[0]];

    double crossN1 = diagDir.cross(toN1);
    double crossP3 = diagDir.cross(toP3);

    // If both on same side, flip p3
    if (crossN1 * crossP3 > 0) {
        // Reflect p3 across the line n0-n2
        Vector2D dNorm = diagDir.normalized();
        double projLen = toP3.dot(dNorm);
        Vector2D proj = flatPositions_[elem.nodeIds[0]] + dNorm * projLen;
        p3 = proj * 2.0 - p3;
    }

    flatPositions_[elem.nodeIds[3]] = p3;
}

void ShellUnfolder::placeNeighborElement(const ShellMesh& mesh,
                                          const ShellElement& elem,
                                          int sharedNode0, int sharedNode1) {
    // The shared edge nodes already have flat positions
    const Vector2D& sp0 = flatPositions_[sharedNode0];
    const Vector2D& sp1 = flatPositions_[sharedNode1];

    // Find which nodes of the neighbor are NOT on the shared edge
    for (int i = 0; i < ShellElement::NUM_NODES; ++i) {
        int nodeId = elem.nodeIds[i];
        if (flatPositions_.find(nodeId) != flatPositions_.end()) {
            continue;  // Already placed
        }

        // Get 3D distances from this node to the shared edge nodes
        const Node* node = mesh.getNode(nodeId);
        const Node* sn0 = mesh.getNode(sharedNode0);
        const Node* sn1 = mesh.getNode(sharedNode1);
        if (!node || !sn0 || !sn1) continue;

        double d0 = node->position.distanceTo(sn0->position);
        double d1 = node->position.distanceTo(sn1->position);

        // Triangulate: compute position from sp0, sp1 and distances d0, d1
        Vector2D candidate = triangulate(sp0, sp1, d0, d1);

        // The new node must be on the opposite side of the shared edge
        // from the already-placed nodes of this element's neighbor
        // Find a node that IS already placed and is NOT on the shared edge
        // to determine which side is "taken"
        bool needFlip = false;
        for (int j = 0; j < ShellElement::NUM_NODES; ++j) {
            int otherNodeId = elem.nodeIds[j];
            if (otherNodeId == nodeId) continue;
            if (otherNodeId == sharedNode0 || otherNodeId == sharedNode1) continue;

            auto it = flatPositions_.find(otherNodeId);
            if (it != flatPositions_.end()) {
                // This is another new node of the same element that was already placed
                // They should be on the same side
                Vector2D edgeDir = sp1 - sp0;
                double crossExisting = edgeDir.cross(it->second - sp0);
                double crossCandidate = edgeDir.cross(candidate - sp0);

                // If they're on opposite sides, don't flip (they should be on the same side
                // since they're both "new" nodes of the neighbor element)
                // Actually, for a quad, the two non-shared nodes should be on the same side
                if (crossExisting * crossCandidate < 0) {
                    needFlip = true;
                }
                break;
            }
        }

        // Check against already-placed elements' nodes to ensure we go to the "empty" side
        // The neighbor element is on the opposite side of the shared edge from elements already processed
        // We need to detect which side is already occupied
        Vector2D edgeDir = sp1 - sp0;

        // Find any node from the previously processed element that shared this edge
        // It should be on the OPPOSITE side from our new nodes
        // Use the centroid of already-placed adjacent elements as reference
        // Simple heuristic: check if any already-placed node (not on edge) is on the same side
        bool foundRef = false;
        for (const auto& [nid, fp] : flatPositions_) {
            if (nid == sharedNode0 || nid == sharedNode1) continue;
            if (nid == nodeId) continue;
            if (elem.containsNode(nid)) continue;  // Skip nodes of current element

            // Check if this node belongs to a neighbor element that shares the same edge
            // Simple: just check if it's close to the shared edge midpoint
            Vector2D mid = (sp0 + sp1) * 0.5;
            Vector2D toNode = fp - mid;
            if (toNode.magnitude() < (sp1 - sp0).magnitude() * 2.0) {
                double crossRef = edgeDir.cross(fp - sp0);
                double crossCand = edgeDir.cross(candidate - sp0);
                if (crossRef * crossCand > 0) {
                    // Candidate is on same side as existing node - need flip
                    needFlip = true;
                    foundRef = true;
                    break;
                } else {
                    foundRef = true;
                    needFlip = false;
                    break;
                }
            }
        }

        if (needFlip) {
            // Reflect across the shared edge line
            Vector2D edgeNorm = edgeDir.normalized();
            Vector2D toCandidate = candidate - sp0;
            double projLen = toCandidate.dot(edgeNorm);
            Vector2D proj = sp0 + edgeNorm * projLen;
            candidate = proj * 2.0 - candidate;
        }

        flatPositions_[nodeId] = candidate;
    }
}

Vector2D ShellUnfolder::triangulate(const Vector2D& p0, const Vector2D& p1,
                                     double d0, double d1) const {
    // Find point P such that |P-p0| = d0, |P-p1| = d1
    // Place in "left" half-plane of p0->p1 by default
    Vector2D edge = p1 - p0;
    double edgeLen = edge.magnitude();

    if (edgeLen < 1e-15) {
        return Vector2D((p0.x + p1.x) * 0.5, (p0.y + p1.y) * 0.5);
    }

    // Using law of cosines: cos(alpha) = (d0^2 + edgeLen^2 - d1^2) / (2 * d0 * edgeLen)
    double cosAlpha = (d0 * d0 + edgeLen * edgeLen - d1 * d1) / (2.0 * d0 * edgeLen);
    cosAlpha = std::max(-1.0, std::min(1.0, cosAlpha));  // Clamp for numerical safety

    double sinAlpha = std::sqrt(1.0 - cosAlpha * cosAlpha);

    // Unit vectors along and perpendicular to edge
    Vector2D eHat = edge * (1.0 / edgeLen);
    Vector2D ePerp(-eHat.y, eHat.x);  // 90° CCW rotation

    // Point is at distance d0 from p0, at angle alpha from the edge direction
    return p0 + eHat * (d0 * cosAlpha) + ePerp * (d0 * sinAlpha);
}

double ShellUnfolder::computeDistortion(const ShellMesh& mesh, const ShellElement& elem) const {
    // Get bent area
    double bentArea = mesh.getElementArea(elem.id);
    if (bentArea < 1e-20) return 0.0;

    // Get flat area
    auto it0 = flatPositions_.find(elem.nodeIds[0]);
    auto it1 = flatPositions_.find(elem.nodeIds[1]);
    auto it2 = flatPositions_.find(elem.nodeIds[2]);
    auto it3 = flatPositions_.find(elem.nodeIds[3]);

    if (it0 == flatPositions_.end() || it1 == flatPositions_.end() ||
        it2 == flatPositions_.end() || it3 == flatPositions_.end()) {
        return 0.0;
    }

    // Flat area using diagonal cross product (same as 3D but in 2D)
    Vector2D d1 = it2->second - it0->second;  // diagonal 0-2
    Vector2D d2 = it3->second - it1->second;  // diagonal 1-3
    double flatArea = 0.5 * std::abs(d1.cross(d2));

    return std::abs(flatArea - bentArea) / bentArea;
}

void ShellUnfolder::getBoundingBox(Vector2D& minP, Vector2D& maxP) const {
    if (flatPositions_.empty()) {
        minP = maxP = Vector2D();
        return;
    }

    auto it = flatPositions_.begin();
    minP = maxP = it->second;
    for (++it; it != flatPositions_.end(); ++it) {
        minP.x = std::min(minP.x, it->second.x);
        minP.y = std::min(minP.y, it->second.y);
        maxP.x = std::max(maxP.x, it->second.x);
        maxP.y = std::max(maxP.y, it->second.y);
    }
}

double ShellUnfolder::getTotalLengthX() const {
    Vector2D minP, maxP;
    getBoundingBox(minP, maxP);
    return maxP.x - minP.x;
}

double ShellUnfolder::getTotalLengthY() const {
    Vector2D minP, maxP;
    getBoundingBox(minP, maxP);
    return maxP.y - minP.y;
}

std::array<Vector2D, 4> ShellUnfolder::getElementFlatPositions(const ShellElement& elem) const {
    std::array<Vector2D, 4> result;
    for (int i = 0; i < 4; ++i) {
        auto it = flatPositions_.find(elem.nodeIds[i]);
        if (it != flatPositions_.end()) {
            result[i] = it->second;
        }
    }
    return result;
}

} // namespace KooRemapper
