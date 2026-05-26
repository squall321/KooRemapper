#pragma once

#include "core/Mesh.h"
#include "core/Vector3D.h"
#include "mapper/EdgeInterpolator.h"
#include "mapper/FaceInterpolator.h"
#include "grid/EdgeCalculator.h"
#include "grid/BoundaryExtractor.h"
#include <array>
#include <string>
#include <vector>

// Knowledge graph (lat.md):
//   @lat: [[modules/mapper]]

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
     * Structured-grid trilinear lookup interpolation.
     *
     * Uses the bent mesh's INTERIOR node grid (built by BoundaryExtractor)
     * directly: (u,v,w) is converted to floating grid coords, the 8
     * surrounding grid nodes are looked up, and trilinear blend is computed
     * from their physical positions.
     *
     * This is the PRIMARY interpolation path because it preserves the
     * actual cross-section shape (e.g. teardrop, U-channel, any topology
     * where the boundary corners are coplanar/colinear and edge-based
     * Coons-style interpolation collapses).
     *
     * Falls back to edgeBasedInterpolate if the node grid is unavailable
     * (e.g. mesh failed structured indexing, or the requested grid cell
     * has missing nodes from a sparse indexing).
     */
    Vector3D gridLookupInterpolate(double u, double v, double w) const;

    /**
     * Check if mapper is valid
     */
    bool isValid() const { return isValid_; }

    /**
     * Get corner positions
     */
    const std::array<Vector3D, 8>& getCorners() const { return corners_; }

    /**
     * Get the auto-detected arc axis (0=i, 1=j, 2=k).
     * This is the axis with the longest neutral edge length and is the
     * dominant interpolation direction in edgeBasedInterpolate.
     */
    int getArcAxis() const { return arcAxis_; }

    /**
     * True if the bent mesh has a closed-loop topology along the arc axis
     * (e.g. teardrop battery cell). Detected in build() by checking if the
     * 4 corner pairs at the arc-axis endpoints coincide. Callers can use
     * this for diagnostics or specialized wrap-around handling.
     */
    bool isClosedLoop() const { return isClosedLoop_; }

    /**
     * True if at least one edge of the parametric box was flagged as
     * degenerate in build() (coincident endpoints AND the interior of
     * the edge curve also collapsed to the endpoint within tolerance).
     * A genuine closed loop has coincident endpoints but a non-trivial
     * interior, so this flag separates "valid closed loop" from "broken".
     */
    bool hasDegenerateEdges() const { return hasDegenerateEdges_; }

    /**
     * Diagnostic message produced during build() for closed-loop and edge
     * validation. Empty if no issues were detected.
     */
    const std::string& getTopologyDiagnostic() const { return topologyDiagnostic_; }

private:
    // 8 corner points
    std::array<Vector3D, 8> corners_;

    // 12 edge interpolators
    std::array<EdgeInterpolator, 12> edges_;

    // 6 face interpolators
    std::array<FaceInterpolator, 6> faces_;

    // Cached interior node grid for trilinear lookup.
    //   gridDimI_, gridDimJ_, gridDimK_ are ELEMENT dimensions (so the
    //   node grid has (dimI+1) x (dimJ+1) x (dimK+1) positions).
    //   gridPositions_ is laid out as a flat vector indexed by
    //   ((i * (dimJ+1) + j) * (dimK+1) + k) for cache-friendly trilinear
    //   access. Missing/sparse positions store NaN x-component as a
    //   sentinel (gridLookupInterpolate falls back to edgeBased on miss).
    int gridDimI_, gridDimJ_, gridDimK_;
    std::vector<Vector3D> gridPositions_;
    bool gridReady_;
    long long gridFilledCount_;
    long long gridTotalCount_;

public:
    /** Diagnostic: how many of (dimI+1)*(dimJ+1)*(dimK+1) grid positions
     *  got a valid node ID. < total means closed-loop seams or partial
     *  indexing (still safe -- per-cell fallback handles it). */
    long long getGridFilledCount() const { return gridFilledCount_; }
    long long getGridTotalCount()  const { return gridTotalCount_; }
    bool isGridLookupActive() const { return gridReady_; }
private:

    inline int gridIdx(int i, int j, int k) const {
        return (i * (gridDimJ_ + 1) + j) * (gridDimK_ + 1) + k;
    }

    bool isValid_;
    bool useTransfinite_;

    // Auto-detected arc axis (0=i, 1=j, 2=k). The 4 edges parallel to this
    // axis carry the curvature; the other two axes are short cross-section
    // directions used for bilinear blending in edgeBasedInterpolate. Set in
    // build() from EdgeCalculator's neutral edge lengths.
    int arcAxis_;

    // Closed-loop / degenerate-edge flags set in build().
    bool isClosedLoop_;
    bool hasDegenerateEdges_;
    std::string topologyDiagnostic_;

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

    /**
     * Closed-loop / degenerate-edge detection. For each axis (i, j, k):
     * if all 4 corner pairs at the axis endpoints coincide, sample each
     * of the 4 edges' midpoints. Distinguish:
     *   - Valid closed loop: midpoints far from endpoints (curve wraps).
     *   - Degenerate axis: midpoints also coincide with endpoints.
     * Updates isClosedLoop_, hasDegenerateEdges_, topologyDiagnostic_.
     */
    void validateTopology(const EdgeCalculator& edgeCalc);
};

} // namespace KooRemapper
