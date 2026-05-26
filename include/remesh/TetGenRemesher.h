#pragma once

#include "remesh/Remesher.h"

// Knowledge graph (lat.md):
//   @lat: [[modules/remesh]]

namespace KooRemapper {
namespace remesh {

// =============================================================================
// TetGenRemesher  --  Phase B backend (constrained Delaunay tetrahedralization)
//
// Wraps third_party/tetgen (Hang Si, AGPL v3).
//
// Build is OPTIONAL via CMake flag KOOREMAPPER_BUILD_TETGEN. When the flag
// is OFF, the .cpp file compiles a stub `run()` that returns
// success=false with a clear "not built" message; callers can detect and
// fall back to LocalImproveRemesher. This lets the rest of the codebase
// compile without dragging in the AGPL TetGen library by default.
//
// Algorithm sketch (when built):
//   1. Translate RemeshTask to tetgenio:
//        - pointlist = patch nodes (fixed first, then free)
//        - facetlist = boundary triangles as polygonal facets
//        - flags: 'p' = constrained tetrahedralization (preserve PSLG)
//                 'q' = quality refinement (radius/edge ratio)
//                 'Y' = no Steiner points on boundary (preserves fixed
//                       boundary nodes); for FREE flat-surface boundary
//                       nodes we emit them as "free" markers and let TetGen
//                       move them within the facet plane.
//   2. Call tetrahedralize().
//   3. Translate output back: node positions, new TET tuples.
//
// The interface promise (Remesher::run) is identical to LocalImprove, so
// the orchestrator can swap backends without other changes.
// =============================================================================

class TetGenRemesher : public Remesher {
public:
    TetGenRemesher() = default;
    ~TetGenRemesher() override = default;

    RemeshResult run(const RemeshTask& task) override;
    const char* name() const override { return "TetGen"; }
};

}  // namespace remesh
}  // namespace KooRemapper
