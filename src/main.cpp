#include "core/Platform.h"
#include "core/Mesh.h"
#include "core/ShellMesh.h"
#include "parser/KFileReader.h"
#include "parser/KFileWriter.h"
#include "parser/DynainWriter.h"
#include "parser/ShellReader.h"
#include "mapper/MeshRemapper.h"
#include "mapper/FlatMeshGenerator.h"
#include "mapper/ShellMapper.h"
#include "example/ExampleMeshGenerator.h"
#include "generator/VariableDensityConfig.h"
#include "generator/YamlConfigReader.h"
#include "generator/VariableDensityMeshGenerator.h"
#include "generator/CurvedMeshGenerator.h"
#include "analysis/StrainCalculator.h"
#include "analysis/ElementAnalyzer.h"
#include "analysis/MaterialModel.h"
#include "cli/ArgumentParser.h"
#include "cli/ConsoleOutput.h"
#include "squeeze/SqueezeConfig.h"
#include "squeeze/SqueezeConfigReader.h"
#include "assembly/AssemblyConfig.h"
#include "assembly/AssemblyConfigReader.h"
#include "assembly/ModelAssembler.h"
#include "util/Logger.h"
#include "util/Timer.h"
#include "util/Validator.h"

#include <iostream>
#include <fstream>
#include <memory>
#include <limits>
#include <sstream>
#include <iomanip>
#include <set>

using namespace KooRemapper;

// Version info
constexpr const char* VERSION = "1.1.0";

/**
 * Display program banner
 */
void printBanner(const ConsoleOutput& console) {
    console.separator('=', 60);
    console.println("  KooRemapper - Mesh Mapping Tool for LS-DYNA", ConsoleOutput::Color::BRIGHT_CYAN);
    console.println("  Version " + std::string(VERSION), ConsoleOutput::Color::CYAN);
    console.separator('=', 60);
    std::cout << "\n";
}

/**
 * Run the mapping operation
 * @param useParallel Use parallel processing (default: true)
 */
int runMapping(const std::string& bentFile, const std::string& flatFile,
               const std::string& outputFile, const ConsoleOutput& console,
               bool useParallel = true) {
    Timer timer;

    // Load bent mesh
    console.info("Loading bent mesh: " + bentFile);
    KFileReader reader;
    Mesh bentMesh;
    try {
        bentMesh = reader.readFile(bentFile);
    } catch (const std::exception& e) {
        console.error("Failed to load bent mesh: " + std::string(e.what()));
        return 1;
    }
    console.success("Loaded " + std::to_string(bentMesh.getNodeCount()) + " nodes, " +
                   std::to_string(bentMesh.getElementCount()) + " elements");

    // Validate bent mesh
    auto bentValidation = Validator::validateBentMesh(bentMesh);
    if (!bentValidation.isValid) {
        for (const auto& err : bentValidation.errors) {
            console.error(err);
        }
        return 1;
    }
    for (const auto& warn : bentValidation.warnings) {
        console.warning(warn);
    }

    // Load flat mesh
    console.info("Loading flat mesh: " + flatFile);
    Mesh flatMesh;
    try {
        flatMesh = reader.readFile(flatFile);
    } catch (const std::exception& e) {
        console.error("Failed to load flat mesh: " + std::string(e.what()));
        return 1;
    }
    console.success("Loaded " + std::to_string(flatMesh.getNodeCount()) + " nodes, " +
                   std::to_string(flatMesh.getElementCount()) + " elements");

    // Validate flat mesh
    auto flatValidation = Validator::validateFlatMesh(flatMesh);
    if (!flatValidation.isValid) {
        for (const auto& err : flatValidation.errors) {
            console.error(err);
        }
        return 1;
    }

    // Perform mapping
    std::string modeStr = useParallel ? "parallel" : "single-threaded";
    console.info("Performing mesh mapping (" + modeStr + " mode)...");
    MeshRemapper remapper;
    remapper.setBentMesh(&bentMesh);
    remapper.setFlatMesh(&flatMesh);

    // Set progress callback
    remapper.setProgressCallback([&console](int percent) {
        console.progressBar(percent);
    });

    if (!remapper.performMapping(useParallel)) {
        console.clearLine();
        console.error("Mapping failed: " + remapper.getErrorMessage());
        return 1;
    }
    console.clearLine();
    console.success("Mapping completed successfully");

    // Print statistics
    const auto& stats = remapper.getStats();
    std::cout << "\n";
    console.header("Mapping Statistics");
    console.keyValue("Nodes processed", std::to_string(stats.nodesProcessed));
    console.keyValue("Elements processed", std::to_string(stats.elementsProcessed));
    console.keyValue("Min Jacobian", std::to_string(stats.minJacobian));
    console.keyValue("Max Jacobian", std::to_string(stats.maxJacobian));
    console.keyValue("Avg Jacobian", std::to_string(stats.avgJacobian));
    if (stats.invalidElements > 0) {
        console.warning("Invalid elements (negative Jacobian): " +
                       std::to_string(stats.invalidElements));
    }
    console.keyValue("Processing time", std::to_string(stats.processingTimeMs) + " ms");
    std::cout << "\n";

    // Write output (use mapped positions)
    console.info("Writing output: " + outputFile);
    KFileWriter writer;
    if (!writer.writeFile(outputFile, remapper.getResult(), true)) {
        console.error("Failed to write output: " + writer.getErrorMessage());
        return 1;
    }
    console.success("Output written successfully");

    timer.stop();
    console.info("Total time: " + timer.elapsedString());

    return 0;
}

/**
 * Run shell-based mapping operation
 */
int runShellMapping(const std::string& bentShellFile, const std::string& flatFile,
                    const std::string& outputFile, double thickness,
                    const ConsoleOutput& console) {
    Timer timer;

    // Load bent shell mesh
    console.info("Loading bent shell mesh: " + bentShellFile);
    ShellReader shellReader;
    ShellMesh bentShell;
    try {
        bentShell = shellReader.readFile(bentShellFile);
    } catch (const std::exception& e) {
        console.error("Failed to load bent shell mesh: " + std::string(e.what()));
        return 1;
    }
    console.success("Loaded " + std::to_string(bentShell.getNodeCount()) + " nodes, " +
                   std::to_string(bentShell.getElementCount()) + " shell elements");

    // Validate
    std::string validationError;
    if (!bentShell.validate(validationError)) {
        console.error("Shell mesh validation failed: " + validationError);
        return 1;
    }

    // Load flat detail mesh
    console.info("Loading flat detail mesh: " + flatFile);
    KFileReader reader;
    Mesh flatMesh;
    try {
        flatMesh = reader.readFile(flatFile);
    } catch (const std::exception& e) {
        console.error("Failed to load flat mesh: " + std::string(e.what()));
        return 1;
    }
    console.success("Loaded " + std::to_string(flatMesh.getNodeCount()) + " nodes, " +
                   std::to_string(flatMesh.getElementCount()) + " elements");

    // Auto-detect thickness from flat mesh Z-range if not specified
    if (thickness <= 0.0) {
        auto [bbMin, bbMax] = flatMesh.getBoundingBox();
        thickness = bbMax.z - bbMin.z;
        if (thickness < 1e-15) {
            // Shell detail (no Z extent) - set thickness to 0
            thickness = 0.0;
            console.info("Detail mesh appears to be a shell (no Z extent)");
        } else {
            console.info("Auto-detected thickness from Z-range: " + std::to_string(thickness));
        }
    } else {
        console.info("Using specified thickness: " + std::to_string(thickness));
    }

    // Build shell mapper
    console.info("Unfolding shell mesh and building mapper...");
    ShellMapper mapper;
    if (!mapper.build(bentShell)) {
        console.error("Failed to build shell mapper: " + mapper.getErrorMessage());
        return 1;
    }

    // Report unfolding results
    const auto& unfolder = mapper.getUnfolder();
    std::cout << "\n";
    console.header("Shell Unfolding Results");
    console.keyValue("Flat extent X", std::to_string(unfolder.getTotalLengthX()));
    console.keyValue("Flat extent Y", std::to_string(unfolder.getTotalLengthY()));
    console.keyValue("Max distortion", std::to_string(unfolder.getMaxDistortion() * 100.0) + "%");
    console.keyValue("Avg distortion", std::to_string(unfolder.getAvgDistortion() * 100.0) + "%");

    if (unfolder.getMaxDistortion() > 0.05) {
        console.warning("High area distortion detected (>" + std::to_string(5.0) +
                       "%). Surface may not be developable.");
    }
    std::cout << "\n";

    // Perform mapping (auto-aligns flat detail BB to unfolded shell BB)
    console.info("Mapping flat mesh onto bent shell...");
    Mesh resultMesh;
    if (!mapper.mapMesh(flatMesh, resultMesh, thickness)) {
        console.error("Mapping failed: " + mapper.getErrorMessage());
        return 1;
    }

    if (mapper.isAxesSwapped()) {
        console.info("Auto-alignment: axes swapped (flat X<->Y) to match unfolded shell");
    }

    int unmapped = mapper.getUnmappedCount();
    if (unmapped > 0) {
        console.warning(std::to_string(unmapped) + " nodes could not be mapped (outside shell domain)");
    }
    console.success("Mapping completed: " + std::to_string(flatMesh.getNodeCount()) + " nodes mapped");

    // Write output
    console.info("Writing output: " + outputFile);
    KFileWriter writer;
    if (!writer.writeFile(outputFile, resultMesh, true)) {
        console.error("Failed to write output: " + writer.getErrorMessage());
        return 1;
    }
    console.success("Output written successfully");

    timer.stop();
    console.info("Total time: " + timer.elapsedString());

    return 0;
}

/**
 * Generate example meshes
 */
int runGenerate(const std::string& type, const std::string& outputPrefix,
                int dimI, int dimJ, int dimK, const ConsoleOutput& console) {
    console.info("Generating example meshes...");

    ExampleMeshConfig config;
    config.dimI = dimI;
    config.dimJ = dimJ;
    config.dimK = dimK;

    // Parse type
    if (type == "teardrop") {
        config.bentType = BentMeshType::TEARDROP;
    } else if (type == "arc") {
        config.bentType = BentMeshType::ARC;
    } else if (type == "scurve") {
        config.bentType = BentMeshType::S_CURVE;
    } else if (type == "helix") {
        config.bentType = BentMeshType::HELIX;
    } else if (type == "torus") {
        config.bentType = BentMeshType::TORUS;
    } else if (type == "twist") {
        config.bentType = BentMeshType::TWIST;
    } else if (type == "bendtwist") {
        config.bentType = BentMeshType::BEND_TWIST;
    } else if (type == "wave") {
        config.bentType = BentMeshType::WAVE;
    } else if (type == "bulge") {
        config.bentType = BentMeshType::BULGE;
    } else if (type == "taper") {
        config.bentType = BentMeshType::TAPER;
    } else if (type == "waterdrop") {
        config.bentType = BentMeshType::WATERDROP;
        // 폴더블 디스플레이 치수: 길이 160mm, 폭 70mm, 두께 1mm
        config.lengthI = 160.0;  // 길이 (접히는 방향)
        config.lengthJ = 70.0;   // 폭 (넓은 방향)
        config.lengthK = 1.0;    // 두께 (얇음)
        config.waterdropFoldRadius = 2.0;  // U자 반경 2mm
        config.waterdropFlatRatio = 0.45;  // 양쪽 45%씩 평평, 중간 10%가 U자
    } else {
        console.error("Unknown mesh type: " + type);
        console.info("Valid types: teardrop, arc, scurve, helix, torus, twist, bendtwist, wave, bulge, taper, waterdrop");
        return 1;
    }

    ExampleMeshGenerator generator;

    // Generate bent mesh
    std::string bentFile = outputPrefix + "_bent.k";
    console.info("Generating bent mesh (" + type + ")...");
    Mesh bentMesh = generator.generateBentMesh(config);
    console.success("Generated " + std::to_string(bentMesh.getNodeCount()) + " nodes, " +
                   std::to_string(bentMesh.getElementCount()) + " elements");

    KFileWriter writer;
    if (!writer.writeFile(bentFile, bentMesh)) {
        console.error("Failed to write bent mesh: " + writer.getErrorMessage());
        return 1;
    }
    console.success("Written: " + bentFile);

    // Generate flat mesh
    std::string flatFile = outputPrefix + "_flat.k";
    console.info("Generating flat mesh...");
    Mesh flatMesh = generator.generateFlatMesh(config);
    console.success("Generated " + std::to_string(flatMesh.getNodeCount()) + " nodes, " +
                   std::to_string(flatMesh.getElementCount()) + " elements");

    if (!writer.writeFile(flatFile, flatMesh)) {
        console.error("Failed to write flat mesh: " + writer.getErrorMessage());
        return 1;
    }
    console.success("Written: " + flatFile);

    // Generate fine flat mesh for mapping test
    std::string fineFile = outputPrefix + "_flat_fine.k";
    console.info("Generating refined flat mesh for mapping test...");
    Mesh fineMesh = generator.generateFlatUnstructuredMesh(config, 2);
    console.success("Generated " + std::to_string(fineMesh.getNodeCount()) + " nodes, " +
                   std::to_string(fineMesh.getElementCount()) + " elements");

    if (!writer.writeFile(fineFile, fineMesh)) {
        console.error("Failed to write fine mesh: " + writer.getErrorMessage());
        return 1;
    }
    console.success("Written: " + fineFile);

    // Generate tetrahedral flat mesh for mapping test
    std::string tetFile = outputPrefix + "_flat_tet.k";
    console.info("Generating tetrahedral flat mesh for mapping test...");
    Mesh tetMesh = generator.generateFlatTetMesh(config);
    console.success("Generated " + std::to_string(tetMesh.getNodeCount()) + " nodes, " +
                   std::to_string(tetMesh.getElementCount()) + " elements (TET4)");

    if (!writer.writeFile(tetFile, tetMesh)) {
        console.error("Failed to write tet mesh: " + writer.getErrorMessage());
        return 1;
    }
    console.success("Written: " + tetFile);

    std::cout << "\n";
    console.info("Example usage for mapping:");
    console.println("  KooRemapper map " + bentFile + " " + fineFile + " " +
                   outputPrefix + "_mapped.k");
    console.println("  KooRemapper map " + bentFile + " " + tetFile + " " +
                   outputPrefix + "_mapped_tet.k");

    return 0;
}

/**
 * Calculate strain between two meshes
 */
int runStrain(const std::string& refFile, const std::string& defFile,
              const std::string& outputFile, const std::string& strainType,
              const ConsoleOutput& console) {
    Timer timer;

    // Load reference mesh
    console.info("Loading reference mesh: " + refFile);
    KFileReader reader;
    Mesh refMesh;
    try {
        refMesh = reader.readFile(refFile);
    } catch (const std::exception& e) {
        console.error("Failed to load reference mesh: " + std::string(e.what()));
        return 1;
    }
    console.success("Loaded " + std::to_string(refMesh.getNodeCount()) + " nodes, " +
                   std::to_string(refMesh.getElementCount()) + " elements");

    // Load deformed mesh
    console.info("Loading deformed mesh: " + defFile);
    Mesh defMesh;
    try {
        defMesh = reader.readFile(defFile);
    } catch (const std::exception& e) {
        console.error("Failed to load deformed mesh: " + std::string(e.what()));
        return 1;
    }
    console.success("Loaded " + std::to_string(defMesh.getNodeCount()) + " nodes, " +
                   std::to_string(defMesh.getElementCount()) + " elements");

    // Setup strain calculator
    StrainCalculator calc;
    calc.setReferenceMesh(&refMesh);
    calc.setDeformedMesh(&defMesh);

    // Set strain type
    if (strainType == "engineering") {
        calc.setStrainType(StrainCalculator::StrainType::ENGINEERING);
    } else if (strainType == "green") {
        calc.setStrainType(StrainCalculator::StrainType::GREEN_LAGRANGE);
    } else if (strainType == "log") {
        calc.setStrainType(StrainCalculator::StrainType::LOGARITHMIC);
    }

    // Calculate strains
    console.info("Calculating strains...");
    if (!calc.calculate()) {
        console.error("Strain calculation failed: " + calc.getErrorMessage());
        return 1;
    }
    console.success("Strain calculation completed");

    // Get statistics
    const auto& stats = calc.getStatistics();
    std::cout << "\n";
    console.header("Strain Statistics");
    console.keyValue("Max Von Mises", std::to_string(stats.maxVonMises));
    console.keyValue("Avg Von Mises", std::to_string(stats.avgVonMises));
    console.keyValue("Max Volumetric", std::to_string(stats.maxVolumetric));
    console.keyValue("Min Volumetric", std::to_string(stats.minVolumetric));
    console.keyValue("Max Principal", std::to_string(stats.maxPrincipal));
    console.keyValue("Min Principal", std::to_string(stats.minPrincipal));
    std::cout << "\n";

    // Export to CSV
    console.info("Exporting results: " + outputFile);
    if (!calc.exportToCSV(outputFile)) {
        console.error("Failed to export results");
        return 1;
    }
    console.success("Results exported successfully");

    timer.stop();
    console.info("Total time: " + timer.elapsedString());

    return 0;
}

/**
 * Unfold a bent mesh to generate flat mesh
 */
int runUnfold(const std::string& bentFile, const std::string& outputFile,
              const ConsoleOutput& console) {
    Timer timer;

    // Load bent mesh
    console.info("Loading bent mesh: " + bentFile);
    KFileReader reader;
    Mesh bentMesh;
    try {
        bentMesh = reader.readFile(bentFile);
    } catch (const std::exception& e) {
        console.error("Failed to load bent mesh: " + std::string(e.what()));
        return 1;
    }
    console.success("Loaded " + std::to_string(bentMesh.getNodeCount()) + " nodes, " +
                   std::to_string(bentMesh.getElementCount()) + " elements");

    // Validate bent mesh
    auto bentValidation = Validator::validateBentMesh(bentMesh);
    if (!bentValidation.isValid) {
        for (const auto& err : bentValidation.errors) {
            console.error(err);
        }
        return 1;
    }
    for (const auto& warn : bentValidation.warnings) {
        console.warning(warn);
    }

    // Generate flat mesh
    console.info("Generating flat mesh from bent mesh...");
    FlatMeshGenerator generator;
    Mesh flatMesh = generator.generateFlatMesh(bentMesh);

    if (flatMesh.getNodeCount() == 0) {
        console.error("Failed to generate flat mesh: " + generator.getErrorMessage());
        return 1;
    }

    // Print dimensions
    std::cout << "\n";
    console.header("Unfolded Mesh Dimensions");
    console.keyValue("Grid size", std::to_string(generator.getDimI()) + " x " +
                                  std::to_string(generator.getDimJ()) + " x " +
                                  std::to_string(generator.getDimK()));
    console.keyValue("Flat length (I)", std::to_string(generator.getFlatLengthI()) + " (arc-length)");
    console.keyValue("Flat length (J)", std::to_string(generator.getFlatLengthJ()));
    console.keyValue("Flat length (K)", std::to_string(generator.getFlatLengthK()));
    std::cout << "\n";

    console.success("Generated " + std::to_string(flatMesh.getNodeCount()) + " nodes, " +
                   std::to_string(flatMesh.getElementCount()) + " elements");

    // Write output
    console.info("Writing output: " + outputFile);
    KFileWriter writer;
    if (!writer.writeFile(outputFile, flatMesh)) {
        console.error("Failed to write output: " + writer.getErrorMessage());
        return 1;
    }
    console.success("Output written successfully");

    timer.stop();
    console.info("Total time: " + timer.elapsedString());

    std::cout << "\n";
    console.info("Usage hint:");
    console.println("  Use this flat mesh as reference for mapping a detailed flat mesh:");
    console.println("  KooRemapper map " + bentFile + " <detailed_flat.k> <output_bent.k>");

    return 0;
}

/**
 * Calculate prestress from deformed configuration
 */
int runPrestress(const std::string& refFile, const std::string& defFile,
                 const std::string& outputFile, 
                 double E, double nu,
                 StrainType strainType,
                 bool outputCSV,
                 const ConsoleOutput& console) {
    Timer timer;

    // Load reference mesh
    console.info("Loading reference mesh: " + refFile);
    KFileReader reader;
    Mesh refMesh;
    try {
        refMesh = reader.readFile(refFile);
    } catch (const std::exception& e) {
        console.error("Failed to load reference mesh: " + std::string(e.what()));
        return 1;
    }
    console.success("Loaded " + std::to_string(refMesh.getNodeCount()) + " nodes, " +
                   std::to_string(refMesh.getElementCount()) + " elements");
    
    // Report materials found in K-file (per-part)
    const auto& parts = refMesh.getParts();
    const auto& materials = refMesh.getMaterials();

    if (!parts.empty()) {
        console.info("Part-Material mapping:");
        int missingMaterialCount = 0;
        for (const auto& [partId, part] : parts) {
            auto matIt = materials.find(part.materialId);
            if (matIt != materials.end()) {
                std::ostringstream oss;
                oss << std::scientific << std::setprecision(4);
                oss << "  Part " << partId << " -> Material " << part.materialId
                    << ": E=" << matIt->second.E << ", nu=" << std::fixed << std::setprecision(4) << matIt->second.nu;
                console.println(oss.str());
            } else {
                console.warning("  Part " + std::to_string(partId) + " -> Material " +
                              std::to_string(part.materialId) + ": NOT FOUND");
                missingMaterialCount++;
            }
        }
        if (missingMaterialCount > 0) {
            console.warning(std::to_string(missingMaterialCount) + " part(s) have missing materials - stress will be 0");
        }
    } else if (refMesh.getMaterialCount() > 0) {
        // No parts but have materials (unusual case)
        console.info("Found " + std::to_string(refMesh.getMaterialCount()) + " material(s) in K-file:");
        for (const auto& [matId, mat] : materials) {
            std::ostringstream oss;
            oss << std::scientific << std::setprecision(4);
            oss << "  Material " << matId << ": E=" << mat.E
                << ", nu=" << std::fixed << std::setprecision(4) << mat.nu;
            console.println(oss.str());
        }
    }

    // Load deformed mesh
    console.info("Loading deformed mesh: " + defFile);
    Mesh defMesh;
    try {
        defMesh = reader.readFile(defFile);
    } catch (const std::exception& e) {
        console.error("Failed to load deformed mesh: " + std::string(e.what()));
        return 1;
    }
    console.success("Loaded " + std::to_string(defMesh.getNodeCount()) + " nodes, " +
                   std::to_string(defMesh.getElementCount()) + " elements");

    // Validate mesh pair
    std::string validationError;
    if (!ElementAnalyzer::validateMeshPair(refMesh, defMesh, validationError)) {
        console.error("Mesh pair validation failed: " + validationError);
        return 1;
    }

    // Setup analyzer
    console.info("Analyzing strain/stress...");
    ElementAnalyzer analyzer;
    analyzer.setStrainType(strainType);
    analyzer.setUsePartMaterials(true);  // Enable per-part material lookup

    // Check if we have materials from command line or K-file
    bool hasCmdLineMaterial = (E > 0 && nu > 0 && nu < 0.5);
    bool hasKFileMaterial = (refMesh.getMaterialCount() > 0);
    bool hasMaterial = hasCmdLineMaterial || hasKFileMaterial;
    
    if (hasCmdLineMaterial) {
        // Command line material overrides K-file materials completely
        MaterialModel material = MaterialModel::isotropicElastic(E, nu);
        analyzer.setMaterial(material);
        analyzer.setUsePartMaterials(false);  // Disable per-part lookup
        console.info("Using command-line material: E=" + std::to_string(E) + ", nu=" + std::to_string(nu));
        if (hasKFileMaterial) {
            console.info("(K-file materials are overridden)");
        }
    } else if (hasKFileMaterial) {
        analyzer.setUsePartMaterials(true);  // Enable per-part lookup
        console.info("Using materials from K-file (per-part)");
    } else {
        console.info("No material specified, computing strain only");
    }

    // Run analysis with progress
    MeshAnalysisResult results = analyzer.analyzeMesh(refMesh, defMesh, 
        [&console](int percent) {
            console.progressBar(percent);
        });
    console.clearLine();
    console.success("Analysis completed");

    // Print statistics
    std::cout << "\n";
    console.header("Analysis Results");
    console.keyValue("Valid elements", std::to_string(results.validElements));
    if (results.invalidElements > 0) {
        console.warning("Invalid elements: " + std::to_string(results.invalidElements));
    }
    
    console.keyValue("Strain type", 
        strainType == StrainType::ENGINEERING ? "Engineering" : "Green-Lagrange");
    console.keyValue("Min von Mises strain", std::to_string(results.minVonMisesStrain));
    console.keyValue("Max von Mises strain", std::to_string(results.maxVonMisesStrain));
    console.keyValue("Avg von Mises strain", std::to_string(results.avgVonMisesStrain));

    if (hasMaterial) {
        std::cout << "\n";
        std::ostringstream ossMin, ossMax, ossAvg;
        ossMin << std::scientific << std::setprecision(6) << results.minVonMisesStress;
        ossMax << std::scientific << std::setprecision(6) << results.maxVonMisesStress;
        ossAvg << std::scientific << std::setprecision(6) << results.avgVonMisesStress;
        console.keyValue("Min von Mises stress", ossMin.str());
        console.keyValue("Max von Mises stress", ossMax.str());
        console.keyValue("Avg von Mises stress", ossAvg.str());
    }
    std::cout << "\n";

    // Write output
    DynainWriter writer;
    writer.setLargeDeformation(strainType == StrainType::GREEN_LAGRANGE);

    if (hasMaterial) {
        console.info("Writing dynain file: " + outputFile);
        if (!writer.writeFile(outputFile, results, strainType, refFile, defFile)) {
            console.error("Failed to write dynain: " + writer.getErrorMessage());
            return 1;
        }
        console.success("Dynain file written successfully");

        // Create a copy of deformed mesh with *INCLUDE for dynain
        // The dynain contains stress-only data, meant to be used with deformed mesh
        // Output filename: same as dynain but with .k extension
        std::string meshOutputFile = outputFile;
        size_t dotPos = meshOutputFile.rfind('.');
        if (dotPos != std::string::npos) {
            meshOutputFile = meshOutputFile.substr(0, dotPos) + ".k";
        } else {
            meshOutputFile += ".k";
        }

        // Get just the dynain filename (not full path) for *INCLUDE
        std::string dynainFilename = outputFile;
        size_t slashPos = dynainFilename.find_last_of("/\\");
        if (slashPos != std::string::npos) {
            dynainFilename = dynainFilename.substr(slashPos + 1);
        }

        // Read deformed mesh file and append *INCLUDE
        std::ifstream srcFile(defFile, std::ios::binary);
        if (!srcFile.is_open()) {
            console.error("Failed to read deformed mesh for copy");
            return 1;
        }

        std::ofstream dstFile(meshOutputFile, std::ios::binary);
        if (!dstFile.is_open()) {
            console.error("Failed to create mesh output file: " + meshOutputFile);
            srcFile.close();
            return 1;
        }

        // Copy original content
        std::string line;
        bool endFound = false;
        while (std::getline(srcFile, line)) {
            // Check for *END keyword
            std::string trimmedLine = line;
            // Remove leading whitespace
            size_t start = trimmedLine.find_first_not_of(" \t");
            if (start != std::string::npos) {
                trimmedLine = trimmedLine.substr(start);
            }
            // Check if it's *END
            if (trimmedLine.length() >= 4 &&
                (trimmedLine[0] == '*') &&
                (trimmedLine[1] == 'E' || trimmedLine[1] == 'e') &&
                (trimmedLine[2] == 'N' || trimmedLine[2] == 'n') &&
                (trimmedLine[3] == 'D' || trimmedLine[3] == 'd')) {
                // Insert *INCLUDE before *END
                dstFile << "*INCLUDE\n";
                dstFile << dynainFilename << "\n";
                endFound = true;
            }
            dstFile << line << "\n";
        }

        // If no *END found, append *INCLUDE at the end
        if (!endFound) {
            dstFile << "*INCLUDE\n";
            dstFile << dynainFilename << "\n";
            dstFile << "*END\n";
        }

        srcFile.close();
        dstFile.close();

        console.success("Deformed mesh with prestress: " + meshOutputFile);
    }

    // Write CSV if requested or if no material
    if (outputCSV || !hasMaterial) {
        std::string csvFile = outputFile;
        if (hasMaterial) {
            // Change extension to .csv
            size_t dotPos = csvFile.rfind('.');
            if (dotPos != std::string::npos) {
                csvFile = csvFile.substr(0, dotPos) + ".csv";
            } else {
                csvFile += ".csv";
            }
        }

        console.info("Writing CSV file: " + csvFile);
        if (!writer.writeStrainCSV(csvFile, results)) {
            console.error("Failed to write CSV: " + writer.getErrorMessage());
            return 1;
        }
        console.success("CSV file written successfully");
    }

    timer.stop();
    console.info("Total time: " + timer.elapsedString());

    return 0;
}

