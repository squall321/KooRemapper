#pragma once

#include "generator/CurveInterpolator.h"
#include "core/Mesh.h"
#include <vector>
#include <string>
#include <functional>

namespace KooRemapper {

/**
 * Configuration for curved mesh generation
 */
struct CurvedMeshConfig {
    // Centerline points (x, y coordinates)
    std::vector<Vector2D> centerlinePoints;
    
    // Interpolation type
    InterpolationType interpolation;
    
    // Cross-section dimensions
    double width;       // Y direction (perpendicular to curve plane)
    double thickness;   // Z direction (in curve plane, normal to tangent)
    
    // Element counts
    int elementsAlongCurve;
    int elementsWidth;      // J direction
    int elementsThickness;  // K direction
    
    // Options
    bool centerAtOrigin;
    
    CurvedMeshConfig()
        : interpolation(InterpolationType::CATMULL_ROM)
        , width(1.0)
        , thickness(1.0)
        , elementsAlongCurve(10)
        , elementsWidth(5)
        , elementsThickness(5)
        , centerAtOrigin(false)
    {}
    
    bool validate(std::string& error) const {
        if (centerlinePoints.size() < 2) {
            error = "At least 2 centerline points required";
            return false;
        }
        if (width <= 0 || thickness <= 0) {
            error = "Width and thickness must be positive";
            return false;
        }
        if (elementsAlongCurve <= 0 || elementsWidth <= 0 || elementsThickness <= 0) {
            error = "Element counts must be positive";
            return false;
        }
        return true;
    }
    
    int getTotalElements() const {
        return elementsAlongCurve * elementsWidth * elementsThickness;
    }
};

/**
 * Statistics from curved mesh generation
 */
struct CurvedMeshStats {
    double arcLength;           // Total arc length of curve
    double scaleFactor;         // Scale factor applied (1.0 if no reference)
    double width;               // Actual width used
    double thickness;           // Actual thickness used
    
    int totalElements;
    int totalNodes;
    
    double maxCurvature;        // Maximum curvature along curve
    double minRadius;           // Minimum radius of curvature
    double curvatureAtMax;      // Parameter t where max curvature occurs
};

/**
 * Generator for curved meshes following a user-defined centerline
 * 
 * Creates a bent HEX8 mesh by:
 * 1. Interpolating the centerline with B-spline/Catmull-Rom
 * 2. Computing tangent and normal at each position
 * 3. Placing cross-section nodes perpendicular to the curve
 * 4. Connecting nodes to form HEX8 elements
 */
class CurvedMeshGenerator {
public:
    using ProgressCallback = std::function<void(int percent)>;
    
    CurvedMeshGenerator();
    ~CurvedMeshGenerator() = default;
    
    /**
     * Generate curved mesh from configuration
     * @param config Mesh configuration
     * @return Generated mesh
     */
    Mesh generate(const CurvedMeshConfig& config);
    
    /**
     * Generate curved mesh with reference scaling
     * @param config Mesh configuration
     * @param refArcLength Reference arc length (I direction)
     * @param refWidth Reference width (J direction)
     * @param refThickness Reference thickness (K direction)
     * @return Generated mesh
     */
    Mesh generate(const CurvedMeshConfig& config,
                  double refArcLength, double refWidth, double refThickness);
    
    /**
     * Set progress callback
     */
    void setProgressCallback(ProgressCallback callback) {
        progressCallback_ = callback;
    }
    
    /**
     * Get generation statistics
     */
    const CurvedMeshStats& getStats() const { return stats_; }
    
    /**
     * Get error message
     */
    const std::string& getErrorMessage() const { return errorMessage_; }

private:
    ProgressCallback progressCallback_;
    CurvedMeshStats stats_;
    std::string errorMessage_;
    CurveInterpolator curve_;
    
    /**
     * Compute curvature at parameter t
     */
    double computeCurvature(double t) const;
    
    /**
     * Analyze curve properties (curvature, etc.)
     */
    void analyzeCurve();
    
    void reportProgress(int percent);
};

} // namespace KooRemapper
