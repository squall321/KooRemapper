#ifndef INTERSECTIONDETECTOR_H
#define INTERSECTIONDETECTOR_H

#include "core/Vector3D.h"
#include <vector>
#include <array>

namespace KooRemapper {

class IntersectionDetector {
public:
    struct Intersection {
        int elem1;
        int elem2;
        Vector3D location;
    };

    struct BoundingBox {
        Vector3D min;
        Vector3D max;

        bool intersects(const BoundingBox& other) const {
            return !(max.x < other.min.x || min.x > other.max.x ||
                     max.y < other.min.y || min.y > other.max.y ||
                     max.z < other.min.z || min.z > other.max.z);
        }
    };

    // Detect self-intersections among solid elements
    std::vector<Intersection> detectSelfIntersections(
        const std::vector<std::array<Vector3D, 8>>& elements,
        double tolerance = 1e-6);

    // Simplified version: just count potential overlaps via bounding boxes
    int countPotentialIntersections(
        const std::vector<std::array<Vector3D, 8>>& elements,
        double tolerance = 1e-6);

private:
    // Compute bounding box for HEX8 element
    BoundingBox computeBoundingBox(const std::array<Vector3D, 8>& nodes,
                                    double margin = 0.0) const;

    // Triangle-triangle intersection test (for detailed check)
    bool triTriIntersect(const Vector3D& v0, const Vector3D& v1, const Vector3D& v2,
                         const Vector3D& u0, const Vector3D& u1, const Vector3D& u2) const;
};

} // namespace KooRemapper

#endif // INTERSECTIONDETECTOR_H
