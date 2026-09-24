#include "parser/KFileWriter.h"
#include <sstream>
#include <iomanip>
#include <ctime>
#include <algorithm>
#include <fstream>
#include <cctype>
#include <set>

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

// Uppercased keyword token of a '*' line: "*ELEMENT_SHELL_TITLE" out of
// "  *element_shell_title   $ comment".
std::string keywordToken(const std::string& line, size_t firstNonWs) {
    std::string up;
    for (size_t i = firstNonWs; i < line.size(); ++i) {
        char c = static_cast<char>(std::toupper(static_cast<unsigned char>(line[i])));
        if (c == ' ' || c == '\t' || c == '\r') break;
        up.push_back(c);
    }
    return up;
}

// Element blocks that KFileReader also loads into mesh.elements but that
// writeElementSection cannot round-trip (a shell/thick-shell is not an
// *ELEMENT_SOLID). They stay in the output verbatim, so their EIDs must not
// be written a second time inside our *ELEMENT_SOLID block.
bool isVerbatimElementKeyword(const std::string& kw) {
    // 옵션 변형(*ELEMENT_SHELL_THICKNESS 등)까지 접두어로 잡는다 — 리더가 그 변형도 읽게 된 뒤로
    // 정확히 같은 이름만 보면 그 EID 가 *ELEMENT_SOLID 블록에 한 번 더 적힌다.
    return kw.rfind("*ELEMENT_SHELL", 0) == 0 || kw.rfind("*ELEMENT_TSHELL", 0) == 0;
}

// EID of one element data line — fixed 8-char field when the line is wide
// enough (same assumption as KFileReader), otherwise the first token.
int elementLineEid(const std::string& line) {
    std::string field;
    if (line.size() >= 48) {
        field = line.substr(0, 8);
    } else {
        size_t i = 0;
        while (i < line.size() && std::isspace(static_cast<unsigned char>(line[i]))) ++i;
        size_t j = i;
        while (j < line.size() && !std::isspace(static_cast<unsigned char>(line[j]))) ++j;
        field = line.substr(i, j - i);
    }
    try {
        return std::stoi(field);
    } catch (...) {
        return 0;
    }
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

    // 원본의 개행을 그대로 따른다. 위 루프가 CR 을 떼므로(그 자체는 옳다 — 남기면 뒤의 파싱이
    // 깨진다) 여기서 되붙이지 않으면 CRLF 덱이 조용히 LF 로 바뀐다. 호출부는 고칠 것이 없다.
    newline_ = deck_newline::detect(sourceFile);
    DeckWriter writer(filename, newline_);
    if (!writer.ok()) {
        errorMessage_ = "Cannot create file: " + filename;
        return false;
    }
    std::ostream& out = writer.stream();

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

        // Shell / thick-shell blocks are copied verbatim, but KFileReader put
        // their elements into mesh.elements too. Collect their EIDs up front
        // (they can appear after *ELEMENT_SOLID) so writeElementSection leaves
        // them out instead of re-emitting them as *ELEMENT_SOLID — that used
        // to produce a deck with the same EID twice.
        std::set<int> verbatimElemIds;
        {
            bool inVerbatimElem = false;
            for (const std::string& line : srcLines) {
                size_t p = 0;
                while (p < line.size() &&
                       std::isspace(static_cast<unsigned char>(line[p]))) {
                    ++p;
                }
                if (p >= line.size()) continue;
                if (line[p] == '*') {
                    inVerbatimElem = isVerbatimElementKeyword(keywordToken(line, p));
                    continue;
                }
                if (!inVerbatimElem || line[p] == '$') continue;
                int eid = elementLineEid(line);
                if (eid > 0) verbatimElemIds.insert(eid);
            }
        }

        auto emitOurNodes = [&]() {
            if (nodeEmitted) return;
            writeNodeSection(out, mesh, useMappedPositions);
            nodeEmitted = true;
        };
        auto emitOurElems = [&]() {
            if (elemEmitted) return;
            writeElementSection(out, mesh, &verbatimElemIds);
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

                const std::string up = keywordToken(line, firstNonWs);
                if (up == "*NODE") {
                    // *NODE family — match exact *NODE only, not *NODE_*
                    // variants like *NODE_RIGID_SURFACE.
                    emitOurNodes();
                    inSkipBlock = true;
                    continue;
                }
                if (up == "*ELEMENT_SOLID" || up == "*ELEMENT_SOLID_TITLE") {
                    // Exact match only: *ELEMENT_SOLID_ORTHO and friends are
                    // not loaded into mesh.elements, so dropping their block
                    // would lose those elements. Copy them verbatim instead.
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
        if (!elemEmitted) writeElementSection(out, mesh, &verbatimElemIds);
        (void)endSuppressed;
        writeEnd(out);

        writer.close();
        return true;
    }
    catch (const std::exception& e) {
        errorMessage_ = std::string("Error writing file: ") + e.what();
        writer.close();
        return false;
    }
}

bool KFileWriter::writeFile(const std::string& filename, const Mesh& mesh,
                            bool useMappedPositions) {
    errorMessage_.clear();

    // 원본 덱이 없는 경로 — 호출자가 setNewline 으로 정해 준 개행을 쓴다(기본 LF).
    DeckWriter writer(filename, newline_);
    if (!writer.ok()) {
        errorMessage_ = "Cannot create file: " + filename;
        return false;
    }
    std::ostream& file = writer.stream();

    try {
        if (includeHeader_) {
            writeHeader(file);
        }

        writeNodeSection(file, mesh, useMappedPositions);
        writeElementSection(file, mesh);
        writeEnd(file);

        writer.close();
        return true;
    }
    catch (const std::exception& e) {
        errorMessage_ = std::string("Error writing file: ") + e.what();
        writer.close();
        return false;
    }
}

void KFileWriter::writeHeader(std::ostream& file) {
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

void KFileWriter::writeNodeSection(std::ostream& file, const Mesh& mesh,
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

void KFileWriter::writeElementSection(std::ostream& file, const Mesh& mesh,
                                      const std::set<int>* skipIds) {
    // Sort elements by ID
    std::vector<std::pair<int, const Element*>> sortedElements;
    for (const auto& [id, elem] : mesh.elements) {
        if (skipIds && skipIds->count(id)) continue;
        sortedElements.push_back({id, &elem});
    }
    // 쉘만 있는 덱이면 쓸 솔리드가 하나도 없다 — 빈 *ELEMENT_SOLID 블록을 남기지 않는다
    if (sortedElements.empty()) return;
    std::sort(sortedElements.begin(), sortedElements.end(),
              [](const auto& a, const auto& b) { return a.first < b.first; });

    file << "*ELEMENT_SOLID" << std::endl;
    file << "$#   eid     pid      n1      n2      n3      n4      n5      n6      n7      n8" << std::endl;

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

void KFileWriter::writeEnd(std::ostream& file) {
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
