#pragma once

#include "core/Mesh.h"
#include "core/Vector3D.h"
#include <vector>
#include <map>
#include <utility>

namespace KooRemapper {

struct ShellCurvatureResult {
    int elementId;
    double maxCurvature;      // max dihedral curvature across edges
    double maxBendingStrain;  // kappa * t/2
    double plasticStrain;     // max(0, bendingStrain - sigy/E)
};

class ShellCurvature {
public:
    std::vector<ShellCurvatureResult> compute(
        const Mesh& mesh,
        int targetPid,        // 0 = all shell parts
        double thickness,     // 0 = auto from SECTION_SHELL
        double sigy,          // yield stress
        double E,             // Young's modulus
        double minCurvature = 0.0  // noise filter
    );

    int getNormalWarnings() const { return normalWarnings_; }

private:
    int normalWarnings_ = 0;

    // Compute QUAD4 element normal via diagonal cross product
    Vector3D computeElementNormal(const Mesh& mesh, const Element& elem) const;

    // Compute element centroid
    Vector3D computeCentroid(const Mesh& mesh, const Element& elem) const;

    // Build edge adjacency: sorted(nodeA,nodeB) -> list of element IDs
    using EdgeKey = std::pair<int, int>;
    std::map<EdgeKey, std::vector<int>> buildEdgeMap(
        const Mesh& mesh, const std::vector<int>& elemIds) const;
};

} // namespace KooRemapper
