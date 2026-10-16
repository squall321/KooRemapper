#pragma once

#include "remesh/PatchExtractor.h"
#include "remesh/Remesher.h"
#include "core/Mesh.h"
#include <memory>
#include <string>
#include <vector>

// Knowledge graph (lat.md):
//   @lat: [[modules/remesh]]

namespace KooRemapper {
namespace remesh {

// =============================================================================
// RemeshOrchestrator
//
// Top-level driver that owns the patch loop and the splice-back logic so
// any Remesher backend just sees `RemeshTask -> RemeshResult`. Lifecycle:
//
//   1. PatchExtractor scans the mesh and emits one Patch per bad-TET cluster
//   2. For each Patch:
//        a. invoke backend.run(patch.task)
//        b. if success:
//             - delete patch.originalElemIds from mesh
//             - allocate fresh node IDs for newly-added patch nodes
//             - push moved/added nodes back into mesh.nodes
//             - emit new TET4 elements into mesh.elements
//        c. else:
//             - leave the original patch untouched, log the message
//   3. Return summary
//
// Backend selection (passed in by the caller):
//   * std::make_shared<LocalImproveRemesher>()  -- Phase A, no external lib
//   * std::make_shared<TetGenRemesher>()        -- Phase B, AGPL TetGen
//
// Stress / dynain handling
// ------------------------
// This module REMOVES original TET elements and emits new ones with fresh
// IDs. Any per-element data attached to the removed elements (initial
// stress, history variables) is dropped. The remesh step is therefore
// expected to run BEFORE prestress / squeeze / dynain generation in the
// user's workflow. The map command does not propagate stress through the
// mesh, so map -> remesh -> prestress sequencing is safe.
// =============================================================================

struct RemeshSummary {
    int patchCount      = 0;
    int patchSucceeded  = 0;
    int patchFailed     = 0;
    int elementsRemoved = 0;
    int elementsAdded   = 0;
    int nodesAdded      = 0;
    double minJacBefore = 0.0;   // worst across all patches before
    double minJacAfter  = 0.0;   // worst across all patches after
    std::vector<std::string> messages;
};

class RemeshOrchestrator {
public:
    RemeshOrchestrator(PatchExtractor::Config patchCfg,
                       std::shared_ptr<Remesher> backend,
                       std::shared_ptr<Remesher> fallbackBackend = nullptr)
        : patchCfg_(std::move(patchCfg)),
          backend_(std::move(backend)),
          fallback_(std::move(fallbackBackend)) {}

    // Apply remeshing to the mesh in place. Returns a summary describing
    // what changed; caller is responsible for writing the mesh out.
    //
    // If a fallback backend was provided AND the primary backend reports
    // failure for a patch, the fallback is invoked on the same patch
    // before declaring it failed. This is what allows tetgen-primary +
    // localimprove-fallback workflows to recover automatically when
    // TetGen rejects a particularly bad patch.
    RemeshSummary run(Mesh& mesh);

    // Report-only mode: scan all patches, return summary with quality
    // statistics, but do NOT modify the mesh. Useful for calibrating
    // thresholds before committing to a real remesh.
    RemeshSummary report(const Mesh& mesh);

    // Iterative driver. Repeatedly applies `run()` until either the
    // worst-element scaledJac across all patches reaches qualityTarget
    // or maxIterations is exhausted. Each iteration's full mesh state is
    // checkpointed; if `keepBest=true` the best-quality checkpoint is
    // restored on exit (otherwise the latest mesh is kept).
    //
    // Use case: "어떤 요소들을 골라잡고, 잡힌 셋트의 경계는 유지하면서
    // 내부 jacobian이 좋아질 때까지 smoothing/remesh 반복" -- caller
    // configures patchCfg_ in EXPLICIT_IDS mode with the selected element
    // IDs, then calls runIterative() with the desired Jacobian target.
    struct IterativeOptions {
        int    maxIterations  = 10;
        double qualityTarget  = 0.30;   // stop once min scaledJac >=
        double convergenceTol = 0.01;   // stop if no patch improves by this much
        bool   keepBest       = true;   // restore best-quality mesh on exit
        bool   verbose        = true;   // emit per-iteration summary in messages
    };

    struct IterativeResult {
        std::vector<RemeshSummary> perIteration;  // one entry per pass
        int    bestIteration = -1;                // index into perIteration
        double bestMinJac    = 0.0;                // minJac at bestIteration
        bool   targetReached = false;
        int    iterationsRun = 0;
    };

    IterativeResult runIterative(Mesh& mesh, const IterativeOptions& opts);

    // 새 노드·요소 번호의 바닥 — 메시 밖(인클루드 닫힘)에 이미 쓰인 최대값. 새 번호는 메시 최대값과 이 값
    // 둘 다의 위로 낸다(쪼갠 덱 = 쪼개지 않은 덱). 0 이면 메시 최대값만 본다(예전과 같다).
    void setIdFloor(int node, int elem) { nodeFloor_ = node; elemFloor_ = elem; }

private:
    PatchExtractor::Config       patchCfg_;
    std::shared_ptr<Remesher>    backend_;
    std::shared_ptr<Remesher>    fallback_;
    int nodeFloor_ = 0;
    int elemFloor_ = 0;
};

}  // namespace remesh
}  // namespace KooRemapper
