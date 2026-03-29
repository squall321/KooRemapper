#include "core_ops.h"
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
#include "mapper/ShellUnfolder.h"
#include "example/ExampleMeshGenerator.h"
#include "generator/VariableDensityConfig.h"
#include "generator/YamlConfigReader.h"
#include "generator/VariableDensityMeshGenerator.h"
#include "generator/CurvedMeshGenerator.h"
#include "analysis/StrainCalculator.h"
#include "analysis/ElementAnalyzer.h"
#include "analysis/MaterialModel.h"
#include "cli/ConsoleOutput.h"
#include "util/Timer.h"
#include "util/Validator.h"
#include <iostream>
#include <fstream>
#include <sstream>
#include <string>
#include <vector>
#include <memory>
#include <limits>
#include <iomanip>

using namespace KooRemapper;

int runMapping(const std::string& bentFile, const std::string& flatFile,
               const std::string& outputFile, const ConsoleOutput& console,
               bool useParallel) {
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
int runGenerateBox(const std::string& yamlFile, ConsoleOutput& console) {
    // Parse YAML
    std::ifstream f(yamlFile);
    if (!f.is_open()) { console.error("Cannot open: " + yamlFile); return 1; }

    std::string configDir;
    {
        size_t sp = yamlFile.find_last_of("/\\");
        if (sp != std::string::npos) configDir = yamlFile.substr(0, sp);
    }

    auto trim = [](const std::string& s) -> std::string {
        size_t a = s.find_first_not_of(" \t\r\n\"'");
        size_t b = s.find_last_not_of(" \t\r\n\"'");
        return (a == std::string::npos) ? "" : s.substr(a, b - a + 1);
    };
    auto resolvePath = [&](const std::string& p) -> std::string {
        if (p.find('/') != std::string::npos || p.find('\\') != std::string::npos)
            return p;
        return configDir.empty() ? p : configDir + "/" + p;
    };

    // Parameters with defaults
    double lx = 100.0, ly = 20.0, lz = 20.0;
    int nx = 4, ny = 4, nz = 2;
    double rho = 7.85e-9, E = 210000.0, nu = 0.3;
    int mid = 1, secid = 1, pid = 1;
    std::string partTitle = "Box";
    std::string outputPath;

    std::string ln;
    while (std::getline(f, ln)) {
        if (!ln.empty() && ln.back() == '\r') ln.pop_back();
        std::string tr = trim(ln);
        if (tr.empty() || tr[0] == '#') continue;
        size_t cp = tr.find(':');
        if (cp == std::string::npos) continue;
        std::string key = trim(tr.substr(0, cp));
        std::string val = trim(tr.substr(cp + 1));

        if      (key == "output")     outputPath = resolvePath(val);
        else if (key == "lx")         { try { lx = std::stod(val); } catch (...) {} }
        else if (key == "ly")         { try { ly = std::stod(val); } catch (...) {} }
        else if (key == "lz")         { try { lz = std::stod(val); } catch (...) {} }
        else if (key == "nx")         { try { nx = std::stoi(val); } catch (...) {} }
        else if (key == "ny")         { try { ny = std::stoi(val); } catch (...) {} }
        else if (key == "nz")         { try { nz = std::stoi(val); } catch (...) {} }
        else if (key == "rho")        { try { rho = std::stod(val); } catch (...) {} }
        else if (key == "E")          { try { E   = std::stod(val); } catch (...) {} }
        else if (key == "nu")         { try { nu  = std::stod(val); } catch (...) {} }
        else if (key == "mid")        { try { mid   = std::stoi(val); } catch (...) {} }
        else if (key == "secid")      { try { secid = std::stoi(val); } catch (...) {} }
        else if (key == "pid")        { try { pid   = std::stoi(val); } catch (...) {} }
        else if (key == "part_title") partTitle = val;
    }
    f.close();

    if (outputPath.empty()) { console.error("[box] output not specified"); return 1; }
    if (nx < 1 || ny < 1 || nz < 1) { console.error("[box] nx/ny/nz must be >= 1"); return 1; }

    // Ensure .k extension
    if (outputPath.size() < 2 || outputPath.substr(outputPath.size() - 2) != ".k")
        outputPath += ".k";

    int npx = nx + 1, npy = ny + 1, npz = nz + 1;
    int nodeCount = npx * npy * npz;
    int elemCount = nx * ny * nz;

    // Node index: (ix, iy, iz) → NID (1-based)
    auto nid = [&](int ix, int iy, int iz) -> int {
        return iz * (npx * npy) + iy * npx + ix + 1;
    };

    std::ofstream out(outputPath);
    if (!out.is_open()) { console.error("[box] Cannot write: " + outputPath); return 1; }

    out << "*KEYWORD\n";
    out << "$\n$ Box mesh: " << lx << "x" << ly << "x" << lz
        << " mm, " << nx << "x" << ny << "x" << nz << " elements\n$\n";

    // MAT_ELASTIC
    char buf[128];
    out << "*MAT_ELASTIC\n";
    out << "$#     mid        ro         e        pr\n";
    snprintf(buf, sizeof(buf), "%10d%10.4g%10.4g%10.4g\n", mid, rho, E, nu);
    out << buf;

    // SECTION_SOLID
    out << "*SECTION_SOLID\n";
    out << "$#   secid    elform\n";
    snprintf(buf, sizeof(buf), "%10d%10d\n", secid, 1);
    out << buf;

    // PART
    out << "*PART\n";
    out << partTitle << "\n";
    out << "$#     pid     secid       mid\n";
    snprintf(buf, sizeof(buf), "%10d%10d%10d\n", pid, secid, mid);
    out << buf;

    // NODE
    out << "*NODE\n";
    out << "$#   nid               x               y               z\n";
    for (int iz = 0; iz < npz; ++iz) {
        double z = lz * iz / nz;
        for (int iy = 0; iy < npy; ++iy) {
            double y = ly * iy / ny;
            for (int ix = 0; ix < npx; ++ix) {
                double x = lx * ix / nx;
                snprintf(buf, sizeof(buf), "%8d%16.9e%16.9e%16.9e\n",
                         nid(ix, iy, iz), x, y, z);
                out << buf;
            }
        }
    }

    // ELEMENT_SOLID (HEX8)
    out << "*ELEMENT_SOLID\n";
    out << "$#   eid     pid      n1      n2      n3      n4      n5      n6      n7      n8\n";
    int eid = 1;
    for (int iz = 0; iz < nz; ++iz) {
        for (int iy = 0; iy < ny; ++iy) {
            for (int ix = 0; ix < nx; ++ix) {
                // HEX8 node ordering: bottom face (CCW from outside) then top face
                int n1 = nid(ix,   iy,   iz);
                int n2 = nid(ix+1, iy,   iz);
                int n3 = nid(ix+1, iy+1, iz);
                int n4 = nid(ix,   iy+1, iz);
                int n5 = nid(ix,   iy,   iz+1);
                int n6 = nid(ix+1, iy,   iz+1);
                int n7 = nid(ix+1, iy+1, iz+1);
                int n8 = nid(ix,   iy+1, iz+1);
                snprintf(buf, sizeof(buf),
                         "%8d%8d%8d%8d%8d%8d%8d%8d%8d%8d\n",
                         eid++, pid, n1, n2, n3, n4, n5, n6, n7, n8);
                out << buf;
            }
        }
    }

    out << "*END\n";
    out.close();

    console.success("[box] " + std::to_string(nodeCount) + " nodes, "
                    + std::to_string(elemCount) + " elements → " + outputPath);
    return 0;
}

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
