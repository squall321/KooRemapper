#include "remesh/RemeshOrchestrator.h"
#include "remesh/LocalImproveRemesher.h"
#include "remesh/TetGenRemesher.h"
#include <algorithm>
#include <cmath>
#include <limits>
#include <sstream>

namespace KooRemapper {
namespace remesh {

namespace {

int findMaxNodeId(const Mesh& m) {
    int mx = 0;
    for (const auto& kv : m.nodes) mx = std::max(mx, kv.first);
    return mx;
}
int findMaxElemId(const Mesh& m) {
    int mx = 0;
    for (const auto& kv : m.elements) mx = std::max(mx, kv.first);
    return mx;
}

}  // namespace

RemeshSummary RemeshOrchestrator::run(Mesh& mesh) {
    RemeshSummary s;
    s.minJacBefore = std::numeric_limits<double>::max();
    s.minJacAfter  = std::numeric_limits<double>::max();

    // 1. Extract patches.
    PatchExtractor ext(patchCfg_);
    auto patches = ext.extract(mesh);
    s.patchCount = (int)patches.size();
    if (!ext.getLastDiagnostic().empty()) {
        s.messages.push_back("[extractor] " + ext.getLastDiagnostic());
    }
    if (patches.empty()) {
        s.minJacBefore = 0.0;
        s.minJacAfter  = 0.0;
        return s;
    }

    // 2. Per-patch process.
    int nextNodeId = findMaxNodeId(mesh) + 1;
    int nextElemId = findMaxElemId(mesh) + 1;

    for (auto& patch : patches) {
        RemeshResult r = backend_->run(patch.task);

        if (r.minJacBefore < s.minJacBefore) s.minJacBefore = r.minJacBefore;

        // Fallback: if primary backend failed and a fallback is available,
        // try the fallback before declaring this patch a loss.
        if (!r.success && fallback_) {
            std::ostringstream warn;
            warn << "[patch fallback] " << backend_->name() << " failed ("
                 << r.message << "); trying " << fallback_->name();
            s.messages.push_back(warn.str());
            r = fallback_->run(patch.task);
        }

        if (!r.success) {
            ++s.patchFailed;
            std::ostringstream msg;
            msg << "[patch fail] " << backend_->name() << ": " << r.message;
            s.messages.push_back(msg.str());
            if (r.minJacBefore < s.minJacAfter) s.minJacAfter = r.minJacBefore;
            continue;
        }

        // 2a. Decide global node IDs for each patch-local index.
        //     - patch.patchToOrig[i] >= 0  -> existing global node, keep ID.
        //       update its position to r.nodes[i].position (free-flagged
        //       boundary or interior node may have moved during smoothing).
        //     - patch.patchToOrig[i] == -1 -> backend added a new node;
        //       this typically only happens for indices >=
        //       patch.patchToOrig.size().
        //     - new nodes appended by backend (i >= patch.patchToOrig.size())
        //       get fresh global IDs.
        std::vector<int> patchIdxToGlobalId(r.nodes.size(), -1);
        size_t inputCount = patch.patchToOrig.size();

        for (size_t i = 0; i < r.nodes.size(); ++i) {
            int globalId;
            if (i < inputCount && patch.patchToOrig[i] >= 0) {
                globalId = patch.patchToOrig[i];
                Node* existing = mesh.getNode(globalId);
                if (existing) {
                    existing->position = r.nodes[i].position;
                    existing->setMappedPosition(r.nodes[i].position);
                } else {
                    // Defensive: re-add if somehow missing.
                    Node n(globalId, r.nodes[i].position);
                    n.setMappedPosition(r.nodes[i].position);
                    mesh.addNode(n);
                }
            } else {
                globalId = nextNodeId++;
                Node n(globalId, r.nodes[i].position);
                n.setMappedPosition(r.nodes[i].position);
                mesh.addNode(n);
                ++s.nodesAdded;
            }
            patchIdxToGlobalId[i] = globalId;
        }

        // 2b. Remove original patch elements.
        int origPid = -1;
        for (int eid : patch.originalElemIds) {
            auto it = mesh.elements.find(eid);
            if (it == mesh.elements.end()) continue;
            if (origPid < 0) origPid = it->second.partId;
            mesh.elements.erase(it);
            ++s.elementsRemoved;
        }
        if (origPid < 0) origPid = 1;

        // 2c. Insert new TET4 elements.
        for (const auto& t : r.tets) {
            int newId = nextElemId++;
            std::array<int, 8> nodeIds;
            int g0 = patchIdxToGlobalId[t.n[0]];
            int g1 = patchIdxToGlobalId[t.n[1]];
            int g2 = patchIdxToGlobalId[t.n[2]];
            int g3 = patchIdxToGlobalId[t.n[3]];
            nodeIds[0] = g0;
            nodeIds[1] = g1;
            nodeIds[2] = g2;
            nodeIds[3] = g3;
            // LS-DYNA TET4 stored as degenerate HEX8: n4..n7 = n3
            nodeIds[4] = g3;
            nodeIds[5] = g3;
            nodeIds[6] = g3;
            nodeIds[7] = g3;
            Element e(newId, origPid, nodeIds);
            e.type = ElementType::TET4;
            mesh.addElement(e);
            ++s.elementsAdded;
        }

        ++s.patchSucceeded;
        s.messages.push_back("[patch ok] " + std::string(backend_->name()) +
                             ": " + r.message);
        if (r.minJacAfter < s.minJacAfter) s.minJacAfter = r.minJacAfter;
    }

    if (s.minJacBefore == std::numeric_limits<double>::max()) s.minJacBefore = 0.0;
    if (s.minJacAfter  == std::numeric_limits<double>::max()) s.minJacAfter  = 0.0;
    return s;
}

RemeshSummary RemeshOrchestrator::report(const Mesh& mesh) {
    // Mesh is taken by const ref but PatchExtractor needs Mesh& (it
    // doesn't actually mutate; cast is safe). Only quality is reported,
    // no backend invocation, no node/element changes.
    PatchExtractor ext(patchCfg_);
    auto patches = ext.extract(const_cast<Mesh&>(mesh));

    RemeshSummary s;
    s.patchCount = (int)patches.size();
    s.minJacBefore = std::numeric_limits<double>::max();
    s.minJacAfter  = 0.0;
    if (!ext.getLastDiagnostic().empty()) {
        s.messages.push_back("[extractor] " + ext.getLastDiagnostic());
    }

    // Per-patch quality histogram: count by bucket.
    int buckets[6] = {0,0,0,0,0,0};  // <0, [0,0.1), [0.1,0.2), [0.2,0.5), [0.5,0.7), [0.7,1]
    auto bucket = [](double q) {
        if (q < 0.0)   return 0;
        if (q < 0.1)   return 1;
        if (q < 0.2)   return 2;
        if (q < 0.5)   return 3;
        if (q < 0.7)   return 4;
        return 5;
    };

    for (auto& patch : patches) {
        for (const auto& t : patch.task.originalTets) {
            const Vector3D& p0 = patch.task.nodes[t.n[0]].position;
            const Vector3D& p1 = patch.task.nodes[t.n[1]].position;
            const Vector3D& p2 = patch.task.nodes[t.n[2]].position;
            const Vector3D& p3 = patch.task.nodes[t.n[3]].position;
            Vector3D e1 = p1 - p0, e2 = p2 - p0, e3 = p3 - p0;
            double V = e1.dot(e2.cross(e3)) / 6.0;
            double e01 = (p1 - p0).magnitude();
            double e02 = (p2 - p0).magnitude();
            double e03 = (p3 - p0).magnitude();
            double e12 = (p2 - p1).magnitude();
            double e13 = (p3 - p1).magnitude();
            double e23 = (p3 - p2).magnitude();
            double maxE = std::max({e01, e02, e03, e12, e13, e23});
            double q = (maxE > 1e-12)
                       ? (V / (maxE * maxE * maxE)) / 0.11785113019775793
                       : 0.0;
            if (q < s.minJacBefore) s.minJacBefore = q;
            ++buckets[bucket(q)];
        }
    }
    if (s.minJacBefore == std::numeric_limits<double>::max()) s.minJacBefore = 0.0;

    std::ostringstream m;
    m << "[quality histogram across "
      << (buckets[0]+buckets[1]+buckets[2]+buckets[3]+buckets[4]+buckets[5])
      << " TETs in selected patches]\n"
      << "  scaled Jac < 0          : " << buckets[0] << " (inverted)\n"
      << "  scaled Jac [ 0  , 0.10) : " << buckets[1] << " (very poor)\n"
      << "  scaled Jac [0.10, 0.20) : " << buckets[2] << " (poor)\n"
      << "  scaled Jac [0.20, 0.50) : " << buckets[3] << " (acceptable)\n"
      << "  scaled Jac [0.50, 0.70) : " << buckets[4] << " (good)\n"
      << "  scaled Jac [0.70, 1.00] : " << buckets[5] << " (excellent)";
    s.messages.push_back(m.str());
    return s;
}

namespace {

// Independently compute the worst scaled-Jac among TET4 elements whose
// 4 vertices all lie in `region`. Used by runIterative to track quality
// without depending on backend-reported values (which can be 0 when a
// backend stub returns failure without scoring).
double regionMinScaledJac(const Mesh& mesh, const std::set<int>& region) {
    static const double EQ_NORM = 0.11785113019775793;  // sqrt(2)/12
    double mn = std::numeric_limits<double>::max();
    for (const auto& kv : mesh.elements) {
        const Element& e = kv.second;
        if (e.type != ElementType::TET4) continue;
        bool inside = true;
        for (int j = 0; j < 4; ++j) {
            if (region.find(e.nodeIds[j]) == region.end()) { inside = false; break; }
        }
        if (!inside) continue;
        const Node* p0 = mesh.getNode(e.nodeIds[0]);
        const Node* p1 = mesh.getNode(e.nodeIds[1]);
        const Node* p2 = mesh.getNode(e.nodeIds[2]);
        const Node* p3 = mesh.getNode(e.nodeIds[3]);
        if (!p0 || !p1 || !p2 || !p3) continue;
        Vector3D e1 = p1->position - p0->position;
        Vector3D e2 = p2->position - p0->position;
        Vector3D e3 = p3->position - p0->position;
        double V = e1.dot(e2.cross(e3)) / 6.0;
        double e01 = (p1->position - p0->position).magnitude();
        double e02 = (p2->position - p0->position).magnitude();
        double e03 = (p3->position - p0->position).magnitude();
        double e12 = (p2->position - p1->position).magnitude();
        double e13 = (p3->position - p1->position).magnitude();
        double e23 = (p3->position - p2->position).magnitude();
        double maxE = std::max({e01, e02, e03, e12, e13, e23});
        if (maxE < 1e-12) continue;
        double q = (V / (maxE * maxE * maxE)) / EQ_NORM;
        if (q < mn) mn = q;
    }
    return (mn == std::numeric_limits<double>::max()) ? 0.0 : mn;
}

}  // namespace

RemeshOrchestrator::IterativeResult
RemeshOrchestrator::runIterative(Mesh& mesh, const IterativeOptions& opts) {
    IterativeResult result;
    result.bestIteration = -1;
    result.bestMinJac = -std::numeric_limits<double>::max();

    // Strategy chain — only NON-DESTRUCTIVE stages, as per user policy
    // "요소를 쪼개기보다는 리메쉬를 해야" (rebuild rather than subdivide):
    //   stage 0: TetGen CDT remesh (boundary-preserving, true topology rebuild)
    //   stage 1: smoothing + 2-3 swap (Laplacian + topology repair, no subdivide)
    // Subdivide is INTENTIONALLY excluded — it monotonically increases
    // element count without improving worst-case Jacobian and was observed
    // to drive minJac negative on bent/thin patches.
    auto tetgenRemesh = std::make_shared<TetGenRemesher>();
    auto smoothSwap   = std::make_shared<LocalImproveRemesher>();

    PatchExtractor::Config savedCfg = patchCfg_;
    bool startedExplicit =
        (patchCfg_.selectionMode == PatchExtractor::SelectionMode::EXPLICIT_IDS);

    // Track the *physical region* we're working in via node IDs. After a
    // stage rebuilds elements, original element IDs are gone but the bulk
    // of the nodes remain (only subdivide adds new interior nodes). We
    // use this set to re-derive explicit element IDs each iteration so
    // BAD_QUALITY scanning never escapes the user-selected region into
    // the rest of the mesh (which previously caused unbounded growth).
    std::set<int> trackedNodeIds;
    {
        PatchExtractor probe(patchCfg_);
        auto patches0 = probe.extract(mesh);
        for (const auto& p : patches0) {
            for (int nid : p.originalNodeIds) trackedNodeIds.insert(nid);
        }
    }

    auto rebuildExplicitFromRegion = [&]() {
        std::vector<int> ids;
        ids.reserve(trackedNodeIds.size());
        for (const auto& kv : mesh.elements) {
            const Element& e = kv.second;
            if (e.type != ElementType::TET4) continue;
            // TET4 stored as degenerate HEX8: nodes 0..3 are the real verts.
            bool inside = true;
            for (int j = 0; j < 4; ++j) {
                if (trackedNodeIds.find(e.nodeIds[j]) == trackedNodeIds.end()) {
                    inside = false;
                    break;
                }
            }
            if (inside) ids.push_back(kv.first);
        }
        return ids;
    };

    auto refreshTrackedNodes = [&](const std::vector<int>& currentIds) {
        for (int eid : currentIds) {
            auto it = mesh.elements.find(eid);
            if (it == mesh.elements.end()) continue;
            const Element& e = it->second;
            for (int j = 0; j < 4; ++j) trackedNodeIds.insert(e.nodeIds[j]);
        }
    };

    Mesh bestMesh = mesh;
    double prevMinJac = -std::numeric_limits<double>::max();

    for (int iter = 0; iter < opts.maxIterations; ++iter) {
        // For every iteration (including iter 0 when started bad-quality),
        // pin the selection to the tracked region. This stops bad-quality
        // mode from leaking into healthy parts of the mesh, and keeps
        // explicit_ids "seed" elements in sync with current mesh state
        // after stages mutate IDs.
        std::vector<int> currentIds = rebuildExplicitFromRegion();
        if (currentIds.empty()) {
            // Region completely consumed (shouldn't happen in normal flow);
            // bail rather than trigger a global scan.
            break;
        }
        patchCfg_.selectionMode      = PatchExtractor::SelectionMode::EXPLICIT_IDS;
        patchCfg_.selectedElementIds = currentIds;
        // Region already encompasses what we want; don't grow it further.
        patchCfg_.ringExpand         = (iter == 0 ? savedCfg.ringExpand : 0);

        RemeshSummary aggregate;
        // True quality of the region BEFORE this iteration's stages.
        aggregate.minJacBefore = regionMinScaledJac(mesh, trackedNodeIds);
        aggregate.minJacAfter  = aggregate.minJacBefore;

        // Stage 0: TetGen CDT remesh — true topology rebuild that respects
        // the patch boundary triangulation. When TetGen is not built in,
        // each patch returns success=false and we fall through to stage 1.
        {
            patchCfg_.allowSubdivide     = false;
            patchCfg_.selectedElementIds = currentIds;
            patchCfg_.ringExpand         = (iter == 0 ? savedCfg.ringExpand : 0);
            auto savedBackend = backend_;
            backend_ = tetgenRemesh;
            RemeshSummary s = run(mesh);
            backend_ = savedBackend;
            aggregate.patchCount      += s.patchCount;
            aggregate.patchSucceeded  += s.patchSucceeded;
            aggregate.patchFailed     += s.patchFailed;
            aggregate.elementsRemoved += s.elementsRemoved;
            aggregate.elementsAdded   += s.elementsAdded;
            aggregate.nodesAdded      += s.nodesAdded;
            currentIds = rebuildExplicitFromRegion();
            refreshTrackedNodes(currentIds);
            double regionAfter = regionMinScaledJac(mesh, trackedNodeIds);
            aggregate.minJacAfter = regionAfter;
            if (opts.verbose) {
                std::ostringstream m;
                m << "  [stage tetgen-cdt]   patches=" << s.patchCount
                  << "  minJac region " << aggregate.minJacBefore
                  << " -> " << regionAfter;
                if (s.patchFailed > 0) m << " (failed=" << s.patchFailed << ")";
                aggregate.messages.push_back(m.str());
            }
        }

        // Stage 1: Laplacian smoothing + 2-3 swap on the (now post-CDT)
        // mesh. Cleans up sliver tets that survived TetGen and polishes
        // interior node positions. NO subdivide.
        if (aggregate.minJacAfter < opts.qualityTarget && !currentIds.empty()) {
            patchCfg_.allowSubdivide     = false;
            patchCfg_.selectedElementIds = currentIds;
            patchCfg_.ringExpand         = 0;
            auto savedBackend = backend_;
            backend_ = smoothSwap;
            double before = aggregate.minJacAfter;
            RemeshSummary s = run(mesh);
            backend_ = savedBackend;
            aggregate.patchSucceeded += s.patchSucceeded;
            aggregate.elementsRemoved += s.elementsRemoved;
            aggregate.elementsAdded   += s.elementsAdded;
            aggregate.nodesAdded      += s.nodesAdded;
            currentIds = rebuildExplicitFromRegion();
            refreshTrackedNodes(currentIds);
            double regionAfter = regionMinScaledJac(mesh, trackedNodeIds);
            aggregate.minJacAfter = regionAfter;
            if (opts.verbose) {
                std::ostringstream m;
                m << "  [stage smooth+swap]  patches=" << s.patchCount
                  << "  minJac region " << before << " -> " << regionAfter;
                aggregate.messages.push_back(m.str());
            }
        }
        (void)startedExplicit;

        if (aggregate.minJacBefore == std::numeric_limits<double>::max())
            aggregate.minJacBefore = 0.0;
        if (aggregate.minJacAfter == std::numeric_limits<double>::max())
            aggregate.minJacAfter = 0.0;

        result.perIteration.push_back(aggregate);
        result.iterationsRun = iter + 1;

        double curMinJac = aggregate.minJacAfter;
        if (curMinJac > result.bestMinJac) {
            result.bestMinJac    = curMinJac;
            result.bestIteration = iter;
            if (opts.keepBest) bestMesh = mesh;
        }

        if (curMinJac >= opts.qualityTarget) {
            result.targetReached = true;
            break;
        }
        if (aggregate.patchCount == 0) break;
        if (iter > 0 && std::abs(curMinJac - prevMinJac) < opts.convergenceTol) {
            break;
        }
        prevMinJac = curMinJac;
    }

    if (opts.keepBest && result.bestIteration >= 0) {
        mesh = bestMesh;
    }
    patchCfg_ = savedCfg;
    return result;
}

}  // namespace remesh
}  // namespace KooRemapper