/**
 * Display mesh info
 */
int runInfo(const std::string& meshFile, const ConsoleOutput& console) {
    console.info("Loading mesh: " + meshFile);

    KFileReader reader;
    Mesh mesh;
    try {
        mesh = reader.readFile(meshFile);
    } catch (const std::exception& e) {
        console.error("Failed to load mesh: " + std::string(e.what()));
        return 1;
    }

    console.header("Mesh Information: " + Platform::getFilename(meshFile));

    console.keyValue("Name", mesh.getName());
    console.keyValue("Nodes", std::to_string(mesh.getNodeCount()));
    console.keyValue("Elements", std::to_string(mesh.getElementCount()));
    console.keyValue("Parts", std::to_string(mesh.getPartCount()));

    // Bounding box
    auto [minBound, maxBound] = mesh.getBoundingBox();
    console.keyValue("Min bound", minBound.toString());
    console.keyValue("Max bound", maxBound.toString());

    Vector3D size = maxBound - minBound;
    console.keyValue("Size", size.toString());

    // Validation
    std::cout << "\n";
    console.info("Running validation...");
    auto result = Validator::validateMesh(mesh);

    if (result.isValid) {
        console.success("Mesh is valid");
    } else {
        console.error("Mesh has validation errors:");
        for (const auto& err : result.errors) {
            console.println("  - " + err, ConsoleOutput::Color::RED);
        }
    }

    for (const auto& warn : result.warnings) {
        console.warning(warn);
    }

    // Element quality check
    std::cout << "\n";
    console.info("Checking element quality...");
    double minJ = std::numeric_limits<double>::max();
    double maxJ = std::numeric_limits<double>::lowest();
    int negativeCount = 0;

    for (const auto& [id, elem] : mesh.getElements()) {
        double j = Validator::calculateJacobian(mesh, elem);
        if (j < minJ) minJ = j;
        if (j > maxJ) maxJ = j;
        if (j <= 0) negativeCount++;
    }

    console.header("Element Quality");
    console.keyValue("Min Jacobian", std::to_string(minJ));
    console.keyValue("Max Jacobian", std::to_string(maxJ));
    if (negativeCount > 0) {
        console.warning("Negative Jacobian elements: " + std::to_string(negativeCount));
    } else {
        console.success("All elements have positive Jacobian");
    }

    return 0;
}

/**
 * Generate variable density mesh from YAML config
 */
int runGenerateVar(const std::string& configFile, const std::string& outputFile,
                   const std::string& refFile, bool noScale,
                   const ConsoleOutput& console) {
    Timer timer;
    
    // Read YAML config (extended version)
    console.info("Reading configuration: " + configFile);
    YamlConfigReader yamlReader;
    ExtendedMeshConfig extConfig;
    try {
        extConfig = yamlReader.readExtendedFile(configFile);
    } catch (const std::exception& e) {
        console.error("Failed to read config: " + std::string(e.what()));
        return 1;
    }
    
    // Determine reference dimensions
    double refLengthI = 0, refLengthJ = 0, refLengthK = 0;
    
    if (!refFile.empty()) {
        // Load from command line reference file
        console.info("Loading reference mesh: " + refFile);
        KFileReader reader;
        try {
            Mesh refMesh = reader.readFile(refFile);
            auto [minB, maxB] = refMesh.getBoundingBox();
            refLengthI = maxB.x - minB.x;
            refLengthJ = maxB.y - minB.y;
            refLengthK = maxB.z - minB.z;
            console.success("Reference dimensions: " + 
                std::to_string(refLengthI) + " x " +
                std::to_string(refLengthJ) + " x " +
                std::to_string(refLengthK));
        } catch (const std::exception& e) {
            console.error("Failed to load reference: " + std::string(e.what()));
            return 1;
        }
    } else if (!extConfig.reference.flatMeshFile.empty() && !noScale) {
        // Load from config's reference file
        console.info("Loading reference mesh: " + extConfig.reference.flatMeshFile);
        KFileReader reader;
        try {
            Mesh refMesh = reader.readFile(extConfig.reference.flatMeshFile);
            auto [minB, maxB] = refMesh.getBoundingBox();
            refLengthI = maxB.x - minB.x;
            refLengthJ = maxB.y - minB.y;
            refLengthK = maxB.z - minB.z;
            console.success("Reference dimensions: " + 
                std::to_string(refLengthI) + " x " +
                std::to_string(refLengthJ) + " x " +
                std::to_string(refLengthK));
        } catch (const std::exception& e) {
            console.error("Failed to load reference: " + std::string(e.what()));
            return 1;
        }
    } else if (extConfig.reference.hasDimensions() && !noScale) {
        // Use config's direct dimensions
        refLengthI = extConfig.reference.lengthI;
        refLengthJ = extConfig.reference.lengthJ;
        refLengthK = extConfig.reference.lengthK;
        console.info("Using config dimensions: " + 
            std::to_string(refLengthI) + " x " +
            std::to_string(refLengthJ) + " x " +
            std::to_string(refLengthK));
    }
    
    Mesh mesh;
    
    // Handle based on mesh type
    if (extConfig.isCurved()) {
        // Curved mesh generation
        console.info("Generating curved mesh from centerline...");
        
        CurvedMeshConfig& curvedConfig = extConfig.curvedConfig;
        
        // Validate
        std::string validationError;
        if (!curvedConfig.validate(validationError)) {
            console.error("Invalid configuration: " + validationError);
            return 1;
        }
        
        console.success("Configuration loaded (CURVED)");
        console.keyValue("Centerline points", std::to_string(curvedConfig.centerlinePoints.size()));
        console.keyValue("Elements along curve", std::to_string(curvedConfig.elementsAlongCurve));
        console.keyValue("Elements J (width)", std::to_string(curvedConfig.elementsWidth));
        console.keyValue("Elements K (thickness)", std::to_string(curvedConfig.elementsThickness));
        console.keyValue("Total elements", std::to_string(curvedConfig.getTotalElements()));
        
        CurvedMeshGenerator generator;
        generator.setProgressCallback([&console](int percent) {
            console.progressBar(percent);
        });
        
        try {
            if (refLengthI > 0) {
                mesh = generator.generate(curvedConfig, refLengthI, refLengthJ, refLengthK);
            } else {
                mesh = generator.generate(curvedConfig);
            }
        } catch (const std::exception& e) {
            console.clearLine();
            console.error("Generation failed: " + std::string(e.what()));
            return 1;
        }
        console.clearLine();
        console.success("Generated " + std::to_string(mesh.getNodeCount()) + " nodes, " +
                       std::to_string(mesh.getElementCount()) + " elements");
        
        // Print curved mesh statistics
        const auto& stats = generator.getStats();
        std::cout << "\n";
        console.header("Curved Mesh Statistics");
        console.keyValue("Arc length", std::to_string(stats.arcLength));
        console.keyValue("Scale factor", std::to_string(stats.scaleFactor));
        console.keyValue("Width", std::to_string(stats.width));
        console.keyValue("Thickness", std::to_string(stats.thickness));
        console.keyValue("Max curvature", std::to_string(stats.maxCurvature));
        console.keyValue("Min radius", std::to_string(stats.minRadius));
        std::cout << "\n";
    } else {
        // Flat variable density mesh generation
        VariableDensityConfig& config = extConfig.flatConfig;
        
        // Validate config
        std::string validationError;
        if (!config.validate(validationError)) {
            console.error("Invalid configuration: " + validationError);
            return 1;
        }
        
        console.success("Configuration loaded (FLAT)");
        console.keyValue("Total I elements", std::to_string(config.getTotalElementsI()));
        console.keyValue("J elements", std::to_string(config.elementsJ));
        console.keyValue("K elements", std::to_string(config.elementsK));
        console.keyValue("Total elements", std::to_string(config.getTotalElements()));
        
        if (refLengthI <= 0 && !noScale) {
            // No reference - use zone lengths as-is
            refLengthI = config.getTotalLength();
            refLengthJ = 1.0;  // Default
            refLengthK = 1.0;  // Default
            console.info("No scaling - using zone lengths directly");
        }
        
        // Generate mesh
        console.info("Generating variable density mesh...");
        VariableDensityMeshGenerator generator;
        generator.setProgressCallback([&console](int percent) {
            console.progressBar(percent);
        });
        
        try {
            mesh = generator.generate(config, refLengthI, refLengthJ, refLengthK);
        } catch (const std::exception& e) {
            console.clearLine();
            console.error("Generation failed: " + std::string(e.what()));
            return 1;
        }
        console.clearLine();
        console.success("Generated " + std::to_string(mesh.getNodeCount()) + " nodes, " +
                       std::to_string(mesh.getElementCount()) + " elements");
        
        // Print statistics
        const auto& stats = generator.getStats();
        std::cout << "\n";
        console.header("Generation Statistics");
        console.keyValue("Scale factor", std::to_string(stats.scaleFactor));
        std::cout << "\n";
        console.println("Zone lengths (after scaling):");
        console.keyValue("  Zone 1 (Dense Start)", std::to_string(stats.zone1Length) + 
            " (" + std::to_string(config.zone1_denseStart.numElements) + " elements)");
        console.keyValue("  Zone 2 (Increasing)", std::to_string(stats.zone2Length) +
            " (" + std::to_string(config.zone2_increasing.numElements) + " elements)");
        console.keyValue("  Zone 3 (Sparse)", std::to_string(stats.zone3Length) +
            " (" + std::to_string(config.zone3_sparse.numElements) + " elements)");
        console.keyValue("  Zone 4 (Decreasing)", std::to_string(stats.zone4Length) +
            " (" + std::to_string(config.zone4_decreasing.numElements) + " elements)");
        console.keyValue("  Zone 5 (Dense End)", std::to_string(stats.zone5Length) +
            " (" + std::to_string(config.zone5_denseEnd.numElements) + " elements)");
        std::cout << "\n";
        console.keyValue("Total length I", std::to_string(stats.totalLengthI));
        console.keyValue("Length J", std::to_string(stats.totalLengthJ));
        console.keyValue("Length K", std::to_string(stats.totalLengthK));
        std::cout << "\n";
        console.keyValue("Dense element size", std::to_string(stats.denseElementSize));
        console.keyValue("Sparse element size", std::to_string(stats.sparseElementSize));
        console.keyValue("Size ratio", std::to_string(stats.sizeRatio) + ":1");
        std::cout << "\n";
    }
    
    // Write output
    console.info("Writing output: " + outputFile);
    KFileWriter writer;
    if (!writer.writeFile(outputFile, mesh)) {
        console.error("Failed to write output: " + writer.getErrorMessage());
        return 1;
    }
    console.success("Output written successfully");
    
    timer.stop();
    console.info("Total time: " + timer.elapsedString());
    
    return 0;
}

/**
 * Squeeze: compress parts and generate reverse prestress for interference fit
 */
int runSqueeze(const std::string& meshFile, const std::string& configFile,
               const std::string& outputPrefix, const ConsoleOutput& console) {
    Timer timer;

    // Load mesh
    console.info("Loading mesh: " + meshFile);
    KFileReader reader;
    Mesh mesh;
    try {
        mesh = reader.readFile(meshFile);
    } catch (const std::exception& e) {
        console.error("Failed to load mesh: " + std::string(e.what()));
        return 1;
    }
    console.success("Loaded " + std::to_string(mesh.getNodeCount()) + " nodes, " +
                   std::to_string(mesh.getElementCount()) + " elements, " +
                   std::to_string(mesh.getPartCount()) + " parts");

    // Read squeeze config
    console.info("Reading squeeze config: " + configFile);
    SqueezeConfigReader configReader;
    SqueezeConfig config;
    try {
        config = configReader.readFile(configFile);
    } catch (const std::exception& e) {
        console.error("Failed to read config: " + std::string(e.what()));
        return 1;
    }
    console.success("Config: " + std::to_string(config.parts.size()) + " part(s) to squeeze");

    // Determine material source
    bool hasYamlMaterial = config.hasMaterial();
    bool hasKFileMaterial = (mesh.getMaterialCount() > 0);

    if (hasYamlMaterial) {
        std::ostringstream oss;
        oss << std::scientific << std::setprecision(4);
        oss << "Using YAML material: E=" << config.E << ", nu=" << std::fixed << std::setprecision(4) << config.nu;
        console.info(oss.str());
    } else if (hasKFileMaterial) {
        console.info("Using materials from K-file (per-part)");
    } else {
        console.error("No material specified (required for stress computation)");
        console.info("Add 'material:' section to YAML or include *MAT_ELASTIC in K-file");
        return 1;
    }

    // Track shared nodes
    std::set<int> allSqueezeNodes;
    int sharedNodeCount = 0;

    // Build part config map for quick lookup
    std::map<int, const PartSqueezeConfig*> partConfigMap;
    for (const auto& pc : config.parts) {
        partConfigMap[pc.pid] = &pc;
    }

    // Process each part
    std::cout << "\n";
    for (const auto& partConfig : config.parts) {
        // Check part exists in mesh
        bool partFound = false;
        for (const auto& [eid, elem] : mesh.getElements()) {
            if (elem.partId == partConfig.pid) {
                partFound = true;
                break;
            }
        }
        if (!partFound) {
            console.warning("Part " + std::to_string(partConfig.pid) + " not found in mesh, skipping");
            continue;
        }

        // Collect nodes belonging to this part
        std::set<int> partNodeIds;
        for (const auto& [eid, elem] : mesh.getElements()) {
            if (elem.partId == partConfig.pid) {
                for (int i = 0; i < Element::NUM_NODES; ++i) {
                    partNodeIds.insert(elem.nodeIds[i]);
                }
            }
        }

        // Count shared nodes
        for (int nid : partNodeIds) {
            if (allSqueezeNodes.count(nid) > 0) {
                sharedNodeCount++;
            }
        }
        allSqueezeNodes.insert(partNodeIds.begin(), partNodeIds.end());

        // Compute bounding box center (neutral plane)
        double minX = std::numeric_limits<double>::max();
        double minY = std::numeric_limits<double>::max();
        double minZ = std::numeric_limits<double>::max();
        double maxX = std::numeric_limits<double>::lowest();
        double maxY = std::numeric_limits<double>::lowest();
        double maxZ = std::numeric_limits<double>::lowest();

        for (int nid : partNodeIds) {
            const auto* node = mesh.getNode(nid);
            if (!node) continue;
            const auto& p = node->position;
            if (p.x < minX) minX = p.x;
            if (p.y < minY) minY = p.y;
            if (p.z < minZ) minZ = p.z;
            if (p.x > maxX) maxX = p.x;
            if (p.y > maxY) maxY = p.y;
            if (p.z > maxZ) maxZ = p.z;
        }

        double centerX = (minX + maxX) * 0.5;
        double centerY = (minY + maxY) * 0.5;
        double centerZ = (minZ + maxZ) * 0.5;

        // Report
        std::ostringstream oss;
        oss << std::fixed << std::setprecision(4);
        oss << "Part " << partConfig.pid << ": eps = ("
            << partConfig.eps_x << ", " << partConfig.eps_y << ", " << partConfig.eps_z << ")";
        console.info(oss.str());

        std::ostringstream oss2;
        oss2 << std::fixed << std::setprecision(3);
        oss2 << "  BB: [" << minX << ", " << minY << ", " << minZ << "] to ["
             << maxX << ", " << maxY << ", " << maxZ << "]";
        console.println(oss2.str());
        console.println("  Center: (" + std::to_string(centerX) + ", " +
                        std::to_string(centerY) + ", " + std::to_string(centerZ) + ")");
        console.println("  Nodes: " + std::to_string(partNodeIds.size()));

        // Squeeze nodes: position = center + (pos - center) * (1 + eps)
        for (int nid : partNodeIds) {
            Node* node = mesh.getNode(nid);
            if (!node) continue;
            const auto& p = node->position;

            Vector3D newPos(
                centerX + (p.x - centerX) * (1.0 + partConfig.eps_x),
                centerY + (p.y - centerY) * (1.0 + partConfig.eps_y),
                centerZ + (p.z - centerZ) * (1.0 + partConfig.eps_z)
            );
            node->setMappedPosition(newPos);
        }
    }

    if (sharedNodeCount > 0) {
        console.warning(std::to_string(sharedNodeCount) +
                       " shared nodes detected between squeeze parts");
    }

    // Write compressed mesh
    std::cout << "\n";
    std::string meshOutputFile = outputPrefix + ".k";
    console.info("Writing compressed mesh: " + meshOutputFile);
    KFileWriter writer;
    if (!writer.writeFile(meshOutputFile, mesh, true)) {
        console.error("Failed to write mesh: " + writer.getErrorMessage());
        return 1;
    }
    console.success("Compressed mesh written");

    // Build reverse prestress (MeshAnalysisResult)
    MeshAnalysisResult results;
    results.hasMaterial = true;
    results.validElements = 0;
    results.invalidElements = 0;

    for (const auto& [eid, elem] : mesh.getElements()) {
        auto it = partConfigMap.find(elem.partId);
        if (it == partConfigMap.end()) continue;  // Not a squeeze part

        const auto& pc = *(it->second);

        // Get material for this element
        double matE = 0, matNu = 0;
        if (hasYamlMaterial) {
            matE = config.E;
            matNu = config.nu;
        } else {
            const MaterialData* matData = mesh.getElementMaterial(elem);
            if (matData && matData->E > 0) {
                matE = matData->E;
                matNu = matData->nu;
            }
        }

        if (matE <= 0) {
            results.invalidElements++;
            continue;
        }

        // Reverse strain: opposite of squeeze strain
        StrainTensor reverseStrain(-pc.eps_x, -pc.eps_y, -pc.eps_z,
                                    0.0, 0.0, 0.0);

        // Compute stress via Hooke's law
        StressTensor stress = StressTensor::fromStrain(reverseStrain, matE, matNu);

        ElementResult er;
        er.elementId = elem.id;
        er.stress = stress;
        er.strain = reverseStrain;
        er.isValid = true;
        er.vonMisesStress = stress.vonMises();
        er.vonMisesStrain = reverseStrain.vonMisesStrain();

        results.elementResults.push_back(er);
        results.validElements++;
    }

    // Write dynain
    std::string dynainFile = outputPrefix + ".dynain";
    console.info("Writing dynain: " + dynainFile);
    DynainWriter dynainWriter;
    if (!dynainWriter.writeFile(dynainFile, results, StrainType::ENGINEERING,
                                meshFile, "squeeze: " + configFile)) {
        console.error("Failed to write dynain: " + dynainWriter.getErrorMessage());
        return 1;
    }
    console.success("Dynain written: " + std::to_string(results.validElements) + " elements");

    // Append *INCLUDE to compressed mesh
    {
        // Get just the dynain filename for *INCLUDE
        std::string dynainBasename = dynainFile;
        size_t slashPos = dynainBasename.find_last_of("/\\");
        if (slashPos != std::string::npos) {
            dynainBasename = dynainBasename.substr(slashPos + 1);
        }

        // Re-read the compressed mesh and insert *INCLUDE before *END
        std::ifstream srcFile(meshOutputFile);
        if (!srcFile.is_open()) {
            console.error("Failed to re-read compressed mesh");
            return 1;
        }

        std::string meshContent;
        std::string line;
        bool endFound = false;

        while (std::getline(srcFile, line)) {
            std::string trimmedLine = line;
            size_t start = trimmedLine.find_first_not_of(" \t");
            if (start != std::string::npos) {
                trimmedLine = trimmedLine.substr(start);
            }

            if (trimmedLine.length() >= 4 &&
                (trimmedLine[0] == '*') &&
                (trimmedLine[1] == 'E' || trimmedLine[1] == 'e') &&
                (trimmedLine[2] == 'N' || trimmedLine[2] == 'n') &&
                (trimmedLine[3] == 'D' || trimmedLine[3] == 'd')) {
                meshContent += "*INCLUDE\n";
                meshContent += dynainBasename + "\n";
                endFound = true;
            }
            meshContent += line + "\n";
        }
        srcFile.close();

        if (!endFound) {
            meshContent += "*INCLUDE\n";
            meshContent += dynainBasename + "\n";
            meshContent += "*END\n";
        }

        std::ofstream dstFile(meshOutputFile, std::ios::binary);
        if (!dstFile.is_open()) {
            console.error("Failed to write mesh with *INCLUDE");
            return 1;
        }
        dstFile << meshContent;
        dstFile.close();

        console.success("Added *INCLUDE to: " + meshOutputFile);
    }

    timer.stop();
    std::cout << "\n";
    console.info("Total time: " + timer.elapsedString());

    return 0;
}

/**
 * Assemble: combine operations (replace, squeeze) on a full model
 */
