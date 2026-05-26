#pragma once

#include "core/ShellElement.h"
#include "mapper/ShellUnfolder.h"
#include <map>
#include <vector>
#include <unordered_map>
#include <cstdint>
#include <array>

// Knowledge graph (lat.md):
//   @lat: [[modules/util]]

namespace KooRemapper {

/**
 * 2D spatial hash for fast point-in-element queries
 *
 * Divides the 2D plane into grid cells and maps each cell to the
 * list of shell elements whose bounding boxes overlap that cell.
 * Used to accelerate finding which flat shell element contains a given point.
 */
class SpatialHash2D {
public:
    SpatialHash2D() = default;

    /**
     * Build the spatial hash from flat shell elements
     * @param elements Shell element map
     * @param flatPositions Flat (unfolded) 2D positions of nodes
     */
    void build(const std::map<int, ShellElement>& elements,
               const std::map<int, Vector2D>& flatPositions);

    /**
     * Find the element containing point (x,y) and compute local coordinates
     * @param x X coordinate
     * @param y Y coordinate
     * @param xi Output: local xi coordinate [-1, 1]
     * @param eta Output: local eta coordinate [-1, 1]
     * @return Element ID, or -1 if not found
     */
    int findContainingElement(double x, double y, double& xi, double& eta) const;

    /**
     * Get candidate elements near point (x,y) (broad phase)
     */
    std::vector<int> getCandidateElements(double x, double y) const;

private:
    double cellSize_ = 1.0;
    double originX_ = 0.0;
    double originY_ = 0.0;

    // Cell hash -> list of element IDs
    std::unordered_map<int64_t, std::vector<int>> cells_;

    // Cached element data for fast queries
    struct ElementData {
        int id;
        std::array<Vector2D, 4> vertices;
    };
    std::map<int, ElementData> elementData_;

    int64_t hashCell(int cx, int cy) const {
        return static_cast<int64_t>(cx) * 1000000007LL + static_cast<int64_t>(cy);
    }

    std::pair<int, int> getCellIndex(double x, double y) const {
        int cx = static_cast<int>(std::floor((x - originX_) / cellSize_));
        int cy = static_cast<int>(std::floor((y - originY_) / cellSize_));
        return {cx, cy};
    }

    // Point-in-quad test using cross products
    bool isPointInQuad(double x, double y, const std::array<Vector2D, 4>& verts) const;

    // Compute bilinear local coordinates (xi, eta) via Newton-Raphson
    bool computeLocalCoords(double x, double y,
                           const std::array<Vector2D, 4>& verts,
                           double& xi, double& eta) const;

    // QUAD4 shape functions at (xi, eta)
    static std::array<double, 4> shapeFunctions(double xi, double eta);
};

} // namespace KooRemapper
