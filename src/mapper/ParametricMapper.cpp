#include "mapper/ParametricMapper.h"
#include <cmath>
#include <algorithm>
#include <limits>

// Knowledge graph (lat.md):
//   @lat: [[modules/mapper]]

namespace KooRemapper {

ParametricMapper::ParametricMapper()
    : isValid_(false), useTransfinite_(true), arcAxis_(0),
      isClosedLoop_(false), hasDegenerateEdges_(false),
      gridDimI_(0), gridDimJ_(0), gridDimK_(0), gridReady_(false)
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

    // Build edge interpolators (kept for fallback path and edge-based mode).
    buildEdges(mesh, edgeCalc);

    // Build face interpolators (kept for fallback transfinite path).
    buildFaces();

    // Cache the structured-grid node positions for direct trilinear lookup.
    // This is the PRIMARY interpolation path: it uses the actual interior
    // node positions instead of reconstructing the shape from boundary
    // corners + edges, so cross-section topology (teardrop, U-channel,
    // any non-convex shape) is preserved exactly.
    gridDimI_ = boundary.getDimI();
    gridDimJ_ = boundary.getDimJ();
    gridDimK_ = boundary.getDimK();
    gridReady_ = false;
    gridFilledCount_ = 0;
    gridTotalCount_ = 0;
    if (gridDimI_ > 0 && gridDimJ_ > 0 && gridDimK_ > 0) {
        long long total = (long long)(gridDimI_ + 1) * (gridDimJ_ + 1) * (gridDimK_ + 1);
        gridTotalCount_ = total;
        gridPositions_.assign((size_t)total,
            Vector3D(std::numeric_limits<double>::quiet_NaN(),
                     std::numeric_limits<double>::quiet_NaN(),
                     std::numeric_limits<double>::quiet_NaN()));
        long long filled = 0;
        for (int i = 0; i <= gridDimI_; ++i) {
            for (int j = 0; j <= gridDimJ_; ++j) {
                for (int k = 0; k <= gridDimK_; ++k) {
                    int nodeId = boundary.getNodeAtGrid(i, j, k);
                    if (nodeId < 0) continue;
                    const Node* n = mesh.getNode(nodeId);
                    if (!n) continue;
                    gridPositions_[gridIdx(i, j, k)] = n->position;
                    ++filled;
                }
            }
        }
        gridFilledCount_ = filled;
        // Always enable grid lookup if grid was allocated. Per-cell coverage
        // is checked inside gridLookupInterpolate (NaN sentinel falls back
        // to edge-based for THAT query only). Closed-loop / shared-seam
        // topologies legitimately reduce raw fill count; we don't want a
        // global threshold to disable the better algorithm wholesale.
        gridReady_ = (filled > 0);
    }

    // Detect arc axis = bent indexer axis with the longest neutral edge length.
    // The 4 edges parallel to this axis are the dominant curvature carriers
    // and will be used as the primary interpolation direction in
    // edgeBasedInterpolate. The other two axes are treated as short
    // cross-section directions blended bilinearly.
    //
    // Why this matters: the StructuredGridIndexer can label any geometric axis
    // as "i". For closed-loop / fully-folded bent meshes (e.g. teardrop), if
    // the indexer labels the arc as j or k while leaving i as a thin
    // thickness direction, the legacy "always-use-i-edges" mapping collapses
    // along the cross-section (Jacobian = 0 everywhere) because the i-edges
    // are barely longer than a point and the j/k corners coincide at the
    // loop seam.
    double lenI = edgeCalc.getNeutralLengthI();
    double lenJ = edgeCalc.getNeutralLengthJ();
    double lenK = edgeCalc.getNeutralLengthK();
    arcAxis_ = 0;
    if (lenJ > lenI && lenJ >= lenK) arcAxis_ = 1;
    else if (lenK > lenI && lenK > lenJ) arcAxis_ = 2;

    // Topology diagnostics: detect closed-loop (coincident arc-endpoint
    // corners) and genuine edge degeneracy (coincident endpoints AND
    // collapsed interior). A valid teardrop closed loop has coincident
    // corners at the seam but the arc-direction edges curve all the way
    // around and have substantial interior length. A truly broken mesh
    // would have an edge whose entire curve is pinned to the endpoint.
    isClosedLoop_ = false;
    hasDegenerateEdges_ = false;
    topologyDiagnostic_.clear();
    validateTopology(edgeCalc);

    isValid_ = true;
}

