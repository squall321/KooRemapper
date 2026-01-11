#include "TestFramework.h"
#include "core/Vector3D.h"
#include "mapper/EdgeInterpolator.h"
#include "mapper/FaceInterpolator.h"
#include <vector>
#include <cmath>

using namespace KooRemapper;
using namespace KooRemapper::Test;

// ============================================================
// Edge Interpolation Tests
// ============================================================

TEST(EdgeInterpolator_LinearEdge) {
    EdgeInterpolator interp;
    std::vector<Vector3D> points = {
        Vector3D(0.0, 0.0, 0.0),
        Vector3D(1.0, 0.0, 0.0)
    };
    interp.build(points);

    // Test endpoints
    Vector3D p0 = interp.interpolate(0.0);
    ASSERT_NEAR(p0.x, 0.0, 1e-6);

    Vector3D p1 = interp.interpolate(1.0);
    ASSERT_NEAR(p1.x, 1.0, 1e-6);

    // Test midpoint
    Vector3D mid = interp.interpolate(0.5);
    ASSERT_NEAR(mid.x, 0.5, 1e-6);
    ASSERT_NEAR(mid.y, 0.0, 1e-6);
}

TEST(EdgeInterpolator_CurvedEdge) {
    EdgeInterpolator interp;
    // Quarter circle in XY plane
    std::vector<Vector3D> points;
    int n = 10;
    for (int i = 0; i <= n; ++i) {
        double t = static_cast<double>(i) / n;
        double angle = t * M_PI / 2.0;
        points.push_back(Vector3D(std::cos(angle), std::sin(angle), 0.0));
    }
    interp.build(points);

    // Endpoints should be on the circle
    Vector3D start = interp.interpolate(0.0);
    ASSERT_NEAR(start.x, 1.0, 1e-4);
    ASSERT_NEAR(start.y, 0.0, 1e-4);

    Vector3D end = interp.interpolate(1.0);
    ASSERT_NEAR(end.x, 0.0, 1e-4);
    ASSERT_NEAR(end.y, 1.0, 1e-4);

    // Midpoint should also be on the circle (approximately)
    Vector3D mid = interp.interpolate(0.5);
    double radius = std::sqrt(mid.x * mid.x + mid.y * mid.y);
    ASSERT_NEAR(radius, 1.0, 0.05);  // Allow some deviation for discrete interpolation
}

TEST(EdgeInterpolator_MultiPointEdge) {
    EdgeInterpolator interp;
    std::vector<Vector3D> points = {
        Vector3D(0.0, 0.0, 0.0),
        Vector3D(0.25, 0.1, 0.0),
        Vector3D(0.5, 0.0, 0.0),
        Vector3D(0.75, -0.1, 0.0),
        Vector3D(1.0, 0.0, 0.0)
    };
    interp.build(points);

    // Should pass through all points approximately
    Vector3D p0 = interp.interpolate(0.0);
    ASSERT_NEAR(p0.x, 0.0, 1e-6);

    Vector3D p1 = interp.interpolate(1.0);
    ASSERT_NEAR(p1.x, 1.0, 1e-6);
}

TEST(EdgeInterpolator_ArcLength) {
    EdgeInterpolator interp;
    // Non-uniform spacing - arc length should normalize
    std::vector<Vector3D> points = {
        Vector3D(0.0, 0.0, 0.0),
        Vector3D(0.1, 0.0, 0.0),  // Short segment
        Vector3D(1.0, 0.0, 0.0)   // Long segment
    };
    interp.build(points);

    // Arc length parameterization should give uniform speed
    Vector3D p = interp.interpolate(0.5);
    // At t=0.5 arc length, should be at middle of total length
    ASSERT_NEAR(p.x, 0.5, 0.1);
}

// ============================================================
// Face Interpolation Tests
// ============================================================

TEST(FaceInterpolator_BilinearSquare) {
    FaceInterpolator interp;
    interp.buildBilinear(
        Vector3D(0.0, 0.0, 0.0),  // (0,0)
        Vector3D(1.0, 0.0, 0.0),  // (1,0)
        Vector3D(0.0, 1.0, 0.0),  // (0,1)
        Vector3D(1.0, 1.0, 0.0)   // (1,1)
    );

    // Test corners
    Vector3D c00 = interp.interpolate(0.0, 0.0);
    ASSERT_NEAR(c00.x, 0.0, 1e-6);
    ASSERT_NEAR(c00.y, 0.0, 1e-6);

    Vector3D c10 = interp.interpolate(1.0, 0.0);
    ASSERT_NEAR(c10.x, 1.0, 1e-6);
    ASSERT_NEAR(c10.y, 0.0, 1e-6);

    Vector3D c01 = interp.interpolate(0.0, 1.0);
    ASSERT_NEAR(c01.x, 0.0, 1e-6);
    ASSERT_NEAR(c01.y, 1.0, 1e-6);

    Vector3D c11 = interp.interpolate(1.0, 1.0);
    ASSERT_NEAR(c11.x, 1.0, 1e-6);
    ASSERT_NEAR(c11.y, 1.0, 1e-6);

    // Test center
    Vector3D center = interp.interpolate(0.5, 0.5);
    ASSERT_NEAR(center.x, 0.5, 1e-6);
    ASSERT_NEAR(center.y, 0.5, 1e-6);
}

