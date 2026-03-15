#include "parser/KFileReader.h"
#include "core/Platform.h"
#include <sstream>
#include <algorithm>
#include <cctype>
#include <stdexcept>
#include <cstdlib>
#include <iostream>

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

    std::ifstream file(filename, std::ios::binary);
    if (!file.is_open()) {
        errorMessage_ = "Cannot open file: " + filename;
        throw std::runtime_error(errorMessage_);
    }

    // Get file size for progress reporting
    file.seekg(0, std::ios::end);
    fileSize_ = file.tellg();
    file.seekg(0, std::ios::beg);

    // Skip UTF-8 BOM if present (0xEF 0xBB 0xBF)
    char bom[3];
    file.read(bom, 3);
    if (!(bom[0] == '\xEF' && bom[1] == '\xBB' && bom[2] == '\xBF')) {
        // No BOM, seek back to beginning
        file.seekg(0, std::ios::beg);
    }

    if (!parseFile(file)) {
        throw std::runtime_error(errorMessage_);
    }

    file.close();
    return std::move(mesh_);
}

bool KFileReader::parseFile(std::ifstream& file) {
    std::string line;

    while (true) {
        if (!std::getline(file, line)) break;
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

            // Support both regular and _TITLE variants (e.g., *NODE, *PART_TITLE)
            // Skip metadata keywords that don't need processing
            if (currentKeyword_ == "KEYWORD" || currentKeyword_ == "TITLE") {
                // These are file metadata, skip to next keyword
                continue;
            }
            else if (currentKeyword_ == "NODE") {
                if (!parseNodeSection(file)) {
                    return false;
                }
            }
            else if (currentKeyword_ == "ELEMENT_SOLID" || currentKeyword_ == "ELEMENT_SOLID_TITLE") {
                if (!parseElementSolidSection(file)) {
                    return false;
                }
            }
            else if (currentKeyword_ == "PART" || currentKeyword_ == "PART_TITLE") {
                if (!parsePartSection(file)) {
                    return false;
                }
            }
            else if (currentKeyword_ == "MAT_ELASTIC" || currentKeyword_ == "MAT_ELASTIC_TITLE" ||
                     currentKeyword_ == "MAT_001" || currentKeyword_ == "MAT_001_TITLE") {
                if (!parseMatElasticSection(file)) {
                    return false;
                }
            }
            else if (currentKeyword_ == "MAT_PIECEWISE_LINEAR_PLASTICITY" ||
                     currentKeyword_ == "MAT_PIECEWISE_LINEAR_PLASTICITY_TITLE" ||
                     currentKeyword_ == "MAT_024" || currentKeyword_ == "MAT_024_TITLE") {
                if (!parseMatPlasticSection(file)) {
                    return false;
                }
            }
            else if (currentKeyword_ == "MAT_RIGID" || currentKeyword_ == "MAT_RIGID_TITLE" ||
                     currentKeyword_ == "MAT_020" || currentKeyword_ == "MAT_020_TITLE") {
                if (!parseMatRigidSection(file)) {
                    return false;
                }
            }
            else if (currentKeyword_ == "SECTION_SOLID" || currentKeyword_ == "SECTION_SOLID_TITLE") {
                // Skip section solid for now (just consume the data lines)
                skipDataLines(file, 2);  // Usually 2 data lines
            }
            else if (currentKeyword_ == "END") {
                break;  // End of file
            }
            else {
                // Unknown keyword - skip until next keyword
                // This handles *SET_SEGMENT, *DEFINE_CURVE, *BOUNDARY_*, etc.
                skipToNextKeyword(file);
            }
        }

        reportProgress(file.tellg());
    }

    return true;
}

