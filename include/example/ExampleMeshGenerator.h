#pragma once

#include "core/Mesh.h"
#include <functional>
#include <string>

namespace KooRemapper {

/**
 * Types of example bent meshes that can be generated
 */
enum class BentMeshType {
    TEARDROP,       // Teardrop shape (물방울)
    ARC,            // Simple arc bend
    S_CURVE,        // S-curve shape
    HELIX,          // Helical twist
    TORUS,          // Torus (donut) section
    TWIST,          // Twisted bar
    BEND_TWIST,     // Combined bend and twist
    WAVE,           // Wavy shape (sine wave in 3D)
    BULGE,          // Localized bulge/expansion
    TAPER,          // Tapered (cone-like)
    WATERDROP,      // Foldable display waterdrop fold (폴더블 물방울 폴딩)
    CUSTOM          // Custom centerline function
};

/**
 * Configuration for example mesh generation
 */
struct ExampleMeshConfig {
    // Grid dimensions (number of elements)
    int dimI = 10;      // Length direction
    int dimJ = 5;       // Width direction
    int dimK = 5;       // Height direction

    // Physical dimensions (undeformed)
    double lengthI = 100.0;     // Length in I direction
    double lengthJ = 20.0;      // Width in J direction
    double lengthK = 20.0;      // Height in K direction

    // Bent mesh type
    BentMeshType bentType = BentMeshType::TEARDROP;

    // Teardrop specific parameters
    double teardropRadius = 30.0;   // Maximum bulge radius
    double teardropLength = 80.0;   // Length of teardrop

    // Arc specific parameters
    double arcAngle = 90.0;         // Bend angle in degrees
    double arcRadius = 50.0;        // Radius of the arc

    // S-curve specific parameters
    double sCurveAmplitude = 30.0;  // Amplitude of S shape
    double sCurveFrequency = 1.0;   // Frequency of S shape

    // Helix specific parameters
    double helixPitch = 20.0;       // Pitch of helix
    double helixRadius = 20.0;      // Radius of helix

    // Torus specific parameters
    double torusRadius = 40.0;      // Major radius of torus
    double torusAngle = 180.0;      // Angle coverage in degrees

    // Twist specific parameters
    double twistAngle = 90.0;       // Total twist angle in degrees

    // Wave specific parameters
    double waveAmplitude = 10.0;    // Wave amplitude
    double waveFrequency = 2.0;     // Number of waves

    // Bulge specific parameters
    double bulgePosition = 0.5;     // Position of bulge center (0-1)
    double bulgeWidth = 0.3;        // Width of bulge region
    double bulgeFactor = 1.5;       // Expansion factor at bulge

    // Taper specific parameters
    double taperRatio = 0.5;        // End scale relative to start

    // Waterdrop fold specific parameters (for foldable display)
    double waterdropFoldRadius = 3.0;    // Fold radius at the hinge (mm)
    double waterdropFoldAngle = 180.0;   // Fold angle (180 = fully closed)
    double waterdropFlatRatio = 0.4;     // Ratio of flat section before fold (0-0.5)

    // Part ID for generated elements
    int partId = 1;

    // Starting node/element IDs
    int startNodeId = 1;
    int startElementId = 1;
};

/**
 * Generates example meshes for testing and demonstration
 */
class ExampleMeshGenerator {
public:
    // Centerline function type: takes parameter t (0-1) and returns position
    using CenterlineFunc = std::function<Vector3D(double t)>;

    // Cross-section scaling function: takes t (0-1) and returns scale factors (width, height)
    using CrossSectionFunc = std::function<std::pair<double, double>(double t)>;

    ExampleMeshGenerator();
    ~ExampleMeshGenerator() = default;

    /**
     * Generate a flat (undeformed) structured mesh
     */
    Mesh generateFlatMesh(const ExampleMeshConfig& config);

    /**
     * Generate a bent structured mesh based on configuration
     */
    Mesh generateBentMesh(const ExampleMeshConfig& config);

    /**
     * Generate a flat unstructured mesh (for mapping test)
     * This creates a finer mesh that will be mapped onto the bent reference
     */
    Mesh generateFlatUnstructuredMesh(const ExampleMeshConfig& config,
                                       int refineFactor = 2);

    /**
     * Generate a flat tetrahedral mesh (for mapping test)
     * Each hexahedron is split into 5 tetrahedra
     */
    Mesh generateFlatTetMesh(const ExampleMeshConfig& config);

    /**
     * Set custom centerline function
     */
    void setCustomCenterline(CenterlineFunc func) {
        customCenterline_ = func;
    }

    /**
     * Set custom cross-section scaling function
     */
    void setCustomCrossSection(CrossSectionFunc func) {
        customCrossSection_ = func;
    }

    /**
     * Get the last error message
     */
    const std::string& getErrorMessage() const { return errorMessage_; }

private:
    CenterlineFunc customCenterline_;
    CrossSectionFunc customCrossSection_;
    std::string errorMessage_;

    // Centerline generators
    Vector3D teardropCenterline(double t, const ExampleMeshConfig& config);
    Vector3D arcCenterline(double t, const ExampleMeshConfig& config);
    Vector3D sCurveCenterline(double t, const ExampleMeshConfig& config);
    Vector3D helixCenterline(double t, const ExampleMeshConfig& config);
    Vector3D torusCenterline(double t, const ExampleMeshConfig& config);
    Vector3D twistCenterline(double t, const ExampleMeshConfig& config);
    Vector3D bendTwistCenterline(double t, const ExampleMeshConfig& config);
    Vector3D waveCenterline(double t, const ExampleMeshConfig& config);
    Vector3D waterdropCenterline(double t, const ExampleMeshConfig& config);

    // Get tangent vector at parameter t
    Vector3D getTangent(double t, const ExampleMeshConfig& config);

    // Get normal and binormal vectors (Frenet-Serret frame)
    void getFrenetFrame(double t, const ExampleMeshConfig& config,
                        Vector3D& tangent, Vector3D& normal, Vector3D& binormal);

    // Cross-section scaling
    std::pair<double, double> teardropCrossSection(double t, const ExampleMeshConfig& config);
    std::pair<double, double> defaultCrossSection(double t, const ExampleMeshConfig& config);
    std::pair<double, double> bulgeCrossSection(double t, const ExampleMeshConfig& config);
    std::pair<double, double> taperCrossSection(double t, const ExampleMeshConfig& config);

    // Get twist angle at parameter t
    double getTwistAngle(double t, const ExampleMeshConfig& config);

    // Create a single node at grid position
    Vector3D computeBentPosition(int i, int j, int k, const ExampleMeshConfig& config);

    // Helpers
    Vector3D getCenterlinePoint(double t, const ExampleMeshConfig& config);
    std::pair<double, double> getCrossSectionScale(double t, const ExampleMeshConfig& config);
};

} // namespace KooRemapper
