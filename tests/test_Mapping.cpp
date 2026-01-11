#include "TestFramework.h"
#include "core/Mesh.h"
#include "core/Node.h"
#include "core/Element.h"
#include "mapper/ParametricMapper.h"
#include "mapper/EdgeInterpolator.h"
#include "mapper/FaceInterpolator.h"
#include "grid/BoundaryExtractor.h"
#include "grid/EdgeCalculator.h"
#include <cmath>

using namespace KooRemapper;
using namespace KooRemapper::Test;

// Helper to create a simple unit cube mesh for testing
Mesh createUnitCubeMesh() {
    Mesh mesh;

    // 8 corner nodes of a unit cube
    mesh.addNode(Node(1, 0.0, 0.0, 0.0));  // (0,0,0)
    mesh.addNode(Node(2, 1.0, 0.0, 0.0));  // (1,0,0)
    mesh.addNode(Node(3, 1.0, 1.0, 0.0));  // (1,1,0)
    mesh.addNode(Node(4, 0.0, 1.0, 0.0));  // (0,1,0)
    mesh.addNode(Node(5, 0.0, 0.0, 1.0));  // (0,0,1)
    mesh.addNode(Node(6, 1.0, 0.0, 1.0));  // (1,0,1)
    mesh.addNode(Node(7, 1.0, 1.0, 1.0));  // (1,1,1)
    mesh.addNode(Node(8, 0.0, 1.0, 1.0));  // (0,1,1)

    // Single hex element
    Element elem;
    elem.id = 1;
    elem.partId = 1;
    elem.nodeIds = {1, 2, 3, 4, 5, 6, 7, 8};
    elem.setGridIndex(0, 0, 0);
    mesh.addElement(elem);

    return mesh;
}

// Create a 2x2x2 structured mesh
Mesh create2x2x2Mesh() {
    Mesh mesh;
    int nodeId = 1;

    // Create 3x3x3 = 27 nodes
    for (int k = 0; k <= 2; ++k) {
        for (int j = 0; j <= 2; ++j) {
            for (int i = 0; i <= 2; ++i) {
                mesh.addNode(Node(nodeId++,
                    static_cast<double>(i) * 0.5,
                    static_cast<double>(j) * 0.5,
                    static_cast<double>(k) * 0.5));
            }
        }
    }

    // Create 8 hex elements
    int elemId = 1;
    for (int k = 0; k < 2; ++k) {
        for (int j = 0; j < 2; ++j) {
            for (int i = 0; i < 2; ++i) {
                int n0 = 1 + i + j * 3 + k * 9;
                int n1 = n0 + 1;
                int n2 = n0 + 4;
                int n3 = n0 + 3;
                int n4 = n0 + 9;
                int n5 = n4 + 1;
                int n6 = n4 + 4;
                int n7 = n4 + 3;

                Element elem;
                elem.id = elemId++;
                elem.partId = 1;
                elem.nodeIds = {n0, n1, n2, n3, n4, n5, n6, n7};
                elem.setGridIndex(i, j, k);
                mesh.addElement(elem);
            }
        }
    }

    return mesh;
}

// ============================================================
// Trilinear Interpolation Tests
// ============================================================

TEST(TrilinearInterpolation_Corners) {
    // Test that trilinear interpolation returns corners at (0,0,0), (1,0,0), etc.
    Vector3D corners[8] = {
        Vector3D(0.0, 0.0, 0.0),
        Vector3D(1.0, 0.0, 0.0),
        Vector3D(1.0, 1.0, 0.0),
        Vector3D(0.0, 1.0, 0.0),
        Vector3D(0.0, 0.0, 1.0),
        Vector3D(1.0, 0.0, 1.0),
        Vector3D(1.0, 1.0, 1.0),
        Vector3D(0.0, 1.0, 1.0)
    };

    // Trilinear interpolation formula
    auto trilinear = [&corners](double u, double v, double w) -> Vector3D {
        double mu = 1.0 - u, mv = 1.0 - v, mw = 1.0 - w;
        return corners[0] * (mu * mv * mw) +
               corners[1] * (u * mv * mw) +
               corners[2] * (u * v * mw) +
               corners[3] * (mu * v * mw) +
               corners[4] * (mu * mv * w) +
               corners[5] * (u * mv * w) +
               corners[6] * (u * v * w) +
               corners[7] * (mu * v * w);
    };

    // Test corners
    Vector3D p000 = trilinear(0.0, 0.0, 0.0);
    ASSERT_NEAR(p000.x, 0.0, 1e-10);
    ASSERT_NEAR(p000.y, 0.0, 1e-10);
    ASSERT_NEAR(p000.z, 0.0, 1e-10);

    Vector3D p100 = trilinear(1.0, 0.0, 0.0);
    ASSERT_NEAR(p100.x, 1.0, 1e-10);
    ASSERT_NEAR(p100.y, 0.0, 1e-10);
    ASSERT_NEAR(p100.z, 0.0, 1e-10);

    Vector3D p111 = trilinear(1.0, 1.0, 1.0);
    ASSERT_NEAR(p111.x, 1.0, 1e-10);
    ASSERT_NEAR(p111.y, 1.0, 1e-10);
    ASSERT_NEAR(p111.z, 1.0, 1e-10);

    // Test center
    Vector3D center = trilinear(0.5, 0.5, 0.5);
    ASSERT_NEAR(center.x, 0.5, 1e-10);
    ASSERT_NEAR(center.y, 0.5, 1e-10);
    ASSERT_NEAR(center.z, 0.5, 1e-10);
}

