#ifndef MATERIALCARDVALIDATOR_H
#define MATERIALCARDVALIDATOR_H

#include <string>
#include <vector>

namespace KooRemapper {

class MaterialCardValidator {
public:
    struct ValidationResult {
        bool isValid;
        std::vector<std::string> errors;
        std::vector<std::string> warnings;

        void addError(const std::string& msg) {
            errors.push_back(msg);
            isValid = false;
        }

        void addWarning(const std::string& msg) {
            warnings.push_back(msg);
        }

        bool hasIssues() const {
            return !errors.empty() || !warnings.empty();
        }
    };

    // Main validation function
    ValidationResult validate(const std::string& materialCard, bool checkPlaceholder = true);

private:
    // Check if line is a valid LS-DYNA keyword
    bool isKeywordLine(const std::string& line) const;

    // Extract keyword type (e.g., "MAT_ELASTIC")
    std::string extractKeyword(const std::string& line) const;

    // Validate specific material types
    void validateElastic(const std::vector<std::string>& lines, ValidationResult& result);
    void validateCohesiveMixedMode(const std::vector<std::string>& lines, ValidationResult& result);
    void validatePlasticKinematic(const std::vector<std::string>& lines, ValidationResult& result);

    // Check field count and values
    bool checkFieldCount(const std::string& line, int expected, ValidationResult& result);
    bool checkPositiveValue(double value, const std::string& fieldName, ValidationResult& result);
    bool checkRange(double value, double min, double max, const std::string& fieldName, ValidationResult& result);

    // Parse data line (skip comments)
    std::vector<std::string> parseDataLine(const std::string& line) const;
    bool isCommentLine(const std::string& line) const;
    bool isBlankLine(const std::string& line) const;
};

} // namespace KooRemapper

#endif // MATERIALCARDVALIDATOR_H
