#pragma once

#include "core/Mesh.h"
#include <string>
#include <vector>

// Knowledge graph (lat.md):
//   @lat: [[modules/util]]

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

    /** 체적 야코비안이 **정의되는** 요소인가.
     *
     * ⚠ 셸(QUAD4)에는 정의되지 않는다. 그런데 `calculateJacobian` 은 TET4 가 아닌 것을 모두
     * HEX8 로 읽어 `nodeIds[4..7]` 이 없으면 `0.0` 을 돌려주고, 그러면 `j <= 0` 이 셸을 전부
     * "음수 야코비안" 으로 센다 — 실측(2026-10-02 현장 보고): 공식 예제 `arc_shell.k`(셸 8요소)가
     * `Min=Max=0.000000` · 음수 **8건**으로 나왔다. 그 노이즈가 정작 **진짜** 음수 야코비안
     * (솔리드)을 가린다. 셸은 종횡비·워프로 보고 야코비안은 솔리드에만 적용한다. */
    static bool jacobianApplies(const Element& elem);

    /**
     * Calculate aspect ratio for a hexahedral element
     */
    static double calculateAspectRatio(const Mesh& mesh, const Element& elem);
};

} // namespace KooRemapper
