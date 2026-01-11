#pragma once

#include "core/Mesh.h"
#include "core/Vector3D.h"
#include "grid/BoundaryExtractor.h"
#include <vector>
#include <array>

namespace KooRemapper {

/**
 * Information about an edge of the structured grid
 */
struct EdgeInfo {
    std::vector<Vector3D> points;       // Points along the edge
    std::vector<double> segmentLengths; // Length of each segment
    double totalLength;                  // Total edge length
    int axis;                           // Which axis this edge is parallel to (0=i, 1=j, 2=k)

    // Corner indices (0-7)
    int startCorner;
    int endCorner;

    EdgeInfo() : totalLength(0.0), axis(0), startCorner(0), endCorner(0) {}

    // Get arc-length parameter for a point (0 to 1)
    double getArcLengthParameter(int pointIndex) const;

    // Interpolate position at parameter t (0 to 1)
    Vector3D interpolate(double t) const;
};

/**
 * Calculates edge lengths and related metrics for a structured grid
 */
class EdgeCalculator {
public:
    EdgeCalculator();
    ~EdgeCalculator() = default;

    /**
     * Calculate all edge information from mesh
     */
    void calculateAllEdges(const Mesh& mesh, const BoundaryExtractor& boundary);

    /**
     * Get edge information (12 edges total)
     *
     * Edge numbering:
     * i-axis edges (j,k constant):
     *   0: j=0, k=0
     *   1: j=N, k=0
     *   2: j=0, k=P
     *   3: j=N, k=P
     *
     * j-axis edges (i,k constant):
     *   4: i=0, k=0
     *   5: i=M, k=0
     *   6: i=0, k=P
     *   7: i=M, k=P
     *
     * k-axis edges (i,j constant):
     *   8: i=0, j=0
     *   9: i=M, j=0
     *   10: i=0, j=N
     *   11: i=M, j=N
     */
    const EdgeInfo& getEdge(int index) const { return edges_[index]; }
    const std::array<EdgeInfo, 12>& getAllEdges() const { return edges_; }

    /**
     * Get neutral (average) edge length for each axis
     */
    double getNeutralLengthI() const { return neutralLengthI_; }
    double getNeutralLengthJ() const { return neutralLengthJ_; }
    double getNeutralLengthK() const { return neutralLengthK_; }

    /**
     * Get average element size along each axis
     */
    double getAvgElementSizeI() const;
    double getAvgElementSizeJ() const;
    double getAvgElementSizeK() const;

    /**
     * Calculate strain (deformation) at each edge
     * Strain = (edge_length - neutral_length) / neutral_length
     */
    double getEdgeStrain(int edgeIndex) const;

    int getDimI() const { return dimI_; }
    int getDimJ() const { return dimJ_; }
    int getDimK() const { return dimK_; }

private:
    std::array<EdgeInfo, 12> edges_;

    double neutralLengthI_;
    double neutralLengthJ_;
    double neutralLengthK_;

    int dimI_, dimJ_, dimK_;

    void calculateEdge(EdgeInfo& edge, const std::vector<int>& nodeIds, const Mesh& mesh);
    void calculateNeutralLengths();
};

} // namespace KooRemapper
