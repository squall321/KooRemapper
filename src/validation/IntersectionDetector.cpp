#include "validation/IntersectionDetector.h"
#include <algorithm>
#include <limits>

// Knowledge graph (lat.md):
//   @lat: [[modules/validation]]

namespace KooRemapper {

IntersectionDetector::BoundingBox IntersectionDetector::computeBoundingBox(
    const std::array<Vector3D, 8>& nodes, double margin) const {

    BoundingBox bbox;
    bbox.min = Vector3D(std::numeric_limits<double>::max(),
                        std::numeric_limits<double>::max(),
                        std::numeric_limits<double>::max());
    bbox.max = Vector3D(std::numeric_limits<double>::lowest(),
                        std::numeric_limits<double>::lowest(),
                        std::numeric_limits<double>::lowest());

    for (const auto& node : nodes) {
        bbox.min.x = std::min(bbox.min.x, node.x);
        bbox.min.y = std::min(bbox.min.y, node.y);
        bbox.min.z = std::min(bbox.min.z, node.z);
        bbox.max.x = std::max(bbox.max.x, node.x);
        bbox.max.y = std::max(bbox.max.y, node.y);
        bbox.max.z = std::max(bbox.max.z, node.z);
    }

    // Add margin
    bbox.min.x -= margin;
    bbox.min.y -= margin;
    bbox.min.z -= margin;
    bbox.max.x += margin;
    bbox.max.y += margin;
    bbox.max.z += margin;

    return bbox;
}

int IntersectionDetector::countPotentialIntersections(
    const std::vector<std::array<Vector3D, 8>>& elements,
    double tolerance) {

    if (elements.size() < 2) return 0;

    // Compute bounding boxes for all elements
    std::vector<BoundingBox> bboxes;
    bboxes.reserve(elements.size());
    for (const auto& elem : elements) {
        bboxes.push_back(computeBoundingBox(elem, tolerance));
    }

    // Count overlapping bounding boxes
    int count = 0;
    for (size_t i = 0; i < bboxes.size(); ++i) {
        for (size_t j = i + 1; j < bboxes.size(); ++j) {
            if (bboxes[i].intersects(bboxes[j])) {
                count++;
            }
        }
    }

    return count;
}

std::vector<IntersectionDetector::Intersection>
IntersectionDetector::detectSelfIntersections(
    const std::vector<std::array<Vector3D, 8>>& elements,
    double tolerance) {

    std::vector<Intersection> intersections;

    if (elements.size() < 2) return intersections;

    // Broad phase: bounding box check
    std::vector<BoundingBox> bboxes;
    bboxes.reserve(elements.size());
    for (const auto& elem : elements) {
        bboxes.push_back(computeBoundingBox(elem, tolerance));
    }

    // Check pairs with overlapping bounding boxes
    for (size_t i = 0; i < bboxes.size(); ++i) {
        for (size_t j = i + 1; j < bboxes.size(); ++j) {
            if (bboxes[i].intersects(bboxes[j])) {
                // Potential intersection found
                // For now, just record the center of overlapping region
                Intersection inter;
                inter.elem1 = static_cast<int>(i);
                inter.elem2 = static_cast<int>(j);

                // Approximate location: center of overlap
                inter.location.x = (std::max(bboxes[i].min.x, bboxes[j].min.x) +
                                   std::min(bboxes[i].max.x, bboxes[j].max.x)) * 0.5;
                inter.location.y = (std::max(bboxes[i].min.y, bboxes[j].min.y) +
                                   std::min(bboxes[i].max.y, bboxes[j].max.y)) * 0.5;
                inter.location.z = (std::max(bboxes[i].min.z, bboxes[j].min.z) +
                                   std::min(bboxes[i].max.z, bboxes[j].max.z)) * 0.5;

                intersections.push_back(inter);
            }
        }
    }

    return intersections;
}

bool IntersectionDetector::triTriIntersect(
    const Vector3D& v0, const Vector3D& v1, const Vector3D& v2,
    const Vector3D& u0, const Vector3D& u1, const Vector3D& u2) const {

    // Simplified Möller-Trumbore triangle-triangle intersection
    // For now, return false (detailed implementation would go here)
    // This is a placeholder for future enhancement
    return false;
}

} // namespace KooRemapper
