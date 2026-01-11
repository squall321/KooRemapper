#pragma once

#include "core/Mesh.h"
#include <string>
#include <fstream>

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
