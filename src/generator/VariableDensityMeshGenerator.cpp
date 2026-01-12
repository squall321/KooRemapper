#include "generator/VariableDensityMeshGenerator.h"
#include <cmath>
#include <stdexcept>

namespace KooRemapper {

VariableDensityMeshGenerator::VariableDensityMeshGenerator()
    : progressCallback_(nullptr)
{}

Mesh VariableDensityMeshGenerator::generate(const VariableDensityConfig& config) {
    // Use config's reference dimensions if available
    double refI = config.reference.lengthI;
    double refJ = config.reference.lengthJ;
    double refK = config.reference.lengthK;
    
    if (refI <= 0) refI = config.getTotalLength();
    if (refJ <= 0) refJ = 1.0;  // Default
    if (refK <= 0) refK = 1.0;  // Default
    
    return generate(config, refI, refJ, refK);
}

Mesh VariableDensityMeshGenerator::generate(
    const VariableDensityConfig& config,
    double refLengthI, double refLengthJ, double refLengthK)
{
    // Validate config
    std::string error;
    if (!config.validate(error)) {
        errorMessage_ = error;
        throw std::runtime_error(error);
    }
    
    reportProgress(5);
    
    // Compute X coordinates (this auto-scales to match refLengthI)
    std::vector<double> xCoords = computeXCoordinates(config, refLengthI);
    
    // Calculate actual zone lengths from coordinates
    // We need to trace through the coordinates to get zone boundaries
    int idx = 0;
    double zone1End = 0, zone2End = 0, zone3End = 0, zone4End = 0;
    
    idx += config.zone1_denseStart.numElements;
    if (idx < static_cast<int>(xCoords.size())) zone1End = xCoords[idx];
    
    idx += config.zone2_increasing.numElements;
    if (idx < static_cast<int>(xCoords.size())) zone2End = xCoords[idx];
    
    idx += config.zone3_sparse.numElements;
    if (idx < static_cast<int>(xCoords.size())) zone3End = xCoords[idx];
    
    idx += config.zone4_decreasing.numElements;
    if (idx < static_cast<int>(xCoords.size())) zone4End = xCoords[idx];
    
    double totalLength = xCoords.empty() ? 0 : xCoords.back();
    
    // Store stats with actual computed lengths
    stats_.zone1Length = zone1End;
    stats_.zone2Length = zone2End - zone1End;
    stats_.zone3Length = zone3End - zone2End;
    stats_.zone4Length = zone4End - zone3End;
    stats_.zone5Length = totalLength - zone4End;
    stats_.totalLengthI = totalLength;
    stats_.totalLengthJ = refLengthJ;
    stats_.totalLengthK = refLengthK;
    
    // Compute element sizes
    if (config.zone1_denseStart.numElements > 0) {
        stats_.denseElementSize = stats_.zone1Length / config.zone1_denseStart.numElements;
    }
    if (config.zone3_sparse.numElements > 0) {
        stats_.sparseElementSize = stats_.zone3Length / config.zone3_sparse.numElements;
    }
    stats_.sizeRatio = (stats_.denseElementSize > 0) ? 
        stats_.sparseElementSize / stats_.denseElementSize : 0;
    
    // Scale factor is now computed internally, but we can show it
    double uniformSum = config.zone1_denseStart.length + config.zone3_sparse.length + config.zone5_denseEnd.length;
    stats_.scaleFactor = (uniformSum > 0) ? stats_.totalLengthI / uniformSum : 1.0;
    
    stats_.totalElementsI = config.getTotalElementsI();
    stats_.totalElementsJ = config.elementsJ;
    stats_.totalElementsK = config.elementsK;
    stats_.totalElements = config.getTotalElements();
    
    reportProgress(20);
    
    // Create mesh
    Mesh mesh = createMesh(xCoords, refLengthJ, refLengthK,
                          config.elementsJ, config.elementsK,
                          config.centerAtOrigin);
    
    stats_.totalNodes = static_cast<int>(mesh.getNodeCount());
    
    reportProgress(100);
    
    return mesh;
}

std::vector<double> VariableDensityMeshGenerator::computeXCoordinates(
    const VariableDensityConfig& config,
    double targetLength)
{
    // Step 1: Calculate uniform zone sizes (unscaled, based on config ratios)
    double uniformLengthSum = config.zone1_denseStart.length + 
                              config.zone3_sparse.length + 
                              config.zone5_denseEnd.length;
    
    // Compute element sizes based on config ratios
    double denseSize = (config.zone1_denseStart.numElements > 0) ?
        config.zone1_denseStart.length / config.zone1_denseStart.numElements : 0.1;
    double sparseSize = (config.zone3_sparse.numElements > 0) ?
        config.zone3_sparse.length / config.zone3_sparse.numElements : 1.0;
    
    // Step 2: Compute transition zone lengths (auto-calculated from sizes)
    double zone2Length = 0;
    if (config.zone2_increasing.numElements > 0) {
        auto spacing = computeTransitionSpacing(
            denseSize, sparseSize,
            config.zone2_increasing.numElements,
            config.zone2_increasing.growthType);
        for (double dx : spacing) zone2Length += dx;
    }
    
    double zone4Length = 0;
    if (config.zone4_decreasing.numElements > 0) {
        auto spacing = computeTransitionSpacing(
            sparseSize, denseSize,
            config.zone4_decreasing.numElements,
            config.zone4_decreasing.growthType);
        for (double dx : spacing) zone4Length += dx;
    }
    
    // Step 3: Calculate total unscaled length
    double totalUnscaled = uniformLengthSum + zone2Length + zone4Length;
    
    // Step 4: Compute final scale factor to match target length
    double finalScale = targetLength / totalUnscaled;
    
    // Step 5: Generate coordinates with final scaling
    std::vector<double> coords;
    coords.push_back(0.0);
    double currentX = 0.0;
    
    // Zone 1: Dense Start (uniform)
    if (config.zone1_denseStart.numElements > 0) {
        double scaledSize = denseSize * finalScale;
        for (int i = 0; i < config.zone1_denseStart.numElements; ++i) {
            currentX += scaledSize;
            coords.push_back(currentX);
        }
    }
    
    // Zone 2: Increasing (dense -> sparse)
    if (config.zone2_increasing.numElements > 0) {
        auto spacing = computeTransitionSpacing(
            denseSize * finalScale, sparseSize * finalScale,
            config.zone2_increasing.numElements,
            config.zone2_increasing.growthType);
        for (double dx : spacing) {
            currentX += dx;
            coords.push_back(currentX);
        }
    }
    
    // Zone 3: Sparse (uniform)
    if (config.zone3_sparse.numElements > 0) {
        double scaledSize = sparseSize * finalScale;
        for (int i = 0; i < config.zone3_sparse.numElements; ++i) {
            currentX += scaledSize;
            coords.push_back(currentX);
        }
    }
    
    // Zone 4: Decreasing (sparse -> dense)
    if (config.zone4_decreasing.numElements > 0) {
        auto spacing = computeTransitionSpacing(
            sparseSize * finalScale, denseSize * finalScale,
            config.zone4_decreasing.numElements,
            config.zone4_decreasing.growthType);
        for (double dx : spacing) {
            currentX += dx;
            coords.push_back(currentX);
        }
    }
    
    // Zone 5: Dense End (uniform)
    if (config.zone5_denseEnd.numElements > 0) {
        double scaledSize = denseSize * finalScale;
        for (int i = 0; i < config.zone5_denseEnd.numElements; ++i) {
            currentX += scaledSize;
            coords.push_back(currentX);
        }
    }
    
    return coords;
}

std::vector<double> VariableDensityMeshGenerator::computeUniformSpacing(
    double length, int numElements)
{
    std::vector<double> spacing;
    double dx = length / numElements;
    for (int i = 0; i < numElements; ++i) {
        spacing.push_back(dx);
    }
    return spacing;
}

std::vector<double> VariableDensityMeshGenerator::computeTransitionSpacing(
    double startSize, double endSize, int numElements,
    GrowthType growthType)
{
    std::vector<double> spacing;
    if (numElements <= 0) return spacing;
    
    switch (growthType) {
        case GrowthType::LINEAR: {
            // Linear interpolation
            for (int i = 0; i < numElements; ++i) {
                double t = static_cast<double>(i) / (numElements - 1);
                if (numElements == 1) t = 0.5;
                double size = startSize + (endSize - startSize) * t;
                spacing.push_back(size);
            }
            break;
        }
        
        case GrowthType::GEOMETRIC: {
            // Geometric progression
            if (startSize <= 0 || endSize <= 0) {
                // Fall back to linear
                return computeTransitionSpacing(startSize, endSize, numElements, GrowthType::LINEAR);
            }
            double ratio = std::pow(endSize / startSize, 1.0 / (numElements - 1));
            if (numElements == 1) ratio = 1.0;
            double size = startSize;
            for (int i = 0; i < numElements; ++i) {
                spacing.push_back(size);
                size *= ratio;
            }
            break;
        }
        
        case GrowthType::EXPONENTIAL: {
            // Exponential growth (same as geometric in discrete case)
            if (startSize <= 0 || endSize <= 0) {
                return computeTransitionSpacing(startSize, endSize, numElements, GrowthType::LINEAR);
            }
            double logRatio = std::log(endSize / startSize);
            for (int i = 0; i < numElements; ++i) {
                double t = static_cast<double>(i) / (numElements - 1);
                if (numElements == 1) t = 0.5;
                double size = startSize * std::exp(logRatio * t);
                spacing.push_back(size);
            }
            break;
        }
    }
    
    // Normalize to ensure total length is correct
    // (The spacing should fit the zone, but we compute sizes independently)
    // This is intentional - the zone length in config is a "weight" for scaling
    
    return spacing;
}

Mesh VariableDensityMeshGenerator::createMesh(
    const std::vector<double>& xCoords,
    double lengthJ, double lengthK,
    int elementsJ, int elementsK,
    bool centerAtOrigin)
{
    Mesh mesh;
    
    int ni = static_cast<int>(xCoords.size());
    int nj = elementsJ + 1;
    int nk = elementsK + 1;
    
    // Compute offsets for centering
    double offsetX = 0, offsetY = 0, offsetZ = 0;
    if (centerAtOrigin) {
        offsetX = -xCoords.back() / 2.0;
        offsetY = -lengthJ / 2.0;
        offsetZ = -lengthK / 2.0;
    }
    
    // Create nodes
    double dy = lengthJ / elementsJ;
    double dz = lengthK / elementsK;
    
    int nodeId = 1;
    for (int k = 0; k < nk; ++k) {
        double z = k * dz + offsetZ;
        for (int j = 0; j < nj; ++j) {
            double y = j * dy + offsetY;
            for (int i = 0; i < ni; ++i) {
                double x = xCoords[i] + offsetX;
                mesh.addNode(nodeId++, x, y, z);
            }
        }
        
        if (progressCallback_) {
            int progress = 20 + (60 * (k + 1) / nk);
            reportProgress(progress);
        }
    }
    
    // Create elements
    int dimI = ni - 1;
    int dimJ = elementsJ;
    int dimK = elementsK;
    
    int elemId = 1;
    for (int k = 0; k < dimK; ++k) {
        for (int j = 0; j < dimJ; ++j) {
            for (int i = 0; i < dimI; ++i) {
                // HEX8 node numbering (LS-DYNA convention)
                int n1 = 1 + i + j * ni + k * ni * nj;
                int n2 = n1 + 1;
                int n3 = n1 + 1 + ni;
                int n4 = n1 + ni;
                int n5 = n1 + ni * nj;
                int n6 = n2 + ni * nj;
                int n7 = n3 + ni * nj;
                int n8 = n4 + ni * nj;
                
                std::array<int, 8> nodeIds = {n1, n2, n3, n4, n5, n6, n7, n8};
                mesh.addElement(elemId++, 1, nodeIds);  // Part ID = 1
            }
        }
        
        if (progressCallback_) {
            int progress = 80 + (20 * (k + 1) / dimK);
            reportProgress(progress);
        }
    }
    
    // Set grid dimensions
    mesh.setGridDimensions(dimI, dimJ, dimK);
    
    return mesh;
}

void VariableDensityMeshGenerator::reportProgress(int percent) {
    if (progressCallback_) {
        progressCallback_(percent);
    }
}

} // namespace KooRemapper