int runAssemble(const std::string& configFile, const ConsoleOutput& console) {
    Timer timer;

    // Determine config directory for relative paths
    std::string configDir;
    size_t slashPos = configFile.find_last_of("/\\");
    if (slashPos != std::string::npos) {
        configDir = configFile.substr(0, slashPos);
    }

    // 1. Read assembly config
    console.info("Reading assembly config: " + configFile);
    AssemblyConfigReader configReader;
    AssemblyConfig config;
    try {
        config = configReader.readFile(configFile);
    } catch (const std::exception& e) {
        console.error("Failed to read config: " + std::string(e.what()));
        return 1;
    }
    console.success("Config: " + std::to_string(config.operations.size()) + " operation(s)");

    // Resolve base model path relative to config
    std::string baseModelPath = config.baseModel;
    if (!configDir.empty() && !baseModelPath.empty() &&
        !(baseModelPath.size() >= 2 && baseModelPath[1] == ':') &&
        baseModelPath[0] != '/' && baseModelPath[0] != '\\') {
        baseModelPath = configDir + "/" + baseModelPath;
    }

    // Resolve output path
    std::string outputPrefix = config.output;
    if (!configDir.empty() && !outputPrefix.empty() &&
        !(outputPrefix.size() >= 2 && outputPrefix[1] == ':') &&
        outputPrefix[0] != '/' && outputPrefix[0] != '\\') {
        outputPrefix = configDir + "/" + outputPrefix;
    }

    // 2. Load base model
    console.info("Loading base model: " + baseModelPath);
    ModelAssembler assembler;
    assembler.setDynamicRelaxation(config.dynamicRelaxation);
    assembler.setDynainEmbed(config.dynainEmbed);
    if (!assembler.loadBaseModel(baseModelPath)) {
        console.error(assembler.getErrorMessage());
        return 1;
    }
    console.success("Loaded " + std::to_string(assembler.getNodeCount()) + " nodes, " +
                   std::to_string(assembler.getElementCount()) + " elements, " +
                   std::to_string(assembler.getPartCount()) + " parts");

    // Determine material
    double matE = config.E;
    double matNu = config.nu;

    // 3. Apply operations
    std::cout << "\n";
    for (size_t i = 0; i < config.operations.size(); ++i) {
        const auto& op = config.operations[i];

        console.info("Operation " + std::to_string(i + 1) + "/" +
                    std::to_string(config.operations.size()) + ":");

        bool ok = false;
        if (op.type == AssemblyOperation::REPLACE) {
            ok = assembler.applyReplace(op.replace, matE, matNu, configDir);
        } else if (op.type == AssemblyOperation::SQUEEZE) {
            ok = assembler.applySqueeze(op.squeeze, matE, matNu);
        } else if (op.type == AssemblyOperation::RESTACK) {
            ok = assembler.applyRestack(op.restack, matE, matNu);
        } else if (op.type == AssemblyOperation::BEND) {
            ok = assembler.applyBend(op.bend, matE, matNu, configDir);
        } else if (op.type == AssemblyOperation::INDENT) {
            ok = assembler.applyIndent(op.indent, matE, matNu);
        } else if (op.type == AssemblyOperation::FORMSTRAIN) {
            ok = assembler.applyFormStrain(op.formstrain);
        } else if (op.type == AssemblyOperation::TET10_CONVERT) {
            ok = assembler.applyTet10Convert(op.tet10);
        } else if (op.type == AssemblyOperation::REFINE) {
            ok = assembler.applyRefine(op.refine);
        } else if (op.type == AssemblyOperation::ELFORM) {
            ok = assembler.applyElform(op.elform);
        } else if (op.type == AssemblyOperation::DISCONNECT) {
            ok = assembler.applyDisconnect(op.disconnect);
        } else if (op.type == AssemblyOperation::IGA) {
            ok = assembler.applyIGA(op.iga, outputPrefix);
        } else if (op.type == AssemblyOperation::WARPAGE) {
            ok = assembler.applyWarpage(op.warpage, matE, matNu, configDir);
        } else if (op.type == AssemblyOperation::OFFSET) {
            ok = assembler.applyOffset(op.offset, matE, matNu);
        } else if (op.type == AssemblyOperation::MATSWAP) {
            ok = assembler.applyMatswap(op.matswap, configDir);
        }

        if (!ok) {
            console.error(assembler.getErrorMessage());
            return 1;
        }

        // Print info messages from assembler
        for (const auto& msg : assembler.infoMessages) {
            console.println(msg);
        }
        assembler.infoMessages.clear();
    }

    // 4. Write output
    std::cout << "\n";
    console.info("Writing output: " + outputPrefix + ".k");
    if (!assembler.writeOutput(outputPrefix)) {
        console.error(assembler.getErrorMessage());
        return 1;
    }
    console.success("Output written");

    // Summary
    if (assembler.getAddedNodeCount() > 0 || assembler.getAddedElementCount() > 0) {
        console.println("  Added: " + std::to_string(assembler.getAddedNodeCount()) +
                        " nodes, " + std::to_string(assembler.getAddedElementCount()) + " elements");
    }
    int dynainCount = static_cast<int>(assembler.getAccumulatedResults().size());
    if (dynainCount > 0) {
        std::string dynainMode = config.dynainEmbed ? " (embedded in .k)" : " (separate .dynain)";
        console.success("Dynain: " + std::to_string(dynainCount) + " elements" + dynainMode);
    }

    timer.stop();
    std::cout << "\n";
    console.info("Total time: " + timer.elapsedString());

    return 0;
}

