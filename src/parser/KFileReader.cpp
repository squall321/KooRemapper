#include "parser/KFileReader.h"
#include "core/Platform.h"
#include <sstream>
#include <algorithm>
#include <cctype>
#include <stdexcept>
#include <cstdlib>

namespace KooRemapper {

KFileReader::KFileReader()
    : currentLine_(0)
    , linesProcessed_(0)
    , fileSize_(0)
    , progressCallback_(nullptr)
{}

Mesh KFileReader::readFile(const std::string& filename) {
    mesh_.clear();
    errorMessage_.clear();
    currentLine_ = 0;
    linesProcessed_ = 0;

    std::ifstream file(filename);
    if (!file.is_open()) {
        errorMessage_ = "Cannot open file: " + filename;
        throw std::runtime_error(errorMessage_);
    }

    // Get file size for progress reporting
    file.seekg(0, std::ios::end);
    fileSize_ = file.tellg();
    file.seekg(0, std::ios::beg);

    if (!parseFile(file)) {
        throw std::runtime_error(errorMessage_);
    }

    file.close();
    return std::move(mesh_);
}

bool KFileReader::parseFile(std::ifstream& file) {
    std::string line;

    while (std::getline(file, line)) {
        currentLine_++;
        linesProcessed_++;

        // Normalize line endings
        if (!line.empty() && line.back() == '\r') {
            line.pop_back();
        }

        // Skip empty lines and comments
        if (line.empty() || isCommentLine(line)) {
            continue;
        }

        // Check for keyword
        if (isKeywordLine(line)) {
            currentKeyword_ = extractKeyword(line);

            if (currentKeyword_ == "NODE") {
                if (!parseNodeSection(file)) {
                    return false;
                }
            }
            else if (currentKeyword_ == "ELEMENT_SOLID") {
                if (!parseElementSolidSection(file)) {
                    return false;
                }
            }
            else if (currentKeyword_ == "END") {
                break;  // End of file
            }
            // Other keywords are skipped
        }

        reportProgress(file.tellg());
    }

    return true;
}

bool KFileReader::parseNodeSection(std::ifstream& file) {
    std::string line;
    std::streampos lastPos = file.tellg();

    while (std::getline(file, line)) {
        currentLine_++;
        linesProcessed_++;

        // Normalize line endings
        if (!line.empty() && line.back() == '\r') {
            line.pop_back();
        }

        // Skip empty lines and comments
        if (line.empty() || isCommentLine(line)) {
            lastPos = file.tellg();
            continue;
        }

        // Check for new keyword (end of NODE section)
        if (isKeywordLine(line)) {
            file.seekg(lastPos);  // Go back to re-read keyword
            currentLine_--;
            return true;
        }

        // Parse node data
        // LS-DYNA format: nid, x, y, z (can be fixed or free format)
        try {
            // Try free format first (comma or space separated)
            auto tokens = tokenize(line);
            if (tokens.size() >= 4) {
                int nid = parseInt(tokens[0]);
                double x = parseDouble(tokens[1]);
                double y = parseDouble(tokens[2]);
                double z = parseDouble(tokens[3]);

                mesh_.addNode(nid, x, y, z);
            }
            else if (line.length() >= 40) {
                // Try fixed format (8-character fields for ID, 16 for coordinates)
                // Standard: I8, 3E16.0
                int nid = parseInt(line.substr(0, 8));
                double x = parseDouble(line.substr(8, 16));
                double y = parseDouble(line.substr(24, 16));
                double z = parseDouble(line.substr(40, 16));

                mesh_.addNode(nid, x, y, z);
            }
        }
        catch (const std::exception& e) {
            errorMessage_ = "Error parsing node at line " + std::to_string(currentLine_) +
                          ": " + e.what();
            return false;
        }

        lastPos = file.tellg();
        reportProgress(lastPos);
    }

    return true;
}

bool KFileReader::parseElementSolidSection(std::ifstream& file) {
    std::string line;
    std::streampos lastPos = file.tellg();

    while (std::getline(file, line)) {
        currentLine_++;
        linesProcessed_++;

        // Normalize line endings
        if (!line.empty() && line.back() == '\r') {
            line.pop_back();
        }

        // Skip empty lines and comments
        if (line.empty() || isCommentLine(line)) {
            lastPos = file.tellg();
            continue;
        }

        // Check for new keyword
        if (isKeywordLine(line)) {
            file.seekg(lastPos);
            currentLine_--;
            return true;
        }

        // Parse element data
        // LS-DYNA format: eid, pid, n1, n2, n3, n4, n5, n6, n7, n8
        try {
            auto tokens = tokenize(line);
            if (tokens.size() >= 10) {
                int eid = parseInt(tokens[0]);
                int pid = parseInt(tokens[1]);
                std::array<int, 8> nodeIds;
                for (int i = 0; i < 8; ++i) {
                    nodeIds[i] = parseInt(tokens[2 + i]);
                }

                Element elem(eid, pid, nodeIds);
                // Detect TET4: n5=n6=n7=n8=n4 (LS-DYNA convention)
                if (nodeIds[4] == nodeIds[3] && nodeIds[5] == nodeIds[3] &&
                    nodeIds[6] == nodeIds[3] && nodeIds[7] == nodeIds[3]) {
                    elem.type = ElementType::TET4;
                }
                mesh_.addElement(elem);
            }
            else if (line.length() >= 80) {
                // Try fixed format (8-character fields)
                int eid = parseInt(line.substr(0, 8));
                int pid = parseInt(line.substr(8, 8));
                std::array<int, 8> nodeIds;
                for (int i = 0; i < 8; ++i) {
                    nodeIds[i] = parseInt(line.substr(16 + i * 8, 8));
                }

                Element elem(eid, pid, nodeIds);
                // Detect TET4: n5=n6=n7=n8=n4 (LS-DYNA convention)
                if (nodeIds[4] == nodeIds[3] && nodeIds[5] == nodeIds[3] &&
                    nodeIds[6] == nodeIds[3] && nodeIds[7] == nodeIds[3]) {
                    elem.type = ElementType::TET4;
                }
                mesh_.addElement(elem);
            }
        }
        catch (const std::exception& e) {
            errorMessage_ = "Error parsing element at line " + std::to_string(currentLine_) +
                          ": " + e.what();
            return false;
        }

        lastPos = file.tellg();
        reportProgress(lastPos);
    }

    return true;
}

void KFileReader::skipToNextKeyword(std::ifstream& file) {
    std::string line;
    while (std::getline(file, line)) {
        currentLine_++;
        if (isKeywordLine(line)) {
            // Seek back to re-read the keyword line
            file.seekg(-static_cast<int>(line.length()) - 1, std::ios::cur);
            currentLine_--;
            break;
        }
    }
}

bool KFileReader::isKeywordLine(const std::string& line) const {
    if (line.empty()) return false;
    return line[0] == '*' && line.length() > 1 && std::isalpha(line[1]);
}

bool KFileReader::isCommentLine(const std::string& line) const {
    if (line.empty()) return false;
    return line[0] == '$';
}

std::string KFileReader::extractKeyword(const std::string& line) const {
    if (line.empty() || line[0] != '*') return "";

    std::string keyword;
    for (size_t i = 1; i < line.length(); ++i) {
        char c = line[i];
        if (std::isalnum(c) || c == '_') {
            keyword += static_cast<char>(std::toupper(c));
        } else {
            break;
        }
    }
    return keyword;
}

std::vector<std::string> KFileReader::tokenize(const std::string& line) const {
    std::vector<std::string> tokens;
    std::string token;

    for (char c : line) {
        if (c == ',' || c == ' ' || c == '\t') {
            if (!token.empty()) {
                tokens.push_back(trim(token));
                token.clear();
            }
        } else {
            token += c;
        }
    }

    if (!token.empty()) {
        tokens.push_back(trim(token));
    }

    return tokens;
}

std::string KFileReader::trim(const std::string& str) const {
    size_t start = 0;
    size_t end = str.length();

    while (start < end && std::isspace(str[start])) {
        start++;
    }
    while (end > start && std::isspace(str[end - 1])) {
        end--;
    }

    return str.substr(start, end - start);
}

double KFileReader::parseDouble(const std::string& str) const {
    std::string trimmed = trim(str);
    if (trimmed.empty()) return 0.0;

    // Handle LS-DYNA format where 'D' or 'd' is used instead of 'E' for exponent
    std::string normalized = trimmed;
    std::replace(normalized.begin(), normalized.end(), 'D', 'E');
    std::replace(normalized.begin(), normalized.end(), 'd', 'e');

    try {
        return std::stod(normalized);
    }
    catch (...) {
        return 0.0;
    }
}

int KFileReader::parseInt(const std::string& str) const {
    std::string trimmed = trim(str);
    if (trimmed.empty()) return 0;

    try {
        return std::stoi(trimmed);
    }
    catch (...) {
        return 0;
    }
}

void KFileReader::reportProgress(std::streampos currentPos) {
    if (progressCallback_ && fileSize_ > 0) {
        int percent = static_cast<int>((static_cast<long>(currentPos) * 100) / fileSize_);
        progressCallback_(percent);
    }
}

} // namespace KooRemapper
