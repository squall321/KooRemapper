#pragma once

#include "core/Mesh.h"
#include "parser/DeckWriter.h"
#include <string>
#include <fstream>
#include <vector>

// Knowledge graph (lat.md):
//   @lat: [[modules/parser]]

namespace KooRemapper {

/**
 * Writer for LS-DYNA keyword (.k) files
 */
class KFileWriter {
public:
    KFileWriter();
    ~KFileWriter() = default;

    /**
     * Write mesh to a k-file
     * @param filename Output file path
     * @param mesh Mesh to write
     * @param useMappedPositions If true, use mapped positions instead of original
     * @return true on success
     */
    bool writeFile(const std::string& filename, const Mesh& mesh,
                   bool useMappedPositions = true);

    /**
     * Write mesh, preserving every non-geometry keyword from a source .k file.
     *
     * Reads `sourceFile` line by line. `*NODE` and `*ELEMENT_SOLID` blocks are
     * SKIPPED and replaced with the current mesh's data; everything else
     * (`*PART`, `*SECTION_*`, `*MAT_*`, `*CONTROL_*`, `*INCLUDE`, `*CONTACT_*`,
     * comments, blank lines) is copied verbatim. The output is a self-contained
     * LS-DYNA input that no longer needs the source file.
     *
     * `*ELEMENT_SHELL` / `*ELEMENT_TSHELL` are copied verbatim as well even
     * though KFileReader loads them into `mesh.elements`; those elements
     * (QUAD4 · `Mesh::thickShellIds`) are left out of the emitted
     * `*ELEMENT_SOLID` block so no EID appears twice. The mesh must carry
     * that mark — the source text is not parsed a second time.
     *
     * 번호가 원본 덱이 선언한 칸 폭에 안 들어가면 쓰지 않는다(false · 산출 없음).
     *
     * Used by `map` / `shellmap` so the output `detail_bent.k` keeps the
     * material/part/section definitions that were authored on the flat
     * source, instead of producing a geometry-only stub.
     *
     * @param filename            Output file path
     * @param mesh                Mesh to write (provides new NODE/ELEMENT_SOLID)
     * @param sourceFile          .k file to copy non-geometry cards from
     * @param useMappedPositions  Use mapped positions instead of original (default true)
     * @return true on success
     */
    bool writeFileWithSource(const std::string& filename, const Mesh& mesh,
                             const std::string& sourceFile,
                             bool useMappedPositions = true);

    /**
     * Get last error message
     */
    const std::string& getErrorMessage() const { return errorMessage_; }

    /**
     * Set coordinate format precision
     */
    void setPrecision(int precision) { precision_ = precision; }

    /**
     * `*NODE`·`*ELEMENT` 의 **ID 칸 폭**(기본 8). `writeFileWithSource` 는 원본 덱의
     * `*KEYWORD` 옵션에서 자동으로 정하므로 부를 필요가 없다.
     * ⚠ 예전에는 8 로 못 박혀 있었다. 원본의 `*KEYWORD I10=Y` 는 그대로 베껴 나가므로
     * **선언은 10칸인데 본문은 8칸인 덱**이 나왔고 rc=0 이었다.
     * `writeFile` 은 이 폭으로 `*KEYWORD`(맨 것 · `I10=Y` · `LONG=Y`)도 쓴다. 실수 칸은 폭 20 이면 20, 그 밖은 16 이다.
     */
    void setIdFieldWidth(int width) { idFieldWidth_ = width; }

    /**
     * `writeFile` 이 셸 · 두께 셸 블록을 메시에서 짓지 않고 이 덱에서 **줄째 옮긴다** — 리더가 메시에 담는 `*ELEMENT_SHELL*` ·
     * `*ELEMENT_TSHELL` 블록만(`gridReaderReadsKeyword`), 첫 `*END` 앞까지. 메시는 셸을 4절점 · 파트 번호로만 담아 8절점 셸의
     * 중간절점 · `_THICKNESS` 의 두께 카드 · 옵션 변형의 키워드를 되쓸 수 없다(2026-11-21 — tetremesh 가 그것들을 rc 0 으로 잃었다).
     * 부르는 쪽이 메시의 셸이 그 덱에서 읽은 그대로임을 지킨다.
     */
    void setVerbatimShellSource(const std::string& path) { verbatimShellSource_ = path; }

    /**
     * 그렇게 쓴 뒤 — 그 덱의 격자 족(솔리드 · 셸 · 두께 셸) 블록 가운데 리더가 읽지 않아(`gridReaderReadsKeyword`) 메시에도 산출에도
     * **없는** 변형. 빔 같은 격자 밖 족은 세지 않는다.
     * 키워드(대문자 · 접미사 뗌)마다 블록 수와 데이터 줄 수(주석 · 빈 줄은 뺀다)를 처음 나온 차례로 준다 — 부르는 쪽이 경고로 찍는다
     * (2026-11-21 — tetremesh 가 `*ELEMENT_SHELL_COMPOSITE` · `*ELEMENT_SOLID_ORTHO` 블록을 rc 0 · 말 없이 뺐다).
     */
    struct SkippedGridVariant {
        std::string keyword;
        size_t blocks = 0;
        size_t lines = 0;
    };
    const std::vector<SkippedGridVariant>& skippedGridVariants() const { return skippedGrid_; }

    /**
     * Set whether to include header comment
     */
    void setIncludeHeader(bool include) { includeHeader_ = include; }

    /**
     * 출력 덱의 개행. `writeFileWithSource` 는 원본에서 **자동 판정**하므로 부를 필요가 없다.
     * 원본이 없는 `writeFile` 경로에서만 호출자가 정해 준다(기본 LF).
     */
    void setNewline(DeckNewline nl) { newline_ = nl; }

private:
    std::string errorMessage_;
    int precision_;
    int idFieldWidth_ = 8;
    bool includeHeader_;
    // 원본 덱의 개행. 이것이 없어서 CRLF 덱이 왕복마다 LF 로 바뀌었다.
    DeckNewline newline_ = DeckNewline::LF;
    std::string verbatimShellSource_;   // 비었으면 셸을 메시에서 짓는다
    std::vector<SkippedGridVariant> skippedGrid_;   // `copyShellBlocks` 가 센 — 리더가 안 읽는 솔리드 · 셸 · 두께 셸 변형

    void writeHeader(std::ostream& file);
    void writeNodeSection(std::ostream& file, const Mesh& mesh, bool useMappedPositions);
    void writeElementSection(std::ostream& file, const Mesh& mesh);
    void writeEnd(std::ostream& file);
    // 원본 없는 쓰기(`writeFile`)에서만 — 셸(QUAD4)은 `*ELEMENT_SHELL`(EID PID N1-N4), 두께 셸(`Mesh::thickShellIds`)은 `*ELEMENT_TSHELL`
    // (EID PID N1-N8). `writeElementSection` 은 둘 다 `*ELEMENT_SOLID` 로 쓰지 않는다(2026-11-08 — 셸이 겹친 육면체 · 두께 셸이 솔리드가 됐다)
    void writeShellSections(std::ostream& file, const Mesh& mesh);
    void copyShellBlocks(std::ostream& file, std::istream& src);   // `setVerbatimShellSource` 의 덱에서

    std::string formatDouble(double value) const;
    std::string formatInt(int value, int width) const;
};

} // namespace KooRemapper