// =============================================================
// MATSWAP: Swap material bundle in an existing LS-DYNA K file
// =============================================================
namespace {

static std::string msw_trim(const std::string& s) {
    size_t a = 0, b = s.size();
    while (a < b && std::isspace((unsigned char)s[a])) ++a;
    while (b > a && std::isspace((unsigned char)s[b-1])) --b;
    return s.substr(a, b - a);
}

static std::vector<std::string> msw_tok10(const std::string& line) {
    std::vector<std::string> v;
    for (size_t i = 0; i < line.size(); i += 10)
        v.push_back(msw_trim(line.substr(i, std::min((size_t)10, line.size()-i))));
    return v;
}

static std::string msw_upper(std::string s) {
    for (auto& c : s) c = (char)std::toupper((unsigned char)c);
    return s;
}

// Determine what kind of ID a parameter name represents (by prefix convention)
static std::string msw_idType(const std::string& name) {
    std::string u = msw_upper(name);
    if (u.size() >= 5 && u.substr(0,5) == "SECID") return "SECID";
    if (u.size() >= 4 && u.substr(0,4) == "HGID")  return "HGID";
    if (u.size() >= 4 && u.substr(0,4) == "LCID")  return "LCID";
    if (u.size() >= 3 && u.substr(0,3) == "MID")   return "MID";
    if (u.size() >= 3 && u.substr(0,3) == "PID")   return "PID";
    return "";
}

struct MswParam { char type; std::string name; int ivalue; };

struct MswBundle {
    std::vector<MswParam>     params;
    std::vector<std::string>  cards;  // all lines except *PARAMETER, *PART, *END
    int bundlePid=0, bundleSecid=0, bundleMid=0, bundleHgid=0;
};

struct MswPartInfo { int pid=0,secid=0,mid=0,hgid=0,dataLine=-1; };

// Resolve token: &VARNAME -> int from params, else stoi
static int msw_resolveInt(const std::string& tok, const std::vector<MswParam>& params) {
    if (!tok.empty() && tok[0]=='&') {
        std::string nm = msw_upper(tok.substr(1));
        for (const auto& p : params) if (msw_upper(p.name)==nm) return p.ivalue;
        return 0;
    }
    try { return std::stoi(tok); } catch(...){ return 0; }
}

// Parse bundle K file: extract *PARAMETER, *PART info, and all other card lines
static MswBundle msw_parseBundle(const std::string& path) {
    MswBundle bnd;
    std::ifstream f(path);
    if (!f.is_open()) throw std::runtime_error("Cannot open bundle: " + path);

    enum Sec { OTHER, PARAM, PART } sec = OTHER;
    bool partTitle=false, partData=false;
    std::string ln;

    while (std::getline(f, ln)) {
        std::string tr = msw_trim(ln);
        if (tr.empty()) { if (sec==OTHER) bnd.cards.push_back(ln); continue; }

        if (tr[0] == '*') {
            std::string up = msw_upper(tr);
            if (up=="*PARAMETER" || up.rfind("*PARAMETER_",0)==0 || up.rfind("*PARAMETER ",0)==0)
                { sec=PARAM; continue; }
            if (up=="*PART")
                { sec=PART; partTitle=false; partData=false; continue; }
            if (up=="*END") { sec=OTHER; continue; }
            sec=OTHER;
            bnd.cards.push_back(ln);
            continue;
        }
        if (tr[0]=='$') { if (sec==OTHER) bnd.cards.push_back(ln); continue; }

        if (sec==PARAM) {
            // Each line: up to 4 pairs of (type+name 10ch)(value 10ch)
            auto toks = msw_tok10(ln);
            for (size_t i=0; i+1<toks.size(); i+=2) {
                const auto& nf = toks[i];
                if (nf.size() < 2) continue;
                MswParam p;
                p.type  = (char)std::toupper((unsigned char)nf[0]);
                p.name  = msw_trim(nf.substr(1));
                p.ivalue = 0;
                if (p.name.empty()) continue;
                try {
                    if      (p.type=='I') p.ivalue = std::stoi(toks[i+1]);
                    else if (p.type=='R') p.ivalue = (int)std::stod(toks[i+1]);
                } catch(...) {}
                bnd.params.push_back(p);
            }
        } else if (sec==PART) {
            if (!partTitle) { partTitle=true; continue; }   // skip title line
            if (!partData) {
                auto toks = msw_tok10(ln);
                if (toks.size()>=5) {
                    bnd.bundlePid   = msw_resolveInt(toks[0], bnd.params);
                    bnd.bundleSecid = msw_resolveInt(toks[1], bnd.params);
                    bnd.bundleMid   = msw_resolveInt(toks[2], bnd.params);
                    bnd.bundleHgid  = msw_resolveInt(toks[4], bnd.params);
                }
                partData=true;
            }
        } else {
            bnd.cards.push_back(ln);
        }
    }
    return bnd;
}

// Scan model lines for max value of field[0] across all keyword blocks
// matching the given prefix (e.g. "*HOURGLASS", "*DEFINE_CURVE", "*SECTION", "*MAT_")
static int msw_scanMaxId(const std::vector<std::string>& lines,
                          const std::string& prefix) {
    int maxId=0;
    bool active=false; bool hasTitle=false; bool titleDone=false;
    for (const auto& ln : lines) {
        std::string tr = msw_trim(ln);
        if (tr.empty()) continue;
        if (tr[0]=='*') {
            std::string up = msw_upper(tr);
            if (up.rfind(prefix,0)==0) {
                active=true;
                hasTitle=(up.find("_TITLE")!=std::string::npos);
                titleDone=!hasTitle;
            } else { active=false; }
            continue;
        }
        if (!active || tr[0]=='$') continue;
        if (!titleDone) { titleDone=true; continue; }
        auto toks = msw_tok10(ln);
        if (!toks.empty()) { try { int id=std::stoi(toks[0]); if(id>maxId) maxId=id; } catch(...){} }
        active=false;
    }
    return maxId;
}

// Get PART data (PID/SECID/MID/HGID) for a given PID
static MswPartInfo msw_getPartInfo(const std::vector<std::string>& lines, int targetPid) {
    MswPartInfo info;
    bool inPart=false; bool titleDone=false;
    for (int i=0; i<(int)lines.size(); ++i) {
        std::string tr = msw_trim(lines[i]);
        if (tr.empty()) continue;
        if (tr[0]=='*') {
            std::string up=msw_upper(tr);
            inPart=(up=="*PART"||up=="*PART_TITLE"); titleDone=false; continue;
        }
        if (!inPart || tr[0]=='$') continue;
        if (!titleDone) { titleDone=true; continue; }
        auto toks = msw_tok10(lines[i]);
        if (toks.size()>=5) {
            try {
                int pid=std::stoi(toks[0]);
                if (pid==targetPid) {
                    info.pid=pid; info.secid=std::stoi(toks[1]);
                    info.mid=std::stoi(toks[2]); info.hgid=std::stoi(toks[4]);
                    info.dataLine=i; return info;
                }
            } catch(...) {}
        }
        titleDone=false; // ready for next title+data pair in same *PART block
    }
    return info;
}

// Check if any PART other than excludePid uses targetId at field[fieldIdx]
static bool msw_isShared(const std::vector<std::string>& lines,
                          int fieldIdx, int targetId, int excludePid) {
    bool inPart=false; bool titleDone=false;
    for (const auto& ln : lines) {
        std::string tr = msw_trim(ln);
        if (tr.empty()) continue;
        if (tr[0]=='*') {
            std::string up=msw_upper(tr);
            inPart=(up=="*PART"||up=="*PART_TITLE"); titleDone=false; continue;
        }
        if (!inPart || tr[0]=='$') continue;
        if (!titleDone) { titleDone=true; continue; }
        auto toks = msw_tok10(ln);
        if ((int)toks.size()>fieldIdx) {
            try {
                int pid=std::stoi(toks[0]);
                if (pid==excludePid) { titleDone=false; continue; }
                if (std::stoi(toks[fieldIdx])==targetId) return true;
            } catch(...) {}
        }
        titleDone=false; // ready for next title+data pair in same *PART block
    }
    return false;
}

// Remove entire keyword block where first data field == targetId
static std::vector<std::string> msw_removeBlock(
        const std::vector<std::string>& lines,
        const std::string& prefix, int targetId) {
    std::vector<bool> rm(lines.size(), false);

    for (int i=0; i<(int)lines.size(); ) {
        std::string tr = msw_trim(lines[i]);
        if (tr.empty() || tr[0]!='*') { ++i; continue; }
        std::string up = msw_upper(tr);
        if (up.rfind(prefix,0)!=0) { ++i; continue; }

        bool hasTitle=(up.find("_TITLE")!=std::string::npos);
        int titlesLeft=hasTitle?1:0, id=-1;

        for (int j=i+1; j<(int)lines.size(); ++j) {
            std::string jt = msw_trim(lines[j]);
            if (jt.empty()||jt[0]=='$') continue;
            if (jt[0]=='*') break;
            if (titlesLeft-->0) continue;
            auto toks=msw_tok10(lines[j]);
            if (!toks.empty()) { try{id=std::stoi(toks[0]);}catch(...){} }
            break;
        }
        if (id!=targetId) { ++i; continue; }

        int start=i, end=i+1;
        while (end<(int)lines.size()) {
            std::string et=msw_trim(lines[end]);
            if (!et.empty()&&et[0]=='*') break;
            ++end;
        }
        for (int k=start;k<end;++k) rm[k]=true;
        i=end;
    }

    std::vector<std::string> out;
    for (int i=0;i<(int)lines.size();++i) if (!rm[i]) out.push_back(lines[i]);
    return out;
}

// Replace &VARNAME tokens in a line with right-justified integer values
// sortedRemap: sorted by name length descending to avoid prefix collisions
static std::string msw_resolveLine(const std::string& line,
        const std::vector<std::pair<std::string,int>>& sortedRemap) {
    std::string r = line;
    for (const auto& kv : sortedRemap) {
        std::string pat = "&" + kv.first;
        int patLen = (int)pat.size();
        std::string val = std::to_string(kv.second);
        std::string repl = ((int)val.size()<=patLen)
            ? std::string(patLen-(int)val.size(),' ')+val : val;
        size_t pos=0;
        while ((pos=r.find(pat,pos))!=std::string::npos) {
            r.replace(pos,patLen,repl);
            pos+=repl.size();
        }
    }
    return r;
}

// Update SECID(field2), MID(field3), HGID(field5) in a PART data line
static std::string msw_updatePartLine(const std::string& ln,
                                       int newSecid, int newMid, int newHgid) {
    std::string r = ln;
    while ((int)r.size()<50) r+=' ';
    auto setF = [&](int start, int w, int v) {
        std::string vs=std::to_string(v);
        if ((int)vs.size()>w) vs=vs.substr(vs.size()-w);
        r.replace(start, w, std::string(w-(int)vs.size(),' ')+vs);
    };
    setF(10,10,newSecid); setF(20,10,newMid); setF(40,10,newHgid);
    return r;
}

// =====================================================================
// Implicit converter helpers  (impl_*)
// =====================================================================

static std::string impl_trim(const std::string& s) {
    size_t a = s.find_first_not_of(" \t\r\n");
    if (a == std::string::npos) return "";
    size_t b = s.find_last_not_of(" \t\r\n");
    return s.substr(a, b - a + 1);
}
static std::string impl_upper(const std::string& s) {
    std::string r = s;
    std::transform(r.begin(), r.end(), r.begin(), ::toupper);
    return r;
}
static std::vector<std::string> impl_tok10(const std::string& s) {
    std::vector<std::string> toks;
    for (int i = 0; i < (int)s.size(); i += 10)
        toks.push_back(impl_trim(s.substr(i, std::min(10, (int)s.size()-i))));
    return toks;
}

// Remove all blocks whose keyword line starts with keyword (case-insensitive, no ID check)
static std::vector<std::string> impl_removeKeyword(
        const std::vector<std::string>& lines, const std::string& keyword) {
    std::vector<bool> rm(lines.size(), false);
    std::string kwUp = impl_upper(keyword);
    for (int i = 0; i < (int)lines.size(); ) {
        std::string up = impl_upper(impl_trim(lines[i]));
        if (up.rfind(kwUp, 0) != 0) { ++i; continue; }
        int end = i + 1;
        while (end < (int)lines.size()) {
            std::string et = impl_trim(lines[end]);
            if (!et.empty() && et[0] == '*') break;
            ++end;
        }
        for (int k = i; k < end; ++k) rm[k] = true;
        i = end;
    }
    std::vector<std::string> out;
    for (size_t i = 0; i < lines.size(); ++i) if (!rm[i]) out.push_back(lines[i]);
    return out;
}

// Remove *DEFINE_CURVE blocks where SIDR field (toks[1]) == 1 (DR load curve)
// Modifies lines in place; returns number of curves removed
static int impl_removeDrCurves(std::vector<std::string>& lines) {
    int removed = 0;
    std::vector<bool> rm(lines.size(), false);
    for (int i = 0; i < (int)lines.size(); ) {
        std::string up = impl_upper(impl_trim(lines[i]));
        if (up.rfind("*DEFINE_CURVE", 0) != 0) { ++i; continue; }
        bool hasTitle = (up.find("_TITLE") != std::string::npos);
        int titlesLeft = hasTitle ? 1 : 0; int sidr = -1;
        for (int j = i+1; j < (int)lines.size(); ++j) {
            std::string jt = impl_trim(lines[j]);
            if (jt.empty() || jt[0]=='$') continue;
            if (jt[0]=='*') break;
            if (titlesLeft-- > 0) continue;
            auto toks = impl_tok10(lines[j]);
            if (toks.size() >= 2) { try { sidr = std::stoi(toks[1]); } catch(...){} }
            break;
        }
        if (sidr != 1) { ++i; continue; }
        int end = i+1;
        while (end < (int)lines.size()) {
            std::string et = impl_trim(lines[end]);
            if (!et.empty() && et[0]=='*') break;
            ++end;
        }
        for (int k = i; k < end; ++k) rm[k] = true;
        ++removed; i = end;
    }
    std::vector<std::string> out;
    for (size_t i = 0; i < lines.size(); ++i) if (!rm[i]) out.push_back(lines[i]);
    lines = std::move(out);
    return removed;
}

// Set a fixed-width field at [pos, pos+width) in a line (right-aligned)
static std::string impl_setField(const std::string& line, int pos, int width,
                                  const std::string& val) {
    std::string r = line;
    while ((int)r.size() < pos + width) r += ' ';
    std::string v = val;
    if ((int)v.size() > width) v = v.substr(v.size() - width);
    r.replace(pos, width, std::string(width - (int)v.size(), ' ') + v);
    return r;
}

// Read endtim from *CONTROL_TERMINATION first data line.
// Returns -1.0 if keyword not found, 0.0 if found but endtim=0, else the value.
static double impl_readEndtime(const std::vector<std::string>& lines) {
    bool inTerm=false, hasTitle=false, titleDone=false, found=false;
    for (const auto& ln : lines) {
        std::string tr = impl_trim(ln);
        if (tr.empty()) continue;
        if (tr[0]=='*') {
            std::string up=impl_upper(tr);
            inTerm = (up.rfind("*CONTROL_TERMINATION",0)==0);
            if (inTerm) found=true;
            hasTitle = (up.find("_TITLE")!=std::string::npos);
            titleDone=false; continue;
        }
        if (!inTerm||tr[0]=='$') continue;
        if (hasTitle&&!titleDone) { titleDone=true; continue; }
        auto toks = impl_tok10(ln);
        if (!toks.empty()) { try { return std::stod(toks[0]); } catch(...) { return 0.0; } }
        inTerm=false;
    }
    return found ? 0.0 : -1.0;
}

// Modify *CONTROL_TIMESTEP: TSSFAC=0.90 (pos 10), DT2MS=0.0 (pos 40)
static bool impl_modifyTimestep(std::vector<std::string>& lines) {
    bool inTs=false, hasTitle=false, titleDone=false;
    for (auto& ln : lines) {
        std::string tr = impl_trim(ln);
        if (tr.empty()) continue;
        if (tr[0]=='*') {
            std::string up=impl_upper(tr);
            inTs=(up.rfind("*CONTROL_TIMESTEP",0)==0);
            hasTitle=(up.find("_TITLE")!=std::string::npos);
            titleDone=false; continue;
        }
        if (!inTs||tr[0]=='$') continue;
        if (hasTitle&&!titleDone) { titleDone=true; continue; }
        ln = impl_setField(ln, 10, 10, "0.900000"); // TSSFAC
        ln = impl_setField(ln, 40, 10, "0.0");      // DT2MS
        return true;
    }
    return false;
}

// Update *CONTROL_TERMINATION endtim field (pos 0, width 10)
static bool impl_modifyTermination(std::vector<std::string>& lines, double endtime) {
    bool inTerm=false, hasTitle=false, titleDone=false;
    for (auto& ln : lines) {
        std::string tr = impl_trim(ln);
        if (tr.empty()) continue;
        if (tr[0]=='*') {
            std::string up=impl_upper(tr);
            inTerm=(up.rfind("*CONTROL_TERMINATION",0)==0);
            hasTitle=(up.find("_TITLE")!=std::string::npos);
            titleDone=false; continue;
        }
        if (!inTerm||tr[0]=='$') continue;
        if (hasTitle&&!titleDone) { titleDone=true; continue; }
        char buf[32]; snprintf(buf, sizeof(buf), "%g", endtime);
        ln = impl_setField(ln, 0, 10, impl_trim(buf));
        return true;
    }
    return false;
}

// Check *SECTION_SHELL for ELFORM=16 (not supported in implicit)
// Appends warning strings; if fix==true, replaces ELFORM=16 with 2
static void impl_checkShellElform(std::vector<std::string>& lines, bool fix,
                                   std::vector<std::string>& warnings) {
    bool inShell=false, hasTitle=false, titleDone=false;
    for (auto& ln : lines) {
        std::string tr = impl_trim(ln);
        if (tr.empty()) continue;
        if (tr[0]=='*') {
            std::string up=impl_upper(tr);
            inShell=(up.rfind("*SECTION_SHELL",0)==0);
            hasTitle=(up.find("_TITLE")!=std::string::npos);
            titleDone=false; continue;
        }
        if (!inShell||tr[0]=='$') continue;
        if (hasTitle&&!titleDone) { titleDone=true; continue; }
        // First data line: SECID(0-10), ELFORM(10-20)
        auto toks = impl_tok10(ln);
        if (toks.size() >= 2) {
            int elform=-1;
            try { elform=std::stoi(toks[1]); } catch(...){}
            if (elform==16) {
                warnings.push_back("[WARNING]  *SECTION_SHELL SECID=" + toks[0] +
                    ": ELFORM=16 not supported in implicit"
                    " (set fix_shell_elform: true to auto-fix)");
                if (fix) ln = impl_setField(ln, 10, 10, "2");
            }
        }
        inShell=false; // one data line per section keyword
    }
}

// Generate the 4 *CONTROL_IMPLICIT_* blocks as a string
static std::string impl_generateImplicitCards(
        const std::string& mode, int level, double endtime,
        double dctolOvr, double ectolOvr, double dt0Ovr, double dtmaxOvr,
        int nsolvrOvr, int kfailOvr, int lsolvrOvr, double rctolOvr,
        int stabOvr,       // -1=auto(level default), 0=force off, 1=force on
        double stabScaleOvr,
        int arcOvr) {      // -1=auto(level default), 0=force off, 1=force on
    // Level table: nsolvr,ilimit,maxref,iteopt,kfail,lsolvr,
    //              dctol,ectol,lstol,rctol,dt0f,dtmaxf,dtminf,
    //              stab,arcl,stabScale
    struct LP { int nsolvr,ilimit,maxref,iteopt,kfail,lsolvr;
                double dctol,ectol,lstol,rctol,dt0f,dtmaxf,dtminf;
                bool stab,arcl; double stabScale; };
    static const LP lv[8] = {
        // Lv1 공격적: loose, no extras
        {12,11,10,11,0, 7, 0.005,0.050,0.90,1e10, 1./100,  1./20,   1./1000,   false,false,1.0},
        // Lv2 표준: standard
        {12,11,15,11,0, 7, 0.001,0.010,0.90,1e10, 1./500,  1./100,  1./10000,  false,false,1.0},
        // Lv3 안정: more iterations
        {12,15,20,11,0, 7, 0.001,0.010,0.95,1e10, 1./1000, 1./200,  1./10000,  false,false,1.0},
        // Lv4 수렴우선: BFGS+LS + KFAIL
        {-2,20,25,11,3, 7, 0.001,0.010,0.95,1e10, 1./2000, 1./500,  1./100000, false,false,1.0},
        // Lv5 강건: + STABILIZATION
        {-2,25,30,15,5, 7, 0.001,0.005,0.99,1e10, 1./5000, 1./1000, 1./100000, true, false,1.0},
        // Lv6 고강건: + MUMPS(30) + RCTOL active
        {-2,30,40,15,8, 30,0.0005,0.002,0.99,0.1, 1./10000,1./2000, 1./100000, true, false,1.0},
        // Lv7 최대안정: all + strictest NR
        {-2,40,50,20,15,30,0.0001,0.001,0.99,0.01,1./50000,1./10000,1./1000000,true, false,1.0},
        // Lv8 좌굴/snap-through: NSOLVR=7(Full NR) + arc-length (Crisfield)
        //   Note: arc-length requires NSOLVR in [6..9]; NSOLVR=7=Full Newton is most reliable
        { 7,40,50,20,15,30,0.0001,0.001,0.99,0.01,1./50000,1./10000,1./1000000,true, true, 1.0},
    };
    int idx = std::max(0, std::min(7, level-1));
    const LP& p = lv[idx];
    int    nsolvr    = (nsolvrOvr!=0)   ? nsolvrOvr    : p.nsolvr;
    double dctol     = (dctolOvr>0)     ? dctolOvr     : p.dctol;
    double ectol     = (ectolOvr>0)     ? ectolOvr     : p.ectol;
    double rctol     = (rctolOvr>0)     ? rctolOvr     : p.rctol;
    double dt0       = (dt0Ovr>0)       ? dt0Ovr       : endtime*p.dt0f;
    double dtmax     = (dtmaxOvr>0)     ? dtmaxOvr     : endtime*p.dtmaxf;
    double dtmin     = -(endtime*p.dtminf);
    int    kfail     = (kfailOvr>=0)    ? kfailOvr     : p.kfail;
    int    lsolvr    = (lsolvrOvr>0)    ? lsolvrOvr    : p.lsolvr;
    bool   stab      = (stabOvr>=0)     ? (stabOvr>0)  : p.stab;
    double stabScale = (stabScaleOvr>0) ? stabScaleOvr : p.stabScale;
    bool   arcl      = (arcOvr>=0)      ? (arcOvr>0)   : p.arcl;
    int    imass     = (mode=="dynamic") ? 1 : 0;
    double gamma     = (mode=="dynamic") ? 0.6  : 0.5;
    double beta      = (mode=="dynamic") ? 0.30 : 0.25;

    // Arc-length requires NSOLVR in [6..9]; if enabled and NSOLVR is out of range, force NSOLVR=7
    if (arcl && (nsolvr < 6 || nsolvr > 9)) nsolvr = 7;

    // Format RCTOL field (scientific if large)
    char rctolBuf[12];
    if (rctol >= 1e9) snprintf(rctolBuf, sizeof(rctolBuf), " 1.000E+10");
    else              snprintf(rctolBuf, sizeof(rctolBuf), "%10.3E", rctol);

    char buf[2048];
    int n = snprintf(buf, sizeof(buf),
        "*CONTROL_IMPLICIT_GENERAL\n"
        "$   IMFLAG       DT0    IMFORM      NSBS       IGS    CNSTN      FORM    ZERO_V\n"
        "         1%10.6f         2         1         2         0         0         0\n"
        "*CONTROL_IMPLICIT_DYNAMICS\n"
        "$    IMASS     GAMMA      BETA    TDYBIR    TDYDTH    TDYBUR     IRATE\n"
        "%10d%10.6f%10.6f       0.0 1.000E+28 1.000E+28         0\n"
        "*CONTROL_IMPLICIT_SOLUTION\n"
        "$   NSOLVR    ILIMIT    MAXREF     DCTOL     ECTOL     RCTOL     LSTOL    ABSTOL\n"
        "%10d%10d%10d%10.6f%10.6f%s%10.6f 1.000E-10\n",
        dt0,
        imass, gamma, beta,
        nsolvr, p.ilimit, p.maxref, dctol, ectol, rctolBuf, p.lstol);

    // Optional: arc-length Card 3 (appended to *CONTROL_IMPLICIT_SOLUTION)
    // ARCCTL=0 (generalized), ARCMTH=1 (Crisfield), ARCDMP=2 (off), rest=0
    if (arcl) {
        n += snprintf(buf+n, sizeof(buf)-n,
            "$   ARCCTL    ARCDIR    ARCLEN    ARCMTH    ARCDMP    ARCPSI    ARCALF    ARCTIM\n"
            "         0         0  0.000000         1         2  0.000000  0.000000  0.000000\n");
    }

    n += snprintf(buf+n, sizeof(buf)-n,
        "*CONTROL_IMPLICIT_AUTO\n"
        "$    IAUTO    ITEOPT    ITEWIN     DTMIN     DTMAX     DTEXP     KFAIL    KCYCLE\n"
        "         1%10d         5%10.3E%10.6f       0.0%10d         0\n",
        p.iteopt, dtmin, dtmax, kfail);

    // Optional: *CONTROL_IMPLICIT_STABILIZATION (level 5+)
    if (stab) {
        n += snprintf(buf+n, sizeof(buf)-n,
            "*CONTROL_IMPLICIT_STABILIZATION\n"
            "$       IAS     SCALE    TSTART      TEND\n"
            "         1%10.6f       0.0 1.000E+28\n",
            stabScale);
    }

    // Optional: *CONTROL_IMPLICIT_SOLVER (MUMPS, level 6+)
    if (lsolvr != 7) {
        n += snprintf(buf+n, sizeof(buf)-n,
            "*CONTROL_IMPLICIT_SOLVER\n"
            "$    LSOLVR    LPRINT     NEGEV     ORDER      DRCM    DRCPRM   AUTOSPC   AUTOTOL\n"
            "%10d         0         2         0         4       0.0         1       0.0\n",
            lsolvr);
    }

    return std::string(buf);
}

// Insert content lines before *END (or append if *END not found)
static void impl_insertBeforeEnd(std::vector<std::string>& lines,
                                  const std::string& content) {
    std::vector<std::string> newLines;
    std::istringstream iss(content);
    std::string ln;
    while (std::getline(iss, ln)) newLines.push_back(ln);
    for (int i = 0; i < (int)lines.size(); ++i) {
        if (impl_upper(impl_trim(lines[i])) == "*END") {
            lines.insert(lines.begin()+i, newLines.begin(), newLines.end());
            return;
        }
    }
    for (const auto& l : newLines) lines.push_back(l);
}

// ── Modal helpers ────────────────────────────────────────────────────────────

static std::string modal_eigmthName(int eigmth) {
    switch (eigmth) {
        case 2:   return "Block Shift Lanczos";
        case 101: return "MCMS (NVH)";
        case 102: return "LOBPCG";
        case 103: return "Fast Lanczos (MPP)";
        default:  return "Method " + std::to_string(eigmth);
    }
}

static std::string modal_generateCards(int nmode, double fmin, double fmax,
                                        double center, int eigmth, int lsolvr) {
    char buf[4096]; int n = 0;
    n += snprintf(buf+n, sizeof(buf)-n,
        "*CONTROL_IMPLICIT_GENERAL\n"
        "$   IMFLAG       DT0    IMFORM      NSBS       IGS    CNSTN      FORM    ZERO_V\n"
        "         1  1.000000         2         1         2         0         0         0\n");
    int lflag = (fmin > 0.0) ? 1 : 0;
    int rflag = (fmax > 0.0) ? 1 : 0;
    n += snprintf(buf+n, sizeof(buf)-n,
        "*CONTROL_IMPLICIT_EIGENVALUE\n"
        "$      NEIG    CENTER     LFLAG    LFTEND     RFLAG    RHTEND    EIGMTH    SHFSCL\n"
        "%10d%10.4f%10d%10.4f%10d%10.4f%10d  0.000000\n",
        nmode, center, lflag, fmin, rflag, fmax, eigmth);
    n += snprintf(buf+n, sizeof(buf)-n,
        "*CONTROL_IMPLICIT_SOLUTION\n"
        "$   NSOLVR    ILIMIT    MAXREF     DCTOL     ECTOL     RCTOL     LSTOL    ABSTOL\n"
        "        12        11        15  0.001000  0.010000 1.000E+10  0.900000 1.000E-10\n");
    if (lsolvr == 30) {
        n += snprintf(buf+n, sizeof(buf)-n,
            "*CONTROL_IMPLICIT_SOLVER\n"
            "$    LSOLVR    LPRINT     NEGEV     ORDER      DRCM    DRCPRM   AUTOSPC    AUTOTOL\n"
            "        30         0         2         0         4  0.000000         1 1.000E-07\n");
    }
    return std::string(buf, n);
}

// ── ALE helpers ─────────────────────────────────────────────────────────────

struct AlePartEntry { int pid; std::string material; };
struct AlePartInfo  { int secid; int mid; int eosid; int hgid; };

static std::vector<int> ale_parsePidList(const std::string& val) {
    std::vector<int> pids;
    std::string s = val;
    // strip [ ]
    size_t lb = s.find('['); if (lb != std::string::npos) s.erase(lb, 1);
    size_t rb = s.find(']'); if (rb != std::string::npos) s.erase(rb, 1);
    std::istringstream iss(s);
    std::string tok;
    while (std::getline(iss, tok, ',')) {
        std::string t = impl_trim(tok);
        if (!t.empty()) { try { pids.push_back(std::stoi(t)); } catch (...) {} }
    }
    return pids;
}

// Scan all *PART cards → map<PID, AlePartInfo>
static std::map<int, AlePartInfo> ale_buildPartMap(
    const std::vector<std::string>& lines) {
    std::map<int, AlePartInfo> pm;
    for (int i = 0; i < (int)lines.size(); ++i) {
        std::string up = impl_upper(impl_trim(lines[i]));
        if (up.rfind("*PART", 0) != 0) continue;
        // Skip *PART_ variants except *PART_TITLE
        if (up.rfind("*PART_", 0) == 0 && up.find("*PART_TITLE") != 0) continue;
        // *PART always has a title line (even without _TITLE suffix), then data line
        int j = i + 1;
        // skip comment lines
        while (j < (int)lines.size() && !lines[j].empty() && lines[j][0] == '$') ++j;
        // skip title line
        if (j < (int)lines.size()) ++j;
        while (j < (int)lines.size() && !lines[j].empty() && lines[j][0] == '$') ++j;
        if (j >= (int)lines.size()) continue;
        auto toks = impl_tok10(lines[j]);
        if (toks.size() < 3) continue;
        AlePartInfo info{};
        try {
            int pid = std::stoi(toks[0]);
            info.secid = (toks.size() > 1) ? std::stoi(toks[1]) : 0;
            info.mid   = (toks.size() > 2) ? std::stoi(toks[2]) : 0;
            info.eosid = (toks.size() > 3) ? std::stoi(toks[3]) : 0;
            info.hgid  = (toks.size() > 4) ? std::stoi(toks[4]) : 0;
            pm[pid] = info;
        } catch (...) {}
    }
    return pm;
}

// Find max IDs in model
static void ale_findMaxIds(const std::vector<std::string>& lines,
    int& maxMid, int& maxEosid, int& maxSecid, int& maxHgid) {
    maxMid = 0; maxEosid = 0; maxSecid = 0; maxHgid = 0;
    for (int i = 0; i < (int)lines.size(); ++i) {
        std::string up = impl_upper(impl_trim(lines[i]));
        bool isMat  = (up.rfind("*MAT_", 0) == 0);
        bool isEos  = (up.rfind("*EOS_", 0) == 0);
        bool isSec  = (up.rfind("*SECTION_", 0) == 0);
        bool isHg   = (up.rfind("*HOURGLASS", 0) == 0);
        if (!isMat && !isEos && !isSec && !isHg) continue;
        bool hasTitle = (up.find("_TITLE") != std::string::npos);
        int j = i + 1;
        while (j < (int)lines.size() && !lines[j].empty() && lines[j][0] == '$') ++j;
        if (hasTitle && j < (int)lines.size()) {
            ++j;
            while (j < (int)lines.size() && !lines[j].empty() && lines[j][0] == '$') ++j;
        }
        if (j >= (int)lines.size()) continue;
        auto toks = impl_tok10(lines[j]);
        if (toks.empty()) continue;
        try {
            int id = std::stoi(toks[0]);
            if (isMat  && id > maxMid)   maxMid   = id;
            if (isEos  && id > maxEosid) maxEosid = id;
            if (isSec  && id > maxSecid) maxSecid = id;
            if (isHg   && id > maxHgid)  maxHgid  = id;
        } catch (...) {}
    }
}

// Check if secid is shared by non-ALE parts
static bool ale_isSharedSection(const std::map<int, AlePartInfo>& partMap,
    int secid, const std::set<int>& alePids) {
    for (const auto& kv : partMap) {
        if (alePids.count(kv.first) == 0 && kv.second.secid == secid)
            return true;
    }
    return false;
}

// Modify SECTION_SOLID ELFORM in-place, returns old ELFORM (-1 if not found)
static int ale_modifySectionElform(std::vector<std::string>& lines,
    int secid, int newElform) {
    for (int i = 0; i < (int)lines.size(); ++i) {
        std::string up = impl_upper(impl_trim(lines[i]));
        if (up.rfind("*SECTION_SOLID", 0) != 0) continue;
        bool hasTitle = (up.find("_TITLE") != std::string::npos);
        int j = i + 1;
        while (j < (int)lines.size() && !lines[j].empty() && lines[j][0] == '$') ++j;
        if (hasTitle && j < (int)lines.size()) {
            ++j;
            while (j < (int)lines.size() && !lines[j].empty() && lines[j][0] == '$') ++j;
        }
        if (j >= (int)lines.size()) continue;
        auto toks = impl_tok10(lines[j]);
        if (toks.size() < 2) continue;
        try {
            int sid = std::stoi(toks[0]);
            if (sid != secid) continue;
            int oldElform = std::stoi(toks[1]);
            lines[j] = impl_setField(lines[j], 10, 10, std::to_string(newElform));
            return oldElform;
        } catch (...) {}
    }
    return -1;
}

// Duplicate a SECTION_SOLID with new ID and ELFORM, returns card text
static std::string ale_duplicateSection(const std::vector<std::string>& lines,
    int oldSecid, int newSecid, int newElform) {
    for (int i = 0; i < (int)lines.size(); ++i) {
        std::string up = impl_upper(impl_trim(lines[i]));
        if (up.rfind("*SECTION_SOLID", 0) != 0) continue;
        bool hasTitle = (up.find("_TITLE") != std::string::npos);
        int j = i + 1;
        while (j < (int)lines.size() && !lines[j].empty() && lines[j][0] == '$') ++j;
        if (hasTitle && j < (int)lines.size()) {
            ++j;
            while (j < (int)lines.size() && !lines[j].empty() && lines[j][0] == '$') ++j;
        }
        if (j >= (int)lines.size()) continue;
        auto toks = impl_tok10(lines[j]);
        if (toks.size() < 2) continue;
        try {
            int sid = std::stoi(toks[0]);
            if (sid != oldSecid) continue;
            // Build duplicate
            std::string result = "*SECTION_SOLID\n";
            result += "$    SECID    ELFORM       AET\n";
            std::string dataLine = lines[j];
            dataLine = impl_setField(dataLine, 0, 10, std::to_string(newSecid));
            dataLine = impl_setField(dataLine, 10, 10, std::to_string(newElform));
            result += dataLine + "\n";
            return result;
        } catch (...) {}
    }
    return "";
}

// Update a specific field in *PART data line for given PID
static bool ale_updatePartField(std::vector<std::string>& lines,
    int pid, int fieldPos, int newValue) {
    for (int i = 0; i < (int)lines.size(); ++i) {
        std::string up = impl_upper(impl_trim(lines[i]));
        if (up.rfind("*PART", 0) != 0) continue;
        if (up.rfind("*PART_", 0) == 0 && up.find("*PART_TITLE") != 0) continue;
        // *PART always has title line then data line
        int j = i + 1;
        while (j < (int)lines.size() && !lines[j].empty() && lines[j][0] == '$') ++j;
        if (j < (int)lines.size()) ++j; // skip title line
        while (j < (int)lines.size() && !lines[j].empty() && lines[j][0] == '$') ++j;
        if (j >= (int)lines.size()) continue;
        auto toks = impl_tok10(lines[j]);
        if (toks.empty()) continue;
        try {
            int p = std::stoi(toks[0]);
            if (p != pid) continue;
            lines[j] = impl_setField(lines[j], fieldPos, 10, std::to_string(newValue));
            return true;
        } catch (...) {}
    }
    return false;
}

// Preset material definitions (unit: t/mm/s → MPa)
static const std::vector<std::string> ALE_PRESET_NAMES = {
    "air", "nitrogen", "argon",
    "water", "electrolyte", "gasoline", "oil", "coolant",
    "resin", "tim", "silicone",
    "tnt", "c4", "vacuum"
};

static bool ale_isPreset(const std::string& mat) {
    std::string m = impl_upper(impl_trim(mat));
    for (const auto& p : ALE_PRESET_NAMES)
        if (m == impl_upper(p)) return true;
    return false;
}

static std::string ale_presetMaterial(const std::string& preset, int mid, int eosid) {
    char buf[4096]; int n = 0;
    std::string p = impl_trim(preset);
    // normalize to lowercase for matching
    std::transform(p.begin(), p.end(), p.begin(), ::tolower);

    // Gas presets: MAT_NULL + EOS_LINEAR_POLYNOMIAL
    struct GasPreset { const char* name; double rho; double gamma; double e0; };
    GasPreset gases[] = {
        {"air",      1.293e-12, 1.40, 2.533e-01},
        {"nitrogen", 1.165e-12, 1.40, 2.280e-01},
        {"argon",    1.661e-12, 1.67, 1.519e-01},
    };
    for (const auto& g : gases) {
        if (p != g.name) continue;
        double c45 = g.gamma - 1.0;
        n += snprintf(buf+n, sizeof(buf)-n,
            "*MAT_NULL\n"
            "$      MID        RO        PC        MU     TEROD     CEROD        YM        PR\n"
            "%10d%10.3E  0.000000  0.000000  0.000000  0.000000  0.000000  0.000000\n",
            mid, g.rho);
        n += snprintf(buf+n, sizeof(buf)-n,
            "*EOS_LINEAR_POLYNOMIAL\n"
            "$    EOSID        C0        C1        C2        C3        C4        C5        C6\n"
            "%10d  0.000000  0.000000  0.000000  0.000000%10.6f%10.6f  0.000000\n"
            "$       E0        V0\n"
            "%10.4E  1.000000\n",
            eosid, c45, c45, g.e0);
        return std::string(buf, n);
    }

    // Liquid presets: MAT_NULL + EOS_GRUNEISEN
    struct LiqPreset { const char* name; double rho; double c; double s1; double gam; double mu; };
    LiqPreset liqs[] = {
        {"water",       1.00e-9,  1.484e+6, 1.979, 0.11, 0.0},
        {"electrolyte", 1.18e-9,  1.200e+6, 1.58,  0.13, 0.0},
        {"gasoline",    7.50e-10, 1.250e+6, 1.60,  0.10, 0.0},
        {"oil",         8.70e-10, 1.350e+6, 1.80,  0.10, 0.0},
        {"coolant",     1.08e-9,  1.600e+6, 1.85,  0.12, 0.0},
        {"resin",       1.15e-9,  1.700e+6, 1.70,  0.10, 1.0e-5},
        {"tim",         2.80e-9,  1.800e+6, 1.60,  0.10, 5.0e-4},
        {"silicone",    1.05e-9,  1.050e+6, 1.50,  0.10, 1.0e-4},
    };
    for (const auto& l : liqs) {
        if (p != l.name) continue;
        n += snprintf(buf+n, sizeof(buf)-n,
            "*MAT_NULL\n"
            "$      MID        RO        PC        MU     TEROD     CEROD        YM        PR\n"
            "%10d%10.3E  0.000000%10.3E  0.000000  0.000000  0.000000  0.000000\n",
            mid, l.rho, l.mu);
        n += snprintf(buf+n, sizeof(buf)-n,
            "*EOS_GRUNEISEN\n"
            "$    EOSID         C        S1        S2        S3     GAMAO         A        E0\n"
            "%10d%10.3E%10.6f  0.000000  0.000000%10.6f  0.000000  0.000000\n"
            "$       V0\n"
            "  1.000000\n",
            eosid, l.c, l.s1, l.gam);
        return std::string(buf, n);
    }

    // Explosive presets: MAT_HIGH_EXPLOSIVE_BURN + EOS_JWL
    struct HePreset { const char* name; double rho; double d; double pcj;
                      double a; double b; double r1; double r2; double omeg; double e0; };
    HePreset hes[] = {
        {"tnt", 1.630e-9, 6.930e+6, 2.100e+4,  3.712e+5, 3.231e+3, 4.15, 0.95, 0.30, 7.0e+3},
        {"c4",  1.601e-9, 8.193e+6, 2.800e+4,  6.098e+5, 1.295e+4, 4.50, 1.40, 0.25, 9.0e+3},
    };
    for (const auto& h : hes) {
        if (p != h.name) continue;
        n += snprintf(buf+n, sizeof(buf)-n,
            "*MAT_HIGH_EXPLOSIVE_BURN\n"
            "$      MID        RO         D       PCJ      BETA         K         G      SIGY\n"
            "%10d%10.3E%10.3E%10.3E  0.000000  0.000000  0.000000  0.000000\n",
            mid, h.rho, h.d, h.pcj);
        n += snprintf(buf+n, sizeof(buf)-n,
            "*EOS_JWL\n"
            "$    EOSID         A         B        R1        R2      OMEG        E0        VO\n"
            "%10d%10.3E%10.3E%10.6f%10.6f%10.6f%10.3E  1.000000\n",
            eosid, h.a, h.b, h.r1, h.r2, h.omeg, h.e0);
        return std::string(buf, n);
    }

    // Vacuum
    if (p == "vacuum") {
        n += snprintf(buf+n, sizeof(buf)-n,
            "*MAT_VACUUM\n"
            "$      MID        RO\n"
            "%10d 1.000E-18\n",
            mid);
        // vacuum has no EOS
        return std::string(buf, n);
    }

    return ""; // unknown preset
}

// Extract MAT + EOS blocks from custom bundle file, renumber MID/EOSID
static std::string ale_customMaterial(const std::string& path, int mid, int eosid) {
    std::ifstream fin(path);
    if (!fin.is_open()) return "";
    std::vector<std::string> blines;
    std::string ln;
    while (std::getline(fin, ln)) {
        if (!ln.empty() && ln.back() == '\r') ln.pop_back();
        blines.push_back(ln);
    }
    std::string result;
    bool inBlock = false;
    bool isMat = false, isEos = false;
    bool foundMat = false, foundEos = false;
    bool matIdDone = false, eosIdDone = false;
    for (int i = 0; i < (int)blines.size(); ++i) {
        std::string up = impl_upper(impl_trim(blines[i]));
        if (!up.empty() && up[0] == '*') {
            inBlock = false;
            isMat = (up.rfind("*MAT_", 0) == 0) && !foundMat;
            isEos = (up.rfind("*EOS_", 0) == 0) && !foundEos;
            if (isMat) { inBlock = true; foundMat = true; matIdDone = false; }
            if (isEos) { inBlock = true; foundEos = true; eosIdDone = false; }
        }
        if (!inBlock) continue;
        std::string line = blines[i];
        if (line.empty() || line[0] == '*' || line[0] == '$') {
            result += line + "\n";
            continue;
        }
        // Data line — replace ID in field 0
        if (isMat && !matIdDone) {
            line = impl_setField(line, 0, 10, std::to_string(mid));
            matIdDone = true;
        }
        if (isEos && !eosIdDone) {
            line = impl_setField(line, 0, 10, std::to_string(eosid));
            eosIdDone = true;
        }
        result += line + "\n";
    }
    return result;
}

static std::string ale_generateHourglass(int hgid) {
    char buf[512]; int n = 0;
    n += snprintf(buf+n, sizeof(buf)-n,
        "*HOURGLASS\n"
        "$     HGID       IHQ        QM       IBQ        Q1        Q2    QB/VDC        QW\n"
        "%10d         3 1.000E-06         0  1.500000 6.000E-02  0.100000  0.100000\n",
        hgid);
    return std::string(buf, n);
}

static std::string ale_generateControlALE(int dct, int nadv, int meth) {
    char buf[512]; int n = 0;
    n += snprintf(buf+n, sizeof(buf)-n,
        "*CONTROL_ALE\n"
        "$      DCT      NADV      METH      AFAC      BFAC      CFAC      DFAC      EFAC\n"
        "%10d%10d%10d  0.000000  0.000000  0.000000  0.000000  0.000000\n",
        dct, nadv, meth);
    return std::string(buf, n);
}

static std::string ale_generateAMMG(const std::vector<int>& pids) {
    std::string s = "*ALE_MULTI-MATERIAL_GROUP\n";
    s += "$      SID    IDTYPE\n";
    for (int pid : pids) {
        char buf[64];
        snprintf(buf, sizeof(buf), "%10d         1\n", pid);
        s += buf;
    }
    return s;
}

static std::string ale_generateRefSystem() {
    return
        "*ALE_REFERENCE_SYSTEM_GROUP\n"
        "$    SIDSID    SIDTYP    PRTYPE     BCTRAN     BCEXP     BCROT\n"
        "         0         0         4         0         0         0\n";
}

static std::string ale_generateCLIS(const std::vector<int>& fsiPids,
    const std::vector<int>& alePids, int ctype, int direc, int nquad, double pfac) {
    std::string s;
    for (int fpid : fsiPids) {
        for (int apid : alePids) {
            char buf[1024]; int n = 0;
            n += snprintf(buf+n, sizeof(buf)-n,
                "*CONSTRAINED_LAGRANGE_IN_SOLID\n"
                "$    SLAVE    MASTER     SSTYP    MSTYP    NQUAD    CTYPE    DIREC     MCOUP\n"
                "%10d%10d         1         1%10d%10d%10d         0\n",
                fpid, apid, nquad, ctype, direc);
            n += snprintf(buf+n, sizeof(buf)-n,
                "$      MC      NORM  NORMTYP     DAMP        K     HMIN     HMAX     PFAC\n"
                "         0  0.000000         0  0.000000  0.000000  0.000000  0.000000%10.6f\n",
                pfac);
            n += snprintf(buf+n, sizeof(buf)-n,
                "$   ILEAK    PLEAK  LCIDPOR     NVENT   IBLOCK\n"
                "         0  0.000000         0         0         0\n");
            s += std::string(buf, n);
        }
    }
    return s;
}

static std::string ale_generateDetonation(int pid, double x, double y, double z, double lt) {
    char buf[256]; int n = 0;
    n += snprintf(buf+n, sizeof(buf)-n,
        "*INITIAL_DETONATION\n"
        "$      PID         X         Y         Z        LT\n"
        "%10d%10.4f%10.4f%10.4f%10.4f\n",
        pid, x, y, z, lt);
    return std::string(buf, n);
}

} // anonymous namespace

