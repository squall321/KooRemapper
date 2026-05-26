#pragma once

#include "core/Vector3D.h"
#include <vector>
#include <string>

// Knowledge graph (lat.md):
//   @lat: [[modules/remesh]]

namespace KooRemapper {
namespace remesh {

// =============================================================================
// Self-contained patch description passed to a Remesher backend.
//
// Coordinates use PATCH-LOCAL indices (0..nodes.size()-1), NOT original mesh
// node IDs. The orchestrator translates between original mesh IDs and patch
// indices on the way in / out. This isolates the backend from global mesh
// state so it can run on any subset of TETs without dragging the whole mesh.
//
// Backends produced for this struct:
//   * LocalImproveRemesher   (Phase A: smoothing + subdivide, no external lib)
//   * TetGenRemesher         (Phase B: third_party/tetgen wrapper)
// Both implement the Remesher abstract interface, so the orchestrator
// switches between them via a config flag.
// =============================================================================

struct PatchNode {
    Vector3D position;       // current physical position
    bool isFixed = true;     // boundary-fixed nodes do NOT move; flat-surface
                             // free nodes may move within tangent plane up to
                             // moveTolerance
    Vector3D tangentNormal;  // surface normal at this node (for free nodes
                             // only; motion constrained to tangent plane).
                             // Length must be 1 if isFixed=false.
    double moveTolerance = 0.0;  // max Euclidean displacement from initial
                                 // position (for free nodes). 0 = no limit.
};

struct PatchTri {
    int n[3];  // patch-local node indices forming a boundary triangle. Order
               // matters: outward normal computed via right-hand rule.
};

struct PatchTet {
    int n[4];  // patch-local node indices. LS-DYNA TET4 vertex convention:
               // n0,n1,n2 form bottom face CCW viewed from n3; n3 is apex.
};

struct RemeshTask {
    std::vector<PatchNode> nodes;
    std::vector<PatchTri> boundaryTris;   // CLOSED surface bounding the patch.
                                          // Backend MUST honor it (preserve
                                          // node positions / topology except
                                          // for nodes flagged isFixed=false).
    std::vector<PatchTet> originalTets;   // existing TETs in the patch. The
                                          // backend replaces them entirely
                                          // with new TETs in the result.

    // Quality targets used by both backends.
    double minJacobianTarget   = 0.20;    // result TETs aim above this
    double maxAspectRatio      = 8.0;
    double minDihedralDeg      = 10.0;

    // Backend-specific hints (Phase A LocalImprove).
    int    laplacianIters      = 5;       // smoothing passes per outer iter
    int    maxOuterIters       = 3;       // smooth -> subdivide cycles
    bool   allowSubdivide      = true;    // if false, smoothing only

    // Backend-specific hints (Phase B TetGen).
    double tetgenQualityRatio  = 1.4;     // -q radius/edge ratio
    double tetgenMinDihedral   = 10.0;    // -qq minimum dihedral angle
};

struct RemeshResult {
    // Updated nodes: indices [0 .. inputNodes.size()-1] correspond to the
    // SAME patch-local indices the input used. New Steiner / interior nodes
    // appended at indices [inputNodes.size() .. nodes.size()-1].
    // The orchestrator allocates fresh global mesh IDs for the new nodes.
    std::vector<PatchNode> nodes;

    // New TETs replacing the input originalTets entirely. Indices reference
    // the result's nodes vector above.
    std::vector<PatchTet> tets;

    // Diagnostics (not all backends populate every field).
    int newNodeCount   = 0;   // == nodes.size() - input.nodes.size()
    int subdivideCount = 0;   // Phase A: subdivided original TETs
    int swapCount      = 0;   // Phase A: edge swaps applied (future)
    int smoothMoves    = 0;   // Phase A: smoothing displacements
    double minJacBefore = 0.0;
    double minJacAfter  = 0.0;

    bool success = false;
    std::string message;      // human-readable status
};

}  // namespace remesh
}  // namespace KooRemapper
