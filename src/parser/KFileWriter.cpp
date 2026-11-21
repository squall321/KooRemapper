#include "parser/DeckScan.h"   // isKeywordLine — 리더와 같은 1열 키워드 규칙
#include "parser/ElementCardLayout.h"
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

// 키워드 줄은 리더와 같은 규칙(`deckscan::isKeywordLine` — 1열 `*` + 글자 · Vol_I 17940). 들여쓴 `*` 줄은 앞 블록의 데이터다 —
// 예전엔 들여쓴 `  *END` 를 끝으로 보아 거기서 `*END` 를 쓰고 원본의 `*END` 를 또 베꼈다(`*END` 가 둘 · 2026-11-08 재검토)
using deckscan::isKeywordLine;

}  // namespace

KFileWriter::KFileWriter()
    : precision_(9)
    , includeHeader_(true)
{}

// 2차 솔리드를 쓸 수 있나 — TET10 인데 덱 순서 전체 절점(`Mesh::solidAllNodes`)이 없으면 쓸 수 없다. 코너 넷만 쓰면
// ELFORM 16·17 파트에 TET4 카드가 들어간다(중간절점이 조용히 사라진다). 리더가 읽은 요소는 늘 전체 절점을 갖는다 —
// 요소를 하나씩 옮겨 담은 새 메시에서만 생긴다. 파일을 열기 **전에** 본다(반쯤 쓴 산출을 남기지 않는다).
static bool secondOrderWritable(const Mesh& mesh, std::string& why) {
    for (const auto& [id, e] : mesh.elements) {
        if (e.type != ElementType::TET10 || mesh.allNodesOf(id)) continue;
        why = "요소 " + std::to_string(id) + " 는 10절점 사면체인데 중간절점 목록이 없다 — 코너만 쓰면 2차 요소가 사라진다";
        return false;
    }
    return true;
}

// ★리더가 같은 번호의 뒤 카드에 덮여 잃은 요소가 있으면 쓰지 않는다(2026-11-17 · DF-14 · 사용자 결정 「감지 · 경고 · 쓰기 거절」).
//   요소 표가 번호 하나로 열쇠를 잡아, 솔리드 1 과 셸 1 처럼 족을 건넌 번호(LS-DYNA 는 족마다 따로 받는다)도 앞 정의를 잃는다. 그대로
//   쓰면 잃은 요소가 산출 덱에서 말없이 빠진다 — 원본을 베끼는 쓰기도 원본 셸 블록과 번호가 같은 솔리드를 건너뛰므로 같다.
//   표는 리더만 채우고(`Mesh::readerLostElements`), 새로 짓는 메시는 원본 것을 옮겨 받는다. 파일을 열기 **전에** 본다
static bool readerLossWritable(const Mesh& mesh, std::string& why) {
    if (mesh.readerLostElements.empty()) return true;
    size_t total = 0;
    std::string pids;
    size_t shown = 0;
    for (const auto& [pid, n] : mesh.readerLostElements) {
        total += n;
        if (shown++ < 5) pids += (pids.empty() ? "" : ", ") + std::to_string(pid);
    }
    if (mesh.readerLostElements.size() > 5) pids += " 외 " + std::to_string(mesh.readerLostElements.size() - 5) + "개";
    why = "입력 덱의 요소 번호가 겹쳐 리더가 앞 정의 " + std::to_string(total) + "개를 잃었다(잃은 요소의 PID " + pids +
          ") — 이대로 쓰면 그 요소가 산출 덱에서 빠진다. 솔리드 · 셸처럼 족을 건넌 겹침은 LS-DYNA 는 받지만 이 도구는 한 표로 읽는다 — "
          "겹친 번호를 옮긴 덱으로 다시 돌린다(info 가 겹친 블록을 짚는다)";
    return false;
}