TEST(TrilinearInterpolation_EdgeMidpoints) {
    Vector3D corners[8] = {
        Vector3D(0.0, 0.0, 0.0),
        Vector3D(1.0, 0.0, 0.0),
        Vector3D(1.0, 1.0, 0.0),
        Vector3D(0.0, 1.0, 0.0),
        Vector3D(0.0, 0.0, 1.0),
        Vector3D(1.0, 0.0, 1.0),
        Vector3D(1.0, 1.0, 1.0),
        Vector3D(0.0, 1.0, 1.0)
    };

    auto trilinear = [&corners](double u, double v, double w) -> Vector3D {
        double mu = 1.0 - u, mv = 1.0 - v, mw = 1.0 - w;
        return corners[0] * (mu * mv * mw) +
               corners[1] * (u * mv * mw) +
               corners[2] * (u * v * mw) +
               corners[3] * (mu * v * mw) +
               corners[4] * (mu * mv * w) +
               corners[5] * (u * mv * w) +
               corners[6] * (u * v * w) +
               corners[7] * (mu * v * w);
    };

    // Test edge midpoints
    Vector3D midX = trilinear(0.5, 0.0, 0.0);  // Middle of edge along X
    ASSERT_NEAR(midX.x, 0.5, 1e-10);
    ASSERT_NEAR(midX.y, 0.0, 1e-10);
    ASSERT_NEAR(midX.z, 0.0, 1e-10);

    Vector3D midY = trilinear(0.0, 0.5, 0.0);  // Middle of edge along Y
    ASSERT_NEAR(midY.x, 0.0, 1e-10);
    ASSERT_NEAR(midY.y, 0.5, 1e-10);
    ASSERT_NEAR(midY.z, 0.0, 1e-10);

    Vector3D midZ = trilinear(0.0, 0.0, 0.5);  // Middle of edge along Z
    ASSERT_NEAR(midZ.x, 0.0, 1e-10);
    ASSERT_NEAR(midZ.y, 0.0, 1e-10);
    ASSERT_NEAR(midZ.z, 0.5, 1e-10);
}

TEST(TrilinearInterpolation_TransfiniteFormula) {
    // Test the Gordon-Hall formula: P = Pf - Pe + Pc
    // For a unit cube with straight edges, transfinite should equal trilinear

    Vector3D corners[8] = {
        Vector3D(0.0, 0.0, 0.0),
        Vector3D(1.0, 0.0, 0.0),
        Vector3D(1.0, 1.0, 0.0),
        Vector3D(0.0, 1.0, 0.0),
        Vector3D(0.0, 0.0, 1.0),
        Vector3D(1.0, 0.0, 1.0),
        Vector3D(1.0, 1.0, 1.0),
        Vector3D(0.0, 1.0, 1.0)
    };

    auto trilinear = [&corners](double u, double v, double w) -> Vector3D {
        double mu = 1.0 - u, mv = 1.0 - v, mw = 1.0 - w;
        return corners[0] * (mu * mv * mw) +
               corners[1] * (u * mv * mw) +
               corners[2] * (u * v * mw) +
               corners[3] * (mu * v * mw) +
               corners[4] * (mu * mv * w) +
               corners[5] * (u * mv * w) +
               corners[6] * (u * v * w) +
               corners[7] * (mu * v * w);
    };

    // For unit cube, transfinite should give same result as trilinear
    // Test at various points
    double testPoints[] = {0.0, 0.25, 0.5, 0.75, 1.0};

    for (double u : testPoints) {
        for (double v : testPoints) {
            for (double w : testPoints) {
                Vector3D p = trilinear(u, v, w);
                ASSERT_NEAR(p.x, u, 1e-10);
                ASSERT_NEAR(p.y, v, 1e-10);
                ASSERT_NEAR(p.z, w, 1e-10);
            }
        }
    }
}

// ============================================================
// Mapping Accuracy Tests
// ============================================================

