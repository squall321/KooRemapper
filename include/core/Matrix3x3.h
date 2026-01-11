#pragma once

#include "core/Vector3D.h"
#include <array>
#include <cmath>
#include <stdexcept>

namespace KooRemapper {

/**
 * 3x3 Matrix class for tensor operations
 * 
 * Storage: Row-major order
 *   [m00 m01 m02]
 *   [m10 m11 m12]
 *   [m20 m21 m22]
 */
class Matrix3x3 {
public:
    // Matrix data (row-major)
    std::array<std::array<double, 3>, 3> m;

    // Constructors
    Matrix3x3() : m{{{{0, 0, 0}}, {{0, 0, 0}}, {{0, 0, 0}}}} {}
    
    Matrix3x3(double m00, double m01, double m02,
              double m10, double m11, double m12,
              double m20, double m21, double m22)
        : m{{{{m00, m01, m02}}, {{m10, m11, m12}}, {{m20, m21, m22}}}} {}

    // Identity matrix
    static Matrix3x3 identity() {
        return Matrix3x3(1, 0, 0,
                         0, 1, 0,
                         0, 0, 1);
    }

    // Zero matrix
    static Matrix3x3 zero() {
        return Matrix3x3();
    }

    // Create from column vectors
    static Matrix3x3 fromColumns(const Vector3D& c0, const Vector3D& c1, const Vector3D& c2) {
        return Matrix3x3(c0.x, c1.x, c2.x,
                         c0.y, c1.y, c2.y,
                         c0.z, c1.z, c2.z);
    }

    // Create from row vectors
    static Matrix3x3 fromRows(const Vector3D& r0, const Vector3D& r1, const Vector3D& r2) {
        return Matrix3x3(r0.x, r0.y, r0.z,
                         r1.x, r1.y, r1.z,
                         r2.x, r2.y, r2.z);
    }

    // Outer product: v1 ⊗ v2
    static Matrix3x3 outerProduct(const Vector3D& v1, const Vector3D& v2) {
        return Matrix3x3(v1.x * v2.x, v1.x * v2.y, v1.x * v2.z,
                         v1.y * v2.x, v1.y * v2.y, v1.y * v2.z,
                         v1.z * v2.x, v1.z * v2.y, v1.z * v2.z);
    }

    // Element access
    double& operator()(int row, int col) { return m[row][col]; }
    const double& operator()(int row, int col) const { return m[row][col]; }

    // Get row/column as Vector3D
    Vector3D row(int i) const {
        return Vector3D(m[i][0], m[i][1], m[i][2]);
    }

    Vector3D col(int j) const {
        return Vector3D(m[0][j], m[1][j], m[2][j]);
    }

    // Matrix addition
    Matrix3x3 operator+(const Matrix3x3& other) const {
        Matrix3x3 result;
        for (int i = 0; i < 3; ++i) {
            for (int j = 0; j < 3; ++j) {
                result.m[i][j] = m[i][j] + other.m[i][j];
            }
        }
        return result;
    }

    // Matrix subtraction
    Matrix3x3 operator-(const Matrix3x3& other) const {
        Matrix3x3 result;
        for (int i = 0; i < 3; ++i) {
            for (int j = 0; j < 3; ++j) {
                result.m[i][j] = m[i][j] - other.m[i][j];
            }
        }
        return result;
    }

    // Scalar multiplication
    Matrix3x3 operator*(double scalar) const {
        Matrix3x3 result;
        for (int i = 0; i < 3; ++i) {
            for (int j = 0; j < 3; ++j) {
                result.m[i][j] = m[i][j] * scalar;
            }
        }
        return result;
    }

    // Matrix multiplication
    Matrix3x3 operator*(const Matrix3x3& other) const {
        Matrix3x3 result;
        for (int i = 0; i < 3; ++i) {
            for (int j = 0; j < 3; ++j) {
                result.m[i][j] = 0;
                for (int k = 0; k < 3; ++k) {
                    result.m[i][j] += m[i][k] * other.m[k][j];
                }
            }
        }
        return result;
    }

    // Matrix-vector multiplication
    Vector3D operator*(const Vector3D& v) const {
        return Vector3D(
            m[0][0] * v.x + m[0][1] * v.y + m[0][2] * v.z,
            m[1][0] * v.x + m[1][1] * v.y + m[1][2] * v.z,
            m[2][0] * v.x + m[2][1] * v.y + m[2][2] * v.z
        );
    }

