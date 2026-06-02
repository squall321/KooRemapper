#pragma once

#include "core/Mesh.h"
#include "grid/ConnectivityAnalyzer.h"
#include "grid/StructuredGridIndexer.h"
#include "grid/BoundaryExtractor.h"
#include "grid/EdgeCalculator.h"
#include "mapper/ParametricMapper.h"
#include "mapper/UnstructuredMeshAnalyzer.h"
#include <functional>
#include <set>
#include <string>

// Knowledge graph (lat.md):
//   @lat: [[modules/mapper]]

namespace KooRemapper {

/**
 * Statistics about the mapping operation
 */
struct MappingStats {
    int nodesProcessed;
    int elementsProcessed;
    double minJacobian;
    double maxJacobian;
    double avgJacobian;
    int invalidElements;  // Elements with negative Jacobian
    int reorientedElements;  // Elements whose connectivity was swapped to match source sign
    double processingTimeMs;

    // Source mesh diagnostics (pre-map): tells whether the source flat mesh
    // already has invalid HEX8 elements before mapping starts. Useful for
    // distinguishing "source was bad" from "mapping broke it".
    int sourceHex8Count;
    int sourcePosJacCount;
    int sourceNegJacCount;
    int sourceDegenerateCount;
    double sourceMinJac;
    double sourceMaxJac;

    MappingStats() : nodesProcessed(0), elementsProcessed(0),
                     minJacobian(0), maxJacobian(0), avgJacobian(0),
                     invalidElements(0), reorientedElements(0), processingTimeMs(0),
                     sourceHex8Count(0), sourcePosJacCount(0), sourceNegJacCount(0),
                     sourceDegenerateCount(0), sourceMinJac(0), sourceMaxJac(0) {}
};

/**
 * Main class for remapping an unstructured mesh using a bent structured mesh as reference
 */
class MeshRemapper {
public:
    using ProgressCallback = std::function<void(int percent)>;

    MeshRemapper();
    ~MeshRemapper() = default;

    /**
     * Set the bent structured mesh (reference for bending)
     */
    void setBentMesh(const Mesh* mesh);

    /**
     * Set the flat unstructured mesh (to be mapped)
     */
    void setFlatMesh(const Mesh* mesh);

    /**
     * Run only the bent-mesh analysis (step1 + step2) so that neutral
     * arc lengths and parametric topology are available without paying the
     * cost of node mapping. Used by the bbox-align preprocessor in
     * runMapping() to learn the bent ijk lengths before deciding whether
     * to rescale the source/target mesh. After this returns true, the
     * getNeutralSize{I,J,K}() and getTopologyDiagnostic() accessors are
     * valid; performMapping() can still be called afterward to do the
     * actual mapping.
     */
    bool analyzeBentOnly();

    /**
     * Perform the mapping operation
     * @param useParallel Use parallel processing (default: true)
     * @return true if successful
     */
    bool performMapping(bool useParallel = true);

    /**
     * Get the result mesh (bent unstructured)
     */
    const Mesh& getResult() const { return resultMesh_; }
    Mesh& getResult() { return resultMesh_; }

    /**
     * Get mapping statistics
     */
    const MappingStats& getStats() const { return stats_; }

    /**
     * Get error message if mapping failed
     */
    const std::string& getErrorMessage() const { return errorMessage_; }

    /**
     * Set progress callback
     */
    void setProgressCallback(ProgressCallback callback) {
        progressCallback_ = callback;
    }

    /**
     * Get the neutral grid generator's output size
     */
    double getNeutralSizeI() const;
    double getNeutralSizeJ() const;
    double getNeutralSizeK() const;

    /**
     * Topology diagnostic from ParametricMapper::validateTopology, surfaced
     * for command-level reporting. Empty when no special topology detected.
     */
    const std::string& getTopologyDiagnostic() const { return topologyDiagnostic_; }

    /** Interior-grid lookup statistics from ParametricMapper. */
    long long getGridFilledCount() const { return paramMapper_.getGridFilledCount(); }
    long long getGridTotalCount()  const { return paramMapper_.getGridTotalCount(); }
    bool isGridLookupActive() const { return paramMapper_.isGridLookupActive(); }

    /**
     * Get auto-detected axis mapping: detail XYZ -> bent ijk
     * Returns array of 3 ints; values 0=i, 1=j, 2=k
     */
    void getAxisMap(int out[3]) const {
        out[0] = axisMap_[0]; out[1] = axisMap_[1]; out[2] = axisMap_[2];
    }

    /**
     * Disable auto axis mapping (use identity X->i, Y->j, Z->k)
     */
    void setAxisMapAuto(bool enable) { axisMapAuto_ = enable; }

    /**
     * Force mapped element Jacobians to be strictly positive by swapping
     * connectivity whenever jacBent < 0, regardless of the source element's
     * own Jacobian sign. Default (false) preserves source sign: if source
     * was right-handed, mapped is right-handed; if source was left-handed
     * (CW winding), mapped stays left-handed. Use this when the source
     * has unreliable winding and you want a guaranteed-valid output for
     * LS-DYNA submission. Ignored for elements with |jacBent| < 1e-15.
     */
    void setForcePositive(bool enable) { forcePositive_ = enable; }
    bool getForcePositive() const { return forcePositive_; }

