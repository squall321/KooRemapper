#pragma once

#include <string>
#include <vector>

namespace KooRemapper {

/**
 * Growth type for transition zones
 */
enum class GrowthType {
    LINEAR,      // Linear interpolation
    GEOMETRIC,   // Geometric progression
    EXPONENTIAL  // Exponential growth
};

/**
 * Configuration for a single zone
 */
struct ZoneConfig {
    double length;          // Zone length (will be scaled)
    int numElements;        // Number of elements in this zone
    GrowthType growthType;  // Growth type (for transition zones)
    
    ZoneConfig() : length(0), numElements(0), growthType(GrowthType::LINEAR) {}
    ZoneConfig(double len, int num, GrowthType type = GrowthType::LINEAR)
        : length(len), numElements(num), growthType(type) {}
};

/**
 * Reference mesh specification
 */
struct ReferenceSpec {
    std::string flatMeshFile;  // Path to reference flat mesh
    
    // Or direct dimensions (used if flatMeshFile is empty)
    double lengthI;
    double lengthJ;
    double lengthK;
    
    ReferenceSpec() : lengthI(0), lengthJ(0), lengthK(0) {}
    
    bool hasFile() const { return !flatMeshFile.empty(); }
    bool hasDimensions() const { return lengthI > 0 && lengthJ > 0 && lengthK > 0; }
};

/**
 * Complete variable density mesh configuration
 */
struct VariableDensityConfig {
    // Reference specification
    ReferenceSpec reference;
    
    // J, K direction elements (uniform)
    int elementsJ;
    int elementsK;
    
    // 5 zones along I direction
    ZoneConfig zone1_denseStart;   // Dense region at start
    ZoneConfig zone2_increasing;   // Transition: dense -> sparse
    ZoneConfig zone3_sparse;       // Sparse region in middle
    ZoneConfig zone4_decreasing;   // Transition: sparse -> dense
    ZoneConfig zone5_denseEnd;     // Dense region at end
    
    // Options
    bool centerAtOrigin;
    
    VariableDensityConfig() 
        : elementsJ(10), elementsK(5), centerAtOrigin(false) {}
    
    // Get total user-defined length (before scaling)
    double getTotalLength() const {
        return zone1_denseStart.length + zone2_increasing.length +
               zone3_sparse.length + zone4_decreasing.length +
               zone5_denseEnd.length;
    }
    
    // Get total I elements
    int getTotalElementsI() const {
        return zone1_denseStart.numElements + zone2_increasing.numElements +
               zone3_sparse.numElements + zone4_decreasing.numElements +
               zone5_denseEnd.numElements;
    }
    
    // Get total elements
    int getTotalElements() const {
        return getTotalElementsI() * elementsJ * elementsK;
    }
    
    // Validate configuration
    bool validate(std::string& error) const {
        if (getTotalLength() <= 0) {
            error = "Total length must be positive";
            return false;
        }
        if (getTotalElementsI() <= 0) {
            error = "Total I elements must be positive";
            return false;
        }
        if (elementsJ <= 0 || elementsK <= 0) {
            error = "Elements J and K must be positive";
            return false;
        }
        return true;
    }
};

} // namespace KooRemapper
