#pragma once

#include "core/Mesh.h"
#include <string>
#include <fstream>

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

private:
    std::string errorMessage_;
    int precision_;
    int coordFieldWidth_;
    bool includeHeader_;

    void writeHeader(std::ofstream& file);
    void writeNodeSection(std::ofstream& file, const Mesh& mesh, bool useMappedPositions);
    void writeElementSection(std::ofstream& file, const Mesh& mesh);
    void writeEnd(std::ofstream& file);

    std::string formatDouble(double value) const;
    std::string formatInt(int value, int width) const;
};

} // namespace KooRemapper