    /**
     * Restrict mapping to nodes referenced by elements with PID in this set.
     * Empty set (default) = no filter, every element-referenced node is
     * mapped. When set, only elements whose partId is in the set contribute
     * to the referenced-node set; nodes NOT referenced by any of those
     * elements (orphans + nodes belonging only to non-target PIDs) pass
     * through with their original positions.
     *
     * Shared-interface caveat: an interface node referenced by both a target
     * PID and a non-target PID IS in the referenced set (because it belongs
     * to a target element) and therefore gets mapped. The non-target PID's
     * element sharing that node will be partially deformed at the interface.
     * If a user wants the non-target PID to stay completely rigid, they
     * should run `disconnect` first to decouple the interface nodes.
     */
    void setTargetPids(const std::set<int>& pids) { targetPids_ = pids; }
    const std::set<int>& getTargetPids() const { return targetPids_; }

    /**
     * Mirror the mapped output along one or more global axes (X / Y / Z).
     * Each axis with the corresponding flag = true gets its node coordinate
     * negated. To preserve element handedness (positive Jacobian), HEX8
     * connectivity n[0..3] <-> n[4..7] is swapped if the total number of
     * mirrored axes is ODD. With even count the parity is preserved
     * automatically (two reflections compose to a rotation).
     *
     * Use case: detail mesh was authored in one Z convention; the bent
     * model expects the opposite. A single --flip-z post-step yields a
     * valid mirrored mesh without re-authoring the source.
     */
    void setOutputFlip(bool fx, bool fy, bool fz) {
        flipOutX_ = fx; flipOutY_ = fy; flipOutZ_ = fz;
    }

private:
    const Mesh* bentMesh_;
    const Mesh* flatMesh_;
    Mesh resultMesh_;

    // Analysis components
    ConnectivityAnalyzer connectivity_;
    StructuredGridIndexer indexer_;
    BoundaryExtractor boundary_;
    EdgeCalculator edgeCalc_;
    ParametricMapper paramMapper_;
    UnstructuredMeshAnalyzer flatAnalyzer_;

    MappingStats stats_;
    std::string errorMessage_;
    std::string topologyDiagnostic_;
    ProgressCallback progressCallback_;

    // Processing steps
    bool step1_AnalyzeBentMesh();
    bool step2_BuildParametricSpace();
    bool step3_AnalyzeFlatMesh();
    bool step4_MapNodes();
    bool step4_MapNodesParallel();  // Parallel version of step4
    bool step5_CopyElements();
    bool step6_ValidateResult();
    bool step6_ValidateResultParallel();  // Parallel version of step6

    // Parallel processing flag
    bool useParallel_;

    // Geometry detection
    bool detectUFoldGeometry() const;

    // Layer ordering flip flags (to match FlatMeshGenerator)
    bool flipI_;
    bool flipJ_;
    bool flipK_;

    // Axis mapping: detail XYZ -> bent ijk
    //   axisMap_[d] = which ijk-axis (0=i,1=j,2=k) the detail's d-axis (0=X,1=Y,2=Z) maps to
    // Determined by matching axis lengths (longest detail axis -> longest bent axis, etc.)
    int axisMap_[3];
    bool axisMapAuto_;  // true = auto-detect, false = identity (X->i, Y->j, Z->k)
    bool forcePositive_ = false;  // see setForcePositive() doc
    bool flipOutX_ = false, flipOutY_ = false, flipOutZ_ = false;  // see setOutputFlip()

    // Subset of PIDs whose elements contribute to the mapped-node set.
    // Empty = map every element-referenced node (default behavior).
    std::set<int> targetPids_;

    // Analyze bent mesh to determine if i/j/k need flipping
    void analyzeLayerOrientation();

    // Match detail flat axes to bent ijk axes by sorted length
    void computeAxisMapping();

    // Pre-map analysis of source flat mesh: counts pos/neg/degenerate HEX8
    // Jacobians and stores results into stats_. Helps users diagnose whether
    // a problem originates in their source mesh vs. in the mapping itself.
    void analyzeSourceMesh();

    // Sample-based orientation correction: ensure mapped element Jacobian
    // sign matches the source flat element's sign by toggling one flip if
    // the combined effect of axisMap permutation parity and analyzeLayer-
    // Orientation flips inverts orientation.
    void correctOrientationBySample();

    // Per-element orientation preservation: after the global flip is set,
    // some elements may still have sign mismatches if the source mesh has
    // mixed HEX8 winding. For each such element, swap n[0..3] <-> n[4..7]
    // to restore matching sign. See reorientMappedElements() body for
    // stress-handling notes (safe for NINT=1, requires list reorder for
    // NINT>1 when stress data is attached -- currently map pipeline has
    // no stress so this is only a guard for future workflows).
    void reorientMappedElements();

    /**
     * Mirror result mesh along selected global axes; swap HEX8 connectivity
     * to preserve handedness if the parity is odd. No-op if no flip flag set.
     */
    void applyOutputFlip();

    // Fix elements with negative Jacobian by reordering nodes (optional, disabled by default)
    void fixNegativeJacobians();

    void reportProgress(int percent);
};

} // namespace KooRemapper
