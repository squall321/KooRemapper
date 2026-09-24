#pragma once

#include "parser/DeckNewline.h"
#include "analysis/ElementAnalyzer.h"
#include "analysis/StrainTensor.h"
#include "analysis/StressTensor.h"
#include "core/Mesh.h"
#include <string>
#include <vector>
#include <fstream>

// Knowledge graph (lat.md):
//   @lat: [[modules/parser]]

namespace KooRemapper {

/**
 * Writer for LS-DYNA dynain format
 * 
 * Outputs *INITIAL_STRESS_SOLID cards for prestress initialization
 */
class DynainWriter {
public:
    DynainWriter();
    ~DynainWriter() = default;

    /**
     * Write dynain file with initial stresses (*INITIAL_STRESS_SOLID only)
     *
     * Note: Use this dynain file with the deformed mesh, not the reference mesh.
     *
     * @param filename    Output file path
     * @param results     Element analysis results
     * @param strainType  Strain type used (for comment)
     * @param refFile     Reference mesh filename (for comment)
     * @param defFile     Deformed mesh filename (for comment)
     * @return true on success
     */
    bool writeFile(
        const std::string& filename,
        const MeshAnalysisResult& results,
        StrainType strainType,
        const std::string& refFile = "",
        const std::string& defFile = ""
    );

    /**
     * Write strain data to CSV file
     * 
     * @param filename  Output CSV path
     * @param results   Element analysis results
     * @return true on success
     */
    /**
     * 출력 dynain 의 개행. `refFile` 을 주면 거기서 자동 판정하므로 보통 부를 필요가 없다.
     */
    void setNewline(DeckNewline nl) { newline_ = nl; }

    bool writeStrainCSV(
        const std::string& filename,
        const MeshAnalysisResult& results
    );

    /**
     * Get error message if write failed
     */
    const std::string& getErrorMessage() const { return errorMessage_; }

    /**
     * Set large deformation flag (for *INITIAL_STRESS_SOLID)
     */
    void setLargeDeformation(bool large) { largeDeformation_ = large; }

private:
    // 원본 덱의 개행. 이것이 없어서 .dynain 이 늘 LF 로 나갔다(원본이 CRLF 여도).
    DeckNewline newline_ = DeckNewline::LF;
    std::string errorMessage_;
    bool largeDeformation_;

    std::string getCurrentDateTime();
};

} // namespace KooRemapper

