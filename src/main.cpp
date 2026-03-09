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
#include <climits>
#include <sstream>
#include <iomanip>
#include <set>
#include <unordered_map>

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
        } else if (op.type == AssemblyOperation::MATDB) {
            ok = assembler.applyMatdb(op.matdb, configDir);
        } else if (op.type == AssemblyOperation::LOAD) {
            ok = assembler.applyLoad(op.load);
        } else if (op.type == AssemblyOperation::CONTACT) {
            ok = assembler.applyContact(op.contact);
        } else if (op.type == AssemblyOperation::BOUNDARY) {
            ok = assembler.applyBoundary(op.boundary);
        } else if (op.type == AssemblyOperation::RBE) {
            ok = assembler.applyRbe(op.rbe);
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
    std::transform(r.begin(), r.end(), r.begin(), [](unsigned char c){ return (char)std::toupper(c); });
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
    // Card 2 must be written first (blank/defaults) so Card 3 is read at correct position.
    // ARCCTL=0 (generalized), ARCMTH=1 (Crisfield), ARCDMP=2 (off), rest=0
    if (arcl) {
        n += snprintf(buf+n, sizeof(buf)-n,
            "$    DNORM    DIVERG     ISTIF   NLPRINT    NLNORM   D3ITCTL     CPCHK\n"
            "         0         0         1         0         0         0         0\n"
            "$   ARCCTL    ARCDIR    ARCLEN    ARCMTH    ARCDMP    ARCPSI    ARCALF    ARCTIM\n"
            "         0         0  0.000000         1         2  0.000000  0.000000  0.000000\n");
    }

    n += snprintf(buf+n, sizeof(buf)-n,
        "*CONTROL_IMPLICIT_AUTO\n"
        "$    IAUTO    ITEOPT    ITEWIN     DTMIN     DTMAX     DTEXP     KFAIL    KCYCLE\n"
        "         1%10d         5%10.3E%10.3E       0.0%10d         0\n",
        p.iteopt, dtmin, dtmax, kfail);

    // Optional: *CONTROL_IMPLICIT_STABILIZATION (level 5+)
    if (stab) {
        n += snprintf(buf+n, sizeof(buf)-n,
            "*CONTROL_IMPLICIT_STABILIZATION\n"
            "$       IAS     SCALE    TSTART      TEND\n"
            "         1%10.6f       0.0 1.000E+28\n",
            stabScale);
    }

    // Always write *CONTROL_IMPLICIT_SOLVER to prevent LS-DYNA from falling back
    // to the internal default (LSOLVR=2 Skyline), which can crash large models.
    n += snprintf(buf+n, sizeof(buf)-n,
        "*CONTROL_IMPLICIT_SOLVER\n"
        "$    LSOLVR    LPRINT     NEGEV     ORDER      DRCM    DRCPRM   AUTOSPC   AUTOTOL\n"
        "%10d         0         2         0         4       0.0         1       0.0\n",
        lsolvr);

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
    std::transform(p.begin(), p.end(), p.begin(), [](unsigned char c){ return (char)std::tolower(c); });

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

// =====================================================================
// Contact manager helpers  (ct_*)
// =====================================================================

struct ContactDef {
    int index = 0;
    std::string type;           // e.g. "AUTOMATIC_SURFACE_TO_SURFACE"
    std::string fullKeyword;    // e.g. "*CONTACT_AUTOMATIC_SURFACE_TO_SURFACE_TITLE"
    bool hasTitle = false;
    std::string title;
    // Card 1
    int ssid=0, msid=0, sstyp=0, mstyp=0, sboxid=0, mboxid=0, spr=0, mpr=0;
    // Card 2
    double fs=0, fd=0, dc=0, vc=0, vdc=0; int penchk=0; double bt=0, dt=1.0e20;
    // Card 3
    double sfsa=1, sfsb=1, sast=0, sbst=0, sfsat=1, sfsbt=1, fsf=1, vsf=1;
    // Optional Card A
    bool hasCardA=false;
    int soft=0; double sofscl=0.1; int lcidab=0; double maxpar=1.025;
    int sbopt=2; int depth=2; int bsort=0; int frcfrq=1;
    // Optional Card B
    bool hasCardB=false;
    double penmax=0; int thkopt=0; int shlthk=0; int snlog=0;
    int isym=0; int i2d3d=0; double sldthk=0; double sldstf=0;
    // Optional Card C
    bool hasCardC=false;
    int igap=1; int ignore_=0; double dprfac=0; double dtstif=0;
    double edgek=0; double flangl=0; int cid_rcf=0;
    // Optional Card D
    bool hasCardD=false;
    int q2tri=0; double dtpchk=0; double sfnbr=0; double fnlscl=0;
    double dnlscl=0; int tcso=0; int tiedid=0; int shledg=0;
    // Optional Card E
    bool hasCardE=false;
    int sharec=0; int cparm8=0; int ipback=0; int srnde=0;
    double fricsf=1; int icor=0; int ftorq=0; int region=0;
    // Optional Card F
    bool hasCardF=false;
    int pstiff=0; int ignroff=0; double fstol=2.0;
    int d2binr=0; int ssftyp=0; int swtpr=0; double tetfac=0;
    // Optional Card G
    bool hasCardG=false;
    double shloff=0;
    // Raw optional cards (backward compat)
    std::vector<std::string> optionalCards;
    int startLine=0, endLine=0;  // [start, end) in rawLines
};

struct SetDef {
    int id = 0;
    std::string type;           // "SEGMENT"/"NODE"/"PART"/"SHELL"/"SOLID"
    bool hasTitle = false;
    std::string title;
    double da1=0, da2=0, da3=0, da4=0;
    std::vector<std::array<int,4>> segments;  // SET_SEGMENT only
    std::vector<int> ids;                     // NODE/PART/SHELL/SOLID
    int startLine=0, endLine=0;
};

// Parse all *CONTACT_* blocks from rawLines
static std::vector<ContactDef> ct_parseContacts(const std::vector<std::string>& lines) {
    std::vector<ContactDef> result;
    int idx = 0;
    for (int i = 0; i < (int)lines.size(); ++i) {
        std::string tr = impl_trim(lines[i]);
        if (tr.empty() || tr[0] != '*') continue;
        std::string up = impl_upper(tr);
        if (up.rfind("*CONTACT_", 0) != 0) continue;
        // Skip *CONTACT comment lines
        if (up.size() >= 2 && up[1] == '$') continue;

        ContactDef c;
        c.startLine = i;
        c.fullKeyword = tr;
        c.index = idx++;

        // Extract type: remove "*CONTACT_" prefix, then strip _TITLE/_ID suffix
        std::string typeStr = up.substr(9);  // after "*CONTACT_"
        c.hasTitle = false;
        // Check _TITLE suffix
        {
            size_t pos = typeStr.rfind("_TITLE");
            if (pos != std::string::npos && pos == typeStr.size() - 6) {
                c.hasTitle = true;
                typeStr = typeStr.substr(0, pos);
            }
        }
        // Check _ID suffix (used in some variants)
        bool hasId = false;
        {
            size_t pos = typeStr.rfind("_ID");
            if (pos != std::string::npos && pos == typeStr.size() - 3) {
                hasId = true;
                typeStr = typeStr.substr(0, pos);
            }
        }
        c.type = typeStr;

        // Collect data lines until next keyword
        int j = i + 1;
        std::vector<std::string> dataLines;
        while (j < (int)lines.size()) {
            std::string jt = impl_trim(lines[j]);
            if (!jt.empty() && jt[0] == '*' && jt[0] != '$') {
                // Check it's really a keyword, not $*comment
                if (jt.size() >= 2 && jt[1] != '$') break;
            }
            dataLines.push_back(lines[j]);
            ++j;
        }
        c.endLine = j;

        // Parse data lines (skip comments/empty)
        int cardNum = 0;
        // If _TITLE or _ID: first non-comment is title/CID line
        bool needTitle = c.hasTitle || hasId;

        for (const auto& dl : dataLines) {
            std::string dtr = impl_trim(dl);
            if (dtr.empty() || dtr[0] == '$') continue;

            if (needTitle) {
                if (hasId) {
                    // CID + title on same line
                    auto toks = impl_tok10(dl);
                    if (!toks.empty()) c.title = dtr;  // store full line as title
                } else {
                    c.title = dtr;
                }
                needTitle = false;
                continue;
            }

            auto toks = impl_tok10(dl);
            if (cardNum == 0) {
                // Card 1: SSID MSID SSTYP MSTYP SBOXID MBOXID SPR MPR
                if (toks.size() >= 1) try { c.ssid   = std::stoi(toks[0]); } catch(...){}
                if (toks.size() >= 2) try { c.msid   = std::stoi(toks[1]); } catch(...){}
                if (toks.size() >= 3) try { c.sstyp  = std::stoi(toks[2]); } catch(...){}
                if (toks.size() >= 4) try { c.mstyp  = std::stoi(toks[3]); } catch(...){}
                if (toks.size() >= 5) try { c.sboxid = std::stoi(toks[4]); } catch(...){}
                if (toks.size() >= 6) try { c.mboxid = std::stoi(toks[5]); } catch(...){}
                if (toks.size() >= 7) try { c.spr    = std::stoi(toks[6]); } catch(...){}
                if (toks.size() >= 8) try { c.mpr    = std::stoi(toks[7]); } catch(...){}
            } else if (cardNum == 1) {
                // Card 2: FS FD DC VC VDC PENCHK BT DT
                if (toks.size() >= 1) try { c.fs     = std::stod(toks[0]); } catch(...){}
                if (toks.size() >= 2) try { c.fd     = std::stod(toks[1]); } catch(...){}
                if (toks.size() >= 3) try { c.dc     = std::stod(toks[2]); } catch(...){}
                if (toks.size() >= 4) try { c.vc     = std::stod(toks[3]); } catch(...){}
                if (toks.size() >= 5) try { c.vdc    = std::stod(toks[4]); } catch(...){}
                if (toks.size() >= 6) try { c.penchk = std::stoi(toks[5]); } catch(...){}
                if (toks.size() >= 7) try { c.bt     = std::stod(toks[6]); } catch(...){}
                if (toks.size() >= 8) try { c.dt     = std::stod(toks[7]); } catch(...){}
            } else if (cardNum == 2) {
                // Card 3: SFSA SFSB SAST SBST SFSAT SFSBT FSF VSF
                if (toks.size() >= 1) try { c.sfsa   = std::stod(toks[0]); } catch(...){}
                if (toks.size() >= 2) try { c.sfsb   = std::stod(toks[1]); } catch(...){}
                if (toks.size() >= 3) try { c.sast   = std::stod(toks[2]); } catch(...){}
                if (toks.size() >= 4) try { c.sbst   = std::stod(toks[3]); } catch(...){}
                if (toks.size() >= 5) try { c.sfsat  = std::stod(toks[4]); } catch(...){}
                if (toks.size() >= 6) try { c.sfsbt  = std::stod(toks[5]); } catch(...){}
                if (toks.size() >= 7) try { c.fsf    = std::stod(toks[6]); } catch(...){}
                if (toks.size() >= 8) try { c.vsf    = std::stod(toks[7]); } catch(...){}
            } else if (cardNum == 3) {
                // Card A: SOFT SOFSCL LCIDAB MAXPAR SBOPT DEPTH BSORT FRCFRQ
                c.hasCardA = true;
                if (toks.size() >= 1) try { c.soft    = std::stoi(toks[0]); } catch(...){}
                if (toks.size() >= 2) try { c.sofscl  = std::stod(toks[1]); } catch(...){}
                if (toks.size() >= 3) try { c.lcidab  = std::stoi(toks[2]); } catch(...){}
                if (toks.size() >= 4) try { c.maxpar  = std::stod(toks[3]); } catch(...){}
                if (toks.size() >= 5) try { c.sbopt   = std::stoi(toks[4]); } catch(...){}
                if (toks.size() >= 6) try { c.depth   = std::stoi(toks[5]); } catch(...){}
                if (toks.size() >= 7) try { c.bsort   = std::stoi(toks[6]); } catch(...){}
                if (toks.size() >= 8) try { c.frcfrq  = std::stoi(toks[7]); } catch(...){}
                c.optionalCards.push_back(dl);
            } else if (cardNum == 4) {
                // Card B: PENMAX THKOPT SHLTHK SNLOG ISYM I2D3D SLDTHK SLDSTF
                c.hasCardB = true;
                if (toks.size() >= 1) try { c.penmax  = std::stod(toks[0]); } catch(...){}
                if (toks.size() >= 2) try { c.thkopt  = std::stoi(toks[1]); } catch(...){}
                if (toks.size() >= 3) try { c.shlthk  = std::stoi(toks[2]); } catch(...){}
                if (toks.size() >= 4) try { c.snlog   = std::stoi(toks[3]); } catch(...){}
                if (toks.size() >= 5) try { c.isym    = std::stoi(toks[4]); } catch(...){}
                if (toks.size() >= 6) try { c.i2d3d   = std::stoi(toks[5]); } catch(...){}
                if (toks.size() >= 7) try { c.sldthk  = std::stod(toks[6]); } catch(...){}
                if (toks.size() >= 8) try { c.sldstf  = std::stod(toks[7]); } catch(...){}
                c.optionalCards.push_back(dl);
            } else if (cardNum == 5) {
                // Card C: IGAP IGNORE DPRFAC DTSTIF EDGEK FLANGL CID_RCF
                c.hasCardC = true;
                if (toks.size() >= 1) try { c.igap    = std::stoi(toks[0]); } catch(...){}
                if (toks.size() >= 2) try { c.ignore_ = std::stoi(toks[1]); } catch(...){}
                if (toks.size() >= 3) try { c.dprfac  = std::stod(toks[2]); } catch(...){}
                if (toks.size() >= 4) try { c.dtstif  = std::stod(toks[3]); } catch(...){}
                if (toks.size() >= 5) try { c.edgek   = std::stod(toks[4]); } catch(...){}
                if (toks.size() >= 6) try { c.flangl  = std::stod(toks[5]); } catch(...){}
                if (toks.size() >= 7) try { c.cid_rcf = std::stoi(toks[6]); } catch(...){}
                c.optionalCards.push_back(dl);
            } else if (cardNum == 6) {
                // Card D: Q2TRI DTPCHK SFNBR FNLSCL DNLSCL TCSO TIEDID SHLEDG
                c.hasCardD = true;
                if (toks.size() >= 1) try { c.q2tri   = std::stoi(toks[0]); } catch(...){}
                if (toks.size() >= 2) try { c.dtpchk  = std::stod(toks[1]); } catch(...){}
                if (toks.size() >= 3) try { c.sfnbr   = std::stod(toks[2]); } catch(...){}
                if (toks.size() >= 4) try { c.fnlscl  = std::stod(toks[3]); } catch(...){}
                if (toks.size() >= 5) try { c.dnlscl  = std::stod(toks[4]); } catch(...){}
                if (toks.size() >= 6) try { c.tcso    = std::stoi(toks[5]); } catch(...){}
                if (toks.size() >= 7) try { c.tiedid  = std::stoi(toks[6]); } catch(...){}
                if (toks.size() >= 8) try { c.shledg  = std::stoi(toks[7]); } catch(...){}
                c.optionalCards.push_back(dl);
            } else if (cardNum == 7) {
                // Card E: SHAREC CPARM8 IPBACK SRNDE FRICSF ICOR FTORQ REGION
                c.hasCardE = true;
                if (toks.size() >= 1) try { c.sharec  = std::stoi(toks[0]); } catch(...){}
                if (toks.size() >= 2) try { c.cparm8  = std::stoi(toks[1]); } catch(...){}
                if (toks.size() >= 3) try { c.ipback  = std::stoi(toks[2]); } catch(...){}
                if (toks.size() >= 4) try { c.srnde   = std::stoi(toks[3]); } catch(...){}
                if (toks.size() >= 5) try { c.fricsf  = std::stod(toks[4]); } catch(...){}
                if (toks.size() >= 6) try { c.icor    = std::stoi(toks[5]); } catch(...){}
                if (toks.size() >= 7) try { c.ftorq   = std::stoi(toks[6]); } catch(...){}
                if (toks.size() >= 8) try { c.region  = std::stoi(toks[7]); } catch(...){}
                c.optionalCards.push_back(dl);
            } else if (cardNum == 8) {
                // Card F: PSTIFF IGNROFF (blank) FSTOL 2DBINR SSFTYP SWTPR TETFAC
                c.hasCardF = true;
                if (toks.size() >= 1) try { c.pstiff  = std::stoi(toks[0]); } catch(...){}
                if (toks.size() >= 2) try { c.ignroff = std::stoi(toks[1]); } catch(...){}
                // field 3 is blank
                if (toks.size() >= 4) try { c.fstol   = std::stod(toks[3]); } catch(...){}
                if (toks.size() >= 5) try { c.d2binr  = std::stoi(toks[4]); } catch(...){}
                if (toks.size() >= 6) try { c.ssftyp  = std::stoi(toks[5]); } catch(...){}
                if (toks.size() >= 7) try { c.swtpr   = std::stoi(toks[6]); } catch(...){}
                if (toks.size() >= 8) try { c.tetfac  = std::stod(toks[7]); } catch(...){}
                c.optionalCards.push_back(dl);
            } else if (cardNum == 9) {
                // Card G: (blank) SHLOFF (rest blank)
                c.hasCardG = true;
                // field 1 is blank
                if (toks.size() >= 2) try { c.shloff  = std::stod(toks[1]); } catch(...){}
                c.optionalCards.push_back(dl);
            } else {
                // Beyond Card G — store raw
                c.optionalCards.push_back(dl);
            }
            cardNum++;
        }
        result.push_back(c);
        i = j - 1;  // advance outer loop
    }
    return result;
}

// Parse all *SET_* blocks from rawLines
static std::vector<SetDef> ct_parseSets(const std::vector<std::string>& lines) {
    std::vector<SetDef> result;
    for (int i = 0; i < (int)lines.size(); ++i) {
        std::string tr = impl_trim(lines[i]);
        if (tr.empty() || tr[0] != '*') continue;
        std::string up = impl_upper(tr);
        if (up.rfind("*SET_", 0) != 0) continue;

        SetDef s;
        s.startLine = i;

        // Determine set type and title
        std::string rest = up.substr(5);  // after "*SET_"
        s.hasTitle = (rest.find("_TITLE") != std::string::npos);
        if (s.hasTitle) {
            size_t pos = rest.find("_TITLE");
            rest = rest.substr(0, pos);
        }
        // Also strip _LIST suffix (e.g., *SET_NODE_LIST)
        {
            size_t pos = rest.find("_LIST");
            if (pos != std::string::npos) rest = rest.substr(0, pos);
        }
        s.type = rest;  // "SEGMENT", "NODE", "PART", "SHELL", "SOLID"

        // Collect data lines
        int j = i + 1;
        while (j < (int)lines.size()) {
            std::string jt = impl_trim(lines[j]);
            if (!jt.empty() && jt[0] == '*' && !(jt.size() >= 2 && jt[1] == '$')) break;
            ++j;
        }
        s.endLine = j;

        // Parse data
        bool titleRead = !s.hasTitle;
        bool headerRead = false;

        for (int k = i + 1; k < j; ++k) {
            std::string dtr = impl_trim(lines[k]);
            if (dtr.empty() || dtr[0] == '$') continue;

            if (!titleRead) {
                s.title = dtr;
                titleRead = true;
                continue;
            }

            auto toks = impl_tok10(lines[k]);

            if (!headerRead) {
                // Header line: SID [DA1 DA2 DA3 DA4] [SOLVER]
                if (!toks.empty()) try { s.id = std::stoi(toks[0]); } catch(...){}
                if (s.type == "SEGMENT") {
                    if (toks.size() >= 2) try { s.da1 = std::stod(toks[1]); } catch(...){}
                    if (toks.size() >= 3) try { s.da2 = std::stod(toks[2]); } catch(...){}
                    if (toks.size() >= 4) try { s.da3 = std::stod(toks[3]); } catch(...){}
                    if (toks.size() >= 5) try { s.da4 = std::stod(toks[4]); } catch(...){}
                }
                headerRead = true;
                continue;
            }

            // Data lines
            if (s.type == "SEGMENT") {
                // N1 N2 N3 N4 [A1 A2 A3 A4]
                std::array<int,4> seg = {0,0,0,0};
                for (int f = 0; f < 4 && f < (int)toks.size(); ++f) {
                    try { seg[f] = std::stoi(toks[f]); } catch(...){}
                }
                if (seg[0] != 0) s.segments.push_back(seg);
            } else {
                // Up to 8 IDs per line
                for (const auto& t : toks) {
                    if (t.empty()) continue;
                    try {
                        int v = std::stoi(t);
                        if (v != 0) s.ids.push_back(v);
                    } catch(...){}
                }
            }
        }
        result.push_back(s);
        i = j - 1;
    }
    return result;
}

// Find max Set ID across all SET_* keywords
static int ct_findMaxSetId(const std::vector<SetDef>& sets) {
    int maxId = 0;
    for (const auto& s : sets) if (s.id > maxId) maxId = s.id;
    return maxId;
}

// Extract outer surface from solid/shell elements of given PID
// Reuses extractSourceSurface() algorithm
static std::vector<std::array<int,4>> ct_extractSurface(
        const KooRemapper::Mesh& mesh, int pid) {
    using namespace KooRemapper;

    // Check for shell elements first
    // (KFileReader stores shells differently — check element types)
    std::vector<std::array<int,4>> faces;

    // Build face count map: sorted key → (count, original winding)
    std::map<std::array<int,4>, std::pair<int, std::array<int,4>>> faceMap;

    bool foundSolid = false;
    for (const auto& [eid, elem] : mesh.getElements()) {
        if (elem.partId != pid) continue;
        foundSolid = true;

        // TET4 detection
        bool isTet = (elem.nodeIds[4] == elem.nodeIds[7] &&
                      elem.nodeIds[4] == elem.nodeIds[6] &&
                      elem.nodeIds[4] == elem.nodeIds[5]);
        int numFaces = isTet ? 4 : 6;

        for (int fi = 0; fi < numFaces; ++fi) {
            auto fn = elem.getFaceNodeIds(fi);
            std::array<int,4> winding = {fn[0], fn[1], fn[2], fn[3]};

            std::array<int,4> key = winding;
            std::sort(key.begin(), key.end());

            auto it = faceMap.find(key);
            if (it == faceMap.end()) {
                faceMap[key] = {1, winding};
            } else {
                it->second.first++;
            }
        }
    }

    if (!foundSolid) {
        // Try shell elements (QUAD4) — TODO: if shells are parsed into elements map
        // For now just return empty; shell handling can be added later
        return faces;
    }

    for (const auto& [key, val] : faceMap) {
        if (val.first == 1) {
            faces.push_back(val.second);
        }
    }
    return faces;
}

// ============================================================
// Module B: Core Detection — Spatial Hash Grid Algorithm
// ============================================================

// ---- B-1. Data structures ----

struct ct_FaceInfo {
    std::array<int, 4> nodeIds;
    Vector3D verts[4];       // cached vertex positions
    Vector3D centroid;
    Vector3D normal;         // unit normal (direction NOT guaranteed outward)
    double area;
    double radius;           // max distance from centroid to any vertex
    int nVerts;              // 3 (tri) or 4 (quad)
    int pid;                 // owning part ID
    int sourceIndex;         // index in original faces vector
};

struct ct_CellKey {
    int ix, iy, iz;
    bool operator==(const ct_CellKey& o) const {
        return ix == o.ix && iy == o.iy && iz == o.iz;
    }
};

struct ct_CellKeyHash {
    size_t operator()(const ct_CellKey& k) const {
        size_t h = size_t(k.ix) * 73856093ULL;
        h ^= size_t(k.iy) * 19349663ULL;
        h ^= size_t(k.iz) * 83492791ULL;
        return h;
    }
};

struct ct_ContactPair {
    int pidA, pidB;
    int faceA, faceB;    // indices into allFaces vector
    double gap;
};

struct ct_PairResult {
    int pidA, pidB;
    std::vector<std::array<int,4>> contactFacesA;
    std::vector<std::array<int,4>> contactFacesB;
    double gapMin, gapMax, gapAvg;
    int pairCount;
};

// ---- B-2. Helpers ----

static ct_CellKey ct_cellKey(const Vector3D& pos, double cellSize) {
    return { (int)std::floor(pos.x / cellSize),
             (int)std::floor(pos.y / cellSize),
             (int)std::floor(pos.z / cellSize) };
}

static std::vector<ct_FaceInfo> ct_buildFaceInfo(
        const std::vector<std::array<int,4>>& faces,
        const KooRemapper::Mesh& mesh,
        int pid) {
    using namespace KooRemapper;
    std::vector<ct_FaceInfo> info;
    info.reserve(faces.size());
    for (int idx = 0; idx < (int)faces.size(); ++idx) {
        ct_FaceInfo fi;
        fi.nodeIds = faces[idx];
        fi.pid = pid;
        fi.sourceIndex = idx;

        // Detect triangle (TET4 degenerate quad)
        bool isTri = (faces[idx][3] == faces[idx][2] ||
                      faces[idx][3] == 0);
        fi.nVerts = isTri ? 3 : 4;

        // Cache vertex positions
        bool valid = true;
        for (int k = 0; k < fi.nVerts; ++k) {
            const auto* nd = mesh.getNode(faces[idx][k]);
            if (!nd) { valid = false; break; }
            fi.verts[k] = nd->position;
        }
        if (!valid) continue;
        if (isTri) fi.verts[3] = fi.verts[2]; // fill 4th slot

        // Centroid
        fi.centroid = Vector3D(0, 0, 0);
        for (int k = 0; k < fi.nVerts; ++k) fi.centroid = fi.centroid + fi.verts[k];
        fi.centroid = fi.centroid * (1.0 / fi.nVerts);

        // Normal
        Vector3D n;
        if (isTri) {
            Vector3D v1 = fi.verts[1] - fi.verts[0];
            Vector3D v2 = fi.verts[2] - fi.verts[0];
            n = v1.cross(v2);
        } else {
            Vector3D d1 = fi.verts[2] - fi.verts[0];
            Vector3D d2 = fi.verts[3] - fi.verts[1];
            n = d1.cross(d2);
        }
        fi.area = n.magnitude() * 0.5;
        if (fi.area < 1e-20) continue; // skip degenerate face
        fi.normal = n.normalized();

        // Radius: max distance from centroid to any vertex
        fi.radius = 0;
        for (int k = 0; k < fi.nVerts; ++k) {
            double r = fi.verts[k].distanceTo(fi.centroid);
            if (r > fi.radius) fi.radius = r;
        }

        info.push_back(fi);
    }
    return info;
}

static double ct_averageFaceSize(const std::vector<ct_FaceInfo>& faces) {
    if (faces.empty()) return 1.0;
    double sum = 0;
    for (const auto& f : faces) sum += std::sqrt(f.area);
    return sum / faces.size();
}

// Insert face into all grid cells its AABB overlaps
static void ct_insertFaceToGrid(
        std::unordered_map<ct_CellKey, std::vector<int>, ct_CellKeyHash>& grid,
        const ct_FaceInfo& fi, int idx, double cellSize) {
    // Compute AABB of face vertices
    double minX = fi.verts[0].x, maxX = fi.verts[0].x;
    double minY = fi.verts[0].y, maxY = fi.verts[0].y;
    double minZ = fi.verts[0].z, maxZ = fi.verts[0].z;
    for (int k = 1; k < fi.nVerts; ++k) {
        if (fi.verts[k].x < minX) minX = fi.verts[k].x;
        if (fi.verts[k].x > maxX) maxX = fi.verts[k].x;
        if (fi.verts[k].y < minY) minY = fi.verts[k].y;
        if (fi.verts[k].y > maxY) maxY = fi.verts[k].y;
        if (fi.verts[k].z < minZ) minZ = fi.verts[k].z;
        if (fi.verts[k].z > maxZ) maxZ = fi.verts[k].z;
    }
    int ixMin = (int)std::floor(minX / cellSize);
    int ixMax = (int)std::floor(maxX / cellSize);
    int iyMin = (int)std::floor(minY / cellSize);
    int iyMax = (int)std::floor(maxY / cellSize);
    int izMin = (int)std::floor(minZ / cellSize);
    int izMax = (int)std::floor(maxZ / cellSize);
    for (int ix = ixMin; ix <= ixMax; ++ix)
        for (int iy = iyMin; iy <= iyMax; ++iy)
            for (int iz = izMin; iz <= izMax; ++iz)
                grid[{ix, iy, iz}].push_back(idx);
}

// ---- B-4. Narrow phase check (4-stage) ----

static bool ct_narrowPhaseCheck(
        const ct_FaceInfo& fA, const ct_FaceInfo& fB,
        double gapTol, double cosThresh, double& gapOut) {

    // Stage 1: centroid distance pre-filter
    double centDist = fA.centroid.distanceTo(fB.centroid);
    if (centDist > fA.radius + fB.radius + gapTol) return false;

    // Stage 2: normal parallelism (direction-agnostic via |dot|)
    double absDot = std::abs(fA.normal.dot(fB.normal));
    if (absDot < cosThresh) return false;

    // Stage 3: vertex-to-plane projection (bilateral)
    // Check A's vertices against B's plane, and vice versa
    double minGap = std::numeric_limits<double>::max();

    // A → B plane
    for (int k = 0; k < fA.nVerts; ++k) {
        Vector3D diff = fA.verts[k] - fB.centroid;
        double gap_k = std::abs(diff.dot(fB.normal));
        // Check projected point is within face B's extent
        Vector3D projPt = fA.verts[k] - fB.normal * diff.dot(fB.normal);
        double projDist = projPt.distanceTo(fB.centroid);
        if (projDist < fB.radius + gapTol) {
            if (gap_k < minGap) minGap = gap_k;
        }
    }
    // B → A plane
    for (int k = 0; k < fB.nVerts; ++k) {
        Vector3D diff = fB.verts[k] - fA.centroid;
        double gap_k = std::abs(diff.dot(fA.normal));
        Vector3D projPt = fB.verts[k] - fA.normal * diff.dot(fA.normal);
        double projDist = projPt.distanceTo(fA.centroid);
        if (projDist < fA.radius + gapTol) {
            if (gap_k < minGap) minGap = gap_k;
        }
    }

    if (minGap > gapTol) return false;
    gapOut = minGap;
    return true;
}

// ---- B-5. Single pair detection ----

static std::vector<ct_ContactPair> ct_detectContacting(
        const std::vector<std::array<int,4>>& facesA,
        const std::vector<std::array<int,4>>& facesB,
        const KooRemapper::Mesh& mesh,
        int pidA, int pidB,
        double gapTolerance = 0.1,
        double normalAngleDeg = 45.0) {

    auto infoA = ct_buildFaceInfo(facesA, mesh, pidA);
    auto infoB = ct_buildFaceInfo(facesB, mesh, pidB);
    if (infoA.empty() || infoB.empty()) return {};

    double avgSize = (ct_averageFaceSize(infoA) + ct_averageFaceSize(infoB)) * 0.5;
    double cellSize = std::max(avgSize, gapTolerance * 2.0);
    cellSize = std::max(cellSize, 1e-10);
    double cosThresh = std::cos(normalAngleDeg * 3.14159265358979323846 / 180.0);

    // Build grid from B (master)
    std::unordered_map<ct_CellKey, std::vector<int>, ct_CellKeyHash> grid;
    for (int j = 0; j < (int)infoB.size(); ++j)
        ct_insertFaceToGrid(grid, infoB[j], j, cellSize);

    // Query with A (slave) — collect candidates with dedup
    std::set<std::pair<int,int>> candidates;
    for (int i = 0; i < (int)infoA.size(); ++i) {
        // AABB cell range for slave face
        double minX = infoA[i].verts[0].x, maxX = minX;
        double minY = infoA[i].verts[0].y, maxY = minY;
        double minZ = infoA[i].verts[0].z, maxZ = minZ;
        for (int k = 1; k < infoA[i].nVerts; ++k) {
            if (infoA[i].verts[k].x < minX) minX = infoA[i].verts[k].x;
            if (infoA[i].verts[k].x > maxX) maxX = infoA[i].verts[k].x;
            if (infoA[i].verts[k].y < minY) minY = infoA[i].verts[k].y;
            if (infoA[i].verts[k].y > maxY) maxY = infoA[i].verts[k].y;
            if (infoA[i].verts[k].z < minZ) minZ = infoA[i].verts[k].z;
            if (infoA[i].verts[k].z > maxZ) maxZ = infoA[i].verts[k].z;
        }
        // Expand by 1 cell margin for tolerance
        int ixMin = (int)std::floor(minX / cellSize) - 1;
        int ixMax = (int)std::floor(maxX / cellSize) + 1;
        int iyMin = (int)std::floor(minY / cellSize) - 1;
        int iyMax = (int)std::floor(maxY / cellSize) + 1;
        int izMin = (int)std::floor(minZ / cellSize) - 1;
        int izMax = (int)std::floor(maxZ / cellSize) + 1;
        for (int ix = ixMin; ix <= ixMax; ++ix)
            for (int iy = iyMin; iy <= iyMax; ++iy)
                for (int iz = izMin; iz <= izMax; ++iz) {
                    auto it = grid.find({ix, iy, iz});
                    if (it == grid.end()) continue;
                    for (int j : it->second)
                        candidates.insert({i, j});
                }
    }

    // Narrow phase
    // faceA/faceB stored as sourceIndex (original index in facesA/facesB),
    // NOT the infoA/infoB index — callers use these to index back into facesA/facesB.
    std::vector<ct_ContactPair> results;
    for (const auto& [i, j] : candidates) {
        double gap;
        if (ct_narrowPhaseCheck(infoA[i], infoB[j], gapTolerance, cosThresh, gap)) {
            results.push_back({pidA, pidB, infoA[i].sourceIndex, infoB[j].sourceIndex, gap});
        }
    }
    return results;
}

// ---- B-6. All-pairs detection (Global Grid) ----

static std::vector<ct_PairResult> ct_detectAllPairs(
        const std::map<int, std::vector<std::array<int,4>>>& surfacesByPid,
        const std::vector<int>& targetPids,
        const std::vector<int>& counterPids,
        const KooRemapper::Mesh& mesh,
        double gapTolerance,
        double normalAngleDeg) {

    // Build face info for all PIDs, tagged with PID
    std::vector<ct_FaceInfo> allFaces;
    // Track per-PID ranges: pid → (startIdx, count)
    std::map<int, std::pair<int,int>> pidRange;

    std::set<int> counterSet(counterPids.begin(), counterPids.end());
    std::set<int> targetSet(targetPids.begin(), targetPids.end());
    // Collect all unique PIDs needed
    std::set<int> allPids;
    allPids.insert(targetPids.begin(), targetPids.end());
    allPids.insert(counterPids.begin(), counterPids.end());

    for (int pid : allPids) {
        auto it = surfacesByPid.find(pid);
        if (it == surfacesByPid.end()) continue;
        int startIdx = (int)allFaces.size();
        auto fi = ct_buildFaceInfo(it->second, mesh, pid);
        allFaces.insert(allFaces.end(), fi.begin(), fi.end());
        pidRange[pid] = {startIdx, (int)fi.size()};
    }
    if (allFaces.empty()) return {};

    double avgSize = ct_averageFaceSize(allFaces);
    double cellSize = std::max(avgSize, gapTolerance * 2.0);
    cellSize = std::max(cellSize, 1e-10);
    double cosThresh = std::cos(normalAngleDeg * 3.14159265358979323846 / 180.0);

    // Insert counter faces into grid
    std::unordered_map<ct_CellKey, std::vector<int>, ct_CellKeyHash> grid;
    for (int pid : counterPids) {
        auto it = pidRange.find(pid);
        if (it == pidRange.end()) continue;
        int start = it->second.first;
        int count = it->second.second;
        for (int i = start; i < start + count; ++i)
            ct_insertFaceToGrid(grid, allFaces[i], i, cellSize);
    }

    // Query with target faces — collect candidates with dedup
    std::set<std::pair<int,int>> candidates;
    for (int pid : targetPids) {
        auto it = pidRange.find(pid);
        if (it == pidRange.end()) continue;
        int start = it->second.first;
        int count = it->second.second;
        for (int i = start; i < start + count; ++i) {
            const auto& fi = allFaces[i];
            double minX = fi.verts[0].x, maxX = minX;
            double minY = fi.verts[0].y, maxY = minY;
            double minZ = fi.verts[0].z, maxZ = minZ;
            for (int k = 1; k < fi.nVerts; ++k) {
                if (fi.verts[k].x < minX) minX = fi.verts[k].x;
                if (fi.verts[k].x > maxX) maxX = fi.verts[k].x;
                if (fi.verts[k].y < minY) minY = fi.verts[k].y;
                if (fi.verts[k].y > maxY) maxY = fi.verts[k].y;
                if (fi.verts[k].z < minZ) minZ = fi.verts[k].z;
                if (fi.verts[k].z > maxZ) maxZ = fi.verts[k].z;
            }
            int ixMin = (int)std::floor(minX / cellSize) - 1;
            int ixMax = (int)std::floor(maxX / cellSize) + 1;
            int iyMin = (int)std::floor(minY / cellSize) - 1;
            int iyMax = (int)std::floor(maxY / cellSize) + 1;
            int izMin = (int)std::floor(minZ / cellSize) - 1;
            int izMax = (int)std::floor(maxZ / cellSize) + 1;
            for (int ix = ixMin; ix <= ixMax; ++ix)
                for (int iy = iyMin; iy <= iyMax; ++iy)
                    for (int iz = izMin; iz <= izMax; ++iz) {
                        auto git = grid.find({ix, iy, iz});
                        if (git == grid.end()) continue;
                        for (int j : git->second) {
                            if (allFaces[j].pid == fi.pid) continue; // skip same PID
                            // Canonical ordering: smaller PID first
                            int a = std::min(i, j), b = std::max(i, j);
                            candidates.insert({a, b});
                        }
                    }
        }
    }

    // Narrow phase + group by PID pair
    std::map<std::pair<int,int>, std::vector<ct_ContactPair>> grouped;
    for (const auto& [a, b] : candidates) {
        double gap;
        if (ct_narrowPhaseCheck(allFaces[a], allFaces[b],
                                gapTolerance, cosThresh, gap)) {
            int pA = std::min(allFaces[a].pid, allFaces[b].pid);
            int pB = std::max(allFaces[a].pid, allFaces[b].pid);
            grouped[{pA, pB}].push_back({pA, pB, a, b, gap});
        }
    }

    // Build results
    std::vector<ct_PairResult> results;
    for (auto& [pidPair, pairs] : grouped) {
        ct_PairResult pr;
        pr.pidA = pidPair.first;
        pr.pidB = pidPair.second;
        pr.pairCount = (int)pairs.size();
        pr.gapMin = std::numeric_limits<double>::max();
        pr.gapMax = 0;
        double gapSum = 0;
        std::set<int> usedA, usedB;
        for (const auto& cp : pairs) {
            if (cp.gap < pr.gapMin) pr.gapMin = cp.gap;
            if (cp.gap > pr.gapMax) pr.gapMax = cp.gap;
            gapSum += cp.gap;
            // Determine which face belongs to which PID
            int idxA = (allFaces[cp.faceA].pid == pr.pidA) ? cp.faceA : cp.faceB;
            int idxB = (allFaces[cp.faceB].pid == pr.pidB) ? cp.faceB : cp.faceA;
            usedA.insert(idxA);
            usedB.insert(idxB);
        }
        pr.gapAvg = pairs.empty() ? 0 : gapSum / pairs.size();
        for (int idx : usedA) pr.contactFacesA.push_back(allFaces[idx].nodeIds);
        for (int idx : usedB) pr.contactFacesB.push_back(allFaces[idx].nodeIds);
        results.push_back(pr);
    }
    return results;
}

// ---- B-7. Merge faces from multiple PIDs (remove internal shared faces) ----

static std::vector<std::array<int,4>> ct_mergeFaces(
        const std::vector<std::vector<std::array<int,4>>>& perPidFaces) {
    // Dedup: sorted key → (count, original winding)
    std::map<std::array<int,4>, std::pair<int, std::array<int,4>>> faceMap;
    for (const auto& faces : perPidFaces) {
        for (const auto& f : faces) {
            std::array<int,4> key = f;
            std::sort(key.begin(), key.end());
            auto it = faceMap.find(key);
            if (it == faceMap.end()) {
                faceMap[key] = {1, f};
            } else {
                it->second.first++;
            }
        }
    }
    std::vector<std::array<int,4>> result;
    for (const auto& [key, val] : faceMap) {
        if (val.first == 1) result.push_back(val.second);
    }
    return result;
}

// ============================================================
// Module A: Part Selection (include/exclude/all filtering)
// ============================================================

static bool ct_matchPartName(const std::string& partName,
                              const std::vector<std::string>& keywords) {
    if (keywords.empty()) return false;
    std::string upper = partName;
    std::transform(upper.begin(), upper.end(), upper.begin(),
                   [](unsigned char c) { return (char)std::toupper(c); });
    for (const auto& kw : keywords) {
        std::string kwUp = kw;
        std::transform(kwUp.begin(), kwUp.end(), kwUp.begin(),
                       [](unsigned char c) { return (char)std::toupper(c); });
        if (upper.find(kwUp) != std::string::npos) return true;
    }
    return false;
}

struct ct_PartSelection {
    std::vector<int> targetPids;
    std::vector<int> counterPids;
};

static ct_PartSelection ct_selectParts(
        const KooRemapper::Mesh& mesh,
        const std::string& scope,
        const std::vector<std::string>& includeKeys,
        const std::vector<std::string>& excludeKeys) {
    using namespace KooRemapper;
    ct_PartSelection sel;

    // Collect all PIDs, filtering by exclude
    std::vector<std::pair<int, std::string>> allParts;
    for (const auto& [pid, part] : mesh.getParts()) {
        if (!excludeKeys.empty() && ct_matchPartName(part.name, excludeKeys))
            continue;
        allParts.push_back({pid, part.name});
    }

    if (scope == "all") {
        // All non-excluded parts are both target and counter
        for (const auto& [pid, name] : allParts) {
            sel.targetPids.push_back(pid);
            sel.counterPids.push_back(pid);
        }
    } else if (!includeKeys.empty()) {
        // Include-matched parts are targets, rest are counters
        for (const auto& [pid, name] : allParts) {
            if (ct_matchPartName(name, includeKeys)) {
                sel.targetPids.push_back(pid);
            }
            // All non-excluded parts are potential counters
            sel.counterPids.push_back(pid);
        }
    }
    // If neither scope nor include → empty (caller uses explicit PID mode)
    return sel;
}

static std::map<int, std::vector<std::array<int,4>>> ct_extractAllSurfaces(
        const KooRemapper::Mesh& mesh,
        const std::vector<int>& pids) {
    std::map<int, std::vector<std::array<int,4>>> result;
    for (int pid : pids) {
        auto faces = ct_extractSurface(mesh, pid);
        if (!faces.empty()) result[pid] = std::move(faces);
    }
    return result;
}

// ============================================================
// Module C: Contact Type Presets
// ============================================================

struct ct_ContactPreset {
    std::string keyword;       // LS-DYNA keyword suffix
    bool needMasterSide;       // false for single_surface
};

static ct_ContactPreset ct_getPreset(const std::string& contactType) {
    std::string t = contactType;
    std::transform(t.begin(), t.end(), t.begin(),
                   [](unsigned char c) { return (char)std::tolower(c); });

    if (t == "auto" || t == "automatic" || t.empty())
        return {"AUTOMATIC_SURFACE_TO_SURFACE", true};
    if (t == "tied")
        return {"TIED_SURFACE_TO_SURFACE", true};
    if (t == "mortar")
        return {"AUTOMATIC_SURFACE_TO_SURFACE_MORTAR", true};
    if (t == "tied_mortar")
        return {"TIED_SURFACE_TO_SURFACE_MORTAR", true};
    if (t == "single")
        return {"AUTOMATIC_SINGLE_SURFACE", false};
    if (t == "eroding")
        return {"ERODING_SURFACE_TO_SURFACE", true};
    if (t == "forming")
        return {"FORMING_SURFACE_TO_SURFACE", true};

    // Custom: use as-is (uppercase)
    std::string upper = contactType;
    std::transform(upper.begin(), upper.end(), upper.begin(),
                   [](unsigned char c) { return (char)std::toupper(c); });
    return {upper, true};
}

// ---- Skip/Subtract helpers ----

// Check if a PID pair has an existing contact
// mode: "tied" → only TIED contacts, "all" → any contact
static bool ct_pairHasExisting(int pidA, int pidB,
        const std::vector<ContactDef>& contacts,
        const std::vector<SetDef>& sets,
        const std::string& mode) {
    for (const auto& ct : contacts) {
        // Check if contact type matches mode
        bool typeMatch = false;
        if (mode == "all") {
            typeMatch = true;
        } else if (mode == "tied") {
            std::string up = ct.type;
            std::transform(up.begin(), up.end(), up.begin(),
                [](unsigned char c) { return (char)std::toupper(c); });
            typeMatch = (up.find("TIED") != std::string::npos);
        } else {
            continue;
        }
        if (!typeMatch) continue;

        // Resolve PIDs from contact sides
        auto resolvePids = [&](int sid, int styp) -> std::vector<int> {
            if (styp == 3) return {sid};
            if (styp == 2) {
                for (const auto& s : sets)
                    if (s.type == "PART" && s.id == sid) return s.ids;
            }
            // SSTYP=0 (segment): can't directly resolve to PID — skip
            return {};
        };

        auto sPids = resolvePids(ct.ssid, ct.sstyp);
        auto mPids = resolvePids(ct.msid, ct.mstyp);
        std::set<int> sSet(sPids.begin(), sPids.end());
        std::set<int> mSet(mPids.begin(), mPids.end());

        // Check both orderings: (A in slave, B in master) or (A in master, B in slave)
        if ((sSet.count(pidA) && mSet.count(pidB)) ||
            (sSet.count(pidB) && mSet.count(pidA))) {
            return true;
        }
    }
    return false;
}

// Get existing tied segments for a PID pair from existing contacts
// Returns {slaveFaces, masterFaces} — empty if not found or not segment-based
static std::pair<std::vector<std::array<int,4>>, std::vector<std::array<int,4>>>
ct_getExistingTiedSegments(int pidA, int pidB,
        const std::vector<ContactDef>& contacts,
        const std::vector<SetDef>& sets,
        const Mesh& mesh, double tol, double nAngle) {
    std::pair<std::vector<std::array<int,4>>, std::vector<std::array<int,4>>> result;

    for (const auto& ct : contacts) {
        // Only TIED contacts
        std::string up = ct.type;
        std::transform(up.begin(), up.end(), up.begin(),
            [](unsigned char c) { return (char)std::toupper(c); });
        if (up.find("TIED") == std::string::npos) continue;

        // Resolve PIDs
        auto resolvePids = [&](int sid, int styp) -> std::vector<int> {
            if (styp == 3) return {sid};
            if (styp == 2) {
                for (const auto& s : sets)
                    if (s.type == "PART" && s.id == sid) return s.ids;
            }
            return {};
        };

        auto sPids = resolvePids(ct.ssid, ct.sstyp);
        auto mPids = resolvePids(ct.msid, ct.mstyp);
        std::set<int> sSet(sPids.begin(), sPids.end());
        std::set<int> mSet(mPids.begin(), mPids.end());

        bool matchForward = (sSet.count(pidA) && mSet.count(pidB));
        bool matchReverse = (sSet.count(pidB) && mSet.count(pidA));
        if (!matchForward && !matchReverse) continue;

        // Found matching tied contact. Get segments.
        if (ct.sstyp == 0 && ct.mstyp == 0) {
            // Already segment-based: read from SetDef
            for (const auto& s : sets) {
                if (s.type == "SEGMENT" && s.id == ct.ssid)
                    result.first = s.segments;
                if (s.type == "SEGMENT" && s.id == ct.msid)
                    result.second = s.segments;
            }
        } else {
            // Part-based: use detect to find tied segments
            auto facesA = ct_extractSurface(mesh, pidA);
            auto facesB = ct_extractSurface(mesh, pidB);
            if (!facesA.empty() && !facesB.empty()) {
                auto pairs = ct_detectContacting(facesA, facesB, mesh, pidA, pidB, tol, nAngle);
                std::set<int> aIdx, bIdx;
                for (const auto& p : pairs) { aIdx.insert(p.faceA); bIdx.insert(p.faceB); }
                for (int i : aIdx) result.first.push_back(facesA[i]);
                for (int i : bIdx) result.second.push_back(facesB[i]);
            }
        }
        if (matchReverse) std::swap(result.first, result.second);
        break;
    }
    return result;
}

// Subtract tiedFaces from allFaces. Returns faces in allFaces that are NOT in tiedFaces.
// Comparison by sorted node IDs.
static std::vector<std::array<int,4>> ct_subtractFaces(
        const std::vector<std::array<int,4>>& allFaces,
        const std::vector<std::array<int,4>>& tiedFaces) {
    // Build set of tied face keys (sorted node IDs)
    std::set<std::array<int,4>> tiedSet;
    for (const auto& f : tiedFaces) {
        auto key = f;
        std::sort(key.begin(), key.end());
        tiedSet.insert(key);
    }
    std::vector<std::array<int,4>> result;
    for (const auto& f : allFaces) {
        auto key = f;
        std::sort(key.begin(), key.end());
        if (!tiedSet.count(key)) result.push_back(f);
    }
    return result;
}

// ---- Generation helpers ----

static std::string ct_generateSetSegment(int setId,
        const std::vector<std::array<int,4>>& faces,
        const std::string& title = "") {
    std::ostringstream ss;
    if (title.empty()) {
        ss << "*SET_SEGMENT\n";
    } else {
        ss << "*SET_SEGMENT_TITLE\n" << title << "\n";
    }
    ss << "$#     sid       da1       da2       da3       da4\n";
    char buf[90]; snprintf(buf, sizeof(buf), "%10d  0.000000  0.000000  0.000000  0.000000", setId);
    ss << buf << "\n";
    ss << "$#      n1        n2        n3        n4\n";
    for (const auto& f : faces) {
        snprintf(buf, sizeof(buf), "%10d%10d%10d%10d", f[0], f[1], f[2], f[3]);
        ss << buf << "\n";
    }
    return ss.str();
}

static std::string ct_generateSetPart(int setId,
        const std::vector<int>& pids,
        const std::string& title = "") {
    std::ostringstream ss;
    if (title.empty()) {
        ss << "*SET_PART_LIST\n";
    } else {
        ss << "*SET_PART_LIST_TITLE\n" << title << "\n";
    }
    ss << "$#     sid\n";
    char buf[90]; snprintf(buf, sizeof(buf), "%10d", setId);
    ss << buf << "\n";
    ss << "$#    pid1      pid2      pid3      pid4      pid5      pid6      pid7      pid8\n";
    for (size_t i = 0; i < pids.size(); ++i) {
        snprintf(buf, sizeof(buf), "%10d", pids[i]);
        ss << buf;
        if ((i + 1) % 8 == 0 || i + 1 == pids.size()) ss << "\n";
    }
    return ss.str();
}

static std::string ct_generateSetNode(int setId,
        const std::vector<int>& nids,
        const std::string& title = "") {
    std::ostringstream ss;
    if (title.empty()) {
        ss << "*SET_NODE_LIST\n";
    } else {
        ss << "*SET_NODE_LIST_TITLE\n" << title << "\n";
    }
    ss << "$#     sid\n";
    char buf[90]; snprintf(buf, sizeof(buf), "%10d", setId);
    ss << buf << "\n";
    ss << "$#    nid1      nid2      nid3      nid4      nid5      nid6      nid7      nid8\n";
    for (size_t i = 0; i < nids.size(); ++i) {
        snprintf(buf, sizeof(buf), "%10d", nids[i]);
        ss << buf;
        if ((i + 1) % 8 == 0 || i + 1 == nids.size()) ss << "\n";
    }
    return ss.str();
}

// Format helpers for Optional Cards A~G
static std::string ct_formatCardA(const ContactDef& d) {
    char buf[90];
    snprintf(buf, sizeof(buf), "%10d%10.2f%10d%10.4f%10d%10d%10d%10d",
             d.soft, d.sofscl, d.lcidab, d.maxpar, d.sbopt, d.depth, d.bsort, d.frcfrq);
    return "$#    soft    sofscl    lcidab    maxpar     sbopt     depth     bsort    frcfrq\n" + std::string(buf);
}
static std::string ct_formatCardB(const ContactDef& d) {
    char buf[90];
    snprintf(buf, sizeof(buf), "%10.4f%10d%10d%10d%10d%10d%10.4f%10.4f",
             d.penmax, d.thkopt, d.shlthk, d.snlog, d.isym, d.i2d3d, d.sldthk, d.sldstf);
    return "$#  penmax    thkopt    shlthk     snlog      isym     i2d3d    sldthk    sldstf\n" + std::string(buf);
}
static std::string ct_formatCardC(const ContactDef& d) {
    char buf[90];
    snprintf(buf, sizeof(buf), "%10d%10d%10.4f%10.4f%10.4f%10.4f%10d%10s",
             d.igap, d.ignore_, d.dprfac, d.dtstif, d.edgek, d.flangl, d.cid_rcf, "");
    return "$#    igap    ignore    dprfac    dtstif     edgek    flangl   cid_rcf\n" + std::string(buf);
}
static std::string ct_formatCardD(const ContactDef& d) {
    char buf[90];
    snprintf(buf, sizeof(buf), "%10d%10.4f%10.4f%10.4f%10.4f%10d%10d%10d",
             d.q2tri, d.dtpchk, d.sfnbr, d.fnlscl, d.dnlscl, d.tcso, d.tiedid, d.shledg);
    return "$#   q2tri    dtpchk     sfnbr    fnlscl    dnlscl      tcso    tiedid    shledg\n" + std::string(buf);
}
static std::string ct_formatCardE(const ContactDef& d) {
    char buf[90];
    snprintf(buf, sizeof(buf), "%10d%10d%10d%10d%10.4f%10d%10d%10d",
             d.sharec, d.cparm8, d.ipback, d.srnde, d.fricsf, d.icor, d.ftorq, d.region);
    return "$#  sharec    cparm8    ipback     srnde    fricsf      icor     ftorq    region\n" + std::string(buf);
}
static std::string ct_formatCardF(const ContactDef& d) {
    char buf[90];
    snprintf(buf, sizeof(buf), "%10d%10d%10s%10.4f%10d%10d%10d%10.4f",
             d.pstiff, d.ignroff, "", d.fstol, d.d2binr, d.ssftyp, d.swtpr, d.tetfac);
    return "$#  pstiff   ignroff              fstol    2dbinr    ssftyp     swtpr    tetfac\n" + std::string(buf);
}
static std::string ct_formatCardG(const ContactDef& d) {
    char buf[90];
    snprintf(buf, sizeof(buf), "%10s%10.4f%10s%10s%10s%10s%10s%10s",
             "", d.shloff, "", "", "", "", "", "");
    return "$#            shloff\n" + std::string(buf);
}

// Append optional cards A~G to stream (ensures card ordering: A before B, etc.)
static void ct_appendOptionalCards(std::ostringstream& ss, const ContactDef& d) {
    // Determine highest card needed
    int maxCard = 0;
    if (d.hasCardG) maxCard = 7;
    else if (d.hasCardF) maxCard = 6;
    else if (d.hasCardE) maxCard = 5;
    else if (d.hasCardD) maxCard = 4;
    else if (d.hasCardC) maxCard = 3;
    else if (d.hasCardB) maxCard = 2;
    else if (d.hasCardA) maxCard = 1;

    // Emit all cards up to maxCard (LS-DYNA sequential dependency)
    if (maxCard >= 1) ss << ct_formatCardA(d) << "\n";
    if (maxCard >= 2) ss << ct_formatCardB(d) << "\n";
    if (maxCard >= 3) ss << ct_formatCardC(d) << "\n";
    if (maxCard >= 4) ss << ct_formatCardD(d) << "\n";
    if (maxCard >= 5) ss << ct_formatCardE(d) << "\n";
    if (maxCard >= 6) ss << ct_formatCardF(d) << "\n";
    if (maxCard >= 7) ss << ct_formatCardG(d) << "\n";
}

static std::string ct_generateContact(const ContactDef& d) {
    std::ostringstream ss;
    std::string kw = "*CONTACT_" + impl_upper(d.type);
    if (!d.title.empty()) kw += "_TITLE";
    ss << kw << "\n";
    if (!d.title.empty()) ss << d.title << "\n";

    char buf[90];
    // Card 1: SSID MSID SSTYP MSTYP SBOXID MBOXID SPR MPR
    snprintf(buf, sizeof(buf), "%10d%10d%10d%10d%10d%10d%10d%10d",
             d.ssid, d.msid, d.sstyp, d.mstyp, d.sboxid, d.mboxid, d.spr, d.mpr);
    ss << "$#    ssid      msid     sstyp     mstyp    sboxid    mboxid       spr       mpr\n";
    ss << buf << "\n";

    // Card 2: FS FD DC VC VDC PENCHK BT DT
    snprintf(buf, sizeof(buf), "%10.2f%10.2f%10.2f%10.2f%10.2f%10d%10.2f%10.3E",
             d.fs, d.fd, d.dc, d.vc, d.vdc, d.penchk, d.bt, d.dt);
    ss << "$#      fs        fd        dc        vc       vdc    penchk        bt        dt\n";
    ss << buf << "\n";

    // Card 3: SFSA SFSB SAST SBST SFSAT SFSBT FSF VSF
    snprintf(buf, sizeof(buf), "%10.2f%10.2f%10.2f%10.2f%10.2f%10.2f%10.2f%10.2f",
             d.sfsa, d.sfsb, d.sast, d.sbst, d.sfsat, d.sfsbt, d.fsf, d.vsf);
    ss << "$#    sfsa      sfsb      sast      sbst     sfsat     sfsbt       fsf       vsf\n";
    ss << buf << "\n";

    // Optional Cards A~G
    ct_appendOptionalCards(ss, d);

    return ss.str();
}

// Modify an existing contact's Card 1 fields in-place
static void ct_modifyContactCard1(std::vector<std::string>& lines,
        const ContactDef& c,
        int newSsid, int newMsid, int newSstyp, int newMstyp) {
    // Find Card 1 data line in [startLine, endLine)
    bool titleSkipped = !c.hasTitle;
    int cardNum = 0;
    for (int i = c.startLine + 1; i < c.endLine; ++i) {
        std::string dtr = impl_trim(lines[i]);
        if (dtr.empty() || dtr[0] == '$') continue;
        if (!titleSkipped) { titleSkipped = true; continue; }
        if (cardNum == 0) {
            // This is Card 1 — modify in place
            std::string line = lines[i];
            if (newSsid  >= 0) line = impl_setField(line, 0, 10, std::to_string(newSsid));
            if (newMsid  >= 0) line = impl_setField(line, 10, 10, std::to_string(newMsid));
            if (newSstyp >= 0) line = impl_setField(line, 20, 10, std::to_string(newSstyp));
            if (newMstyp >= 0) line = impl_setField(line, 30, 10, std::to_string(newMstyp));
            lines[i] = line;
            return;
        }
        cardNum++;
    }
}

// Modify Card 2 FS field
static void ct_modifyContactFs(std::vector<std::string>& lines,
        const ContactDef& c, double newFs) {
    bool titleSkipped = !c.hasTitle;
    int cardNum = 0;
    for (int i = c.startLine + 1; i < c.endLine; ++i) {
        std::string dtr = impl_trim(lines[i]);
        if (dtr.empty() || dtr[0] == '$') continue;
        if (!titleSkipped) { titleSkipped = true; continue; }
        if (cardNum == 1) {
            // Card 2 — modify FS at [0, 10)
            char buf[20]; snprintf(buf, sizeof(buf), "%10.2f", newFs);
            lines[i] = impl_setField(lines[i], 0, 10, std::string(buf));
            return;
        }
        cardNum++;
    }
}

// Replace all optional cards (Card A~G) in existing contact
// Finds Card 3 position, removes everything after it until endLine, inserts new cards
static void ct_modifyOptionalCards(std::vector<std::string>& lines,
        ContactDef& ct, const ContactDef& newVals) {
    // Find position after Card 3
    bool titleSkipped = !ct.hasTitle;
    int cardNum = 0;
    int card3Line = -1;
    for (int i = ct.startLine + 1; i < ct.endLine; ++i) {
        std::string dtr = impl_trim(lines[i]);
        if (dtr.empty() || dtr[0] == '$') continue;
        if (!titleSkipped) { titleSkipped = true; continue; }
        if (cardNum == 2) { card3Line = i; break; }
        cardNum++;
    }
    if (card3Line < 0) return;

    // Find range of optional cards: from card3Line+1 to endLine
    // Skip any comment lines that follow Card 3 data line
    int optStart = card3Line + 1;
    int optEnd = ct.endLine;

    // Remove old optional card lines (including their comment lines)
    if (optEnd > optStart) {
        lines.erase(lines.begin() + optStart, lines.begin() + optEnd);
    }

    // Generate new optional cards
    std::ostringstream ss;
    ct_appendOptionalCards(ss, newVals);
    std::string newCards = ss.str();

    // Insert new lines
    std::vector<std::string> newLines;
    if (!newCards.empty()) {
        std::istringstream is(newCards);
        std::string ln;
        while (std::getline(is, ln)) newLines.push_back(ln);
    }

    if (!newLines.empty()) {
        lines.insert(lines.begin() + optStart, newLines.begin(), newLines.end());
    }

    // Update endLine
    int delta = (int)newLines.size() - (optEnd - optStart);
    ct.endLine += delta;

    // Update parsed fields
    ct.hasCardA = newVals.hasCardA; ct.soft = newVals.soft; ct.sofscl = newVals.sofscl;
    ct.lcidab = newVals.lcidab; ct.maxpar = newVals.maxpar; ct.sbopt = newVals.sbopt;
    ct.depth = newVals.depth; ct.bsort = newVals.bsort; ct.frcfrq = newVals.frcfrq;
    ct.hasCardB = newVals.hasCardB; ct.penmax = newVals.penmax; ct.thkopt = newVals.thkopt;
    ct.shlthk = newVals.shlthk; ct.snlog = newVals.snlog; ct.isym = newVals.isym;
    ct.i2d3d = newVals.i2d3d; ct.sldthk = newVals.sldthk; ct.sldstf = newVals.sldstf;
    ct.hasCardC = newVals.hasCardC; ct.igap = newVals.igap; ct.ignore_ = newVals.ignore_;
    ct.dprfac = newVals.dprfac; ct.dtstif = newVals.dtstif; ct.edgek = newVals.edgek;
    ct.flangl = newVals.flangl; ct.cid_rcf = newVals.cid_rcf;
    ct.hasCardD = newVals.hasCardD; ct.hasCardE = newVals.hasCardE;
    ct.hasCardF = newVals.hasCardF; ct.hasCardG = newVals.hasCardG;
}

// Remove a block [startLine, endLine) from lines
static void ct_removeBlock(std::vector<std::string>& lines, int startLine, int endLine) {
    if (startLine >= 0 && endLine > startLine && endLine <= (int)lines.size()) {
        lines.erase(lines.begin() + startLine, lines.begin() + endLine);
    }
}

// SSTYP description
static std::string ct_stypName(int styp) {
    switch(styp) {
        case 0: return "Segment Set";
        case 1: return "Shell Set";
        case 2: return "Part Set";
        case 3: return "Part ID";
        case 4: return "Node Set";
        case 5: return "All Parts";
        case 6: return "Exempt Parts";
        default: return "Unknown(" + std::to_string(styp) + ")";
    }
}

// Analyze and print contact report
static void ct_analyze(const std::vector<ContactDef>& contacts,
                       const std::vector<SetDef>& sets,
                       const KooRemapper::Mesh& mesh,
                       ConsoleOutput& console) {
    // Contacts
    console.println("\n--- Contacts (" + std::to_string(contacts.size()) + ") ---");
    if (contacts.empty()) {
        console.println("  No contacts found.");
    }
    for (const auto& c : contacts) {
        console.println("  [" + std::to_string(c.index) + "] " + c.fullKeyword);
        if (!c.title.empty()) console.println("      Title: " + c.title);

        // Slave info
        std::string slaveInfo = "      Slave:  ";
        if (c.sstyp == 3) slaveInfo += "PID " + std::to_string(c.ssid);
        else if (c.sstyp == 0) slaveInfo += "SET_SEGMENT " + std::to_string(c.ssid);
        else if (c.sstyp == 2) slaveInfo += "SET_PART " + std::to_string(c.ssid);
        else if (c.sstyp == 4) slaveInfo += "SET_NODE " + std::to_string(c.ssid);
        else if (c.sstyp == 5) slaveInfo += "All Parts";
        else slaveInfo += "ID=" + std::to_string(c.ssid);
        slaveInfo += " (SSTYP=" + std::to_string(c.sstyp) + ", " + ct_stypName(c.sstyp) + ")";

        // Resolve set members
        if (c.sstyp == 2 || c.sstyp == 0) {
            for (const auto& s : sets) {
                if (s.id == c.ssid) {
                    if (s.type == "PART" && !s.ids.empty()) {
                        slaveInfo += " -> [";
                        for (size_t k = 0; k < s.ids.size(); ++k) {
                            if (k) slaveInfo += ", ";
                            slaveInfo += std::to_string(s.ids[k]);
                        }
                        slaveInfo += "]";
                    } else if (s.type == "SEGMENT") {
                        slaveInfo += " -> " + std::to_string(s.segments.size()) + " segments";
                    }
                    break;
                }
            }
        }
        console.println(slaveInfo);

        // Master info
        std::string masterInfo = "      Master: ";
        if (c.mstyp == 3) masterInfo += "PID " + std::to_string(c.msid);
        else if (c.mstyp == 0) masterInfo += "SET_SEGMENT " + std::to_string(c.msid);
        else if (c.mstyp == 2) masterInfo += "SET_PART " + std::to_string(c.msid);
        else if (c.mstyp == 4) masterInfo += "SET_NODE " + std::to_string(c.msid);
        else if (c.msid == 0 && c.mstyp == 0) masterInfo += "(none)";
        else masterInfo += "ID=" + std::to_string(c.msid);
        if (c.msid != 0 || c.mstyp != 0)
            masterInfo += " (MSTYP=" + std::to_string(c.mstyp) + ", " + ct_stypName(c.mstyp) + ")";

        if (c.mstyp == 2 || c.mstyp == 0) {
            for (const auto& s : sets) {
                if (s.id == c.msid) {
                    if (s.type == "PART" && !s.ids.empty()) {
                        masterInfo += " -> [";
                        for (size_t k = 0; k < s.ids.size(); ++k) {
                            if (k) masterInfo += ", ";
                            masterInfo += std::to_string(s.ids[k]);
                        }
                        masterInfo += "]";
                    } else if (s.type == "SEGMENT") {
                        masterInfo += " -> " + std::to_string(s.segments.size()) + " segments";
                    }
                    break;
                }
            }
        }
        console.println(masterInfo);

        // Friction & Card 2 options
        char fbuf[120];
        snprintf(fbuf, sizeof(fbuf), "      FS=%.2f  FD=%.2f", c.fs, c.fd);
        std::string optLine(fbuf);
        if (c.dc != 0) { snprintf(fbuf, sizeof(fbuf), "  DC=%.2f", c.dc); optLine += fbuf; }
        if (c.vc != 0) { snprintf(fbuf, sizeof(fbuf), "  VC=%.2f", c.vc); optLine += fbuf; }
        if (c.penchk != 0) optLine += "  PENCHK=" + std::to_string(c.penchk);
        console.println(optLine);

        // Card A
        if (c.hasCardA) {
            std::string ca = "      Card A: SOFT=" + std::to_string(c.soft);
            if (c.sofscl != 0.1) { snprintf(fbuf, sizeof(fbuf), "  SOFSCL=%.2f", c.sofscl); ca += fbuf; }
            if (c.depth != 2) ca += "  DEPTH=" + std::to_string(c.depth);
            if (c.sbopt != 2) ca += "  SBOPT=" + std::to_string(c.sbopt);
            if (c.bsort != 0) ca += "  BSORT=" + std::to_string(c.bsort);
            if (c.frcfrq != 1) ca += "  FRCFRQ=" + std::to_string(c.frcfrq);
            if (c.lcidab != 0) ca += "  LCIDAB=" + std::to_string(c.lcidab);
            if (c.maxpar != 1.025) { snprintf(fbuf, sizeof(fbuf), "  MAXPAR=%.4f", c.maxpar); ca += fbuf; }
            console.println(ca);
        }
        // Card B
        if (c.hasCardB) {
            std::string cb = "      Card B:";
            if (c.penmax != 0) { snprintf(fbuf, sizeof(fbuf), " PENMAX=%.4f", c.penmax); cb += fbuf; }
            if (c.thkopt != 0) cb += " THKOPT=" + std::to_string(c.thkopt);
            if (c.shlthk != 0) cb += " SHLTHK=" + std::to_string(c.shlthk);
            if (c.snlog != 0) cb += " SNLOG=" + std::to_string(c.snlog);
            if (c.isym != 0) cb += " ISYM=" + std::to_string(c.isym);
            if (c.i2d3d != 0) cb += " I2D3D=" + std::to_string(c.i2d3d);
            if (c.sldthk != 0) { snprintf(fbuf, sizeof(fbuf), " SLDTHK=%.4f", c.sldthk); cb += fbuf; }
            if (c.sldstf != 0) { snprintf(fbuf, sizeof(fbuf), " SLDSTF=%.4f", c.sldstf); cb += fbuf; }
            console.println(cb);
        }
        // Card C
        if (c.hasCardC) {
            std::string cc = "      Card C:";
            if (c.igap != 1) cc += " IGAP=" + std::to_string(c.igap);
            if (c.ignore_ != 0) cc += " IGNORE=" + std::to_string(c.ignore_);
            if (c.dprfac != 0) { snprintf(fbuf, sizeof(fbuf), " DPRFAC=%.4f", c.dprfac); cc += fbuf; }
            if (c.dtstif != 0) { snprintf(fbuf, sizeof(fbuf), " DTSTIF=%.4f", c.dtstif); cc += fbuf; }
            if (c.edgek != 0) { snprintf(fbuf, sizeof(fbuf), " EDGEK=%.4f", c.edgek); cc += fbuf; }
            if (c.flangl != 0) { snprintf(fbuf, sizeof(fbuf), " FLANGL=%.4f", c.flangl); cc += fbuf; }
            if (c.cid_rcf != 0) cc += " CID_RCF=" + std::to_string(c.cid_rcf);
            console.println(cc);
        }
        // Card D
        if (c.hasCardD) {
            std::string cd = "      Card D:";
            if (c.q2tri != 0) cd += " Q2TRI=" + std::to_string(c.q2tri);
            if (c.shledg != 0) cd += " SHLEDG=" + std::to_string(c.shledg);
            if (c.tcso != 0) cd += " TCSO=" + std::to_string(c.tcso);
            if (c.tiedid != 0) cd += " TIEDID=" + std::to_string(c.tiedid);
            console.println(cd);
        }
        // Card E
        if (c.hasCardE) {
            std::string ce = "      Card E:";
            if (c.sharec != 0) ce += " SHAREC=" + std::to_string(c.sharec);
            if (c.cparm8 != 0) ce += " CPARM8=" + std::to_string(c.cparm8);
            if (c.ipback != 0) ce += " IPBACK=" + std::to_string(c.ipback);
            if (c.fricsf != 1.0) { snprintf(fbuf, sizeof(fbuf), " FRICSF=%.4f", c.fricsf); ce += fbuf; }
            if (c.icor != 0) ce += " ICOR=" + std::to_string(c.icor);
            if (c.region != 0) ce += " REGION=" + std::to_string(c.region);
            console.println(ce);
        }
        // Card F
        if (c.hasCardF) {
            std::string cf = "      Card F:";
            if (c.pstiff != 0) cf += " PSTIFF=" + std::to_string(c.pstiff);
            if (c.ignroff != 0) cf += " IGNROFF=" + std::to_string(c.ignroff);
            if (c.fstol != 2.0) { snprintf(fbuf, sizeof(fbuf), " FSTOL=%.4f", c.fstol); cf += fbuf; }
            console.println(cf);
        }
        // Card G
        if (c.hasCardG) {
            snprintf(fbuf, sizeof(fbuf), "      Card G: SHLOFF=%.4f", c.shloff);
            console.println(std::string(fbuf));
        }
        console.println("");
    }

    // Sets
    console.println("--- Sets (" + std::to_string(sets.size()) + ") ---");
    if (sets.empty()) {
        console.println("  No sets found.");
    }
    for (const auto& s : sets) {
        std::string info = "  SET_" + s.type + " " + std::to_string(s.id) + ": ";
        if (s.type == "SEGMENT") {
            info += std::to_string(s.segments.size()) + " segments";
        } else {
            info += std::to_string(s.ids.size()) + " entries";
            if (s.ids.size() <= 10) {
                info += " [";
                for (size_t k = 0; k < s.ids.size(); ++k) {
                    if (k) info += ", ";
                    info += std::to_string(s.ids[k]);
                }
                info += "]";
            }
        }
        if (!s.title.empty()) info += " \"" + s.title + "\"";
        console.println(info);
    }

    // Coverage analysis
    console.println("\n--- Coverage ---");
    std::map<int, std::vector<std::string>> pidContacts;
    for (const auto& [pid, part] : mesh.getParts()) {
        pidContacts[pid];  // ensure entry exists
    }
    for (const auto& c : contacts) {
        auto addCoverage = [&](int id, int styp, const std::string& role) {
            if (styp == 3) {
                // Direct PID
                pidContacts[id].push_back(role + "[" + std::to_string(c.index) + "]");
            } else if (styp == 2) {
                // Part set — resolve
                for (const auto& s : sets) {
                    if (s.id == id && (s.type == "PART")) {
                        for (int pid : s.ids) {
                            pidContacts[pid].push_back(role + "[" + std::to_string(c.index) + "]");
                        }
                    }
                }
            } else if (styp == 5) {
                // All parts
                for (auto& [pid, v] : pidContacts) {
                    v.push_back(role + "[" + std::to_string(c.index) + "]");
                }
            }
        };
        addCoverage(c.ssid, c.sstyp, "slave");
        addCoverage(c.msid, c.mstyp, "master");
    };

    for (const auto& [pid, roles] : pidContacts) {
        std::string line = "  PID " + std::to_string(pid) + ": ";
        if (roles.empty()) {
            line += "no contact (!)";
        } else {
            for (size_t k = 0; k < roles.size(); ++k) {
                if (k) line += ", ";
                line += roles[k];
            }
        }
        console.println(line);
    }
    console.println("");
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

// =====================================================================
// optimize helpers: material-specific global card optimizations
// =====================================================================

struct OptimizeConfig {
    std::string mode;               // "rubber" (extendable later)
    double tssfac = 0.67;          // TSSFAC default for rubber
    std::vector<int> pids;         // target PIDs for CONTACT modification
    std::string analysisType;      // "explicit" / "implicit" / "" (auto-detect)
};

// Check if a contact references any of the target PIDs
static bool opt_contactInvolvesPid(const ContactDef& ct,
                                    const std::set<int>& targetPids,
                                    const std::vector<SetDef>& sets) {
    auto checkSide = [&](int sid, int styp) -> bool {
        if (styp == 3) {
            return targetPids.count(sid) > 0;
        } else if (styp == 2) {
            for (const auto& s : sets) {
                if (s.type == "PART" && s.id == sid) {
                    for (int pid : s.ids) {
                        if (targetPids.count(pid)) return true;
                    }
                }
            }
        }
        return false;
    };
    return checkSide(ct.ssid, ct.sstyp) || checkSide(ct.msid, ct.mstyp);
}

// Find and modify a CONTROL keyword's first data line field
// Returns: 0=not found, 1=already correct, 2=modified
static int opt_patchControlField(std::vector<std::string>& lines,
                                  const std::string& keyword,
                                  int fieldPos, int fieldWidth,
                                  const std::string& newVal) {
    bool inBlock = false, hasTitle = false, titleDone = false;
    for (auto& ln : lines) {
        std::string tr = impl_trim(ln);
        if (tr.empty()) continue;
        if (tr[0] == '*') {
            std::string up = impl_upper(tr);
            inBlock = (up.rfind(keyword, 0) == 0);
            hasTitle = (up.find("_TITLE") != std::string::npos);
            titleDone = false;
            continue;
        }
        if (!inBlock || tr[0] == '$') continue;
        if (hasTitle && !titleDone) { titleDone = true; continue; }
        std::string curVal;
        if ((int)ln.size() > fieldPos) {
            int end = std::min((int)ln.size(), fieldPos + fieldWidth);
            curVal = impl_trim(ln.substr(fieldPos, end - fieldPos));
        }
        if (curVal == impl_trim(newVal)) return 1;
        ln = impl_setField(ln, fieldPos, fieldWidth, newVal);
        return 2;
    }
    return 0;
}

static bool opt_hasKeyword(const std::vector<std::string>& lines, const std::string& keyword) {
    for (const auto& ln : lines) {
        std::string tr = impl_trim(ln);
        if (!tr.empty() && tr[0] == '*') {
            if (impl_upper(tr).rfind(keyword, 0) == 0) return true;
        }
    }
    return false;
}

static std::string opt_readControlField(const std::vector<std::string>& lines,
                                         const std::string& keyword,
                                         int fieldPos, int fieldWidth) {
    bool inBlock = false, hasTitle = false, titleDone = false;
    for (const auto& ln : lines) {
        std::string tr = impl_trim(ln);
        if (tr.empty()) continue;
        if (tr[0] == '*') {
            std::string up = impl_upper(tr);
            inBlock = (up.rfind(keyword, 0) == 0);
            hasTitle = (up.find("_TITLE") != std::string::npos);
            titleDone = false;
            continue;
        }
        if (!inBlock || tr[0] == '$') continue;
        if (hasTitle && !titleDone) { titleDone = true; continue; }
        if ((int)ln.size() > fieldPos) {
            int end = std::min((int)ln.size(), fieldPos + fieldWidth);
            return impl_trim(ln.substr(fieldPos, end - fieldPos));
        }
        return "";
    }
    return "";
}

// Detect if model uses implicit solver
static bool opt_isImplicit(const std::vector<std::string>& lines) {
    for (const auto& ln : lines) {
        std::string tr = impl_trim(ln);
        if (!tr.empty() && tr[0] == '*') {
            if (impl_upper(tr).rfind("*CONTROL_IMPLICIT", 0) == 0) return true;
        }
    }
    return false;
}

// Apply rubber optimization to lines, returns info messages
static std::vector<std::string> opt_applyRubber(std::vector<std::string>& lines,
                                                  const OptimizeConfig& cfg) {
    std::vector<std::string> msgs;
    std::set<int> targetPids(cfg.pids.begin(), cfg.pids.end());

    // Determine analysis type: explicit / implicit
    bool isImplicit;
    if (cfg.analysisType == "implicit") {
        isImplicit = true;
        msgs.push_back("[optimize] Analysis type: implicit (specified)");
    } else if (cfg.analysisType == "explicit") {
        isImplicit = false;
        msgs.push_back("[optimize] Analysis type: explicit (specified)");
    } else {
        isImplicit = opt_isImplicit(lines);
        msgs.push_back(std::string("[optimize] Analysis type: ") +
                       (isImplicit ? "implicit" : "explicit") + " (auto-detected)");
    }

    // 1. CONTROL_ACCURACY: INN=4 (field 1, pos 10)
    {
        int r = opt_patchControlField(lines, "*CONTROL_ACCURACY", 10, 10, "4");
        if (r == 0) {
            impl_insertBeforeEnd(lines,
                "*CONTROL_ACCURACY\n"
                "$      OSU       INN    PIDOSU\n"
                "         0         4");
            msgs.push_back("[optimize] *CONTROL_ACCURACY: INN=4 (inserted)");
        } else if (r == 2) {
            msgs.push_back("[optimize] *CONTROL_ACCURACY: INN=4 (modified)");
        } else {
            msgs.push_back("[optimize] *CONTROL_ACCURACY: INN=4 (OK)");
        }
    }

    // 2. CONTROL_ENERGY: HGEN=2, RWEN=2, SLNTEN=2, RYLEN=2
    {
        if (!opt_hasKeyword(lines, "*CONTROL_ENERGY")) {
            impl_insertBeforeEnd(lines,
                "*CONTROL_ENERGY\n"
                "$     HGEN      RWEN    SLNTEN     RYLEN\n"
                "         2         2         2         2");
            msgs.push_back("[optimize] *CONTROL_ENERGY: HGEN=2,RWEN=2,SLNTEN=2,RYLEN=2 (inserted)");
        } else {
            bool anyMod = false;
            if (opt_patchControlField(lines, "*CONTROL_ENERGY", 0, 10, "2")==2) anyMod=true;
            if (opt_patchControlField(lines, "*CONTROL_ENERGY", 10, 10, "2")==2) anyMod=true;
            if (opt_patchControlField(lines, "*CONTROL_ENERGY", 20, 10, "2")==2) anyMod=true;
            if (opt_patchControlField(lines, "*CONTROL_ENERGY", 30, 10, "2")==2) anyMod=true;
            msgs.push_back(std::string("[optimize] *CONTROL_ENERGY: HGEN=2,RWEN=2,SLNTEN=2,RYLEN=2 (") +
                           (anyMod ? "modified)" : "OK)"));
        }
    }

    // 3. CONTROL_TIMESTEP: TSSFAC — explicit only
    if (!isImplicit) {
        char buf[16];
        snprintf(buf, sizeof(buf), "%10.6f", cfg.tssfac);
        std::string tssfacStr(buf);

        if (!opt_hasKeyword(lines, "*CONTROL_TIMESTEP")) {
            impl_insertBeforeEnd(lines,
                "*CONTROL_TIMESTEP\n"
                "$   DTINIT    TSSFAC      ISDO    TSLIMT     DT2MS      LCTM     ERODE     MS1ST\n"
                "       0.0" + tssfacStr + "         0       0.0       0.0         0         0         0");
            msgs.push_back("[optimize] *CONTROL_TIMESTEP: TSSFAC=" + impl_trim(tssfacStr) + " (inserted)");
        } else {
            std::string oldVal = opt_readControlField(lines, "*CONTROL_TIMESTEP", 10, 10);
            int r = opt_patchControlField(lines, "*CONTROL_TIMESTEP", 10, 10, impl_trim(tssfacStr));
            if (r == 2)
                msgs.push_back("[optimize] *CONTROL_TIMESTEP: TSSFAC=" + impl_trim(tssfacStr) + " (was " + oldVal + ")");
            else
                msgs.push_back("[optimize] *CONTROL_TIMESTEP: TSSFAC=" + impl_trim(tssfacStr) + " (OK)");
        }

        // DT2MS warning — explicit only
        std::string dt2ms = opt_readControlField(lines, "*CONTROL_TIMESTEP", 40, 10);
        if (!dt2ms.empty()) {
            double dt2msVal = 0;
            try { dt2msVal = std::stod(dt2ms); } catch(...) {}
            if (dt2msVal != 0.0)
                msgs.push_back("[optimize] WARNING: DT2MS=" + dt2ms + " (dynamic impact requires DT2MS=0)");
        }
    } else {
        msgs.push_back("[optimize] *CONTROL_TIMESTEP: TSSFAC skipped (implicit — use CONTROL_IMPLICIT_AUTO dt0/dtmax)");
    }

    // 4. CONTROL_BULK_VISCOSITY: warning only, explicit only
    if (!isImplicit) {
        if (opt_hasKeyword(lines, "*CONTROL_BULK_VISCOSITY")) {
            std::string q1s = opt_readControlField(lines, "*CONTROL_BULK_VISCOSITY", 0, 10);
            std::string q2s = opt_readControlField(lines, "*CONTROL_BULK_VISCOSITY", 10, 10);
            double q1v = 1.5, q2v = 0.06;
            try { q1v = std::stod(q1s); } catch(...) {}
            try { q2v = std::stod(q2s); } catch(...) {}
            if (std::abs(q1v - 1.5) < 0.01 && std::abs(q2v - 0.06) < 0.001) {
                msgs.push_back("[optimize] *CONTROL_BULK_VISCOSITY: Q1=1.5, Q2=0.06 (OK)");
            } else {
                char wbuf[128];
                snprintf(wbuf, sizeof(wbuf),
                    "[optimize] WARNING: *CONTROL_BULK_VISCOSITY Q1=%.2f Q2=%.3f (recommended: Q1=1.5, Q2=0.06)", q1v, q2v);
                msgs.push_back(std::string(wbuf));
            }
        } else {
            msgs.push_back("[optimize] *CONTROL_BULK_VISCOSITY: not present (LS-DYNA defaults apply)");
        }
    } else {
        msgs.push_back("[optimize] *CONTROL_BULK_VISCOSITY: skipped (implicit — not applicable)");
    }

    // 5. CONTACT: SOFT=0, SBOPT=2.0 for target PIDs
    if (!targetPids.empty()) {
        auto contacts = ct_parseContacts(lines);
        auto sets = ct_parseSets(lines);
        int modCount = 0;

        for (const auto& ct : contacts) {
            if (!opt_contactInvolvesPid(ct, targetPids, sets)) continue;

            bool titleSkipped = !ct.hasTitle;
            int cardNum = 0;
            for (int i = ct.startLine + 1; i < ct.endLine; ++i) {
                std::string dtr = impl_trim(lines[i]);
                if (dtr.empty() || dtr[0] == '$') continue;
                if (!titleSkipped) { titleSkipped = true; continue; }
                if (cardNum == 3) {
                    // Card A: SOFT(0,10) SOFSCL(10,10) LCIDAB(20,10) MAXPAR(30,10) SBOPT(40,10)
                    bool modified = false;
                    char buf[16];

                    auto softToks = impl_tok10(lines[i]);
                    int curSoft = 0;
                    if (!softToks.empty()) try { curSoft = std::stoi(softToks[0]); } catch(...) {}
                    if (curSoft != 0) {
                        lines[i] = impl_setField(lines[i], 0, 10, "0");
                        modified = true;
                        snprintf(buf, sizeof(buf), "SOFT=%d->0", curSoft);
                        msgs.push_back("[optimize] CONTACT #" + std::to_string(ct.index) + ": " + buf);
                    }

                    int curSbopt = 2;
                    if (softToks.size() >= 5) try { curSbopt = std::stoi(softToks[4]); } catch(...) {}
                    if (curSbopt == 1) {
                        lines[i] = impl_setField(lines[i], 40, 10, "2");
                        modified = true;
                        msgs.push_back("[optimize] CONTACT #" + std::to_string(ct.index) + ": SBOPT=1->2");
                    }

                    if (modified) modCount++;
                    break;
                }
                cardNum++;
            }

            if (!ct.hasCardA && ct.soft != 0) {
                msgs.push_back("[optimize] CONTACT #" + std::to_string(ct.index) +
                               ": no Card A found, cannot set SOFT/SBOPT");
            }
        }

        // Warn about segment-based contacts
        for (const auto& ct : contacts) {
            if (ct.sstyp == 0 && ct.mstyp == 0) continue;
            bool hasPid = false;
            if (ct.sstyp == 3 && targetPids.count(ct.ssid)) hasPid = true;
            if (ct.mstyp == 3 && targetPids.count(ct.msid)) hasPid = true;
            if (!hasPid) continue;
            if (ct.sstyp == 0 || ct.mstyp == 0)
                msgs.push_back("[optimize] WARNING: CONTACT #" + std::to_string(ct.index) +
                               " has SSTYP=0 side - SOFT/SBOPT not verified");
        }

        if (modCount > 0)
            msgs.push_back("[optimize] " + std::to_string(modCount) + " contact(s) modified");
    }

    return msgs;
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
    std::string optimizeMode;           // "rubber" or empty
    double optimizeTssfac = 0.67;      // default TSSFAC for optimize
    std::string optimizeAnalysisType;  // "explicit"/"implicit"/""
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
            else if (key=="optimize")       optimizeMode = val;
            else if (key=="tssfac")         { try { optimizeTssfac = std::stod(val); } catch(...) {} }
            else if (key=="analysis_type")  optimizeAnalysisType = val;
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

    // Apply optimize if specified
    if (!optimizeMode.empty()) {
        console.println("");
        console.println("[optimize] Applying '" + optimizeMode + "' optimization...");

        // Collect all swapped PIDs for contact modification scope
        OptimizeConfig optCfg;
        optCfg.mode = optimizeMode;
        optCfg.tssfac = optimizeTssfac;
        optCfg.analysisType = optimizeAnalysisType;
        for (const auto& sw : swaps) {
            for (int pid : sw.pids) optCfg.pids.push_back(pid);
        }

        // Re-read the output file, apply optimize, re-write
        std::string outputPath = outputPrefix + ".k";
        std::vector<std::string> lines;
        {
            std::ifstream fin(outputPath);
            if (!fin.is_open()) { console.error("Cannot re-read: " + outputPath); return 1; }
            std::string l;
            while (std::getline(fin, l)) {
                if (!l.empty() && l.back()=='\r') l.pop_back();
                lines.push_back(l);
            }
        }

        std::vector<std::string> msgs;
        if (optCfg.mode == "rubber") {
            msgs = opt_applyRubber(lines, optCfg);
        } else {
            console.error("Unknown optimize mode: " + optCfg.mode);
            return 1;
        }
        for (const auto& m : msgs) console.println(m);

        {
            std::ofstream fout(outputPath);
            if (!fout.is_open()) { console.error("Cannot write: " + outputPath); return 1; }
            for (const auto& l : lines) fout << l << "\n";
        }
        console.println("[optimize] Done -> " + outputPath);
    }

    return 0;
}

// ============================================================
//  matdb command — material database-driven swap
// ============================================================
int runMatdb(const std::string& yamlFile, ConsoleOutput& console) {
    using namespace KooRemapper;

    std::ifstream f(yamlFile);
    if (!f.is_open()) { console.error("Cannot open: " + yamlFile); return 1; }

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
    auto stripQuotes = [](const std::string& s) -> std::string {
        if (s.size() >= 2 && ((s.front()=='"' && s.back()=='"') || (s.front()=='\'' && s.back()=='\'')))
            return s.substr(1, s.size()-2);
        return s;
    };

    std::string modelFile, outputFile;
    MatdbOperation op;
    bool inMaterialsList = false;
    int materialsIndent = 0;
    bool inMaterialItem = false;
    int materialItemIndent = 0;

    std::string ln;
    while (std::getline(f, ln)) {
        if (!ln.empty() && ln.back()=='\r') ln.pop_back();
        int indent = countIndent(ln);
        std::string tr = trim(ln);
        if (tr.empty() || tr[0]=='#') continue;

        // Check if we're leaving materials list
        if (inMaterialsList && indent <= materialsIndent && tr.substr(0,2) != "- ") {
            inMaterialsList = false;
            inMaterialItem = false;
        }

        size_t cp = tr.find(':');
        if (cp == std::string::npos) continue;
        std::string key = trim(tr.substr(0, cp));
        std::string val = stripQuotes(trim(tr.substr(cp+1)));

        if (!inMaterialsList) {
            if      (key == "model")    modelFile = val;
            else if (key == "output")   outputFile = val;
            else if (key == "database") op.databasePath = val;
            else if (key == "mat_type") op.globalMatType = val;
            else if (key == "thermal")  op.globalThermal = (val == "true" || val == "yes" || val == "1");
            else if (key == "materials") {
                inMaterialsList = true;
                materialsIndent = indent;
            }
        }

        // Parse materials list items
        if (inMaterialsList) {
            if (tr.substr(0, 2) == "- " && indent > materialsIndent) {
                // New list item
                op.rules.push_back({});
                inMaterialItem = true;
                materialItemIndent = indent;
                // Parse inline key-value after "- "
                std::string rest = trim(tr.substr(2));
                size_t rcp = rest.find(':');
                if (rcp != std::string::npos) {
                    std::string rk = trim(rest.substr(0, rcp));
                    std::string rv = stripQuotes(trim(rest.substr(rcp+1)));
                    auto& rule = op.rules.back();
                    if      (rk == "match")    rule.match = rv;
                    else if (rk == "mid")      { try { rule.mid = std::stoi(rv); } catch(...) {} }
                    else if (rk == "mat_type") rule.matType = rv;
                    else if (rk == "thermal")  rule.thermalOverride = (rv == "true" || rv == "yes" || rv == "1") ? 1 : 0;
                }
            } else if (inMaterialItem && indent > materialItemIndent) {
                // Sub-key of current material item
                auto& rule = op.rules.back();
                if      (key == "match")    rule.match = val;
                else if (key == "mid")      { try { rule.mid = std::stoi(val); } catch(...) {} }
                else if (key == "mat_type") rule.matType = val;
                else if (key == "thermal")  rule.thermalOverride = (val == "true" || val == "yes" || val == "1") ? 1 : 0;
            }
        }
    }
    f.close();

    if (modelFile.empty()) { console.error("[matdb] 'model' not specified"); return 1; }
    if (outputFile.empty()) { console.error("[matdb] 'output' not specified"); return 1; }

    // Resolve model path relative to config dir
    if (!configDir.empty() && modelFile.find('/') == std::string::npos && modelFile.find('\\') == std::string::npos)
        modelFile = configDir + "/" + modelFile;

    // Output prefix
    std::string outputPrefix = outputFile;
    if (outputPrefix.size() > 2 && outputPrefix.substr(outputPrefix.size()-2) == ".k")
        outputPrefix = outputPrefix.substr(0, outputPrefix.size()-2);
    if (!configDir.empty() && outputPrefix.find('/') == std::string::npos && outputPrefix.find('\\') == std::string::npos)
        outputPrefix = configDir + "/" + outputPrefix;

    console.println("[matdb] Model: " + modelFile);
    console.println("[matdb] Output: " + outputPrefix + ".k");
    console.println("[matdb] Mat type: " + op.globalMatType);
    console.println("[matdb] Thermal: " + std::string(op.globalThermal ? "ON" : "OFF"));
    if (!op.rules.empty())
        console.println("[matdb] Material rules: " + std::to_string(op.rules.size()));

    ModelAssembler assembler;
    if (!assembler.loadRawOnly(modelFile)) {
        console.error(assembler.getErrorMessage());
        return 1;
    }

    if (!assembler.applyMatdb(op, configDir)) {
        console.error(assembler.getErrorMessage());
        return 1;
    }

    for (const auto& msg : assembler.infoMessages)
        console.println(msg);

    if (!assembler.writeOutput(outputPrefix)) {
        console.error(assembler.getErrorMessage());
        return 1;
    }

    console.println("[matdb] Done -> " + outputPrefix + ".k");
    return 0;
}

// ============================================================
//  load command — segment-based load generation
// ============================================================
int runLoad(const std::string& yamlFile, ConsoleOutput& console) {
    using namespace KooRemapper;

    std::ifstream f(yamlFile);
    if (!f.is_open()) { console.error("Cannot open: " + yamlFile); return 1; }

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
    auto stripQuotes = [](const std::string& s) -> std::string {
        if (s.size() >= 2 && ((s.front()=='"' && s.back()=='"') || (s.front()=='\'' && s.back()=='\'')))
            return s.substr(1, s.size()-2);
        return s;
    };

    std::string modelFile, outputFile;
    LoadOperation loadOp;
    bool inLoadsList = false;
    int loadsListIndent = 0;
    bool inLoadItem = false;
    int loadItemIndent = 0;
    bool inCurveList = false;
    int curveListIndent = 0;

    std::string ln;
    while (std::getline(f, ln)) {
        if (!ln.empty() && ln.back()=='\r') ln.pop_back();
        int indent = countIndent(ln);
        std::string tr = trim(ln);
        if (tr.empty() || tr[0]=='#') continue;

        // Exit loads list
        if (inLoadsList && indent <= loadsListIndent && tr.substr(0,2) != "- ") {
            inLoadsList = false;
            inLoadItem = false;
            inCurveList = false;
        }

        // Exit curve list
        if (inCurveList && indent <= curveListIndent && tr.substr(0,2) != "- ") {
            inCurveList = false;
        }

        // Curve points: - [0.0, 1.0]
        if (inCurveList && tr.substr(0,2) == "- ") {
            std::string rest = trim(tr.substr(2));
            if (rest.front() == '[' && rest.back() == ']') {
                rest = rest.substr(1, rest.size()-2);
                size_t comma = rest.find(',');
                if (comma != std::string::npos) {
                    LoadCurvePoint pt;
                    try {
                        pt.time = std::stod(trim(rest.substr(0, comma)));
                        pt.value = std::stod(trim(rest.substr(comma+1)));
                        loadOp.loads.back().curve.push_back(pt);
                    } catch(...) {}
                }
            }
            continue;
        }

        size_t cp = tr.find(':');
        if (cp == std::string::npos) continue;
        std::string key = trim(tr.substr(0, cp));
        std::string val = stripQuotes(trim(tr.substr(cp+1)));

        if (!inLoadsList) {
            if      (key == "model")  modelFile = val;
            else if (key == "output") outputFile = val;
            else if (key == "loads") {
                inLoadsList = true;
                loadsListIndent = indent;
            }
            continue;
        }

        // Load list item start
        if (inLoadsList && tr.substr(0,2) == "- " && indent > loadsListIndent) {
            loadOp.loads.push_back({});
            inLoadItem = true;
            inCurveList = false;
            loadItemIndent = indent;
            std::string rest = trim(tr.substr(2));
            size_t rcp = rest.find(':');
            if (rcp != std::string::npos) {
                std::string rk = trim(rest.substr(0, rcp));
                std::string rv = stripQuotes(trim(rest.substr(rcp+1)));
                auto& lcase = loadOp.loads.back();
                if      (rk == "part") {
                    try { lcase.pid = std::stoi(rv); } catch(...) { lcase.partName = rv; }
                }
                else if (rk == "mode")       lcase.mode = rv;
                else if (rk == "value")      { try { lcase.value = std::stod(rv); } catch(...) {} }
                else if (rk == "select")     lcase.select = rv;
                else if (rk == "angle")      { try { lcase.angle = std::stod(rv); } catch(...) {} }
                else if (rk == "set_id")     { try { lcase.setId = std::stoi(rv); } catch(...) {} }
                else if (rk == "contact_id") { try { lcase.contactId = std::stoi(rv); } catch(...) {} }
            }
            continue;
        }

        // Sub-keys of current load item
        if (inLoadItem && indent > loadItemIndent) {
            auto& lcase = loadOp.loads.back();

            if (key == "curve") {
                inCurveList = true;
                curveListIndent = indent;
                continue;
            }

            if (key == "direction") {
                if (val.front() == '[' && val.back() == ']') {
                    std::string inner = val.substr(1, val.size()-2);
                    std::istringstream iss(inner);
                    std::string tok;
                    int di = 0;
                    while (std::getline(iss, tok, ',') && di < 3) {
                        try { lcase.direction[di] = std::stod(trim(tok)); } catch(...) {}
                        di++;
                    }
                }
                continue;
            }

            if      (key == "part") {
                try { lcase.pid = std::stoi(val); } catch(...) { lcase.partName = val; }
            }
            else if (key == "mode")       lcase.mode = val;
            else if (key == "value")      { try { lcase.value = std::stod(val); } catch(...) {} }
            else if (key == "select")     lcase.select = val;
            else if (key == "angle")      { try { lcase.angle = std::stod(val); } catch(...) {} }
            else if (key == "set_id")     { try { lcase.setId = std::stoi(val); } catch(...) {} }
            else if (key == "contact_id") { try { lcase.contactId = std::stoi(val); } catch(...) {} }
        }
    }
    f.close();

    if (modelFile.empty()) { console.error("[load] 'model' not specified"); return 1; }
    if (outputFile.empty()) { console.error("[load] 'output' not specified"); return 1; }
    if (loadOp.loads.empty()) { console.error("[load] 'loads' list is empty"); return 1; }

    if (!configDir.empty() && modelFile.find('/') == std::string::npos && modelFile.find('\\') == std::string::npos)
        modelFile = configDir + "/" + modelFile;

    std::string outputPrefix = outputFile;
    if (outputPrefix.size() > 2 && outputPrefix.substr(outputPrefix.size()-2) == ".k")
        outputPrefix = outputPrefix.substr(0, outputPrefix.size()-2);
    if (!configDir.empty() && outputPrefix.find('/') == std::string::npos && outputPrefix.find('\\') == std::string::npos)
        outputPrefix = configDir + "/" + outputPrefix;

    console.println("[load] Model: " + modelFile);
    console.println("[load] Output: " + outputPrefix + ".k");
    console.println("[load] Load cases: " + std::to_string(loadOp.loads.size()));

    ModelAssembler assembler;
    if (!assembler.loadBaseModel(modelFile)) {
        console.error(assembler.getErrorMessage());
        return 1;
    }

    if (!assembler.applyLoad(loadOp)) {
        console.error(assembler.getErrorMessage());
        return 1;
    }

    for (const auto& msg : assembler.infoMessages)
        console.println(msg);

    if (!assembler.writeOutput(outputPrefix)) {
        console.error(assembler.getErrorMessage());
        return 1;
    }

    console.println("[load] Done -> " + outputPrefix + ".k");
    return 0;
}

// Standalone boundary command
int runBoundary(const std::string& yamlFile, ConsoleOutput& console) {
    using namespace KooRemapper;

    std::ifstream f(yamlFile);
    if (!f.is_open()) { console.error("Cannot open: " + yamlFile); return 1; }

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
    auto stripQuotes = [](const std::string& s) -> std::string {
        if (s.size() >= 2 && ((s.front()=='"' && s.back()=='"') || (s.front()=='\'' && s.back()=='\'')))
            return s.substr(1, s.size()-2);
        return s;
    };

    std::string modelFile, outputFile;
    BoundaryOperation boundaryOp;
    bool inBoundariesList = false;
    int boundariesListIndent = 0;
    bool inBoundaryItem = false;

    std::string ln;
    while (std::getline(f, ln)) {
        if (!ln.empty() && ln.back()=='\r') ln.pop_back();
        int indent = countIndent(ln);
        std::string tr = trim(ln);
        if (tr.empty() || tr[0]=='#') continue;

        // Exit boundaries list
        if (inBoundariesList && indent <= boundariesListIndent && tr.substr(0,2) != "- ") {
            inBoundariesList = false;
            inBoundaryItem = false;
        }

        size_t cp = tr.find(':');
        if (cp == std::string::npos) continue;
        std::string key = trim(tr.substr(0, cp));
        std::string val = stripQuotes(trim(tr.substr(cp+1)));

        if (!inBoundariesList) {
            if      (key == "model")  modelFile = val;
            else if (key == "output") outputFile = val;
            else if (key == "boundaries") {
                inBoundariesList = true;
                boundariesListIndent = indent;
            }
            continue;
        }

        // Boundary list item start
        if (inBoundariesList && tr.substr(0,2) == "- " && indent > boundariesListIndent) {
            boundaryOp.boundaries.push_back({});
            inBoundaryItem = true;
            std::string rest = trim(tr.substr(2));
            size_t rcp = rest.find(':');
            if (rcp != std::string::npos) {
                std::string rk = trim(rest.substr(0, rcp));
                std::string rv = stripQuotes(trim(rest.substr(rcp+1)));
                auto& bc = boundaryOp.boundaries.back();
                if (rk == "part") {
                    try { bc.pid = std::stoi(rv); } catch(...) { bc.partName = rv; }
                } else if (rk == "dof") bc.dof = rv;
                else if (rk == "select") bc.select = rv;
            }
            continue;
        }

        // Sub-keys of boundary item
        if (inBoundaryItem && !boundaryOp.boundaries.empty()) {
            auto& bc = boundaryOp.boundaries.back();
            if (key == "part") {
                try { bc.pid = std::stoi(val); } catch(...) { bc.partName = val; }
            } else if (key == "dof") bc.dof = val;
            else if (key == "select") bc.select = val;
            else if (key == "angle") { try { bc.angle = std::stod(val); } catch(...) {} }
            else if (key == "set_id") { try { bc.setId = std::stoi(val); } catch(...) {} }
            else if (key == "dofx") { try { bc.dofx = std::stoi(val); } catch(...) {} }
            else if (key == "dofy") { try { bc.dofy = std::stoi(val); } catch(...) {} }
            else if (key == "dofz") { try { bc.dofz = std::stoi(val); } catch(...) {} }
            else if (key == "dofrx") { try { bc.dofrx = std::stoi(val); } catch(...) {} }
            else if (key == "dofry") { try { bc.dofry = std::stoi(val); } catch(...) {} }
            else if (key == "dofrz") { try { bc.dofrz = std::stoi(val); } catch(...) {} }
            else if (key == "direction" && !val.empty() && val.front() == '[' && val.back() == ']') {
                std::string inner = val.substr(1, val.size()-2);
                std::istringstream iss(inner);
                std::string tok;
                int di = 0;
                while (std::getline(iss, tok, ',') && di < 3) {
                    try { bc.direction[di] = std::stod(trim(tok)); } catch(...) {}
                    di++;
                }
            }
            continue;
        }
    }
    f.close();

    if (modelFile.empty()) { console.error("model not specified"); return 1; }
    if (outputFile.empty()) outputFile = modelFile;

    // Resolve paths
    if (!configDir.empty()) {
        auto hasDir = [](const std::string& p) {
            return p.find('/') != std::string::npos || p.find('\\') != std::string::npos;
        };
        if (!hasDir(modelFile))  modelFile  = configDir + "/" + modelFile;
        if (!hasDir(outputFile)) outputFile = configDir + "/" + outputFile;
    }

    std::string outputPrefix = outputFile;
    if (outputPrefix.size() >= 2 && outputPrefix.substr(outputPrefix.size()-2) == ".k")
        outputPrefix = outputPrefix.substr(0, outputPrefix.size()-2);

    console.println("[boundary] Model: " + modelFile);
    console.println("[boundary] Output: " + outputPrefix + ".k");
    console.println("[boundary] Boundary cases: " + std::to_string(boundaryOp.boundaries.size()));

    ModelAssembler assembler;
    if (!assembler.loadBaseModel(modelFile)) {
        console.error(assembler.getErrorMessage());
        return 1;
    }

    if (!assembler.applyBoundary(boundaryOp)) {
        console.error(assembler.getErrorMessage());
        return 1;
    }

    for (const auto& msg : assembler.infoMessages)
        console.println(msg);

    if (!assembler.writeOutput(outputPrefix)) {
        console.error(assembler.getErrorMessage());
        return 1;
    }

    console.println("[boundary] Done -> " + outputPrefix + ".k");
    return 0;
}

// ── Standalone RBE command ──────────────────────────────────────────────────
int runRbe(const std::string& yamlFile, ConsoleOutput& console) {
    using namespace KooRemapper;

    std::ifstream f(yamlFile);
    if (!f.is_open()) { console.error("Cannot open: " + yamlFile); return 1; }

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
    auto stripQuotes = [](const std::string& s) -> std::string {
        if (s.size() >= 2 && ((s.front()=='"' && s.back()=='"') || (s.front()=='\'' && s.back()=='\'')))
            return s.substr(1, s.size()-2);
        return s;
    };

    std::string modelFile, outputFile;
    RbeOperation rbeOp;
    bool inRbeList = false;
    int rbeListIndent = 0;
    bool inRbeItem = false;

    std::string ln;
    while (std::getline(f, ln)) {
        if (!ln.empty() && ln.back()=='\r') ln.pop_back();
        int indent = countIndent(ln);
        std::string tr = trim(ln);
        if (tr.empty() || tr[0]=='#') continue;

        // Exit rbe list
        if (inRbeList && indent <= rbeListIndent && tr.substr(0,2) != "- ") {
            inRbeList = false;
            inRbeItem = false;
        }

        size_t cp = tr.find(':');
        if (cp == std::string::npos) continue;
        std::string key = trim(tr.substr(0, cp));
        std::string val = stripQuotes(trim(tr.substr(cp+1)));

        if (!inRbeList) {
            if      (key == "model")  modelFile = val;
            else if (key == "output") outputFile = val;
            else if (key == "rbe") {
                inRbeList = true;
                rbeListIndent = indent;
            }
            continue;
        }

        // RBE list item start
        if (inRbeList && tr.substr(0,2) == "- " && indent > rbeListIndent) {
            rbeOp.constraints.push_back({});
            inRbeItem = true;
            std::string rest = trim(tr.substr(2));
            size_t rcp = rest.find(':');
            if (rcp != std::string::npos) {
                std::string rk = trim(rest.substr(0, rcp));
                std::string rv = stripQuotes(trim(rest.substr(rcp+1)));
                auto& rc = rbeOp.constraints.back();
                if (rk == "part") {
                    try { rc.pid = std::stoi(rv); } catch(...) { rc.partName = rv; }
                } else if (rk == "select") rc.select = rv;
                else if (rk == "type") rc.type = rv;
                else if (rk == "mode") rc.mode = rv;
            }
            continue;
        }

        // Sub-keys of rbe item
        if (inRbeItem && !rbeOp.constraints.empty()) {
            auto& rc = rbeOp.constraints.back();
            if (key == "part") {
                try { rc.pid = std::stoi(val); } catch(...) { rc.partName = val; }
            } else if (key == "select") rc.select = val;
            else if (key == "type") rc.type = val;
            else if (key == "mode") rc.mode = val;
            else if (key == "angle") { try { rc.angle = std::stod(val); } catch(...) {} }
            else if (key == "direction" && !val.empty() && val.front() == '[' && val.back() == ']') {
                std::string inner = val.substr(1, val.size()-2);
                std::istringstream iss(inner);
                std::string tok;
                int di = 0;
                while (std::getline(iss, tok, ',') && di < 3) {
                    try { rc.direction[di] = std::stod(trim(tok)); } catch(...) {}
                    di++;
                }
            }
            continue;
        }
    }
    f.close();

    if (modelFile.empty()) { console.error("model not specified"); return 1; }
    if (outputFile.empty()) outputFile = modelFile;

    // Resolve paths
    if (!configDir.empty()) {
        auto hasDir = [](const std::string& p) {
            return p.find('/') != std::string::npos || p.find('\\') != std::string::npos;
        };
        if (!hasDir(modelFile))  modelFile  = configDir + "/" + modelFile;
        if (!hasDir(outputFile)) outputFile = configDir + "/" + outputFile;
    }

    std::string outputPrefix = outputFile;
    if (outputPrefix.size() >= 2 && outputPrefix.substr(outputPrefix.size()-2) == ".k")
        outputPrefix = outputPrefix.substr(0, outputPrefix.size()-2);

    console.println("[rbe] Model: " + modelFile);
    console.println("[rbe] Output: " + outputPrefix + ".k");
    console.println("[rbe] Constraints: " + std::to_string(rbeOp.constraints.size()));

    ModelAssembler assembler;
    if (!assembler.loadBaseModel(modelFile)) {
        console.error(assembler.getErrorMessage());
        return 1;
    }

    if (!assembler.applyRbe(rbeOp)) {
        console.error(assembler.getErrorMessage());
        return 1;
    }

    for (const auto& msg : assembler.infoMessages)
        console.println(msg);

    if (!assembler.writeOutput(outputPrefix)) {
        console.error(assembler.getErrorMessage());
        return 1;
    }

    console.println("[rbe] Done -> " + outputPrefix + ".k");
    return 0;
}

// Standalone optimize command
int runOptimize(const std::string& yamlFile, ConsoleOutput& console) {
    // Parse YAML
    std::ifstream f(yamlFile);
    if (!f.is_open()) { console.error("Cannot open: " + yamlFile); return 1; }

    std::string configDir;
    size_t lastSlash = yamlFile.find_last_of("/\\");
    if (lastSlash != std::string::npos) configDir = yamlFile.substr(0, lastSlash);

    auto trim = [](const std::string& s) -> std::string {
        size_t a=0, b=s.size();
        while (a<b && std::isspace((unsigned char)s[a])) ++a;
        while (b>a && std::isspace((unsigned char)s[b-1])) --b;
        return s.substr(a,b-a);
    };

    std::string modelFile, outputFile;
    OptimizeConfig cfg;
    cfg.mode = "rubber";  // default

    std::string ln;
    while (std::getline(f, ln)) {
        if (!ln.empty() && ln.back()=='\r') ln.pop_back();
        std::string tr = trim(ln);
        if (tr.empty() || tr[0]=='#') continue;
        size_t cp = tr.find(':');
        if (cp == std::string::npos) continue;
        std::string key = trim(tr.substr(0, cp));
        std::string val = trim(tr.substr(cp+1));

        if      (key == "model")    modelFile = val;
        else if (key == "output")   outputFile = val;
        else if (key == "optimize")      cfg.mode = val;
        else if (key == "tssfac")        { try { cfg.tssfac = std::stod(val); } catch(...) {} }
        else if (key == "analysis_type") cfg.analysisType = val;
        else if (key == "pid")           cfg.pids = { std::stoi(val) };
        else if (key == "pids") {
            std::string lv = val;
            if (!lv.empty() && lv.front()=='[') lv = lv.substr(1);
            if (!lv.empty() && lv.back()==']') lv.pop_back();
            std::istringstream ss(lv); std::string tok;
            while (std::getline(ss, tok, ',')) {
                std::string t = trim(tok);
                if (!t.empty()) try { cfg.pids.push_back(std::stoi(t)); } catch(...) {}
            }
        }
    }

    if (modelFile.empty())  { console.error("optimize YAML: 'model' not specified");  return 1; }
    if (outputFile.empty()) { console.error("optimize YAML: 'output' not specified"); return 1; }

    // Resolve paths relative to configDir
    auto resolvePath = [&](const std::string& p) -> std::string {
        if (!configDir.empty() && !p.empty() &&
            p[0] != '/' && p[0] != '\\' &&
            !(p.size() >= 2 && p[1] == ':')) {
            return configDir + "/" + p;
        }
        return p;
    };
    std::string modelPath = resolvePath(modelFile);
    std::string outputPath = resolvePath(outputFile);

    console.println("[optimize] Mode   : " + cfg.mode);
    console.println("[optimize] Model  : " + modelPath);
    console.println("[optimize] Output : " + outputPath);
    if (!cfg.pids.empty()) {
        std::string pidStr;
        for (int pid : cfg.pids) {
            if (!pidStr.empty()) pidStr += ", ";
            pidStr += std::to_string(pid);
        }
        console.println("[optimize] PIDs   : " + pidStr);
    }

    // Read model
    std::vector<std::string> lines;
    {
        std::ifstream mf(modelPath);
        if (!mf.is_open()) { console.error("Cannot open model: " + modelPath); return 1; }
        std::string l;
        while (std::getline(mf, l)) {
            if (!l.empty() && l.back()=='\r') l.pop_back();
            lines.push_back(l);
        }
    }

    // Apply optimization
    std::vector<std::string> msgs;
    if (cfg.mode == "rubber") {
        msgs = opt_applyRubber(lines, cfg);
    } else {
        console.error("Unknown optimize mode: " + cfg.mode);
        return 1;
    }

    for (const auto& m : msgs) console.println(m);

    // Write output
    {
        std::ofstream fout(outputPath);
        if (!fout.is_open()) { console.error("Cannot write: " + outputPath); return 1; }
        for (const auto& l : lines) fout << l << "\n";
    }

    console.println("[optimize] Done -> " + outputPath);
    return 0;
}

// =====================================================================
// stabilize command: explicit solver stabilization (12-level system)
// =====================================================================
struct StabilizeConfig {
    std::string mode;           // "explicit"
    int level = 0;             // 0=manual, 1-12=preset
    bool confirmErosion = false;
    // time step / erosion
    double tssfac = -1;         // -1 = not set
    int erode = -1;
    // hourglass
    int ihq = -1;
    double qh = -1;
    // accuracy
    int osu = -1;
    int inn = -1;
    int esortSolid = -1;
    int esortShell = -1;
    // shell (irnxx: INT_MIN = not set; valid values: -1, -2)
    int bwc = -1;
    int miter = -1;
    int irnxx = INT_MIN;
    double wrpang = -1;
    // contact global Card 1
    int orien = -1;
    int shlthk = -1;
    int enmass = -1;
    int islchk = -1;
    // contact global Card 2
    double xpene = -1;
    int nsbcs = -1;
    // contact per-contact (Card A)
    int soft = -1;
    int sbopt = -1;
    int depth = -1;
    double maxpar = -1;
    // contact per-contact (Card C)
    int ignore_ = -1;
    // bulk viscosity (forced override)
    double bulkQ1 = -1;
    double bulkQ2 = -1;
    // energy
    int hgen = -1;
    int rwen = -1;
    int slnten = -1;
    int rylen = -1;
};

static bool stab_hasShellElements(const std::vector<std::string>& lines) {
    for (const auto& ln : lines) {
        std::string tr = impl_trim(ln);
        if (!tr.empty() && tr[0] == '*')
            if (impl_upper(tr).rfind("*ELEMENT_SHELL", 0) == 0) return true;
    }
    return false;
}

// Like opt_patchControlField but can target card N (0=first data card)
static int stab_patchControlFieldN(std::vector<std::string>& lines,
                                    const std::string& keyword, int cardIdx,
                                    int fieldPos, int fieldWidth,
                                    const std::string& newVal) {
    bool inBlock = false, hasTitle = false, titleDone = false;
    int dataCardSeen = 0;
    for (auto& ln : lines) {
        std::string tr = impl_trim(ln);
        if (tr.empty()) continue;
        if (tr[0] == '*') {
            std::string up = impl_upper(tr);
            inBlock    = (up.rfind(keyword, 0) == 0);
            hasTitle   = (up.find("_TITLE") != std::string::npos);
            titleDone  = false;
            dataCardSeen = 0;
            continue;
        }
        if (!inBlock || tr[0] == '$') continue;
        if (hasTitle && !titleDone) { titleDone = true; continue; }
        if (dataCardSeen < cardIdx) { ++dataCardSeen; continue; }
        std::string curVal;
        if ((int)ln.size() > fieldPos) {
            int end = std::min((int)ln.size(), fieldPos + fieldWidth);
            curVal = impl_trim(ln.substr(fieldPos, end - fieldPos));
        }
        if (curVal == impl_trim(newVal)) return 1;
        ln = impl_setField(ln, fieldPos, fieldWidth, newVal);
        return 2;
    }
    return 0;
}

// If *CONTROL_CONTACT exists with only Card 1, insert a blank Card 2 after it.
static void stab_ensureControlContactCard2(std::vector<std::string>& lines) {
    bool inBlock = false, hasTitle = false, titleDone = false;
    int dataCardSeen = 0, card1Idx = -1;
    for (int i = 0; i < (int)lines.size(); ++i) {
        std::string tr = impl_trim(lines[i]);
        if (tr.empty()) continue;
        if (tr[0] == '*') {
            std::string up = impl_upper(tr);
            bool isCC = (up.rfind("*CONTROL_CONTACT", 0) == 0);
            if (inBlock && card1Idx >= 0 && dataCardSeen == 1) {
                // Leaving block with only Card 1 → insert blank Card 2
                lines.insert(lines.begin() + card1Idx + 1, "");
                return;
            }
            inBlock      = isCC;
            hasTitle     = isCC && (up.find("_TITLE") != std::string::npos);
            titleDone    = false;
            dataCardSeen = 0;
            card1Idx     = -1;
            continue;
        }
        if (!inBlock || tr[0] == '$') continue;
        if (hasTitle && !titleDone) { titleDone = true; continue; }
        if (dataCardSeen == 0) card1Idx = i;
        else if (dataCardSeen == 1) return; // Card 2 already exists
        ++dataCardSeen;
    }
    if (inBlock && card1Idx >= 0 && dataCardSeen == 1)
        lines.insert(lines.begin() + card1Idx + 1, "");
}

static std::vector<std::string> stab_applyExplicit(
        std::vector<std::string>& lines,
        const StabilizeConfig& cfg) {
    std::vector<std::string> msgs;
    auto tag = [](const std::string& s) { return "[stabilize] " + s; };

    bool hasShell = stab_hasShellElements(lines);
    if (!hasShell) msgs.push_back(tag("Note: No *ELEMENT_SHELL — shell-specific options will be skipped"));

    // ── 1. CONTROL_ENERGY ────────────────────────────────────────────
    if (cfg.hgen >= 0 || cfg.rwen >= 0 || cfg.slnten >= 0 || cfg.rylen >= 0) {
        int h = cfg.hgen   >= 0 ? cfg.hgen   : 2;
        int r = cfg.rwen   >= 0 ? cfg.rwen   : 2;
        int s = cfg.slnten >= 0 ? cfg.slnten : 2;
        int y = cfg.rylen  >= 0 ? cfg.rylen  : 2;
        bool anyMod = false;
        if (!opt_hasKeyword(lines, "*CONTROL_ENERGY")) {
            char buf[90]; snprintf(buf, sizeof(buf), "%10d%10d%10d%10d", h, r, s, y);
            impl_insertBeforeEnd(lines,
                "*CONTROL_ENERGY\n"
                "$     HGEN      RWEN    SLNTEN     RYLEN\n" + std::string(buf));
            msgs.push_back(tag("*CONTROL_ENERGY: HGEN=" + std::to_string(h) +
                               ",RWEN=" + std::to_string(r) + ",SLNTEN=" + std::to_string(s) +
                               ",RYLEN=" + std::to_string(y) + " (inserted)"));
        } else {
            if (cfg.hgen   >= 0 && opt_patchControlField(lines, "*CONTROL_ENERGY",  0, 10, std::to_string(cfg.hgen))   == 2) anyMod = true;
            if (cfg.rwen   >= 0 && opt_patchControlField(lines, "*CONTROL_ENERGY", 10, 10, std::to_string(cfg.rwen))   == 2) anyMod = true;
            if (cfg.slnten >= 0 && opt_patchControlField(lines, "*CONTROL_ENERGY", 20, 10, std::to_string(cfg.slnten)) == 2) anyMod = true;
            if (cfg.rylen  >= 0 && opt_patchControlField(lines, "*CONTROL_ENERGY", 30, 10, std::to_string(cfg.rylen))  == 2) anyMod = true;
            msgs.push_back(tag(std::string("*CONTROL_ENERGY: ") + (anyMod ? "modified" : "OK")));
        }
    }

    // ── 2. CONTROL_ACCURACY ──────────────────────────────────────────
    if (cfg.osu >= 0 || cfg.inn >= 0) {
        bool anyMod = false;
        if (!opt_hasKeyword(lines, "*CONTROL_ACCURACY")) {
            int o = cfg.osu >= 0 ? cfg.osu : 0;
            int n = cfg.inn >= 0 ? cfg.inn : 4;
            char buf[90]; snprintf(buf, sizeof(buf), "%10d%10d", o, n);
            impl_insertBeforeEnd(lines,
                "*CONTROL_ACCURACY\n"
                "$      OSU       INN    PIDOSU\n" + std::string(buf));
            msgs.push_back(tag("*CONTROL_ACCURACY: OSU=" + std::to_string(o) +
                               ",INN=" + std::to_string(n) + " (inserted)"));
        } else {
            if (cfg.osu >= 0 && opt_patchControlField(lines, "*CONTROL_ACCURACY",  0, 10, std::to_string(cfg.osu)) == 2) anyMod = true;
            if (cfg.inn >= 0 && opt_patchControlField(lines, "*CONTROL_ACCURACY", 10, 10, std::to_string(cfg.inn)) == 2) anyMod = true;
            msgs.push_back(tag(std::string("*CONTROL_ACCURACY: ") + (anyMod ? "modified" : "OK")));
        }
    }

    // ── 3. CONTROL_SOLID (ESORT) ──────────────────────────────────────
    if (cfg.esortSolid >= 0) {
        int r = opt_patchControlField(lines, "*CONTROL_SOLID", 0, 10, std::to_string(cfg.esortSolid));
        if (r == 0) {
            char buf[90]; snprintf(buf, sizeof(buf), "%10d", cfg.esortSolid);
            impl_insertBeforeEnd(lines,
                "*CONTROL_SOLID\n"
                "$    ESORT    FMATRX    NIPTETS     SWLOCL     PSFAIL       T10      ICOH     TET13\n" + std::string(buf));
            msgs.push_back(tag("*CONTROL_SOLID: ESORT=" + std::to_string(cfg.esortSolid) + " (inserted)"));
        } else {
            msgs.push_back(tag(std::string("*CONTROL_SOLID: ESORT=") + std::to_string(cfg.esortSolid) +
                               (r == 2 ? " (modified)" : " (OK)")));
        }
    }

    // ── 4. CONTROL_SHELL (WRPANG ESORT IRNXX BWC MITER) ──────────────
    bool needShellCard = (cfg.esortShell >= 0 || cfg.bwc >= 0 || cfg.miter >= 0 ||
                          cfg.irnxx != INT_MIN || cfg.wrpang >= 0);
    if (needShellCard && !hasShell) {
        msgs.push_back(tag("*CONTROL_SHELL: skipped (no shell elements in model)"));
    } else if (needShellCard) {
        bool anyMod = false;
        if (!opt_hasKeyword(lines, "*CONTROL_SHELL")) {
            double wrp = cfg.wrpang     >= 0       ? cfg.wrpang     : 20.0;
            int    es  = cfg.esortShell >= 0       ? cfg.esortShell : 0;
            int    iro = cfg.irnxx      != INT_MIN ? cfg.irnxx      : -1;
            int    bw  = cfg.bwc        >= 0       ? cfg.bwc        : 2;
            int    mi  = cfg.miter      >= 0       ? cfg.miter      : 1;
            char buf[90];
            snprintf(buf, sizeof(buf), "%10.4f%10d%10d%10s%10s%10d%10d",
                     wrp, es, iro, "", "", bw, mi);
            impl_insertBeforeEnd(lines,
                "*CONTROL_SHELL\n"
                "$   WRPANG     ESORT     IRNXX    ISTUPD    THEORY       BWC     MITER      PROJ\n" +
                std::string(buf));
            msgs.push_back(tag("*CONTROL_SHELL: inserted"));
        } else {
            if (cfg.wrpang >= 0) {
                char buf[16]; snprintf(buf, sizeof(buf), "%10.4f", cfg.wrpang);
                if (opt_patchControlField(lines, "*CONTROL_SHELL",  0, 10, std::string(buf)) == 2) anyMod = true;
            }
            if (cfg.esortShell >= 0 && opt_patchControlField(lines, "*CONTROL_SHELL", 10, 10, std::to_string(cfg.esortShell)) == 2) anyMod = true;
            if (cfg.irnxx != INT_MIN && opt_patchControlField(lines, "*CONTROL_SHELL", 20, 10, std::to_string(cfg.irnxx)) == 2) anyMod = true;
            if (cfg.bwc   >= 0 && opt_patchControlField(lines, "*CONTROL_SHELL", 50, 10, std::to_string(cfg.bwc))   == 2) anyMod = true;
            if (cfg.miter >= 0 && opt_patchControlField(lines, "*CONTROL_SHELL", 60, 10, std::to_string(cfg.miter)) == 2) anyMod = true;
            msgs.push_back(tag(std::string("*CONTROL_SHELL: ") + (anyMod ? "modified" : "OK")));
        }
    }

    // ── 5. CONTROL_TIMESTEP (TSSFAC, ERODE) ──────────────────────────
    if (cfg.tssfac >= 0 || cfg.erode >= 0) {
        bool anyMod = false;
        if (!opt_hasKeyword(lines, "*CONTROL_TIMESTEP")) {
            double ts = cfg.tssfac >= 0 ? cfg.tssfac : 0.9;
            int    er = cfg.erode  >= 0 ? cfg.erode  : 0;
            char buf[90];
            snprintf(buf, sizeof(buf), "       0.0%10.6f         0       0.0       0.0         0%10d         0",
                     ts, er);
            impl_insertBeforeEnd(lines,
                "*CONTROL_TIMESTEP\n"
                "$   DTINIT    TSSFAC      ISDO    TSLIMT     DT2MS      LCTM     ERODE     MS1ST\n" +
                std::string(buf));
            msgs.push_back(tag("*CONTROL_TIMESTEP: inserted"));
        } else {
            if (cfg.tssfac >= 0) {
                char buf[16]; snprintf(buf, sizeof(buf), "%10.6f", cfg.tssfac);
                int r = opt_patchControlField(lines, "*CONTROL_TIMESTEP", 10, 10, std::string(buf));
                if (r == 2) anyMod = true;
                msgs.push_back(tag("*CONTROL_TIMESTEP: TSSFAC=" + std::to_string(cfg.tssfac) +
                                   (r == 2 ? " (modified)" : " (OK)")));
            }
            if (cfg.erode >= 0) {
                int r = opt_patchControlField(lines, "*CONTROL_TIMESTEP", 60, 10, std::to_string(cfg.erode));
                if (r == 2) anyMod = true;
                msgs.push_back(tag("*CONTROL_TIMESTEP: ERODE=" + std::to_string(cfg.erode) +
                                   (r == 2 ? " (modified)" : " (OK)")));
            }
        }
    }

    // ── 6. CONTROL_HOURGLASS ─────────────────────────────────────────
    if (cfg.ihq >= 0 || cfg.qh >= 0) {
        bool anyMod = false;
        if (!opt_hasKeyword(lines, "*CONTROL_HOURGLASS")) {
            int    h = cfg.ihq >= 0 ? cfg.ihq : 1;
            double q = cfg.qh  >= 0 ? cfg.qh  : 0.1;
            char buf[90]; snprintf(buf, sizeof(buf), "%10d%10.4f", h, q);
            impl_insertBeforeEnd(lines,
                "*CONTROL_HOURGLASS\n"
                "$      IHQ        QH\n" + std::string(buf));
            msgs.push_back(tag("*CONTROL_HOURGLASS: IHQ=" + std::to_string(h) +
                               ",QH=" + std::to_string(q) + " (inserted)"));
        } else {
            if (cfg.ihq >= 0 && opt_patchControlField(lines, "*CONTROL_HOURGLASS", 0, 10, std::to_string(cfg.ihq)) == 2) anyMod = true;
            if (cfg.qh  >= 0) {
                char buf[16]; snprintf(buf, sizeof(buf), "%10.4f", cfg.qh);
                if (opt_patchControlField(lines, "*CONTROL_HOURGLASS", 10, 10, std::string(buf)) == 2) anyMod = true;
            }
            msgs.push_back(tag(std::string("*CONTROL_HOURGLASS: ") + (anyMod ? "modified" : "OK")));
        }
    }

    // ── 7. CONTROL_CONTACT (Card 1 + Card 2) ─────────────────────────
    bool needCC1 = (cfg.orien >= 0 || cfg.shlthk >= 0 || cfg.islchk >= 0 || cfg.enmass >= 0);
    bool needCC2 = (cfg.nsbcs >= 0 || cfg.xpene  >= 0);
    if (needCC1 || needCC2) {
        bool anyMod = false;
        if (!opt_hasKeyword(lines, "*CONTROL_CONTACT")) {
            std::string c1(80, ' ');
            if (cfg.islchk >= 0) c1 = impl_setField(c1, 20, 10, std::to_string(cfg.islchk));
            if (cfg.shlthk >= 0) c1 = impl_setField(c1, 30, 10, std::to_string(cfg.shlthk));
            if (cfg.orien  >= 0) c1 = impl_setField(c1, 60, 10, std::to_string(cfg.orien));
            if (cfg.enmass >= 0) c1 = impl_setField(c1, 70, 10, std::to_string(cfg.enmass));
            std::string c2(80, ' ');
            if (cfg.nsbcs >= 0) c2 = impl_setField(c2, 20, 10, std::to_string(cfg.nsbcs));
            if (cfg.xpene >= 0) {
                char buf[16]; snprintf(buf, sizeof(buf), "%10.4f", cfg.xpene);
                c2 = impl_setField(c2, 40, 10, std::string(buf));
            }
            impl_insertBeforeEnd(lines,
                "*CONTROL_CONTACT\n"
                "$    SLSFAC    RWPNAL    ISLCHK    SHLTHK    PENOPT    THKCHG     ORIEN    ENMASS\n" + c1 + "\n"
                "$    USRSTR    USRFRC     NSBCS    INTERM     XPENE     SSTHK      ECDT   TIEDPRJ\n" + c2);
            msgs.push_back(tag("*CONTROL_CONTACT: inserted"));
        } else {
            if (cfg.islchk >= 0 && opt_patchControlField(lines, "*CONTROL_CONTACT", 20, 10, std::to_string(cfg.islchk)) == 2) anyMod = true;
            if (cfg.shlthk >= 0 && opt_patchControlField(lines, "*CONTROL_CONTACT", 30, 10, std::to_string(cfg.shlthk)) == 2) anyMod = true;
            if (cfg.orien  >= 0 && opt_patchControlField(lines, "*CONTROL_CONTACT", 60, 10, std::to_string(cfg.orien))  == 2) anyMod = true;
            if (cfg.enmass >= 0 && opt_patchControlField(lines, "*CONTROL_CONTACT", 70, 10, std::to_string(cfg.enmass)) == 2) anyMod = true;
            if (needCC2) {
                stab_ensureControlContactCard2(lines);
                if (cfg.nsbcs >= 0 && stab_patchControlFieldN(lines, "*CONTROL_CONTACT", 1, 20, 10, std::to_string(cfg.nsbcs)) == 2) anyMod = true;
                if (cfg.xpene >= 0) {
                    char buf[16]; snprintf(buf, sizeof(buf), "%10.4f", cfg.xpene);
                    if (stab_patchControlFieldN(lines, "*CONTROL_CONTACT", 1, 40, 10, std::string(buf)) == 2) anyMod = true;
                }
            }
            msgs.push_back(tag(std::string("*CONTROL_CONTACT: ") + (anyMod ? "modified" : "OK")));
        }
    }

    // ── 8. CONTROL_BULK_VISCOSITY (forced override) ────────────────────
    if (cfg.bulkQ1 >= 0 || cfg.bulkQ2 >= 0) {
        bool anyMod = false;
        if (!opt_hasKeyword(lines, "*CONTROL_BULK_VISCOSITY")) {
            double q1 = cfg.bulkQ1 >= 0 ? cfg.bulkQ1 : 1.5;
            double q2 = cfg.bulkQ2 >= 0 ? cfg.bulkQ2 : 0.06;
            char buf[90]; snprintf(buf, sizeof(buf), "%10.4f%10.4f", q1, q2);
            impl_insertBeforeEnd(lines,
                "*CONTROL_BULK_VISCOSITY\n"
                "$       Q1        Q2\n" + std::string(buf));
            msgs.push_back(tag("*CONTROL_BULK_VISCOSITY: Q1=" + std::to_string(q1) +
                               ",Q2=" + std::to_string(q2) + " (inserted)"));
        } else {
            if (cfg.bulkQ1 >= 0) {
                char buf[16]; snprintf(buf, sizeof(buf), "%10.4f", cfg.bulkQ1);
                if (opt_patchControlField(lines, "*CONTROL_BULK_VISCOSITY",  0, 10, std::string(buf)) == 2) anyMod = true;
            }
            if (cfg.bulkQ2 >= 0) {
                char buf[16]; snprintf(buf, sizeof(buf), "%10.4f", cfg.bulkQ2);
                if (opt_patchControlField(lines, "*CONTROL_BULK_VISCOSITY", 10, 10, std::string(buf)) == 2) anyMod = true;
            }
            msgs.push_back(tag(std::string("*CONTROL_BULK_VISCOSITY: ") + (anyMod ? "modified (forced)" : "OK")));
        }
    }

    // ── 9. Per-contact optional cards (Card A: SOFT/SBOPT/DEPTH/MAXPAR; Card C: IGNORE) ──
    bool needPerContact = (cfg.soft >= 0 || cfg.sbopt >= 0 || cfg.depth >= 0 ||
                           cfg.maxpar >= 0 || cfg.ignore_ >= 0);
    if (needPerContact) {
        auto contacts = ct_parseContacts(lines);
        int modCount = 0;
        for (auto& ct : contacts) {
            ContactDef merged = ct;
            bool changed = false;
            if (cfg.soft   >= 0 || cfg.sbopt >= 0 || cfg.depth >= 0 || cfg.maxpar >= 0) {
                merged.hasCardA = true;
                if (cfg.soft   >= 0) { merged.soft   = cfg.soft;         changed = true; }
                if (cfg.sbopt  >= 0) { merged.sbopt  = cfg.sbopt;        changed = true; }
                if (cfg.depth  >= 0) { merged.depth  = cfg.depth;        changed = true; }
                if (cfg.maxpar >= 0) { merged.maxpar = cfg.maxpar;       changed = true; }
            }
            if (cfg.ignore_ >= 0) {
                merged.hasCardA = true;
                merged.hasCardB = true;
                merged.hasCardC = true;
                merged.ignore_ = cfg.ignore_;
                changed = true;
            }
            if (changed) {
                ct_modifyOptionalCards(lines, ct, merged);
                contacts = ct_parseContacts(lines);  // re-parse after line shift
                modCount++;
            }
        }
        if (modCount > 0)
            msgs.push_back(tag(std::to_string(modCount) + " contact(s) updated (Card A/C options)"));
        else if (!contacts.empty())
            msgs.push_back(tag("Per-contact options: all contacts already up to date"));
        else
            msgs.push_back(tag("Per-contact options: no *CONTACT_* found in model"));
    }

    return msgs;
}

static void stab_resolveLevel(StabilizeConfig& cfg) {
    int lv = cfg.level;
    if (lv <= 0) return;

    // Level 1+: Energy diagnostics
    if (lv >= 1) {
        if (cfg.hgen   < 0) cfg.hgen   = 2;
        if (cfg.rwen   < 0) cfg.rwen   = 2;
        if (cfg.slnten < 0) cfg.slnten = 2;
        if (cfg.rylen  < 0) cfg.rylen  = 2;
    }
    // Level 2+: Accuracy
    if (lv >= 2) {
        if (cfg.osu        < 0) cfg.osu        = 1;
        if (cfg.inn        < 0) cfg.inn        = 4;
        if (cfg.esortSolid < 0) cfg.esortSolid = 1;
        if (cfg.esortShell < 0) cfg.esortShell = 1;
    }
    // Level 3+: Time step 1
    if (lv >= 3) {
        if (cfg.tssfac < 0) cfg.tssfac = 0.80;
    }
    // Level 4+: Hourglass stiffness
    if (lv >= 4) {
        if (cfg.ihq < 0) cfg.ihq = 4;
        if (cfg.qh  < 0) cfg.qh  = 0.10;
    }
    // Level 5+: Shell stabilization
    if (lv >= 5) {
        if (cfg.bwc   < 0)        cfg.bwc   = 1;
        if (cfg.miter < 0)        cfg.miter = 2;
        if (cfg.irnxx == INT_MIN) cfg.irnxx = -2;
        if (cfg.wrpang < 0)       cfg.wrpang = 10.0;
    }
    // Level 6+: Contact 1st stage
    if (lv >= 6) {
        if (cfg.orien  < 0) cfg.orien  = 2;
        if (cfg.shlthk < 0) cfg.shlthk = 1;
        if (cfg.xpene  < 0) cfg.xpene  = 2.0;
        if (cfg.islchk < 0) cfg.islchk = 2;
        if (cfg.soft   < 0) cfg.soft   = 1;
        if (cfg.sbopt  < 0) cfg.sbopt  = 2;
        if (cfg.depth  < 0) cfg.depth  = 3;
    }
    // Level 7+: Time step 2 + Bulk viscosity forced
    if (lv >= 7) {
        if (cfg.tssfac < 0 || cfg.tssfac > 0.67) cfg.tssfac = 0.67;
        if (cfg.bulkQ1 < 0) cfg.bulkQ1 = 1.5;
        if (cfg.bulkQ2 < 0) cfg.bulkQ2 = 0.06;
    }
    // Level 8+: Contact 2nd stage (pinball)
    if (lv >= 8) {
        cfg.shlthk = 2;
        cfg.soft   = 2;
        cfg.sbopt  = 3;
        cfg.depth  = 5;
        if (cfg.nsbcs  < 0) cfg.nsbcs  = 5;
        if (cfg.enmass < 0) cfg.enmass = 1;
        if (cfg.ignore_ < 0) cfg.ignore_ = 1;
        if (cfg.maxpar  < 0) cfg.maxpar  = 1.15;
    }
    // Level 9+: Best hourglass (Belytschko-Bindeman)
    if (lv >= 9) {
        cfg.ihq = 6;
        cfg.qh  = 1.0;
    }
    // Level 10+: Time step 3 + reduce NSBCS
    if (lv >= 10) {
        if (cfg.tssfac > 0.60) cfg.tssfac = 0.60;
        if (cfg.nsbcs  > 2)    cfg.nsbcs  = 2;
    }
    // Level 11+: Erosion
    if (lv >= 11) {
        if (cfg.erode < 0) cfg.erode = 11;
        cfg.enmass = 2;
        if (cfg.nsbcs  > 1)    cfg.nsbcs  = 1;
        if (cfg.tssfac > 0.55) cfg.tssfac = 0.55;
    }
    // Level 12+: Maximum conservative
    if (lv >= 12) {
        if (cfg.tssfac > 0.50) cfg.tssfac = 0.50;
        cfg.bulkQ1 = 2.0;
        cfg.bulkQ2 = 0.10;
    }
}

int runStabilize(const std::string& yamlFile, ConsoleOutput& console) {
    std::ifstream f(yamlFile);
    if (!f.is_open()) { console.error("Cannot open: " + yamlFile); return 1; }

    std::string configDir;
    size_t lastSlash = yamlFile.find_last_of("/\\");
    if (lastSlash != std::string::npos) configDir = yamlFile.substr(0, lastSlash);

    auto trim = [](const std::string& s) -> std::string {
        size_t a=0, b=s.size();
        while (a<b && std::isspace((unsigned char)s[a])) ++a;
        while (b>a && std::isspace((unsigned char)s[b-1])) --b;
        return s.substr(a, b-a);
    };

    std::string modelFile, outputFile;
    StabilizeConfig cfg;
    cfg.mode = "explicit";

    std::string ln;
    while (std::getline(f, ln)) {
        if (!ln.empty() && ln.back()=='\r') ln.pop_back();
        std::string tr = trim(ln);
        if (tr.empty() || tr[0]=='#') continue;
        size_t cp = tr.find(':');
        if (cp == std::string::npos) continue;
        std::string key = trim(tr.substr(0, cp));
        std::string val = trim(tr.substr(cp+1));
        if (val.empty()) continue;

        auto parseInt  = [&](int& v)    { try { v = std::stoi(val); } catch(...) {} };
        auto parseDbl  = [&](double& v) { try { v = std::stod(val); } catch(...) {} };
        auto parseBool = [&](bool& v)   { v = (val=="true"||val=="yes"||val=="1"); };

        if      (key == "model")           modelFile = val;
        else if (key == "output")          outputFile = val;
        else if (key == "stabilize")       cfg.mode = val;
        else if (key == "level")           parseInt(cfg.level);
        else if (key == "confirm_erosion") parseBool(cfg.confirmErosion);
        else if (key == "tssfac")          parseDbl(cfg.tssfac);
        else if (key == "erode")           parseInt(cfg.erode);
        else if (key == "ihq")             parseInt(cfg.ihq);
        else if (key == "qh")              parseDbl(cfg.qh);
        else if (key == "osu")             parseInt(cfg.osu);
        else if (key == "inn")             parseInt(cfg.inn);
        else if (key == "esort_solid")     parseInt(cfg.esortSolid);
        else if (key == "esort_shell")     parseInt(cfg.esortShell);
        else if (key == "bwc")             parseInt(cfg.bwc);
        else if (key == "miter")           parseInt(cfg.miter);
        else if (key == "irnxx")           parseInt(cfg.irnxx);
        else if (key == "wrpang")          parseDbl(cfg.wrpang);
        else if (key == "orien")           parseInt(cfg.orien);
        else if (key == "shlthk")          parseInt(cfg.shlthk);
        else if (key == "enmass")          parseInt(cfg.enmass);
        else if (key == "islchk")          parseInt(cfg.islchk);
        else if (key == "xpene")           parseDbl(cfg.xpene);
        else if (key == "nsbcs")           parseInt(cfg.nsbcs);
        else if (key == "soft")            parseInt(cfg.soft);
        else if (key == "sbopt")           parseInt(cfg.sbopt);
        else if (key == "depth")           parseInt(cfg.depth);
        else if (key == "maxpar")          parseDbl(cfg.maxpar);
        else if (key == "ignore")          parseInt(cfg.ignore_);
        else if (key == "bulk_q1")         parseDbl(cfg.bulkQ1);
        else if (key == "bulk_q2")         parseDbl(cfg.bulkQ2);
        else if (key == "hgen")            parseInt(cfg.hgen);
        else if (key == "rwen")            parseInt(cfg.rwen);
        else if (key == "slnten")          parseInt(cfg.slnten);
        else if (key == "rylen")           parseInt(cfg.rylen);
    }

    if (modelFile.empty())  { console.error("stabilize YAML: 'model' not specified");  return 1; }
    if (outputFile.empty()) { console.error("stabilize YAML: 'output' not specified"); return 1; }

    auto resolvePath = [&](const std::string& p) -> std::string {
        if (!configDir.empty() && !p.empty() &&
            p[0] != '/' && p[0] != '\\' &&
            !(p.size() >= 2 && p[1] == ':'))
            return configDir + "/" + p;
        return p;
    };
    std::string modelPath  = resolvePath(modelFile);
    std::string outputPath = resolvePath(outputFile);

    // Apply level presets (before erosion check, so erode is filled if needed)
    stab_resolveLevel(cfg);

    // Erosion confirmation
    if (cfg.erode >= 0 && !cfg.confirmErosion) {
        console.println("[stabilize] WARNING: ERODE=" + std::to_string(cfg.erode) +
                        " will allow element deletion during the simulation.");
        console.println("[stabilize] Add 'confirm_erosion: true' to YAML to skip this prompt.");
        std::cout << "Apply ERODE? [y/N]: " << std::flush;
        std::string answer;
        std::getline(std::cin, answer);
        for (auto& c : answer) c = std::tolower((unsigned char)c);
        if (answer != "y" && answer != "yes") {
            cfg.erode = -1;
            console.println("[stabilize] ERODE skipped.");
        }
    }

    console.println("[stabilize] Mode  : " + cfg.mode);
    console.println("[stabilize] Model : " + modelPath);
    console.println("[stabilize] Output: " + outputPath);
    if (cfg.level > 0)
        console.println("[stabilize] Level : " + std::to_string(cfg.level));

    // Read model
    std::vector<std::string> lines;
    {
        std::ifstream mf(modelPath);
        if (!mf.is_open()) { console.error("Cannot open model: " + modelPath); return 1; }
        std::string l;
        while (std::getline(mf, l)) {
            if (!l.empty() && l.back()=='\r') l.pop_back();
            lines.push_back(l);
        }
    }

    // Apply
    if (cfg.mode != "explicit") {
        console.error("Unknown stabilize mode: " + cfg.mode + " (only 'explicit' supported)");
        return 1;
    }
    auto msgs = stab_applyExplicit(lines, cfg);
    for (const auto& m : msgs) console.println(m);

    // Write output
    {
        std::ofstream fout(outputPath);
        if (!fout.is_open()) { console.error("Cannot write: " + outputPath); return 1; }
        for (const auto& l : lines) fout << l << "\n";
    }

    console.println("[stabilize] Done -> " + outputPath);
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
        // strip inline comment
        { size_t h = val.find('#'); if (h != std::string::npos) val = trimYaml(val.substr(0,h)); }
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

    // Remove *CONTROL_DYNAMICS — explicit quasi-static damping not applicable to implicit
    removeAndLog("*CONTROL_DYNAMICS");

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
            lines = impl_removeKeyword(lines, "*CONTROL_IMPLICIT_BUCKLE");
            lines = impl_removeKeyword(lines, "*CONTROL_IMPLICIT_FORMING");
            lines = impl_removeKeyword(lines, "*CONTROL_IMPLICIT_ROTATIONAL_DYNAMICS");
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
            lines = impl_removeKeyword(lines, "*CONTROL_IMPLICIT_BUCKLE");
            lines = impl_removeKeyword(lines, "*CONTROL_IMPLICIT_FORMING");
            lines = impl_removeKeyword(lines, "*CONTROL_IMPLICIT_ROTATIONAL_DYNAMICS");
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
        std::transform(matLower.begin(), matLower.end(), matLower.begin(), [](unsigned char c){ return (char)std::tolower(c); });
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

// ── Contact command ──────────────────────────────────────────────────────────
int runContact(const std::string& yamlFile, ConsoleOutput& console) {
    // 1. Parse YAML
    std::string configDir;
    {
        size_t sep = yamlFile.find_last_of("/\\");
        configDir = (sep != std::string::npos) ? yamlFile.substr(0, sep+1) : "";
    }
    auto resolvePath = [&](const std::string& p) -> std::string {
        if (!configDir.empty() && !p.empty() &&
            p[0]!='/' && p[0]!='\\' && !(p.size()>=2 && p[1]==':') &&
            p.find('/')  == std::string::npos &&
            p.find('\\') == std::string::npos)
            return configDir + "/" + p;
        return p;
    };

    std::ifstream yin(yamlFile);
    if (!yin.is_open()) { console.error("Cannot open YAML: " + yamlFile); return 1; }

    std::string modelFile, outputFile;

    struct ContactAction {
        std::string action;  // analyze/create/convert/modify/remove
        // create fields
        std::string type;
        struct Side {
            int pid = 0;
            std::vector<int> pids;
            bool asSegment = false;
            bool facing = false;   // filter segments to only those facing the other side
        };
        Side slave, master;
        double friction = -1.0;  // -1 = not set (sentinel)
        std::string title;
        // convert/modify/remove fields
        int contactIndex = -1;
        std::string slaveTo, masterTo;  // "segment"
        bool convertFacing = false;     // facing filter for convert action
        // Card 1 extended
        int sboxid = -1, mboxid = -1, spr = -1, mpr = -1;
        // Card 2 extended (-1 = not set sentinel for doubles, -1 for ints)
        double fd = -1, dc = -1, vc = -1, vdc = -1; int penchk = -1; double bt = -1, dt = -1;
        // Card 3
        double sfsa=-1, sfsb=-1, sast=-1, sbst=-1, sfsat=-1, sfsbt=-1, fsf=-1, vsf=-1;
        // Card A
        int soft = -1; double sofscl = -1; int lcidab = -1; double maxpar = -1;
        int sbopt = -1, depth = -1, bsort = -1, frcfrq = -1;
        // Card B
        double penmax = -1; int thkopt = -1, shlthk = -1, snlog = -1;
        int isym = -1, i2d3d = -1; double sldthk = -1, sldstf = -1;
        // Card C
        int igap = -1, ignore_ = -1; double dprfac = -1, dtstif = -1;
        double edgek = -1, flangl = -1; int cid_rcf = -1;
        // Card D
        int q2tri = -1; double dtpchk = -1, sfnbr = -1, fnlscl = -1, dnlscl = -1;
        int tcso = -1, tiedid = -1, shledg = -1;
        // Card E
        int sharec = -1, cparm8 = -1, ipback = -1, srnde = -1;
        double fricsf = -1; int icor = -1, ftorq = -1, region = -1;
        // Card F
        int pstiff = -1, ignroff = -1; double fstol = -1;
        int d2binr = -1, ssftyp = -1, swtpr = -1; double tetfac = -1;
        // Card G
        double shloff = -1;
        // detect fields
        std::string scope;                        // "all" or empty
        std::vector<std::string> includeKeys;     // part name include keywords
        std::vector<std::string> excludeKeys;     // part name exclude keywords
        std::string contactType = "auto";         // contact type preset
        double detectTolerance = 0.1;
        double detectNormalAngle = 45.0;
        bool detectAutoCreate = false;
        std::string titlePrefix;                  // e.g. "Tied" → "Tied_PartA_PartB"
        std::string skipExisting;                 // "tied"/"all"/empty → pair-level skip
        bool subtractExisting = false;            // segment-level subtraction
    };
    std::vector<ContactAction> actions;

    // Simple YAML parser
    {
        std::string line;
        bool inContacts = false;
        int contactsIndent = 0;
        ContactAction curAction;
        bool hasAction = false;
        std::string currentSide;  // "slave" or "master"

        auto flushAction = [&]() {
            if (hasAction) {
                actions.push_back(curAction);
                curAction = ContactAction{};
                hasAction = false;
                currentSide.clear();
            }
        };

        auto parsePidList = [](const std::string& s) -> std::vector<int> {
            std::vector<int> result;
            std::string buf;
            for (char c : s) {
                if (c == '[' || c == ']' || c == ' ') continue;
                if (c == ',') {
                    if (!buf.empty()) { try { result.push_back(std::stoi(buf)); } catch(...){} buf.clear(); }
                } else {
                    buf += c;
                }
            }
            if (!buf.empty()) { try { result.push_back(std::stoi(buf)); } catch(...){} }
            return result;
        };

        while (std::getline(yin, line)) {
            std::string raw = line;
            int indent = 0;
            for (char c : raw) { if (c == ' ') ++indent; else break; }
            std::string t = impl_trim(raw);
            if (t.empty() || t[0] == '#') continue;

            size_t colon = t.find(':');
            if (colon == std::string::npos) continue;
            std::string key = impl_trim(t.substr(0, colon));
            std::string val = impl_trim(t.substr(colon+1));
            // strip inline comment
            { size_t h = val.find('#'); if (h != std::string::npos) val = impl_trim(val.substr(0, h)); }

            // Top-level keys
            if (key == "model" && indent < 4) { modelFile = val; inContacts = false; continue; }
            if (key == "output" && indent < 4) { outputFile = val; inContacts = false; continue; }

            if (key == "contacts" && indent < 4) {
                inContacts = true;
                contactsIndent = indent;
                continue;
            }

            if (!inContacts) continue;

            // Detect new list item: "- action: ..."
            if (t.find("- action") == 0) {
                flushAction();
                size_t ac = t.find(':');
                if (ac != std::string::npos) {
                    curAction.action = impl_trim(t.substr(ac+1));
                    // strip inline comment from action
                    size_t h = curAction.action.find('#');
                    if (h != std::string::npos) curAction.action = impl_trim(curAction.action.substr(0, h));
                }
                hasAction = true;
                currentSide.clear();
                continue;
            }

            if (!hasAction) continue;

            // Sub-keys of current action
            if (key == "type") { curAction.type = val; continue; }
            if (key == "title") { curAction.title = val; continue; }
            if (key == "contact_index") { try { curAction.contactIndex = std::stoi(val); } catch(...){} continue; }
            if (key == "slave_to") { curAction.slaveTo = val; continue; }
            if (key == "master_to") { curAction.masterTo = val; continue; }
            if (key == "facing" && curAction.action == "convert") {
                curAction.convertFacing = (val=="true"||val=="yes"||val=="1"); continue;
            }
            // Card 1
            if (key == "friction") { try { curAction.friction = std::stod(val); } catch(...){} continue; }
            if (key == "sboxid")  { try { curAction.sboxid = std::stoi(val); } catch(...){} continue; }
            if (key == "mboxid")  { try { curAction.mboxid = std::stoi(val); } catch(...){} continue; }
            if (key == "spr")     { try { curAction.spr = std::stoi(val); } catch(...){} continue; }
            if (key == "mpr")     { try { curAction.mpr = std::stoi(val); } catch(...){} continue; }
            // Card 2
            if (key == "fd")      { try { curAction.fd = std::stod(val); } catch(...){} continue; }
            if (key == "dc")      { try { curAction.dc = std::stod(val); } catch(...){} continue; }
            if (key == "vc")      { try { curAction.vc = std::stod(val); } catch(...){} continue; }
            if (key == "vdc")     { try { curAction.vdc = std::stod(val); } catch(...){} continue; }
            if (key == "penchk")  { try { curAction.penchk = std::stoi(val); } catch(...){} continue; }
            if (key == "bt")      { try { curAction.bt = std::stod(val); } catch(...){} continue; }
            if (key == "dt")      { try { curAction.dt = std::stod(val); } catch(...){} continue; }
            // Card 3
            if (key == "sfsa")    { try { curAction.sfsa = std::stod(val); } catch(...){} continue; }
            if (key == "sfsb")    { try { curAction.sfsb = std::stod(val); } catch(...){} continue; }
            if (key == "sast")    { try { curAction.sast = std::stod(val); } catch(...){} continue; }
            if (key == "sbst")    { try { curAction.sbst = std::stod(val); } catch(...){} continue; }
            if (key == "sfsat")   { try { curAction.sfsat = std::stod(val); } catch(...){} continue; }
            if (key == "sfsbt")   { try { curAction.sfsbt = std::stod(val); } catch(...){} continue; }
            if (key == "fsf")     { try { curAction.fsf = std::stod(val); } catch(...){} continue; }
            if (key == "vsf")     { try { curAction.vsf = std::stod(val); } catch(...){} continue; }
            // Card A
            if (key == "soft")    { try { curAction.soft = std::stoi(val); } catch(...){} continue; }
            if (key == "sofscl")  { try { curAction.sofscl = std::stod(val); } catch(...){} continue; }
            if (key == "lcidab")  { try { curAction.lcidab = std::stoi(val); } catch(...){} continue; }
            if (key == "maxpar")  { try { curAction.maxpar = std::stod(val); } catch(...){} continue; }
            if (key == "sbopt")   { try { curAction.sbopt = std::stoi(val); } catch(...){} continue; }
            if (key == "depth")   { try { curAction.depth = std::stoi(val); } catch(...){} continue; }
            if (key == "bsort")   { try { curAction.bsort = std::stoi(val); } catch(...){} continue; }
            if (key == "frcfrq")  { try { curAction.frcfrq = std::stoi(val); } catch(...){} continue; }
            // Card B
            if (key == "penmax")  { try { curAction.penmax = std::stod(val); } catch(...){} continue; }
            if (key == "thkopt")  { try { curAction.thkopt = std::stoi(val); } catch(...){} continue; }
            if (key == "shlthk")  { try { curAction.shlthk = std::stoi(val); } catch(...){} continue; }
            if (key == "snlog")   { try { curAction.snlog = std::stoi(val); } catch(...){} continue; }
            if (key == "isym")    { try { curAction.isym = std::stoi(val); } catch(...){} continue; }
            if (key == "i2d3d")   { try { curAction.i2d3d = std::stoi(val); } catch(...){} continue; }
            if (key == "sldthk")  { try { curAction.sldthk = std::stod(val); } catch(...){} continue; }
            if (key == "sldstf")  { try { curAction.sldstf = std::stod(val); } catch(...){} continue; }
            // Card C
            if (key == "igap")    { try { curAction.igap = std::stoi(val); } catch(...){} continue; }
            if (key == "ignore")  { try { curAction.ignore_ = std::stoi(val); } catch(...){} continue; }
            if (key == "dprfac")  { try { curAction.dprfac = std::stod(val); } catch(...){} continue; }
            if (key == "dtstif")  { try { curAction.dtstif = std::stod(val); } catch(...){} continue; }
            if (key == "edgek")   { try { curAction.edgek = std::stod(val); } catch(...){} continue; }
            if (key == "flangl")  { try { curAction.flangl = std::stod(val); } catch(...){} continue; }
            if (key == "cid_rcf") { try { curAction.cid_rcf = std::stoi(val); } catch(...){} continue; }
            // Card D
            if (key == "q2tri")   { try { curAction.q2tri = std::stoi(val); } catch(...){} continue; }
            if (key == "dtpchk")  { try { curAction.dtpchk = std::stod(val); } catch(...){} continue; }
            if (key == "sfnbr")   { try { curAction.sfnbr = std::stod(val); } catch(...){} continue; }
            if (key == "fnlscl")  { try { curAction.fnlscl = std::stod(val); } catch(...){} continue; }
            if (key == "dnlscl")  { try { curAction.dnlscl = std::stod(val); } catch(...){} continue; }
            if (key == "tcso")    { try { curAction.tcso = std::stoi(val); } catch(...){} continue; }
            if (key == "tiedid")  { try { curAction.tiedid = std::stoi(val); } catch(...){} continue; }
            if (key == "shledg")  { try { curAction.shledg = std::stoi(val); } catch(...){} continue; }
            // Card E
            if (key == "sharec")  { try { curAction.sharec = std::stoi(val); } catch(...){} continue; }
            if (key == "cparm8")  { try { curAction.cparm8 = std::stoi(val); } catch(...){} continue; }
            if (key == "ipback")  { try { curAction.ipback = std::stoi(val); } catch(...){} continue; }
            if (key == "srnde")   { try { curAction.srnde = std::stoi(val); } catch(...){} continue; }
            if (key == "fricsf")  { try { curAction.fricsf = std::stod(val); } catch(...){} continue; }
            if (key == "icor")    { try { curAction.icor = std::stoi(val); } catch(...){} continue; }
            if (key == "ftorq")   { try { curAction.ftorq = std::stoi(val); } catch(...){} continue; }
            if (key == "region")  { try { curAction.region = std::stoi(val); } catch(...){} continue; }
            // Card F
            if (key == "pstiff")  { try { curAction.pstiff = std::stoi(val); } catch(...){} continue; }
            if (key == "ignroff") { try { curAction.ignroff = std::stoi(val); } catch(...){} continue; }
            if (key == "fstol")   { try { curAction.fstol = std::stod(val); } catch(...){} continue; }
            if (key == "d2binr" || key == "2dbinr") { try { curAction.d2binr = std::stoi(val); } catch(...){} continue; }
            if (key == "ssftyp")  { try { curAction.ssftyp = std::stoi(val); } catch(...){} continue; }
            if (key == "swtpr")   { try { curAction.swtpr = std::stoi(val); } catch(...){} continue; }
            if (key == "tetfac")  { try { curAction.tetfac = std::stod(val); } catch(...){} continue; }
            // Card G
            if (key == "shloff")  { try { curAction.shloff = std::stod(val); } catch(...){} continue; }

            // detect fields
            if (key == "scope") { curAction.scope = val; continue; }
            if (key == "contact_type") { curAction.contactType = val; continue; }
            if (key == "tolerance") { try { curAction.detectTolerance = std::stod(val); } catch(...){} continue; }
            if (key == "normal_angle") { try { curAction.detectNormalAngle = std::stod(val); } catch(...){} continue; }
            if (key == "auto_create") { curAction.detectAutoCreate = (val=="true"||val=="yes"||val=="1"); continue; }
            if (key == "title_prefix") { curAction.titlePrefix = val; continue; }
            if (key == "skip_existing") { curAction.skipExisting = val; continue; }
            if (key == "subtract_existing") { curAction.subtractExisting = (val=="true"||val=="yes"||val=="1"); continue; }
            if (key == "include" || key == "exclude") {
                // Parse list: [kw1, kw2, ...] or bare value
                std::vector<std::string>& tgt = (key == "include") ?
                    curAction.includeKeys : curAction.excludeKeys;
                std::string v = val;
                if (!v.empty() && v.front() == '[') v.erase(v.begin());
                if (!v.empty() && v.back() == ']') v.pop_back();
                std::istringstream kss(v);
                std::string kw;
                while (std::getline(kss, kw, ',')) {
                    size_t s = kw.find_first_not_of(" \t");
                    size_t e = kw.find_last_not_of(" \t");
                    if (s != std::string::npos && e != std::string::npos)
                        tgt.push_back(kw.substr(s, e - s + 1));
                }
                continue;
            }

            // slave:/master: can be inline { pid: N } or multiline
            if (key == "slave" || key == "master") {
                currentSide = key;
                ContactAction::Side& side = (key == "slave") ? curAction.slave : curAction.master;
                // Check for inline: { pid: 1, as_segment: true }
                if (val.find('{') != std::string::npos) {
                    // Parse inline map
                    std::string inner = val;
                    size_t br = inner.find('{');
                    if (br != std::string::npos) inner = inner.substr(br+1);
                    br = inner.find('}');
                    if (br != std::string::npos) inner = inner.substr(0, br);
                    // Split by comma (but not inside brackets)
                    std::vector<std::string> pairs;
                    {
                        std::string cur;
                        int bracketDepth = 0;
                        for (char ch : inner) {
                            if (ch == '[') { bracketDepth++; cur += ch; }
                            else if (ch == ']') { bracketDepth--; cur += ch; }
                            else if (ch == ',' && bracketDepth == 0) {
                                pairs.push_back(cur); cur.clear();
                            } else { cur += ch; }
                        }
                        if (!cur.empty()) pairs.push_back(cur);
                    }
                    for (const auto& pr : pairs) {
                        size_t c2 = pr.find(':');
                        if (c2 == std::string::npos) continue;
                        std::string k2 = impl_trim(pr.substr(0, c2));
                        std::string v2 = impl_trim(pr.substr(c2+1));
                        if (k2 == "pid") { try { side.pid = std::stoi(v2); } catch(...){} }
                        else if (k2 == "pids") { side.pids = parsePidList(v2); }
                        else if (k2 == "as_segment") { side.asSegment = (v2=="true"||v2=="yes"||v2=="1"); }
                        else if (k2 == "facing") { side.facing = (v2=="true"||v2=="yes"||v2=="1"); }
                    }
                    currentSide.clear();
                }
                continue;
            }

            // Multiline slave/master sub-keys
            if (!currentSide.empty()) {
                ContactAction::Side& side = (currentSide == "slave") ? curAction.slave : curAction.master;
                if (key == "pid") { try { side.pid = std::stoi(val); } catch(...){} continue; }
                if (key == "pids") { side.pids = parsePidList(val); continue; }
                if (key == "as_segment") { side.asSegment = (val=="true"||val=="yes"||val=="1"); continue; }
                if (key == "facing") { side.facing = (val=="true"||val=="yes"||val=="1"); continue; }
            }
        }
        flushAction();
    }

    if (modelFile.empty()) { console.error("YAML missing 'model' key"); return 1; }
    if (actions.empty()) { console.error("YAML has no contact actions"); return 1; }

    std::string modelPath = resolvePath(modelFile);
    std::string outPath;
    if (!outputFile.empty()) {
        outPath = resolvePath(outputFile);
    }

    // 2. Read model as rawLines
    std::vector<std::string> lines;
    {
        std::ifstream mf(modelPath);
        if (!mf.is_open()) { console.error("Cannot open model: " + modelPath); return 1; }
        std::string ln;
        while (std::getline(mf, ln)) lines.push_back(ln);
    }

    // 3. Optionally load Mesh (for surface extraction)
    bool needMesh = false;
    for (const auto& act : actions) {
        if (act.action == "create" && (act.slave.asSegment || act.master.asSegment)) needMesh = true;
        if (act.action == "convert") needMesh = true;
        if (act.action == "detect") needMesh = true;
    }

    KooRemapper::Mesh mesh;
    if (needMesh) {
        KooRemapper::KFileReader reader;
        try {
            mesh = reader.readFile(modelPath);
        } catch (const std::exception& e) {
            console.error("Cannot parse mesh: " + modelPath + " (" + e.what() + ")");
            return 1;
        }
    }

    // 4. Parse existing contacts and sets
    auto contacts = ct_parseContacts(lines);
    auto sets     = ct_parseSets(lines);
    int nextSetId = ct_findMaxSetId(sets) + 1;

    console.println("[contact] Model: " + modelFile + " (" + std::to_string(lines.size()) + " lines)");
    console.println("[contact] Found " + std::to_string(contacts.size()) + " contacts, " +
                    std::to_string(sets.size()) + " sets");

    // 5. Process actions
    std::vector<std::string> insertBlocks;   // blocks to insert before *END
    std::vector<std::pair<int,int>> removeRanges;  // (start,end) to remove (sorted descending later)
    bool modified = false;
    bool analyzeOnly = true;

    for (size_t ai = 0; ai < actions.size(); ++ai) {
        const auto& act = actions[ai];

        // ── analyze ──
        if (act.action == "analyze") {
            ct_analyze(contacts, sets, mesh, console);
            continue;
        }

        analyzeOnly = false;

        // ── create ──
        if (act.action == "create") {
            std::string ctype = act.type;
            // Normalize type to uppercase with underscores
            for (auto& c : ctype) { if (c == '-') c = '_'; c = static_cast<char>(toupper(static_cast<unsigned char>(c))); }

            int ssid = 0, msid = 0, sstyp = 0, mstyp = 0;

            // Facing filter: when both slave and master have as_segment+facing,
            // use detect algorithm to extract only mutually facing segments
            bool useFacingFilter = (act.slave.asSegment && act.slave.facing &&
                                    act.master.asSegment && act.master.facing &&
                                    act.slave.pid > 0 && act.master.pid > 0);

            if (useFacingFilter) {
                double tol = act.detectTolerance;
                double angle = act.detectNormalAngle;
                auto slaveFacesAll = ct_extractSurface(mesh, act.slave.pid);
                auto masterFacesAll = ct_extractSurface(mesh, act.master.pid);
                if (slaveFacesAll.empty() || masterFacesAll.empty()) {
                    console.warning("[contact] No surface found for facing filter (slave:" +
                        std::to_string(act.slave.pid) + " master:" + std::to_string(act.master.pid) + ")");
                } else {
                    auto pairs = ct_detectContacting(slaveFacesAll, masterFacesAll, mesh,
                        act.slave.pid, act.master.pid, tol, angle);
                    if (pairs.empty()) {
                        console.warning("[contact] No facing segments found between PID " +
                            std::to_string(act.slave.pid) + " and PID " + std::to_string(act.master.pid));
                    } else {
                        // Collect unique facing faces for each side
                        std::set<int> sIdxSet, mIdxSet;
                        for (const auto& p : pairs) { sIdxSet.insert(p.faceA); mIdxSet.insert(p.faceB); }
                        std::vector<std::array<int,4>> sFaces, mFaces;
                        for (int idx : sIdxSet) sFaces.push_back(slaveFacesAll[idx]);
                        for (int idx : mIdxSet) mFaces.push_back(masterFacesAll[idx]);

                        ssid = nextSetId++;
                        insertBlocks.push_back(ct_generateSetSegment(ssid, sFaces,
                            "Slave_PID" + std::to_string(act.slave.pid) + "_facing"));
                        sstyp = 0;
                        msid = nextSetId++;
                        insertBlocks.push_back(ct_generateSetSegment(msid, mFaces,
                            "Master_PID" + std::to_string(act.master.pid) + "_facing"));
                        mstyp = 0;
                        console.println("[contact] Facing filter: " +
                            std::to_string(slaveFacesAll.size()) + " -> " + std::to_string(sFaces.size()) +
                            " slave, " + std::to_string(masterFacesAll.size()) + " -> " +
                            std::to_string(mFaces.size()) + " master segments");
                    }
                }
            } else {
            // Determine slave side
            if (act.slave.asSegment && act.slave.pid > 0) {
                // Extract surface → SET_SEGMENT
                auto faces = ct_extractSurface(mesh, act.slave.pid);
                if (faces.empty()) {
                    console.warning("[contact] No surface found for slave PID " +
                                std::to_string(act.slave.pid));
                } else {
                    ssid = nextSetId++;
                    insertBlocks.push_back(ct_generateSetSegment(ssid, faces,
                        "Slave_PID" + std::to_string(act.slave.pid)));
                    sstyp = 0;
                    console.println("[contact] Created SET_SEGMENT " + std::to_string(ssid) +
                                  " (" + std::to_string(faces.size()) + " faces) for slave PID " +
                                  std::to_string(act.slave.pid));
                }
            } else if (!act.slave.pids.empty()) {
                // Multiple PIDs → SET_PART
                ssid = nextSetId++;
                insertBlocks.push_back(ct_generateSetPart(ssid, act.slave.pids, "Slave_parts"));
                sstyp = 2;
                console.println("[contact] Created SET_PART " + std::to_string(ssid) +
                              " (" + std::to_string(act.slave.pids.size()) + " parts) for slave");
            } else if (act.slave.pid > 0) {
                // Single PID → direct SSTYP=3
                ssid = act.slave.pid;
                sstyp = 3;
            }

            // Determine master side (similar logic)
            if (act.master.asSegment && act.master.pid > 0) {
                auto faces = ct_extractSurface(mesh, act.master.pid);
                if (faces.empty()) {
                    console.warning("[contact] No surface found for master PID " +
                                std::to_string(act.master.pid));
                } else {
                    msid = nextSetId++;
                    insertBlocks.push_back(ct_generateSetSegment(msid, faces,
                        "Master_PID" + std::to_string(act.master.pid)));
                    mstyp = 0;
                    console.println("[contact] Created SET_SEGMENT " + std::to_string(msid) +
                                  " (" + std::to_string(faces.size()) + " faces) for master PID " +
                                  std::to_string(act.master.pid));
                }
            } else if (!act.master.pids.empty()) {
                msid = nextSetId++;
                insertBlocks.push_back(ct_generateSetPart(msid, act.master.pids, "Master_parts"));
                mstyp = 2;
                console.println("[contact] Created SET_PART " + std::to_string(msid) +
                              " (" + std::to_string(act.master.pids.size()) + " parts) for master");
            } else if (act.master.pid > 0) {
                msid = act.master.pid;
                mstyp = 3;
            }
            } // end else (not useFacingFilter)

            // For single surface types, master is unused
            bool isSingle = (ctype.find("SINGLE_SURFACE") != std::string::npos);
            if (isSingle) {
                // Slave only — if pids given, use SET_PART
                if (!act.slave.pids.empty() && sstyp != 2) {
                    ssid = nextSetId++;
                    insertBlocks.push_back(ct_generateSetPart(ssid, act.slave.pids, "SingleSurf_parts"));
                    sstyp = 2;
                }
                msid = 0; mstyp = 0;
            }

            // Build ContactDef from action
            ContactDef newDef;
            newDef.type = ctype;
            newDef.ssid = ssid; newDef.msid = msid;
            newDef.sstyp = sstyp; newDef.mstyp = mstyp;
            newDef.title = act.title.empty() ? ("Contact_" + std::to_string(ai)) : act.title;
            // Card 1 optional
            if (act.sboxid >= 0) newDef.sboxid = act.sboxid;
            if (act.mboxid >= 0) newDef.mboxid = act.mboxid;
            if (act.spr >= 0) newDef.spr = act.spr;
            if (act.mpr >= 0) newDef.mpr = act.mpr;
            // Card 2
            newDef.fs = (act.friction >= 0) ? act.friction : 0.0;
            if (act.fd >= 0) newDef.fd = act.fd;
            if (act.dc >= 0) newDef.dc = act.dc;
            if (act.vc >= 0) newDef.vc = act.vc;
            if (act.vdc >= 0) newDef.vdc = act.vdc;
            if (act.penchk >= 0) newDef.penchk = act.penchk;
            if (act.bt >= 0) newDef.bt = act.bt;
            if (act.dt >= 0) newDef.dt = act.dt;
            // Card 3
            if (act.sfsa >= 0) newDef.sfsa = act.sfsa;
            if (act.sfsb >= 0) newDef.sfsb = act.sfsb;
            if (act.sast >= 0) newDef.sast = act.sast;
            if (act.sbst >= 0) newDef.sbst = act.sbst;
            if (act.sfsat >= 0) newDef.sfsat = act.sfsat;
            if (act.sfsbt >= 0) newDef.sfsbt = act.sfsbt;
            if (act.fsf >= 0) newDef.fsf = act.fsf;
            if (act.vsf >= 0) newDef.vsf = act.vsf;
            // Card A — any field set → hasCardA
            if (act.soft>=0||act.sofscl>=0||act.lcidab>=0||act.maxpar>=0||
                act.sbopt>=0||act.depth>=0||act.bsort>=0||act.frcfrq>=0) {
                newDef.hasCardA = true;
                if (act.soft >= 0) newDef.soft = act.soft;
                if (act.sofscl >= 0) newDef.sofscl = act.sofscl;
                if (act.lcidab >= 0) newDef.lcidab = act.lcidab;
                if (act.maxpar >= 0) newDef.maxpar = act.maxpar;
                if (act.sbopt >= 0) newDef.sbopt = act.sbopt;
                if (act.depth >= 0) newDef.depth = act.depth;
                if (act.bsort >= 0) newDef.bsort = act.bsort;
                if (act.frcfrq >= 0) newDef.frcfrq = act.frcfrq;
            }
            // Card B
            if (act.penmax>=0||act.thkopt>=0||act.shlthk>=0||act.snlog>=0||
                act.isym>=0||act.i2d3d>=0||act.sldthk>=0||act.sldstf>=0) {
                newDef.hasCardB = true; newDef.hasCardA = true;
                if (act.penmax >= 0) newDef.penmax = act.penmax;
                if (act.thkopt >= 0) newDef.thkopt = act.thkopt;
                if (act.shlthk >= 0) newDef.shlthk = act.shlthk;
                if (act.snlog >= 0) newDef.snlog = act.snlog;
                if (act.isym >= 0) newDef.isym = act.isym;
                if (act.i2d3d >= 0) newDef.i2d3d = act.i2d3d;
                if (act.sldthk >= 0) newDef.sldthk = act.sldthk;
                if (act.sldstf >= 0) newDef.sldstf = act.sldstf;
            }
            // Card C
            if (act.igap>=0||act.ignore_>=0||act.dprfac>=0||act.dtstif>=0||
                act.edgek>=0||act.flangl>=0||act.cid_rcf>=0) {
                newDef.hasCardC = true; newDef.hasCardB = true; newDef.hasCardA = true;
                if (act.igap >= 0) newDef.igap = act.igap;
                if (act.ignore_ >= 0) newDef.ignore_ = act.ignore_;
                if (act.dprfac >= 0) newDef.dprfac = act.dprfac;
                if (act.dtstif >= 0) newDef.dtstif = act.dtstif;
                if (act.edgek >= 0) newDef.edgek = act.edgek;
                if (act.flangl >= 0) newDef.flangl = act.flangl;
                if (act.cid_rcf >= 0) newDef.cid_rcf = act.cid_rcf;
            }
            // Card D
            if (act.q2tri>=0||act.dtpchk>=0||act.sfnbr>=0||act.fnlscl>=0||
                act.dnlscl>=0||act.tcso>=0||act.tiedid>=0||act.shledg>=0) {
                newDef.hasCardD = true; newDef.hasCardC = true;
                newDef.hasCardB = true; newDef.hasCardA = true;
                if (act.q2tri >= 0) newDef.q2tri = act.q2tri;
                if (act.dtpchk >= 0) newDef.dtpchk = act.dtpchk;
                if (act.sfnbr >= 0) newDef.sfnbr = act.sfnbr;
                if (act.fnlscl >= 0) newDef.fnlscl = act.fnlscl;
                if (act.dnlscl >= 0) newDef.dnlscl = act.dnlscl;
                if (act.tcso >= 0) newDef.tcso = act.tcso;
                if (act.tiedid >= 0) newDef.tiedid = act.tiedid;
                if (act.shledg >= 0) newDef.shledg = act.shledg;
            }
            // Card E
            if (act.sharec>=0||act.cparm8>=0||act.ipback>=0||act.srnde>=0||
                act.fricsf>=0||act.icor>=0||act.ftorq>=0||act.region>=0) {
                newDef.hasCardE = true; newDef.hasCardD = true;
                newDef.hasCardC = true; newDef.hasCardB = true; newDef.hasCardA = true;
                if (act.sharec >= 0) newDef.sharec = act.sharec;
                if (act.cparm8 >= 0) newDef.cparm8 = act.cparm8;
                if (act.ipback >= 0) newDef.ipback = act.ipback;
                if (act.srnde >= 0) newDef.srnde = act.srnde;
                if (act.fricsf >= 0) newDef.fricsf = act.fricsf;
                if (act.icor >= 0) newDef.icor = act.icor;
                if (act.ftorq >= 0) newDef.ftorq = act.ftorq;
                if (act.region >= 0) newDef.region = act.region;
            }
            // Card F
            if (act.pstiff>=0||act.ignroff>=0||act.fstol>=0||
                act.d2binr>=0||act.ssftyp>=0||act.swtpr>=0||act.tetfac>=0) {
                newDef.hasCardF = true; newDef.hasCardE = true; newDef.hasCardD = true;
                newDef.hasCardC = true; newDef.hasCardB = true; newDef.hasCardA = true;
                if (act.pstiff >= 0) newDef.pstiff = act.pstiff;
                if (act.ignroff >= 0) newDef.ignroff = act.ignroff;
                if (act.fstol >= 0) newDef.fstol = act.fstol;
                if (act.d2binr >= 0) newDef.d2binr = act.d2binr;
                if (act.ssftyp >= 0) newDef.ssftyp = act.ssftyp;
                if (act.swtpr >= 0) newDef.swtpr = act.swtpr;
                if (act.tetfac >= 0) newDef.tetfac = act.tetfac;
            }
            // Card G
            if (act.shloff >= 0) {
                newDef.hasCardG = true; newDef.hasCardF = true; newDef.hasCardE = true;
                newDef.hasCardD = true; newDef.hasCardC = true;
                newDef.hasCardB = true; newDef.hasCardA = true;
                newDef.shloff = act.shloff;
            }

            insertBlocks.push_back(ct_generateContact(newDef));
            console.println("[contact] Created *CONTACT_" + ctype +
                          (act.title.empty() ? "" : " (" + act.title + ")"));
            modified = true;
            continue;
        }

        // ── convert ──
        if (act.action == "convert") {
            if (act.contactIndex < 0 || act.contactIndex >= (int)contacts.size()) {
                console.error("[contact] Invalid contact_index: " + std::to_string(act.contactIndex));
                return 1;
            }
            auto& ct = contacts[act.contactIndex];

            // Helper: collect face list from a contact side.
            // Handles sstyp=3 (direct PID), sstyp=2 (SET_PART), sstyp=0 (SET_SEGMENT).
            auto collectFaces = [&](int sid, int styp) -> std::vector<std::array<int,4>> {
                if (styp == 3) return ct_extractSurface(mesh, sid);
                if (styp == 2) {
                    for (const auto& s : sets)
                        if (s.type == "PART" && s.id == sid) {
                            std::vector<std::array<int,4>> result;
                            for (int pid : s.ids) {
                                auto f = ct_extractSurface(mesh, pid);
                                result.insert(result.end(), f.begin(), f.end());
                            }
                            return result;
                        }
                }
                if (styp == 0) {
                    for (const auto& s : sets)
                        if (s.type == "SEGMENT" && s.id == sid)
                            return s.segments;
                }
                return {};
            };

            // Facing filter: detect only mutually facing segments
            bool convertBothSegment = (act.slaveTo == "segment" && act.masterTo == "segment");
            if (act.convertFacing && convertBothSegment) {
                double tol = act.detectTolerance;
                double angle = act.detectNormalAngle;
                auto slaveFacesAll = collectFaces(ct.ssid, ct.sstyp);
                auto masterFacesAll = collectFaces(ct.msid, ct.mstyp);
                if (slaveFacesAll.empty() || masterFacesAll.empty()) {
                    console.warning("[contact] No faces for facing filter (contact [" +
                        std::to_string(act.contactIndex) + "] sstyp=" +
                        std::to_string(ct.sstyp) + " mstyp=" + std::to_string(ct.mstyp) + ")");
                } else {
                    // Representative PIDs (0 for SET_SEGMENT; only used for tagging)
                    int sPid = (ct.sstyp == 3) ? ct.ssid : 0;
                    int mPid = (ct.mstyp == 3) ? ct.msid : 1;
                    auto pairs = ct_detectContacting(slaveFacesAll, masterFacesAll, mesh,
                        sPid, mPid, tol, angle);
                    if (pairs.empty()) {
                        console.warning("[contact] No facing segments found for contact [" +
                            std::to_string(act.contactIndex) + "]");
                    } else {
                        std::set<int> sIdxSet, mIdxSet;
                        for (const auto& p : pairs) { sIdxSet.insert(p.faceA); mIdxSet.insert(p.faceB); }
                        std::vector<std::array<int,4>> sFaces, mFaces;
                        for (int idx : sIdxSet) sFaces.push_back(slaveFacesAll[idx]);
                        for (int idx : mIdxSet) mFaces.push_back(masterFacesAll[idx]);

                        int newSsid = nextSetId++;
                        insertBlocks.push_back(ct_generateSetSegment(newSsid, sFaces,
                            "Slave_facing"));
                        int newMsid = nextSetId++;
                        insertBlocks.push_back(ct_generateSetSegment(newMsid, mFaces,
                            "Master_facing"));
                        ct_modifyContactCard1(lines, ct, newSsid, newMsid, 0, 0);
                        console.println("[contact] [" + std::to_string(act.contactIndex) +
                            "] Facing filter: slave " + std::to_string(slaveFacesAll.size()) +
                            " -> " + std::to_string(sFaces.size()) +
                            ", master " + std::to_string(masterFacesAll.size()) +
                            " -> " + std::to_string(mFaces.size()) + " segments");
                        ct.ssid = newSsid; ct.sstyp = 0;
                        ct.msid = newMsid; ct.mstyp = 0;
                        modified = true;
                    }
                }
                continue;
            }

            // Convert slave to segment
            if (act.slaveTo == "segment" && ct.sstyp == 3) {
                auto faces = ct_extractSurface(mesh, ct.ssid);
                if (faces.empty()) {
                    console.warning("[contact] No surface for slave PID " + std::to_string(ct.ssid));
                } else {
                    int newSid = nextSetId++;
                    insertBlocks.push_back(ct_generateSetSegment(newSid, faces,
                        "Slave_PID" + std::to_string(ct.ssid)));
                    ct_modifyContactCard1(lines, ct, newSid, ct.msid, 0, ct.mstyp);
                    console.println("[contact] [" + std::to_string(act.contactIndex) +
                                  "] Slave PID " + std::to_string(ct.ssid) +
                                  " -> SET_SEGMENT " + std::to_string(newSid) +
                                  " (" + std::to_string(faces.size()) + " faces)");
                    ct.ssid = newSid;
                    ct.sstyp = 0;
                    modified = true;
                }
            } else if (act.slaveTo == "segment" && ct.sstyp == 2) {
                // Part set → expand to segment
                // Find the set and get PIDs
                for (const auto& s : sets) {
                    if (s.type == "PART" && s.id == ct.ssid) {
                        std::vector<std::array<int,4>> allFaces;
                        for (int pid : s.ids) {
                            auto faces = ct_extractSurface(mesh, pid);
                            allFaces.insert(allFaces.end(), faces.begin(), faces.end());
                        }
                        if (!allFaces.empty()) {
                            int newSid = nextSetId++;
                            insertBlocks.push_back(ct_generateSetSegment(newSid, allFaces,
                                "Slave_expanded"));
                            ct_modifyContactCard1(lines, ct, newSid, ct.msid, 0, ct.mstyp);
                            console.println("[contact] [" + std::to_string(act.contactIndex) +
                                          "] Slave SET_PART " + std::to_string(ct.ssid) +
                                          " -> SET_SEGMENT " + std::to_string(newSid) +
                                          " (" + std::to_string(allFaces.size()) + " faces)");
                            ct.ssid = newSid;
                            ct.sstyp = 0;
                            modified = true;
                        }
                        break;
                    }
                }
            }

            // Convert master to segment
            if (act.masterTo == "segment" && ct.mstyp == 3) {
                auto faces = ct_extractSurface(mesh, ct.msid);
                if (faces.empty()) {
                    console.warning("[contact] No surface for master PID " + std::to_string(ct.msid));
                } else {
                    int newSid = nextSetId++;
                    insertBlocks.push_back(ct_generateSetSegment(newSid, faces,
                        "Master_PID" + std::to_string(ct.msid)));
                    ct_modifyContactCard1(lines, ct, ct.ssid, newSid, ct.sstyp, 0);
                    console.println("[contact] [" + std::to_string(act.contactIndex) +
                                  "] Master PID " + std::to_string(ct.msid) +
                                  " -> SET_SEGMENT " + std::to_string(newSid) +
                                  " (" + std::to_string(faces.size()) + " faces)");
                    ct.msid = newSid;
                    ct.mstyp = 0;
                    modified = true;
                }
            } else if (act.masterTo == "segment" && ct.mstyp == 2) {
                for (const auto& s : sets) {
                    if (s.type == "PART" && s.id == ct.msid) {
                        std::vector<std::array<int,4>> allFaces;
                        for (int pid : s.ids) {
                            auto faces = ct_extractSurface(mesh, pid);
                            allFaces.insert(allFaces.end(), faces.begin(), faces.end());
                        }
                        if (!allFaces.empty()) {
                            int newSid = nextSetId++;
                            insertBlocks.push_back(ct_generateSetSegment(newSid, allFaces,
                                "Master_expanded"));
                            ct_modifyContactCard1(lines, ct, ct.ssid, newSid, ct.sstyp, 0);
                            console.println("[contact] [" + std::to_string(act.contactIndex) +
                                          "] Master SET_PART " + std::to_string(ct.msid) +
                                          " -> SET_SEGMENT " + std::to_string(newSid) +
                                          " (" + std::to_string(allFaces.size()) + " faces)");
                            ct.msid = newSid;
                            ct.mstyp = 0;
                            modified = true;
                        }
                        break;
                    }
                }
            }
            continue;
        }

        // ── modify ──
        if (act.action == "modify") {
            if (act.contactIndex < 0 || act.contactIndex >= (int)contacts.size()) {
                console.error("[contact] Invalid contact_index: " + std::to_string(act.contactIndex));
                return 1;
            }
            auto& ct = contacts[act.contactIndex];
            std::string modFields;

            // Card 1 modifications
            if (act.sboxid >= 0 || act.mboxid >= 0 || act.spr >= 0 || act.mpr >= 0) {
                // Full Card 1 rewrite via ct_modifyContactCard1 doesn't cover these,
                // so use impl_setField for extended fields
                // For now, reuse ct_modifyContactCard1 for ssid/msid/sstyp/mstyp: skip (no change)
            }

            // Card 2 modifications (FS + extended)
            if (act.friction >= 0) { ct_modifyContactFs(lines, ct, act.friction); ct.fs = act.friction; }
            // For other Card 2 fields, we need to modify in-place too
            {
                bool card2Modified = false;
                bool titleSkipped2 = !ct.hasTitle;
                int cn2 = 0;
                for (int i = ct.startLine + 1; i < ct.endLine; ++i) {
                    std::string dtr = impl_trim(lines[i]);
                    if (dtr.empty() || dtr[0] == '$') continue;
                    if (!titleSkipped2) { titleSkipped2 = true; continue; }
                    if (cn2 == 1) {
                        // Card 2 line
                        char buf[20];
                        if (act.fd >= 0)     { snprintf(buf,sizeof(buf),"%10.2f",act.fd);     lines[i]=impl_setField(lines[i],10,10,buf); ct.fd=act.fd; card2Modified=true; }
                        if (act.dc >= 0)     { snprintf(buf,sizeof(buf),"%10.2f",act.dc);     lines[i]=impl_setField(lines[i],20,10,buf); ct.dc=act.dc; card2Modified=true; }
                        if (act.vc >= 0)     { snprintf(buf,sizeof(buf),"%10.2f",act.vc);     lines[i]=impl_setField(lines[i],30,10,buf); ct.vc=act.vc; card2Modified=true; }
                        if (act.vdc >= 0)    { snprintf(buf,sizeof(buf),"%10.2f",act.vdc);    lines[i]=impl_setField(lines[i],40,10,buf); ct.vdc=act.vdc; card2Modified=true; }
                        if (act.penchk >= 0) { lines[i]=impl_setField(lines[i],50,10,std::to_string(act.penchk)); ct.penchk=act.penchk; card2Modified=true; }
                        if (act.bt >= 0)     { snprintf(buf,sizeof(buf),"%10.2f",act.bt);     lines[i]=impl_setField(lines[i],60,10,buf); ct.bt=act.bt; card2Modified=true; }
                        if (act.dt >= 0)     { snprintf(buf,sizeof(buf),"%10.3E",act.dt);     lines[i]=impl_setField(lines[i],70,10,buf); ct.dt=act.dt; card2Modified=true; }
                        break;
                    }
                    cn2++;
                }
                if (card2Modified) {
                    modFields += " Card2";
                } else {
                    bool card2Requested = (act.fd>=0||act.dc>=0||act.vc>=0||act.vdc>=0||
                                           act.penchk>=0||act.bt>=0||act.dt>=0);
                    if (card2Requested)
                        console.warning("[contact] [" + std::to_string(act.contactIndex) +
                            "] Card2 not found in file — add it explicitly or the contact has only Card1");
                }
            }

            // Card 3 modifications
            {
                bool card3Modified = false;
                bool titleSkipped3 = !ct.hasTitle;
                int cn3 = 0;
                for (int i = ct.startLine + 1; i < ct.endLine; ++i) {
                    std::string dtr = impl_trim(lines[i]);
                    if (dtr.empty() || dtr[0] == '$') continue;
                    if (!titleSkipped3) { titleSkipped3 = true; continue; }
                    if (cn3 == 2) {
                        // Card 3 line
                        char buf[20];
                        if (act.sfsa >= 0)  { snprintf(buf,sizeof(buf),"%10.2f",act.sfsa);  lines[i]=impl_setField(lines[i],0,10,buf); ct.sfsa=act.sfsa; card3Modified=true; }
                        if (act.sfsb >= 0)  { snprintf(buf,sizeof(buf),"%10.2f",act.sfsb);  lines[i]=impl_setField(lines[i],10,10,buf); ct.sfsb=act.sfsb; card3Modified=true; }
                        if (act.sast >= 0)  { snprintf(buf,sizeof(buf),"%10.2f",act.sast);  lines[i]=impl_setField(lines[i],20,10,buf); ct.sast=act.sast; card3Modified=true; }
                        if (act.sbst >= 0)  { snprintf(buf,sizeof(buf),"%10.2f",act.sbst);  lines[i]=impl_setField(lines[i],30,10,buf); ct.sbst=act.sbst; card3Modified=true; }
                        if (act.sfsat >= 0) { snprintf(buf,sizeof(buf),"%10.2f",act.sfsat); lines[i]=impl_setField(lines[i],40,10,buf); ct.sfsat=act.sfsat; card3Modified=true; }
                        if (act.sfsbt >= 0) { snprintf(buf,sizeof(buf),"%10.2f",act.sfsbt); lines[i]=impl_setField(lines[i],50,10,buf); ct.sfsbt=act.sfsbt; card3Modified=true; }
                        if (act.fsf >= 0)   { snprintf(buf,sizeof(buf),"%10.2f",act.fsf);   lines[i]=impl_setField(lines[i],60,10,buf); ct.fsf=act.fsf; card3Modified=true; }
                        if (act.vsf >= 0)   { snprintf(buf,sizeof(buf),"%10.2f",act.vsf);   lines[i]=impl_setField(lines[i],70,10,buf); ct.vsf=act.vsf; card3Modified=true; }
                        break;
                    }
                    cn3++;
                }
                if (card3Modified) {
                    modFields += " Card3";
                } else {
                    bool card3Requested = (act.sfsa>=0||act.sfsb>=0||act.sast>=0||act.sbst>=0||
                                           act.sfsat>=0||act.sfsbt>=0||act.fsf>=0||act.vsf>=0);
                    if (card3Requested)
                        console.warning("[contact] [" + std::to_string(act.contactIndex) +
                            "] Card3 not found in file — contact may only have Card1/Card2");
                }
            }

            // Optional Cards A~G: merge YAML values into existing ContactDef, then replace
            bool anyOptional = (act.soft>=0||act.sofscl>=0||act.lcidab>=0||act.maxpar>=0||
                act.sbopt>=0||act.depth>=0||act.bsort>=0||act.frcfrq>=0||
                act.penmax>=0||act.thkopt>=0||act.shlthk>=0||act.snlog>=0||
                act.isym>=0||act.i2d3d>=0||act.sldthk>=0||act.sldstf>=0||
                act.igap>=0||act.ignore_>=0||act.dprfac>=0||act.dtstif>=0||
                act.edgek>=0||act.flangl>=0||act.cid_rcf>=0||
                act.q2tri>=0||act.dtpchk>=0||act.sfnbr>=0||act.fnlscl>=0||
                act.dnlscl>=0||act.tcso>=0||act.tiedid>=0||act.shledg>=0||
                act.sharec>=0||act.cparm8>=0||act.ipback>=0||act.srnde>=0||
                act.fricsf>=0||act.icor>=0||act.ftorq>=0||act.region>=0||
                act.pstiff>=0||act.ignroff>=0||act.fstol>=0||
                act.d2binr>=0||act.ssftyp>=0||act.swtpr>=0||act.tetfac>=0||
                act.shloff>=0);

            if (anyOptional) {
                // Start from existing parsed values
                ContactDef merged = ct;
                // Card A
                if (act.soft>=0||act.sofscl>=0||act.lcidab>=0||act.maxpar>=0||
                    act.sbopt>=0||act.depth>=0||act.bsort>=0||act.frcfrq>=0) {
                    merged.hasCardA = true;
                    if (act.soft >= 0) merged.soft = act.soft;
                    if (act.sofscl >= 0) merged.sofscl = act.sofscl;
                    if (act.lcidab >= 0) merged.lcidab = act.lcidab;
                    if (act.maxpar >= 0) merged.maxpar = act.maxpar;
                    if (act.sbopt >= 0) merged.sbopt = act.sbopt;
                    if (act.depth >= 0) merged.depth = act.depth;
                    if (act.bsort >= 0) merged.bsort = act.bsort;
                    if (act.frcfrq >= 0) merged.frcfrq = act.frcfrq;
                }
                // Card B
                if (act.penmax>=0||act.thkopt>=0||act.shlthk>=0||act.snlog>=0||
                    act.isym>=0||act.i2d3d>=0||act.sldthk>=0||act.sldstf>=0) {
                    merged.hasCardB = true; merged.hasCardA = true;
                    if (act.penmax >= 0) merged.penmax = act.penmax;
                    if (act.thkopt >= 0) merged.thkopt = act.thkopt;
                    if (act.shlthk >= 0) merged.shlthk = act.shlthk;
                    if (act.snlog >= 0) merged.snlog = act.snlog;
                    if (act.isym >= 0) merged.isym = act.isym;
                    if (act.i2d3d >= 0) merged.i2d3d = act.i2d3d;
                    if (act.sldthk >= 0) merged.sldthk = act.sldthk;
                    if (act.sldstf >= 0) merged.sldstf = act.sldstf;
                }
                // Card C
                if (act.igap>=0||act.ignore_>=0||act.dprfac>=0||act.dtstif>=0||
                    act.edgek>=0||act.flangl>=0||act.cid_rcf>=0) {
                    merged.hasCardC = true; merged.hasCardB = true; merged.hasCardA = true;
                    if (act.igap >= 0) merged.igap = act.igap;
                    if (act.ignore_ >= 0) merged.ignore_ = act.ignore_;
                    if (act.dprfac >= 0) merged.dprfac = act.dprfac;
                    if (act.dtstif >= 0) merged.dtstif = act.dtstif;
                    if (act.edgek >= 0) merged.edgek = act.edgek;
                    if (act.flangl >= 0) merged.flangl = act.flangl;
                    if (act.cid_rcf >= 0) merged.cid_rcf = act.cid_rcf;
                }
                // Card D~G: same pattern
                if (act.q2tri>=0||act.shledg>=0||act.tcso>=0||act.tiedid>=0||
                    act.dtpchk>=0||act.sfnbr>=0||act.fnlscl>=0||act.dnlscl>=0) {
                    merged.hasCardD = true; merged.hasCardC = true;
                    merged.hasCardB = true; merged.hasCardA = true;
                    if (act.q2tri >= 0) merged.q2tri = act.q2tri;
                    if (act.dtpchk >= 0) merged.dtpchk = act.dtpchk;
                    if (act.sfnbr >= 0) merged.sfnbr = act.sfnbr;
                    if (act.fnlscl >= 0) merged.fnlscl = act.fnlscl;
                    if (act.dnlscl >= 0) merged.dnlscl = act.dnlscl;
                    if (act.tcso >= 0) merged.tcso = act.tcso;
                    if (act.tiedid >= 0) merged.tiedid = act.tiedid;
                    if (act.shledg >= 0) merged.shledg = act.shledg;
                }
                if (act.sharec>=0||act.cparm8>=0||act.ipback>=0||act.srnde>=0||
                    act.fricsf>=0||act.icor>=0||act.ftorq>=0||act.region>=0) {
                    merged.hasCardE = true; merged.hasCardD = true;
                    merged.hasCardC = true; merged.hasCardB = true; merged.hasCardA = true;
                    if (act.sharec >= 0) merged.sharec = act.sharec;
                    if (act.cparm8 >= 0) merged.cparm8 = act.cparm8;
                    if (act.ipback >= 0) merged.ipback = act.ipback;
                    if (act.srnde >= 0) merged.srnde = act.srnde;
                    if (act.fricsf >= 0) merged.fricsf = act.fricsf;
                    if (act.icor >= 0) merged.icor = act.icor;
                    if (act.ftorq >= 0) merged.ftorq = act.ftorq;
                    if (act.region >= 0) merged.region = act.region;
                }
                if (act.pstiff>=0||act.ignroff>=0||act.fstol>=0||
                    act.d2binr>=0||act.ssftyp>=0||act.swtpr>=0||act.tetfac>=0) {
                    merged.hasCardF = true; merged.hasCardE = true; merged.hasCardD = true;
                    merged.hasCardC = true; merged.hasCardB = true; merged.hasCardA = true;
                    if (act.pstiff >= 0) merged.pstiff = act.pstiff;
                    if (act.ignroff >= 0) merged.ignroff = act.ignroff;
                    if (act.fstol >= 0) merged.fstol = act.fstol;
                    if (act.d2binr >= 0) merged.d2binr = act.d2binr;
                    if (act.ssftyp >= 0) merged.ssftyp = act.ssftyp;
                    if (act.swtpr >= 0) merged.swtpr = act.swtpr;
                    if (act.tetfac >= 0) merged.tetfac = act.tetfac;
                }
                if (act.shloff >= 0) {
                    merged.hasCardG = true; merged.hasCardF = true; merged.hasCardE = true;
                    merged.hasCardD = true; merged.hasCardC = true;
                    merged.hasCardB = true; merged.hasCardA = true;
                    merged.shloff = act.shloff;
                }

                ct_modifyOptionalCards(lines, ct, merged);
                modFields += " OptCards";
                // Re-parse since line numbers shifted
                contacts = ct_parseContacts(lines);
                sets = ct_parseSets(lines);
            }

            if (act.friction >= 0) modFields += " FS=" + std::to_string(act.friction);
            console.println("[contact] [" + std::to_string(act.contactIndex) +
                          "] Modified:" + modFields);
            modified = true;
            continue;
        }

        // ── remove ──
        if (act.action == "remove") {
            if (act.contactIndex < 0 || act.contactIndex >= (int)contacts.size()) {
                console.error("[contact] Invalid contact_index: " + std::to_string(act.contactIndex));
                return 1;
            }
            auto& ct = contacts[act.contactIndex];
            console.println("[contact] Removing [" + std::to_string(act.contactIndex) +
                          "] " + ct.fullKeyword);
            removeRanges.push_back({ct.startLine, ct.endLine});
            modified = true;
            continue;
        }

        // ── detect ──
        if (act.action == "detect") {
            analyzeOnly = false;
            double tol = act.detectTolerance;
            double nAngle = act.detectNormalAngle;
            auto preset = ct_getPreset(act.contactType);
            std::string prefix = act.titlePrefix.empty() ? "Auto" : act.titlePrefix;

            bool autoMode = (act.scope == "all" || !act.includeKeys.empty());

            if (autoMode) {
                // --- Automatic mode: scope/include/exclude ---
                auto sel = ct_selectParts(mesh, act.scope, act.includeKeys, act.excludeKeys);
                if (sel.targetPids.empty()) {
                    console.warning("[contact] detect: no target parts matched");
                    continue;
                }

                int excludeCount = (int)mesh.getParts().size() -
                    (int)std::set<int>(sel.counterPids.begin(), sel.counterPids.end()).size();
                console.println("[contact] Part selection: " +
                    std::to_string(sel.targetPids.size()) + " target, " +
                    std::to_string(sel.counterPids.size()) + " counter" +
                    (excludeCount > 0 ? " (" + std::to_string(excludeCount) + " excluded)" : ""));

                // Extract surfaces for all relevant PIDs
                std::set<int> allPids(sel.targetPids.begin(), sel.targetPids.end());
                allPids.insert(sel.counterPids.begin(), sel.counterPids.end());
                auto surfMap = ct_extractAllSurfaces(mesh,
                    std::vector<int>(allPids.begin(), allPids.end()));

                int totalFaces = 0;
                for (const auto& [pid, f] : surfMap) totalFaces += (int)f.size();
                console.println("[contact] Extracted surfaces: " +
                    std::to_string(totalFaces) + " total faces");

                // Run all-pairs detection
                auto pairResults = ct_detectAllPairs(surfMap, sel.targetPids,
                    sel.counterPids, mesh, tol, nAngle);

                if (pairResults.empty()) {
                    console.println("[contact] No contacting pairs found");
                    continue;
                }

                console.println("[contact] Detected " +
                    std::to_string(pairResults.size()) + " contacting pair(s):");

                int createdContacts = 0;
                int skippedPairs = 0;
                int subtractedPairs = 0;
                for (const auto& pr : pairResults) {
                    // Get part names
                    std::string nameA, nameB;
                    auto itA = mesh.getParts().find(pr.pidA);
                    auto itB = mesh.getParts().find(pr.pidB);
                    if (itA != mesh.getParts().end()) nameA = itA->second.name;
                    if (itB != mesh.getParts().end()) nameB = itB->second.name;
                    if (nameA.empty()) nameA = "PID" + std::to_string(pr.pidA);
                    if (nameB.empty()) nameB = "PID" + std::to_string(pr.pidB);

                    // skip_existing: skip this pair if existing contact covers it
                    if (!act.skipExisting.empty()) {
                        if (ct_pairHasExisting(pr.pidA, pr.pidB, contacts, sets, act.skipExisting)) {
                            console.println("  PID " + std::to_string(pr.pidA) +
                                " (" + nameA + ") <-> PID " + std::to_string(pr.pidB) +
                                " (" + nameB + "): skipped (existing " + act.skipExisting + ")");
                            skippedPairs++;
                            continue;
                        }
                    }

                    // Determine final face lists (possibly with subtraction)
                    auto facesA = pr.contactFacesA;
                    auto facesB = pr.contactFacesB;

                    // subtract_existing: remove tied segments from detected faces
                    if (act.subtractExisting) {
                        auto [tiedA, tiedB] = ct_getExistingTiedSegments(
                            pr.pidA, pr.pidB, contacts, sets, mesh, tol, nAngle);
                        if (!tiedA.empty() || !tiedB.empty()) {
                            auto newA = ct_subtractFaces(facesA, tiedA);
                            auto newB = ct_subtractFaces(facesB, tiedB);
                            if (newA.empty() && newB.empty()) {
                                console.println("  PID " + std::to_string(pr.pidA) +
                                    " (" + nameA + ") <-> PID " + std::to_string(pr.pidB) +
                                    " (" + nameB + "): all segments tied, skipped");
                                skippedPairs++;
                                continue;
                            }
                            console.println("  PID " + std::to_string(pr.pidA) +
                                " (" + nameA + ") <-> PID " + std::to_string(pr.pidB) +
                                " (" + nameB + "): subtracted " +
                                std::to_string(facesA.size() - newA.size()) + "/" +
                                std::to_string(facesB.size() - newB.size()) + " tied segments");
                            facesA = std::move(newA);
                            facesB = std::move(newB);
                            subtractedPairs++;
                        }
                    }

                    char gapBuf[128];
                    snprintf(gapBuf, sizeof(gapBuf), "gap %.3f~%.3f",
                             pr.gapMin, pr.gapMax);
                    console.println("  PID " + std::to_string(pr.pidA) +
                        " (" + nameA + ") <-> PID " + std::to_string(pr.pidB) +
                        " (" + nameB + "): " +
                        std::to_string((int)facesA.size()) + "/" +
                        std::to_string((int)facesB.size()) +
                        " segments, " + gapBuf);

                    // Create SET_SEGMENTs
                    int slaveSid = nextSetId++;
                    int masterSid = nextSetId++;
                    insertBlocks.push_back(ct_generateSetSegment(slaveSid,
                        facesA,
                        prefix + "_S_" + nameA));
                    insertBlocks.push_back(ct_generateSetSegment(masterSid,
                        facesB,
                        prefix + "_M_" + nameB));
                    modified = true;

                    if (act.detectAutoCreate) {
                        ContactDef def{};
                        def.type = preset.keyword;
                        def.fullKeyword = "*CONTACT_" + preset.keyword;
                        def.hasTitle = true;
                        def.title = prefix + "_" + nameA + "_" + nameB;
                        def.ssid = slaveSid;
                        def.msid = preset.needMasterSide ? masterSid : 0;
                        def.sstyp = 0; // SET_SEGMENT
                        def.mstyp = preset.needMasterSide ? 0 : 0;
                        // Card 1 optional
                        if (act.sboxid >= 0) def.sboxid = act.sboxid;
                        if (act.mboxid >= 0) def.mboxid = act.mboxid;
                        if (act.spr >= 0) def.spr = act.spr;
                        if (act.mpr >= 0) def.mpr = act.mpr;
                        // Card 2
                        def.fs = (act.friction >= 0) ? act.friction : 0.0;
                        if (act.fd >= 0) def.fd = act.fd;
                        if (act.dc >= 0) def.dc = act.dc;
                        if (act.vc >= 0) def.vc = act.vc;
                        if (act.vdc >= 0) def.vdc = act.vdc;
                        if (act.penchk >= 0) def.penchk = act.penchk;
                        if (act.bt >= 0) def.bt = act.bt;
                        if (act.dt >= 0) def.dt = act.dt;
                        // Card 3
                        if (act.sfsa >= 0) def.sfsa = act.sfsa;
                        if (act.sfsb >= 0) def.sfsb = act.sfsb;
                        if (act.sast >= 0) def.sast = act.sast;
                        if (act.sbst >= 0) def.sbst = act.sbst;
                        if (act.sfsat >= 0) def.sfsat = act.sfsat;
                        if (act.sfsbt >= 0) def.sfsbt = act.sfsbt;
                        if (act.fsf >= 0) def.fsf = act.fsf;
                        if (act.vsf >= 0) def.vsf = act.vsf;
                        // Card A
                        if (act.soft>=0||act.sofscl>=0||act.lcidab>=0||act.maxpar>=0||
                            act.sbopt>=0||act.depth>=0||act.bsort>=0||act.frcfrq>=0) {
                            def.hasCardA = true;
                            if (act.soft >= 0) def.soft = act.soft;
                            if (act.sofscl >= 0) def.sofscl = act.sofscl;
                            if (act.lcidab >= 0) def.lcidab = act.lcidab;
                            if (act.maxpar >= 0) def.maxpar = act.maxpar;
                            if (act.sbopt >= 0) def.sbopt = act.sbopt;
                            if (act.depth >= 0) def.depth = act.depth;
                            if (act.bsort >= 0) def.bsort = act.bsort;
                            if (act.frcfrq >= 0) def.frcfrq = act.frcfrq;
                        }
                        // Card B
                        if (act.penmax>=0||act.thkopt>=0||act.shlthk>=0||act.snlog>=0||
                            act.isym>=0||act.i2d3d>=0||act.sldthk>=0||act.sldstf>=0) {
                            def.hasCardB = true; def.hasCardA = true;
                            if (act.penmax >= 0) def.penmax = act.penmax;
                            if (act.thkopt >= 0) def.thkopt = act.thkopt;
                            if (act.shlthk >= 0) def.shlthk = act.shlthk;
                            if (act.snlog >= 0) def.snlog = act.snlog;
                            if (act.isym >= 0) def.isym = act.isym;
                            if (act.i2d3d >= 0) def.i2d3d = act.i2d3d;
                            if (act.sldthk >= 0) def.sldthk = act.sldthk;
                            if (act.sldstf >= 0) def.sldstf = act.sldstf;
                        }
                        // Card C
                        if (act.igap>=0||act.ignore_>=0||act.dprfac>=0||act.dtstif>=0||
                            act.edgek>=0||act.flangl>=0||act.cid_rcf>=0) {
                            def.hasCardC = true; def.hasCardB = true; def.hasCardA = true;
                            if (act.igap >= 0) def.igap = act.igap;
                            if (act.ignore_ >= 0) def.ignore_ = act.ignore_;
                            if (act.dprfac >= 0) def.dprfac = act.dprfac;
                            if (act.dtstif >= 0) def.dtstif = act.dtstif;
                            if (act.edgek >= 0) def.edgek = act.edgek;
                            if (act.flangl >= 0) def.flangl = act.flangl;
                            if (act.cid_rcf >= 0) def.cid_rcf = act.cid_rcf;
                        }
                        // Card D
                        if (act.q2tri>=0||act.dtpchk>=0||act.sfnbr>=0||act.fnlscl>=0||
                            act.dnlscl>=0||act.tcso>=0||act.tiedid>=0||act.shledg>=0) {
                            def.hasCardD = true; def.hasCardC = true;
                            def.hasCardB = true; def.hasCardA = true;
                            if (act.q2tri >= 0) def.q2tri = act.q2tri;
                            if (act.dtpchk >= 0) def.dtpchk = act.dtpchk;
                            if (act.sfnbr >= 0) def.sfnbr = act.sfnbr;
                            if (act.fnlscl >= 0) def.fnlscl = act.fnlscl;
                            if (act.dnlscl >= 0) def.dnlscl = act.dnlscl;
                            if (act.tcso >= 0) def.tcso = act.tcso;
                            if (act.tiedid >= 0) def.tiedid = act.tiedid;
                            if (act.shledg >= 0) def.shledg = act.shledg;
                        }
                        // Card E
                        if (act.sharec>=0||act.cparm8>=0||act.ipback>=0||act.srnde>=0||
                            act.fricsf>=0||act.icor>=0||act.ftorq>=0||act.region>=0) {
                            def.hasCardE = true; def.hasCardD = true;
                            def.hasCardC = true; def.hasCardB = true; def.hasCardA = true;
                            if (act.sharec >= 0) def.sharec = act.sharec;
                            if (act.cparm8 >= 0) def.cparm8 = act.cparm8;
                            if (act.ipback >= 0) def.ipback = act.ipback;
                            if (act.srnde >= 0) def.srnde = act.srnde;
                            if (act.fricsf >= 0) def.fricsf = act.fricsf;
                            if (act.icor >= 0) def.icor = act.icor;
                            if (act.ftorq >= 0) def.ftorq = act.ftorq;
                            if (act.region >= 0) def.region = act.region;
                        }
                        // Card F
                        if (act.pstiff>=0||act.ignroff>=0||act.fstol>=0||
                            act.d2binr>=0||act.ssftyp>=0||act.swtpr>=0||act.tetfac>=0) {
                            def.hasCardF = true; def.hasCardE = true; def.hasCardD = true;
                            def.hasCardC = true; def.hasCardB = true; def.hasCardA = true;
                            if (act.pstiff >= 0) def.pstiff = act.pstiff;
                            if (act.ignroff >= 0) def.ignroff = act.ignroff;
                            if (act.fstol >= 0) def.fstol = act.fstol;
                            if (act.d2binr >= 0) def.d2binr = act.d2binr;
                            if (act.ssftyp >= 0) def.ssftyp = act.ssftyp;
                            if (act.swtpr >= 0) def.swtpr = act.swtpr;
                            if (act.tetfac >= 0) def.tetfac = act.tetfac;
                        }
                        // Card G
                        if (act.shloff >= 0) {
                            def.hasCardG = true; def.hasCardF = true; def.hasCardE = true;
                            def.hasCardD = true; def.hasCardC = true;
                            def.hasCardB = true; def.hasCardA = true;
                            def.shloff = act.shloff;
                        }
                        insertBlocks.push_back(ct_generateContact(def));
                        createdContacts++;
                    }
                }

                if (act.detectAutoCreate || skippedPairs > 0 || subtractedPairs > 0) {
                    std::string summary = "[contact] Created " +
                        std::to_string(createdContacts) + " contacts";
                    if (skippedPairs > 0)
                        summary += ", " + std::to_string(skippedPairs) + " skipped";
                    if (subtractedPairs > 0)
                        summary += ", " + std::to_string(subtractedPairs) + " subtracted";
                    console.println(summary);
                }
            } else {
                // --- Explicit PID mode (backward compatible) ---
                std::vector<std::array<int,4>> slaveFaces, masterFaces;
                int slavePid = act.slave.pid;
                int masterPid = act.master.pid;

                if (!act.slave.pids.empty()) {
                    std::vector<std::vector<std::array<int,4>>> perPid;
                    for (int p : act.slave.pids) perPid.push_back(ct_extractSurface(mesh, p));
                    slaveFaces = ct_mergeFaces(perPid);
                    slavePid = act.slave.pids[0]; // representative
                } else if (slavePid > 0) {
                    slaveFaces = ct_extractSurface(mesh, slavePid);
                }

                if (!act.master.pids.empty()) {
                    std::vector<std::vector<std::array<int,4>>> perPid;
                    for (int p : act.master.pids) perPid.push_back(ct_extractSurface(mesh, p));
                    masterFaces = ct_mergeFaces(perPid);
                    masterPid = act.master.pids[0];
                } else if (masterPid > 0) {
                    masterFaces = ct_extractSurface(mesh, masterPid);
                }

                if (slaveFaces.empty() || masterFaces.empty()) {
                    console.warning("[contact] detect: empty surface(s)");
                    continue;
                }

                console.println("[contact] Detecting: " +
                    std::to_string(slaveFaces.size()) + " slave faces x " +
                    std::to_string(masterFaces.size()) + " master faces" +
                    "  tol=" + std::to_string(tol) +
                    "  angle=" + std::to_string(nAngle));

                auto pairs = ct_detectContacting(slaveFaces, masterFaces, mesh,
                                                  slavePid, masterPid, tol, nAngle);

                if (pairs.empty()) {
                    console.println("[contact] No contacting segments found");
                    continue;
                }

                // Collect unique faces
                std::set<int> usedS, usedM;
                double gMin = 1e30, gMax = 0, gSum = 0;
                for (const auto& cp : pairs) {
                    usedS.insert(cp.faceA);
                    usedM.insert(cp.faceB);
                    if (cp.gap < gMin) gMin = cp.gap;
                    if (cp.gap > gMax) gMax = cp.gap;
                    gSum += cp.gap;
                }
                double gAvg = pairs.empty() ? 0 : gSum / pairs.size();

                std::vector<std::array<int,4>> sFaces, mFaces;
                for (int i : usedS) sFaces.push_back(slaveFaces[i]);
                for (int j : usedM) mFaces.push_back(masterFaces[j]);

                char gapBuf[128];
                snprintf(gapBuf, sizeof(gapBuf),
                         "gap min=%.4f max=%.4f avg=%.4f", gMin, gMax, gAvg);
                console.println("[contact] Found " +
                    std::to_string(pairs.size()) + " pairs, " +
                    std::to_string(sFaces.size()) + " slave / " +
                    std::to_string(mFaces.size()) + " master segments, " + gapBuf);

                int slaveSid = nextSetId++;
                int masterSid = nextSetId++;
                insertBlocks.push_back(ct_generateSetSegment(slaveSid, sFaces,
                    prefix + "_Slave"));
                insertBlocks.push_back(ct_generateSetSegment(masterSid, mFaces,
                    prefix + "_Master"));
                modified = true;

                if (act.detectAutoCreate) {
                    ContactDef def{};
                    def.type = preset.keyword;
                    def.fullKeyword = "*CONTACT_" + preset.keyword;
                    def.hasTitle = true;
                    def.title = prefix + "_PID" + std::to_string(slavePid) +
                                "_PID" + std::to_string(masterPid);
                    def.ssid = slaveSid;
                    def.msid = masterSid;
                    def.sstyp = 0; def.mstyp = 0;
                    // Card 1 optional
                    if (act.sboxid >= 0) def.sboxid = act.sboxid;
                    if (act.mboxid >= 0) def.mboxid = act.mboxid;
                    if (act.spr >= 0) def.spr = act.spr;
                    if (act.mpr >= 0) def.mpr = act.mpr;
                    // Card 2
                    def.fs = (act.friction >= 0) ? act.friction : 0.0;
                    if (act.fd >= 0) def.fd = act.fd;
                    if (act.dc >= 0) def.dc = act.dc;
                    if (act.vc >= 0) def.vc = act.vc;
                    if (act.vdc >= 0) def.vdc = act.vdc;
                    if (act.penchk >= 0) def.penchk = act.penchk;
                    if (act.bt >= 0) def.bt = act.bt;
                    if (act.dt >= 0) def.dt = act.dt;
                    // Card 3
                    if (act.sfsa >= 0) def.sfsa = act.sfsa;
                    if (act.sfsb >= 0) def.sfsb = act.sfsb;
                    if (act.sast >= 0) def.sast = act.sast;
                    if (act.sbst >= 0) def.sbst = act.sbst;
                    if (act.sfsat >= 0) def.sfsat = act.sfsat;
                    if (act.sfsbt >= 0) def.sfsbt = act.sfsbt;
                    if (act.fsf >= 0) def.fsf = act.fsf;
                    if (act.vsf >= 0) def.vsf = act.vsf;
                    // Card A
                    if (act.soft>=0||act.sofscl>=0||act.lcidab>=0||act.maxpar>=0||
                        act.sbopt>=0||act.depth>=0||act.bsort>=0||act.frcfrq>=0) {
                        def.hasCardA = true;
                        if (act.soft >= 0) def.soft = act.soft;
                        if (act.sofscl >= 0) def.sofscl = act.sofscl;
                        if (act.lcidab >= 0) def.lcidab = act.lcidab;
                        if (act.maxpar >= 0) def.maxpar = act.maxpar;
                        if (act.sbopt >= 0) def.sbopt = act.sbopt;
                        if (act.depth >= 0) def.depth = act.depth;
                        if (act.bsort >= 0) def.bsort = act.bsort;
                        if (act.frcfrq >= 0) def.frcfrq = act.frcfrq;
                    }
                    // Card B
                    if (act.penmax>=0||act.thkopt>=0||act.shlthk>=0||act.snlog>=0||
                        act.isym>=0||act.i2d3d>=0||act.sldthk>=0||act.sldstf>=0) {
                        def.hasCardB = true; def.hasCardA = true;
                        if (act.penmax >= 0) def.penmax = act.penmax;
                        if (act.thkopt >= 0) def.thkopt = act.thkopt;
                        if (act.shlthk >= 0) def.shlthk = act.shlthk;
                        if (act.snlog >= 0) def.snlog = act.snlog;
                        if (act.isym >= 0) def.isym = act.isym;
                        if (act.i2d3d >= 0) def.i2d3d = act.i2d3d;
                        if (act.sldthk >= 0) def.sldthk = act.sldthk;
                        if (act.sldstf >= 0) def.sldstf = act.sldstf;
                    }
                    // Card C
                    if (act.igap>=0||act.ignore_>=0||act.dprfac>=0||act.dtstif>=0||
                        act.edgek>=0||act.flangl>=0||act.cid_rcf>=0) {
                        def.hasCardC = true; def.hasCardB = true; def.hasCardA = true;
                        if (act.igap >= 0) def.igap = act.igap;
                        if (act.ignore_ >= 0) def.ignore_ = act.ignore_;
                        if (act.dprfac >= 0) def.dprfac = act.dprfac;
                        if (act.dtstif >= 0) def.dtstif = act.dtstif;
                        if (act.edgek >= 0) def.edgek = act.edgek;
                        if (act.flangl >= 0) def.flangl = act.flangl;
                        if (act.cid_rcf >= 0) def.cid_rcf = act.cid_rcf;
                    }
                    // Card D
                    if (act.q2tri>=0||act.dtpchk>=0||act.sfnbr>=0||act.fnlscl>=0||
                        act.dnlscl>=0||act.tcso>=0||act.tiedid>=0||act.shledg>=0) {
                        def.hasCardD = true; def.hasCardC = true;
                        def.hasCardB = true; def.hasCardA = true;
                        if (act.q2tri >= 0) def.q2tri = act.q2tri;
                        if (act.dtpchk >= 0) def.dtpchk = act.dtpchk;
                        if (act.sfnbr >= 0) def.sfnbr = act.sfnbr;
                        if (act.fnlscl >= 0) def.fnlscl = act.fnlscl;
                        if (act.dnlscl >= 0) def.dnlscl = act.dnlscl;
                        if (act.tcso >= 0) def.tcso = act.tcso;
                        if (act.tiedid >= 0) def.tiedid = act.tiedid;
                        if (act.shledg >= 0) def.shledg = act.shledg;
                    }
                    // Card E
                    if (act.sharec>=0||act.cparm8>=0||act.ipback>=0||act.srnde>=0||
                        act.fricsf>=0||act.icor>=0||act.ftorq>=0||act.region>=0) {
                        def.hasCardE = true; def.hasCardD = true;
                        def.hasCardC = true; def.hasCardB = true; def.hasCardA = true;
                        if (act.sharec >= 0) def.sharec = act.sharec;
                        if (act.cparm8 >= 0) def.cparm8 = act.cparm8;
                        if (act.ipback >= 0) def.ipback = act.ipback;
                        if (act.srnde >= 0) def.srnde = act.srnde;
                        if (act.fricsf >= 0) def.fricsf = act.fricsf;
                        if (act.icor >= 0) def.icor = act.icor;
                        if (act.ftorq >= 0) def.ftorq = act.ftorq;
                        if (act.region >= 0) def.region = act.region;
                    }
                    // Card F
                    if (act.pstiff>=0||act.ignroff>=0||act.fstol>=0||
                        act.d2binr>=0||act.ssftyp>=0||act.swtpr>=0||act.tetfac>=0) {
                        def.hasCardF = true; def.hasCardE = true; def.hasCardD = true;
                        def.hasCardC = true; def.hasCardB = true; def.hasCardA = true;
                        if (act.pstiff >= 0) def.pstiff = act.pstiff;
                        if (act.ignroff >= 0) def.ignroff = act.ignroff;
                        if (act.fstol >= 0) def.fstol = act.fstol;
                        if (act.d2binr >= 0) def.d2binr = act.d2binr;
                        if (act.ssftyp >= 0) def.ssftyp = act.ssftyp;
                        if (act.swtpr >= 0) def.swtpr = act.swtpr;
                        if (act.tetfac >= 0) def.tetfac = act.tetfac;
                    }
                    // Card G
                    if (act.shloff >= 0) {
                        def.hasCardG = true; def.hasCardF = true; def.hasCardE = true;
                        def.hasCardD = true; def.hasCardC = true;
                        def.hasCardB = true; def.hasCardA = true;
                        def.shloff = act.shloff;
                    }
                    insertBlocks.push_back(ct_generateContact(def));
                    console.println("[contact] Created *CONTACT_" + preset.keyword);
                }
            }
            continue;
        }

        console.warning("[contact] Unknown action: " + act.action);
    }

    // 6. Apply removals (descending order to preserve indices)
    if (!removeRanges.empty()) {
        std::sort(removeRanges.begin(), removeRanges.end(),
                  [](const auto& a, const auto& b){ return a.first > b.first; });
        for (const auto& [start, end] : removeRanges) {
            ct_removeBlock(lines, start, end);
        }
    }

    // 7. Insert new blocks before *END
    if (!insertBlocks.empty()) {
        int endPos = -1;
        for (int i = (int)lines.size()-1; i >= 0; --i) {
            std::string up = impl_trim(lines[i]);
            for (auto& c : up) c = static_cast<char>(toupper(static_cast<unsigned char>(c)));
            if (up == "*END") { endPos = i; break; }
        }
        if (endPos < 0) endPos = (int)lines.size();

        std::vector<std::string> combined;
        for (const auto& blk : insertBlocks) {
            // Split block into lines
            std::istringstream bs(blk);
            std::string bl;
            while (std::getline(bs, bl)) combined.push_back(bl);
        }
        lines.insert(lines.begin() + endPos, combined.begin(), combined.end());
    }

    // 8. Write output if modified
    if (analyzeOnly && !modified) {
        console.println("[contact] Analysis only — no output written.");
        return 0;
    }

    if (outPath.empty()) {
        console.error("YAML missing 'output' key (required for non-analyze actions)");
        return 1;
    }

    std::ofstream outf(outPath);
    if (!outf.is_open()) { console.error("Cannot write output: " + outPath); return 1; }
    for (const auto& ln : lines) outf << ln << "\n";
    console.println("[contact] Done -> " + outputFile);
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
        console.println("  matdb       Replace materials from JSON database (structural + thermal)");
        console.println("  implicit    Convert explicit K-file to implicit solver settings");
        console.println("  modal       Convert explicit K-file to modal (natural frequency) analysis");
        console.println("  ale         Convert parts to ALE (fluid/gas/explosive) with material presets");
        console.println("  contact     Analyze, create, modify, convert contact definitions");
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
            } else if (helpCmd == "optimize") {
                console.println("Usage: KooRemapper optimize <config.yaml>");
                std::cout << "\n";
                console.println("Apply material-specific global card optimization.");
                console.println("Can also be used with 'optimize: rubber' inside matswap YAML.");
                std::cout << "\n";
                console.println("Standalone YAML Format:");
                console.println("  model: model.k");
                console.println("  output: optimized.k");
                console.println("  optimize: rubber              # optimization mode");
                console.println("  pids: [3, 5]                  # target PIDs (for contact scope)");
                console.println("  tssfac: 0.67                  # optional, default 0.67");
                std::cout << "\n";
                console.println("Matswap Integration:");
                console.println("  model: model.k");
                console.println("  output: result.k");
                console.println("  swaps:");
                console.println("    - bundle: rubber.k");
                console.println("      pid: 3");
                console.println("  optimize: rubber              # applied after matswap");
                console.println("  tssfac: 0.67                  # optional");
                std::cout << "\n";
                console.println("Rubber Mode Actions:");
                console.println("  Forced modify + notice:");
                console.println("    *CONTROL_ACCURACY    INN=4 (invariant node numbering)");
                console.println("    *CONTROL_ENERGY      HGEN=2,RWEN=2,SLNTEN=2,RYLEN=2");
                console.println("    *CONTROL_TIMESTEP    TSSFAC (default 0.67)");
                console.println("    *CONTACT_*           SOFT=0, SBOPT=2.0 (for target PIDs)");
                std::cout << "\n";
                console.println("  Warning only:");
                console.println("    *CONTROL_TIMESTEP         DT2MS != 0 warning");
                console.println("    *CONTROL_BULK_VISCOSITY   Q1/Q2 deviation warning");
            } else if (helpCmd == "stabilize") {
                console.println("Usage: KooRemapper stabilize <config.yaml>");
                std::cout << "\n";
                console.println("Apply explicit solver stabilization measures (12-level cumulative system).");
                console.println("Each level includes all measures from lower levels.");
                std::cout << "\n";
                console.println("YAML Format (level preset):");
                console.println("  model:     model.k");
                console.println("  output:    stabilized.k");
                console.println("  stabilize: explicit");
                console.println("  level:     6           # preset level 1-12");
                std::cout << "\n";
                console.println("YAML Format (manual — set specific options):");
                console.println("  model:     model.k");
                console.println("  output:    stabilized.k");
                console.println("  stabilize: explicit");
                console.println("  tssfac:    0.80        # *CONTROL_TIMESTEP TSSFAC");
                console.println("  ihq:       4           # *CONTROL_HOURGLASS type");
                console.println("  soft:      1           # *CONTACT_* Card A SOFT");
                std::cout << "\n";
                console.println("Level Presets:");
                console.println("  Lv 1  Energy diagnostics: HGEN=RWEN=SLNTEN=RYLEN=2");
                console.println("  Lv 2  Accuracy: OSU=1, INN=4, ESORT=1 (solid+shell)");
                console.println("  Lv 3  Time step 1: TSSFAC=0.80");
                console.println("  Lv 4  Hourglass stiffness: IHQ=4, QH=0.10");
                console.println("  Lv 5  Shell stabilization: BWC=1, MITER=2, IRNXX=-2, WRPANG=10");
                console.println("          (auto-skipped if no *ELEMENT_SHELL in model)");
                console.println("  Lv 6  Contact stage 1: ORIEN=2, SHLTHK=1, XPENE=2, ISLCHK=2");
                console.println("          per-contact: SOFT=1, SBOPT=2, DEPTH=3");
                console.println("  Lv 7  Time step 2: TSSFAC=0.67 + BULK Q1=1.5, Q2=0.06 (forced)");
                console.println("  Lv 8  Contact stage 2 (pinball): SOFT=2, SBOPT=3, DEPTH=5");
                console.println("          SHLTHK=2, NSBCS=5, ENMASS=1, IGNORE=1, MAXPAR=1.15");
                console.println("  Lv 9  Best hourglass: IHQ=6 (Belytschko-Bindeman), QH=1.0");
                console.println("  Lv10  Time step 3: TSSFAC=0.60, NSBCS=2");
                console.println("  Lv11  Erosion: ERODE=11, ENMASS=2, NSBCS=1, TSSFAC=0.55");
                console.println("          (requires confirm_erosion: true or interactive y/N prompt)");
                console.println("  Lv12  Maximum conservative: TSSFAC=0.50, Q1=2.0, Q2=0.10");
                std::cout << "\n";
                console.println("All YAML options (manual mode):");
                console.println("  tssfac esort_solid esort_shell osu inn ihq qh");
                console.println("  bwc miter irnxx wrpang");
                console.println("  orien shlthk xpene islchk enmass nsbcs");
                console.println("  soft sbopt depth maxpar ignore");
                console.println("  bulk_q1 bulk_q2 erode confirm_erosion");
                console.println("  hgen rwen slnten rylen");
                std::cout << "\n";
                console.println("Examples: see examples/explicit/");
            } else if (helpCmd == "contact") {
                console.println("Usage: KooRemapper contact <config.yaml>");
                std::cout << "\n";
                console.println("Analyze, create, modify, convert, remove, or detect contact definitions.");
                console.println("Manages *CONTACT_*, *SET_SEGMENT, *SET_PART, *SET_NODE keywords.");
                std::cout << "\n";
                console.println("YAML Config Format:");
                console.println("  model:  model.k");
                console.println("  output: model_contact.k      # optional for analyze-only");
                console.println("");
                console.println("  contacts:");
                console.println("    # Analyze (report only, no modification)");
                console.println("    - action: analyze");
                console.println("");
                console.println("    # Create: part ID direct (SSTYP=3)");
                console.println("    - action: create");
                console.println("      type: automatic_surface_to_surface");
                console.println("      slave:  { pid: 1 }");
                console.println("      master: { pid: 2 }");
                console.println("      friction: 0.3");
                console.println("      soft: 2");
                console.println("      title: Case_to_Board");
                console.println("");
                console.println("    # Create: multiple PIDs -> auto SET_PART (SSTYP=2)");
                console.println("    - action: create");
                console.println("      type: automatic_surface_to_surface");
                console.println("      slave:  { pids: [1, 2, 3] }");
                console.println("      master: { pids: [4, 5] }");
                console.println("");
                console.println("    # Create: extract surface segments (SSTYP=0)");
                console.println("    - action: create");
                console.println("      type: automatic_surface_to_surface");
                console.println("      slave:  { pid: 1, as_segment: true }");
                console.println("      master: { pid: 2, as_segment: true }");
                console.println("");
                console.println("    # Create: single surface self-contact");
                console.println("    - action: create");
                console.println("      type: automatic_single_surface");
                console.println("      slave:  { pids: [1, 2, 3, 4] }");
                console.println("      soft: 2");
                console.println("");
                console.println("    # Convert: part -> segment (extract outer surface)");
                console.println("    - action: convert");
                console.println("      contact_index: 0          # from analyze report");
                console.println("      slave_to: segment");
                console.println("      master_to: segment");
                console.println("");
                console.println("    # Modify: change friction / SOFT");
                console.println("    - action: modify");
                console.println("      contact_index: 0");
                console.println("      friction: 0.5");
                console.println("      soft: 2");
                console.println("");
                console.println("    # Remove a contact definition");
                console.println("    - action: remove");
                console.println("      contact_index: 0");
                console.println("");
                console.println("    # Detect: auto-find contacting segments between two PIDs");
                console.println("    - action: detect");
                console.println("      slave:  { pid: 1 }");
                console.println("      master: { pid: 2 }");
                console.println("      tolerance: 0.1");
                console.println("      auto_create: true");
                console.println("      contact_type: auto         # auto/tied/mortar/tied_mortar/single/eroding/forming");
                console.println("");
                console.println("    # Detect: all parts (scope: all)");
                console.println("    - action: detect");
                console.println("      scope: all");
                console.println("      exclude: [rigid, null]");
                console.println("      tolerance: 0.1");
                console.println("      auto_create: true");
                console.println("");
                console.println("    # Detect: keyword-based part selection");
                console.println("    - action: detect");
                console.println("      include: [bolt, plate]");
                console.println("      exclude: [rigid]");
                console.println("      tolerance: 0.05");
                console.println("      auto_create: true");
                console.println("      contact_type: tied");
                std::cout << "\n";
                console.println("SSTYP/MSTYP values:");
                console.println("  0  Segment set (*SET_SEGMENT)");
                console.println("  1  Shell element set (*SET_SHELL)");
                console.println("  2  Part set (*SET_PART)");
                console.println("  3  Part ID (direct)");
                console.println("  4  Node set (*SET_NODE)");
                console.println("  5  All parts (entire model)");
                std::cout << "\n";
                console.println("Workflow:");
                console.println("  1. Run with 'analyze' action to see contacts and indices");
                console.println("  2. Use contact_index from report for convert/modify/remove");
                console.println("  3. Multiple actions processed in order");
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
            console.println("  matdb        Replace materials from JSON DB (structural + thermal)");
            console.println("  implicit     Convert explicit K-file to implicit solver settings");
            console.println("  modal        Convert explicit K-file to modal (natural frequency) analysis");
            console.println("  ale          Convert parts to ALE with material presets");
            console.println("  contact      Analyze, create, modify, convert contact definitions");
            console.println("  optimize     Apply material-specific global card optimization");
            console.println("  stabilize    Apply explicit solver stabilization (12-level system)");
            console.println("  info         Display information about a mesh file");
            console.println("  help         Show help for a command");
            console.println("  version      Show version information");
            std::cout << "\n";
            console.println("Use 'KooRemapper help <command>' for details.");
            console.println("  Key commands: help assemble  help implicit  help modal  help ale  help contact");
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

    // Matdb command
    if (command == "matdb") {
        if (argc < 3) {
            console.error("Usage: KooRemapper matdb <config.yaml>");
            console.println("  Material database-driven swap: replace structural materials from JSON DB");
            console.println("  Options: mat_type (MAT_ELASTIC/MAT_024/MAT_RIGID), thermal (true/false)");
            return 1;
        }
        printBanner(console);
        return runMatdb(argv[2], console);
    }

    // Load command
    if (command == "load") {
        if (argc < 3) {
            console.error("Usage: KooRemapper load <config.yaml>");
            console.println("  Apply segment-based loads (pressure/force) to model");
            console.println("  Modes: force, pressure, normal_pressure");
            console.println("  Select: direction, set, tied");
            return 1;
        }
        printBanner(console);
        return runLoad(argv[2], console);
    }

    // Boundary command
    if (command == "boundary") {
        if (argc < 3) {
            console.error("Usage: KooRemapper boundary <config.yaml>");
            console.println("  Apply nodal SPC boundary conditions");
            console.println("  DOF: all, xyz, x, y, z, xy, xz, yz, custom");
            console.println("  Select: direction, set");
            return 1;
        }
        printBanner(console);
        return runBoundary(argv[2], console);
    }

    // RBE command
    if (command == "rbe") {
        if (argc < 3) {
            console.error("Usage: KooRemapper rbe <config.yaml>");
            console.println("  Create RBE constraints (CNRB/CONSTRAINED_INTERPOLATION)");
            console.println("  Type: rbe2 (rigid), rbe3 (interpolation)");
            console.println("  Mode: spider (one centroid), face (per-face centroid)");
            return 1;
        }
        printBanner(console);
        return runRbe(argv[2], console);
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

    // Contact command
    if (command == "contact") {
        if (argc < 3) {
            console.error("Usage: KooRemapper contact <config.yaml>");
            return 1;
        }
        printBanner(console);
        return runContact(argv[2], console);
    }

    // Optimize command
    if (command == "optimize") {
        if (argc < 3) {
            console.error("Usage: KooRemapper optimize <config.yaml>");
            return 1;
        }
        printBanner(console);
        return runOptimize(argv[2], console);
    }

    // Stabilize command
    if (command == "stabilize") {
        if (argc < 3) {
            console.error("Usage: KooRemapper stabilize <config.yaml>");
            return 1;
        }
        printBanner(console);
        return runStabilize(argv[2], console);
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
