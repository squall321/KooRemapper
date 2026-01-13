#include "core/Platform.h"
#include "core/Mesh.h"
#include "parser/KFileReader.h"
#include "parser/KFileWriter.h"
#include "parser/DynainWriter.h"
#include "mapper/MeshRemapper.h"
#include "mapper/FlatMeshGenerator.h"
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
#include "util/Logger.h"
#include "util/Timer.h"
#include "util/Validator.h"

#include <iostream>
#include <memory>
#include <limits>

using namespace KooRemapper;

// Version info
constexpr const char* VERSION = "1.0.0";

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
 */
int runMapping(const std::string& bentFile, const std::string& flatFile,
               const std::string& outputFile, const ConsoleOutput& console) {
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
    console.info("Performing mesh mapping...");
    MeshRemapper remapper;
    remapper.setBentMesh(&bentMesh);
    remapper.setFlatMesh(&flatMesh);

    // Set progress callback
    remapper.setProgressCallback([&console](int percent) {
        console.progressBar(percent);
    });

    if (!remapper.performMapping()) {
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
    
    // Report materials found in K-file
    if (refMesh.getMaterialCount() > 0) {
        console.info("Found " + std::to_string(refMesh.getMaterialCount()) + " material(s) in K-file:");
        for (const auto& [matId, mat] : refMesh.getMaterials()) {
            console.println("  Material " + std::to_string(matId) + 
                          ": E=" + std::to_string(mat.E) + 
                          ", nu=" + std::to_string(mat.nu));
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
        console.keyValue("Min von Mises stress", std::to_string(results.minVonMisesStress));
        console.keyValue("Max von Mises stress", std::to_string(results.maxVonMisesStress));
        console.keyValue("Avg von Mises stress", std::to_string(results.avgVonMisesStress));
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

int main(int argc, char* argv[]) {
    ConsoleOutput console;

    // Check for subcommand
    if (argc < 2) {
        printBanner(console);
        console.println("Usage: KooRemapper <command> [options]");
        std::cout << "\n";
        console.println("Commands:");
        console.println("  map         Map a flat mesh onto a bent reference mesh");
        console.println("  unfold      Generate flat mesh from a bent structured mesh");
        console.println("  generate    Generate example meshes for testing");
        console.println("  generate-var Generate variable density mesh from YAML config");
        console.println("  strain      Calculate strain between two meshes");
        console.println("  prestress   Calculate prestress from deformed configuration");
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
                console.println("Usage: KooRemapper map <bent_mesh> <flat_mesh> <output>");
                std::cout << "\n";
                console.println("Map a flat unstructured mesh onto a bent structured mesh.");
                std::cout << "\n";
                console.println("Arguments:");
                console.println("  bent_mesh   The bent structured reference mesh (k-file)");
                console.println("  flat_mesh   The flat mesh to be mapped (k-file)");
                console.println("  output      Output file path for the mapped mesh");
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
                console.println("  --strain <type>  Strain type: engineering (default), green");
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
            } else {
                console.error("Unknown command: " + helpCmd);
                return 1;
            }
        } else {
            printBanner(console);
            console.println("Usage: KooRemapper <command> [options]");
            std::cout << "\n";
            console.println("Commands:");
            console.println("  map         Map a flat mesh onto a bent reference mesh");
            console.println("  unfold      Generate flat mesh from a bent structured mesh");
            console.println("  generate    Generate example meshes for testing");
            console.println("  generate-var Generate variable density mesh from YAML config");
            console.println("  strain      Calculate strain between two meshes");
            console.println("  prestress   Calculate prestress from deformed configuration");
            console.println("  info        Display information about a mesh file");
            console.println("  help        Show help for a command");
            console.println("  version     Show version information");
        }
        return 0;
    }

    // Map command
    if (command == "map") {
        if (argc < 5) {
            console.error("Usage: KooRemapper map <bent_mesh> <flat_mesh> <output>");
            return 1;
        }
        printBanner(console);
        return runMapping(argv[2], argv[3], argv[4], console);
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

        StrainType strainType = StrainType::ENGINEERING;
        if (strainTypeStr == "green" || strainTypeStr == "green-lagrange") {
            strainType = StrainType::GREEN_LAGRANGE;
        }

        printBanner(console);
        return runPrestress(refFile, defFile, output, E, nu, strainType, outputCSV, console);
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
