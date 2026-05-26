#pragma once

#include "remesh/RemeshTask.h"

// Knowledge graph (lat.md):
//   @lat: [[modules/remesh]]

namespace KooRemapper {
namespace remesh {

// =============================================================================
// Abstract backend interface for local TET patch remeshing.
//
// Two implementations exist (selected at orchestrator level):
//   * LocalImproveRemesher  - self-contained smoothing + subdivide. No
//                             external dependency. Phase A.
//   * TetGenRemesher        - constrained Delaunay tetrahedralization via
//                             third_party/tetgen (AGPL v3). Phase B.
//
// Both consume the same RemeshTask and produce the same RemeshResult so the
// orchestrator can swap them at runtime via a single config flag without
// rewriting glue code.
// =============================================================================

class Remesher {
public:
    virtual ~Remesher() = default;

    // Remesh a single patch. Must be reentrant (called once per patch by the
    // orchestrator, possibly across many PIDs and many bad-TET clusters).
    virtual RemeshResult run(const RemeshTask& task) = 0;

    // Backend identification for diagnostic logging.
    virtual const char* name() const = 0;
};

}  // namespace remesh
}  // namespace KooRemapper