bool KFileReader::parseNodeSection(std::ifstream& file) {
    std::string line;
    std::streampos lastPos;
    int nodeCount = 0;
    int skippedLines = 0;


    while (true) {
        lastPos = file.tellg();  // Save position BEFORE reading line
        if (!std::getline(file, line)) break;

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

        // Check for new keyword (end of NODE section)
        if (isKeywordLine(line)) {
            file.seekg(lastPos);  // Go back to re-read keyword (lastPos is position BEFORE this line)
            currentLine_--;
            return true;
        }

        // Parse node data
        // LS-DYNA format: nid, x, y, z [, tc, rc] (can be fixed or free format)
        // Fixed format: I8, 3E16.0, [2I8] (nid=8chars, x/y/z=16chars each, tc/rc=8chars each optional)
        // Minimum length for fixed format: 8 + 16 + 16 + 16 = 56 chars (without tc/rc)
        // With tc/rc: 56 + 8 + 8 = 72 chars
        bool parsed = false;
        try {
            // Try free format first (comma or space separated)
            // This handles most real-world k-files where data is space-separated
            auto tokens = tokenize(line);
            if (tokens.size() >= 4) {
                int nid = parseInt(tokens[0]);
                double x = parseDouble(tokens[1]);
                double y = parseDouble(tokens[2]);
                double z = parseDouble(tokens[3]);
                // tc and rc (tokens[4], tokens[5]) are ignored if present

                if (nid > 0) {
                    mesh_.addNode(nid, x, y, z);
                    nodeCount++;
                    parsed = true;

                    continue;
                }
            }

            // Fallback to strict fixed format (for packed data without spaces)
            // Fixed format has 8-char ID, then 16-char coordinate fields
            // Coordinates may not have spaces between them (e.g., "-1.0e+00-2.0e+00")
            if (!parsed && line.length() >= 56) {
                // Standard fixed format: I8, 3E16.0, [2I8 for tc, rc]
                int nid = parseInt(line.substr(0, 8));
                double x = parseDouble(line.substr(8, 16));
                double y = parseDouble(line.substr(24, 16));
                double z = parseDouble(line.substr(40, 16));
                // tc and rc at positions 56-64 and 64-72 are ignored (optional)

                if (nid > 0) {
                    mesh_.addNode(nid, x, y, z);
                    nodeCount++;
                    parsed = true;
                }
            }

            if (!parsed) {
                skippedLines++;
            }
        }
        catch (const std::exception& e) {
            errorMessage_ = "Error parsing node at line " + std::to_string(currentLine_) +
                          ": " + e.what();
            return false;
        }

        reportProgress(file.tellg());
    }

    return true;
}

bool KFileReader::parseElementSolidSection(std::ifstream& file) {
    std::string line;
    std::streampos lastPos;
    int elementCount = 0;


    while (true) {
        lastPos = file.tellg();  // Save position BEFORE reading line
        if (!std::getline(file, line)) break;

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

        // Check for new keyword
        if (isKeywordLine(line)) {
            file.seekg(lastPos);  // lastPos is position BEFORE this line
            file.clear();  // Clear any stream state flags
            currentLine_--;
            return true;
        }

        // Parse element data
        // LS-DYNA supports two formats:
        // Format 1 (single line): eid, pid, n1, n2, n3, n4, n5, n6, n7, n8
        // Format 2 (two lines, 10-node):
        //   Line 1: eid, pid
        //   Line 2: n1, n2, n3, n4, n5, n6, n7, n8, n9, n10
        //   For HEX8: n9=n10=0
        try {
            auto tokens = tokenize(line);

            // Check if this is Format 1 (single line with 10+ tokens)
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
                elementCount++;
            }
            // Check if this is Format 2 (two lines: eid/pid on first line)
            // First line has only 2-3 tokens (eid, pid, [optional])
            else if (tokens.size() >= 2 && tokens.size() <= 3) {
                // First line: eid, pid (may be free or fixed format)
                int eid = parseInt(tokens[0]);
                int pid = parseInt(tokens[1]);

                if (eid <= 0) {
                    continue;
                }

                // Read second line for node IDs
                std::string nodeLine;
                std::streampos nodeLinePos;

                while (true) {
                    nodeLinePos = file.tellg();  // Save position BEFORE reading
                    if (!std::getline(file, nodeLine)) break;
                    currentLine_++;
                    linesProcessed_++;

                    // Normalize line endings
                    if (!nodeLine.empty() && nodeLine.back() == '\r') {
                        nodeLine.pop_back();
                    }

                    // Skip comment lines and empty lines
                    if (isCommentLine(nodeLine) || nodeLine.empty()) {
                        continue;
                    }

                    // Got a non-comment, non-empty line
                    break;
                }

                // Check if we hit a keyword instead of node data
                if (isKeywordLine(nodeLine)) {
                    // nodeLinePos points to position BEFORE nodeLine was read
                    file.seekg(nodeLinePos);
                    currentLine_--;
                    return true;
                }

                if (nodeLine.empty()) {
                    // EOF reached
                    continue;
                }

                // Try fixed format first (8-char fields, nodes may be packed without spaces)
                // Node line: n1-n10 in 8-char fields = 80 chars, but we only need first 8 nodes
                if (nodeLine.length() >= 64) {
                    std::array<int, 8> nodeIds;
                    for (int i = 0; i < 8; ++i) {
                        nodeIds[i] = parseInt(nodeLine.substr(i * 8, 8));
                    }

                    Element elem(eid, pid, nodeIds);
                    // Detect TET4: n5=n6=n7=n8=n4 (LS-DYNA convention)
                    if (nodeIds[4] == nodeIds[3] && nodeIds[5] == nodeIds[3] &&
                        nodeIds[6] == nodeIds[3] && nodeIds[7] == nodeIds[3]) {
                        elem.type = ElementType::TET4;
                    }
                    mesh_.addElement(elem);
                    elementCount++;
                }
                else {
                    // Try free format
                    auto nodeTokens = tokenize(nodeLine);
                    if (nodeTokens.size() >= 8) {
                        std::array<int, 8> nodeIds;
                        for (int i = 0; i < 8; ++i) {
                            nodeIds[i] = parseInt(nodeTokens[i]);
                        }

                        Element elem(eid, pid, nodeIds);
                        if (nodeIds[4] == nodeIds[3] && nodeIds[5] == nodeIds[3] &&
                            nodeIds[6] == nodeIds[3] && nodeIds[7] == nodeIds[3]) {
                            elem.type = ElementType::TET4;
                        }
                        mesh_.addElement(elem);
                        elementCount++;
                    }
                }
                // After reading two-line element, continue to next iteration
                // This ensures we don't fall through to other parsing cases
                continue;
            }
            else if (line.length() >= 80) {
                // Try fixed format single line (8-character fields)
                // Format: eid(8) + pid(8) + n1-n8(8*8=64) = 80 chars
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
                elementCount++;
            }
        }
        catch (const std::exception& e) {
            errorMessage_ = "Error parsing element at line " + std::to_string(currentLine_) +
                          ": " + e.what();
            return false;
        }

        reportProgress(file.tellg());
    }

    return true;
}

