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
            else if (currentKeyword_ == "PART") {
                if (!parsePartSection(file)) {
                    return false;
                }
            }
            else if (currentKeyword_ == "MAT_ELASTIC" || currentKeyword_ == "MAT_001") {
                if (!parseMatElasticSection(file)) {
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

bool KFileReader::parsePartSection(std::ifstream& file) {
    std::string line;
    std::streampos lastPos = file.tellg();
    int dataLineCount = 0;  // Track data lines (skip comment lines)
    
    // *PART format:
    // $ heading (optional comment line)
    // pid, secid, mid, eosid, hgid, grav, adpopt, tmid
    
    int pid = 0, secid = 0, mid = 0;
    
    while (std::getline(file, line)) {
        currentLine_++;
        linesProcessed_++;
        
        // Normalize line endings
        if (!line.empty() && line.back() == '\r') {
            line.pop_back();
        }
        
        // Skip empty lines
        if (line.empty()) {
            lastPos = file.tellg();
            continue;
        }
        
        // Skip comment lines (but don't count as data)
        if (isCommentLine(line)) {
            lastPos = file.tellg();
            continue;
        }
        
        // Check for new keyword (end of PART section)
        if (isKeywordLine(line)) {
            file.seekg(lastPos);
            currentLine_--;
            return true;
        }
        
        // Parse part data (first non-comment data line)
        try {
            auto tokens = tokenize(line);
            if (tokens.size() >= 3) {
                pid = parseInt(tokens[0]);
                secid = parseInt(tokens[1]);
                mid = parseInt(tokens[2]);
            }
            else if (line.length() >= 24) {
                // Fixed format: 8-character fields
                pid = parseInt(line.substr(0, 8));
                secid = parseInt(line.substr(8, 8));
                mid = parseInt(line.substr(16, 8));
            }
            
            if (pid > 0) {
                mesh_.addPart(pid, secid, mid);
            }
        }
        catch (const std::exception& e) {
            // Non-fatal, just skip
        }
        
        lastPos = file.tellg();
        dataLineCount++;
        
        // Only read one data line per *PART card
        if (dataLineCount >= 1) {
            break;
        }
    }
    
    return true;
}

bool KFileReader::parseMatElasticSection(std::ifstream& file) {
    std::string line;
    std::streampos lastPos = file.tellg();
    int dataLineCount = 0;
    
    // *MAT_ELASTIC format:
    // Card 1: mid, ro, e, pr, da, db, not used, not used
    // (mid=material ID, ro=density, e=Young's modulus, pr=Poisson's ratio)
    
    int mid = 0;
    double density = 0, E = 0, nu = 0;
    
    while (std::getline(file, line)) {
        currentLine_++;
        linesProcessed_++;
        
        // Normalize line endings
        if (!line.empty() && line.back() == '\r') {
            line.pop_back();
        }
        
        // Skip empty lines
        if (line.empty()) {
            lastPos = file.tellg();
            continue;
        }
        
        // Skip comment lines
        if (isCommentLine(line)) {
            lastPos = file.tellg();
            continue;
        }
        
        // Check for new keyword
        if (isKeywordLine(line)) {
            file.seekg(lastPos);
            currentLine_--;
            return true;
        }
        
        // Parse material data (first data line contains the essential info)
        if (dataLineCount == 0) {
            try {
                auto tokens = tokenize(line);
                if (tokens.size() >= 4) {
                    mid = parseInt(tokens[0]);
                    density = parseDouble(tokens[1]);
                    E = parseDouble(tokens[2]);
                    nu = parseDouble(tokens[3]);
                }
                else if (line.length() >= 40) {
                    // Fixed format: 10-character fields typically
                    mid = parseInt(line.substr(0, 10));
                    density = parseDouble(line.substr(10, 10));
                    E = parseDouble(line.substr(20, 10));
                    nu = parseDouble(line.substr(30, 10));
                }
                
                if (mid > 0 && E > 0) {
                    mesh_.addMaterial(mid, E, nu, density);
                }
            }
            catch (const std::exception& e) {
                // Non-fatal, just skip
            }
        }
        
        lastPos = file.tellg();
        dataLineCount++;
        
        // Only need first data line for *MAT_ELASTIC
        if (dataLineCount >= 1) {
            break;
        }
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
