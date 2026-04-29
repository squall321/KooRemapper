#include "remesh/PatchExtractor.h"
#include <algorithm>
#include <array>
#include <cmath>
#include <map>
#include <queue>
#include <sstream>
#include <unordered_map>
#include <unordered_set>

namespace KooRemapper {
namespace remesh {

namespace {

// LS-DYNA TET4 face convention. Each face is the triangle of 3 vertices
// OPPOSITE to one tet vertex. Winding is chosen so the outward normal
// (n1-n0)x(n2-n0) points AWAY from the opposite vertex when the tet has
// positive signed volume.
//   face 0 opposite v0: (1,2,3)
//   face 1 opposite v1: (0,3,2)
//   face 2 opposite v2: (0,1,3)
//   face 3 opposite v3: (0,2,1)
constexpr int TET_FACE[4][3] = {
    {1, 2, 3},
    {0, 3, 2},
    {0, 1, 3},
    {0, 2, 1},
};

struct FaceKey {
    int a, b, c;  // sorted ascending
    bool operator==(const FaceKey& o) const {
        return a == o.a && b == o.b && c == o.c;
    }
};
struct FaceKeyHash {
    size_t operator()(const FaceKey& f) const noexcept {
        size_t h = std::hash<int>{}(f.a);
        h ^= std::hash<int>{}(f.b) + 0x9e3779b9 + (h << 6) + (h >> 2);
        h ^= std::hash<int>{}(f.c) + 0x9e3779b9 + (h << 6) + (h >> 2);
        return h;
    }
};

FaceKey makeFaceKey(int a, int b, int c) {
    int x[3] = {a, b, c};
    std::sort(x, x + 3);
    return {x[0], x[1], x[2]};
}

double tetSignedVolume(const Vector3D& p0, const Vector3D& p1,
                       const Vector3D& p2, const Vector3D& p3) {
    Vector3D e1 = p1 - p0;
    Vector3D e2 = p2 - p0;
    Vector3D e3 = p3 - p0;
    return e1.dot(e2.cross(e3)) / 6.0;
}

double tetMinJac(const Vector3D& p0, const Vector3D& p1,
                 const Vector3D& p2, const Vector3D& p3) {
    // SCALED JACOBIAN for TET4. Industry-standard quality metric:
    //   1.0  = equilateral (perfect) tet
    //   0.0  = degenerate (zero-volume)
    //   < 0  = inverted (negative volume)
    //
    // Definition: V_actual / V_equilateral_with_same_max_edge.
    //   V_equilateral(L) = (sqrt(2)/12) * L^3 ~= 0.1178 * L^3
    // So scaledJac = (V / L_max^3) / 0.1178. Capped to no more than ~1
    // for any real tet (equilateral has the highest V per max-edge cubed).
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

double tetAspectRatio(const Vector3D& p0, const Vector3D& p1,
                      const Vector3D& p2, const Vector3D& p3) {
    double e01 = (p1 - p0).magnitude();
    double e02 = (p2 - p0).magnitude();
    double e03 = (p3 - p0).magnitude();
    double e12 = (p2 - p1).magnitude();
    double e13 = (p3 - p1).magnitude();
    double e23 = (p3 - p2).magnitude();
    double maxEdge = std::max({e01, e02, e03, e12, e13, e23});
    double minEdge = std::min({e01, e02, e03, e12, e13, e23});
    if (minEdge < 1e-12) return 1e9;
    return maxEdge / minEdge;
}

bool isBadTet(const Vector3D& p0, const Vector3D& p1,
              const Vector3D& p2, const Vector3D& p3,
              double minJacThr, double maxAspectThr) {
    double j = tetMinJac(p0, p1, p2, p3);
    if (j < minJacThr) return true;
    double ar = tetAspectRatio(p0, p1, p2, p3);
    if (ar > maxAspectThr) return true;
    return false;
}

}  // namespace

std::vector<PatchExtractor::Patch> PatchExtractor::extract(const Mesh& mesh) {
    std::ostringstream diag;
    std::vector<Patch> patches;

    // -------------------------------------------------------------------
    // 1. Collect candidate TET4 elements (all matching target PIDs).
    // -------------------------------------------------------------------
    std::unordered_set<int> targetPidSet(cfg_.targetPids.begin(),
                                          cfg_.targetPids.end());
    bool allPids = cfg_.targetPids.empty();

    std::vector<int> candidateTetIds;
    candidateTetIds.reserve(mesh.elements.size() / 4);
    for (const auto& kv : mesh.elements) {
        const Element& e = kv.second;
        if (e.type != ElementType::TET4) continue;
        if (!allPids && targetPidSet.find(e.partId) == targetPidSet.end())
            continue;
        candidateTetIds.push_back(kv.first);
    }
    diag << "candidate TET4 elements (target PIDs): "
         << candidateTetIds.size() << "\n";
    if (candidateTetIds.empty()) {
        diag_ = diag.str();
        return patches;
    }

    // -------------------------------------------------------------------
    // 2. Build face -> {elementIds} map across ALL elements in the mesh,
    //    so we can detect inter-PID and non-TET sharing later. For
    //    cross-PID sharing detection we need to know what other elements
    //    touch each face of each candidate TET.
    // -------------------------------------------------------------------
    std::unordered_map<FaceKey, std::vector<int>, FaceKeyHash> faceToElems;
    faceToElems.reserve(mesh.elements.size() * 2);
    for (const auto& kv : mesh.elements) {
        const Element& e = kv.second;
        if (e.type == ElementType::TET4) {
            for (int f = 0; f < 4; ++f) {
                FaceKey k = makeFaceKey(e.nodeIds[TET_FACE[f][0]],
                                         e.nodeIds[TET_FACE[f][1]],
                                         e.nodeIds[TET_FACE[f][2]]);
                faceToElems[k].push_back(kv.first);
            }
        } else if (e.type == ElementType::HEX8) {
            // record HEX8 faces too so adjacent hex pins TET nodes
            static const int HF[6][4] = {
                {0,3,2,1},{4,5,6,7},{0,1,5,4},{2,3,7,6},{0,4,7,3},{1,2,6,5}
            };
            for (int f = 0; f < 6; ++f) {
                // HEX face is a quad; record the two diagonals as 'tri keys'?
                // Simpler: record the 4 nodes individually so node-sharing
                // detection (next pass) works without needing exact face match.
            }
            // For pinning purposes node-membership is sufficient (handled
            // in node-fixity pass below). Skip face hashing for HEX.
        }
    }

    // Map node -> set of element IDs touching it (for fixity detection).
    std::unordered_map<int, std::vector<int>> nodeToElems;
    nodeToElems.reserve(mesh.nodes.size());
    for (const auto& kv : mesh.elements) {
        const Element& e = kv.second;
        int nUnique = (e.type == ElementType::TET4) ? 4 : Element::NUM_NODES;
        for (int i = 0; i < nUnique; ++i) {
            nodeToElems[e.nodeIds[i]].push_back(kv.first);
        }
    }

    // -------------------------------------------------------------------
    // 3. Build the SEED set of elements to remesh -- two modes:
    //    BAD_QUALITY: scan candidate TETs, flag those with low Jacobian or
    //                 high aspect ratio.
    //    EXPLICIT_IDS: caller specified the seed elements directly; we just
    //                 verify each is a TET4 in this mesh.
    // -------------------------------------------------------------------
    std::unordered_set<int> badIds;  // semantically: seed ids
    if (cfg_.selectionMode == PatchExtractor::SelectionMode::EXPLICIT_IDS) {
        for (int eid : cfg_.selectedElementIds) {
            auto it = mesh.elements.find(eid);
            if (it == mesh.elements.end()) continue;
            if (it->second.type != ElementType::TET4) continue;
            badIds.insert(eid);
        }
        diag << "explicit seed TET4 elements: " << badIds.size() << "\n";
    } else {
        for (int eid : candidateTetIds) {
            const Element& e = mesh.elements.at(eid);
            const Node* p[4];
            bool ok = true;
            for (int i = 0; i < 4; ++i) {
                p[i] = mesh.getNode(e.nodeIds[i]);
                if (!p[i]) { ok = false; break; }
            }
            if (!ok) continue;
            if (isBadTet(p[0]->position, p[1]->position, p[2]->position,
                         p[3]->position,
                         cfg_.minJacobianThreshold, cfg_.maxAspectRatio)) {
                badIds.insert(eid);
            }
        }
        diag << "bad TET4 elements: " << badIds.size() << "\n";
    }
    if (badIds.empty()) {
        diag_ = diag.str();
        return patches;
    }

    // -------------------------------------------------------------------
    // 4. Cluster bad TETs via face-adjacency BFS, then expand each cluster
    //    by `ringExpand` rings of face-adjacent neighbor TETs (any quality).
    //    Same-PID restriction: only expand into TETs sharing the cluster's
    //    PID, so different parts stay independent patches.
    // -------------------------------------------------------------------
    std::unordered_set<int> visited;
    for (int seedId : badIds) {
        if (visited.count(seedId)) continue;

        int seedPid = mesh.elements.at(seedId).partId;

        // Collect cluster of bad TETs reachable from seed via face-adjacency
        // (within same PID).
        std::unordered_set<int> cluster;
        std::queue<int> q;
        q.push(seedId);
        cluster.insert(seedId);
        while (!q.empty()) {
            int cur = q.front(); q.pop();
            const Element& e = mesh.elements.at(cur);
            for (int f = 0; f < 4; ++f) {
                FaceKey k = makeFaceKey(e.nodeIds[TET_FACE[f][0]],
                                         e.nodeIds[TET_FACE[f][1]],
                                         e.nodeIds[TET_FACE[f][2]]);
                auto it = faceToElems.find(k);
                if (it == faceToElems.end()) continue;
                for (int neighborId : it->second) {
                    if (neighborId == cur) continue;
                    if (cluster.count(neighborId)) continue;
                    if (!badIds.count(neighborId)) continue;
                    if (mesh.elements.at(neighborId).partId != seedPid) continue;
                    cluster.insert(neighborId);
                    q.push(neighborId);
                }
            }
        }

        // Expand cluster outward by ringExpand rings (BFS layered).
        // Two adjacency modes:
        //   FACE: only elements sharing a 3-vertex face are picked up
        //         (conservative, follows topology of TET subdivision).
        //   NODE: any element touching ANY shared node joins the next ring
        //         (aggressive; one ring sweeps a wider neighborhood).
        std::unordered_set<int> patchTets = cluster;
        std::unordered_set<int> frontier = cluster;
        for (int ring = 0; ring < cfg_.ringExpand; ++ring) {
            std::unordered_set<int> nextFrontier;
            if (cfg_.ringMode == PatchExtractor::RingMode::FACE) {
                for (int cur : frontier) {
                    const Element& e = mesh.elements.at(cur);
                    for (int f = 0; f < 4; ++f) {
                        FaceKey k = makeFaceKey(e.nodeIds[TET_FACE[f][0]],
                                                 e.nodeIds[TET_FACE[f][1]],
                                                 e.nodeIds[TET_FACE[f][2]]);
                        auto it = faceToElems.find(k);
                        if (it == faceToElems.end()) continue;
                        for (int neighborId : it->second) {
                            if (neighborId == cur) continue;
                            if (patchTets.count(neighborId)) continue;
                            const Element& ne = mesh.elements.at(neighborId);
                            if (ne.type != ElementType::TET4) continue;
                            if (ne.partId != seedPid) continue;
                            patchTets.insert(neighborId);
                            nextFrontier.insert(neighborId);
                        }
                    }
                }
            } else {  // NODE mode
                for (int cur : frontier) {
                    const Element& e = mesh.elements.at(cur);
                    for (int v = 0; v < 4; ++v) {
                        int nid = e.nodeIds[v];
                        auto it = nodeToElems.find(nid);
                        if (it == nodeToElems.end()) continue;
                        for (int neighborId : it->second) {
                            if (neighborId == cur) continue;
                            if (patchTets.count(neighborId)) continue;
                            const Element& ne = mesh.elements.at(neighborId);
                            if (ne.type != ElementType::TET4) continue;
                            if (ne.partId != seedPid) continue;
                            patchTets.insert(neighborId);
                            nextFrontier.insert(neighborId);
                        }
                    }
                }
            }
            frontier = std::move(nextFrontier);
            if (frontier.empty()) break;
        }

        for (int eid : patchTets) visited.insert(eid);

        // -------------------------------------------------------------------
        // 5. Build the Patch struct: collect unique nodes, assign patch-local
        //    indices, find boundary triangles, classify node fixity.
        // -------------------------------------------------------------------
        Patch patch;
        patch.originalElemIds = std::set<int>(patchTets.begin(), patchTets.end());

        // 5a. unique node IDs
        std::map<int, int> origToPatchIdx;
        for (int eid : patchTets) {
            const Element& e = mesh.elements.at(eid);
            for (int i = 0; i < 4; ++i) {
                int nid = e.nodeIds[i];
                if (origToPatchIdx.find(nid) == origToPatchIdx.end()) {
                    int newIdx = (int)origToPatchIdx.size();
                    origToPatchIdx[nid] = newIdx;
                    patch.originalNodeIds.insert(nid);
                }
            }
        }
        patch.patchToOrig.assign(origToPatchIdx.size(), -1);
        for (const auto& kv : origToPatchIdx) {
            patch.patchToOrig[kv.second] = kv.first;
        }

        // 5b. node positions
        patch.task.nodes.resize(origToPatchIdx.size());
        for (const auto& kv : origToPatchIdx) {
            const Node* n = mesh.getNode(kv.first);
            PatchNode pn;
            pn.position = n ? n->position : Vector3D();
            pn.isFixed = true;          // default: pin everything
            pn.moveTolerance = 0.0;
            patch.task.nodes[kv.second] = pn;
        }

        // 5c. interior face count: a face is INTERNAL to patch if BOTH
        //     elements sharing it are in patchTets. Else it's BOUNDARY.
        std::unordered_map<FaceKey, int, FaceKeyHash> faceUseCountInPatch;
        for (int eid : patchTets) {
            const Element& e = mesh.elements.at(eid);
            for (int f = 0; f < 4; ++f) {
                FaceKey k = makeFaceKey(e.nodeIds[TET_FACE[f][0]],
                                         e.nodeIds[TET_FACE[f][1]],
                                         e.nodeIds[TET_FACE[f][2]]);
                ++faceUseCountInPatch[k];
            }
        }

        // Boundary triangles: faces touched by exactly ONE patch tet.
        // We need them in the original (oriented) winding so the backend
        // gets a consistent outward-normal surface.
        std::vector<PatchTri> boundary;
        std::set<int> boundaryNodesPatch;
        for (int eid : patchTets) {
            const Element& e = mesh.elements.at(eid);
            for (int f = 0; f < 4; ++f) {
                int a = e.nodeIds[TET_FACE[f][0]];
                int b = e.nodeIds[TET_FACE[f][1]];
                int c = e.nodeIds[TET_FACE[f][2]];
                FaceKey k = makeFaceKey(a, b, c);
                if (faceUseCountInPatch[k] != 1) continue;  // interior
                PatchTri tri{{ origToPatchIdx[a], origToPatchIdx[b],
                              origToPatchIdx[c] }};
                boundary.push_back(tri);
                boundaryNodesPatch.insert(origToPatchIdx[a]);
                boundaryNodesPatch.insert(origToPatchIdx[b]);
                boundaryNodesPatch.insert(origToPatchIdx[c]);
            }
        }
        patch.task.boundaryTris = std::move(boundary);

        // 5d. originalTets in patch-local indices
        patch.task.originalTets.reserve(patchTets.size());
        for (int eid : patchTets) {
            const Element& e = mesh.elements.at(eid);
            PatchTet t;
            for (int i = 0; i < 4; ++i) {
                t.n[i] = origToPatchIdx[e.nodeIds[i]];
            }
            patch.task.originalTets.push_back(t);
        }

        // Carry over backend tuning so LocalImprove/TetGen honor the
        // YAML-supplied options instead of using RemeshTask defaults.
        patch.task.minJacobianTarget  = cfg_.minJacobianThreshold;
        patch.task.maxAspectRatio     = cfg_.maxAspectRatio;
        patch.task.laplacianIters     = cfg_.laplacianIters;
        patch.task.maxOuterIters      = cfg_.maxOuterIters;
        patch.task.allowSubdivide     = cfg_.allowSubdivide;
        patch.task.tetgenQualityRatio = cfg_.tetgenQualityRatio;
        patch.task.tetgenMinDihedral  = cfg_.tetgenMinDihedral;

        // 5e. node fixity classification.
        //     A boundary node may become FREE (movable in tangent plane) iff:
        //       - not used by any element OUTSIDE the patch
        //       - all incident boundary tris share normals within
        //         surfaceFlatnessDeg
        //     Interior nodes (not on boundary) are always free, with no
        //     tangent constraint.
        if (cfg_.surfaceMoveTolerance > 0.0) {
            // precompute boundary-tri normals + node->incident-tri map
            std::vector<Vector3D> triNormals(patch.task.boundaryTris.size());
            std::unordered_map<int, std::vector<int>> nodeToTri;
            for (size_t ti = 0; ti < patch.task.boundaryTris.size(); ++ti) {
                const PatchTri& t = patch.task.boundaryTris[ti];
                Vector3D p0 = patch.task.nodes[t.n[0]].position;
                Vector3D p1 = patch.task.nodes[t.n[1]].position;
                Vector3D p2 = patch.task.nodes[t.n[2]].position;
                Vector3D n = (p1 - p0).cross(p2 - p0);
                double mag = n.magnitude();
                triNormals[ti] = (mag > 1e-12) ? (n * (1.0 / mag)) : Vector3D();
                for (int v = 0; v < 3; ++v) nodeToTri[t.n[v]].push_back((int)ti);
            }

            const double cosThr = std::cos(cfg_.surfaceFlatnessDeg
                                            * 3.14159265358979323846 / 180.0);

            for (int patchIdx : boundaryNodesPatch) {
                int origNid = patch.patchToOrig[patchIdx];

                // pinned if shared with any element outside the patch
                bool pinnedByExternal = false;
                auto it = nodeToElems.find(origNid);
                if (it != nodeToElems.end()) {
                    for (int eid : it->second) {
                        if (!patchTets.count(eid)) {
                            pinnedByExternal = true; break;
                        }
                    }
                }
                if (pinnedByExternal) continue;  // stays fixed

                // check normal coherence among incident boundary triangles
                const auto& tris = nodeToTri[patchIdx];
                bool flat = true;
                Vector3D avg(0, 0, 0);
                for (int ti : tris) avg += triNormals[ti];
                double mag = avg.magnitude();
                if (mag < 1e-12) { continue; }  // degenerate, keep pinned
                avg = avg * (1.0 / mag);
                for (int ti : tris) {
                    if (triNormals[ti].dot(avg) < cosThr) { flat = false; break; }
                }
                if (!flat) continue;  // feature edge / curved; pin

                // free this node
                PatchNode& pn = patch.task.nodes[patchIdx];
                pn.isFixed = false;
                pn.tangentNormal = avg;
                pn.moveTolerance = cfg_.surfaceMoveTolerance;
            }
        }

        // 5f. interior nodes (not on boundary): always free, no tangent
        //     constraint.
        for (size_t i = 0; i < patch.task.nodes.size(); ++i) {
            if (boundaryNodesPatch.count((int)i)) continue;
            PatchNode& pn = patch.task.nodes[i];
            pn.isFixed = false;
            pn.tangentNormal = Vector3D();  // 0-vector = unconstrained
            pn.moveTolerance = 0.0;
        }

        patches.push_back(std::move(patch));
    }

    diag << "patches built: " << patches.size() << "\n";
    diag_ = diag.str();
    return patches;
}

}  // namespace remesh
}  // namespace KooRemapper
