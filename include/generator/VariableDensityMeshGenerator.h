#pragma once

#include "generator/VariableDensityConfig.h"
#include "core/Mesh.h"
#include <vector>
#include <string>
#include <functional>

namespace KooRemapper {

/**
 * Statistics from mesh generation
 */
struct VariableDensityStats {
    double scaleFactor;
    
    // Actual lengths after scaling
    double zone1Length;
    double zone2Length;
    double zone3Length;
    double zone4Length;
    double zone5Length;
    double totalLengthI;
    double totalLengthJ;
    double totalLengthK;
    
    // Element sizes
    double denseElementSize;
    double sparseElementSize;
    double sizeRatio;
    
    // Counts
    int totalElementsI;
    int totalElementsJ;
    int totalElementsK;
    int totalElements;
    int totalNodes;
};

/**
 * Generator for variable density flat meshes
 * 
 * Creates meshes with:
 * - Dense regions at bend locations
 * - Sparse regions in flat areas
 * - Smooth transitions between
 */
class VariableDensityMeshGenerator {
public:
    using ProgressCallback = std::function<void(int percent)>;
    
    VariableDensityMeshGenerator();
    ~VariableDensityMeshGenerator() = default;
    
    /**
     * Generate mesh from configuration
     * @param config Mesh configuration
     * @return Generated mesh
     */
    Mesh generate(const VariableDensityConfig& config);
    
    /**
     * Generate mesh with reference scaling
     * @param config Mesh configuration
     * @param refLengthI Reference length in I direction
     * @param refLengthJ Reference length in J direction
     * @param refLengthK Reference length in K direction
     * @return Generated mesh
     */
    Mesh generate(const VariableDensityConfig& config,
                  double refLengthI, double refLengthJ, double refLengthK);
    
    /**
     * Set progress callback
     */
    void setProgressCallback(ProgressCallback callback) {
        progressCallback_ = callback;
    }
    
    /**
     * Get generation statistics
     */
    const VariableDensityStats& getStats() const { return stats_; }
    
    /**
     * Get error message
     */
    const std::string& getErrorMessage() const { return errorMessage_; }

private:
    ProgressCallback progressCallback_;
    VariableDensityStats stats_;
    std::string errorMessage_;
    
    /**
     * Compute X coordinates with variable spacing
     */
    std::vector<double> computeXCoordinates(
        const VariableDensityConfig& config,
        double scaleFactor);
    
    /**
     * Compute transition zone spacing
     * @param startSize Starting element size
     * @param endSize Ending element size
     * @param numElements Number of elements
     * @param growthType Type of growth
     * @return Vector of element sizes
     */
    std::vector<double> computeTransitionSpacing(
        double startSize, double endSize, int numElements,
        GrowthType growthType);
    
    /**
     * Generate uniform spacing
     */
    std::vector<double> computeUniformSpacing(
        double length, int numElements);
    
    /**
     * Create mesh from coordinate arrays
     */
    Mesh createMesh(
        const std::vector<double>& xCoords,
        double lengthJ, double lengthK,
        int elementsJ, int elementsK,
        bool centerAtOrigin);
    
    void reportProgress(int percent);
};

} // namespace KooRemapper
