#include "util/Validator.h"
#include "core/Platform.h"
#include <fstream>
#include <cmath>
#include <algorithm>

namespace KooRemapper {

ValidationResult Validator::validateMesh(const Mesh& mesh) {
    ValidationResult result;

    // Check if mesh has nodes
    if (mesh.getNodeCount() == 0) {
        result.addError("Mesh has no nodes");
        return result;
    }

    // Check if mesh has elements
    if (mesh.getElementCount() == 0) {
        result.addError("Mesh has no elements");
        return result;
    }

    // Check element node references
    for (const auto& pair : mesh.getElements()) {
        const Element& elem = pair.second;

        for (int i = 0; i < 8; ++i) {
            if (!mesh.getNode(elem.nodeIds[i])) {
                result.addError("Element " + std::to_string(elem.id) +
                               " references non-existent node " +
                               std::to_string(elem.nodeIds[i]));
            }
        }
    }

    return result;
}

ValidationResult Validator::validateBentMesh(const Mesh& mesh) {
    ValidationResult result = validateMesh(mesh);
    if (!result.isValid) return result;

    // Check that all elements are hexahedral
    int nonHex8Count = 0;
    int tet4Count = 0;
    for (const auto& pair : mesh.getElements()) {
        const Element& elem = pair.second;
        if (elem.type != ElementType::HEX8) {
            nonHex8Count++;
            if (elem.type == ElementType::TET4) {
                tet4Count++;
            }
        }
    }

    if (nonHex8Count > 0) {
        if (tet4Count == nonHex8Count) {
            result.addError("Bent mesh contains " + std::to_string(tet4Count) +
                           " TET4 elements. Only structured HEX8 meshes are supported as bent reference.");
        } else {
            result.addError("Bent mesh contains " + std::to_string(nonHex8Count) +
                           " non-hexahedral elements. Only structured HEX8 meshes are supported.");
        }
    }

    // Check for minimum number of elements
    if (mesh.getElementCount() < 1) {
        result.addError("Bent mesh must have at least 1 element");
    }

    // Warning for small meshes
    if (mesh.getElementCount() < 8) {
        result.addWarning("Bent mesh has fewer than 8 elements, "
                         "structured grid detection may be unreliable");
    }

    return result;
}

ValidationResult Validator::validateFlatMesh(const Mesh& mesh) {
    ValidationResult result = validateMesh(mesh);
    if (!result.isValid) return result;

    // Check that all elements are hexahedral or tetrahedral
    for (const auto& pair : mesh.getElements()) {
        const Element& elem = pair.second;
        if (elem.type != ElementType::HEX8 && elem.type != ElementType::TET4) {
            result.addError("Element " + std::to_string(elem.id) +
                           " is not a supported element type (HEX8 or TET4)");
        }
    }

    return result;
}

ValidationResult Validator::validateElementQuality(const Mesh& mesh) {
    ValidationResult result;

    int negativeJacobian = 0;
    int highAspectRatio = 0;
    double minJacobian = std::numeric_limits<double>::max();
    double maxAspectRatio = 0;

    for (const auto& pair : mesh.getElements()) {
        const Element& elem = pair.second;

        double jacobian = calculateJacobian(mesh, elem);
        double aspectRatio = calculateAspectRatio(mesh, elem);

        if (jacobian <= 0) {
            ++negativeJacobian;
        }
        minJacobian = std::min(minJacobian, jacobian);

        if (aspectRatio > 10.0) {
            ++highAspectRatio;
        }
        maxAspectRatio = std::max(maxAspectRatio, aspectRatio);
    }

    if (negativeJacobian > 0) {
        result.addError(std::to_string(negativeJacobian) +
                       " elements have negative or zero Jacobian");
    }

    if (highAspectRatio > 0) {
        result.addWarning(std::to_string(highAspectRatio) +
                         " elements have high aspect ratio (>10)");
    }

    return result;
}

double Validator::calculateJacobian(const Mesh& mesh, const Element& elem) {
    if (elem.type == ElementType::TET4) {
        // TET4 Jacobian: 6 * volume = det([v1-v0, v2-v0, v3-v0])
        std::array<Vector3D, 4> verts;
        for (int i = 0; i < 4; ++i) {
            const Node* node = mesh.getNode(elem.nodeIds[i]);
            if (!node) return 0.0;
            verts[i] = node->getEffectivePosition();
        }

        Vector3D e1 = verts[1] - verts[0];
        Vector3D e2 = verts[2] - verts[0];
        Vector3D e3 = verts[3] - verts[0];

        // Jacobian = e1 . (e2 x e3)  (6 * signed volume)
        return e1.dot(e2.cross(e3));
    }

    // HEX8: Get corner nodes
    std::array<Vector3D, 8> corners;
    for (int i = 0; i < 8; ++i) {
        const Node* node = mesh.getNode(elem.nodeIds[i]);
        if (!node) return 0.0;
        corners[i] = node->getEffectivePosition();
    }

    // Calculate Jacobian at element center
    Vector3D dxdu = (corners[1] + corners[2] + corners[5] + corners[6]) * 0.25 -
                    (corners[0] + corners[3] + corners[4] + corners[7]) * 0.25;
    Vector3D dxdv = (corners[2] + corners[3] + corners[6] + corners[7]) * 0.25 -
                    (corners[0] + corners[1] + corners[4] + corners[5]) * 0.25;
    Vector3D dxdw = (corners[4] + corners[5] + corners[6] + corners[7]) * 0.25 -
                    (corners[0] + corners[1] + corners[2] + corners[3]) * 0.25;

    return dxdu.dot(dxdv.cross(dxdw));
}

double Validator::calculateAspectRatio(const Mesh& mesh, const Element& elem) {
    // Get corner nodes
    std::array<Vector3D, 8> corners;
    for (int i = 0; i < 8; ++i) {
        const Node* node = mesh.getNode(elem.nodeIds[i]);
        if (!node) return 0.0;
        corners[i] = node->getEffectivePosition();
    }

    // Calculate edge lengths (12 edges of a hex)
    std::vector<double> lengths;

    // Bottom face edges (0-1, 1-2, 2-3, 3-0)
    lengths.push_back(corners[0].distanceTo(corners[1]));
    lengths.push_back(corners[1].distanceTo(corners[2]));
    lengths.push_back(corners[2].distanceTo(corners[3]));
    lengths.push_back(corners[3].distanceTo(corners[0]));

    // Top face edges (4-5, 5-6, 6-7, 7-4)
    lengths.push_back(corners[4].distanceTo(corners[5]));
    lengths.push_back(corners[5].distanceTo(corners[6]));
    lengths.push_back(corners[6].distanceTo(corners[7]));
    lengths.push_back(corners[7].distanceTo(corners[4]));

    // Vertical edges (0-4, 1-5, 2-6, 3-7)
    lengths.push_back(corners[0].distanceTo(corners[4]));
    lengths.push_back(corners[1].distanceTo(corners[5]));
    lengths.push_back(corners[2].distanceTo(corners[6]));
    lengths.push_back(corners[3].distanceTo(corners[7]));

    double minLen = *std::min_element(lengths.begin(), lengths.end());
    double maxLen = *std::max_element(lengths.begin(), lengths.end());

    if (minLen <= 0) return std::numeric_limits<double>::max();

    return maxLen / minLen;
}

bool Validator::fileExists(const std::string& path) {
    return Platform::fileExists(path);
}

bool Validator::isWritable(const std::string& path) {
    // Try to create/open the file
    std::ofstream file(path, std::ios::app);
    bool writable = file.is_open();
    file.close();

    // If we created it, remove it
    if (writable) {
        std::ifstream check(path);
        if (check.peek() == std::ifstream::traits_type::eof()) {
            check.close();
            std::remove(path.c_str());
        }
    }

    return writable;
}

bool Validator::isValidKFile(const std::string& path) {
    std::ifstream file(path);
    if (!file.is_open()) return false;

    std::string line;
    bool hasKeyword = false;

    while (std::getline(file, line)) {
        // Skip empty lines
        if (line.empty()) continue;

        // Check for k-file keyword (starts with *)
        if (line[0] == '*') {
            hasKeyword = true;
            break;
        }

        // Check for comment lines ($ prefix)
        if (line[0] == '$') continue;

        // If we hit a non-comment, non-keyword line first, might not be valid
        break;
    }

    return hasKeyword;
}

} // namespace KooRemapper