// 번호가 덱의 정수 칸에 들어가나 — 8칸 덱(맨 `*KEYWORD`)에 9자리 번호를 쓰면 칸이 붙은 깨진 덱이 rc 0 으로 나갔다(2026-11-21). 원본이
// `*NODE %` 처럼 블록마다 폭을 넓혀 그 번호를 담았더라도 이 쓰기는 덱이 선언한 폭 하나로만 쓴다 — 못 담으면 쓰지 않는다. 10칸
// 이상은 LS-DYNA 정수 상한(2147483647 — 열 자리 · Vol_I 19325)이 다 들어간다. 셸 · 두께 셸은 메시에서 쓸 때만 본다(원본 블록을
// 그대로 옮기면 그 줄은 원본의 폭이다). 파일을 열기 **전에** 본다
static bool idsFitField(const Mesh& mesh, int fw, bool shellsFromMesh, std::string& why) {
    if (fw >= 10) return true;
    long long limit = 1;
    for (int i = 0; i < fw; ++i) limit *= 10;
    auto fits = [&](long long v, const char* what) {
        if (v < limit) return true;
        why = std::to_string(fw) + "칸에 들어가지 않는 번호가 있다 — " + what + " " + std::to_string(v) + ". 이 쓰기는 덱이 선언한 칸 폭(" +
              std::to_string(fw) + ") 하나로 쓴다 — 번호를 낮추거나 `*KEYWORD I10=Y` 로 선언한 덱으로 다시 돌린다";
        return false;
    };
    for (const auto& [id, node] : mesh.nodes)
        if (!fits(node.id, "절점 번호")) return false;
    for (const auto& [id, e] : mesh.elements) {
        if (!shellsFromMesh && (e.type == ElementType::QUAD4 || mesh.thickShellIds.count(id))) continue;
        if (!fits(e.id, "요소 번호") || !fits(e.partId, "요소의 파트 번호")) return false;
        if (const auto* all = mesh.allNodesOf(id)) {
            for (int n : *all)
                if (!fits(n, "요소가 가리키는 절점 번호")) return false;
        } else {
            for (int n : e.nodeIds)
                if (!fits(n, "요소가 가리키는 절점 번호")) return false;
        }
    }
    return true;
}