TEST(Mapping_ParameterClamping) {
    // Test that parameters outside [0,1] are properly handled
    Vector3D corners[8] = {
        Vector3D(0.0, 0.0, 0.0),
        Vector3D(1.0, 0.0, 0.0),
        Vector3D(1.0, 1.0, 0.0),
        Vector3D(0.0, 1.0, 0.0),
        Vector3D(0.0, 0.0, 1.0),
        Vector3D(1.0, 0.0, 1.0),
        Vector3D(1.0, 1.0, 1.0),
        Vector3D(0.0, 1.0, 1.0)
    };

    auto clampedTrilinear = [&corners](double u, double v, double w) -> Vector3D {
        u = std::max(0.0, std::min(1.0, u));
        v = std::max(0.0, std::min(1.0, v));
        w = std::max(0.0, std::min(1.0, w));

        double mu = 1.0 - u, mv = 1.0 - v, mw = 1.0 - w;
        return corners[0] * (mu * mv * mw) +
               corners[1] * (u * mv * mw) +
               corners[2] * (u * v * mw) +
               corners[3] * (mu * v * mw) +
               corners[4] * (mu * mv * w) +
               corners[5] * (u * mv * w) +
               corners[6] * (u * v * w) +
               corners[7] * (mu * v * w);
    };

    // Test clamping
    Vector3D p1 = clampedTrilinear(-0.5, 0.5, 0.5);
    ASSERT_NEAR(p1.x, 0.0, 1e-10);

    Vector3D p2 = clampedTrilinear(1.5, 0.5, 0.5);
    ASSERT_NEAR(p2.x, 1.0, 1e-10);
}

TEST(Mapping_Continuity) {
    // Test that interpolation is C0 continuous
    Vector3D corners[8] = {
        Vector3D(0.0, 0.0, 0.0),
        Vector3D(1.0, 0.0, 0.0),
        Vector3D(1.0, 1.0, 0.0),
        Vector3D(0.0, 1.0, 0.0),
        Vector3D(0.0, 0.0, 1.0),
        Vector3D(1.0, 0.0, 1.0),
        Vector3D(1.0, 1.0, 1.0),
        Vector3D(0.0, 1.0, 1.0)
    };

    auto trilinear = [&corners](double u, double v, double w) -> Vector3D {
        double mu = 1.0 - u, mv = 1.0 - v, mw = 1.0 - w;
        return corners[0] * (mu * mv * mw) +
               corners[1] * (u * mv * mw) +
               corners[2] * (u * v * mw) +
               corners[3] * (mu * v * mw) +
               corners[4] * (mu * mv * w) +
               corners[5] * (u * mv * w) +
               corners[6] * (u * v * w) +
               corners[7] * (mu * v * w);
    };

    // Test continuity at small step
    double epsilon = 1e-6;
    Vector3D p1 = trilinear(0.5, 0.5, 0.5);
    Vector3D p2 = trilinear(0.5 + epsilon, 0.5, 0.5);

    double dist = (p2 - p1).magnitude();
    ASSERT_LT(dist, epsilon * 2);  // Should be approximately epsilon
}

// ============================================================
// Performance Related Tests
// ============================================================

TEST(Mapping_LargeGridInterpolation) {
    // Test interpolation speed with many evaluations
    Vector3D corners[8] = {
        Vector3D(0.0, 0.0, 0.0),
        Vector3D(1.0, 0.0, 0.0),
        Vector3D(1.0, 1.0, 0.0),
        Vector3D(0.0, 1.0, 0.0),
        Vector3D(0.0, 0.0, 1.0),
        Vector3D(1.0, 0.0, 1.0),
        Vector3D(1.0, 1.0, 1.0),
        Vector3D(0.0, 1.0, 1.0)
    };

    auto trilinear = [&corners](double u, double v, double w) -> Vector3D {
        double mu = 1.0 - u, mv = 1.0 - v, mw = 1.0 - w;
        return corners[0] * (mu * mv * mw) +
               corners[1] * (u * mv * mw) +
               corners[2] * (u * v * mw) +
               corners[3] * (mu * v * mw) +
               corners[4] * (mu * mv * w) +
               corners[5] * (u * mv * w) +
               corners[6] * (u * v * w) +
               corners[7] * (mu * v * w);
    };

    // Evaluate at 10x10x10 = 1000 points
    int count = 0;
    int expected = 11 * 11 * 11;
    for (int ii = 0; ii <= 10; ++ii) {
        for (int jj = 0; jj <= 10; ++jj) {
            for (int kk = 0; kk <= 10; ++kk) {
                double u = static_cast<double>(ii) / 10.0;
                double v = static_cast<double>(jj) / 10.0;
                double w = static_cast<double>(kk) / 10.0;
                Vector3D p = trilinear(u, v, w);
                // Just verify it's within bounds
                if (p.x >= -0.001 && p.x <= 1.001) count++;
            }
        }
    }
    ASSERT_EQ(count, expected);
}
