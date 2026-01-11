#pragma once

#include "core/Mesh.h"
#include "core/Vector3D.h"
#include "mapper/EdgeInterpolator.h"
#include "mapper/FaceInterpolator.h"
#include "grid/EdgeCalculator.h"
#include "grid/BoundaryExtractor.h"
#include <array>

namespace KooRemapper {

/**
 * Maps parametric coordinates (u,v,w) in [0,1]^3 to physical coordinates
 * using transfinite interpolation (Gordon-Hall method)
 */
class ParametricMapper {
public:
    ParametricMapper();
    ~ParametricMapper() = default;

    /**
     * Build mapper from a bent structured mesh
     */
    void build(const Mesh& mesh, const BoundaryExtractor& boundary,
               const EdgeCalculator& edgeCalc);

    /**
     * Map parametric coordinate to physical coordinate
     * @param u Parameter along i-axis [0,1]
     * @param v Parameter along j-axis [0,1]
     * @param w Parameter along k-axis [0,1]
     * @return Physical position
     */
    Vector3D mapToPhysical(double u, double v, double w) const;

    /**
     * Simpler trilinear interpolation using only 8 corners
     */
    Vector3D trilinearInterpolate(double u, double v, double w) const;

    /**
     * Full transfinite interpolation using edges and faces
     */
    Vector3D transfiniteInterpolate(double u, double v, double w) const;

    /**
     * Edge-based interpolation using i-edges with bilinear blend in v,w
     */
    Vector3D edgeBasedInterpolate(double u, double v, double w) const;

    /**
     * Check if mapper is valid
     */
    bool isValid() const { return isValid_; }

    /**
     * Get corner positions
     */
    const std::array<Vector3D, 8>& getCorners() const { return corners_; }

private:
    // 8 corner points
    std::array<Vector3D, 8> corners_;

    // 12 edge interpolators
    std::array<EdgeInterpolator, 12> edges_;

    // 6 face interpolators
    std::array<FaceInterpolator, 6> faces_;

    bool isValid_;
    bool useTransfinite_;

    /**
     * Build edge interpolators
     */
    void buildEdges(const Mesh& mesh, const EdgeCalculator& edgeCalc);

    /**
     * Build face interpolators
     */
    void buildFaces();

    /**
     * Get edge index for given axis and position
     * axis: 0=i, 1=j, 2=k
     * For i-edges: pos = j*2 + k (where j,k are 0 or 1)
     * For j-edges: pos = i*2 + k
     * For k-edges: pos = i*2 + j
     */
    int getEdgeIndex(int axis, int pos) const;

    /**
     * Detect if this is a U-fold geometry
     * U-fold has start and end i-edges at similar X positions
     */
    bool isUFoldGeometry() const;
};

} // namespace KooRemapper
