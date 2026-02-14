#pragma once

#include "core/Mesh.h"
#include <string>
#include <fstream>
#include <vector>
#include <functional>

namespace KooRemapper {

/**
 * Parser for LS-DYNA keyword (.k) files
 *
 * Supports:
 *   - *NODE
 *   - *ELEMENT_SOLID / *ELEMENT_TSHELL / *ELEMENT_SHELL
 *   - *PART (with material ID mapping)
 *   - *MAT_ELASTIC (001)
 *   - *MAT_PIECEWISE_LINEAR_PLASTICITY (024)
 *   - *MAT_RIGID (020)
 *   - *MAT_VISCOELASTIC (006) - uses gi (long-time shear modulus)
 *   - *END
 */
class KFileReader {
public:
    using ProgressCallback = std::function<void(int percent)>;

    KFileReader();
    ~KFileReader() = default;

    /**
     * Read a k-file and return the mesh
     * @param filename Path to the k-file
     * @return Parsed mesh
     * @throws std::runtime_error on parse errors
     */
    Mesh readFile(const std::string& filename);

    /**
     * Set progress callback
     */
    void setProgressCallback(ProgressCallback callback) {
        progressCallback_ = callback;
    }

    /**
     * Get last error message
     */
    const std::string& getErrorMessage() const { return errorMessage_; }

    /**
     * Get number of lines processed
     */
    int getLinesProcessed() const { return linesProcessed_; }

private:
    Mesh mesh_;
    std::string errorMessage_;
    std::string currentKeyword_;
    int currentLine_;
    int linesProcessed_;
    long fileSize_;
    ProgressCallback progressCallback_;
    std::vector<std::pair<int, std::string>> unsupportedMaterials_;  // (MID, keyword)

    // Parse methods
    bool parseFile(std::ifstream& file);
    bool parseNodeSection(std::ifstream& file);
    bool parseElementSolidSection(std::ifstream& file);
    bool parseElementShellSection(std::ifstream& file);
    bool parsePartSection(std::ifstream& file);
    bool parseMatElasticSection(std::ifstream& file);
    bool parseMatPlasticSection(std::ifstream& file);
    bool parseMatRigidSection(std::ifstream& file);
    bool parseMatViscoelasticSection(std::ifstream& file);
    bool parseMatMooneyRivlinSection(std::ifstream& file);
    bool parseSectionShellSection(std::ifstream& file);
    void skipToNextKeyword(std::ifstream& file);
    void skipDataLines(std::ifstream& file, int count);
    bool isMaterialKeyword(const std::string& keyword) const;
    bool isSupportedMaterial(const std::string& keyword) const;

    // Helper methods
    bool isKeywordLine(const std::string& line) const;
    bool isCommentLine(const std::string& line) const;
    std::string extractKeyword(const std::string& line) const;
    std::vector<std::string> tokenize(const std::string& line) const;
    std::vector<std::string> tokenizeFixed(const std::string& line, int fieldWidth = 10) const;
    std::string trim(const std::string& str) const;

    // Fixed-format parsing (LS-DYNA uses fixed column widths)
    double parseDouble(const std::string& str) const;
    int parseInt(const std::string& str) const;

    // Report progress
    void reportProgress(std::streampos currentPos);
};

} // namespace KooRemapper
