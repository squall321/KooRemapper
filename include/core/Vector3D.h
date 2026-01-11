#pragma once

#include <cmath>
#include <string>
#include <ostream>

namespace KooRemapper {

/**
 * 3D Vector class for geometric operations
 */
class Vector3D {
public:
    double x, y, z;

    // Constructors
    Vector3D() : x(0.0), y(0.0), z(0.0) {}
    Vector3D(double x, double y, double z) : x(x), y(y), z(z) {}
    Vector3D(const Vector3D& other) = default;

    // Assignment
    Vector3D& operator=(const Vector3D& other) = default;

    // Arithmetic operators
    Vector3D operator+(const Vector3D& other) const {
        return Vector3D(x + other.x, y + other.y, z + other.z);
    }

    Vector3D operator-(const Vector3D& other) const {
        return Vector3D(x - other.x, y - other.y, z - other.z);
    }

    Vector3D operator*(double scalar) const {
        return Vector3D(x * scalar, y * scalar, z * scalar);
    }

    Vector3D operator/(double scalar) const {
        return Vector3D(x / scalar, y / scalar, z / scalar);
    }

    // Compound assignment operators
    Vector3D& operator+=(const Vector3D& other) {
        x += other.x;
        y += other.y;
        z += other.z;
        return *this;
    }

    Vector3D& operator-=(const Vector3D& other) {
        x -= other.x;
        y -= other.y;
        z -= other.z;
        return *this;
    }

    Vector3D& operator*=(double scalar) {
        x *= scalar;
        y *= scalar;
        z *= scalar;
        return *this;
    }

    Vector3D& operator/=(double scalar) {
        x /= scalar;
        y /= scalar;
        z /= scalar;
        return *this;
    }

    // Unary minus
    Vector3D operator-() const {
        return Vector3D(-x, -y, -z);
    }

    // Comparison operators
    bool operator==(const Vector3D& other) const {
        return x == other.x && y == other.y && z == other.z;
    }

    bool operator!=(const Vector3D& other) const {
        return !(*this == other);
    }

    // Dot product
    double dot(const Vector3D& other) const {
        return x * other.x + y * other.y + z * other.z;
    }

    // Cross product
    Vector3D cross(const Vector3D& other) const {
        return Vector3D(
            y * other.z - z * other.y,
            z * other.x - x * other.z,
            x * other.y - y * other.x
        );
    }

    // Magnitude (length)
    double magnitude() const {
        return std::sqrt(x * x + y * y + z * z);
    }

    // Squared magnitude (faster when you don't need the actual length)
    double magnitudeSquared() const {
        return x * x + y * y + z * z;
    }

    // Normalize (return unit vector)
    Vector3D normalized() const {
        double mag = magnitude();
        if (mag > 0.0) {
            return *this / mag;
        }
        return Vector3D(0.0, 0.0, 0.0);
    }

    // Normalize in place
    void normalize() {
        double mag = magnitude();
        if (mag > 0.0) {
            x /= mag;
            y /= mag;
            z /= mag;
        }
    }

    // Distance to another point
    double distanceTo(const Vector3D& other) const {
        return (*this - other).magnitude();
    }

    // Linear interpolation
    static Vector3D lerp(const Vector3D& a, const Vector3D& b, double t) {
        return a * (1.0 - t) + b * t;
    }

    // Check if approximately equal (with tolerance)
    bool isApprox(const Vector3D& other, double tolerance = 1e-10) const {
        return std::abs(x - other.x) < tolerance &&
               std::abs(y - other.y) < tolerance &&
               std::abs(z - other.z) < tolerance;
    }

    // Access by index
    double& operator[](int index) {
        switch (index) {
            case 0: return x;
            case 1: return y;
            case 2: return z;
            default: return x;  // fallback
        }
    }

    const double& operator[](int index) const {
        switch (index) {
            case 0: return x;
            case 1: return y;
            case 2: return z;
            default: return x;  // fallback
        }
    }

    // String representation
    std::string toString() const;

    // Output stream operator
    friend std::ostream& operator<<(std::ostream& os, const Vector3D& v);
};

// Scalar multiplication from the left
inline Vector3D operator*(double scalar, const Vector3D& v) {
    return v * scalar;
}

} // namespace KooRemapper
