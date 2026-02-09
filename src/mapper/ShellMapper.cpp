#include "mapper/ShellMapper.h"
#include "util/Logger.h"
#include <cmath>

namespace KooRemapper {

std::array<double, 4> ShellMapper::shapeFunctions(double xi, double eta) {
    return {
        0.25 * (1.0 - xi) * (1.0 - eta),
        0.25 * (1.0 + xi) * (1.0 - eta),
        0.25 * (1.0 + xi) * (1.0 + eta),
        0.25 * (1.0 - xi) * (1.0 + eta)
    };
}

std::array<double, 4> ShellMapper::shapeFunctionDerivsXi(double xi, double eta) {
    (void)xi;
    return {
        -0.25 * (1.0 - eta),
         0.25 * (1.0 - eta),
         0.25 * (1.0 + eta),
        -0.25 * (1.0 + eta)
    };
}

std::array<double, 4> ShellMapper::shapeFunctionDerivsEta(double xi, double eta) {
    (void)eta;
    return {
        -0.25 * (1.0 - xi),
        -0.25 * (1.0 + xi),
         0.25 * (1.0 + xi),
         0.25 * (1.0 - xi)
    };
}

bool ShellMapper::build(const ShellMesh& bentShell) {
    bentShell_ = &bentShell;
    unmappedCount_ = 0;

    // Step 1: Unfold bent shell to flat 2D
    if (!unfolder_.unfold(bentShell)) {
        errorMessage_ = "Failed to unfold shell mesh";
        return false;
    }

    // Step 2: Build spatial hash from unfolded elements
    spatialHash_.build(bentShell.getElements(), unfolder_.getFlatPositions());

    return true;
}

Vector3D ShellMapper::interpolateOnBentSurface(int elemId, double xi, double eta) const {
    const auto* elem = bentShell_->getElement(elemId);
    if (!elem) return Vector3D();

    auto N = shapeFunctions(xi, eta);
    Vector3D pos;

    for (int i = 0; i < 4; ++i) {
        const Node* node = bentShell_->getNode(elem->nodeIds[i]);
        if (node) {
            pos += node->position * N[i];
        }
    }

    return pos;
}

Vector3D ShellMapper::computeNormal(int elemId, double xi, double eta) const {
    const auto* elem = bentShell_->getElement(elemId);
    if (!elem) return Vector3D(0, 0, 1);

    // Interpolate node-averaged normals using shape functions (smooth normal)
    // This gives continuous normal variation within each element,
    // enabling proper bending strain capture through thickness.
    auto N = shapeFunctions(xi, eta);
    Vector3D normal;
    for (int i = 0; i < 4; ++i) {
        normal += bentShell_->getNodeNormal(elem->nodeIds[i]) * N[i];
    }

    double mag = normal.magnitude();
    if (mag > 1e-15) {
        return normal / mag;
    }

    // Fallback: tangent cross product (for degenerate cases)
    auto dNdxi = shapeFunctionDerivsXi(xi, eta);
    auto dNdeta = shapeFunctionDerivsEta(xi, eta);

    Vector3D dPdxi, dPdeta;
    for (int i = 0; i < 4; ++i) {
        const Node* node = bentShell_->getNode(elem->nodeIds[i]);
        if (node) {
            dPdxi += node->position * dNdxi[i];
            dPdeta += node->position * dNdeta[i];
        }
    }

    normal = dPdxi.cross(dPdeta);
    mag = normal.magnitude();
    if (mag > 1e-15) {
        return normal / mag;
    }
    return Vector3D(0, 0, 1);
}

void ShellMapper::computeAlignment(const Mesh& flatDetail) const {
    // Get unfolded shell bounding box
    Vector2D unfoldMin, unfoldMax;
    unfolder_.getBoundingBox(unfoldMin, unfoldMax);
    double unfoldSizeX = unfoldMax.x - unfoldMin.x;
    double unfoldSizeY = unfoldMax.y - unfoldMin.y;

    // Get flat detail XY bounding box
    auto [flatBBMin, flatBBMax] = flatDetail.getBoundingBox();
    double flatSizeX = flatBBMax.x - flatBBMin.x;
    double flatSizeY = flatBBMax.y - flatBBMin.y;

    flatMinX_ = flatBBMin.x;
    flatMinY_ = flatBBMin.y;
    flatMaxX_ = flatBBMax.x;
    flatMaxY_ = flatBBMax.y;

    // Detect axis swap: compare aspect ratios
    // Normal:  flat X → unfold X, flat Y → unfold Y
    // Swapped: flat X → unfold Y, flat Y → unfold X (with reversal for orientation)
    if (unfoldSizeX > 1e-15 && unfoldSizeY > 1e-15 &&
        flatSizeX > 1e-15 && flatSizeY > 1e-15) {

        double ratioNormal = std::abs(flatSizeX / flatSizeY - unfoldSizeX / unfoldSizeY);
        double ratioSwapped = std::abs(flatSizeX / flatSizeY - unfoldSizeY / unfoldSizeX);

        axesSwapped_ = (ratioSwapped < ratioNormal);

        if (axesSwapped_) {
            // Swap + reverse one axis to convert reflection to rotation (det=+1)
            // flat X → unfold Y (normal direction)
            // flat Y → unfold X (reversed direction: flatMaxY maps to unfoldMinX)
            scaleX_ = unfoldSizeY / flatSizeX;
            scaleY_ = unfoldSizeX / flatSizeY;
            offsetX_ = unfoldMin.y;
            offsetY_ = unfoldMax.x;  // Start from max, go backwards
        } else {
            // flat X → unfold X, flat Y → unfold Y
            scaleX_ = unfoldSizeX / flatSizeX;
            scaleY_ = unfoldSizeY / flatSizeY;
            offsetX_ = unfoldMin.x;
            offsetY_ = unfoldMin.y;
        }
    } else {
        axesSwapped_ = false;
        scaleX_ = scaleY_ = 1.0;
        offsetX_ = offsetY_ = 0.0;
    }

    alignmentComputed_ = true;
}

void ShellMapper::transformToUnfolded(double flatX, double flatY,
                                       double& unfoldX, double& unfoldY) const {
    if (axesSwapped_) {
        // flat X → unfold Y (forward), flat Y → unfold X (reversed for orientation)
        unfoldY = (flatX - flatMinX_) * scaleX_ + offsetX_;
        unfoldX = offsetY_ - (flatY - flatMinY_) * scaleY_;
    } else {
        unfoldX = (flatX - flatMinX_) * scaleX_ + offsetX_;
        unfoldY = (flatY - flatMinY_) * scaleY_ + offsetY_;
    }
}

Vector3D ShellMapper::mapPoint(const Vector3D& flatPoint, double thickness) const {
    if (!bentShell_) return flatPoint;

    double x = flatPoint.x;
    double y = flatPoint.y;
    double z = flatPoint.z;

    // Transform flat detail coordinates to unfolded shell coordinates
    double ux, uy;
    transformToUnfolded(x, y, ux, uy);

    // Find which flat shell element contains this (ux, uy) point
    double xi, eta;
    int elemId = spatialHash_.findContainingElement(ux, uy, xi, eta);

    if (elemId < 0) {
        unmappedCount_++;
        return flatPoint;  // Return original if not found
    }

    // Interpolate position on bent surface
    Vector3D surfacePos = interpolateOnBentSurface(elemId, xi, eta);

    // Compute shell normal at this point
    Vector3D normal = computeNormal(elemId, xi, eta);

    // Map thickness direction: z is the offset from the shell mid-surface
    // If thickness > 0, normalize z to [-0.5, 0.5] range
    double w = 0.0;
    if (thickness > 1e-15) {
        w = z / thickness;
    }

    return surfacePos + normal * (w * thickness);
}

bool ShellMapper::mapMesh(const Mesh& flatDetail, Mesh& resultMesh, double thickness) const {
    if (!bentShell_) {
        errorMessage_ = "ShellMapper not built";
        return false;
    }

    // Compute alignment transform (flat detail BB → unfolded shell BB)
    computeAlignment(flatDetail);

    // Copy mesh structure
    resultMesh = flatDetail;
    unmappedCount_ = 0;

    // Map each node
    for (auto& [nodeId, node] : resultMesh.nodes) {
        Vector3D bentPos = mapPoint(node.position, thickness);
        node.setMappedPosition(bentPos);
    }

    if (unmappedCount_ > 0) {
        Logger::instance().warning("ShellMapper: " + std::to_string(unmappedCount_) +
                                   " nodes could not be mapped (outside shell domain)");
    }

    return true;
}

} // namespace KooRemapper
