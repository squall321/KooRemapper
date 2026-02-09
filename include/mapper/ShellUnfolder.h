#pragma once

#include "core/ShellMesh.h"
#include "core/Vector3D.h"
#include "generator/CurveInterpolator.h"  // For Vector2D
#include <map>
#include <vector>

namespace KooRemapper {

/**
 * Edge-length preserving shell unfolder
 *
 * Takes a bent QUAD4 shell mesh and flattens it onto the XY plane
 * while preserving edge lengths. Uses BFS propagation from a start element.
 *
 * For developable surfaces (single curvature), the unfolding is exact.
 * For non-developable surfaces, a distortion warning is issued.
 */
class ShellUnfolder {
public:
    ShellUnfolder() = default;

    /**
     * Unfold the bent shell mesh onto the XY plane
     * @param bentShell The bent shell mesh (with connectivity built)
     * @return true on success
     */
    bool unfold(const ShellMesh& bentShell);

    // Results
    const std::map<int, Vector2D>& getFlatPositions() const { return flatPositions_; }

    // Get bounding box of unfolded mesh
    void getBoundingBox(Vector2D& minP, Vector2D& maxP) const;
    double getTotalLengthX() const;
    double getTotalLengthY() const;

    // Distortion metrics
    double getMaxDistortion() const { return maxDistortion_; }
    double getAvgDistortion() const { return avgDistortion_; }

    // Get the flat node positions for a specific element
    std::array<Vector2D, 4> getElementFlatPositions(const ShellElement& elem) const;

private:
    std::map<int, Vector2D> flatPositions_;  // nodeId -> 2D position
    double maxDistortion_ = 0.0;
    double avgDistortion_ = 0.0;

    // Place the first element on the XY plane
    void placeStartElement(const ShellMesh& mesh, const ShellElement& elem);

    // Place a neighbor element across a shared edge
    void placeNeighborElement(const ShellMesh& mesh,
                              const ShellElement& elem,
                              int sharedNode0, int sharedNode1);

    // Compute 2D position from two known points and distances
    // Returns the point on the "left" side of p0->p1 direction
    Vector2D triangulate(const Vector2D& p0, const Vector2D& p1,
                         double d0, double d1) const;

    // Compute area distortion between bent and flat element
    double computeDistortion(const ShellMesh& mesh, const ShellElement& elem) const;
};

} // namespace KooRemapper