bool KFileReader::parsePartSection(std::ifstream& file) {
    std::string line;
    std::streampos lastPos;
    bool foundData = false;
    bool readTitle = false;
    std::string partTitle;

    // *PART format (with title):
    // Line 1: title (text, e.g., "Flex-Dummy")
    // Line 2: pid, secid, mid, eosid, hgid, grav, adpopt, tmid

    int pid = 0, secid = 0, mid = 0;

    while (true) {
        lastPos = file.tellg();  // Save position BEFORE reading line
        if (!std::getline(file, line)) break;

        currentLine_++;
        linesProcessed_++;

        // Normalize line endings
        if (!line.empty() && line.back() == '\r') {
            line.pop_back();
        }

        // Skip empty lines
        if (line.empty()) {
            continue;
        }

        // Skip comment lines
        if (isCommentLine(line)) {
            continue;
        }

        // Check for new keyword (end of PART section)
        if (isKeywordLine(line)) {
            file.seekg(lastPos);
            currentLine_--;
            return true;
        }

        // First non-comment line is the title - read it
        if (!readTitle) {
            partTitle = trim(line);
            readTitle = true;
            continue;
        }

        // Parse part data (second non-comment line)
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
                mesh_.addPart(pid, secid, mid, partTitle);
                foundData = true;
            }
        }
        catch (const std::exception& e) {
            // Non-fatal, just skip
        }

        // Only read one data line per *PART card
        if (foundData) {
            break;
        }
    }

    return true;
}

