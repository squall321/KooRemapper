#include "parser/KFileWriter.h"
#include <sstream>
#include <iomanip>
#include <ctime>
#include <algorithm>
#include <fstream>
#include <cctype>

// Knowledge graph (lat.md):
//   @lat: [[modules/parser]]

namespace KooRemapper {

namespace {
// Case-insensitive prefix check for keyword detection.
// Accepts variants like "*NODE", "*node ", "*NODE_RIGID_SURFACE" (when
// prefix="*NODE"); the caller decides whether sub-variants should be
// treated as "same family".
bool startsWithKeyword(const std::string& line, const char* keyword) {
    size_t i = 0;
    // Allow leading whitespace before '*'
    while (i < line.size() && std::isspace(static_cast<unsigned char>(line[i]))) ++i;
    size_t k = 0;
    while (keyword[k] != '\0') {
        if (i >= line.size()) return false;
        char a = static_cast<char>(std::toupper(static_cast<unsigned char>(line[i])));
        char b = static_cast<char>(std::toupper(static_cast<unsigned char>(keyword[k])));
        if (a != b) return false;
        ++i; ++k;
    }
    // Match if the keyword ends here or is followed by space/_/end-of-line
    if (i >= line.size()) return true;
    char next = line[i];
    return next == ' ' || next == '\t' || next == '_' || next == '\r';
}
}  // namespace

KFileWriter::KFileWriter()
    : precision_(9)
    , coordFieldWidth_(16)
    , includeHeader_(true)
{}

bool KFileWriter::writeFileWithSource(const std::string& filename, const Mesh& mesh,
                                      const std::string& sourceFile,
                                      bool useMappedPositions) {
    errorMessage_.clear();

    // Slurp source so we can stream it out while substituting NODE/ELEMENT
    // blocks. Reading first guards against the case where filename and
    // sourceFile point at the same path.
    std::ifstream src(sourceFile);
    if (!src.is_open()) {
        errorMessage_ = "Cannot open source file for preservation: " + sourceFile;
        return false;
    }
    std::vector<std::string> srcLines;
    srcLines.reserve(1024);
    {
        std::string line;
        while (std::getline(src, line)) {
            if (!line.empty() && line.back() == '\r') line.pop_back();
            srcLines.push_back(std::move(line));
        }
    }
    src.close();

    std::ofstream out(filename);
    if (!out.is_open()) {
        errorMessage_ = "Cannot create file: " + filename;
        return false;
    }

    try {
        if (includeHeader_) writeHeader(out);

        // Block-skipping state machine. When we enter a NODE or ELEMENT_SOLID
        // block, we drop the source content (the keyword line itself and all
        // subsequent data lines) until the next *KEYWORD. The replacement
        // block is emitted once, at the first time we see the corresponding
        // keyword. `*END` is emitted by writeEnd() at the very bottom, so we
        // skip any `*END` line we find in the source.
        bool inSkipBlock = false;
        bool nodeEmitted = false;
        bool elemEmitted = false;
        bool endSuppressed = false;  // we'll emit our own *END

        auto emitOurNodes = [&]() {
            if (nodeEmitted) return;
            writeNodeSection(out, mesh, useMappedPositions);
            nodeEmitted = true;
        };
        auto emitOurElems = [&]() {
            if (elemEmitted) return;
            writeElementSection(out, mesh);
            elemEmitted = true;
        };

        for (const std::string& line : srcLines) {
            // Detect start of a new keyword block (any line beginning with '*'
            // after optional whitespace).
            size_t firstNonWs = 0;
            while (firstNonWs < line.size() &&
                   std::isspace(static_cast<unsigned char>(line[firstNonWs]))) {
                ++firstNonWs;
            }
            bool isKeyword = firstNonWs < line.size() && line[firstNonWs] == '*';

            if (isKeyword) {
                // Exiting the previous skip block (if any).
                inSkipBlock = false;

                if (startsWithKeyword(line, "*NODE")) {
                    // *NODE family — match exact *NODE only, not *NODE_*
                    // variants like *NODE_RIGID_SURFACE.
                    std::string up;
                    for (size_t i = firstNonWs; i < line.size(); ++i) {
                        char c = static_cast<char>(std::toupper(
                            static_cast<unsigned char>(line[i])));
                        if (c == ' ' || c == '\t' || c == '\r') break;
                        up.push_back(c);
                    }
                    if (up == "*NODE") {
                        emitOurNodes();
                        inSkipBlock = true;
                        continue;
                    }
                }
                if (startsWithKeyword(line, "*ELEMENT_SOLID")) {
                    emitOurElems();
                    inSkipBlock = true;
                    continue;
                }
                if (startsWithKeyword(line, "*END")) {
                    endSuppressed = true;
                    continue;
                }
                // Other keyword — fall through to verbatim emit
            }

            if (inSkipBlock) continue;
            out << line << "\n";
        }

        // If the source somehow lacked the keyword we were planning to
        // substitute, emit it now so the output is still well-formed.
        if (!nodeEmitted) writeNodeSection(out, mesh, useMappedPositions);
        if (!elemEmitted) writeElementSection(out, mesh);
        (void)endSuppressed;
        writeEnd(out);

        out.close();
        return true;
    }
    catch (const std::exception& e) {
        errorMessage_ = std::string("Error writing file: ") + e.what();
        out.close();
        return false;
    }
}

bool KFileWriter::writeFile(const std::string& filename, const Mesh& mesh,
                            bool useMappedPositions) {
    errorMessage_.clear();

    std::ofstream file(filename);
    if (!file.is_open()) {
        errorMessage_ = "Cannot create file: " + filename;
        return false;
    }

    try {
        if (includeHeader_) {
            writeHeader(file);
        }

        writeNodeSection(file, mesh, useMappedPositions);
        writeElementSection(file, mesh);
        writeEnd(file);

        file.close();
        return true;
    }
    catch (const std::exception& e) {
        errorMessage_ = std::string("Error writing file: ") + e.what();
        file.close();
        return false;
    }
}

void KFileWriter::writeHeader(std::ofstream& file) {
    // Get current time
    std::time_t now = std::time(nullptr);
    char timeStr[64];
    std::strftime(timeStr, sizeof(timeStr), "%Y-%m-%d %H:%M:%S", std::localtime(&now));

    file << "$" << std::endl;
    file << "$ LS-DYNA Keyword File" << std::endl;
    file << "$ Generated by KooRemapper" << std::endl;
    file << "$ Date: " << timeStr << std::endl;
    file << "$" << std::endl;
}

void KFileWriter::writeNodeSection(std::ofstream& file, const Mesh& mesh,
                                   bool useMappedPositions) {
    file << "*NODE" << std::endl;
    file << "$#   nid               x               y               z" << std::endl;

    // Sort nodes by ID for consistent output
    std::vector<std::pair<int, const Node*>> sortedNodes;
    for (const auto& [id, node] : mesh.nodes) {
        sortedNodes.push_back({id, &node});
    }
    std::sort(sortedNodes.begin(), sortedNodes.end(),
              [](const auto& a, const auto& b) { return a.first < b.first; });

    for (const auto& [id, nodePtr] : sortedNodes) {
        const Node& node = *nodePtr;
        const Vector3D& pos = useMappedPositions && node.isMapped
                            ? node.mappedPosition
                            : node.position;

        file << std::setw(8) << node.id
             << formatDouble(pos.x)
             << formatDouble(pos.y)
             << formatDouble(pos.z)
             << std::endl;
    }
}

void KFileWriter::writeElementSection(std::ofstream& file, const Mesh& mesh) {
    file << "*ELEMENT_SOLID" << std::endl;
    file << "$#   eid     pid      n1      n2      n3      n4      n5      n6      n7      n8" << std::endl;

    // Sort elements by ID
    std::vector<std::pair<int, const Element*>> sortedElements;
    for (const auto& [id, elem] : mesh.elements) {
        sortedElements.push_back({id, &elem});
    }
    std::sort(sortedElements.begin(), sortedElements.end(),
              [](const auto& a, const auto& b) { return a.first < b.first; });

    for (const auto& [id, elemPtr] : sortedElements) {
        const Element& elem = *elemPtr;

        file << std::setw(8) << elem.id
             << std::setw(8) << elem.partId;

        if (elem.type == ElementType::TET4) {
            // TET4: write 4 nodes, then repeat n4 for n5-n8 (LS-DYNA convention)
            for (int i = 0; i < 4; ++i) {
                file << std::setw(8) << elem.nodeIds[i];
            }
            for (int i = 4; i < 8; ++i) {
                file << std::setw(8) << elem.nodeIds[3];  // Repeat n4
            }
        } else {
            // HEX8 and others: write all 8 nodes
            for (int i = 0; i < Element::NUM_NODES; ++i) {
                file << std::setw(8) << elem.nodeIds[i];
            }
        }
        file << std::endl;
    }
}

void KFileWriter::writeEnd(std::ofstream& file) {
    file << "*END" << std::endl;
}

std::string KFileWriter::formatDouble(double value) const {
    std::ostringstream oss;
    oss << std::setw(coordFieldWidth_)
        << std::scientific
        << std::setprecision(precision_)
        << value;
    return oss.str();
}

std::string KFileWriter::formatInt(int value, int width) const {
    std::ostringstream oss;
    oss << std::setw(width) << value;
    return oss.str();
}

} // namespace KooRemapper
