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
    i10_ = false;

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
                // Detect i10=y on *KEYWORD line (10-char integer fields)
                std::string upLine = line;
                for (auto& c : upLine) c = (char)std::toupper((unsigned char)c);
                if (upLine.find("I10") != std::string::npos) {
                    i10_ = true;
                }
                continue;
            }
            else if (currentKeyword_ == "NODE") {
                if (!parseNodeSection(file)) {
                    return false;
                }
            }
            else if (currentKeyword_ == "ELEMENT_SOLID" || currentKeyword_ == "ELEMENT_SOLID_TITLE" ||
                     currentKeyword_ == "ELEMENT_TSHELL" || currentKeyword_ == "ELEMENT_TSHELL_TITLE") {
                if (!parseElementSolidSection(file)) {
                    return false;
                }
            }
            else if (currentKeyword_ == "ELEMENT_SHELL" || currentKeyword_ == "ELEMENT_SHELL_TITLE") {
                if (!parseElementShellSection(file)) {
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
            else if (currentKeyword_ == "MAT_VISCOELASTIC" || currentKeyword_ == "MAT_VISCOELASTIC_TITLE" ||
                     currentKeyword_ == "MAT_006" || currentKeyword_ == "MAT_006_TITLE") {
                if (!parseMatViscoelasticSection(file)) {
                    return false;
                }
            }
            else if (currentKeyword_ == "MAT_MOONEY-RIVLIN_RUBBER" ||
                     currentKeyword_ == "MAT_MOONEY-RIVLIN_RUBBER_TITLE" ||
                     currentKeyword_ == "MAT_027" || currentKeyword_ == "MAT_027_TITLE") {
                if (!parseMatMooneyRivlinSection(file)) {
                    return false;
                }
            }
            else if (currentKeyword_ == "SECTION_SOLID" || currentKeyword_ == "SECTION_SOLID_TITLE" ||
                     currentKeyword_ == "SECTION_TSHELL" || currentKeyword_ == "SECTION_TSHELL_TITLE") {
                skipToNextKeyword(file);
            }
            else if (currentKeyword_ == "SECTION_SHELL" || currentKeyword_ == "SECTION_SHELL_TITLE") {
                if (!parseSectionShellSection(file)) {
                    return false;
                }
            }
            else if (currentKeyword_ == "END") {
                break;  // End of file
            }
            else {
                // Check if this is an unsupported material
                if (isMaterialKeyword(currentKeyword_) && !isSupportedMaterial(currentKeyword_)) {
                    // Read MID from the next line and record
                    std::streampos matPos = file.tellg();
                    std::string dataLine;
                    if (std::getline(file, dataLine)) {
                        auto tokens = tokenize(dataLine);
                        if (!tokens.empty()) {
                            try {
                                int mid = parseInt(tokens[0]);
                                unsupportedMaterials_.push_back({mid, currentKeyword_});
                            } catch (...) {
                                // Failed to parse MID, just record with MID=0
                                unsupportedMaterials_.push_back({0, currentKeyword_});
                            }
                        }
                    }
                    // Restore position and skip
                    file.seekg(matPos);
                    file.clear();
                }
                // Unknown keyword - skip until next keyword
                // This handles *SET_SEGMENT, *DEFINE_CURVE, *BOUNDARY_*, etc.
                skipToNextKeyword(file);
            }
        }

        reportProgress(file.tellg());
    }

    // Check for unsupported materials
    if (!unsupportedMaterials_.empty()) {
        errorMessage_ = "Unsupported material types found:\n";
        for (const auto& mat : unsupportedMaterials_) {
            errorMessage_ += "  MID " + std::to_string(mat.first) + ": *" + mat.second + "\n";
        }

        // Find parts using unsupported materials
        std::vector<int> affectedParts;
        for (const auto& part : mesh_.getParts()) {
            for (const auto& mat : unsupportedMaterials_) {
                if (part.second.materialId == mat.first) {
                    affectedParts.push_back(part.first);
                    break;
                }
            }
        }

        if (!affectedParts.empty()) {
            errorMessage_ += "\nAffected parts (will be skipped in stress calculation):\n";
            for (int pid : affectedParts) {
                errorMessage_ += "  PID " + std::to_string(pid);
                const auto& part = mesh_.getParts().at(pid);
                if (!part.name.empty()) {
                    errorMessage_ += " (" + part.name + ")";
                }
                errorMessage_ += "\n";
            }
        }

        errorMessage_ += "\nSupported materials: MAT_ELASTIC, MAT_PIECEWISE_LINEAR_PLASTICITY, "
                        "MAT_RIGID, MAT_VISCOELASTIC, MAT_MOONEY-RIVLIN_RUBBER";
        return false;
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
        //
        // IMPORTANT: Try fixed-width format FIRST before tokenizing,
        // because packed node IDs (no spaces) will be incorrectly parsed as 2-line format
        try {
            // Try fixed format single line first
            // i10=y: eid(10)+pid(10)+n1-n8(10*8) = 100 chars
            // normal: eid(8)+pid(8)+n1-n8(8*8) = 80 chars
            {
                int fw = i10_ ? 10 : 8;
                int minLen = fw * 10;  // eid + pid + 8 nodes
                if (line.length() >= (size_t)minLen) {
                    int eid = parseInt(line.substr(0, fw));
                    int pid = parseInt(line.substr(fw, fw));
                    std::array<int, 8> nodeIds;
                    for (int i = 0; i < 8; ++i) {
                        nodeIds[i] = parseInt(line.substr(fw * 2 + i * fw, fw));
                    }

                    if (eid > 0 && nodeIds[0] > 0) {
                        Element elem(eid, pid, nodeIds);
                        // Detect TET4: n5=n6=n7=n8=n4 (LS-DYNA convention)
                        if (nodeIds[4] == nodeIds[3] && nodeIds[5] == nodeIds[3] &&
                            nodeIds[6] == nodeIds[3] && nodeIds[7] == nodeIds[3]) {
                            elem.type = ElementType::TET4;
                        }
                        mesh_.addElement(elem);
                        elementCount++;
                        continue;  // Successfully parsed, move to next line
                    }
                    // else: fall through to free format
                }
            }

            // Now try free format (space/comma separated)
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

                // Try fixed format first (nodes may be packed without spaces)
                // i10=y: 10-char fields, otherwise 8-char fields
                bool parsedNodeLine = false;
                {
                    int fw = i10_ ? 10 : 8;
                    if (nodeLine.length() >= (size_t)(fw * 8)) {
                        std::array<int, 8> nodeIds;
                        for (int i = 0; i < 8; ++i) {
                            nodeIds[i] = parseInt(nodeLine.substr(i * fw, fw));
                        }

                        if (nodeIds[0] > 0) {
                            Element elem(eid, pid, nodeIds);
                            // Detect TET4: n5=n6=n7=n8=n4 (LS-DYNA convention)
                            if (nodeIds[4] == nodeIds[3] && nodeIds[5] == nodeIds[3] &&
                                nodeIds[6] == nodeIds[3] && nodeIds[7] == nodeIds[3]) {
                                elem.type = ElementType::TET4;
                            }
                            mesh_.addElement(elem);
                            elementCount++;
                            parsedNodeLine = true;
                        }
                    }
                }
                if (!parsedNodeLine) {
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
            // Note: Fixed-width format is now handled at the beginning of this try block
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

bool KFileReader::parseElementShellSection(std::ifstream& file) {
    // Parse *ELEMENT_SHELL section
    // Format: EID PID N1 N2 N3 N4 (4-node shell, sometimes N5-N8 on same line)
    // Store as 8-node Element with N5-N8 = N1-N4 for compatibility
    std::string line;
    std::streampos lastPos;
    int elementCount = 0;

    bool hasTitle = (currentKeyword_.find("TITLE") != std::string::npos);

    while (true) {
        lastPos = file.tellg();
        if (!std::getline(file, line)) break;
        currentLine_++;
        linesProcessed_++;

        // Normalize line endings
        if (!line.empty() && line.back() == '\r') {
            line.pop_back();
        }

        // Skip empty lines and comments
        if (line.empty() || isCommentLine(line)) continue;

        // Check for next keyword
        if (isKeywordLine(line)) {
            file.seekg(lastPos);
            file.clear();
            currentLine_--;
            linesProcessed_--;
            break;
        }

        // Skip title line for _TITLE variant (first data line per element is title)
        if (hasTitle && elementCount == 0) {
            // Title lines in ELEMENT_SHELL_TITLE appear before each element group
            // Just check: if it doesn't start with digits, it's a title
            auto tokens = tokenize(line);
            if (tokens.empty()) continue;
            bool isTitle = false;
            try { parseInt(tokens[0]); } catch (...) { isTitle = true; }
            if (isTitle) continue;
        }

        try {
            // Try fixed format first (8-char fields): EID(8) PID(8) N1(8) N2(8) N3(8) N4(8) = 48 chars min
            if (line.length() >= 48) {
                int eid = parseInt(line.substr(0, 8));
                int pid = parseInt(line.substr(8, 8));
                if (eid > 0 && pid > 0) {
                    std::array<int, 8> nodeIds;
                    nodeIds[0] = parseInt(line.substr(16, 8));
                    nodeIds[1] = parseInt(line.substr(24, 8));
                    nodeIds[2] = parseInt(line.substr(32, 8));
                    nodeIds[3] = parseInt(line.substr(40, 8));
                    // Duplicate for 8-node compatibility
                    nodeIds[4] = nodeIds[0];
                    nodeIds[5] = nodeIds[1];
                    nodeIds[6] = nodeIds[2];
                    nodeIds[7] = nodeIds[3];

                    Element elem(eid, pid, nodeIds);
                    elem.type = ElementType::QUAD4;
                    mesh_.addElement(elem);
                    elementCount++;
                    continue;
                }
            }

            // Fallback: free format
            auto tokens = tokenize(line);
            if (tokens.size() >= 6) {
                int eid = parseInt(tokens[0]);
                int pid = parseInt(tokens[1]);
                std::array<int, 8> nodeIds;
                nodeIds[0] = parseInt(tokens[2]);
                nodeIds[1] = parseInt(tokens[3]);
                nodeIds[2] = parseInt(tokens[4]);
                nodeIds[3] = parseInt(tokens[5]);
                nodeIds[4] = nodeIds[0];
                nodeIds[5] = nodeIds[1];
                nodeIds[6] = nodeIds[2];
                nodeIds[7] = nodeIds[3];

                Element elem(eid, pid, nodeIds);
                elem.type = ElementType::QUAD4;
                mesh_.addElement(elem);
                elementCount++;
            }
        }
        catch (const std::exception& e) {
            // Skip unparseable lines
            continue;
        }

        reportProgress(file.tellg());
    }

    return true;
}

bool KFileReader::parseSectionShellSection(std::ifstream& file) {
    // *SECTION_SHELL format (LS-DYNA):
    // Card 1: SECID(10) ELFORM(10) SHRF(10) NIP(10) PROPT(10) QR/IRID(10) ICOMP(10) SETYP(10)
    // Card 2: T1(10) T2(10) T3(10) T4(10) NLOC(10) MAREA(10) IDOF(10) EDGSET(10)
    // We extract SECID from card 1 and T1 from card 2.
    std::string line;
    std::streampos lastPos;
    bool hasTitle = (currentKeyword_.find("TITLE") != std::string::npos);

    // Skip title line if _TITLE variant
    if (hasTitle) {
        while (true) {
            lastPos = file.tellg();
            if (!std::getline(file, line)) return true;
            currentLine_++;
            linesProcessed_++;
            if (!line.empty() && line.back() == '\r') line.pop_back();
            if (line.empty() || isCommentLine(line)) continue;
            if (isKeywordLine(line)) { file.seekg(lastPos); currentLine_--; linesProcessed_--; return true; }
            break; // consumed title line
        }
    }

    // Card 1: read SECID
    int secId = 0;
    while (true) {
        lastPos = file.tellg();
        if (!std::getline(file, line)) return true;
        currentLine_++;
        linesProcessed_++;
        if (!line.empty() && line.back() == '\r') line.pop_back();
        if (line.empty() || isCommentLine(line)) continue;
        if (isKeywordLine(line)) { file.seekg(lastPos); currentLine_--; linesProcessed_--; return true; }
        try {
            if (line.length() >= 10) {
                secId = parseInt(line.substr(0, 10));
            } else {
                auto tokens = tokenize(line);
                if (!tokens.empty()) secId = parseInt(tokens[0]);
            }
        } catch (...) {}
        break;
    }

    // Card 2: read T1 (first field)
    double thickness = 0.0;
    while (true) {
        lastPos = file.tellg();
        if (!std::getline(file, line)) break;
        currentLine_++;
        linesProcessed_++;
        if (!line.empty() && line.back() == '\r') line.pop_back();
        if (line.empty() || isCommentLine(line)) continue;
        if (isKeywordLine(line)) { file.seekg(lastPos); currentLine_--; linesProcessed_--; break; }
        try {
            if (line.length() >= 10) {
                thickness = parseDouble(line.substr(0, 10));
            } else {
                auto tokens = tokenize(line);
                if (!tokens.empty()) thickness = parseDouble(tokens[0]);
            }
        } catch (...) {}
        break;
    }

    if (secId > 0 && thickness > 0) {
        mesh_.shellSections[secId] = SectionShellData(secId, thickness);
    }

    // Skip remaining cards
    skipToNextKeyword(file);
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

                // Reset for next part
                readTitle = false;
                partTitle.clear();
                pid = 0;
                secid = 0;
                mid = 0;
            }
        }
        catch (const std::exception& e) {
            // Non-fatal, just skip
        }

        // Continue reading next part (don't break!)
        if (foundData) {
            foundData = false;  // Reset for next part
        }
    }

    return true;
}

