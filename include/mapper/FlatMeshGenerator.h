#pragma once

#include "core/Mesh.h"
#include "grid/ConnectivityAnalyzer.h"
#include "grid/StructuredGridIndexer.h"
#include "grid/BoundaryExtractor.h"
#include "grid/EdgeCalculator.h"
#include <string>

namespace KooRemapper {

/**
 * Generates a flat (unfolded) mesh from a bent structured mesh
 *
 * The algorithm:
 * 1. Analyze the bent mesh to get structured indices
 * 2. Extract the centerline (z-center) and compute arc-length along i-direction
 * 3. Compute cross-section size from j-k plane
 * 4. Generate flat nodes with X = arc-length, Y = local j, Z = local k
 */
class FlatMeshGenerator {
public:
    FlatMeshGenerator();
    ~FlatMeshGenerator() = default;

    /**
     * Generate flat mesh from bent mesh
     * @param bentMesh The bent structured mesh (must be HEX8)
     * @return The generated flat mesh
     */
    Mesh generateFlatMesh(const Mesh& bentMesh);

    /**
     * Get error message if generation failed
     */
    const std::string& getErrorMessage() const { return errorMessage_; }

    /**
     * Get computed dimensions
     */
    double getFlatLengthI() const { return flatLengthI_; }
    double getFlatLengthJ() const { return flatLengthJ_; }
    double getFlatLengthK() const { return flatLengthK_; }

    /**
     * Get grid dimensions
     */
    int getDimI() const { return dimI_; }
    int getDimJ() const { return dimJ_; }
    int getDimK() const { return dimK_; }

private:
    // Analysis components
    ConnectivityAnalyzer connectivity_;
    StructuredGridIndexer indexer_;
    BoundaryExtractor boundary_;
    EdgeCalculator edgeCalc_;

    // Results (flat-axis-oriented; see axisPerm_ for bent<->flat mapping)
    double flatLengthI_;
    double flatLengthJ_;
    double flatLengthK_;
    int dimI_, dimJ_, dimK_;

    // Bent-mesh indexer dimensions (raw, before axis permutation).
    int bentDimI_, bentDimJ_, bentDimK_;

    // Axis permutation: axisPerm_[flatAxis] = bent indexer axis.
    //   axisPerm_[0] = which bent axis (0=i,1=j,2=k) is the ARC (longest edge length)
    //   axisPerm_[1] = which bent axis is flat Y (width)
    //   axisPerm_[2] = which bent axis is flat Z (thickness)
    // All getNodeAt/element lookups in this class go through this permutation
    // so the flat coordinate frame is consistent regardless of how the
    // indexer happened to label axes on the input mesh.
    int axisPerm_[3];

    // Cross-section axis directions (in bent mesh local coordinates)
    // These are determined by analyzing the first cross-section
    Vector3D jAxisDir_;  // Direction of J axis in bent mesh
    Vector3D kAxisDir_;  // Direction of K axis in bent mesh

    std::string errorMessage_;

    // Internal mesh copies
    Mesh originalMesh_;   // Original bent mesh (preserves original element connectivity)
    Mesh analyzedMesh_;   // Modified copy with reordered nodes for indexing

    /**
     * Analyze bent mesh structure
     */
    bool analyzeBentMesh(const Mesh& bentMesh);

    /**
     * Calculate flat dimensions from bent mesh
     * - X length: arc-length along center line (z=center of k)
     * - Y length: average j-edge length
     * - Z length: average k-edge length
     */
    void calculateFlatDimensions();

    /**
     * Compute center-line arc-length for each i-layer
     * Returns cumulative arc-length at each i position
     */
    std::vector<double> computeCenterlineArcLengths();

    /**
     * Generate the flat mesh nodes and elements
     */
    Mesh generateMesh();

    /**
     * Get node at FLAT-axis grid position (fi, fj, fk).
     * Internally permutes to bent-axis indices via axisPerm_ and calls
     * getNodeAtBent. Use this from all post-permutation code paths
     * (generateMesh, detectApexShift, analyzeCrossSectionAxes, etc.).
     */
    const Node* getNodeAt(int fi, int fj, int fk) const;

    /**
     * Get node at raw BENT-axis grid position (bi, bj, bk).
     * Bypasses axis permutation -- use this only during axis detection
     * inside analyzeBentMesh, before axisPerm_ is finalized.
     */
    const Node* getNodeAtBent(int bi, int bj, int bk) const;

    /**
     * Analyze cross-section at i=0 to determine J and K axis directions
     */
    void analyzeCrossSectionAxes();

    /**
     * Detect optimal cyclic shift for closed-loop bent meshes.
     *
     * Returns the amount to cyclic-shift i indexing so that new i=0 lands at
     * the lowest-curvature point on the centerline. This puts the mesh's
     * fold apex (max curvature) at the middle of the unfold, giving a
     * symmetric, intuitive flat layout.
     *
     * Returns 0 if the mesh is not a closed loop (fewer than 80% of
     * cross-section nodes shared between i=0 and i=dimI), or if the
     * lowest-curvature point already coincides with i=0.
     */
    int detectApexShift();
};

} // namespace KooRemapper