int runMatswap(const std::string& modelFile, const std::string& bundleFile,
               int targetPid, const std::string& outputFile,
               ConsoleOutput& console) {

    console.println("[matswap] Model  : " + modelFile);
    console.println("[matswap] Bundle : " + bundleFile);
    console.println("[matswap] Target PID: " + std::to_string(targetPid));

    // 1. Read model
    std::vector<std::string> modelLines;
    {
        std::ifstream f(modelFile);
        if (!f.is_open()) { console.error("Cannot open model: " + modelFile); return 1; }
        std::string ln; while (std::getline(f,ln)) modelLines.push_back(ln);
    }

    // 2. Parse bundle
    MswBundle bundle;
    try { bundle = msw_parseBundle(bundleFile); }
    catch (const std::exception& e) { console.error(std::string(e.what())); return 1; }

    console.println("[matswap] Bundle cards: " + std::to_string(bundle.cards.size()) +
                    "  params: " + std::to_string(bundle.params.size()));
    console.println("[matswap] Bundle PART -> MID=" + std::to_string(bundle.bundleMid) +
                    " SECID=" + std::to_string(bundle.bundleSecid) +
                    " HGID=" + std::to_string(bundle.bundleHgid));

    // 3. Get target PART info
    MswPartInfo tp = msw_getPartInfo(modelLines, targetPid);
    if (tp.dataLine < 0) {
        console.error("PID " + std::to_string(targetPid) + " not found in model");
        return 1;
    }
    console.println("[matswap] Current PART " + std::to_string(targetPid) +
                    " -> MID=" + std::to_string(tp.mid) +
                    " SECID=" + std::to_string(tp.secid) +
                    " HGID=" + std::to_string(tp.hgid));

    // 4. Check which IDs are shared with other PARTs
    bool hgidShared  = msw_isShared(modelLines, 4, tp.hgid,  targetPid);
    bool secidShared = msw_isShared(modelLines, 1, tp.secid, targetPid);
    bool midShared   = msw_isShared(modelLines, 2, tp.mid,   targetPid);
    console.println("[matswap] ID sharing -> MID:" + std::string(midShared?"shared":"orphan") +
                    "  SECID:" + std::string(secidShared?"shared":"orphan") +
                    "  HGID:" + std::string(hgidShared?"shared":"orphan"));

    // 5. Scan model for max IDs (for new ID allocation)
    int maxHGID  = msw_scanMaxId(modelLines, "*HOURGLASS");
    int maxLCID  = msw_scanMaxId(modelLines, "*DEFINE_CURVE");
    int maxSECID = msw_scanMaxId(modelLines, "*SECTION");
    int maxMID   = msw_scanMaxId(modelLines, "*MAT_");
    console.println("[matswap] Model max IDs -> HGID=" + std::to_string(maxHGID) +
                    " LCID=" + std::to_string(maxLCID) +
                    " SECID=" + std::to_string(maxSECID) +
                    " MID=" + std::to_string(maxMID));

    // 6. Build remap table: &PARAM_NAME -> new integer value
    std::map<std::string,int> remap;
    for (const auto& p : bundle.params) {
        if (p.type!='I' && p.type!='R') continue;
        std::string idt = msw_idType(p.name);
        int newVal;
        if      (idt=="HGID")  newVal = ++maxHGID;
        else if (idt=="LCID")  newVal = ++maxLCID;
        else if (idt=="SECID") newVal = ++maxSECID;
        else if (idt=="MID")   newVal = midShared ? ++maxMID : tp.mid;
        else if (idt=="PID")   continue;  // PID: not remapped (bundle PART is skipped)
        else                   newVal = p.ivalue;
        remap[p.name] = newVal;
        console.println("[matswap]   &" + p.name + " (" + idt + ") " +
                        std::to_string(p.ivalue) + " -> " + std::to_string(newVal));
    }

    // Sort by name length descending to avoid prefix collisions (&MID10 before &MID1)
    std::vector<std::pair<std::string,int>> sortedRemap(remap.begin(), remap.end());
    std::sort(sortedRemap.begin(), sortedRemap.end(),
              [](const auto& a, const auto& b){ return a.first.size() > b.first.size(); });

    // 7. Resolve bundle cards (&VARNAME -> concrete numbers)
    std::vector<std::string> resolvedCards;
    for (const auto& c : bundle.cards)
        resolvedCards.push_back(msw_resolveLine(c, sortedRemap));

    // 8. Remove orphaned old cards from model
    if (!hgidShared  && tp.hgid >0) {
        modelLines = msw_removeBlock(modelLines, "*HOURGLASS", tp.hgid);
        console.println("[matswap] Removed *HOURGLASS HGID=" + std::to_string(tp.hgid));
    }
    if (!secidShared && tp.secid>0) {
        modelLines = msw_removeBlock(modelLines, "*SECTION",   tp.secid);
        console.println("[matswap] Removed *SECTION SECID=" + std::to_string(tp.secid));
    }
    if (!midShared   && tp.mid  >0) {
        modelLines = msw_removeBlock(modelLines, "*MAT_",      tp.mid);
        console.println("[matswap] Removed *MAT_ MID=" + std::to_string(tp.mid));
    }

    // 9. Update target PART data line with new IDs
    int newSecid=tp.secid, newMid=tp.mid, newHgid=tp.hgid;
    for (const auto& p : bundle.params) {
        if (!remap.count(p.name)) continue;
        std::string idt = msw_idType(p.name);
        if (idt=="SECID") newSecid = remap.at(p.name);
        if (idt=="MID")   newMid   = remap.at(p.name);
        if (idt=="HGID")  newHgid  = remap.at(p.name);
    }
    MswPartInfo tp2 = msw_getPartInfo(modelLines, targetPid);
    if (tp2.dataLine >= 0) {
        modelLines[tp2.dataLine] = msw_updatePartLine(modelLines[tp2.dataLine],
                                                      newSecid, newMid, newHgid);
        console.println("[matswap] Updated PART " + std::to_string(targetPid) +
                        " -> SECID=" + std::to_string(newSecid) +
                        " MID=" + std::to_string(newMid) +
                        " HGID=" + std::to_string(newHgid));
    }

    // 10. Insert resolved bundle cards just before *END
    std::vector<std::string> output;
    bool inserted = false;
    for (const auto& ln : modelLines) {
        if (!inserted && msw_upper(msw_trim(ln))=="*END") {
            for (const auto& c : resolvedCards) output.push_back(c);
            inserted = true;
        }
        output.push_back(ln);
    }
    if (!inserted) for (const auto& c : resolvedCards) output.push_back(c);

    // 11. Write output file
    {
        std::ofstream fout(outputFile);
        if (!fout.is_open()) { console.error("Cannot write: " + outputFile); return 1; }
        for (const auto& ln : output) fout << ln << "\n";
    }
    console.println("[matswap] Done -> " + outputFile);
    return 0;
}

// YAML-based matswap: supports multiple swaps and swap_all
// YAML format:
//   model: model.k
//   output: result.k
//   swaps:
//     - bundle: rubber.k
//       pids: [1, 3]
//     - bundle: foam.k
//       swap_all: true
int runMatswapYaml(const std::string& yamlFile, ConsoleOutput& console) {
    using namespace KooRemapper;

    // Simple YAML parser for matswap config
    std::ifstream f(yamlFile);
    if (!f.is_open()) { console.error("Cannot open: " + yamlFile); return 1; }

    // Config directory for relative paths
    std::string configDir;
    size_t lastSlash = yamlFile.find_last_of("/\\");
    if (lastSlash != std::string::npos) configDir = yamlFile.substr(0, lastSlash);

    auto trim = [](const std::string& s) -> std::string {
        size_t a=0, b=s.size();
        while (a<b && std::isspace((unsigned char)s[a])) ++a;
        while (b>a && std::isspace((unsigned char)s[b-1])) --b;
        return s.substr(a,b-a);
    };
    auto countIndent = [](const std::string& s) -> int {
        int n=0; while (n<(int)s.size() && s[n]==' ') ++n; return n;
    };

    std::string modelFile, outputFile;
    std::vector<MatswapOperation> swaps;
    bool inSwapsList = false;
    int swapsIndent = 0;
    bool inSwapItem = false;
    int swapItemIndent = 0;

    std::string ln;
    while (std::getline(f, ln)) {
        if (!ln.empty() && ln.back()=='\r') ln.pop_back();
        std::string tr = trim(ln);
        if (tr.empty() || tr[0]=='#') continue;

        int indent = countIndent(ln);

        // New swap item: "  - bundle: ..." or "  - " on its own line
        if (inSwapsList && indent > swapsIndent && tr[0]=='-') {
            swaps.push_back(MatswapOperation{});
            inSwapItem = true;
            swapItemIndent = indent;
            // Parse inline key after dash
            std::string rest = trim(tr.substr(1));
            size_t cp = rest.find(':');
            if (cp != std::string::npos) {
                std::string key = trim(rest.substr(0,cp));
                std::string val = trim(rest.substr(cp+1));
                auto parseIL = [&](const std::string& v, std::vector<int>& out) {
                    std::string lv=v;
                    if (!lv.empty()&&lv.front()=='[') lv=lv.substr(1);
                    if (!lv.empty()&&lv.back()==']') lv.pop_back();
                    std::istringstream ss(lv); std::string tok;
                    while (std::getline(ss,tok,',')) { std::string t=trim(tok); if(!t.empty()) out.push_back(std::stoi(t)); }
                };
                if (key=="bundle") swaps.back().bundleFile = val;
                else if (key=="swap_all") swaps.back().swapAll = (val=="true"||val=="yes"||val=="1");
                else if (key=="pid")  swaps.back().pids = { std::stoi(val) };
                else if (key=="pids") parseIL(val, swaps.back().pids);
                else if (key=="mid")  swaps.back().mids = { std::stoi(val) };
                else if (key=="mids") parseIL(val, swaps.back().mids);
            }
            continue;
        }

        // Sub-keys of current swap item
        if (inSwapItem && !swaps.empty() && indent > swapItemIndent) {
            size_t cp = tr.find(':');
            if (cp != std::string::npos) {
                std::string key = trim(tr.substr(0,cp));
                std::string val = trim(tr.substr(cp+1));
                auto parseIL = [&](const std::string& v, std::vector<int>& out) {
                    std::string lv=v;
                    if (!lv.empty()&&lv.front()=='[') lv=lv.substr(1);
                    if (!lv.empty()&&lv.back()==']') lv.pop_back();
                    std::istringstream ss(lv); std::string tok;
                    while (std::getline(ss,tok,',')) { std::string t=trim(tok); if(!t.empty()) out.push_back(std::stoi(t)); }
                };
                try {
                    if (key=="bundle") swaps.back().bundleFile = val;
                    else if (key=="swap_all") swaps.back().swapAll=(val=="true"||val=="yes"||val=="1");
                    else if (key=="pid")  swaps.back().pids = { std::stoi(val) };
                    else if (key=="pids") parseIL(val, swaps.back().pids);
                    else if (key=="mid")  swaps.back().mids = { std::stoi(val) };
                    else if (key=="mids") parseIL(val, swaps.back().mids);
                } catch(...) {}
            }
            continue;
        }

        // Exit lists if indent drops
        if (inSwapsList && indent <= swapsIndent) { inSwapsList=false; inSwapItem=false; }

        // Top-level keys
        size_t cp = tr.find(':');
        if (cp != std::string::npos) {
            std::string key = trim(tr.substr(0,cp));
            std::string val = trim(tr.substr(cp+1));
            auto parseIL = [&](const std::string& v, std::vector<int>& out) {
                std::string lv=v;
                if (!lv.empty()&&lv.front()=='[') lv=lv.substr(1);
                if (!lv.empty()&&lv.back()==']') lv.pop_back();
                std::istringstream ss(lv); std::string tok;
                while (std::getline(ss,tok,',')) { std::string t=trim(tok); if(!t.empty()) try{ out.push_back(std::stoi(t)); }catch(...){} }
            };
            if      (key=="model")  modelFile  = val;
            else if (key=="output") outputFile = val;
            else if (key=="swaps")  { inSwapsList=true; swapsIndent=indent; }
            // Single-swap shorthand: bundle/pid/pids/mid/mids/swap_all at top level
            else if (key=="bundle") {
                if (swaps.empty()) swaps.push_back(MatswapOperation{});
                swaps.back().bundleFile = val;
            }
            else if (key=="pid") {
                if (swaps.empty()) swaps.push_back(MatswapOperation{});
                swaps.back().pids = { std::stoi(val) };
            }
            else if (key=="pids") {
                if (swaps.empty()) swaps.push_back(MatswapOperation{});
                parseIL(val, swaps.back().pids);
            }
            else if (key=="mid") {
                if (swaps.empty()) swaps.push_back(MatswapOperation{});
                swaps.back().mids = { std::stoi(val) };
            }
            else if (key=="mids") {
                if (swaps.empty()) swaps.push_back(MatswapOperation{});
                parseIL(val, swaps.back().mids);
            }
            else if (key=="swap_all") {
                if (swaps.empty()) swaps.push_back(MatswapOperation{});
                swaps.back().swapAll = (val=="true"||val=="yes"||val=="1");
            }
        }
    }

    if (modelFile.empty())  { console.error("matswap YAML: 'model' not specified");  return 1; }
    if (outputFile.empty()) { console.error("matswap YAML: 'output' not specified"); return 1; }
    if (swaps.empty())      { console.error("matswap YAML: no swaps defined");        return 1; }

    console.println("[matswap] Model  : " + modelFile);
    console.println("[matswap] Output : " + outputFile);
    console.println("[matswap] Swaps  : " + std::to_string(swaps.size()));

    ModelAssembler assembler;
    if (!assembler.loadBaseModel(modelFile)) {
        console.error(assembler.getErrorMessage()); return 1;
    }

    for (size_t i=0; i<swaps.size(); ++i) {
        console.println("[matswap] --- Swap " + std::to_string(i+1) + "/" + std::to_string(swaps.size()) + " ---");
        if (!assembler.applyMatswap(swaps[i], configDir)) {
            console.error(assembler.getErrorMessage()); return 1;
        }
        for (const auto& msg : assembler.infoMessages) console.println(msg);
        assembler.infoMessages.clear();
    }

    // writeOutput appends ".k" - strip trailing ".k" from outputFile if present
    std::string outputPrefix = outputFile;
    if (outputPrefix.size() >= 2 &&
        outputPrefix.substr(outputPrefix.size()-2) == ".k") {
        outputPrefix = outputPrefix.substr(0, outputPrefix.size()-2);
    }

    if (!assembler.writeOutput(outputPrefix)) {
        console.error(assembler.getErrorMessage()); return 1;
    }
    console.println("[matswap] Done -> " + outputPrefix + ".k");
    return 0;
}

// =====================================================================
// implicit command: convert explicit K-file to implicit solver settings
// =====================================================================
int runImplicit(const std::string& yamlFile, ConsoleOutput& console) {
    // 1. Parse YAML
    std::ifstream f(yamlFile);
    if (!f.is_open()) { console.error("Cannot open: " + yamlFile); return 1; }

    std::string configDir;
    size_t lastSlash = yamlFile.find_last_of("/\\");
    if (lastSlash != std::string::npos) configDir = yamlFile.substr(0, lastSlash);

    std::string modelFile, outputFile;
    std::string mode = "static";
    int level = 2;
    double endtimeYaml = -1.0; // -1 = not specified by user
    double dctolOvr=-1.0, ectolOvr=-1.0, dt0Ovr=-1.0, dtmaxOvr=-1.0, rctolOvr=-1.0;
    double stabScaleOvr = 0.0;
    int nsolvrOvr = 0, kfailOvr = -1, lsolvrOvr = 0, stabOvr = -1, arcOvr = -1;
    bool fixShellElform = false;
    bool keepDrCurves   = false;

    auto trimYaml = [](const std::string& s) -> std::string {
        size_t a=s.find_first_not_of(" \t\r\n");
        if (a==std::string::npos) return "";
        size_t b=s.find_last_not_of(" \t\r\n");
        return s.substr(a,b-a+1);
    };

    std::string line;
    while (std::getline(f, line)) {
        std::string tr = trimYaml(line);
        if (tr.empty() || tr[0]=='#') continue;
        size_t cp = tr.find(':');
        if (cp==std::string::npos) continue;
        std::string key = trimYaml(tr.substr(0,cp));
        std::string val = trimYaml(tr.substr(cp+1));
        if (val.empty()) continue;
        try {
            if      (key=="model")   modelFile  = val;
            else if (key=="output")  outputFile = val;
            else if (key=="mode")    mode = val;
            else if (key=="level")   level = std::stoi(val);
            else if (key=="endtime") endtimeYaml = std::stod(val);
            else if (key=="dctol")   dctolOvr  = std::stod(val);
            else if (key=="ectol")   ectolOvr  = std::stod(val);
            else if (key=="dt0")     dt0Ovr    = std::stod(val);
            else if (key=="dtmax")   dtmaxOvr  = std::stod(val);
            else if (key=="nsolvr")     nsolvrOvr    = std::stoi(val);
            else if (key=="kfail")      kfailOvr     = std::stoi(val);
            else if (key=="lsolvr")     lsolvrOvr    = std::stoi(val);
            else if (key=="rctol")      rctolOvr     = std::stod(val);
            else if (key=="stab")        stabOvr      = (val=="true"||val=="yes"||val=="1")?1:0;
            else if (key=="stab_scale")  stabScaleOvr = std::stod(val);
            else if (key=="arc_length")  arcOvr       = (val=="true"||val=="yes"||val=="1")?1:0;
            else if (key=="fix_shell_elform") fixShellElform=(val=="true"||val=="yes"||val=="1");
            else if (key=="keep_dr_curves")   keepDrCurves  =(val=="true"||val=="yes"||val=="1");
        } catch(...) {}
    }

    if (modelFile.empty())  { console.error("implicit YAML: 'model' not specified");  return 1; }
    if (outputFile.empty()) { console.error("implicit YAML: 'output' not specified"); return 1; }
    if (level<1||level>8)   { console.error("implicit: level must be 1~8");           return 1; }
    if (mode!="static"&&mode!="dynamic") {
        console.error("implicit: mode must be 'static' or 'dynamic'"); return 1;
    }

    // Resolve model path relative to YAML (only if path is a bare filename with no directory)
    auto resolvePath = [&](const std::string& p) -> std::string {
        if (!configDir.empty() && !p.empty() &&
            p[0]!='/' && p[0]!='\\' && !(p.size()>=2 && p[1]==':') &&
            p.find('/')  == std::string::npos &&
            p.find('\\') == std::string::npos)
            return configDir + "/" + p;
        return p;
    };
    std::string modelPath = resolvePath(modelFile);
    std::string outPath   = resolvePath(outputFile);

    // 2. Read model file
    std::vector<std::string> lines;
    {
        std::ifstream mf(modelPath);
        if (!mf.is_open()) { console.error("Cannot open model: " + modelPath); return 1; }
        std::string ln;
        while (std::getline(mf, ln)) lines.push_back(ln);
    }

    // Print header
    static const char* levelNames[8] = {"공격적","표준","안정","수렴우선","강건","고강건","최대안정","좌굴/스냅스루"};
    static const double dtmaxF[8]  = {1./20,1./100,1./200,1./500,1./1000,1./2000,1./10000,1./10000};
    static const int    nsolvrL[8] = {12,12,12,-2,-2,-2,-2,7};
    static const double dctolL[8]  = {0.005,0.001,0.001,0.001,0.001,0.0005,0.0001,0.0001};
    static const int    kfailL[8]  = {0,0,0,3,5,8,15,15};
    static const int    lsolvrL[8] = {7,7,7,7,7,30,30,30};
    static const bool   stabL[8]   = {false,false,false,false,true,true,true,true};
    static const double rctolL[8]  = {1e10,1e10,1e10,1e10,1e10,0.1,0.01,0.01};
    static const bool   arclL[8]   = {false,false,false,false,false,false,false,true};
    int li = level-1;
    console.println("[implicit] Model   : " + modelPath);
    console.println("[implicit] Output  : " + outPath);
    console.println("[implicit] Mode    : " + mode +
                    " (IMASS=" + (mode=="static"?"0":"1") + ")");

    // 3. Determine effective endtime
    double endtime = endtimeYaml;
    std::string endtimeSource;
    if (endtime < 0) {
        double modelEnd = impl_readEndtime(lines);
        if (modelEnd > 0.0) {
            endtime = modelEnd; endtimeSource = "from model";
        } else if (modelEnd == 0.0) {
            console.println("[WARNING]  endtim=0 detected (DR mode). Add 'endtime:' to YAML. Using 1.0 as fallback.");
            endtime = 1.0; endtimeSource = "fallback=1.0";
        } else { // -1: not found
            console.println("[WARNING]  *CONTROL_TERMINATION not found. Add 'endtime:' to YAML. Using 1.0 as fallback.");
            endtime = 1.0; endtimeSource = "fallback=1.0";
        }
    } else {
        endtimeSource = "from YAML";
    }

    // Compute display values for level summary
    int    dispNsolvr = (nsolvrOvr!=0) ? nsolvrOvr : nsolvrL[li];
    double dispDctol  = (dctolOvr>0)   ? dctolOvr  : dctolL[li];
    double dispDtmax  = (dtmaxOvr>0)   ? dtmaxOvr  : endtime*dtmaxF[li];
    int    dispKfail  = (kfailOvr>=0)  ? kfailOvr  : kfailL[li];
    int    dispLsolvr = (lsolvrOvr>0)  ? lsolvrOvr : lsolvrL[li];
    bool   dispStab   = (stabOvr>=0)   ? (stabOvr>0): stabL[li];
    double dispRctol  = (rctolOvr>0)   ? rctolOvr  : rctolL[li];
    bool   dispArcl   = (arcOvr>=0)    ? (arcOvr>0) : arclL[li];
    // arc-length forces NSOLVR into [6..9]
    if (dispArcl && (dispNsolvr < 6 || dispNsolvr > 9)) dispNsolvr = 7;
    char lvBuf[256];
    int ln = snprintf(lvBuf, sizeof(lvBuf),
        "[implicit] Level   : %d (%s)  NSOLVR=%d  DCTOL=%.6g  DTMAX=%.6g",
        level, levelNames[li], dispNsolvr, dispDctol, dispDtmax);
    if (dispKfail  > 0)   ln += snprintf(lvBuf+ln, sizeof(lvBuf)-ln, "  +KFAIL=%d", dispKfail);
    if (dispStab)         ln += snprintf(lvBuf+ln, sizeof(lvBuf)-ln, "  +STAB");
    if (dispLsolvr == 30) ln += snprintf(lvBuf+ln, sizeof(lvBuf)-ln, "  +MUMPS");
    if (dispRctol  < 1e9) ln += snprintf(lvBuf+ln, sizeof(lvBuf)-ln, "  +RCTOL=%.4g", dispRctol);
    if (dispArcl)         ln += snprintf(lvBuf+ln, sizeof(lvBuf)-ln, "  +ARC-LENGTH");
    console.println(lvBuf);
    char etBuf[80];
    snprintf(etBuf, sizeof(etBuf), "[implicit] Endtime : %g (%s)", endtime, endtimeSource.c_str());
    console.println(etBuf);

    // 4. Remove explicit-specific blocks
    auto removeAndLog = [&](const std::string& kw) {
        size_t before = lines.size();
        lines = impl_removeKeyword(lines, kw);
        if (lines.size() < before) console.println("[implicit] Removed : " + kw);
    };
    removeAndLog("*CONTROL_DYNAMIC_RELAXATION");
    removeAndLog("*CONTROL_BULK_VISCOSITY");
    removeAndLog("*DATABASE_BINARY_D3DRLF");

    // 5. DR load curves (SIDR=1) - removed by default
    if (!keepDrCurves) {
        int n = impl_removeDrCurves(lines);
        if (n > 0) {
            char buf[64];
            snprintf(buf, sizeof(buf), "[implicit] Removed : %d *DEFINE_CURVE (SIDR=1)", n);
            console.println(buf);
        }
    }

    // 6. Modify *CONTROL_TIMESTEP: DT2MS=0, TSSFAC=0.90
    if (impl_modifyTimestep(lines))
        console.println("[implicit] Modified: *CONTROL_TIMESTEP (DT2MS=0.0, TSSFAC=0.90)");

    // 7. Update *CONTROL_TERMINATION endtim if user specified
    if (endtimeYaml > 0) {
        double oldEnd = impl_readEndtime(lines);
        if (impl_modifyTermination(lines, endtimeYaml)) {
            char buf[128];
            snprintf(buf, sizeof(buf),
                "[implicit] Modified: *CONTROL_TERMINATION (endtim: %g -> %g)", oldEnd, endtimeYaml);
            console.println(buf);
        }
    }

    // 8. Check *SECTION_SHELL ELFORM=16
    std::vector<std::string> shellWarnings;
    impl_checkShellElform(lines, fixShellElform, shellWarnings);
    for (const auto& w : shellWarnings) console.println(w);
    if (fixShellElform && !shellWarnings.empty())
        console.println("[implicit] Fixed   : ELFORM=16 -> 2 in *SECTION_SHELL");

    // 9. Remove existing *CONTROL_IMPLICIT_* if present, then re-insert
    {
        bool hadImplicit = false;
        for (const auto& ln : lines)
            if (impl_upper(impl_trim(ln)).rfind("*CONTROL_IMPLICIT",0)==0) { hadImplicit=true; break; }
        if (hadImplicit) {
            console.println("[WARNING]  *CONTROL_IMPLICIT_* already exists. Replacing...");
            lines = impl_removeKeyword(lines, "*CONTROL_IMPLICIT_GENERAL");
            lines = impl_removeKeyword(lines, "*CONTROL_IMPLICIT_DYNAMICS");
            lines = impl_removeKeyword(lines, "*CONTROL_IMPLICIT_SOLUTION");
            lines = impl_removeKeyword(lines, "*CONTROL_IMPLICIT_AUTO");
            lines = impl_removeKeyword(lines, "*CONTROL_IMPLICIT_STABILIZATION");
            lines = impl_removeKeyword(lines, "*CONTROL_IMPLICIT_SOLVER");
        }
    }

    // 10. Generate and insert CONTROL_IMPLICIT blocks
    std::string implCards = impl_generateImplicitCards(
        mode, level, endtime, dctolOvr, ectolOvr, dt0Ovr, dtmaxOvr,
        nsolvrOvr, kfailOvr, lsolvrOvr, rctolOvr, stabOvr, stabScaleOvr, arcOvr);
    impl_insertBeforeEnd(lines, implCards);
    // Build inserted block list for console
    {
        std::string msg = "[implicit] Inserted: *CONTROL_IMPLICIT_GENERAL/DYNAMICS/SOLUTION/AUTO";
        if ((stabOvr>=0)?(stabOvr>0):stabL[li])              msg += "  +STABILIZATION";
        if (((lsolvrOvr>0)?lsolvrOvr:lsolvrL[li]) == 30)     msg += "  +SOLVER(MUMPS)";
        if ((arcOvr>=0)?(arcOvr>0):arclL[li])                msg += "  +ARC-LENGTH(Crisfield)";
        console.println(msg);
    }

    // 11. Write output
    std::ofstream out(outPath);
    if (!out.is_open()) { console.error("Cannot write output: " + outPath); return 1; }
    for (const auto& ln : lines) out << ln << "\n";
    console.println("[implicit] Done    -> " + outPath);
    return 0;
}

