#pragma once

#include "core/Mesh.h"
#include "parser/DeckWriter.h"
#include <string>
#include <fstream>
#include <set>

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
     * though KFileReader loads them into `mesh.elements`; those EIDs are left
     * out of the emitted `*ELEMENT_SOLID` block so no EID appears twice.
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
     * Set field width for coordinates (default: 16)
     */
    void setCoordinateFieldWidth(int width) { coordFieldWidth_ = width; }

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
    int coordFieldWidth_;
    bool includeHeader_;
    // 원본 덱의 개행. 이것이 없어서 CRLF 덱이 왕복마다 LF 로 바뀌었다.
    DeckNewline newline_ = DeckNewline::LF;

    void writeHeader(std::ostream& file);
    void writeNodeSection(std::ostream& file, const Mesh& mesh, bool useMappedPositions);
    // skipIds: EIDs whose source block is copied verbatim (shell / thick
    // shell), so they must not be re-emitted as *ELEMENT_SOLID.
    void writeElementSection(std::ostream& file, const Mesh& mesh,
                             const std::set<int>* skipIds = nullptr);
    void writeEnd(std::ostream& file);

    std::string formatDouble(double value) const;
    std::string formatInt(int value, int width) const;
};

} // namespace KooRemapper
