#pragma once

#include "remesh/RemeshTask.h"
#include "core/Mesh.h"
#include <vector>
#include <set>
#include <string>

// Knowledge graph (lat.md):
//   @lat: [[modules/remesh]]

namespace KooRemapper {
namespace remesh {

// =============================================================================
// PatchExtractor
//
// Walks a mesh, identifies bad TET4 elements per target PID, expands each
// connected cluster of bad TETs by N face-adjacent rings, and packages the
// region into a self-contained RemeshTask plus the metadata needed by the
// orchestrator to splice the result back into the original mesh.
//
// Boundary preservation policy
// ----------------------------
// A patch's boundary triangulation is the set of TET faces that are:
//   * shared with a TET that is NOT in the patch (interior surface), OR
//   * not shared with any element (outer surface of the part).
// Nodes on the boundary triangulation are PINNED by default. A node is
// flagged free (movable in its surface tangent plane) only if all of:
//   * not used by any element OUTSIDE the patch (no cross-PID, no non-TET);
//   * not on a feature edge (sharp boundary) -- detected by checking that
//     all boundary triangles incident to the node share normals within
//     surfaceFlatnessDeg of each other.
// Free nodes get an averaged surface normal as their tangentNormal so the
// backend constrains motion to the tangent plane.
//
// This matches the spec: boundary preserved by default; only
// near-flat surface regions allowed to move (within surfaceMoveTolerance).
// =============================================================================

class PatchExtractor {
public:
    // Selection mode for choosing which elements to remesh.
    //   BAD_QUALITY: scan target PIDs, flag elements whose Jacobian is below
    //                minJacobianThreshold or aspect ratio exceeds the cap.
    //                Each connected cluster of flagged elements becomes a
    //                seed; the patch is grown by ringExpand rings.
    //   EXPLICIT_IDS: caller supplies an exact list of element IDs as the
    //                seed (selectedElementIds). The patch is grown by
    //                ringExpand rings via either node- or face-adjacency
    //                (see ringMode). Use this for hand-picked local repair
    //                without quality scanning.
    enum class SelectionMode { BAD_QUALITY, EXPLICIT_IDS };

    // Ring-expansion adjacency. node-mode includes any element touching a
    // shared node (more aggressive); face-mode requires a shared 3-vertex
    // face (more conservative, matches connectivity of TET subdivision).
    enum class RingMode { NODE, FACE };

    struct Config {
        SelectionMode selectionMode = SelectionMode::BAD_QUALITY;
        std::vector<int> selectedElementIds;   // EXPLICIT_IDS seed set
        std::vector<int> targetPids;       // empty = all parts with TET4
        double minJacobianThreshold = 0.2; // bad if Jacobian < this
        double maxAspectRatio       = 8.0; // bad if aspect ratio > this
        int    ringExpand           = 2;   // grow patch this many rings
                                           // around each seed
        // FACE (default, safe): only elements sharing a full triangular
        //   face join the next ring. Result is a manifold patch with a
        //   well-defined closed boundary triangulation -- required for
        //   TetGen to remesh the patch successfully.
        // NODE (aggressive): any element touching ANY shared node joins.
        //   This grows patches faster but can create non-manifold patches
        //   (a vertex touches the patch from multiple disconnected
        //   directions) that produce malformed boundary triangulations
        //   and crash TetGen with heap corruption / access violations.
        //   Use NODE only with backend=localimprove, or with a manifold-
        //   repair post-process (TODO).
        RingMode ringMode = RingMode::FACE;
        double surfaceFlatnessDeg   = 5.0; // boundary node free if all
                                           // incident-tri normals agree within
        double surfaceMoveTolerance = 0.0; // 0 = surface fully pinned;
                                           // >0 = free-flagged nodes may move
                                           // in tangent plane up to this dist
        bool   preserveMultiMaterial = true;  // pin nodes shared with other PIDs

        // Backend tuning copied verbatim into each emitted RemeshTask so
        // LocalImprove/TetGen actually honor user-supplied YAML settings
        // (laplacian_iters etc.). Without this the backends just used
        // RemeshTask defaults regardless of YAML.
        double minJacobianTarget   = 0.20;
        int    laplacianIters      = 5;
        int    maxOuterIters       = 3;
        bool   allowSubdivide      = true;
        double tetgenQualityRatio  = 1.4;
        double tetgenMinDihedral   = 10.0;
    };

    struct Patch {
        std::set<int>  originalElemIds;     // mesh elements consumed/removed
        std::set<int>  originalNodeIds;     // mesh nodes touched by patch TETs
        std::vector<int> patchToOrig;       // patchNodeIdx -> origNodeId
                                            // (-1 for new interior nodes the
                                            //  backend will add)
        RemeshTask     task;                // ready to hand to a Remesher
    };

    explicit PatchExtractor(Config cfg) : cfg_(std::move(cfg)) {}

    // Scan mesh, return one Patch per bad-TET cluster (after ring expansion).
    // Returns empty vector if no bad TETs found in the requested PIDs.
    std::vector<Patch> extract(const Mesh& mesh);

    const std::string& getLastDiagnostic() const { return diag_; }

private:
    Config cfg_;
    std::string diag_;
};

}  // namespace remesh
}  // namespace KooRemapper
