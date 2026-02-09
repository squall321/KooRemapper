#include "parser/ShellReader.h"
#include <sstream>
#include <algorithm>
#include <cctype>
#include <stdexcept>
#include <cstdlib>

namespace KooRemapper {

ShellReader::ShellReader()
    : currentLine_(0)
    , linesProcessed_(0)
    , fileSize_(0)
    , progressCallback_(nullptr)
{}

ShellMesh ShellReader::readFile(const std::string& filename) {
    mesh_.clear();
    errorMessage_.clear();
    currentLine_ = 0;
    linesProcessed_ = 0;

    std::ifstream file(filename, std::ios::binary);
    if (!file.is_open()) {
        errorMessage_ = "Cannot open file: " + filename;
        throw std::runtime_error(errorMessage_);
    }

    file.seekg(0, std::ios::end);
    fileSize_ = static_cast<long>(file.tellg());
    file.seekg(0, std::ios::beg);

    // Skip UTF-8 BOM
    char bom[3];
    file.read(bom, 3);
    if (!(bom[0] == '\xEF' && bom[1] == '\xBB' && bom[2] == '\xBF')) {
        file.seekg(0, std::ios::beg);
    }

    if (!parseFile(file)) {
        throw std::runtime_error(errorMessage_);
    }

    file.close();

    // Build connectivity after parsing
    mesh_.buildConnectivity();

    return std::move(mesh_);
}

bool ShellReader::parseFile(std::ifstream& file) {
    std::string line;

    while (true) {
        if (!std::getline(file, line)) break;
        currentLine_++;
        linesProcessed_++;

        if (!line.empty() && line.back() == '\r') {
            line.pop_back();
        }

        if (line.empty() || isCommentLine(line)) continue;

        if (isKeywordLine(line)) {
            currentKeyword_ = extractKeyword(line);

            if (currentKeyword_ == "KEYWORD" || currentKeyword_ == "TITLE") {
                continue;
            }
            else if (currentKeyword_ == "NODE") {
                if (!parseNodeSection(file)) return false;
            }
            else if (currentKeyword_ == "ELEMENT_SHELL" ||
                     currentKeyword_ == "ELEMENT_SHELL_TITLE") {
                if (!parseElementShellSection(file)) return false;
            }
            else if (currentKeyword_ == "PART" || currentKeyword_ == "PART_TITLE") {
                if (!parsePartSection(file)) return false;
            }
            else if (currentKeyword_ == "END") {
                break;
            }
            else {
                skipToNextKeyword(file);
            }
        }

        reportProgress(file.tellg());
    }

    return true;
}

bool ShellReader::parseNodeSection(std::ifstream& file) {
    std::string line;
    std::streampos lastPos;

    while (true) {
        lastPos = file.tellg();
        if (!std::getline(file, line)) break;
        currentLine_++;
        linesProcessed_++;

        if (!line.empty() && line.back() == '\r') line.pop_back();
        if (line.empty() || isCommentLine(line)) continue;

        if (isKeywordLine(line)) {
            file.seekg(lastPos);
            currentLine_--;
            return true;
        }

        try {
            // Try free format first
            auto tokens = tokenize(line);
            if (tokens.size() >= 4) {
                int nid = parseInt(tokens[0]);
                double x = parseDouble(tokens[1]);
                double y = parseDouble(tokens[2]);
                double z = parseDouble(tokens[3]);
                if (nid > 0) {
                    mesh_.addNode(nid, x, y, z);
                    continue;
                }
            }

            // Fallback: fixed format (I8, 3E16.0)
            if (line.length() >= 56) {
                int nid = parseInt(line.substr(0, 8));
                double x = parseDouble(line.substr(8, 16));
                double y = parseDouble(line.substr(24, 16));
                double z = parseDouble(line.substr(40, 16));
                if (nid > 0) {
                    mesh_.addNode(nid, x, y, z);
                }
            }
        } catch (...) {
            // Skip unparseable lines
        }
    }
    return true;
}

bool ShellReader::parseElementShellSection(std::ifstream& file) {
    std::string line;
    std::streampos lastPos;
    bool isTitleFormat = (currentKeyword_ == "ELEMENT_SHELL_TITLE");

    while (true) {
        lastPos = file.tellg();
        if (!std::getline(file, line)) break;
        currentLine_++;
        linesProcessed_++;

        if (!line.empty() && line.back() == '\r') line.pop_back();
        if (line.empty() || isCommentLine(line)) continue;

        if (isKeywordLine(line)) {
            file.seekg(lastPos);
            currentLine_--;
            return true;
        }

        // If TITLE variant, skip the title line
        if (isTitleFormat) {
            // Title line - skip it, read data line next
            lastPos = file.tellg();
            if (!std::getline(file, line)) break;
            currentLine_++;
            linesProcessed_++;
            if (!line.empty() && line.back() == '\r') line.pop_back();

            if (isKeywordLine(line)) {
                file.seekg(lastPos);
                currentLine_--;
                return true;
            }
        }

        try {
            // *ELEMENT_SHELL format: EID PID N1 N2 N3 N4 [N5 N6 N7 N8]
            // Fixed format: 10-char fields
            auto tokens = tokenize(line);
            if (tokens.size() >= 6) {
                int eid = parseInt(tokens[0]);
                int pid = parseInt(tokens[1]);
                int n1 = parseInt(tokens[2]);
                int n2 = parseInt(tokens[3]);
                int n3 = parseInt(tokens[4]);
                int n4 = parseInt(tokens[5]);

                if (eid > 0 && n1 > 0 && n2 > 0 && n3 > 0 && n4 > 0) {
                    std::array<int, 4> nodeIds = {n1, n2, n3, n4};
                    mesh_.addElement(eid, pid, nodeIds);
                    continue;
                }
            }

            // Fallback: fixed format (8I10 = 10-char fields)
            if (line.length() >= 60) {
                int eid = parseInt(line.substr(0, 10));
                int pid = parseInt(line.substr(10, 10));
                int n1 = parseInt(line.substr(20, 10));
                int n2 = parseInt(line.substr(30, 10));
                int n3 = parseInt(line.substr(40, 10));
                int n4 = parseInt(line.substr(50, 10));

                if (eid > 0 && n1 > 0 && n2 > 0 && n3 > 0 && n4 > 0) {
                    std::array<int, 4> nodeIds = {n1, n2, n3, n4};
                    mesh_.addElement(eid, pid, nodeIds);
                }
            }
        } catch (...) {
            // Skip unparseable lines
        }
    }
    return true;
}

bool ShellReader::parsePartSection(std::ifstream& file) {
    std::string line;
    std::streampos lastPos;
    bool isTitleFormat = (currentKeyword_ == "PART_TITLE");

    while (true) {
        // Read title line
        lastPos = file.tellg();
        if (!std::getline(file, line)) break;
        currentLine_++;
        linesProcessed_++;

        if (!line.empty() && line.back() == '\r') line.pop_back();
        if (line.empty() || isCommentLine(line)) continue;

        if (isKeywordLine(line)) {
            file.seekg(lastPos);
            currentLine_--;
            return true;
        }

        // This is the title line (or data line for non-title format)
        std::string titleLine = line;

        // Read data line: PID SECID MID ...
        lastPos = file.tellg();
        if (!std::getline(file, line)) break;
        currentLine_++;
        linesProcessed_++;

        if (!line.empty() && line.back() == '\r') line.pop_back();

        if (isKeywordLine(line)) {
            file.seekg(lastPos);
            currentLine_--;
            return true;
        }

        try {
            auto tokens = tokenize(line);
            if (tokens.size() >= 3) {
                int pid = parseInt(tokens[0]);
                // tokens[1] = SECID, tokens[2] = MID
                if (pid > 0) {
                    // We don't need material info for shell mapping, just record the part
                    // (ShellMesh doesn't have a parts_ map, but we keep it for future use)
                }
            }
        } catch (...) {
            // Skip
        }
    }
    return true;
}

void ShellReader::skipToNextKeyword(std::ifstream& file) {
    std::string line;
    std::streampos lastPos;

    while (true) {
        lastPos = file.tellg();
        if (!std::getline(file, line)) break;
        currentLine_++;
        linesProcessed_++;

        if (!line.empty() && line.back() == '\r') line.pop_back();

        if (isKeywordLine(line)) {
            file.seekg(lastPos);
            currentLine_--;
            return;
        }
    }
}

// --- Helper methods (same patterns as KFileReader) ---

bool ShellReader::isKeywordLine(const std::string& line) const {
    if (line.empty()) return false;
    return line[0] == '*' && line.length() > 1 && std::isalpha(line[1]);
}

bool ShellReader::isCommentLine(const std::string& line) const {
    if (line.empty()) return false;
    return line[0] == '$';
}

std::string ShellReader::extractKeyword(const std::string& line) const {
    std::string keyword;
    for (size_t i = 1; i < line.length(); ++i) {
        char c = line[i];
        if (std::isalnum(c) || c == '_' || c == '-') {
            keyword += static_cast<char>(std::toupper(c));
        } else {
            break;
        }
    }
    return keyword;
}

std::vector<std::string> ShellReader::tokenize(const std::string& line) const {
    std::vector<std::string> tokens;
    std::string token;

    for (char c : line) {
        if (c == ',' || c == ' ' || c == '\t') {
            if (!token.empty()) {
                tokens.push_back(token);
                token.clear();
            }
        } else {
            token += c;
        }
    }
    if (!token.empty()) tokens.push_back(token);

    return tokens;
}

std::string ShellReader::trim(const std::string& str) const {
    size_t start = str.find_first_not_of(" \t\r\n");
    if (start == std::string::npos) return "";
    size_t end = str.find_last_not_of(" \t\r\n");
    return str.substr(start, end - start + 1);
}

double ShellReader::parseDouble(const std::string& str) const {
    std::string s = trim(str);
    if (s.empty()) return 0.0;

    // Handle LS-DYNA exponential notation (1.0-3 means 1.0e-3)
    for (size_t i = 1; i < s.length(); ++i) {
        if ((s[i] == '-' || s[i] == '+') && s[i-1] != 'e' && s[i-1] != 'E' &&
            s[i-1] != 'd' && s[i-1] != 'D' && std::isdigit(s[i-1])) {
            s.insert(i, "e");
            break;
        }
    }

    // Replace D/d with E/e
    for (auto& c : s) {
        if (c == 'd' || c == 'D') c = 'e';
    }

    try {
        return std::stod(s);
    } catch (...) {
        return 0.0;
    }
}

int ShellReader::parseInt(const std::string& str) const {
    std::string s = trim(str);
    if (s.empty()) return 0;
    try {
        return std::stoi(s);
    } catch (...) {
        return 0;
    }
}

void ShellReader::reportProgress(std::streampos currentPos) {
    if (progressCallback_ && fileSize_ > 0) {
        int percent = static_cast<int>(100.0 * static_cast<double>(currentPos) / fileSize_);
        progressCallback_(std::min(percent, 100));
    }
}

} // namespace KooRemapper
