#include "remesh/LocalImproveRemesher.h"
#include <algorithm>
#include <array>
#include <cmath>
#include <limits>
#include <set>
#include <sstream>
#include <unordered_map>
#include <vector>

// Knowledge graph (lat.md):
//   @lat: [[modules/remesh]]

namespace KooRemapper {
namespace remesh {

namespace {

double tetSignedVolume(const Vector3D& p0, const Vector3D& p1,
                       const Vector3D& p2, const Vector3D& p3) {
    Vector3D e1 = p1 - p0;
    Vector3D e2 = p2 - p0;
    Vector3D e3 = p3 - p0;
    return e1.dot(e2.cross(e3)) / 6.0;
}

double tetMinJac(const Vector3D& p0, const Vector3D& p1,
                 const Vector3D& p2, const Vector3D& p3) {
    // Scaled Jacobian: 1.0 = equilateral perfect, 0 = degenerate, <0 = inverted.
    // See PatchExtractor.cpp for the full derivation. Same metric is used so
    // patch-side detection and backend-side quality scoring agree.
    double V = tetSignedVolume(p0, p1, p2, p3);
    double e01 = (p1 - p0).magnitude();
    double e02 = (p2 - p0).magnitude();
    double e03 = (p3 - p0).magnitude();
    double e12 = (p2 - p1).magnitude();
    double e13 = (p3 - p1).magnitude();
    double e23 = (p3 - p2).magnitude();
    double maxEdge = std::max({e01, e02, e03, e12, e13, e23});
    if (maxEdge < 1e-12) return 0.0;
    static const double EQUILATERAL_NORM = 0.11785113019775793;  // sqrt(2)/12
    return (V / (maxEdge * maxEdge * maxEdge)) / EQUILATERAL_NORM;
}

// Return signed Jacobian-quality of a tet from result-state vectors.
double tetQuality(const std::vector<PatchNode>& nodes, const PatchTet& t) {
    return tetMinJac(nodes[t.n[0]].position,
                     nodes[t.n[1]].position,
                     nodes[t.n[2]].position,
                     nodes[t.n[3]].position);
}

// Project a 3D vector onto the plane defined by unit normal n.
Vector3D projectToPlane(const Vector3D& v, const Vector3D& n) {
    double d = v.dot(n);
    return Vector3D(v.x - d * n.x, v.y - d * n.y, v.z - d * n.z);
}

// Apply node.moveTolerance constraint relative to original position.
Vector3D clampToTolerance(const Vector3D& proposed, const Vector3D& original,
                          double tol) {
    if (tol <= 0.0) return proposed;
    Vector3D delta = proposed - original;
    double mag = delta.magnitude();
    if (mag <= tol) return proposed;
    return original + delta * (tol / mag);
}

// One Laplacian smoothing pass over free nodes.
//   For each free node, set its proposed position to the centroid of
//   the incident-TET centroids. Apply tangent projection (free surface
//   nodes) and moveTolerance clamp. Reject the move if any incident TET
//   would flip sign.
int smoothPass(std::vector<PatchNode>& nodes,
               const std::vector<PatchTet>& tets,
               const std::vector<Vector3D>& original) {
    // node -> incident tet indices
    std::vector<std::vector<int>> nodeToTet(nodes.size());
    for (int ti = 0; ti < (int)tets.size(); ++ti) {
        for (int v = 0; v < 4; ++v) nodeToTet[tets[ti].n[v]].push_back(ti);
    }

    int moved = 0;
    for (size_t ni = 0; ni < nodes.size(); ++ni) {
        PatchNode& pn = nodes[ni];
        if (pn.isFixed) continue;
        if (nodeToTet[ni].empty()) continue;

        // Centroid of incident-tet centroids
        Vector3D target(0, 0, 0);
        for (int ti : nodeToTet[ni]) {
            const PatchTet& t = tets[ti];
            Vector3D c = (nodes[t.n[0]].position + nodes[t.n[1]].position +
                          nodes[t.n[2]].position + nodes[t.n[3]].position) *
                         0.25;
            target += c;
        }
        target = target * (1.0 / (double)nodeToTet[ni].size());

        // For free surface nodes, restrict motion to the tangent plane of
        // the surface normal, then clamp to moveTolerance.
        Vector3D candidate = target;
        if (pn.tangentNormal.magnitude() > 1e-9) {
            Vector3D delta = target - original[ni];
            Vector3D tangentDelta = projectToPlane(delta, pn.tangentNormal);
            candidate = original[ni] + tangentDelta;
        }
        candidate = clampToTolerance(candidate, original[ni], pn.moveTolerance > 0
                                                              ? pn.moveTolerance
                                                              : 1e30);

        // Accept-or-reject: only commit if no incident tet flips sign.
        Vector3D backup = pn.position;
        pn.position = candidate;
        bool ok = true;
        for (int ti : nodeToTet[ni]) {
            const PatchTet& t = tets[ti];
            double V = tetSignedVolume(nodes[t.n[0]].position,
                                       nodes[t.n[1]].position,
                                       nodes[t.n[2]].position,
                                       nodes[t.n[3]].position);
            if (V <= 0.0) { ok = false; break; }
        }
        if (!ok) { pn.position = backup; continue; }
        ++moved;
    }
    return moved;
}

// Subdivide one TET by inserting its centroid as a new interior node,
// producing 4 new TETs. The new node is appended to `nodes`. The 4 new
// tets reuse the original 4 face-vertex triples but with the centroid
// substituted for the opposite vertex.
//
// Pre-existing winding of the tet is preserved (face0 opposite v0 = (1,2,3)
// etc, see PatchExtractor TET_FACE), so the 4 child tets inherit positive
// orientation if the parent had positive orientation.
void subdivideOne(const PatchTet& parent,
                  std::vector<PatchNode>& nodes,
                  std::vector<PatchTet>& outChildren) {
    // centroid
    Vector3D c = (nodes[parent.n[0]].position + nodes[parent.n[1]].position +
                  nodes[parent.n[2]].position + nodes[parent.n[3]].position) *
                 0.25;
    PatchNode cn;
    cn.position = c;
    cn.isFixed = false;            // interior new node is free for future smoothing
    cn.tangentNormal = Vector3D();
    cn.moveTolerance = 0.0;
    int centroidIdx = (int)nodes.size();
    nodes.push_back(cn);

    // Children: replace each parent vertex with the centroid in turn,
    // keeping the opposite face triple intact.
    //   FACE[i] = (a,b,c) is the parent face opposite v_i, wound so its
    //   outward normal points AWAY from v_i. The centroid lives on the
    //   SAME side of that face as v_i (it's inside the parent), so naive
    //   reuse of FACE order would make the child have a NEGATIVE volume
    //   when scored by LS-DYNA's (n1-n0)x(n2-n0).(n3-n0) > 0 convention.
    //   We swap the first two face vertices to flip the base winding,
    //   which restores positive child orientation.
    static constexpr int FACE[4][3] = {
        {1, 2, 3}, {0, 3, 2}, {0, 1, 3}, {0, 2, 1}
    };
    for (int f = 0; f < 4; ++f) {
        PatchTet ct;
        ct.n[0] = parent.n[FACE[f][1]];   // swapped
        ct.n[1] = parent.n[FACE[f][0]];   // swapped
        ct.n[2] = parent.n[FACE[f][2]];
        ct.n[3] = centroidIdx;
        outChildren.push_back(ct);
    }
}

// -----------------------------------------------------------------------
// 2-3 face-edge swap.
//
// Two TETs T1 = (a,b,c,d1) and T2 = (a,b,c,d2) sharing the triangular
// face (a,b,c) form a bipyramid d1-(a,b,c)-d2. They can be replaced by
// 3 TETs sharing the new edge d1-d2:
//      (a,b,d1,d2), (b,c,d1,d2), (c,a,d1,d2)
// The swap is geometrically valid only if d1 and d2 lie on opposite
// sides of the (a,b,c) plane and the bipyramid is convex (no flipped
// child after swap). We accept the swap iff:
//   * all 3 children have positive scaled Jacobian, AND
//   * the worst child quality is strictly better than the worst of T1/T2.
//
// This handles the topology-change case that smoothing+subdivide cannot:
// when the bad shape is in the connectivity itself, edge swap rerouts
// the diagonal through a different vertex pair.
// -----------------------------------------------------------------------

// returns scaled Jac for (n0,n1,n2,n3) ordered so positive volume = positive
// quality. Negative if winding flipped.
double quickQuality(const Vector3D& p0, const Vector3D& p1,
                    const Vector3D& p2, const Vector3D& p3) {
    static const double EQ_NORM = 0.11785113019775793;
    double V = tetSignedVolume(p0, p1, p2, p3);
    double e01 = (p1 - p0).magnitude();
    double e02 = (p2 - p0).magnitude();
    double e03 = (p3 - p0).magnitude();
    double e12 = (p2 - p1).magnitude();
    double e13 = (p3 - p1).magnitude();
    double e23 = (p3 - p2).magnitude();
    double maxE = std::max({e01, e02, e03, e12, e13, e23});
    if (maxE < 1e-12) return 0.0;
    return (V / (maxE * maxE * maxE)) / EQ_NORM;
}

// Hash key for an unordered face triple.
struct FaceKey3 {
    int a, b, c;  // sorted ascending
    bool operator==(const FaceKey3& o) const { return a==o.a && b==o.b && c==o.c; }
};
struct FaceKey3Hash {
    size_t operator()(const FaceKey3& f) const noexcept {
        size_t h = std::hash<int>{}(f.a);
        h ^= std::hash<int>{}(f.b) + 0x9e3779b9 + (h << 6) + (h >> 2);
        h ^= std::hash<int>{}(f.c) + 0x9e3779b9 + (h << 6) + (h >> 2);
        return h;
    }
};
FaceKey3 sortedKey3(int a, int b, int c) {
    int v[3] = {a,b,c}; std::sort(v, v+3); return {v[0],v[1],v[2]};
}

constexpr int LOCAL_FACE[4][3] = {
    {1, 2, 3}, {0, 3, 2}, {0, 1, 3}, {0, 2, 1}
};

// Ensure tet has positive volume by swapping vertex pair if needed.
// Returns swapped copy.
PatchTet ensurePositive(const PatchTet& t,
                        const std::vector<PatchNode>& nodes) {
    PatchTet out = t;
    double V = tetSignedVolume(nodes[t.n[0]].position, nodes[t.n[1]].position,
                                nodes[t.n[2]].position, nodes[t.n[3]].position);
    if (V < 0) std::swap(out.n[1], out.n[2]);
    return out;
}

int twoThreeSwapPass(std::vector<PatchTet>& tets,
                     const std::vector<PatchNode>& nodes,
                     double minJacAccept) {
    // Build face -> {tet indices} map.
    std::unordered_map<FaceKey3, std::vector<int>, FaceKey3Hash> faceMap;
    faceMap.reserve(tets.size() * 4);
    for (int ti = 0; ti < (int)tets.size(); ++ti) {
        for (int f = 0; f < 4; ++f) {
            int a = tets[ti].n[LOCAL_FACE[f][0]];
            int b = tets[ti].n[LOCAL_FACE[f][1]];
            int c = tets[ti].n[LOCAL_FACE[f][2]];
            faceMap[sortedKey3(a, b, c)].push_back(ti);
        }
    }

    std::vector<bool> consumed(tets.size(), false);
    std::vector<PatchTet> additions;
    int swaps = 0;

    for (auto& kv : faceMap) {
        const auto& tids = kv.second;
        if (tids.size() != 2) continue;        // boundary or non-manifold
        int t1 = tids[0], t2 = tids[1];
        if (consumed[t1] || consumed[t2]) continue;

        const PatchTet& T1 = tets[t1];
        const PatchTet& T2 = tets[t2];

        // shared face vertices (kv.first.a, .b, .c)
        std::set<int> sharedSet = {kv.first.a, kv.first.b, kv.first.c};
        // apex of each tet = the one vertex not in shared face
        int apex1 = -1, apex2 = -1;
        for (int i = 0; i < 4; ++i) if (!sharedSet.count(T1.n[i])) { apex1 = T1.n[i]; break; }
        for (int i = 0; i < 4; ++i) if (!sharedSet.count(T2.n[i])) { apex2 = T2.n[i]; break; }
        if (apex1 < 0 || apex2 < 0) continue;
        if (apex1 == apex2) continue;   // degenerate

        // Order shared vertices a,b,c so the bipyramid is consistently wound.
        int a = kv.first.a, b = kv.first.b, c = kv.first.c;

        // Children candidates after 2-3 swap (each shares the new edge a1-a2):
        //   C1 = (a, b, apex1, apex2)
        //   C2 = (b, c, apex1, apex2)
        //   C3 = (c, a, apex1, apex2)
        PatchTet candidates[3];
        candidates[0].n[0] = a; candidates[0].n[1] = b;
        candidates[0].n[2] = apex1; candidates[0].n[3] = apex2;
        candidates[1].n[0] = b; candidates[1].n[1] = c;
        candidates[1].n[2] = apex1; candidates[1].n[3] = apex2;
        candidates[2].n[0] = c; candidates[2].n[1] = a;
        candidates[2].n[2] = apex1; candidates[2].n[3] = apex2;

        // Score before/after.
        double q1 = quickQuality(nodes[T1.n[0]].position, nodes[T1.n[1]].position,
                                  nodes[T1.n[2]].position, nodes[T1.n[3]].position);
        double q2 = quickQuality(nodes[T2.n[0]].position, nodes[T2.n[1]].position,
                                  nodes[T2.n[2]].position, nodes[T2.n[3]].position);
        double oldMin = std::min(q1, q2);

        double newMin = std::numeric_limits<double>::max();
        bool valid = true;
        for (int k = 0; k < 3; ++k) {
            // ensure positive winding for candidate
            PatchTet cand = ensurePositive(candidates[k], nodes);
            double cq = quickQuality(nodes[cand.n[0]].position, nodes[cand.n[1]].position,
                                      nodes[cand.n[2]].position, nodes[cand.n[3]].position);
            if (cq <= 0.0) { valid = false; break; }
            if (cq < newMin) newMin = cq;
            candidates[k] = cand;
        }
        if (!valid) continue;

        // Accept criteria: strict improvement, AND new worst above acceptance.
        if (newMin <= oldMin + 1e-6) continue;
        if (oldMin >= minJacAccept) continue;     // no need to swap good pairs

        // Apply swap: mark consumed, add 3 new tets.
        consumed[t1] = true;
        consumed[t2] = true;
        for (int k = 0; k < 3; ++k) additions.push_back(candidates[k]);
        ++swaps;
    }

    if (swaps == 0) return 0;

    // Rebuild tets vector excluding consumed.
    std::vector<PatchTet> next;
    next.reserve(tets.size() - 2 * swaps + 3 * swaps);
    for (int i = 0; i < (int)tets.size(); ++i) {
        if (!consumed[i]) next.push_back(tets[i]);
    }
    for (auto& a : additions) next.push_back(a);
    tets = std::move(next);
    return swaps;
}

}  // namespace

RemeshResult LocalImproveRemesher::run(const RemeshTask& task) {
    RemeshResult result;
    result.nodes = task.nodes;
    result.tets  = task.originalTets;

    const size_t inputNodeCount = task.nodes.size();

    // Capture original positions (anchor for moveTolerance).
    std::vector<Vector3D> original(inputNodeCount);
    for (size_t i = 0; i < inputNodeCount; ++i) {
        original[i] = task.nodes[i].position;
    }
    // Pad original[] for new nodes added during subdivision (anchor at
    // their insertion centroid; tolerance 0 => locked unless re-flagged).
    auto extendOriginalTo = [&](size_t newSize) {
        while (original.size() < newSize) {
            original.push_back(result.nodes[original.size()].position);
        }
    };

    // initial quality
    double minBefore = std::numeric_limits<double>::max();
    for (const auto& t : result.tets) {
        minBefore = std::min(minBefore, tetQuality(result.nodes, t));
    }
    result.minJacBefore = (minBefore == std::numeric_limits<double>::max())
                          ? 0.0 : minBefore;

    int totalSmoothMoves = 0;
    int totalSubdivides  = 0;
    int totalSwaps       = 0;

    // -------------------------------------------------------------------
    // Outer loop:
    //   smoothing -> 2-3 swap (topology fix) -> subdivide bad -> repeat
    // -------------------------------------------------------------------
    for (int outer = 0; outer < task.maxOuterIters; ++outer) {

        // 1. smoothing passes
        for (int s = 0; s < task.laplacianIters; ++s) {
            extendOriginalTo(result.nodes.size());
            int m = smoothPass(result.nodes, result.tets, original);
            totalSmoothMoves += m;
            if (m == 0) break;
        }

        // 2. 2-3 face-edge swaps for any pair below acceptance.
        //    Picks ONLY pairs whose worst element is below
        //    minJacobianTarget AND where the swap strictly improves
        //    worst-quality. Topology change handles cases that
        //    smoothing+subdivide alone cannot.
        int swaps = twoThreeSwapPass(result.tets, result.nodes,
                                      task.minJacobianTarget);
        totalSwaps += swaps;
        if (swaps > 0) {
            // re-smooth after topology change
            for (int s = 0; s < task.laplacianIters; ++s) {
                extendOriginalTo(result.nodes.size());
                int m = smoothPass(result.nodes, result.tets, original);
                totalSmoothMoves += m;
                if (m == 0) break;
            }
        }

        if (!task.allowSubdivide) break;

        // 3. subdivide bad tets that remain
        std::vector<int> badIdx;
        for (int i = 0; i < (int)result.tets.size(); ++i) {
            double q = tetQuality(result.nodes, result.tets[i]);
            if (q < task.minJacobianTarget) badIdx.push_back(i);
        }
        if (badIdx.empty()) break;

        std::vector<PatchTet> nextTets;
        nextTets.reserve(result.tets.size() + badIdx.size() * 3);
        std::vector<bool> isBad(result.tets.size(), false);
        for (int bi : badIdx) isBad[bi] = true;

        for (int i = 0; i < (int)result.tets.size(); ++i) {
            if (!isBad[i]) {
                nextTets.push_back(result.tets[i]);
            } else {
                subdivideOne(result.tets[i], result.nodes, nextTets);
                ++totalSubdivides;
            }
        }
        result.tets = std::move(nextTets);
    }

    // final quality
    double minAfter = std::numeric_limits<double>::max();
    for (const auto& t : result.tets) {
        minAfter = std::min(minAfter, tetQuality(result.nodes, t));
    }
    result.minJacAfter = (minAfter == std::numeric_limits<double>::max())
                         ? 0.0 : minAfter;

    result.newNodeCount   = (int)(result.nodes.size() - inputNodeCount);
    result.subdivideCount = totalSubdivides;
    result.smoothMoves    = totalSmoothMoves;
    result.swapCount      = totalSwaps;
    result.success        = true;

    std::ostringstream msg;
    msg << "LocalImprove: smoothMoves=" << totalSmoothMoves
        << " swaps=" << totalSwaps
        << " subdivides=" << totalSubdivides
        << " newNodes=" << result.newNodeCount
        << " scaledJac " << result.minJacBefore << " -> " << result.minJacAfter;
    result.message = msg.str();
    return result;
}

}  // namespace remesh
}  // namespace KooRemapper
