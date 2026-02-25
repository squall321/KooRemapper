#include "validation/MaterialCardValidator.h"
#include <sstream>
#include <algorithm>
#include <cctype>
#include <cmath>

namespace KooRemapper {

MaterialCardValidator::ValidationResult MaterialCardValidator::validate(
    const std::string& materialCard, bool checkPlaceholder) {

    ValidationResult result;
    result.isValid = true;

    if (materialCard.empty()) {
        result.addError("Material card is empty");
        return result;
    }

    // Split into lines
    std::vector<std::string> lines;
    std::istringstream iss(materialCard);
    std::string line;
    while (std::getline(iss, line)) {
        lines.push_back(line);
    }

    if (lines.empty()) {
        result.addError("Material card has no content");
        return result;
    }

    // Find keyword line
    std::string keyword;
    int keywordLineIdx = -1;
    for (size_t i = 0; i < lines.size(); ++i) {
        if (isKeywordLine(lines[i])) {
            keyword = extractKeyword(lines[i]);
            keywordLineIdx = static_cast<int>(i);
            break;
        }
    }

    if (keyword.empty()) {
        result.addError("No valid *MAT_ keyword found");
        return result;
    }

    // Check for @MID@ placeholder if required
    if (checkPlaceholder) {
        bool hasMidPlaceholder = false;
        for (const auto& ln : lines) {
            if (ln.find("@MID@") != std::string::npos) {
                hasMidPlaceholder = true;
                break;
            }
        }
        if (!hasMidPlaceholder) {
            result.addWarning("No @MID@ placeholder found - material ID assignment may fail");
        }
    }

    // Validate based on keyword type
    if (keyword.find("MAT_ELASTIC") != std::string::npos) {
        validateElastic(lines, result);
    } else if (keyword.find("MAT_COHESIVE_MIXED_MODE") != std::string::npos) {
        validateCohesiveMixedMode(lines, result);
    } else if (keyword.find("MAT_PLASTIC_KINEMATIC") != std::string::npos ||
               keyword.find("MAT_024") != std::string::npos) {
        validatePlasticKinematic(lines, result);
    } else {
        // Generic validation for unknown types
        result.addWarning("Unknown material type '" + keyword + "' - skipping detailed validation");
    }

    return result;
}

bool MaterialCardValidator::isKeywordLine(const std::string& line) const {
    std::string upper = line;
    std::transform(upper.begin(), upper.end(), upper.begin(), ::toupper);
    return upper.find("*MAT") != std::string::npos;
}

std::string MaterialCardValidator::extractKeyword(const std::string& line) const {
    std::string upper = line;
    std::transform(upper.begin(), upper.end(), upper.begin(), ::toupper);

    size_t start = upper.find("*MAT");
    if (start == std::string::npos) return "";

    size_t end = upper.find_first_of(" \t\r\n", start);
    if (end == std::string::npos) end = upper.length();

    return upper.substr(start, end - start);
}

void MaterialCardValidator::validateElastic(
    const std::vector<std::string>& lines, ValidationResult& result) {

    // Find first data line (non-comment, non-blank after keyword)
    int dataLineIdx = -1;
    for (size_t i = 0; i < lines.size(); ++i) {
        if (isKeywordLine(lines[i])) {
            // Look for data line after keyword
            for (size_t j = i + 1; j < lines.size(); ++j) {
                if (!isCommentLine(lines[j]) && !isBlankLine(lines[j])) {
                    dataLineIdx = static_cast<int>(j);
                    break;
                }
            }
            break;
        }
    }

    if (dataLineIdx < 0) {
        result.addError("*MAT_ELASTIC: No data line found");
        return;
    }

    auto fields = parseDataLine(lines[dataLineIdx]);

    // Expected: MID RO E PR (at least 4 fields)
    if (fields.size() < 4) {
        result.addError("*MAT_ELASTIC: Expected at least 4 fields (MID, RO, E, PR), found " +
                       std::to_string(fields.size()));
        return;
    }

    // Check if MID is @MID@ (skip numeric check)
    bool midIsPlaceholder = (fields[0] == "@MID@");

    // Validate RO (density) - must be positive
    if (!midIsPlaceholder) {
        try {
            double ro = std::stod(fields[1]);
            if (ro <= 0) {
                result.addWarning("*MAT_ELASTIC: Density (RO) should be positive, got " + fields[1]);
            }
        } catch (...) {
            // Field might be @MID@ or other placeholder
            if (fields[1].find("@") == std::string::npos) {
                result.addWarning("*MAT_ELASTIC: Cannot parse density (RO): " + fields[1]);
            }
        }
    }

    // Validate E (Young's modulus) - must be positive
    try {
        double e = std::stod(fields[2]);
        if (e <= 0) {
            result.addError("*MAT_ELASTIC: Young's modulus (E) must be positive, got " + fields[2]);
        }
    } catch (...) {
        if (fields[2].find("@") == std::string::npos) {
            result.addWarning("*MAT_ELASTIC: Cannot parse Young's modulus (E): " + fields[2]);
        }
    }

    // Validate PR (Poisson's ratio) - must be in (0, 0.5)
    try {
        double pr = std::stod(fields[3]);
        if (pr <= 0 || pr >= 0.5) {
            result.addError("*MAT_ELASTIC: Poisson's ratio (PR) must be in range (0, 0.5), got " + fields[3]);
        }
    } catch (...) {
        if (fields[3].find("@") == std::string::npos) {
            result.addWarning("*MAT_ELASTIC: Cannot parse Poisson's ratio (PR): " + fields[3]);
        }
    }
}

void MaterialCardValidator::validateCohesiveMixedMode(
    const std::vector<std::string>& lines, ValidationResult& result) {

    // Find data lines
    std::vector<int> dataLineIndices;
    bool afterKeyword = false;
    for (size_t i = 0; i < lines.size(); ++i) {
        if (isKeywordLine(lines[i])) {
            afterKeyword = true;
            continue;
        }
        if (afterKeyword && !isCommentLine(lines[i]) && !isBlankLine(lines[i])) {
            dataLineIndices.push_back(static_cast<int>(i));
        }
    }

    if (dataLineIndices.size() < 2) {
        result.addError("*MAT_COHESIVE_MIXED_MODE: Expected at least 2 data lines (Card 1 and Card 2)");
        return;
    }

    // Card 1: MID, RO, ROFLG, INTFAIL
    auto card1 = parseDataLine(lines[dataLineIndices[0]]);
    if (card1.size() < 4) {
        result.addWarning("*MAT_COHESIVE_MIXED_MODE Card 1: Expected 4 fields, found " +
                         std::to_string(card1.size()));
    }

    // Card 2: EN, ET, GNC, GTC, XMU, T, S
    auto card2 = parseDataLine(lines[dataLineIndices[1]]);
    if (card2.size() < 7) {
        result.addWarning("*MAT_COHESIVE_MIXED_MODE Card 2: Expected 7 fields, found " +
                         std::to_string(card2.size()));
    } else {
        // Validate EN, ET (cohesive stiffness) - must be positive
        try {
            double en = std::stod(card2[0]);
            if (en <= 0) {
                result.addError("*MAT_COHESIVE_MIXED_MODE: Normal stiffness (EN) must be positive");
            }
        } catch (...) {}

        try {
            double et = std::stod(card2[1]);
            if (et <= 0) {
                result.addError("*MAT_COHESIVE_MIXED_MODE: Tangential stiffness (ET) must be positive");
            }
        } catch (...) {}
    }
}

void MaterialCardValidator::validatePlasticKinematic(
    const std::vector<std::string>& lines, ValidationResult& result) {

    // Find first data line
    int dataLineIdx = -1;
    bool afterKeyword = false;
    for (size_t i = 0; i < lines.size(); ++i) {
        if (isKeywordLine(lines[i])) {
            afterKeyword = true;
            continue;
        }
        if (afterKeyword && !isCommentLine(lines[i]) && !isBlankLine(lines[i])) {
            dataLineIdx = static_cast<int>(i);
            break;
        }
    }

    if (dataLineIdx < 0) {
        result.addError("*MAT_PLASTIC_KINEMATIC: No data line found");
        return;
    }

    auto fields = parseDataLine(lines[dataLineIdx]);

    // Expected: MID, RO, E, PR, SIGY, ETAN, ...
    if (fields.size() < 5) {
        result.addWarning("*MAT_PLASTIC_KINEMATIC: Expected at least 5 fields (MID, RO, E, PR, SIGY)");
        return;
    }

    // Validate E, PR (same as elastic)
    try {
        double e = std::stod(fields[2]);
        if (e <= 0) {
            result.addError("*MAT_PLASTIC_KINEMATIC: Young's modulus (E) must be positive");
        }
    } catch (...) {}

    try {
        double pr = std::stod(fields[3]);
        if (pr <= 0 || pr >= 0.5) {
            result.addError("*MAT_PLASTIC_KINEMATIC: Poisson's ratio (PR) must be in range (0, 0.5)");
        }
    } catch (...) {}

    // Validate SIGY (yield stress) - must be positive
    try {
        double sigy = std::stod(fields[4]);
        if (sigy <= 0) {
            result.addError("*MAT_PLASTIC_KINEMATIC: Yield stress (SIGY) must be positive");
        }
    } catch (...) {}
}

std::vector<std::string> MaterialCardValidator::parseDataLine(const std::string& line) const {
    std::vector<std::string> fields;
    std::istringstream iss(line);
    std::string field;

    while (iss >> field) {
        // Skip inline comments
        if (field[0] == '$') break;
        fields.push_back(field);
    }

    return fields;
}

bool MaterialCardValidator::isCommentLine(const std::string& line) const {
    for (char c : line) {
        if (std::isspace(static_cast<unsigned char>(c))) continue;
        return (c == '$');
    }
    return false;
}

bool MaterialCardValidator::isBlankLine(const std::string& line) const {
    return std::all_of(line.begin(), line.end(),
                      [](unsigned char c) { return std::isspace(c); });
}

} // namespace KooRemapper
