#pragma once

#include "core/Mesh.h"
#include <string>
#include <vector>

namespace KooRemapper {

/**
 * Validation results
 */
struct ValidationResult {
    bool isValid;
    std::vector<std::string> errors;
    std::vector<std::string> warnings;

    ValidationResult() : isValid(true) {}

    void addError(const std::string& msg) {
        errors.push_back(msg);
        isValid = false;
    }

    void addWarning(const std::string& msg) {
        warnings.push_back(msg);
    }
};

/**
 * Mesh validator
 */
class Validator {
public:
    /**
     * Validate a mesh for general consistency
     */
    static ValidationResult validateMesh(const Mesh& mesh);

    /**
     * Validate that mesh is suitable as a structured bent reference
     */
    static ValidationResult validateBentMesh(const Mesh& mesh);

    /**
     * Validate that mesh is suitable for mapping
     */
    static ValidationResult validateFlatMesh(const Mesh& mesh);

    /**
     * Validate element quality (Jacobian, aspect ratio, etc.)
     */
    static ValidationResult validateElementQuality(const Mesh& mesh);

    /**
     * Check if file exists and is readable
     */
    static bool fileExists(const std::string& path);

    /**
     * Check if path is writable
     */
    static bool isWritable(const std::string& path);

    /**
     * Validate k-file format
     */
    static bool isValidKFile(const std::string& path);

    /**
     * Calculate Jacobian for a hexahedral or tetrahedral element
     */
    static double calculateJacobian(const Mesh& mesh, const Element& elem);

    /**
     * Calculate aspect ratio for a hexahedral element
     */
    static double calculateAspectRatio(const Mesh& mesh, const Element& elem);
};

} // namespace KooRemapper
