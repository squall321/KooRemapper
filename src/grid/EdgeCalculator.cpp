#include "grid/EdgeCalculator.h"
#include <algorithm>
#include <numeric>

namespace KooRemapper {

double EdgeInfo::getArcLengthParameter(int pointIndex) const {
    if (pointIndex <= 0 || totalLength <= 0) return 0.0;
    if (pointIndex >= static_cast<int>(points.size()) - 1) return 1.0;

    double length = 0.0;
    for (int i = 0; i < pointIndex; ++i) {
        length += segmentLengths[i];
    }
    return length / totalLength;
}

Vector3D EdgeInfo::interpolate(double t) const {
    if (points.empty()) return Vector3D();
    if (t <= 0.0) return points.front();
    if (t >= 1.0) return points.back();

    // Index-based interpolation: t maps directly to point indices
    // t=0 -> index 0, t=1 -> index (n-1)
    // This ensures that t = i/dimI returns the exact position at index i
    //
    // For a mesh with n points (indices 0 to n-1):
    // t = i / (n-1) should return points[i]

    int n = static_cast<int>(points.size());
    if (n < 2) return points.front();

    double scaledT = t * (n - 1);
    int idx = static_cast<int>(scaledT);
    double localT = scaledT - idx;

    // Clamp index
    if (idx >= n - 1) {
        return points.back();
    }

    return Vector3D::lerp(points[idx], points[idx + 1], localT);
}

EdgeCalculator::EdgeCalculator()
    : neutralLengthI_(0), neutralLengthJ_(0), neutralLengthK_(0)
    , dimI_(0), dimJ_(0), dimK_(0)
{}

void EdgeCalculator::calculateAllEdges(const Mesh& mesh, const BoundaryExtractor& boundary) {
    dimI_ = boundary.getDimI();
    dimJ_ = boundary.getDimJ();
    dimK_ = boundary.getDimK();

    const auto& edgeNodes = boundary.getEdgeNodes();

    // Calculate each edge
    for (int i = 0; i < 12; ++i) {
        edges_[i].axis = edgeNodes[i].axis;
        calculateEdge(edges_[i], edgeNodes[i].nodeIds, mesh);
    }

    // Set corner indices for each edge
    // i-axis edges
    edges_[0].startCorner = 0; edges_[0].endCorner = 1;  // j=0, k=0
    edges_[1].startCorner = 3; edges_[1].endCorner = 2;  // j=N, k=0
    edges_[2].startCorner = 4; edges_[2].endCorner = 5;  // j=0, k=P
    edges_[3].startCorner = 7; edges_[3].endCorner = 6;  // j=N, k=P

    // j-axis edges
    edges_[4].startCorner = 0; edges_[4].endCorner = 3;  // i=0, k=0
    edges_[5].startCorner = 1; edges_[5].endCorner = 2;  // i=M, k=0
    edges_[6].startCorner = 4; edges_[6].endCorner = 7;  // i=0, k=P
    edges_[7].startCorner = 5; edges_[7].endCorner = 6;  // i=M, k=P

    // k-axis edges
    edges_[8].startCorner = 0; edges_[8].endCorner = 4;   // i=0, j=0
    edges_[9].startCorner = 1; edges_[9].endCorner = 5;   // i=M, j=0
    edges_[10].startCorner = 3; edges_[10].endCorner = 7; // i=0, j=N
    edges_[11].startCorner = 2; edges_[11].endCorner = 6; // i=M, j=N

    calculateNeutralLengths();
}

void EdgeCalculator::calculateEdge(EdgeInfo& edge, const std::vector<int>& nodeIds,
                                   const Mesh& mesh) {
    edge.points.clear();
    edge.segmentLengths.clear();
    edge.totalLength = 0.0;

    // Collect points
    for (int nodeId : nodeIds) {
        const Node* node = mesh.getNode(nodeId);
        if (node) {
            edge.points.push_back(node->position);
        }
    }

    // Calculate segment lengths
    for (size_t i = 0; i + 1 < edge.points.size(); ++i) {
        double length = edge.points[i].distanceTo(edge.points[i + 1]);
        edge.segmentLengths.push_back(length);
        edge.totalLength += length;
    }
}

void EdgeCalculator::calculateNeutralLengths() {
    // Neutral length is the average of all edges along that axis

    // i-axis edges: 0, 1, 2, 3
    double sumI = 0.0;
    for (int i = 0; i < 4; ++i) {
        sumI += edges_[i].totalLength;
    }
    neutralLengthI_ = sumI / 4.0;

    // j-axis edges: 4, 5, 6, 7
    double sumJ = 0.0;
    for (int i = 4; i < 8; ++i) {
        sumJ += edges_[i].totalLength;
    }
    neutralLengthJ_ = sumJ / 4.0;

    // k-axis edges: 8, 9, 10, 11
    double sumK = 0.0;
    for (int i = 8; i < 12; ++i) {
        sumK += edges_[i].totalLength;
    }
    neutralLengthK_ = sumK / 4.0;
}

double EdgeCalculator::getAvgElementSizeI() const {
    return (dimI_ > 0) ? neutralLengthI_ / dimI_ : 0.0;
}

double EdgeCalculator::getAvgElementSizeJ() const {
    return (dimJ_ > 0) ? neutralLengthJ_ / dimJ_ : 0.0;
}

double EdgeCalculator::getAvgElementSizeK() const {
    return (dimK_ > 0) ? neutralLengthK_ / dimK_ : 0.0;
}

double EdgeCalculator::getEdgeStrain(int edgeIndex) const {
    if (edgeIndex < 0 || edgeIndex >= 12) return 0.0;

    double neutralLength;
    switch (edges_[edgeIndex].axis) {
        case 0: neutralLength = neutralLengthI_; break;
        case 1: neutralLength = neutralLengthJ_; break;
        case 2: neutralLength = neutralLengthK_; break;
        default: return 0.0;
    }

    if (neutralLength <= 0) return 0.0;

    return (edges_[edgeIndex].totalLength - neutralLength) / neutralLength;
}

} // namespace KooRemapper