void ParametricMapper::validateTopology(const EdgeCalculator& edgeCalc) {
    const double coincidentTol = 1e-6;

    // Corner pair structure (LS-DYNA hex ordering):
    //   i-axis endpoints:  (0<->1), (3<->2), (4<->5), (7<->6)
    //   j-axis endpoints:  (0<->3), (1<->2), (4<->7), (5<->6)
    //   k-axis endpoints:  (0<->4), (1<->5), (2<->6), (3<->7)
    // For a closed loop along axis A, all 4 pairs on that axis coincide.
    const int cornerPairs[3][4][2] = {
        {{0,1}, {3,2}, {4,5}, {7,6}},  // i
        {{0,3}, {1,2}, {4,7}, {5,6}},  // j
        {{0,4}, {1,5}, {2,6}, {3,7}}   // k
    };
    const char* axisName[3] = {"i", "j", "k"};

    for (int axis = 0; axis < 3; ++axis) {
        int coincCount = 0;
        for (int p = 0; p < 4; ++p) {
            Vector3D d = corners_[cornerPairs[axis][p][0]] -
                         corners_[cornerPairs[axis][p][1]];
            if (std::sqrt(d.x*d.x + d.y*d.y + d.z*d.z) < coincidentTol) {
                ++coincCount;
            }
        }
        if (coincCount == 4) {
            // All four corner pairs on this axis coincide. Could be a
            // valid closed loop (if the connecting edges curve around) or
            // a degenerate axis (if the edges collapse). Distinguish by
            // sampling the edge interpolators at param 0.5.
            //
            // Edge indices for each axis:
            //   axis 0 (i-edges):  0..3
            //   axis 1 (j-edges):  4..7
            //   axis 2 (k-edges):  8..11
            int eStart = axis * 4;
            int collapsedEdgeCount = 0;
            for (int e = 0; e < 4; ++e) {
                const EdgeInfo& info = edgeCalc.getEdge(eStart + e);
                if (info.points.size() < 2) { ++collapsedEdgeCount; continue; }
                // Pick a midpoint-ish sample along the edge chain.
                const Vector3D& a = info.points.front();
                const Vector3D& mid = info.points[info.points.size() / 2];
                Vector3D dm = mid - a;
                double midDist = std::sqrt(dm.x*dm.x + dm.y*dm.y + dm.z*dm.z);
                // If endpoints coincide AND midpoint also coincides with
                // them, the edge is truly degenerate (zero-length curve).
                if (midDist < coincidentTol) ++collapsedEdgeCount;
            }
            if (collapsedEdgeCount == 4) {
                // All 4 edges on this axis have zero length interior.
                // This is NOT a closed loop -- it's a broken/degenerate
                // axis and the mapping will collapse along it.
                hasDegenerateEdges_ = true;
                topologyDiagnostic_ += std::string("DEGENERATE axis ") +
                    axisName[axis] + ": all 4 edges have zero interior length. ";
            } else if (collapsedEdgeCount == 0) {
                // Clean closed loop: coincident corners but edges curve
                // around with substantial length.
                isClosedLoop_ = true;
                topologyDiagnostic_ += std::string("Closed-loop topology along ") +
                    axisName[axis] + " axis detected (valid). ";
            } else {
                // Some edges curve, some don't. Unusual; mark as
                // degenerate to be safe.
                hasDegenerateEdges_ = true;
                topologyDiagnostic_ += std::string("Partial-degenerate axis ") +
                    axisName[axis] + ": " + std::to_string(collapsedEdgeCount) +
                    "/4 edges collapsed. ";
            }
        }
    }
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

    // Primary path: trilinear lookup over the actual structured-grid
    // INTERIOR nodes. This represents the exact bent geometry (any
    // cross-section topology, including teardrop / U / closed loop) by
    // blending the 8 interior grid nodes surrounding the parametric
    // query point. Falls back to edge-based when the grid is unavailable.
    //
    // The previous edge-based-only path reconstructed shape from 8
    // boundary corners + 12 boundary edges. That works for shapes whose
    // cross-section is well-approximated by 4-corner bilinear blending
    // (cylinders, simple bends), but COLLAPSES to 1D when the cross-
    // section corners are coplanar/colinear -- which is exactly what
    // happens for teardrop battery cells where the cross-section
    // perimeter (k axis) loops back near its start point.
    if (gridReady_) {
        return gridLookupInterpolate(u, v, w);
    }
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

Vector3D ParametricMapper::gridLookupInterpolate(double u, double v, double w) const {
    // Caller (mapToPhysical) clamps u,v,w to [0,1] and checks gridReady_.
    // Convert parametric coords into floating grid index space:
    //   real_i = u * gridDimI_   (gridDimI_ is # of element layers in i;
    //                             node grid spans i in [0, gridDimI_])
    double real_i = u * (double)gridDimI_;
    double real_j = v * (double)gridDimJ_;
    double real_k = w * (double)gridDimK_;

    int i_low = (int)std::floor(real_i);
    int j_low = (int)std::floor(real_j);
    int k_low = (int)std::floor(real_k);
    if (i_low < 0) i_low = 0;
    if (j_low < 0) j_low = 0;
    if (k_low < 0) k_low = 0;
    if (i_low >= gridDimI_) i_low = gridDimI_ - 1;
    if (j_low >= gridDimJ_) j_low = gridDimJ_ - 1;
    if (k_low >= gridDimK_) k_low = gridDimK_ - 1;
    int i_high = i_low + 1;
    int j_high = j_low + 1;
    int k_high = k_low + 1;
    // i_high never exceeds gridDimI_ because i_low was clamped to gridDimI_-1
    // and the node grid has gridDimI_+1 layers indexed [0, gridDimI_].

    double ti = real_i - (double)i_low;
    double tj = real_j - (double)j_low;
    double tk = real_k - (double)k_low;
    if (ti < 0.0) ti = 0.0; else if (ti > 1.0) ti = 1.0;
    if (tj < 0.0) tj = 0.0; else if (tj > 1.0) tj = 1.0;
    if (tk < 0.0) tk = 0.0; else if (tk > 1.0) tk = 1.0;

    const Vector3D& p000 = gridPositions_[gridIdx(i_low,  j_low,  k_low )];
    const Vector3D& p100 = gridPositions_[gridIdx(i_high, j_low,  k_low )];
    const Vector3D& p010 = gridPositions_[gridIdx(i_low,  j_high, k_low )];
    const Vector3D& p110 = gridPositions_[gridIdx(i_high, j_high, k_low )];
    const Vector3D& p001 = gridPositions_[gridIdx(i_low,  j_low,  k_high)];
    const Vector3D& p101 = gridPositions_[gridIdx(i_high, j_low,  k_high)];
    const Vector3D& p011 = gridPositions_[gridIdx(i_low,  j_high, k_high)];
    const Vector3D& p111 = gridPositions_[gridIdx(i_high, j_high, k_high)];

    // Sparse-grid guard: if any of the 8 surrounding nodes is missing
    // (sentinel NaN), fall back to boundary-based edge interpolation.
    if (std::isnan(p000.x) || std::isnan(p100.x) || std::isnan(p010.x) ||
        std::isnan(p110.x) || std::isnan(p001.x) || std::isnan(p101.x) ||
        std::isnan(p011.x) || std::isnan(p111.x)) {
        return edgeBasedInterpolate(u, v, w);
    }

    double mi = 1.0 - ti, mj = 1.0 - tj, mk = 1.0 - tk;
    double w000 = mi * mj * mk;
    double w100 = ti * mj * mk;
    double w010 = mi * tj * mk;
    double w110 = ti * tj * mk;
    double w001 = mi * mj * tk;
    double w101 = ti * mj * tk;
    double w011 = mi * tj * tk;
    double w111 = ti * tj * tk;

    return Vector3D(
        p000.x * w000 + p100.x * w100 + p010.x * w010 + p110.x * w110 +
        p001.x * w001 + p101.x * w101 + p011.x * w011 + p111.x * w111,
        p000.y * w000 + p100.y * w100 + p010.y * w010 + p110.y * w110 +
        p001.y * w001 + p101.y * w101 + p011.y * w011 + p111.y * w111,
        p000.z * w000 + p100.z * w100 + p010.z * w010 + p110.z * w110 +
        p001.z * w001 + p101.z * w101 + p011.z * w011 + p111.z * w111
    );
}

Vector3D ParametricMapper::edgeBasedInterpolate(double u, double v, double w) const {
    // Interpolate using the 4 edges parallel to the auto-detected ARC axis,
    // then bilinearly blend across the two short cross-section axes.
    //
    // EdgeCalculator's edge ordering (consistent with transfiniteInterpolate):
    //   axis 0 (i-edges, vary in u): edges_[0..3] at (j,k) = (0,0),(N,0),(0,P),(N,P)
    //   axis 1 (j-edges, vary in v): edges_[4..7] at (i,k) = (0,0),(M,0),(0,P),(M,P)
    //   axis 2 (k-edges, vary in w): edges_[8..11] at (i,j) = (0,0),(M,0),(0,N),(M,N)
    //
    // For arcAxis = 0: arcRatio=u, cross=(v,w) -- i was the long arc direction (legacy default).
    // For arcAxis = 1: arcRatio=v, cross=(u,w) -- bent indexer labeled arc as j.
    // For arcAxis = 2: arcRatio=w, cross=(u,v) -- bent indexer labeled arc as k.
    //
    // Picking the long axis as the curve carrier is mandatory for closed-loop
    // bent meshes (teardrop); using the short i-edges in that case collapses
    // the cross-section blend and produces zero-Jacobian output everywhere.

    double arcRatio, ratioA, ratioB;
    int eStart;
    if (arcAxis_ == 1) {
        arcRatio = v; ratioA = u; ratioB = w; eStart = 4;
    } else if (arcAxis_ == 2) {
        arcRatio = w; ratioA = u; ratioB = v; eStart = 8;
    } else {
        arcRatio = u; ratioA = v; ratioB = w; eStart = 0;
    }

    Vector3D p00 = edges_[eStart + 0].interpolate(arcRatio);  // crossA=0, crossB=0
    Vector3D p10 = edges_[eStart + 1].interpolate(arcRatio);  // crossA=max, crossB=0
    Vector3D p01 = edges_[eStart + 2].interpolate(arcRatio);  // crossA=0, crossB=max
    Vector3D p11 = edges_[eStart + 3].interpolate(arcRatio);  // crossA=max, crossB=max

    const double mA = 1.0 - ratioA;
    const double mB = 1.0 - ratioB;
    Vector3D bottom = p00 * mA + p10 * ratioA;  // crossB=0 line
    Vector3D top    = p01 * mA + p11 * ratioA;  // crossB=max line
    return bottom * mB + top * ratioB;
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