// ── Modal command ─────────────────────────────────────────────────────────────
int runModal(const std::string& yamlFile, ConsoleOutput& console) {
    // 1. Parse YAML
    std::string modelPath, outPath;
    int    nmode   = 10;
    double fmin    = 0.0;
    double fmax    = 0.0;
    double center  = 0.0;
    int    eigmth  = 2;
    int    lsolvr  = 7;
    bool   fixElform   = false;
    bool   keepDrCurves = false;

    // Resolve configDir for relative paths
    std::string configDir;
    {
        std::string yf = yamlFile;
        size_t sep = yf.find_last_of("/\\");
        configDir = (sep != std::string::npos) ? yf.substr(0, sep+1) : "";
    }

    {
        std::ifstream yin(yamlFile);
        if (!yin.is_open()) { console.error("Cannot open YAML: " + yamlFile); return 1; }
        std::string line;
        while (std::getline(yin, line)) {
            std::string t = impl_trim(line);
            if (t.empty() || t[0] == '#') continue;
            size_t colon = t.find(':');
            if (colon == std::string::npos) continue;
            std::string key = impl_trim(t.substr(0, colon));
            std::string val = impl_trim(t.substr(colon+1));
            if (val.empty() || val[0] == '#') continue;
            // strip inline comment
            size_t hpos = val.find('#');
            if (hpos != std::string::npos) val = impl_trim(val.substr(0, hpos));
            if (key == "model")              modelPath  = val;
            else if (key == "output")        outPath    = val;
            else if (key == "nmode")         nmode      = std::stoi(val);
            else if (key == "fmin")          fmin       = std::stod(val);
            else if (key == "fmax")          fmax       = std::stod(val);
            else if (key == "center")        center     = std::stod(val);
            else if (key == "eigmth")        eigmth     = std::stoi(val);
            else if (key == "solver")        lsolvr     = std::stoi(val);
            else if (key == "fix_shell_elform")  fixElform   = (val == "true");
            else if (key == "keep_dr_curves")    keepDrCurves = (val == "true");
        }
    }

    if (modelPath.empty()) { console.error("YAML missing 'model' field"); return 1; }
    if (outPath.empty())   { console.error("YAML missing 'output' field"); return 1; }

    // Prepend configDir if path has no directory component (same logic as runImplicit)
    auto resolvePath = [&](const std::string& p) -> std::string {
        if (!configDir.empty() && !p.empty() &&
            p[0] != '/' && p[0] != '\\' && !(p.size() >= 2 && p[1] == ':') &&
            p.find('/')  == std::string::npos &&
            p.find('\\') == std::string::npos)
            return configDir + "/" + p;
        return p;
    };
    std::string modelFullPath = resolvePath(modelPath);
    std::string outFullPath   = resolvePath(outPath);

    // 2. Read model file
    std::vector<std::string> lines;
    {
        std::ifstream fin(modelFullPath);
        if (!fin.is_open()) { console.error("Cannot open model: " + modelFullPath); return 1; }
        std::string ln;
        while (std::getline(fin, ln)) {
            if (!ln.empty() && ln.back() == '\r') ln.pop_back();
            lines.push_back(ln);
        }
    }

    // Console header
    console.println("[modal] Model   : " + modelPath);
    console.println("[modal] Output  : " + outPath);
    {
        std::string freqRange = (fmin > 0.0 || fmax > 0.0)
            ? " (" + std::to_string((int)fmin) + " ~ " + std::to_string((int)fmax) + " Hz)"
            : " (no frequency limits)";
        console.println("[modal] Modes   : " + std::to_string(nmode) + freqRange);
    }
    console.println("[modal] Method  : " + modal_eigmthName(eigmth) + " (EIGMTH=" + std::to_string(eigmth) + ")");
    console.println("[modal] Solver  : " + std::to_string(lsolvr) + (lsolvr == 30 ? " (MUMPS)" : " (default)"));

    // 3. Remove explicit-only blocks
    size_t before;
    before = lines.size();
    lines = impl_removeKeyword(lines, "*CONTROL_DYNAMIC_RELAXATION");
    if (lines.size() < before) console.println("[modal] Removed : *CONTROL_DYNAMIC_RELAXATION");

    before = lines.size();
    lines = impl_removeKeyword(lines, "*CONTROL_BULK_VISCOSITY");
    if (lines.size() < before) console.println("[modal] Removed : *CONTROL_BULK_VISCOSITY");

    before = lines.size();
    lines = impl_removeKeyword(lines, "*DATABASE_BINARY_D3DRLF");
    if (lines.size() < before) console.println("[modal] Removed : *DATABASE_BINARY_D3DRLF");

    // 4. Remove DR curves (SIDR=1) unless keep_dr_curves
    if (!keepDrCurves) {
        int nRemoved = impl_removeDrCurves(lines);
        if (nRemoved > 0)
            console.println("[modal] Removed : " + std::to_string(nRemoved) + " *DEFINE_CURVE (SIDR=1)");
    }

    // 5. Modify CONTROL_TIMESTEP (DT2MS=0, TSSFAC=0.9)
    if (impl_modifyTimestep(lines))
        console.println("[modal] Modified: *CONTROL_TIMESTEP (DT2MS=0.0, TSSFAC=0.90)");

    // 6. Shell ELFORM=16 check/fix
    {
        std::vector<std::string> warnings;
        impl_checkShellElform(lines, fixElform, warnings);
        for (const auto& w : warnings) console.println(w);
    }

    // 7. Remove existing CONTROL_IMPLICIT_* blocks, then re-insert fresh ones
    {
        bool hadImplicit = false;
        for (const auto& ln : lines) {
            std::string up = impl_upper(impl_trim(ln));
            if (up.rfind("*CONTROL_IMPLICIT_", 0) == 0) { hadImplicit = true; break; }
        }
        if (hadImplicit) {
            console.println("[WARNING]  *CONTROL_IMPLICIT_* already exists. Replacing...");
            lines = impl_removeKeyword(lines, "*CONTROL_IMPLICIT_GENERAL");
            lines = impl_removeKeyword(lines, "*CONTROL_IMPLICIT_DYNAMICS");
            lines = impl_removeKeyword(lines, "*CONTROL_IMPLICIT_SOLUTION");
            lines = impl_removeKeyword(lines, "*CONTROL_IMPLICIT_AUTO");
            lines = impl_removeKeyword(lines, "*CONTROL_IMPLICIT_STABILIZATION");
            lines = impl_removeKeyword(lines, "*CONTROL_IMPLICIT_SOLVER");
            lines = impl_removeKeyword(lines, "*CONTROL_IMPLICIT_EIGENVALUE");
        }
    }

    // 8. Generate and insert modal CONTROL cards
    std::string modalCards = modal_generateCards(nmode, fmin, fmax, center, eigmth, lsolvr);
    impl_insertBeforeEnd(lines, modalCards);
    console.println("[modal] Inserted: *CONTROL_IMPLICIT_GENERAL");
    {
        std::string freq = "";
        if (fmin > 0.0 || fmax > 0.0)
            freq = " (NEIG=" + std::to_string(nmode) + ", " +
                   std::to_string((int)fmin) + "~" + std::to_string((int)fmax) + " Hz)";
        else
            freq = " (NEIG=" + std::to_string(nmode) + ", no freq limits)";
        console.println("[modal] Inserted: *CONTROL_IMPLICIT_EIGENVALUE" + freq);
    }
    console.println("[modal] Inserted: *CONTROL_IMPLICIT_SOLUTION");
    if (lsolvr == 30)
        console.println("[modal] Inserted: *CONTROL_IMPLICIT_SOLVER (MUMPS)");

    // 9. Write output
    std::ofstream out(outFullPath);
    if (!out.is_open()) { console.error("Cannot write output: " + outFullPath); return 1; }
    for (const auto& ln : lines) out << ln << "\n";
    console.println("[modal] Done    -> " + outPath);
    return 0;
}

// ── ALE command ───────────────────────────────────────────────────────────────
int runAle(const std::string& yamlFile, ConsoleOutput& console) {
    // 1. Parse YAML
    std::string modelFile, outputFile;
    std::vector<AlePartEntry> aleEntries;
    std::vector<int> fsiPids;
    int    elform  = 11;
    int    dct     = 1, nadv = 1, meth = 2;
    int    ctype   = 2, direc = 1, nquad = 2;
    double pfac    = 0.1;
    // detonation
    bool   hasDet  = false;
    int    detPid  = 0;
    double detX = 0, detY = 0, detZ = 0, detLt = 0;

    std::string configDir;
    {
        std::string yf = yamlFile;
        size_t sep = yf.find_last_of("/\\");
        configDir = (sep != std::string::npos) ? yf.substr(0, sep+1) : "";
    }

    {
        std::ifstream yin(yamlFile);
        if (!yin.is_open()) { console.error("Cannot open YAML: " + yamlFile); return 1; }
        std::string line;
        bool inAleParts = false;
        bool inDetonation = false;
        AlePartEntry curEntry{0, ""};
        int aleIndent = 0;
        while (std::getline(yin, line)) {
            std::string raw = line;
            // compute indent
            int indent = 0;
            for (char c : raw) { if (c == ' ') ++indent; else break; }
            std::string t = impl_trim(raw);
            if (t.empty() || t[0] == '#') continue;

            // Check for top-level keys (indent=0 or low indent)
            size_t colon = t.find(':');
            if (colon == std::string::npos) continue;
            std::string key = impl_trim(t.substr(0, colon));
            std::string val = impl_trim(t.substr(colon+1));
            // strip inline comment
            { size_t h = val.find('#'); if (h != std::string::npos) val = impl_trim(val.substr(0, h)); }

            // Detect ale_parts list
            if (key == "ale_parts" && indent < 4) {
                inAleParts = true;
                inDetonation = false;
                aleIndent = indent;
                continue;
            }
            if (key == "detonation" && indent < 4) {
                inDetonation = true;
                inAleParts = false;
                hasDet = true;
                continue;
            }

            // Inside ale_parts list
            if (inAleParts) {
                if (indent <= aleIndent && key != "-" && t.find("- pid") == std::string::npos
                    && key != "pid" && key != "material") {
                    // Exited ale_parts
                    inAleParts = false;
                    if (curEntry.pid > 0) aleEntries.push_back(curEntry);
                    curEntry = {0, ""};
                    // fall through to parse this line as top-level
                } else {
                    // Parse list item
                    if (t.find("- pid") != std::string::npos) {
                        if (curEntry.pid > 0) aleEntries.push_back(curEntry);
                        curEntry = {0, ""};
                        // extract pid value after "- pid:"
                        size_t pidColon = t.find("pid:");
                        if (pidColon != std::string::npos) {
                            std::string pv = impl_trim(t.substr(pidColon + 4));
                            size_t h = pv.find('#'); if (h != std::string::npos) pv = impl_trim(pv.substr(0, h));
                            try { curEntry.pid = std::stoi(pv); } catch (...) {}
                        }
                    } else if (key == "material") {
                        curEntry.material = val;
                    }
                    continue;
                }
            }

            // Inside detonation block
            if (inDetonation) {
                if (indent < 2 && key != "pid" && key != "x" && key != "y" && key != "z" && key != "lt") {
                    inDetonation = false;
                    // fall through
                } else {
                    if (key == "pid") try { detPid = std::stoi(val); } catch (...) {}
                    else if (key == "x") try { detX = std::stod(val); } catch (...) {}
                    else if (key == "y") try { detY = std::stod(val); } catch (...) {}
                    else if (key == "z") try { detZ = std::stod(val); } catch (...) {}
                    else if (key == "lt") try { detLt = std::stod(val); } catch (...) {}
                    continue;
                }
            }

            // Top-level keys
            if (key == "model")    modelFile  = val;
            else if (key == "output")   outputFile = val;
            else if (key == "fsi_pids") fsiPids    = ale_parsePidList(val);
            else if (key == "elform")   try { elform = std::stoi(val); } catch (...) {}
            else if (key == "dct")      try { dct    = std::stoi(val); } catch (...) {}
            else if (key == "nadv")     try { nadv   = std::stoi(val); } catch (...) {}
            else if (key == "meth")     try { meth   = std::stoi(val); } catch (...) {}
            else if (key == "ctype")    try { ctype  = std::stoi(val); } catch (...) {}
            else if (key == "direc")    try { direc  = std::stoi(val); } catch (...) {}
            else if (key == "nquad")    try { nquad  = std::stoi(val); } catch (...) {}
            else if (key == "pfac")     try { pfac   = std::stod(val); } catch (...) {}
        }
        // flush last ale entry
        if (curEntry.pid > 0) aleEntries.push_back(curEntry);
    }

    if (modelFile.empty())  { console.error("YAML missing 'model' field"); return 1; }
    if (outputFile.empty()) { console.error("YAML missing 'output' field"); return 1; }
    if (aleEntries.empty()) { console.error("YAML missing 'ale_parts' entries"); return 1; }

    // Path resolution
    auto resolvePath = [&](const std::string& p) -> std::string {
        if (!configDir.empty() && !p.empty() &&
            p[0] != '/' && p[0] != '\\' && !(p.size() >= 2 && p[1] == ':') &&
            p.find('/')  == std::string::npos &&
            p.find('\\') == std::string::npos)
            return configDir + "/" + p;
        return p;
    };
    std::string modelPath = resolvePath(modelFile);
    std::string outPath   = resolvePath(outputFile);

    // 2. Read model file
    std::vector<std::string> lines;
    {
        std::ifstream fin(modelPath);
        if (!fin.is_open()) { console.error("Cannot open model: " + modelPath); return 1; }
        std::string ln;
        while (std::getline(fin, ln)) {
            if (!ln.empty() && ln.back() == '\r') ln.pop_back();
            lines.push_back(ln);
        }
    }

    // 3. Build PART map
    auto partMap = ale_buildPartMap(lines);

    // Build ale PID list and set
    std::vector<int> alePids;
    std::set<int> alePidSet;
    for (const auto& e : aleEntries) {
        alePids.push_back(e.pid);
        alePidSet.insert(e.pid);
    }

    // Console header
    {
        std::string pidStr;
        for (const auto& e : aleEntries) {
            if (!pidStr.empty()) pidStr += ", ";
            pidStr += std::to_string(e.pid) + " (" + e.material + ")";
        }
        console.println("[ale] Model    : " + modelFile);
        console.println("[ale] Output   : " + outputFile);
        console.println("[ale] ALE PIDs : " + pidStr);
        if (!fsiPids.empty()) {
            std::string fs;
            for (int p : fsiPids) { if (!fs.empty()) fs += ", "; fs += std::to_string(p); }
            console.println("[ale] FSI PIDs : " + fs);
        }
        console.println("[ale] Unit sys : t/mm/s (preset values in MPa)");
    }

    // 4. Validation — remove invalid entries
    {
        std::vector<AlePartEntry> validEntries;
        for (const auto& e : aleEntries) {
            if (partMap.find(e.pid) == partMap.end()) {
                console.error("[ale] PID " + std::to_string(e.pid) + " not found in model. Skipping.");
            } else {
                validEntries.push_back(e);
            }
        }
        aleEntries = validEntries;
        alePids.clear();
        alePidSet.clear();
        for (const auto& e : aleEntries) { alePids.push_back(e.pid); alePidSet.insert(e.pid); }
    }
    {
        std::vector<int> validFsi;
        for (int fp : fsiPids) {
            if (alePidSet.count(fp)) {
                console.error("[ale] FSI PID " + std::to_string(fp) + " overlaps with ALE PID. Self-coupling not allowed.");
            } else {
                validFsi.push_back(fp);
            }
        }
        fsiPids = validFsi;
    }
    if (aleEntries.empty()) {
        console.error("[ale] No valid ALE parts to process. Aborting.");
        return 1;
    }

    // 5. Find max IDs
    int maxMid = 0, maxEosid = 0, maxSecid = 0, maxHgid = 0;
    ale_findMaxIds(lines, maxMid, maxEosid, maxSecid, maxHgid);
    int nextMid = maxMid + 1;
    int nextEosid = maxEosid + 1;
    int nextSecid = maxSecid + 1;
    int nextHgid  = maxHgid + 1;

    // Allocate a single ALE hourglass ID
    int aleHgid = nextHgid++;

    // 6. Process each ALE part
    std::string insertCards;
    bool hasHe = false;

    for (const auto& entry : aleEntries) {
        if (partMap.find(entry.pid) == partMap.end()) continue;
        const auto& info = partMap[entry.pid];

        // 6a. Handle shared section
        if (ale_isSharedSection(partMap, info.secid, alePidSet)) {
            int newSecid = nextSecid++;
            std::string secCard = ale_duplicateSection(lines, info.secid, newSecid, elform);
            if (!secCard.empty()) {
                insertCards += secCard;
                ale_updatePartField(lines, entry.pid, 10, newSecid); // SECID pos=10
                console.println("[ale] NewSec   : SECID=" + std::to_string(newSecid) +
                    " (copied from " + std::to_string(info.secid) +
                    ", shared) ELFORM -> " + std::to_string(elform));
            } else {
                console.println("[WARNING]  PID=" + std::to_string(entry.pid) +
                    " SECID=" + std::to_string(info.secid) +
                    " — *SECTION_SOLID not found (shell element?)");
            }
        } else {
            // Modify ELFORM in-place
            int oldElform = ale_modifySectionElform(lines, info.secid, elform);
            if (oldElform == elform) {
                console.println("[INFO]  PID=" + std::to_string(entry.pid) +
                    " SECID=" + std::to_string(info.secid) + " already ELFORM=" + std::to_string(elform));
            } else if (oldElform >= 0) {
                console.println("[ale] Modified : *SECTION_SOLID SECID=" + std::to_string(info.secid) +
                    " ELFORM=" + std::to_string(oldElform) + " -> " + std::to_string(elform) +
                    "  (PID=" + std::to_string(entry.pid) + ")");
            } else {
                console.println("[WARNING]  PID=" + std::to_string(entry.pid) +
                    " SECID=" + std::to_string(info.secid) +
                    " — *SECTION_SOLID not found (shell element?)");
            }
        }

        // 6b. Material replacement
        int newMid = nextMid++;
        int newEosid = (entry.material != "vacuum") ? nextEosid++ : 0;

        std::string matCards;
        if (ale_isPreset(entry.material)) {
            matCards = ale_presetMaterial(entry.material, newMid, newEosid);
        } else {
            // Custom bundle file
            std::string bundlePath = resolvePath(entry.material);
            matCards = ale_customMaterial(bundlePath, newMid, newEosid);
            if (matCards.empty()) {
                console.error("[ale] Cannot load bundle: " + entry.material);
                continue;
            }
        }
        insertCards += matCards;

        // Update PART: MID(pos 20), EOSID(pos 30), HGID(pos 40)
        ale_updatePartField(lines, entry.pid, 20, newMid);
        ale_updatePartField(lines, entry.pid, 30, newEosid);
        ale_updatePartField(lines, entry.pid, 40, aleHgid);

        // Determine MAT/EOS type names for console
        std::string matName, eosName;
        std::string matLower = impl_trim(entry.material);
        std::transform(matLower.begin(), matLower.end(), matLower.begin(), ::tolower);
        if (matLower == "tnt" || matLower == "c4") {
            matName = "*MAT_HIGH_EXPLOSIVE_BURN"; eosName = "*EOS_JWL"; hasHe = true;
        } else if (matLower == "vacuum") {
            matName = "*MAT_VACUUM"; eosName = "(none)";
        } else if (matLower == "air" || matLower == "nitrogen" || matLower == "argon") {
            matName = "*MAT_NULL"; eosName = "*EOS_LINEAR_POLYNOMIAL";
        } else if (ale_isPreset(entry.material)) {
            matName = "*MAT_NULL"; eosName = "*EOS_GRUNEISEN";
        } else {
            matName = "custom"; eosName = "custom";
        }
        console.println("[ale] Material : PID=" + std::to_string(entry.pid) +
            " -> " + matName + " (MID=" + std::to_string(newMid) + ") + " +
            eosName + " (EOSID=" + std::to_string(newEosid) + ")");
    }

    // 7. Generate HOURGLASS card
    insertCards += ale_generateHourglass(aleHgid);
    console.println("[ale] Hourglass: HGID=" + std::to_string(aleHgid) + " (IHQ=3, Flanagan-Belytschko)");

    // 8. Remove existing ALE control cards if present, then insert
    {
        size_t before = lines.size();
        lines = impl_removeKeyword(lines, "*CONTROL_ALE");
        if (lines.size() < before) console.println("[WARNING]  Existing *CONTROL_ALE replaced.");
    }
    insertCards += ale_generateControlALE(dct, nadv, meth);
    console.println("[ale] Inserted : *CONTROL_ALE (DCT=" + std::to_string(dct) +
        ", NADV=" + std::to_string(nadv) + ", METH=" + std::to_string(meth) + ")");

    // 9. ALE_MULTI-MATERIAL_GROUP
    {
        size_t before = lines.size();
        lines = impl_removeKeyword(lines, "*ALE_MULTI-MATERIAL_GROUP");
        if (lines.size() < before) console.println("[WARNING]  Existing *ALE_MULTI-MATERIAL_GROUP replaced.");
    }
    insertCards += ale_generateAMMG(alePids);
    console.println("[ale] Inserted : *ALE_MULTI-MATERIAL_GROUP (" +
        std::to_string(alePids.size()) + " groups)");

    // 10. ALE_REFERENCE_SYSTEM_GROUP
    {
        size_t before = lines.size();
        lines = impl_removeKeyword(lines, "*ALE_REFERENCE_SYSTEM_GROUP");
        if (lines.size() < before) console.println("[WARNING]  Existing *ALE_REFERENCE_SYSTEM_GROUP replaced.");
    }
    insertCards += ale_generateRefSystem();
    console.println("[ale] Inserted : *ALE_REFERENCE_SYSTEM_GROUP (PRTYPE=4)");

    // 11. FSI coupling
    if (!fsiPids.empty()) {
        lines = impl_removeKeyword(lines, "*CONSTRAINED_LAGRANGE_IN_SOLID");
        insertCards += ale_generateCLIS(fsiPids, alePids, ctype, direc, nquad, pfac);
        int numClis = (int)fsiPids.size() * (int)alePids.size();
        console.println("[ale] Inserted : *CONSTRAINED_LAGRANGE_IN_SOLID x" +
            std::to_string(numClis));
    }

    // 12. Detonation point
    if (hasDet && detPid > 0) {
        insertCards += ale_generateDetonation(detPid, detX, detY, detZ, detLt);
        console.println("[ale] Inserted : *INITIAL_DETONATION (PID=" +
            std::to_string(detPid) + ")");
    } else if (hasHe && !hasDet) {
        console.println("[WARNING]  HE preset used but no 'detonation:' section in YAML");
    }

    // Insert all generated cards before *END
    impl_insertBeforeEnd(lines, insertCards);

    // 13. Write output
    std::ofstream outf(outPath);
    if (!outf.is_open()) { console.error("Cannot write output: " + outPath); return 1; }
    for (const auto& ln : lines) outf << ln << "\n";
    console.println("[ale] Done     -> " + outputFile);
    return 0;
}