    // Compound operators
    Matrix3x3& operator+=(const Matrix3x3& other) {
        for (int i = 0; i < 3; ++i) {
            for (int j = 0; j < 3; ++j) {
                m[i][j] += other.m[i][j];
            }
        }
        return *this;
    }

    Matrix3x3& operator-=(const Matrix3x3& other) {
        for (int i = 0; i < 3; ++i) {
            for (int j = 0; j < 3; ++j) {
                m[i][j] -= other.m[i][j];
            }
        }
        return *this;
    }

    Matrix3x3& operator*=(double scalar) {
        for (int i = 0; i < 3; ++i) {
            for (int j = 0; j < 3; ++j) {
                m[i][j] *= scalar;
            }
        }
        return *this;
    }

    // Transpose
    Matrix3x3 transpose() const {
        return Matrix3x3(m[0][0], m[1][0], m[2][0],
                         m[0][1], m[1][1], m[2][1],
                         m[0][2], m[1][2], m[2][2]);
    }

    // Determinant
    double determinant() const {
        return m[0][0] * (m[1][1] * m[2][2] - m[1][2] * m[2][1])
             - m[0][1] * (m[1][0] * m[2][2] - m[1][2] * m[2][0])
             + m[0][2] * (m[1][0] * m[2][1] - m[1][1] * m[2][0]);
    }

    // Trace
    double trace() const {
        return m[0][0] + m[1][1] + m[2][2];
    }

    // Inverse (throws if singular)
    Matrix3x3 inverse() const {
        double det = determinant();
        if (std::abs(det) < 1e-14) {
            throw std::runtime_error("Matrix3x3::inverse: Singular matrix");
        }

        double invDet = 1.0 / det;

        Matrix3x3 result;
        result.m[0][0] = (m[1][1] * m[2][2] - m[1][2] * m[2][1]) * invDet;
        result.m[0][1] = (m[0][2] * m[2][1] - m[0][1] * m[2][2]) * invDet;
        result.m[0][2] = (m[0][1] * m[1][2] - m[0][2] * m[1][1]) * invDet;
        result.m[1][0] = (m[1][2] * m[2][0] - m[1][0] * m[2][2]) * invDet;
        result.m[1][1] = (m[0][0] * m[2][2] - m[0][2] * m[2][0]) * invDet;
        result.m[1][2] = (m[0][2] * m[1][0] - m[0][0] * m[1][2]) * invDet;
        result.m[2][0] = (m[1][0] * m[2][1] - m[1][1] * m[2][0]) * invDet;
        result.m[2][1] = (m[0][1] * m[2][0] - m[0][0] * m[2][1]) * invDet;
        result.m[2][2] = (m[0][0] * m[1][1] - m[0][1] * m[1][0]) * invDet;

        return result;
    }

    // Symmetric part: 1/2 * (A + A^T)
    Matrix3x3 symmetric() const {
        Matrix3x3 result;
        for (int i = 0; i < 3; ++i) {
            for (int j = 0; j < 3; ++j) {
                result.m[i][j] = 0.5 * (m[i][j] + m[j][i]);
            }
        }
        return result;
    }

    // Skew-symmetric part: 1/2 * (A - A^T)
    Matrix3x3 skewSymmetric() const {
        Matrix3x3 result;
        for (int i = 0; i < 3; ++i) {
            for (int j = 0; j < 3; ++j) {
                result.m[i][j] = 0.5 * (m[i][j] - m[j][i]);
            }
        }
        return result;
    }

    // Frobenius norm: sqrt(sum of squares)
    double frobeniusNorm() const {
        double sum = 0;
        for (int i = 0; i < 3; ++i) {
            for (int j = 0; j < 3; ++j) {
                sum += m[i][j] * m[i][j];
            }
        }
        return std::sqrt(sum);
    }

    // Double contraction A : B = sum(A_ij * B_ij)
    double doubleContraction(const Matrix3x3& other) const {
        double sum = 0;
        for (int i = 0; i < 3; ++i) {
            for (int j = 0; j < 3; ++j) {
                sum += m[i][j] * other.m[i][j];
            }
        }
        return sum;
    }

    // Check if approximately equal
    bool isApprox(const Matrix3x3& other, double tolerance = 1e-10) const {
        for (int i = 0; i < 3; ++i) {
            for (int j = 0; j < 3; ++j) {
                if (std::abs(m[i][j] - other.m[i][j]) > tolerance) {
                    return false;
                }
            }
        }
        return true;
    }
};

// Scalar multiplication from the left
inline Matrix3x3 operator*(double scalar, const Matrix3x3& mat) {
    return mat * scalar;
}

} // namespace KooRemapper

