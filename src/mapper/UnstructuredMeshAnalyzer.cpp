#include "mapper/UnstructuredMeshAnalyzer.h"
#include <limits>

namespace KooRemapper {

UnstructuredMeshAnalyzer::UnstructuredMeshAnalyzer()
{}

void UnstructuredMeshAnalyzer::analyze(const Mesh& mesh) {
    if (mesh.nodes.empty()) {
        bbMin_ = bbMax_ = dimensions_ = center_ = Vector3D();
        return;
    }

    // Calculate bounding box
    bbMin_ = Vector3D(std::numeric_limits<double>::max(),
                       std::numeric_limits<double>::max(),
                       std::numeric_limits<double>::max());
    bbMax_ = Vector3D(std::numeric_limits<double>::lowest(),
                       std::numeric_limits<double>::lowest(),
                       std::numeric_limits<double>::lowest());

    for (const auto& [id, node] : mesh.nodes) {
        bbMin_.x = std::min(bbMin_.x, node.position.x);
        bbMin_.y = std::min(bbMin_.y, node.position.y);
        bbMin_.z = std::min(bbMin_.z, node.position.z);
        bbMax_.x = std::max(bbMax_.x, node.position.x);
        bbMax_.y = std::max(bbMax_.y, node.position.y);
        bbMax_.z = std::max(bbMax_.z, node.position.z);
    }

    dimensions_ = bbMax_ - bbMin_;
    center_ = (bbMin_ + bbMax_) * 0.5;
}

Vector3D UnstructuredMeshAnalyzer::normalize(const Vector3D& pos) const {
    Vector3D normalized;

    if (dimensions_.x > 0) {
        normalized.x = (pos.x - bbMin_.x) / dimensions_.x;
    } else {
        normalized.x = 0.5;
    }

    if (dimensions_.y > 0) {
        normalized.y = (pos.y - bbMin_.y) / dimensions_.y;
    } else {
        normalized.y = 0.5;
    }

    if (dimensions_.z > 0) {
        normalized.z = (pos.z - bbMin_.z) / dimensions_.z;
    } else {
        normalized.z = 0.5;
    }

    return normalized;
}

Vector3D UnstructuredMeshAnalyzer::getScaleFactor(const UnstructuredMeshAnalyzer& other) const {
    Vector3D scale(1.0, 1.0, 1.0);

    if (dimensions_.x > 0 && other.dimensions_.x > 0) {
        scale.x = other.dimensions_.x / dimensions_.x;
    }
    if (dimensions_.y > 0 && other.dimensions_.y > 0) {
        scale.y = other.dimensions_.y / dimensions_.y;
    }
    if (dimensions_.z > 0 && other.dimensions_.z > 0) {
        scale.z = other.dimensions_.z / dimensions_.z;
    }

    return scale;
}

Vector3D UnstructuredMeshAnalyzer::getScaleToSize(double targetX, double targetY, double targetZ) const {
    Vector3D scale(1.0, 1.0, 1.0);

    if (dimensions_.x > 0) scale.x = targetX / dimensions_.x;
    if (dimensions_.y > 0) scale.y = targetY / dimensions_.y;
    if (dimensions_.z > 0) scale.z = targetZ / dimensions_.z;

    return scale;
}

} // namespace KooRemapper