bool KFileReader::parseMatElasticSection(std::ifstream& file) {
    std::string line;
    std::streampos lastPos;
    int dataLineCount = 0;

    // *MAT_ELASTIC format:
    // Card 1: mid, ro, e, pr, da, db, not used, not used
    // (mid=material ID, ro=density, e=Young's modulus, pr=Poisson's ratio)

    int mid = 0;
    double density = 0, E = 0, nu = 0;

    while (true) {
        lastPos = file.tellg();
        if (!std::getline(file, line)) break;

        currentLine_++;
        linesProcessed_++;

        // Normalize line endings
        if (!line.empty() && line.back() == '\r') {
            line.pop_back();
        }

        // Skip empty lines
        if (line.empty()) {
            continue;
        }

        // Skip comment lines
        if (isCommentLine(line)) {
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

        dataLineCount++;

        // Only need first data line for *MAT_ELASTIC
        if (dataLineCount >= 1) {
            break;
        }
    }

    return true;
}

bool KFileReader::parseMatPlasticSection(std::ifstream& file) {
    std::string line;
    std::streampos lastPos;
    int dataLineCount = 0;

    // *MAT_PIECEWISE_LINEAR_PLASTICITY format (4 cards):
    // Card 1: mid, ro, e, pr, sigy, etan, fail, tdel
    // Card 2: c, p, lcss, lcsr, vp, lcf, (not used), (not used)
    // Card 3: eps1, eps2, eps3, eps4, eps5, eps6, eps7, eps8
    // Card 4: es1, es2, es3, es4, es5, es6, es7, es8
    // We only need Card 1 for basic material properties

    int mid = 0;
    double density = 0, E = 0, nu = 0;

    while (true) {
        lastPos = file.tellg();
        if (!std::getline(file, line)) break;

        currentLine_++;
        linesProcessed_++;

        // Normalize line endings
        if (!line.empty() && line.back() == '\r') {
            line.pop_back();
        }

        // Skip empty lines
        if (line.empty()) {
            continue;
        }

        // Skip comment lines
        if (isCommentLine(line)) {
            continue;
        }

        // Check for new keyword
        if (isKeywordLine(line)) {
            file.seekg(lastPos);
            currentLine_--;
            return true;
        }

        // Parse first card (contains mid, ro, e, pr)
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
                    // Fixed format: 10-character fields
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

        dataLineCount++;

        // Read all 4 data lines for MAT_PIECEWISE_LINEAR_PLASTICITY
        if (dataLineCount >= 4) {
            break;
        }
    }

    return true;
}

bool KFileReader::parseMatRigidSection(std::ifstream& file) {
    std::string line;
    std::streampos lastPos;
    int dataLineCount = 0;

    // *MAT_RIGID format (3 cards):
    // Card 1: mid, ro, e, pr, n, couple, m, alias
    // Card 2: cmo, con1, con2
    // Card 3: lco or a1, a2, a3, v1, v2, v3
    // We only need Card 1 for basic material properties

    int mid = 0;
    double density = 0, E = 0, nu = 0;

    while (true) {
        lastPos = file.tellg();
        if (!std::getline(file, line)) break;

        currentLine_++;
        linesProcessed_++;

        // Normalize line endings
        if (!line.empty() && line.back() == '\r') {
            line.pop_back();
        }

        // Skip empty lines
        if (line.empty()) {
            continue;
        }

        // Skip comment lines
        if (isCommentLine(line)) {
            continue;
        }

        // Check for new keyword
        if (isKeywordLine(line)) {
            file.seekg(lastPos);
            currentLine_--;
            return true;
        }

        // Parse first card (contains mid, ro, e, pr)
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
                    // Fixed format: 10-character fields
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

        dataLineCount++;

        // Read all 3 data lines for MAT_RIGID
        if (dataLineCount >= 3) {
            break;
        }
    }

    return true;
}

void KFileReader::skipToNextKeyword(std::ifstream& file) {
    std::string line;
    std::streampos lastPos;

    while (true) {
        lastPos = file.tellg();
        if (!std::getline(file, line)) break;

        currentLine_++;

        // Normalize line endings (critical for cross-platform compatibility)
        if (!line.empty() && line.back() == '\r') {
            line.pop_back();
        }

        // Skip empty lines and comments
        if (line.empty() || isCommentLine(line)) {
            continue;
        }

        if (isKeywordLine(line)) {
            // Seek back to re-read the keyword line
            file.seekg(lastPos);
            currentLine_--;
            break;
        }
    }
}

void KFileReader::skipDataLines(std::ifstream& file, int count) {
    std::string line;
    std::streampos lastPos;
    int skipped = 0;

    while (skipped < count) {
        lastPos = file.tellg();
        if (!std::getline(file, line)) break;

        currentLine_++;

        // Normalize line endings
        if (!line.empty() && line.back() == '\r') {
            line.pop_back();
        }

        // Skip empty lines and comments (don't count them)
        if (line.empty() || isCommentLine(line)) {
            continue;
        }

        // Check for new keyword (end of section)
        if (isKeywordLine(line)) {
            file.seekg(lastPos);
            currentLine_--;
            return;
        }

        skipped++;
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