bool KFileWriter::writeFileWithSource(const std::string& filename, const Mesh& mesh,
                                      const std::string& sourceFile,
                                      bool useMappedPositions) {
    errorMessage_.clear();
    if (!secondOrderWritable(mesh, errorMessage_)) return false;
    if (!readerLossWritable(mesh, errorMessage_)) return false;

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

    // ★원본의 **첫** `*END` 앞만 본다(LS-DYNA · 리더가 거기서 멈춘다). 그 뒤 줄은 아래 걸음이 그대로 베낀다. 예전엔 `*KEYWORD` 찾기 · 폭 ·
    //   셸 번호 미리 훑기가 덱 끝까지 읽어, 첫 `*END` 뒤의 읽히지 않는 셸 블록에 산 솔리드와 같은 번호가 있으면 그 솔리드를 쓰지 않았다
    //   (map rc 0 · 2026-11-08 여섯째 검토)
    const std::vector<std::string> liveLines(srcLines.begin(),
                                             srcLines.begin() + static_cast<std::ptrdiff_t>(deckscan::firstEndLine(srcLines)));
    // 원본 덱이 선언한 칸 폭을 따른다. 원본의 `*KEYWORD I10=Y` 는 그대로 베껴 나가므로
    // 이것을 안 하면 **선언은 10칸인데 본문은 8칸인 덱**이 나간다(그 상태로 rc=0 이었다).
    idFieldWidth_ = KooRemapper::deckFieldWidth(liveLines);
    // 번호가 그 칸에 안 들어가면 산출을 만들기 전에 멈춘다(셸 · 두께 셸 블록은 원본 줄을 그대로 옮기므로 보지 않는다)
    if (!idsFitField(mesh, idFieldWidth_, /*shellsFromMesh=*/false, errorMessage_)) return false;

    DeckWriter writer(filename, newline_);
    if (!writer.ok()) {
        errorMessage_ = "Cannot create file: " + filename;
        return false;
    }
    std::ostream& out = writer.stream();

    try {
        // ★원본에 `*KEYWORD` 가 **없을 때만** 넣는다. 있는 덱 앞에 맨 `*KEYWORD` 를 끼우면
        //   `deckFieldWidth` 가 **첫 번째** 것에서 멈추므로 `*KEYWORD I10=Y` 덱이 8칸으로
        //   읽힌다 — 선언 10칸·본문 8칸이라는 cnrb2 의 그 결함을 쓰는 쪽에서 되살리는 꼴이다.
        //   없는 덱은 지금도 8 이므로(`deckFieldWidth` 의 마지막 `return 8`) 폭은 안 움직인다.
        //   `includeHeader_` 밖에 둔다 — 이건 머리말 장식이 아니라 **있어야 읽히는 카드**다.
        if (!KooRemapper::hasKeywordCard(liveLines)) out << "*KEYWORD\n";
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

        // 셸 · 두께 셸 블록은 원본 줄을 그대로 옮긴다. 리더가 그 요소도 메시에 담았지만 `writeElementSection` 이 메시의 사실(QUAD4 ·
        // 두께 셸 표지)로 `*ELEMENT_SOLID` 에서 뺀다. 예전엔 여기서 원본의 셸 블록 줄을 8칸으로 다시 읽어 번호를 모았다 — 10칸 줄 ·
        // 두께 카드 · 리더가 안 읽는 변형(`_BETA` · `_COMPOSITE`)의 줄에서 나온 수와 번호가 같은 솔리드가 산출에서 빠졌다(rc 0 ·
        // 2026-11-21)

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

        // ★원본의 **첫** `*END` 에서 끝낸다 — 못 쓴 블록을 그 앞에 쓰고 `*END` 를 쓴 뒤, 남은 원본 줄은 그대로 베낀다(LS-DYNA 는 첫
        //   `*END` 에서 멈추고 리더도 거기서 멈춘다). 예전엔 원본의 `*END` 를 모두 지우고 맨 끝에 하나만 써, 첫 `*END` 뒤에 있던 카드
        //   (읽히지 않던 것)가 산출에서 **살아났다** — map 이 덱 끝의 죽은 `*PART` 를 첫 `*END` 앞으로 옮겼다(셋째 묶음)
        bool afterEnd = false;
        for (const std::string& line : srcLines) {
            if (afterEnd) { out << line << "\n"; continue; }
            // Detect start of a new keyword block — 리더와 같은 키워드 줄(1열 `*` + 글자)만
            const bool isKeyword = isKeywordLine(line);

            if (isKeyword) {
                // Exiting the previous skip block (if any).
                inSkipBlock = false;

                // 블록 이름은 리더가 뽑는 그 이름으로 가른다(`*NODE%` 처럼 접미사를 붙여 쓴 줄도 리더는 `NODE` 로 읽는다)
                const std::string name = gridReaderKeywordName(line);
                if (name == "NODE") {
                    // *NODE family — match exact *NODE only, not *NODE_*
                    // variants like *NODE_RIGID_SURFACE.
                    emitOurNodes();
                    inSkipBlock = true;
                    continue;
                }
                if (name == "ELEMENT_SOLID" || name == "ELEMENT_SOLID_TITLE") {
                    // Exact match only: *ELEMENT_SOLID_ORTHO and friends are
                    // not loaded into mesh.elements, so dropping their block
                    // would lose those elements. Copy them verbatim instead.
                    emitOurElems();
                    inSkipBlock = true;
                    continue;
                }
                if (startsWithKeyword(line, "*END")) {
                    emitOurNodes();
                    emitOurElems();
                    writeEnd(out);
                    endSuppressed = true;
                    afterEnd = true;
                    continue;
                }
                // Other keyword — fall through to verbatim emit
            }

            if (inSkipBlock) continue;
            out << line << "\n";
        }

        // If the source somehow lacked the keyword we were planning to
        // substitute, emit it now so the output is still well-formed.
        if (!afterEnd) {   // 원본에 *END 가 없었다 — 끝에 쓴다
            if (!nodeEmitted) writeNodeSection(out, mesh, useMappedPositions);
            if (!elemEmitted) writeElementSection(out, mesh);
            writeEnd(out);
        }
        (void)endSuppressed;

        // 쓰기 · 닫기 실패(디스크 참 · 파일 크기 상한)면 잘린 덱이다 — 성공이라 하지 않는다(여섯째 검토 S2)
        if (!writer.close()) {
            errorMessage_ = "덱을 쓰다 멈췄다: " + writer.error();
            return false;
        }
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
    if (!secondOrderWritable(mesh, errorMessage_)) return false;
    if (!readerLossWritable(mesh, errorMessage_)) return false;

    if (!idsFitField(mesh, idFieldWidth_, /*shellsFromMesh=*/verbatimShellSource_.empty(), errorMessage_)) return false;
    // 셸 블록을 옮겨 올 덱은 산출을 만들기 전에 연다 — 못 열면 빈 산출을 남기지 않는다
    std::ifstream shellSrc;
    if (!verbatimShellSource_.empty()) {
        shellSrc.open(verbatimShellSource_);
        if (!shellSrc.is_open()) {
            errorMessage_ = "셸 블록을 옮겨 올 덱을 열 수 없다: " + verbatimShellSource_;
            return false;
        }
    }

    // 원본 덱이 없는 경로 — 호출자가 setNewline 으로 정해 준 개행을 쓴다(기본 LF).
    DeckWriter writer(filename, newline_);
    if (!writer.ok()) {
        errorMessage_ = "Cannot create file: " + filename;
        return false;
    }
    std::ostream& file = writer.stream();

    try {
        // ★이 경로는 메시 하나로 **덱 전체를 지어낸다** — 원본이 없으니 `*KEYWORD` 도
        //   아무도 안 준다. 빠지면 LS-DYNA 가 키워드 덱으로 안 읽는다.
        //   `includeHeader_` 밖에 둔다(위와 같은 이유). DynainWriter·IGA·surface_extract 와
        //   같은 차례 — 카드가 먼저, `$` 머리말이 뒤다.
        //   본문을 쓰는 그 폭을 선언한다 — 10칸 · 20칸 본문 위에 맨 `*KEYWORD` 를 쓰면 LS-DYNA 가 8칸으로 읽는다(2026-11-21)
        file << (idFieldWidth_ >= 20 ? "*KEYWORD LONG=Y\n" : idFieldWidth_ == 10 ? "*KEYWORD I10=Y\n" : "*KEYWORD\n");
        if (includeHeader_) {
            writeHeader(file);
        }

        writeNodeSection(file, mesh, useMappedPositions);
        writeElementSection(file, mesh);
        // 셸 · 두께 셸은 제 키워드로(예전엔 `*ELEMENT_SOLID` 에 섞였다) — 옮겨 올 덱이 있으면 그 블록을 줄째 옮긴다
        if (verbatimShellSource_.empty()) writeShellSections(file, mesh);
        else copyShellBlocks(file, shellSrc);
        writeEnd(file);

        if (!writer.close()) {   // 쓰기 · 닫기 실패면 잘린 덱이다(여섯째 검토 S2)
            errorMessage_ = "덱을 쓰다 멈췄다: " + writer.error();
            return false;
        }
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

        file << std::setw(idFieldWidth_) << node.id
             << formatDouble(pos.x)
             << formatDouble(pos.y)
             << formatDouble(pos.z);
        // TC/RC 는 **둘 중 하나라도 0 이 아닐 때만** 낸다. 그래야 구속이 없는 덱의 출력
        // 바이트가 그대로 남는다(전 op sha256 불변 관문을 깨지 않는다).
        if (node.tc != 0 || node.rc != 0)
            file << std::setw(idFieldWidth_) << node.tc << std::setw(idFieldWidth_) << node.rc;
        file << std::endl;
    }
}

void KFileWriter::writeElementSection(std::ostream& file, const Mesh& mesh) {
    // Sort elements by ID
    std::vector<std::pair<int, const Element*>> sortedElements;
    for (const auto& [id, elem] : mesh.elements) {
        // 셸(QUAD4) · 두께 셸은 솔리드 블록에 쓰지 않는다 — 원본이 있으면 그 블록을 그대로 베끼고, 없으면 `writeShellSections` 가 제
        // 키워드로 쓴다(2026-11-08 — 셸은 n5-n8 = n1-n4 인 겹친 육면체로, 두께 셸은 솔리드로 나갔다)
        if (elem.type == ElementType::QUAD4 || mesh.thickShellIds.count(id)) continue;
        sortedElements.push_back({id, &elem});
    }
    // 쉘만 있는 덱이면 쓸 솔리드가 하나도 없다 — 빈 *ELEMENT_SOLID 블록을 남기지 않는다
    if (sortedElements.empty()) return;
    std::sort(sortedElements.begin(), sortedElements.end(),
              [](const auto& a, const auto& b) { return a.first < b.first; });

    file << "*ELEMENT_SOLID" << std::endl;

    // ★2차 솔리드가 하나라도 있으면 블록 전체를 **표준 두 카드 꼴**로 쓴다 — Card 1 = EID PID · Card 2 이후 = 절점 열 칸씩
    //   (Vol_I 163572-163667). 아래 한 줄 꼴(EID PID N1..N8)은 4-8절점 요소만 받는 옛 꼴이다(Remark 4) — 2차 요소를 그
    //   꼴로 쓰면 중간절점이 사라진다(2026-10-17 전에는 TET10 이 앞 8칸만 써졌다). 한 블록에 두 꼴을 섞지 않는다.
    bool anySecond = false;
    for (const auto& [id, elemPtr] : sortedElements)
        if (mesh.allNodesOf(id) || elemPtr->type == ElementType::TET10) { anySecond = true; break; }
    if (anySecond) {
        file << "$#" << std::setw(idFieldWidth_ - 2) << "eid" << std::setw(idFieldWidth_) << "pid" << std::endl;
        for (const auto& [id, elemPtr] : sortedElements) {
            const Element& elem = *elemPtr;
            file << std::setw(idFieldWidth_) << elem.id << std::setw(idFieldWidth_) << elem.partId << std::endl;
            std::vector<int> nodes;
            if (const auto* all = mesh.allNodesOf(id)) nodes = *all;
            else if (elem.type == ElementType::TET4)
                nodes = {elem.nodeIds[0], elem.nodeIds[1], elem.nodeIds[2], elem.nodeIds[3],
                         elem.nodeIds[3], elem.nodeIds[3], elem.nodeIds[3], elem.nodeIds[3]};
            else nodes.assign(elem.nodeIds.begin(), elem.nodeIds.end());
            for (size_t k = 0; k < nodes.size(); ++k) {
                file << std::setw(idFieldWidth_) << nodes[k];
                if (k % 10 == 9 || k + 1 == nodes.size()) file << std::endl;
            }
        }
        return;
    }

    // 주석 눈금도 칸 폭을 따라야 한다 — 10칸 덱에 8칸 눈금을 달면 사람이 칸을 잘못 센다.
    {
        static const char* const kCols[10] = {"eid", "pid", "n1", "n2", "n3",
                                              "n4", "n5", "n6", "n7", "n8"};
        std::ostringstream hdr;
        hdr << "$#";
        for (int c = 0; c < 10; ++c)
            hdr << std::setw(c == 0 ? idFieldWidth_ - 2 : idFieldWidth_) << kCols[c];
        file << hdr.str() << std::endl;
    }

    for (const auto& [id, elemPtr] : sortedElements) {
        const Element& elem = *elemPtr;

        file << std::setw(idFieldWidth_) << elem.id
             << std::setw(idFieldWidth_) << elem.partId;

        if (elem.type == ElementType::TET4) {
            // TET4: write 4 nodes, then repeat n4 for n5-n8 (LS-DYNA convention)
            for (int i = 0; i < 4; ++i) {
                file << std::setw(idFieldWidth_) << elem.nodeIds[i];
            }
            for (int i = 4; i < 8; ++i) {
                file << std::setw(idFieldWidth_) << elem.nodeIds[3];  // Repeat n4
            }
        } else {
            // HEX8 and others: write all 8 nodes
            for (int i = 0; i < Element::NUM_NODES; ++i) {
                file << std::setw(idFieldWidth_) << elem.nodeIds[i];
            }
        }
        file << std::endl;
    }
}

void KFileWriter::writeShellSections(std::ostream& file, const Mesh& mesh) {
    std::vector<const Element*> shells, tshells;
    for (const auto& [id, elem] : mesh.elements) {
        if (elem.type == ElementType::QUAD4) shells.push_back(&elem);
        else if (mesh.thickShellIds.count(id)) tshells.push_back(&elem);
    }
    if (!shells.empty()) {
        file << "*ELEMENT_SHELL" << std::endl;
        for (const Element* e : shells) {
            file << std::setw(idFieldWidth_) << e->id << std::setw(idFieldWidth_) << e->partId;
            for (int i = 0; i < 4; ++i) file << std::setw(idFieldWidth_) << e->nodeIds[i];
            file << std::endl;
        }
    }
    if (!tshells.empty()) {
        file << "*ELEMENT_TSHELL" << std::endl;
        for (const Element* e : tshells) {
            file << std::setw(idFieldWidth_) << e->id << std::setw(idFieldWidth_) << e->partId;
            for (int i = 0; i < Element::NUM_NODES; ++i) file << std::setw(idFieldWidth_) << e->nodeIds[i];
            file << std::endl;
        }
    }
}

void KFileWriter::copyShellBlocks(std::ostream& file, std::istream& src) {
    bool copying = false;
    std::string line;
    while (std::getline(src, line)) {
        if (!line.empty() && line.back() == '\r') line.pop_back();
        if (isKeywordLine(line)) {
            const std::string name = gridReaderKeywordName(line);
            if (name == "END") break;   // 리더도 첫 `*END` 에서 멈춘다
            copying = gridReaderReadsKeyword(line) &&
                      (name.rfind("ELEMENT_SHELL", 0) == 0 || name.rfind("ELEMENT_TSHELL", 0) == 0);
        }
        if (copying) file << line << "\n";
    }
}

void KFileWriter::writeEnd(std::ostream& file) {
    file << "*END" << std::endl;
}

std::string KFileWriter::formatDouble(double value) const {
    std::ostringstream oss;
    oss << std::setw(realFieldWidth(idFieldWidth_))   // 실수 칸도 덱 폭을 따른다 — 20칸 덱은 20, 그 밖은 16
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
