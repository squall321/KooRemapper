#include "TestFramework.h"
#include "core/Vector3D.h"
#include <cmath>

using namespace KooRemapper;
using namespace KooRemapper::Test;

// ============================================================
// Vector3D Basic Operations Tests
// ============================================================

TEST(Vector3D_DefaultConstructor) {
    Vector3D v;
    ASSERT_NEAR(v.x, 0.0, 1e-10);
    ASSERT_NEAR(v.y, 0.0, 1e-10);
    ASSERT_NEAR(v.z, 0.0, 1e-10);
}

TEST(Vector3D_ParameterizedConstructor) {
    Vector3D v(1.0, 2.0, 3.0);
    ASSERT_NEAR(v.x, 1.0, 1e-10);
    ASSERT_NEAR(v.y, 2.0, 1e-10);
    ASSERT_NEAR(v.z, 3.0, 1e-10);
}

TEST(Vector3D_Addition) {
    Vector3D a(1.0, 2.0, 3.0);
    Vector3D b(4.0, 5.0, 6.0);
    Vector3D c = a + b;
    ASSERT_NEAR(c.x, 5.0, 1e-10);
    ASSERT_NEAR(c.y, 7.0, 1e-10);
    ASSERT_NEAR(c.z, 9.0, 1e-10);
}

TEST(Vector3D_Subtraction) {
    Vector3D a(4.0, 5.0, 6.0);
    Vector3D b(1.0, 2.0, 3.0);
    Vector3D c = a - b;
    ASSERT_NEAR(c.x, 3.0, 1e-10);
    ASSERT_NEAR(c.y, 3.0, 1e-10);
    ASSERT_NEAR(c.z, 3.0, 1e-10);
}

TEST(Vector3D_ScalarMultiplication) {
    Vector3D v(1.0, 2.0, 3.0);
    Vector3D c = v * 2.0;
    ASSERT_NEAR(c.x, 2.0, 1e-10);
    ASSERT_NEAR(c.y, 4.0, 1e-10);
    ASSERT_NEAR(c.z, 6.0, 1e-10);
}

TEST(Vector3D_ScalarDivision) {
    Vector3D v(2.0, 4.0, 6.0);
    Vector3D c = v / 2.0;
    ASSERT_NEAR(c.x, 1.0, 1e-10);
    ASSERT_NEAR(c.y, 2.0, 1e-10);
    ASSERT_NEAR(c.z, 3.0, 1e-10);
}

TEST(Vector3D_DotProduct) {
    Vector3D a(1.0, 2.0, 3.0);
    Vector3D b(4.0, 5.0, 6.0);
    double dot = a.dot(b);
    ASSERT_NEAR(dot, 32.0, 1e-10);  // 1*4 + 2*5 + 3*6 = 32
}

TEST(Vector3D_CrossProduct) {
    Vector3D a(1.0, 0.0, 0.0);
    Vector3D b(0.0, 1.0, 0.0);
    Vector3D c = a.cross(b);
    ASSERT_NEAR(c.x, 0.0, 1e-10);
    ASSERT_NEAR(c.y, 0.0, 1e-10);
    ASSERT_NEAR(c.z, 1.0, 1e-10);
}

TEST(Vector3D_Magnitude) {
    Vector3D v(3.0, 4.0, 0.0);
    ASSERT_NEAR(v.magnitude(), 5.0, 1e-10);
}

TEST(Vector3D_MagnitudeSquared) {
    Vector3D v(3.0, 4.0, 0.0);
    ASSERT_NEAR(v.magnitudeSquared(), 25.0, 1e-10);
}

TEST(Vector3D_Normalize) {
    Vector3D v(3.0, 4.0, 0.0);
    Vector3D n = v.normalized();
    ASSERT_NEAR(n.magnitude(), 1.0, 1e-10);
    ASSERT_NEAR(n.x, 0.6, 1e-10);
    ASSERT_NEAR(n.y, 0.8, 1e-10);
}

TEST(Vector3D_Distance) {
    Vector3D a(0.0, 0.0, 0.0);
    Vector3D b(3.0, 4.0, 0.0);
    ASSERT_NEAR(a.distanceTo(b), 5.0, 1e-10);
}

TEST(Vector3D_Negation) {
    Vector3D v(1.0, -2.0, 3.0);
    Vector3D n = -v;
    ASSERT_NEAR(n.x, -1.0, 1e-10);
    ASSERT_NEAR(n.y, 2.0, 1e-10);
    ASSERT_NEAR(n.z, -3.0, 1e-10);
}

TEST(Vector3D_CompoundAddition) {
    Vector3D a(1.0, 2.0, 3.0);
    a += Vector3D(1.0, 1.0, 1.0);
    ASSERT_NEAR(a.x, 2.0, 1e-10);
    ASSERT_NEAR(a.y, 3.0, 1e-10);
    ASSERT_NEAR(a.z, 4.0, 1e-10);
}

TEST(Vector3D_CompoundSubtraction) {
    Vector3D a(2.0, 3.0, 4.0);
    a -= Vector3D(1.0, 1.0, 1.0);
    ASSERT_NEAR(a.x, 1.0, 1e-10);
    ASSERT_NEAR(a.y, 2.0, 1e-10);
    ASSERT_NEAR(a.z, 3.0, 1e-10);
}

TEST(Vector3D_CompoundMultiplication) {
    Vector3D a(1.0, 2.0, 3.0);
    a *= 2.0;
    ASSERT_NEAR(a.x, 2.0, 1e-10);
    ASSERT_NEAR(a.y, 4.0, 1e-10);
    ASSERT_NEAR(a.z, 6.0, 1e-10);
}

// ============================================================
// Vector3D Edge Cases
// ============================================================

TEST(Vector3D_ZeroVector) {
    Vector3D v(0.0, 0.0, 0.0);
    ASSERT_NEAR(v.magnitude(), 0.0, 1e-10);
}

TEST(Vector3D_UnitVectors) {
    Vector3D x(1.0, 0.0, 0.0);
    Vector3D y(0.0, 1.0, 0.0);
    Vector3D z(0.0, 0.0, 1.0);

    ASSERT_NEAR(x.magnitude(), 1.0, 1e-10);
    ASSERT_NEAR(y.magnitude(), 1.0, 1e-10);
    ASSERT_NEAR(z.magnitude(), 1.0, 1e-10);

    // Orthogonality
    ASSERT_NEAR(x.dot(y), 0.0, 1e-10);
    ASSERT_NEAR(y.dot(z), 0.0, 1e-10);
    ASSERT_NEAR(z.dot(x), 0.0, 1e-10);
}

TEST(Vector3D_CrossProductProperties) {
    Vector3D a(1.0, 2.0, 3.0);
    Vector3D b(4.0, 5.0, 6.0);

    // Cross product is anti-commutative
    Vector3D axb = a.cross(b);
    Vector3D bxa = b.cross(a);

    ASSERT_NEAR(axb.x, -bxa.x, 1e-10);
    ASSERT_NEAR(axb.y, -bxa.y, 1e-10);
    ASSERT_NEAR(axb.z, -bxa.z, 1e-10);

    // Cross product is perpendicular to both vectors
    ASSERT_NEAR(axb.dot(a), 0.0, 1e-10);
    ASSERT_NEAR(axb.dot(b), 0.0, 1e-10);
}
