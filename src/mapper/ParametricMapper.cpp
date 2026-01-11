#include "mapper/ParametricMapper.h"
#include <cmath>
#include <algorithm>

namespace KooRemapper {

ParametricMapper::ParametricMapper()
    : isValid_(false), useTransfinite_(true)
{}

void ParametricMapper::build(const Mesh& mesh, const BoundaryExtractor& boundary,
                              const EdgeCalculator& edgeCalc) {
    isValid_ = false;

    // Get corner nodes
    auto cornerNodeIds = boundary.getCornerNodes();

    // Get corner positions
    for (int i = 0; i < 8; ++i) {
        const Node* node = mesh.getNode(cornerNodeIds[i]);
        if (node) {
            corners_[i] = node->position;
        } else {
            return;  // Invalid - missing corner node
        }
    }

    // Build edge interpolators
    buildEdges(mesh, edgeCalc);

    // Build face interpolators
    buildFaces();

    isValid_ = true;
}

void ParametricMapper::buildEdges(const Mesh& mesh, const EdgeCalculator& edgeCalc) {
    (void)mesh;  // Suppress unused warning
    // Copy edge data from EdgeCalculator
    for (int i = 0; i < 12; ++i) {
        const EdgeInfo& info = edgeCalc.getEdge(i);
        edges_[i].build(info.points);
    }
}

void ParametricMapper::buildFaces() {
    // Face 0: i=0 (u=0), varies in v,w
    faces_[0].buildBilinear(corners_[0], corners_[3], corners_[4], corners_[7]);

    // Face 1: i=M (u=1)
    faces_[1].buildBilinear(corners_[1], corners_[2], corners_[5], corners_[6]);

    // Face 2: j=0 (v=0)
    faces_[2].buildBilinear(corners_[0], corners_[1], corners_[4], corners_[5]);

    // Face 3: j=N (v=1)
    faces_[3].buildBilinear(corners_[3], corners_[2], corners_[7], corners_[6]);

    // Face 4: k=0 (w=0)
    faces_[4].buildBilinear(corners_[0], corners_[1], corners_[3], corners_[2]);

    // Face 5: k=P (w=1)
    faces_[5].buildBilinear(corners_[4], corners_[5], corners_[7], corners_[6]);
}

Vector3D ParametricMapper::mapToPhysical(double u, double v, double w) const {
    if (!isValid_) return Vector3D();

    // Clamp to valid range
    u = std::max(0.0, std::min(1.0, u));
    v = std::max(0.0, std::min(1.0, v));
    w = std::max(0.0, std::min(1.0, w));

    // Always use edge-based interpolation for structured grids
    // This ensures bent -> unfold -> remap returns exact original positions
    // when the flat mesh is generated from the bent mesh.
    //
    // Edge-based interpolation uses the actual edge curves and bilinear
    // interpolation in the cross-section plane, which is more accurate
    // for structured hex meshes than Gordon-Hall transfinite interpolation.
    //
    // For unstructured or refined flat meshes mapped to bent reference,
    // edge-based still works well because edges define the deformation field.
    return edgeBasedInterpolate(u, v, w);
}

bool ParametricMapper::isUFoldGeometry() const {
    // Check if start and end X coordinates of i-edges are similar
    // This indicates a U-fold shape where the mesh folds back on itself
    double startX = corners_[0].x;
    double endX = corners_[1].x;

    // Estimate mesh size from various directions
    double meshSize = std::max({
        std::abs(corners_[1].x - corners_[0].x),
        std::abs(corners_[1].y - corners_[0].y),
        std::abs(corners_[1].z - corners_[0].z),
        std::abs(corners_[5].x - corners_[0].x),
        std::abs(corners_[5].z - corners_[0].z),
        std::abs(corners_[4].x - corners_[0].x),
        std::abs(corners_[4].y - corners_[0].y)
    });

    if (meshSize < 1e-10) return false;

    double xDiff = std::abs(endX - startX);

    // If X difference is less than 10% of mesh extent, it's likely U-fold
    return (xDiff / meshSize) < 0.1;
}

Vector3D ParametricMapper::edgeBasedInterpolate(double u, double v, double w) const {
    // Interpolate using edges directly
    // For structured grids, this gives exact results at grid nodes
    
    const double mu = 1.0 - u;
    const double mv = 1.0 - v;
    const double mw = 1.0 - w;
    
    // Get points on the 4 i-edges at this u
    Vector3D p00 = edges_[0].interpolate(u);  // j=0, k=0
    Vector3D p10 = edges_[1].interpolate(u);  // j=N, k=0
    Vector3D p01 = edges_[2].interpolate(u);  // j=0, k=P
    Vector3D p11 = edges_[3].interpolate(u);  // j=N, k=P
    
    // Bilinear interpolation in v,w at this u-slice
    Vector3D bottom = p00 * mv + p10 * v;  // k=0 line
    Vector3D top = p01 * mv + p11 * v;     // k=P line
    
    return bottom * mw + top * w;
}

Vector3D ParametricMapper::trilinearInterpolate(double u, double v, double w) const {
    // Trilinear interpolation using 8 corners
    // Fast path for simple cases
    const double mu = 1.0 - u;
    const double mv = 1.0 - v;
    const double mw = 1.0 - w;

    // Pre-compute weight products
    const double w000 = mu * mv * mw;
    const double w100 = u * mv * mw;
    const double w110 = u * v * mw;
    const double w010 = mu * v * mw;
    const double w001 = mu * mv * w;
    const double w101 = u * mv * w;
    const double w111 = u * v * w;
    const double w011 = mu * v * w;

    return Vector3D(
        corners_[0].x * w000 + corners_[1].x * w100 + corners_[2].x * w110 + corners_[3].x * w010 +
        corners_[4].x * w001 + corners_[5].x * w101 + corners_[6].x * w111 + corners_[7].x * w011,
        corners_[0].y * w000 + corners_[1].y * w100 + corners_[2].y * w110 + corners_[3].y * w010 +
        corners_[4].y * w001 + corners_[5].y * w101 + corners_[6].y * w111 + corners_[7].y * w011,
        corners_[0].z * w000 + corners_[1].z * w100 + corners_[2].z * w110 + corners_[3].z * w010 +
        corners_[4].z * w001 + corners_[5].z * w101 + corners_[6].z * w111 + corners_[7].z * w011
    );
}

Vector3D ParametricMapper::transfiniteInterpolate(double u, double v, double w) const {
    // Gordon-Hall transfinite interpolation
    // P(u,v,w) = P_faces - P_edges + P_corners
    // This provides C0 continuity at faces and better shape preservation

    const double mu = 1.0 - u;
    const double mv = 1.0 - v;
    const double mw = 1.0 - w;

    // Pre-compute commonly used weight products for edges
    const double mv_mw = mv * mw;
    const double v_mw = v * mw;
    const double mv_w = mv * w;
    const double v_w = v * w;
    const double mu_mw = mu * mw;
    const double u_mw = u * mw;
    const double mu_w = mu * w;
    const double u_w = u * w;
    const double mu_mv = mu * mv;
    const double u_mv = u * mv;
    const double mu_v = mu * v;
    const double u_v = u * v;

    // Face contributions - use edge-based Coons patches for better accuracy
    Vector3D Pf;
    Pf = faces_[0].interpolate(v, w) * mu;
    Pf += faces_[1].interpolate(v, w) * u;
    Pf += faces_[2].interpolate(u, w) * mv;
    Pf += faces_[3].interpolate(u, w) * v;
    Pf += faces_[4].interpolate(u, v) * mw;
    Pf += faces_[5].interpolate(u, v) * w;

    // Edge contributions (subtract) - use actual edge curves for accuracy
    Vector3D Pe;
    // i-edges (vary in u)
    Pe = edges_[0].interpolate(u) * mv_mw;   // j=0, k=0
    Pe += edges_[1].interpolate(u) * v_mw;   // j=N, k=0
    Pe += edges_[2].interpolate(u) * mv_w;   // j=0, k=P
    Pe += edges_[3].interpolate(u) * v_w;    // j=N, k=P
    // j-edges (vary in v)
    Pe += edges_[4].interpolate(v) * mu_mw;  // i=0, k=0
    Pe += edges_[5].interpolate(v) * u_mw;   // i=M, k=0
    Pe += edges_[6].interpolate(v) * mu_w;   // i=0, k=P
    Pe += edges_[7].interpolate(v) * u_w;    // i=M, k=P
    // k-edges (vary in w)
    Pe += edges_[8].interpolate(w) * mu_mv;  // i=0, j=0
    Pe += edges_[9].interpolate(w) * u_mv;   // i=M, j=0
    Pe += edges_[10].interpolate(w) * mu_v;  // i=0, j=N
    Pe += edges_[11].interpolate(w) * u_v;   // i=M, j=N

    // Corner contributions (add back)
    Vector3D Pc;
    Pc = corners_[0] * (mu * mv_mw);
    Pc += corners_[1] * (u * mv_mw);
    Pc += corners_[2] * (u * v_mw);
    Pc += corners_[3] * (mu * v_mw);
    Pc += corners_[4] * (mu * mv_w);
    Pc += corners_[5] * (u * mv_w);
    Pc += corners_[6] * (u * v_w);
    Pc += corners_[7] * (mu * v_w);

    return Pf - Pe + Pc;
}

int ParametricMapper::getEdgeIndex(int axis, int pos) const {
    // axis 0 (i-edges): indices 0-3
    // axis 1 (j-edges): indices 4-7
    // axis 2 (k-edges): indices 8-11
    return axis * 4 + pos;
}

} // namespace KooRemapper
