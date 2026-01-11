#pragma once

#include "analysis/ElementAnalyzer.h"
#include "analysis/StrainTensor.h"
#include "analysis/StressTensor.h"
#include "core/Mesh.h"
#include <string>
#include <vector>
#include <fstream>

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
     * Write dynain file with initial stresses
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
    std::string errorMessage_;
    bool largeDeformation_;

    void writeHeader(std::ofstream& file, 
                    StrainType strainType,
                    const std::string& refFile,
                    const std::string& defFile);
    
    void writeStressCard(std::ofstream& file, const ElementResult& result);
    
    std::string getCurrentDateTime();
};

} // namespace KooRemapper

