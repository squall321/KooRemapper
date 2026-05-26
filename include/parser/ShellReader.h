#pragma once

#include "core/ShellMesh.h"
#include <string>
#include <fstream>
#include <vector>
#include <functional>

// Knowledge graph (lat.md):
//   @lat: [[modules/parser]]

namespace KooRemapper {

/**
 * Parser for LS-DYNA keyword (.k) files containing shell elements
 *
 * Reads *NODE, *ELEMENT_SHELL, and *PART keywords to build a ShellMesh.
 * Designed for reading bent reference shell meshes for shell-based mapping.
 */
class ShellReader {
public:
    using ProgressCallback = std::function<void(int percent)>;

    ShellReader();
    ~ShellReader() = default;

    /**
     * Read a k-file and return a ShellMesh
     * @param filename Path to the k-file
     * @return Parsed shell mesh
     * @throws std::runtime_error on parse errors
     */
    ShellMesh readFile(const std::string& filename);

    void setProgressCallback(ProgressCallback callback) { progressCallback_ = callback; }
    const std::string& getErrorMessage() const { return errorMessage_; }
    int getLinesProcessed() const { return linesProcessed_; }

private:
    ShellMesh mesh_;
    std::string errorMessage_;
    std::string currentKeyword_;
    int currentLine_;
    int linesProcessed_;
    long fileSize_;
    ProgressCallback progressCallback_;

    bool parseFile(std::ifstream& file);
    bool parseNodeSection(std::ifstream& file);
    bool parseElementShellSection(std::ifstream& file);
    bool parsePartSection(std::ifstream& file);
    void skipToNextKeyword(std::ifstream& file);

    // Helpers (same patterns as KFileReader)
    bool isKeywordLine(const std::string& line) const;
    bool isCommentLine(const std::string& line) const;
    std::string extractKeyword(const std::string& line) const;
    std::vector<std::string> tokenize(const std::string& line) const;
    std::string trim(const std::string& str) const;
    double parseDouble(const std::string& str) const;
    int parseInt(const std::string& str) const;
    void reportProgress(std::streampos currentPos);
};

} // namespace KooRemapper
