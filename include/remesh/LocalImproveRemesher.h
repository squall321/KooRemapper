#pragma once

#include "remesh/Remesher.h"

namespace KooRemapper {
namespace remesh {

// =============================================================================
// LocalImproveRemesher  --  Phase A backend
//
// Self-contained TET mesh improvement without external CDT library. Two
// operations applied in alternating outer iterations:
//
//   1. Laplacian smoothing on free nodes
//      - interior nodes: move toward centroid of incident-tet centroids
//      - flat-surface free nodes: same, then project back to tangent plane
//        (motion within node.moveTolerance from initial position)
//      - fixed nodes: untouched
//
//   2. Subdivide bad TETs (Jacobian < target after smoothing)
//      - replace 1 TET with 4 TETs by inserting the centroid as a new
//        interior node, fanning to the 4 original faces
//      - this monotonically improves quality of the WORST element by
//        cutting it into smaller pieces; geometry preserved exactly
//
// Limitation vs. Phase B (TetGen):
//   * No constrained Delaunay topology change. Severely tangled regions
//     where the boundary triangulation itself is the problem cannot be
//     fully resolved -- subdivide reduces tet sizes but inherited bad
//     shape persists.
//   * Achieves ~70-80% recovery on typical mapping-induced distortion;
//     drop-in upgrade to TetGenRemesher recommended for the rest.
// =============================================================================

class LocalImproveRemesher : public Remesher {
public:
    LocalImproveRemesher() = default;
    ~LocalImproveRemesher() override = default;

    RemeshResult run(const RemeshTask& task) override;
    const char* name() const override { return "LocalImprove"; }
};

}  // namespace remesh
}  // namespace KooRemapper