TEST(FaceInterpolator_BilinearTrapezoid) {
    FaceInterpolator interp;
    // Trapezoid shape
    interp.buildBilinear(
        Vector3D(0.0, 0.0, 0.0),
        Vector3D(2.0, 0.0, 0.0),
        Vector3D(0.5, 1.0, 0.0),
        Vector3D(1.5, 1.0, 0.0)
    );

    // Center should be at average
    Vector3D center = interp.interpolate(0.5, 0.5);
    ASSERT_NEAR(center.x, 1.0, 1e-6);
    ASSERT_NEAR(center.y, 0.5, 1e-6);
}

TEST(FaceInterpolator_3DFace) {
    FaceInterpolator interp;
    // Face in 3D space
    interp.buildBilinear(
        Vector3D(0.0, 0.0, 0.0),
        Vector3D(1.0, 0.0, 0.0),
        Vector3D(0.0, 1.0, 1.0),
        Vector3D(1.0, 1.0, 1.0)
    );

    Vector3D center = interp.interpolate(0.5, 0.5);
    ASSERT_NEAR(center.x, 0.5, 1e-6);
    ASSERT_NEAR(center.y, 0.5, 1e-6);
    ASSERT_NEAR(center.z, 0.5, 1e-6);
}

// ============================================================
// Interpolation Speed/Precision Tests
// ============================================================

TEST(EdgeInterpolator_HighPrecision) {
    EdgeInterpolator interp;
    // Build a sine wave edge
    std::vector<Vector3D> points;
    int n = 100;
    for (int i = 0; i <= n; ++i) {
        double t = static_cast<double>(i) / n;
        points.push_back(Vector3D(t, std::sin(t * M_PI), 0.0));
    }
    interp.build(points);

    // Test at many intermediate points
    bool allValid = true;
    for (int i = 0; i <= 1000; ++i) {
        double t = static_cast<double>(i) / 1000;
        Vector3D p = interp.interpolate(t);
        if (p.x < -0.01 || p.x > 1.01) allValid = false;
        if (p.y < -0.01 || p.y > 1.01) allValid = false;
    }
    ASSERT_TRUE(allValid);
}

TEST(FaceInterpolator_Monotonicity) {
    FaceInterpolator interp;
    interp.buildBilinear(
        Vector3D(0.0, 0.0, 0.0),
        Vector3D(1.0, 0.0, 0.0),
        Vector3D(0.0, 1.0, 0.0),
        Vector3D(1.0, 1.0, 0.0)
    );

    // Moving in u direction should monotonically increase x
    double prevX = -1.0;
    for (int i = 0; i <= 100; ++i) {
        double u = static_cast<double>(i) / 100;
        Vector3D p = interp.interpolate(u, 0.5);
        ASSERT_GT(p.x, prevX - 1e-10);
        prevX = p.x;
    }
}

TEST(EdgeInterpolator_BoundaryConditions) {
    EdgeInterpolator interp;
    std::vector<Vector3D> points = {
        Vector3D(0.0, 0.0, 0.0),
        Vector3D(0.5, 0.5, 0.5),
        Vector3D(1.0, 1.0, 1.0)
    };
    interp.build(points);

    // Test clamping behavior at boundaries
    Vector3D pNeg = interp.interpolate(-0.1);  // Should clamp to 0
    ASSERT_NEAR(pNeg.x, 0.0, 0.2);

    Vector3D pOver = interp.interpolate(1.1);  // Should clamp to 1
    ASSERT_NEAR(pOver.x, 1.0, 0.2);
}

TEST(FaceInterpolator_BoundaryConditions) {
    FaceInterpolator interp;
    interp.buildBilinear(
        Vector3D(0.0, 0.0, 0.0),
        Vector3D(1.0, 0.0, 0.0),
        Vector3D(0.0, 1.0, 0.0),
        Vector3D(1.0, 1.0, 0.0)
    );

    // Parameters outside [0,1] should still produce reasonable results
    Vector3D p = interp.interpolate(0.5, 0.5);
    ASSERT_NEAR(p.x, 0.5, 1e-6);
    ASSERT_NEAR(p.y, 0.5, 1e-6);
}
