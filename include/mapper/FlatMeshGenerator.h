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

    // Results
    double flatLengthI_;
    double flatLengthJ_;
    double flatLengthK_;
    int dimI_, dimJ_, dimK_;

    // Cross-section axis directions (in bent mesh local coordinates)
    // These are determined by analyzing the first cross-section
    Vector3D jAxisDir_;  // Direction of J axis in bent mesh
    Vector3D kAxisDir_;  // Direction of K axis in bent mesh

    std::string errorMessage_;

    // Internal mesh copy for analysis
    Mesh analyzedMesh_;

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
     * Get node at grid position from analyzed mesh
     */
    const Node* getNodeAt(int i, int j, int k) const;

    /**
     * Analyze cross-section at i=0 to determine J and K axis directions
     */
    void analyzeCrossSectionAxes();
};

} // namespace KooRemapper
