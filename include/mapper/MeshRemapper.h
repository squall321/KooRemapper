#pragma once

#include "core/Mesh.h"
#include "grid/ConnectivityAnalyzer.h"
#include "grid/StructuredGridIndexer.h"
#include "grid/BoundaryExtractor.h"
#include "grid/EdgeCalculator.h"
#include "mapper/ParametricMapper.h"
#include "mapper/UnstructuredMeshAnalyzer.h"
#include <functional>
#include <string>

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
    double processingTimeMs;

    MappingStats() : nodesProcessed(0), elementsProcessed(0),
                     minJacobian(0), maxJacobian(0), avgJacobian(0),
                     invalidElements(0), processingTimeMs(0) {}
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
     * Perform the mapping operation
     * @return true if successful
     */
    bool performMapping();

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
    ProgressCallback progressCallback_;

    // Processing steps
    bool step1_AnalyzeBentMesh();
    bool step2_BuildParametricSpace();
    bool step3_AnalyzeFlatMesh();
    bool step4_MapNodes();
    bool step5_CopyElements();
    bool step6_ValidateResult();

    // Geometry detection
    bool detectUFoldGeometry() const;

    void reportProgress(int percent);
};

} // namespace KooRemapper
