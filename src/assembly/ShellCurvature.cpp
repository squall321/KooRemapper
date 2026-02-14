#include "assembly/ShellCurvature.h"
#include <cmath>
#include <algorithm>
#include <iostream>

namespace KooRemapper {

Vector3D ShellCurvature::computeElementNormal(const Mesh& mesh, const Element& elem) const {
    // QUAD4: diagonal cross product for robust normal
    const auto& p0 = mesh.nodes.at(elem.nodeIds[0]).position;
    const auto& p1 = mesh.nodes.at(elem.nodeIds[1]).position;
    const auto& p2 = mesh.nodes.at(elem.nodeIds[2]).position;
    const auto& p3 = mesh.nodes.at(elem.nodeIds[3]).position;

    Vector3D d1 = p2 - p0;
    Vector3D d2 = p3 - p1;

    Vector3D normal = d1.cross(d2);
    double len = normal.magnitude();
    if (len > 1e-15) {
        normal = normal * (1.0 / len);
    }
    return normal;
}

Vector3D ShellCurvature::computeCentroid(const Mesh& mesh, const Element& elem) const {
    Vector3D c;
    for (int i = 0; i < 4; i++) {
        c += mesh.nodes.at(elem.nodeIds[i]).position;
    }
    return c * 0.25;
}

static std::pair<int,int> makeEdgeKey(int a, int b) {
    return (a < b) ? std::make_pair(a, b) : std::make_pair(b, a);
}

std::map<ShellCurvature::EdgeKey, std::vector<int>>
ShellCurvature::buildEdgeMap(const Mesh& mesh, const std::vector<int>& elemIds) const {
    std::map<EdgeKey, std::vector<int>> edgeMap;

    for (int eid : elemIds) {
        const auto& elem = mesh.elements.at(eid);
        // QUAD4 has 4 edges: (0,1), (1,2), (2,3), (3,0)
        for (int i = 0; i < 4; i++) {
            int nA = elem.nodeIds[i];
            int nB = elem.nodeIds[(i + 1) % 4];
            auto key = makeEdgeKey(nA, nB);
            edgeMap[key].push_back(eid);
        }
    }

    return edgeMap;
}

std::vector<ShellCurvatureResult> ShellCurvature::compute(
    const Mesh& mesh,
    int targetPid,
    double thickness,
    double sigy,
    double E,
    double minCurvature)
{
    normalWarnings_ = 0;
    std::vector<ShellCurvatureResult> results;

    // Collect target shell elements
    std::vector<int> targetElemIds;
    for (const auto& [eid, elem] : mesh.elements) {
        if (elem.type != ElementType::QUAD4) continue;
        if (targetPid > 0 && elem.partId != targetPid) continue;
        targetElemIds.push_back(eid);
    }

    if (targetElemIds.empty()) return results;

    // Build edge adjacency
    auto edgeMap = buildEdgeMap(mesh, targetElemIds);

    // Pre-compute normals and centroids
    std::map<int, Vector3D> normals;
    std::map<int, Vector3D> centroids;
    for (int eid : targetElemIds) {
        const auto& elem = mesh.elements.at(eid);
        normals[eid] = computeElementNormal(mesh, elem);
        centroids[eid] = computeCentroid(mesh, elem);
    }

    // For each element, find max curvature from shared edges
    std::map<int, double> maxCurvatureMap;
    for (int eid : targetElemIds) {
        maxCurvatureMap[eid] = 0.0;
    }

    for (const auto& [edge, elems] : edgeMap) {
        if (elems.size() != 2) continue;  // boundary edge -> skip

        int eidA = elems[0];
        int eidB = elems[1];

        const Vector3D& nA = normals[eidA];
        const Vector3D& nB = normals[eidB];

        // Dot product for dihedral angle
        double dot = nA.dot(nB);
        dot = std::max(-1.0, std::min(1.0, dot));  // clamp for numerical safety

        // Check for inconsistent normals
        if (dot < -0.5) {
            normalWarnings_++;
            continue;  // skip this edge
        }

        double theta = std::acos(dot);  // dihedral angle

        // L = centroid distance (issue 4 fix)
        double L = centroids[eidA].distanceTo(centroids[eidB]);
        if (L < 1e-15) continue;

        double kappa = theta / L;

        // Update max curvature for both elements
        if (kappa > maxCurvatureMap[eidA]) maxCurvatureMap[eidA] = kappa;
        if (kappa > maxCurvatureMap[eidB]) maxCurvatureMap[eidB] = kappa;
    }

    // Compute bending strain and plastic strain per element
    double yieldStrain = (E > 0) ? sigy / E : 0.0;

    for (int eid : targetElemIds) {
        double kappa = maxCurvatureMap[eid];

        // Apply minimum curvature filter
        if (kappa < minCurvature) continue;

        // Get thickness for this element
        double t = thickness;
        if (t <= 0) {
            // Auto from SECTION_SHELL via part
            const auto& elem = mesh.elements.at(eid);
            auto partIt = mesh.parts.find(elem.partId);
            if (partIt != mesh.parts.end()) {
                auto secIt = mesh.shellSections.find(partIt->second.sectionId);
                if (secIt != mesh.shellSections.end()) {
                    t = secIt->second.thickness;
                }
            }
        }
        if (t <= 0) continue;  // no thickness available

        double bendingStrain = kappa * t / 2.0;
        double plasticStrain = std::max(0.0, bendingStrain - yieldStrain);

        if (plasticStrain > 0) {
            results.push_back({eid, kappa, bendingStrain, plasticStrain});
        }
    }

    return results;
}

} // namespace KooRemapper