int main(int argc, char* argv[]) {
    ConsoleOutput console;

    // Check for subcommand
    if (argc < 2) {
        printBanner(console);
        console.println("Usage: KooRemapper <command> [options]");
        std::cout << "\n";
        console.println("Commands:");
        console.println("  map         Map a flat mesh onto a bent reference mesh (HEX8)");
        console.println("  shellmap    Map a flat mesh using a bent shell reference (QUAD4)");
        console.println("  unfold      Generate flat mesh from a bent structured mesh");
        console.println("  generate    Generate example meshes for testing");
        console.println("  generate-var Generate variable density mesh from YAML config");
        console.println("  strain      Calculate strain between two meshes");
        console.println("  prestress   Calculate prestress from deformed configuration");
        console.println("  squeeze     Compress parts for interference fit modeling");
        console.println("  assemble    Assemble model with part replace/squeeze operations");
        console.println("  matswap     Swap material bundle for a part (with HOURGLASS/CURVE/SECTION)");
        console.println("  implicit    Convert explicit K-file to implicit solver settings");
        console.println("  modal       Convert explicit K-file to modal (natural frequency) analysis");
        console.println("  ale         Convert parts to ALE (fluid/gas/explosive) with material presets");
        console.println("  info        Display information about a mesh file");
        console.println("  help        Show help for a command");
        console.println("  version     Show version information");
        std::cout << "\n";
        console.println("Use 'KooRemapper help <command>' for more information.");
        return 1;
    }

    std::string command = argv[1];

    // Version command
    if (command == "version" || command == "--version" || command == "-v") {
        console.println("KooRemapper version " + std::string(VERSION));
        return 0;
    }

    // Help command
    if (command == "help" || command == "--help" || command == "-h") {
        if (argc > 2) {
            std::string helpCmd = argv[2];
            if (helpCmd == "map") {
                console.println("Usage: KooRemapper map [--single] <bent_mesh> <flat_mesh> <output>");
                std::cout << "\n";
                console.println("Map a flat unstructured mesh onto a bent structured mesh.");
                std::cout << "\n";
                console.println("Arguments:");
                console.println("  bent_mesh   The bent structured reference mesh (k-file)");
                console.println("  flat_mesh   The flat mesh to be mapped (k-file)");
                console.println("  output      Output file path for the mapped mesh");
                std::cout << "\n";
                console.println("Options:");
                console.println("  --single, -s  Use single-threaded mode (default: parallel)");
                std::cout << "\n";
                console.println("By default, parallel processing is used for faster mapping.");
                console.println("Use --single for debugging or when OpenMP is not available.");
            } else if (helpCmd == "generate") {
                console.println("Usage: KooRemapper generate [options] <type> <output_prefix>");
                std::cout << "\n";
                console.println("Generate example meshes for testing.");
                std::cout << "\n";
                console.println("Arguments:");
                console.println("  type           Mesh type:");
                console.println("                   teardrop, arc, scurve, helix");
                console.println("                   torus, twist, bendtwist, wave, bulge, taper");
                console.println("                   waterdrop (foldable display)");
                console.println("  output_prefix  Prefix for output files");
                std::cout << "\n";
                console.println("Options:");
                console.println("  --dim-i <n>    Number of elements in I direction (default: 10)");
                console.println("  --dim-j <n>    Number of elements in J direction (default: 5)");
                console.println("  --dim-k <n>    Number of elements in K direction (default: 5)");
            } else if (helpCmd == "strain") {
                console.println("Usage: KooRemapper strain [options] <ref_mesh> <def_mesh> <output.csv>");
                std::cout << "\n";
                console.println("Calculate strain tensor between reference and deformed meshes.");
                std::cout << "\n";
                console.println("Arguments:");
                console.println("  ref_mesh   Reference (undeformed) mesh (k-file)");
                console.println("  def_mesh   Deformed mesh (k-file)");
                console.println("  output     Output CSV file for strain data");
                std::cout << "\n";
                console.println("Options:");
                console.println("  --type <t>  Strain type: engineering (default), green, log");
            } else if (helpCmd == "info") {
                console.println("Usage: KooRemapper info <mesh_file>");
                std::cout << "\n";
                console.println("Display information about a mesh file.");
            } else if (helpCmd == "unfold") {
                console.println("Usage: KooRemapper unfold <bent_mesh> <output_flat>");
                std::cout << "\n";
                console.println("Generate a flat (unfolded) mesh from a bent structured mesh.");
                std::cout << "\n";
                console.println("Arguments:");
                console.println("  bent_mesh    The bent structured mesh (k-file)");
                console.println("  output_flat  Output file path for the flat mesh");
                std::cout << "\n";
                console.println("Description:");
                console.println("  This command analyzes a bent structured HEX8 mesh and");
                console.println("  generates a corresponding flat mesh by:");
                console.println("  1. Computing arc-length along the centerline for X dimension");
                console.println("  2. Preserving cross-section size for Y and Z dimensions");
                std::cout << "\n";
                console.println("  The generated flat mesh can be used as a reference for mapping");
                console.println("  detailed flat meshes back to the bent shape.");
            } else if (helpCmd == "prestress") {
                console.println("Usage: KooRemapper prestress [options] <ref_mesh> <def_mesh> <output>");
                std::cout << "\n";
                console.println("Calculate prestress from reference and deformed mesh configurations.");
                std::cout << "\n";
                console.println("Arguments:");
                console.println("  ref_mesh   Reference (undeformed) mesh (k-file)");
                console.println("  def_mesh   Deformed mesh (k-file, same topology)");
                console.println("  output     Output file (dynain format or CSV)");
                std::cout << "\n";
                console.println("Options:");
                console.println("  --E <value>      Young's modulus (overrides K-file materials)");
                console.println("  --nu <value>     Poisson's ratio (overrides K-file materials)");
                console.println("  --strain <type>  Strain type: engineering, green (default)");
                console.println("  --csv            Also output strain/stress CSV file");
                std::cout << "\n";
                console.println("Material Properties:");
                console.println("  The tool automatically reads *PART and *MAT_ELASTIC cards from");
                console.println("  the reference K-file. Each element uses its part's material.");
                console.println("  If --E and --nu are specified, they override K-file materials.");
                std::cout << "\n";
                console.println("Description:");
                console.println("  Computes strain tensor from mesh deformation.");
                console.println("  If materials are available (from K-file or command line),");
                console.println("  computes stress using Hooke's law and outputs *INITIAL_STRESS_SOLID");
                console.println("  cards in dynain format.");
            } else if (helpCmd == "generate-var") {
                console.println("Usage: KooRemapper generate-var [options] <config.yaml> <output.k>");
                std::cout << "\n";
                console.println("Generate mesh from YAML configuration (flat or curved).");
                std::cout << "\n";
                console.println("Arguments:");
                console.println("  config.yaml  YAML configuration file");
                console.println("  output.k     Output K-file");
                std::cout << "\n";
                console.println("Options:");
                console.println("  --ref <file>   Reference flat mesh for scaling");
                console.println("  --no-scale     Don't scale to reference (use YAML lengths as-is)");
                std::cout << "\n";
                console.println("YAML Format (Flat Variable Density):");
                console.println("  type: flat  # Optional, default is flat");
                console.println("  reference:");
                console.println("    flat_mesh: \"ref_flat.k\"  # Reference for auto-scaling");
                console.println("  elements_j: 50");
                console.println("  elements_k: 10");
                console.println("  variable_density:");
                console.println("    zone1_dense_start:");
                console.println("      length: 10.0");
                console.println("      num_elements: 50");
                console.println("    ...");
                std::cout << "\n";
                console.println("YAML Format (Curved from Centerline):");
                console.println("  type: curved");
                console.println("  reference:");
                console.println("    flat_mesh: \"ref_flat.k\"  # For scaling (optional)");
                console.println("  centerline_points:");
                console.println("    - [0, 0]");
                console.println("    - [50, 0]");
                console.println("    - [100, 50]");
                console.println("    - [150, 50]");
                console.println("  interpolation: catmull_rom  # linear, catmull_rom, bspline");
                console.println("  cross_section:  # Only if no reference");
                console.println("    width: 10.0");
                console.println("    thickness: 2.0");
                console.println("  elements_along_curve: 100");
                console.println("  elements_j: 20");
                console.println("  elements_k: 5");
            } else if (helpCmd == "shellmap") {
                console.println("Usage: KooRemapper shellmap [options] <bent_shell> <flat_detail> <output>");
                std::cout << "\n";
                console.println("Map a flat detail mesh onto a bent QUAD4 shell reference mesh.");
                std::cout << "\n";
                console.println("Arguments:");
                console.println("  bent_shell   Bent shell reference mesh (QUAD4 elements, k-file)");
                console.println("  flat_detail  Flat detail mesh to be mapped (solid or shell, k-file)");
                console.println("  output       Output file path for the mapped mesh");
                std::cout << "\n";
                console.println("Options:");
                console.println("  --thickness <t>  Shell thickness for Z-offset mapping");
                console.println("                   Default: auto-detect from flat mesh Z-range");
                std::cout << "\n";
                console.println("Description:");
                console.println("  Unlike 'map' (which requires a structured HEX8 reference),");
                console.println("  'shellmap' uses an unstructured QUAD4 shell as reference.");
                console.println("  The shell is unfolded to a flat plane (edge-length preserving),");
                console.println("  then flat detail nodes are mapped onto the bent shell surface.");
                std::cout << "\n";
                console.println("  Best for: developable surfaces (single curvature, e.g. cylinders).");
                console.println("  Non-developable surfaces will show a distortion warning.");
            } else if (helpCmd == "squeeze") {
                console.println("Usage: KooRemapper squeeze <mesh.k> <config.yaml> <output_prefix>");
                std::cout << "\n";
                console.println("Compress parts for interference fit modeling.");
                std::cout << "\n";
                console.println("Arguments:");
                console.println("  mesh.k         Input mesh with multiple parts (k-file)");
                console.println("  config.yaml    YAML config specifying per-part strain conditions");
                console.println("  output_prefix  Output prefix (generates .k and _dynain.dat)");
                std::cout << "\n";
                console.println("Output:");
                console.println("  <prefix>.k          Compressed mesh with *INCLUDE dynain");
                console.println("  <prefix>_dynain.dat  Reverse prestress (*INITIAL_STRESS_SOLID)");
                std::cout << "\n";
                console.println("YAML Config Format:");
                console.println("  parts:");
                console.println("    - pid: 1");
                console.println("      eps_x: 0.0");
                console.println("      eps_y: 0.0");
                console.println("      eps_z: -0.02      # 2% compression in Z");
                console.println("    - pid: 3");
                console.println("      eps_x: -0.01");
                console.println("      eps_y: -0.01");
                console.println("  material:              # Optional (overrides K-file)");
                console.println("    E: 210000.0");
                console.println("    nu: 0.3");
                std::cout << "\n";
                console.println("Description:");
                console.println("  For each specified part:");
                console.println("  1. Computes bounding box center (neutral plane)");
                console.println("  2. Compresses nodes by specified strain relative to center");
                console.println("  3. Generates reverse (tensile) prestress via Hooke's law");
                console.println("  Use with LS-DYNA dynamic relaxation to model interference fits.");
            } else if (helpCmd == "assemble") {
                console.println("Usage: KooRemapper assemble <config.yaml>");
                std::cout << "\n";
                console.println("Assemble a full model with sequential part operations.");
                std::cout << "\n";
                console.println("Arguments:");
                console.println("  config.yaml  YAML config specifying base model, operations, and material");
                std::cout << "\n";
                console.println("Output:");
                console.println("  <output>.k          Assembled model (all keywords preserved)");
                console.println("  <output>.dynain     Accumulated prestress (*INITIAL_STRESS_SOLID)");
                std::cout << "\n";
                console.println("YAML Top-level Keys:");
                console.println("  base_model: model.k          # Input K-file");
                console.println("  output: result               # Output prefix (no extension)");
                console.println("  dynamic_relaxation: true     # Insert *CONTROL_DYNAMIC_RELAXATION");
                console.println("  dynain_embed: true           # Embed dynain inline (no .dynain file)");
                console.println("  material:");
                console.println("    E: 210000.0                # Global Young's modulus");
                console.println("    nu: 0.3                    # Global Poisson's ratio");
                std::cout << "\n";
                console.println("Operation Types:");
                std::cout << "\n";
                console.println("  replace      Replace part with mapped detail mesh");
                console.println("    target_pid: 3              # Part to replace");
                console.println("    detail_flat: detail.k      # Flat detail mesh");
                console.println("    shell_bent:  ref.k         # Bent QUAD4 shell reference");
                console.println("    prestress: true            # Compute bending prestress");
                std::cout << "\n";
                console.println("  squeeze      Interference fit - compress part nodes");
                console.println("    target_pid: 5");
                console.println("    eps_x: -0.02  eps_y: 0.0  eps_z: 0.0");
                std::cout << "\n";
                console.println("  restack      Extrude/restack layers (solid rebuild)");
                console.println("    source_pid: 2              # Source part to extrude from");
                console.println("    layers:                    # Layer stack definition");
                console.println("      - pid: 10  thickness: 0.3  secid: 1  mid: 1  hgid: 1");
                console.println("      - pid: 11  thickness: 0.5  secid: 2  mid: 2  hgid: 1");
                std::cout << "\n";
                console.println("  bend         Apply bending deformation + prestress");
                console.println("    target_pid: 3");
                console.println("    deflection_file: bend.dat  # Grid deflection data (CSV)");
                console.println("    plane: xy                  # Bending plane (xy/xz/yz)");
                console.println("    thickness: 0.5");
                std::cout << "\n";
                console.println("  indent       Apply indentation/embossing deformation + prestress");
                console.println("    target_pid: 3");
                console.println("    depth: 0.5                 # Indent depth (negative = emboss)");
                console.println("    r1: 2.0  r2: 1.0           # Fillet radii");
                console.println("    center_x: 50.0  center_y: 30.0");
                console.println("    direction: z               # Indent axis (x/y/z)");
                console.println("    thickness: 0.5");
                std::cout << "\n";
                console.println("  formstrain   Compute plastic strain from shell dihedral angles");
                console.println("    target_pid: 3");
                console.println("    shell_thickness: 0.5");
                std::cout << "\n";
                console.println("  refine       Mesh refinement (1:2 or 1:3 subdivision)");
                console.println("    target_pid: 3");
                console.println("    ratio: 2                   # 2 or 3");
                std::cout << "\n";
                console.println("  elform       Change element formulation (ELFORM)");
                console.println("    target_pid: 3");
                console.println("    target_elform: hex20       # tet4/hex8/hex20/tet10/quad8/tria6");
                std::cout << "\n";
                console.println("  disconnect   Decohere conformal mesh (full/czm/mefem)");
                console.println("    target_pid: 3");
                console.println("    mode: czm                  # full / czm / mefem");
                console.println("    cohesive_part_id: 99       # CZM/MEFEM: new cohesive part ID");
                console.println("    failure_strain: 0.1        # CZM: failure strain");
                std::cout << "\n";
                console.println("  iga          Embed FE part in IGA (NURBS) trivariate box");
                console.println("    targets:");
                console.println("      - target_pid: 3");
                console.println("        element_size: 0.6      # NURBS box voxel size");
                console.println("        pr: 1  ps: 1  pt: 1    # Polynomial order");
                console.println("        ir: 0                  # Integration: 0=reduced, 1=full");
                std::cout << "\n";
                console.println("  offset       Extrude surface elements to solid layer(s)");
                console.println("    source_pid: 3");
                console.println("    thickness: 1.0");
                console.println("    offset_direction: +normal  # +normal/-normal/+x/-x/+y/-y/+z/-z");
                console.println("    num_layers: 1");
                console.println("    connection_mode: tied      # tied / czm / contact");
                console.println("    use_local_normals: true    # Per-node normal averaging");
                console.println("    swap_all: false            # Region filter: bbox/node_id/element_id");
                std::cout << "\n";
                console.println("  warpage      Apply warpage (out-of-plane deflection) to shell");
                console.println("    dat_file: warp.dat         # Warpage measurement data");
                console.println("    plane: xy                  # Shell plane");
                console.println("    deflection_axis: z");
                console.println("    target_pid: 3");
                std::cout << "\n";
                console.println("  matswap      Replace material bundle (MAT+HG+CURVE+SECTION)");
                console.println("    bundle: rubber.k           # Bundle file with *PARAMETER block");
                console.println("    pid: 1                     # Single PID");
                console.println("    pids: [1, 2, 3]            # Multiple PIDs");
                console.println("    swap_all: true             # All parts in model");
                std::cout << "\n";
                console.println("Examples: see examples/ directory");
                console.println("  examples/offset/   examples/iga/   examples/matswap/");
                console.println("  examples/disconnect/   examples/formstrain/");
            } else if (helpCmd == "matswap") {
                console.println("Usage: KooRemapper matswap <config.yaml>");
                console.println("       KooRemapper matswap <model.k> <bundle.k> <pid> <output.k>");
                std::cout << "\n";
                console.println("Replace material bundle for one or more parts.");
                console.println("Replaces MAT + HOURGLASS + DEFINE_CURVE + SECTION as a complete unit.");
                std::cout << "\n";
                console.println("YAML Config Format:");
                console.println("  model: model.k");
                console.println("  output: result.k");
                console.println("  swaps:");
                console.println("    - bundle: rubber.k         # Bundle file (with *PARAMETER block)");
                console.println("      pid: 1                   # Single PID");
                console.println("    - bundle: foam.k");
                console.println("      pids: [2, 3, 5]          # Multiple PIDs");
                console.println("    - bundle: rubber.k");
                console.println("      swap_all: true           # All parts in model");
                std::cout << "\n";
                console.println("Bundle File Format (*.k with *PARAMETER):");
                console.println("  *PARAMETER");
                console.println("  I HGID1            1I LCID1            1");
                console.println("  I MID1             1I SECID1           1");
                console.println("  I PID1             1");
                console.println("  *HOURGLASS_TITLE");
                console.println("  ...   &HGID1 ...");
                console.println("  *DEFINE_CURVE_TITLE");
                console.println("  ...   &LCID1 ...");
                console.println("  *MAT_...");
                console.println("  ... &MID1 ... &LCID1 ...");
                console.println("  *SECTION_SOLID_TITLE");
                console.println("  ...   &SECID1 ...");
                console.println("  *PART");
                console.println("  ...   &PID1   &SECID1   &MID1   ...   &HGID1 ...");
                console.println("  *END");
                std::cout << "\n";
                console.println("Parameter name prefix convention:");
                console.println("  HGID*  -> Hourglass ID  (always new ID = model max + 1)");
                console.println("  LCID*  -> Curve ID      (always new ID = model max + 1)");
                console.println("  SECID* -> Section ID    (always new ID = model max + 1)");
                console.println("  MID*   -> Material ID   (reuse orphan ID if possible)");
                console.println("  PID*   -> Part ID       (skipped - PART card not inserted)");
                std::cout << "\n";
                console.println("Note: Output file has no *PARAMETER block (resolved to numbers).");
                console.println("      Orphaned old MAT/SECTION/HOURGLASS cards are auto-removed.");
                console.println("      Shared cards (used by non-target parts) are preserved.");
                std::cout << "\n";
                console.println("Examples: see examples/matswap/");
            } else if (helpCmd == "implicit") {
                console.println("Usage: KooRemapper implicit <config.yaml>");
                std::cout << "\n";
                console.println("Convert an explicit LS-DYNA K-file to implicit solver settings.");
                console.println("Removes explicit-only cards and inserts CONTROL_IMPLICIT_* blocks.");
                std::cout << "\n";
                console.println("YAML Config Format:");
                console.println("  model: explicit.k");
                console.println("  output: implicit.k");
                console.println("  mode: static           # static(IMASS=0) | dynamic(IMASS=1), default=static");
                console.println("  level: 2               # 1(aggressive)~7(max stability), default=2");
                console.println("  endtime: 1.0           # optional: update *CONTROL_TERMINATION + DT base");
                console.println("");
                console.println("  # Fine-grained overrides (level defaults used if omitted):");
                console.println("  dctol:                 # Displacement convergence tolerance");
                console.println("  ectol:                 # Energy convergence tolerance");
                console.println("  dt0:                   # Initial timestep");
                console.println("  dtmax:                 # Maximum timestep");
                console.println("  nsolvr:                # Nonlinear solver (12=BFGS, -2=BFGS+line search)");
                console.println("  kfail:                 # Step cuts before stiffness reform (0=none)");
                console.println("  rctol:                 # Residual force tolerance (1e10=disabled default)");
                console.println("  lsolvr:                # Linear solver (7=default sparse, 30=MUMPS)");
                console.println("  stab: false            # *CONTROL_IMPLICIT_STABILIZATION on/off override");
                console.println("  stab_scale: 1.0        # Stabilization SCALE factor (smaller=more stabilization)");
                console.println("  arc_length: false      # Arc-length method on/off (auto-sets NSOLVR=7 if needed)");
                console.println("");
                console.println("  # Cleanup options:");
                console.println("  fix_shell_elform: false  # true: ELFORM=16->2 auto-fix (default: warn only)");
                console.println("  keep_dr_curves: false    # true: keep SIDR=1 DEFINE_CURVEs (default: remove)");
                std::cout << "\n";
                console.println("Level Spectrum --- Table 1: Nonlinear solver & convergence tolerances");
                console.println("  Lv  Name           NSOLVR  ILIM  MXREF  ITOPT  KFAIL   DCTOL   ECTOL   LSTOL   RCTOL");
                console.println("  --  -------------  ------  ----  -----  -----  -----  ------  ------  ------  ------");
                console.println("   1  공격적           12     11    10     11      0    0.0050  0.0500  0.90    (off)");
                console.println("   2  표준             12     11    15     11      0    0.0010  0.0100  0.90    (off)");
                console.println("   3  안정             12     15    20     11      0    0.0010  0.0100  0.95    (off)");
                console.println("   4  수렴우선         -2     20    25     11      3    0.0010  0.0100  0.95    (off)");
                console.println("   5  강건             -2     25    30     15      5    0.0010  0.0050  0.99    (off)");
                console.println("   6  고강건           -2     30    40     15      8    0.0005  0.0020  0.99    0.1");
                console.println("   7  최대안정         -2     40    50     20     15    0.0001  0.0010  0.99    0.01");
                console.println("   8  좌굴/스냅스루     7*     40    50     20     15    0.0001  0.0010  0.99    0.01");
                console.println("  * NSOLVR=7 (Full Newton): arc-length requires NSOLVR in [6..9]");
                console.println("  ILIM=ILIMIT, MXREF=MAXREF, ITOPT=ITEOPT, RCTOL off = 1E+10 (disabled)");
                std::cout << "\n";
                console.println("Level Spectrum --- Table 2: Time stepping & activated features");
                console.println("  Lv  DT0         DTMAX       DTMIN         LSOLVR        STAB    ARC-LEN");
                console.println("  --  ----------  ----------  ------------  ------------  ------  -------");
                console.println("   1  T/100       T/20        -T/1000       7 (default)   off     off");
                console.println("   2  T/500       T/100       -T/10000      7 (default)   off     off");
                console.println("   3  T/1000      T/200       -T/10000      7 (default)   off     off");
                console.println("   4  T/2000      T/500       -T/100000     7 (default)   off     off");
                console.println("   5  T/5000      T/1000      -T/100000     7 (default)   ON      off");
                console.println("   6  T/10000     T/2000      -T/100000     30 (MUMPS)    ON      off");
                console.println("   7  T/50000     T/10000     -T/1000000    30 (MUMPS)    ON      off");
                console.println("   8  T/50000     T/10000     -T/1000000    30 (MUMPS)    ON      ON(Crisfield)");
                std::cout << "\n";
                console.println("Feature notes:");
                console.println("  KFAIL     : reform tangent stiffness after N consecutive step bisections");
                console.println("  LSTOL     : line search convergence tolerance (NSOLVR=-2 only)");
                console.println("  RCTOL     : residual force norm tolerance (off=1e10; try 0.1 to activate)");
                console.println("  STAB(IAS) : *CONTROL_IMPLICIT_STABILIZATION IAS=1 - artificial stiffness");
                console.println("              prevents singular K from rigid body modes / springback unloading");
                console.println("  MUMPS(30) : *CONTROL_IMPLICIT_SOLVER LSOLVR=30 - parallel direct solver");
                console.println("              more robust for ill-conditioned/contact-heavy stiffness matrices");
                console.println("  ARC-LEN   : *CONTROL_IMPLICIT_SOLUTION Card3 - Crisfield arc-length method");
                console.println("              ARCCTL=0(generalized), ARCMTH=1(Crisfield), ARCDMP=2(off)");
                console.println("              use when load-displacement path has negative slope (snap-through)");
                std::cout << "\n";
                console.println("Removed cards:");
                console.println("  *CONTROL_DYNAMIC_RELAXATION  (always)");
                console.println("  *CONTROL_BULK_VISCOSITY       (always)");
                console.println("  *DATABASE_BINARY_D3DRLF       (always)");
                console.println("  *DEFINE_CURVE with SIDR=1     (unless keep_dr_curves: true)");
                std::cout << "\n";
                console.println("Inserted cards (always):");
                console.println("  *CONTROL_IMPLICIT_GENERAL / DYNAMICS / SOLUTION / AUTO");
                console.println("Inserted cards (level 5+):");
                console.println("  *CONTROL_IMPLICIT_STABILIZATION");
                console.println("Inserted cards (level 6+):");
                console.println("  *CONTROL_IMPLICIT_SOLVER (MUMPS)");
                console.println("Inserted cards (level 8 / arc_length:true):");
                console.println("  *CONTROL_IMPLICIT_SOLUTION Card 3 (arc-length parameters)");
                std::cout << "\n";
                console.println("Mode: static vs dynamic");
                console.println("  static   IMASS=0, GAMMA=0.5, BETA=0.25  (quasi-static loading)");
                console.println("  dynamic  IMASS=1, GAMMA=0.6, BETA=0.30  (structural dynamics, num. damping)");
            } else if (helpCmd == "modal") {
                console.println("Usage: KooRemapper modal <config.yaml>");
                std::cout << "\n";
                console.println("Convert an explicit LS-DYNA K-file for natural frequency (modal) analysis.");
                console.println("Removes explicit-only cards and inserts *CONTROL_IMPLICIT_EIGENVALUE.");
                std::cout << "\n";
                console.println("YAML Config Format:");
                console.println("  model: explicit.k          # Input explicit K-file");
                console.println("  output: modal.k            # Output file");
                console.println("");
                console.println("  # Key parameters (all have defaults):");
                console.println("  nmode:  10                 # Number of modes to extract (default: 10)");
                console.println("  fmin:   0.0                # Lower frequency bound Hz (default: 0 = no limit)");
                console.println("  fmax:   2000.0             # Upper frequency bound Hz (default: 0 = no limit)");
                console.println("");
                console.println("  # Advanced (optional):");
                console.println("  center: 0.0                # Frequency shift center Hz (default: 0.0)");
                console.println("  eigmth: 2                  # Eigensolver method (see below)");
                console.println("  solver: 7                  # Linear solver (7=default sparse, 30=MUMPS)");
                console.println("  fix_shell_elform: false    # true: ELFORM=16->2 auto-fix (default: warn)");
                console.println("  keep_dr_curves:  false     # true: keep SIDR=1 DEFINE_CURVEs (default: remove)");
                std::cout << "\n";
                console.println("Eigenvalue method (eigmth):");
                console.println("  2   Block Shift Lanczos   -- general purpose (default)");
                console.println("  101 MCMS                  -- NVH, thousands of modes");
                console.println("  102 LOBPCG                -- large models, iterative");
                console.println("  103 Fast Lanczos          -- MPP parallel");
                std::cout << "\n";
                console.println("Frequency limits:");
                console.println("  fmin=0 (default) -> LFLAG=0 (no lower bound, searches from -inf)");
                console.println("  fmin>0           -> LFLAG=1, LFTEND=fmin Hz");
                console.println("  fmax=0 (default) -> RFLAG=0 (no upper bound)");
                console.println("  fmax>0           -> RFLAG=1, RHTEND=fmax Hz");
                std::cout << "\n";
                console.println("Output files (automatic, no DATABASE card needed):");
                console.println("  eigout   ASCII frequency list (natural frequencies in Hz)");
                console.println("  d3eigv   Binary mode shapes (view in LS-PrePost)");
                std::cout << "\n";
                console.println("Removed cards:");
                console.println("  *CONTROL_DYNAMIC_RELAXATION  (always)");
                console.println("  *CONTROL_BULK_VISCOSITY       (always)");
                console.println("  *DATABASE_BINARY_D3DRLF       (always)");
                console.println("  *DEFINE_CURVE with SIDR=1     (unless keep_dr_curves: true)");
                std::cout << "\n";
                console.println("Inserted cards:");
                console.println("  *CONTROL_IMPLICIT_GENERAL   (IMFLAG=1, DT0=1.0, IMFORM=2, IGS=2)");
                console.println("  *CONTROL_IMPLICIT_EIGENVALUE (NEIG, LFLAG/RFLAG, EIGMTH)");
                console.println("  *CONTROL_IMPLICIT_SOLUTION  (NSOLVR=12, standard tolerances)");
                console.println("  *CONTROL_IMPLICIT_SOLVER    (only when solver: 30)");
                std::cout << "\n";
                console.println("Examples: see examples/modal/");
            } else if (helpCmd == "ale") {
                console.println("Usage: KooRemapper ale <config.yaml>");
                std::cout << "\n";
                console.println("Convert parts to ALE (Arbitrary Lagrangian-Eulerian) with material presets.");
                console.println("Changes ELFORM, inserts CONTROL_ALE, AMMG, material cards, and FSI coupling.");
                std::cout << "\n";
                console.println("YAML Config Format:");
                console.println("  model:   explicit.k");
                console.println("  output:  ale.k");
                console.println("");
                console.println("  ale_parts:                  # Parts to convert (required)");
                console.println("    - pid: 3");
                console.println("      material: air           # Preset name or custom .k bundle path");
                console.println("    - pid: 4");
                console.println("      material: water");
                console.println("");
                console.println("  fsi_pids: [1, 2]            # Lagrangian parts for FSI coupling (optional)");
                console.println("  elform: 11                  # ALE ELFORM (11=multi-mat, 12=single, default: 11)");
                console.println("");
                console.println("  # *CONTROL_ALE options (optional):");
                console.println("  dct:  1       # Advection logic (1=default, -1=improved)");
                console.println("  nadv: 1       # Advection cycles (default: 1)");
                console.println("  meth: 2       # Advection method (2=Van Leer, default)");
                console.println("");
                console.println("  # FSI options (*CONSTRAINED_LAGRANGE_IN_SOLID, optional):");
                console.println("  ctype: 2      # Coupling type (2=accel+vel, default)");
                console.println("  pfac:  0.1    # Penalty factor");
                console.println("");
                console.println("  # Detonation point (for he/c4 presets, optional):");
                console.println("  detonation:");
                console.println("    pid: 5");
                console.println("    x: 100.0");
                console.println("    y: 50.0");
                console.println("    z: 0.0");
                console.println("    lt: 0.0     # Detonation time");
                std::cout << "\n";
                console.println("Material presets (unit: t/mm/s -> MPa):");
                console.println("  Gas (MAT_NULL + EOS_LINEAR_POLYNOMIAL):");
                console.println("    air        rho=1.293e-12  gamma=1.40");
                console.println("    nitrogen   rho=1.165e-12  gamma=1.40");
                console.println("    argon      rho=1.661e-12  gamma=1.67");
                console.println("  Liquid (MAT_NULL + EOS_GRUNEISEN):");
                console.println("    water       rho=1.00e-9   C=1484   S1=1.979");
                console.println("    electrolyte rho=1.18e-9   C=1200   S1=1.58   (battery)");
                console.println("    gasoline    rho=7.50e-10  C=1250   S1=1.60   (fuel tank)");
                console.println("    oil         rho=8.70e-10  C=1350   S1=1.80   (hydraulic)");
                console.println("    coolant     rho=1.08e-9   C=1600   S1=1.85   (50% EG)");
                console.println("    resin       rho=1.15e-9   C=1700   S1=1.70   MU=1e-5 (epoxy)");
                console.println("    tim         rho=2.80e-9   C=1800   S1=1.60   MU=5e-4 (gap filler)");
                console.println("    silicone    rho=1.05e-9   C=1050   S1=1.50   MU=1e-4 (gel/oil)");
                console.println("  Explosive (MAT_HIGH_EXPLOSIVE_BURN + EOS_JWL):");
                console.println("    tnt        rho=1.63e-9  D=6.93e6  PCJ=21000");
                console.println("    c4         rho=1.60e-9  D=8.19e6  PCJ=28000");
                console.println("  Special:");
                console.println("    vacuum     MAT_VACUUM (rho~1e-18, void filler)");
                std::cout << "\n";
                console.println("Auto-inserted cards:");
                console.println("  *SECTION_SOLID     ELFORM modified (or new section if shared)");
                console.println("  *MAT_* + *EOS_*    Per-part material replacement");
                console.println("  *HOURGLASS         IHQ=3 Flanagan-Belytschko for ALE");
                console.println("  *CONTROL_ALE       Advection control");
                console.println("  *ALE_MULTI-MATERIAL_GROUP    Material group definition");
                console.println("  *ALE_REFERENCE_SYSTEM_GROUP  Mesh smoothing (PRTYPE=4)");
                console.println("  *CONSTRAINED_LAGRANGE_IN_SOLID  FSI coupling (if fsi_pids)");
                console.println("  *INITIAL_DETONATION             Detonation point (if he/c4)");
                std::cout << "\n";
                console.println("Examples: see examples/ale/");
            } else {
                console.error("Unknown command: " + helpCmd);
                return 1;
            }
        } else {
            printBanner(console);
            console.println("Usage: KooRemapper <command> [options]");
            std::cout << "\n";
            console.println("Commands:");
            console.println("  map          Map a flat mesh onto a bent reference mesh (HEX8)");
            console.println("  shellmap     Map a flat mesh using a bent shell reference (QUAD4)");
            console.println("  unfold       Generate flat mesh from a bent structured mesh");
            console.println("  generate     Generate example meshes for testing");
            console.println("  generate-var Generate variable density mesh from YAML config");
            console.println("  strain       Calculate strain between two meshes");
            console.println("  prestress    Calculate prestress from deformed configuration");
            console.println("  squeeze      Compress parts for interference fit modeling");
            console.println("  assemble     Assemble model with sequential part operations");
            console.println("  matswap      Replace material bundle (MAT+HG+CURVE+SECTION) for parts");
            console.println("  implicit     Convert explicit K-file to implicit solver settings");
            console.println("  modal        Convert explicit K-file to modal (natural frequency) analysis");
            console.println("  ale          Convert parts to ALE with material presets");
            console.println("  info         Display information about a mesh file");
            console.println("  help         Show help for a command");
            console.println("  version      Show version information");
            std::cout << "\n";
            console.println("Use 'KooRemapper help <command>' for details.");
            console.println("  Key commands: help assemble  help implicit  help modal  help ale");
        }
        return 0;
    }

    // Map command
    if (command == "map") {
        // Parse options
        bool useParallel = true;  // Default: parallel mode
        std::vector<std::string> positionalArgs;

        for (int i = 2; i < argc; ++i) {
            std::string arg = argv[i];
            if (arg == "--single" || arg == "-s") {
                useParallel = false;
            } else if (arg[0] != '-') {
                positionalArgs.push_back(arg);
            }
        }

        if (positionalArgs.size() < 3) {
            console.error("Usage: KooRemapper map [--single] <bent_mesh> <flat_mesh> <output>");
            console.println("Options:");
            console.println("  --single, -s  Use single-threaded mode (default: parallel)");
            return 1;
        }
        printBanner(console);
        return runMapping(positionalArgs[0], positionalArgs[1], positionalArgs[2], console, useParallel);
    }

    // Shell-based mapping command
    if (command == "shellmap") {
        double thickness = -1.0;  // Auto-detect
        std::vector<std::string> positionalArgs;

        for (int i = 2; i < argc; ++i) {
            std::string arg = argv[i];
            if (arg == "--thickness" && i + 1 < argc) {
                try {
                    thickness = std::stod(argv[++i]);
                } catch (...) {
                    console.error("Invalid thickness value");
                    return 1;
                }
            } else if (arg[0] != '-') {
                positionalArgs.push_back(arg);
            }
        }

        if (positionalArgs.size() < 3) {
            console.error("Usage: KooRemapper shellmap [--thickness <t>] <bent_shell> <flat_detail> <output>");
            return 1;
        }
        printBanner(console);
        return runShellMapping(positionalArgs[0], positionalArgs[1], positionalArgs[2],
                              thickness, console);
    }

    // Unfold command
    if (command == "unfold") {
        if (argc < 4) {
            console.error("Usage: KooRemapper unfold <bent_mesh> <output_flat>");
            return 1;
        }
        printBanner(console);
        return runUnfold(argv[2], argv[3], console);
    }

    // Generate command
    if (command == "generate") {
        ArgumentParser parser("KooRemapper generate", "Generate example meshes");
        parser.addPositional("type", "Mesh type: teardrop, arc, scurve, helix");
        parser.addPositional("output_prefix", "Prefix for output files");
        parser.addOption("", "dim-i", "Elements in I direction", "10");
        parser.addOption("", "dim-j", "Elements in J direction", "5");
        parser.addOption("", "dim-k", "Elements in K direction", "5");

        // Repack arguments for parser
        int subArgc = argc - 1;
        char** subArgv = argv + 1;

        if (!parser.parse(subArgc, subArgv)) {
            console.error(parser.getError());
            return 1;
        }

        std::string type = parser.getPositional("type");
        std::string prefix = parser.getPositional("output_prefix");

        if (type.empty() || prefix.empty()) {
            console.error("Usage: KooRemapper generate [options] <type> <output_prefix>");
            console.info("Types: teardrop, arc, scurve, helix");
            return 1;
        }

        int dimI = parser.getInt("dim-i").value_or(10);
        int dimJ = parser.getInt("dim-j").value_or(5);
        int dimK = parser.getInt("dim-k").value_or(5);

        printBanner(console);
        return runGenerate(type, prefix, dimI, dimJ, dimK, console);
    }

    // Generate-var command
    if (command == "generate-var") {
        ArgumentParser parser("KooRemapper generate-var", "Generate variable density mesh");
        parser.addPositional("config", "YAML configuration file");
        parser.addPositional("output", "Output K-file");
        parser.addOption("", "ref", "Reference flat mesh for scaling", "");
        parser.addFlag("", "no-scale", "Don't scale to reference");

        int subArgc = argc - 1;
        char** subArgv = argv + 1;

        if (!parser.parse(subArgc, subArgv)) {
            console.error(parser.getError());
            return 1;
        }

        std::string configFile = parser.getPositional("config");
        std::string outputFile = parser.getPositional("output");
        std::string refFile = parser.getOption("ref");
        bool noScale = parser.hasFlag("no-scale");

        if (configFile.empty() || outputFile.empty()) {
            console.error("Usage: KooRemapper generate-var [options] <config.yaml> <output.k>");
            return 1;
        }

        printBanner(console);
        return runGenerateVar(configFile, outputFile, refFile, noScale, console);
    }

    // Strain command
    if (command == "strain") {
        ArgumentParser parser("KooRemapper strain", "Calculate strain between meshes");
        parser.addPositional("ref_mesh", "Reference mesh (k-file)");
        parser.addPositional("def_mesh", "Deformed mesh (k-file)");
        parser.addPositional("output", "Output CSV file");
        parser.addOption("", "type", "Strain type: engineering, green, log", "engineering");

        int subArgc = argc - 1;
        char** subArgv = argv + 1;

        if (!parser.parse(subArgc, subArgv)) {
            console.error(parser.getError());
            return 1;
        }

        std::string refFile = parser.getPositional("ref_mesh");
        std::string defFile = parser.getPositional("def_mesh");
        std::string output = parser.getPositional("output");
        std::string strainType = parser.getOption("type");
        if (strainType.empty()) strainType = "engineering";

        if (refFile.empty() || defFile.empty() || output.empty()) {
            console.error("Usage: KooRemapper strain [options] <ref_mesh> <def_mesh> <output.csv>");
            return 1;
        }

        printBanner(console);
        return runStrain(refFile, defFile, output, strainType, console);
    }

    // Prestress command
    if (command == "prestress") {
        ArgumentParser parser("KooRemapper prestress", "Calculate prestress");
        parser.addPositional("ref_mesh", "Reference mesh (k-file)");
        parser.addPositional("def_mesh", "Deformed mesh (k-file)");
        parser.addPositional("output", "Output file (dynain or csv)");
        parser.addOption("", "E", "Young's modulus", "0");
        parser.addOption("", "nu", "Poisson's ratio", "0");
        parser.addOption("", "strain", "Strain type: engineering, green", "engineering");
        parser.addFlag("", "csv", "Output CSV file");

        int subArgc = argc - 1;
        char** subArgv = argv + 1;

        if (!parser.parse(subArgc, subArgv)) {
            console.error(parser.getError());
            return 1;
        }

        std::string refFile = parser.getPositional("ref_mesh");
        std::string defFile = parser.getPositional("def_mesh");
        std::string output = parser.getPositional("output");
        
        if (refFile.empty() || defFile.empty() || output.empty()) {
            console.error("Usage: KooRemapper prestress [options] <ref_mesh> <def_mesh> <output>");
            return 1;
        }

        double E = parser.getDouble("E").value_or(0.0);
        double nu = parser.getDouble("nu").value_or(0.0);
        std::string strainTypeStr = parser.getOption("strain");
        bool outputCSV = parser.hasFlag("csv");

        StrainType strainType = StrainType::GREEN_LAGRANGE;
        if (strainTypeStr == "engineering") {
            strainType = StrainType::ENGINEERING;
        }

        printBanner(console);
        return runPrestress(refFile, defFile, output, E, nu, strainType, outputCSV, console);
    }

    // Squeeze command
    if (command == "squeeze") {
        std::vector<std::string> positionalArgs;

        for (int i = 2; i < argc; ++i) {
            std::string arg = argv[i];
            if (arg[0] != '-') {
                positionalArgs.push_back(arg);
            }
        }

        if (positionalArgs.size() < 3) {
            console.error("Usage: KooRemapper squeeze <mesh.k> <config.yaml> <output_prefix>");
            return 1;
        }
        printBanner(console);
        return runSqueeze(positionalArgs[0], positionalArgs[1], positionalArgs[2], console);
    }

    // Assemble command
    if (command == "assemble") {
        if (argc < 3) {
            console.error("Usage: KooRemapper assemble <config.yaml>");
            return 1;
        }
        printBanner(console);
        return runAssemble(argv[2], console);
    }

    // Matswap command
    if (command == "matswap") {
        // YAML mode: single argument ending in .yaml/.yml
        if (argc == 3) {
            std::string arg = argv[2];
            if (arg.size() >= 5 &&
                (arg.substr(arg.size()-5) == ".yaml" || arg.substr(arg.size()-4) == ".yml")) {
                printBanner(console);
                return runMatswapYaml(arg, console);
            }
        }
        // Legacy positional mode
        if (argc < 6) {
            console.error("Usage (YAML):    KooRemapper matswap <config.yaml>");
            console.error("Usage (legacy):  KooRemapper matswap <model.k> <bundle.k> <target_pid> <output.k>");
            console.println("  config.yaml: YAML with model/output/swaps (supports multiple PIDs, swap_all)");
            return 1;
        }
        std::string modelFile  = argv[2];
        std::string bundleFile = argv[3];
        int targetPid = std::stoi(argv[4]);
        std::string outputFile = argv[5];
        printBanner(console);
        return runMatswap(modelFile, bundleFile, targetPid, outputFile, console);
    }

    // Implicit command
    if (command == "implicit") {
        if (argc < 3) {
            console.error("Usage: KooRemapper implicit <config.yaml>");
            return 1;
        }
        printBanner(console);
        return runImplicit(argv[2], console);
    }

    // Modal command
    if (command == "modal") {
        if (argc < 3) {
            console.error("Usage: KooRemapper modal <config.yaml>");
            return 1;
        }
        printBanner(console);
        return runModal(argv[2], console);
    }

    // ALE command
    if (command == "ale") {
        if (argc < 3) {
            console.error("Usage: KooRemapper ale <config.yaml>");
            return 1;
        }
        printBanner(console);
        return runAle(argv[2], console);
    }

    // Info command
    if (command == "info") {
        if (argc < 3) {
            console.error("Usage: KooRemapper info <mesh_file>");
            return 1;
        }
        printBanner(console);
        return runInfo(argv[2], console);
    }

    // Unknown command
    console.error("Unknown command: " + command);
    console.info("Use 'KooRemapper help' for a list of commands.");
    return 1;
}