bool KFileReader::parseMatElasticSection(std::ifstream& file) {
    std::string line;
    std::streampos lastPos;
    int dataLineCount = 0;

    // Check if this is a _TITLE variant (has an extra title line to skip)
    bool hasTitle = (currentKeyword_.find("_TITLE") != std::string::npos);
    bool titleSkipped = false;

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

        // Skip title line for _TITLE variants
        if (hasTitle && !titleSkipped) {
            titleSkipped = true;
            continue;
        }

        // Parse material data (first data line contains the essential info)
        if (dataLineCount == 0) {
            try {
                // LS-DYNA default: fixed format (10-character fields)
                auto tokens = tokenizeFixed(line, 10);
                if (tokens.size() >= 4) {
                    mid = parseInt(tokens[0]);
                    density = parseDouble(tokens[1]);
                    E = parseDouble(tokens[2]);
                    nu = parseDouble(tokens[3]);
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

    // Check if this is a _TITLE variant (has an extra title line to skip)
    bool hasTitle = (currentKeyword_.find("_TITLE") != std::string::npos);
    bool titleSkipped = false;

    // *MAT_PIECEWISE_LINEAR_PLASTICITY format (4 cards):
    // Card 1: mid, ro, e, pr, sigy, etan, fail, tdel
    // Card 2: c, p, lcss, lcsr, vp, lcf, (not used), (not used)
    // Card 3: eps1, eps2, eps3, eps4, eps5, eps6, eps7, eps8
    // Card 4: es1, es2, es3, es4, es5, es6, es7, es8

    int mid = 0;
    double density = 0, E = 0, nu = 0, sigy = 0;

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

        // Skip title line for _TITLE variants
        if (hasTitle && !titleSkipped) {
            titleSkipped = true;
            continue;
        }

        // Parse first card (contains mid, ro, e, pr, sigy)
        if (dataLineCount == 0) {
            try {
                // LS-DYNA default: fixed format (10-character fields)
                auto tokens = tokenizeFixed(line, 10);
                if (tokens.size() >= 4) {
                    mid = parseInt(tokens[0]);
                    density = parseDouble(tokens[1]);
                    E = parseDouble(tokens[2]);
                    nu = parseDouble(tokens[3]);
                }
                if (tokens.size() >= 5) {
                    sigy = parseDouble(tokens[4]);
                }

                if (mid > 0 && E > 0) {
                    mesh_.addMaterial(mid, E, nu, density);
                    if (sigy > 0) {
                        mesh_.materials[mid].sigy = sigy;
                    }
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

    // Check if this is a _TITLE variant (has an extra title line to skip)
    bool hasTitle = (currentKeyword_.find("_TITLE") != std::string::npos);
    bool titleSkipped = false;

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

        // Skip title line for _TITLE variants
        if (hasTitle && !titleSkipped) {
            titleSkipped = true;
            continue;
        }

        // Parse first card (contains mid, ro, e, pr)
        if (dataLineCount == 0) {
            try {
                // LS-DYNA default: fixed format (10-character fields)
                auto tokens = tokenizeFixed(line, 10);
                if (tokens.size() >= 4) {
                    mid = parseInt(tokens[0]);
                    density = parseDouble(tokens[1]);
                    E = parseDouble(tokens[2]);
                    nu = parseDouble(tokens[3]);
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

bool KFileReader::parseMatViscoelasticSection(std::ifstream& file) {
    std::string line;
    std::streampos lastPos;
    int dataLineCount = 0;

    // Check if this is a _TITLE variant (has an extra title line to skip)
    bool hasTitle = (currentKeyword_.find("_TITLE") != std::string::npos);
    bool titleSkipped = false;

    // *MAT_VISCOELASTIC format (1 card):
    // Card 1: mid, ro, bulk, g0, gi, beta
    // mid = material ID
    // ro = density
    // bulk = bulk modulus (K)
    // g0 = short-time shear modulus
    // gi = long-time shear modulus (equilibrium, t->infinity)
    // beta = decay constant
    //
    // For prestress calculation, use gi (long-time/equilibrium shear modulus)
    // Convert to E and nu:
    //   E = 9*K*G / (3*K + G)
    //   nu = (3*K - 2*G) / (2*(3*K + G))

    int mid = 0;
    double density = 0, bulk = 0, g0 = 0, gi = 0;

    while (true) {
        lastPos = file.tellg();
        if (!std::getline(file, line)) break;

        currentLine_++;
        linesProcessed_++;

        if (!line.empty() && line.back() == '') {
            line.pop_back();
        }

        if (line.empty()) {
            continue;
        }

        if (isCommentLine(line)) {
            continue;
        }

        if (isKeywordLine(line)) {
            file.seekg(lastPos);
            currentLine_--;
            return true;
        }

        // Skip title line for _TITLE variants
        if (hasTitle && !titleSkipped) {
            titleSkipped = true;
            continue;
        }

        if (dataLineCount == 0) {
            try {
                // LS-DYNA default: fixed format (10-character fields)
                auto tokens = tokenizeFixed(line, 10);
                if (tokens.size() >= 5) {
                    mid = parseInt(tokens[0]);
                    density = parseDouble(tokens[1]);
                    bulk = parseDouble(tokens[2]);
                    g0 = parseDouble(tokens[3]);
                    gi = parseDouble(tokens[4]);
                }

                if (mid > 0 && bulk > 0 && gi > 0) {
                    // Use gi (long-time shear modulus) for equilibrium state
                    double G = gi;
                    double K = bulk;
                    double E = 9.0 * K * G / (3.0 * K + G);
                    double nu = (3.0 * K - 2.0 * G) / (2.0 * (3.0 * K + G));
                    mesh_.addMaterial(mid, E, nu, density);
                }
            }
            catch (const std::exception& e) {
                // Non-fatal, just skip
            }
        }

        dataLineCount++;

        if (dataLineCount >= 1) {
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
        // LS-DYNA keywords can contain letters, numbers, underscores, and hyphens
        if (std::isalnum(c) || c == '_' || c == '-') {
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

std::vector<std::string> KFileReader::tokenizeFixed(const std::string& line, int fieldWidth) const {
    std::vector<std::string> tokens;

    for (size_t i = 0; i < line.length(); i += fieldWidth) {
        size_t len = std::min(static_cast<size_t>(fieldWidth), line.length() - i);
        std::string field = line.substr(i, len);
        tokens.push_back(trim(field));
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

bool KFileReader::isMaterialKeyword(const std::string& keyword) const {
    // Check if keyword starts with "MAT_"
    return keyword.find("MAT_") == 0;
}

bool KFileReader::isSupportedMaterial(const std::string& keyword) const {
    // List of supported material keywords
    if (keyword.find("MAT_ELASTIC") == 0 || keyword.find("MAT_001") == 0) return true;
    if (keyword.find("MAT_PIECEWISE_LINEAR_PLASTICITY") == 0 || keyword.find("MAT_024") == 0) return true;
    if (keyword.find("MAT_RIGID") == 0 || keyword.find("MAT_020") == 0) return true;
    if (keyword.find("MAT_VISCOELASTIC") == 0 || keyword.find("MAT_006") == 0) return true;
    if (keyword.find("MAT_MOONEY-RIVLIN_RUBBER") == 0 || keyword.find("MAT_027") == 0) return true;
    return false;
}

bool KFileReader::parseMatMooneyRivlinSection(std::ifstream& file) {
    std::string line;
    std::streampos lastPos;
    bool foundData = false;
    bool readTitle = false;
    std::string matTitle;

    // *MAT_MOONEY-RIVLIN_RUBBER format:
    // Line 0 (optional): title
    // Line 1: MID, RHO, PR, A, B, REF
    // Line 2 (optional): SGL, SW, ST, LCID
    //
    // For prestress calculation, we need:
    // - PR (Poisson's ratio)
    // - A, B (Mooney-Rivlin constants)
    //
    // Equivalent linear elastic moduli:
    // G0 = 2(A + B)  (initial shear modulus)
    // E = 2*G0*(1 + PR)
    // nu = PR

    int mid = 0;
    double rho = 0.0, pr = 0.0, a = 0.0, b = 0.0;

    while (true) {
        lastPos = file.tellg();
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
            file.seekg(lastPos);
            file.clear();
            currentLine_--;
            return true;
        }

        // Check if this is title line (for _TITLE variant)
        if (currentKeyword_.find("_TITLE") != std::string::npos && !readTitle) {
            matTitle = line;
            readTitle = true;
            continue;
        }

        if (!foundData) {
            // Parse first data line using fixed-width format (10 chars per field)
            auto tokens = tokenizeFixed(line);

            // Minimum required: MID, RHO, PR, A (B and REF are optional)
            if (tokens.size() >= 4) {
                mid = parseInt(tokens[0]);
                rho = parseDouble(tokens[1]);
                pr = parseDouble(tokens[2]);
                a = parseDouble(tokens[3]);
                b = (tokens.size() >= 5) ? parseDouble(tokens[4]) : 0.0;
                // ref = (tokens.size() >= 6) ? parseDouble(tokens[5]) : 0.0;  // Not needed

                foundData = true;

                // Calculate equivalent linear elastic properties
                // Initial shear modulus: G0 = 2(A + B)
                double G = 2.0 * (a + b);

                // Young's modulus: E = 2*G*(1 + nu)
                double E = 2.0 * G * (1.0 + pr);

                // Create material
                MaterialData mat;
                mat.id = mid;
                mat.density = rho;
                mat.E = E;
                mat.nu = pr;

                if (!matTitle.empty()) {
                    mat.name = matTitle;
                } else {
                    mat.name = "MAT_" + std::to_string(mid);
                }

                mesh_.addMaterial(mat);

                // Only need first data line for *MAT_MOONEY-RIVLIN_RUBBER
                return true;
            }
        }

        reportProgress(file.tellg());
    }

    return true;
}

} // namespace KooRemapper
