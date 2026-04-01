#include "squeeze_assemble.h"
#include "relax.h"
#include "core/Mesh.h"
#include "parser/KFileReader.h"
#include "parser/KFileWriter.h"
#include "parser/DynainWriter.h"
#include "squeeze/SqueezeConfig.h"
#include "squeeze/SqueezeConfigReader.h"
#include "assembly/AssemblyConfig.h"
#include "assembly/AssemblyConfigReader.h"
#include "assembly/ModelAssembler.h"
#include "cli/ConsoleOutput.h"
#include "util/Timer.h"
#include <iostream>
#include <fstream>
#include <sstream>
#include <string>
#include <vector>
#include <memory>
#include <limits>
#include <set>
#include <unordered_map>
#include <iomanip>

using namespace KooRemapper;

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
    } else if (config.strainMode) {
        console.info("strain_mode: no material needed (*INITIAL_STRAIN_SOLID)");
    } else {
        console.error("No material specified (required for stress computation)");
        console.info("Add 'material:' section to YAML, include *MAT_ELASTIC in K-file, or set strain_mode: true");
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
        if (partConfig.hasSwelling()) {
            std::ostringstream oss;
            oss << std::fixed << std::setprecision(4);
            oss << "Part " << partConfig.pid << ": swelling = " << partConfig.swelling
                << " (" << (partConfig.swelling * 100.0) << "%)";
            console.info(oss.str());
        } else {
            std::ostringstream oss;
            oss << std::fixed << std::setprecision(4);
            oss << "Part " << partConfig.pid << ": eps = ("
                << partConfig.eps_x << ", " << partConfig.eps_y << ", " << partConfig.eps_z << ")";
            console.info(oss.str());
        }

        std::ostringstream oss2;
        oss2 << std::fixed << std::setprecision(3);
        oss2 << "  BB: [" << minX << ", " << minY << ", " << minZ << "] to ["
             << maxX << ", " << maxY << ", " << maxZ << "]";
        console.println(oss2.str());
        console.println("  Center: (" + std::to_string(centerX) + ", " +
                        std::to_string(centerY) + ", " + std::to_string(centerZ) + ")");
        console.println("  Nodes: " + std::to_string(partNodeIds.size()));

        // Swelling parts: no node movement (thermal expansion cards inserted later)
        if (partConfig.hasSwelling()) {
            console.println("  Mode: thermal expansion (no node movement)");
            continue;
        }

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

    // Write dynain: stress mode or strain mode
    std::string dynainFile = outputPrefix + ".dynain";
    int dynainElementCount = 0;

    if (config.strainMode) {
        // strain_mode: write *INITIAL_STRAIN_SOLID directly — no material needed
        console.info("Writing strain dynain: " + dynainFile);
        std::ofstream sf(dynainFile);
        if (!sf.is_open()) { console.error("Cannot write dynain: " + dynainFile); return 1; }
        sf << "*KEYWORD\n";
        sf << "$\n$ KooRemapper - Initial Strain File (strain_mode)\n";
        sf << "$ Source: " << configFile << "\n$\n";
        sf << "*INITIAL_STRAIN_SOLID\n";
        sf << "$#    eid    nint   nhisv   large\n";
        sf << "$#       eps11        eps22        eps33        eps12        eps23        eps13\n";
        for (const auto& [eid, elem] : mesh.getElements()) {
            auto it = partConfigMap.find(elem.partId);
            if (it == partConfigMap.end()) continue;
            const auto& pc = *(it->second);
            if (pc.hasSwelling()) continue;
            // Card 1
            sf << std::setw(10) << eid
               << std::setw(8)  << 1
               << std::setw(8)  << 0
               << std::setw(8)  << 0 << "\n";
            // Card 2: reverse strain (eps_x/y/z negated, shear = 0)
            sf << std::scientific << std::setprecision(4)
               << std::setw(13) << -pc.eps_x
               << std::setw(13) << -pc.eps_y
               << std::setw(13) << -pc.eps_z
               << std::setw(13) << 0.0
               << std::setw(13) << 0.0
               << std::setw(13) << 0.0 << "\n";
            ++dynainElementCount;
        }
        sf << "*END\n";
        console.success("Strain dynain written: " + std::to_string(dynainElementCount) + " elements");
    } else {
        // stress mode: compute stress via Hooke's law -> *INITIAL_STRESS_SOLID
        MeshAnalysisResult results;
        results.hasMaterial = true;
        results.validElements = 0;
        results.invalidElements = 0;

        for (const auto& [eid, elem] : mesh.getElements()) {
            auto it = partConfigMap.find(elem.partId);
            if (it == partConfigMap.end()) continue;

            const auto& pc = *(it->second);
            if (pc.hasSwelling()) continue;

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

            if (matE <= 0) { results.invalidElements++; continue; }

            StrainTensor reverseStrain(-pc.eps_x, -pc.eps_y, -pc.eps_z, 0.0, 0.0, 0.0);
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

        console.info("Writing dynain: " + dynainFile);
        DynainWriter dynainWriter;
        if (!dynainWriter.writeFile(dynainFile, results, StrainType::ENGINEERING,
                                    meshFile, "squeeze: " + configFile)) {
            console.error("Failed to write dynain: " + dynainWriter.getErrorMessage());
            return 1;
        }
        dynainElementCount = results.validElements;
        console.success("Dynain written: " + std::to_string(dynainElementCount) + " elements");
    }

    // Build swelling thermal expansion cards
    std::string swellingCards;
    {
        bool hasSwelling = false;
        for (const auto& partConfig : config.parts) {
            if (!partConfig.hasSwelling()) continue;
            hasSwelling = true;

            // Find MID for this part
            int partMid = 0;
            const auto& parts = mesh.getParts();
            auto pit = parts.find(partConfig.pid);
            if (pit != parts.end()) {
                partMid = pit->second.materialId;
            }

            // Fallback: use PID as MID (common LS-DYNA convention)
            if (partMid <= 0) {
                partMid = partConfig.pid;
                console.info("  Part " + std::to_string(partConfig.pid) +
                            ": *PART not found, using PID as MID=" + std::to_string(partMid));
            }

            // *MAT_ADD_THERMAL_EXPANSION: CTE = swelling, will use DT=1.0
            char buf[256];
            swellingCards += "$\n";
            swellingCards += "$ Swelling for Part " + std::to_string(partConfig.pid) +
                           " (MID=" + std::to_string(partMid) + ")\n";
            swellingCards += "$\n";
            swellingCards += "*MAT_ADD_THERMAL_EXPANSION\n";
            swellingCards += "$#     mid      lcid     mult     lcid2    mult2\n";
            snprintf(buf, sizeof(buf), "%10d%10d%10.4g%10d%10.4g\n",
                     partMid, 0, partConfig.swelling, 0, 0.0);
            swellingCards += buf;

            // Collect nodes for this part for *INITIAL_TEMPERATURE
            std::set<int> partNodeIds;
            for (const auto& [eid, elem] : mesh.getElements()) {
                if (elem.partId == partConfig.pid) {
                    for (int i = 0; i < Element::NUM_NODES; ++i) {
                        partNodeIds.insert(elem.nodeIds[i]);
                    }
                }
            }
            swellingCards += "*INITIAL_TEMPERATURE_NODE\n";
            swellingCards += "$#     nid      temp       loc\n";
            for (int nid : partNodeIds) {
                snprintf(buf, sizeof(buf), "%10d%10.4g%10d\n", nid, 1.0, 0);
                swellingCards += buf;
            }

            console.success("Swelling cards generated for Part " +
                          std::to_string(partConfig.pid) + ": " +
                          std::to_string(partNodeIds.size()) + " nodes, alpha=" +
                          std::to_string(partConfig.swelling));
        }
    }

    // Append *INCLUDE (dynain) + swelling cards to compressed mesh
    {
        // Get just the dynain filename for *INCLUDE
        std::string dynainBasename = dynainFile;
        size_t slashPos = dynainBasename.find_last_of("/\\");
        if (slashPos != std::string::npos) {
            dynainBasename = dynainBasename.substr(slashPos + 1);
        }

        bool hasDynain = (dynainElementCount > 0);

        // Re-read the compressed mesh and insert before *END
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
                if (hasDynain) {
                    meshContent += "*INCLUDE\n";
                    meshContent += dynainBasename + "\n";
                }
                if (!swellingCards.empty()) {
                    meshContent += swellingCards;
                }
                if (config.relax.enabled) {
                    const auto& rc = config.relax;
                    if (rc.endtime > 0) {
                        char tbuf[64];
                        snprintf(tbuf, sizeof(tbuf), "*CONTROL_TERMINATION\n$#  endtim\n%10.4g\n", rc.endtime);
                        meshContent += tbuf;
                    }
                    meshContent += relax_generateCards(rc.level, rc.mode, rc.drterm,
                        rc.nrcyckOvr, rc.drtolOvr, rc.drfctrOvr,
                        rc.tssfdrOvr, rc.irelalOvr, rc.edttlOvr, rc.d3drlf);
                }
                endFound = true;
            }
            meshContent += line + "\n";
        }
        srcFile.close();

        if (!endFound) {
            if (hasDynain) {
                meshContent += "*INCLUDE\n";
                meshContent += dynainBasename + "\n";
            }
            if (!swellingCards.empty()) {
                meshContent += swellingCards;
            }
            if (config.relax.enabled) {
                const auto& rc = config.relax;
                if (rc.endtime > 0) {
                    char tbuf[64];
                    snprintf(tbuf, sizeof(tbuf), "*CONTROL_TERMINATION\n$#  endtim\n%10.4g\n", rc.endtime);
                    meshContent += tbuf;
                }
                meshContent += relax_generateCards(rc.level, rc.mode, rc.drterm,
                    rc.nrcyckOvr, rc.drtolOvr, rc.drfctrOvr,
                    rc.tssfdrOvr, rc.irelalOvr, rc.edttlOvr, rc.d3drlf);
            }
            meshContent += "*END\n";
        }

        std::ofstream dstFile(meshOutputFile, std::ios::binary);
        if (!dstFile.is_open()) {
            console.error("Failed to write mesh with additions");
            return 1;
        }
        dstFile << meshContent;
        dstFile.close();

        if (hasDynain) {
            console.success("Added *INCLUDE to: " + meshOutputFile);
        }
        if (!swellingCards.empty()) {
            console.success("Added thermal expansion cards to: " + meshOutputFile);
        }
        if (config.relax.enabled) {
            const auto& rc = config.relax;
            static const char* lvNames[5] = {"fast","standard","stable","conservative","max"};
            int li = std::max(0, std::min(4, rc.level - 1));
            char rbuf[128];
            snprintf(rbuf, sizeof(rbuf), "[relax] Inserted *CONTROL_DYNAMIC_RELAXATION  level=%d(%s)  mode=%s%s",
                rc.level, lvNames[li], rc.mode.c_str(), rc.d3drlf ? "  +D3DRLF" : "");
            console.success(rbuf);
            if (rc.endtime > 0) {
                char tbuf[64];
                snprintf(tbuf, sizeof(tbuf), "[relax] Inserted *CONTROL_TERMINATION  endtim=%g", rc.endtime);
                console.println(tbuf);
            }
        }
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

    // 2. Load base model (skip if first op is 'generate')
    ModelAssembler assembler;
    assembler.setDynamicRelaxation(config.dynamicRelaxation);
    assembler.setDynainEmbed(config.dynainEmbed);
    bool firstIsGenerate = !config.operations.empty() &&
                           config.operations[0].type == AssemblyOperation::GENERATE;
    if (!firstIsGenerate) {
        console.info("Loading base model: " + baseModelPath);
        if (!assembler.loadBaseModel(baseModelPath)) {
            console.error(assembler.getErrorMessage());
            return 1;
        }
        console.success("Loaded " + std::to_string(assembler.getNodeCount()) + " nodes, " +
                       std::to_string(assembler.getElementCount()) + " elements, " +
                       std::to_string(assembler.getPartCount()) + " parts");
    }

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
            if (!op.formstrain.targetPids.empty()) {
                for (int pid : op.formstrain.targetPids) {
                    FormStrainOperation fs = op.formstrain; fs.targetPid = pid; fs.targetPids = {};
                    ok = assembler.applyFormStrain(fs);
                    if (!ok) break;
                }
            } else {
                ok = assembler.applyFormStrain(op.formstrain);
            }
        } else if (op.type == AssemblyOperation::TET10_CONVERT) {
            if (!op.tet10.targetPids.empty()) {
                for (int pid : op.tet10.targetPids) {
                    Tet10ConvertOperation t = op.tet10; t.targetPid = pid; t.targetPids = {};
                    ok = assembler.applyTet10Convert(t);
                    if (!ok) break;
                }
            } else {
                ok = assembler.applyTet10Convert(op.tet10);
            }
        } else if (op.type == AssemblyOperation::REFINE) {
            if (!op.refine.targetPids.empty()) {
                for (int pid : op.refine.targetPids) {
                    RefineOperation r = op.refine; r.targetPid = pid; r.targetPids = {};
                    ok = assembler.applyRefine(r);
                    if (!ok) break;
                }
            } else {
                ok = assembler.applyRefine(op.refine);
            }
        } else if (op.type == AssemblyOperation::ELFORM) {
            if (!op.elform.targetPids.empty()) {
                for (int pid : op.elform.targetPids) {
                    ElformOperation e = op.elform; e.targetPid = pid; e.targetPids = {};
                    ok = assembler.applyElform(e);
                    if (!ok) break;
                }
            } else {
                ok = assembler.applyElform(op.elform);
            }
        } else if (op.type == AssemblyOperation::DISCONNECT) {
            ok = assembler.applyDisconnect(op.disconnect);
        } else if (op.type == AssemblyOperation::IGA) {
            ok = assembler.applyIGA(op.iga, outputPrefix);
        } else if (op.type == AssemblyOperation::WARPAGE) {
            if (!op.warpage.targetPids.empty()) {
                for (int pid : op.warpage.targetPids) {
                    WarpageOperation w = op.warpage; w.targetPid = pid; w.targetPids = {};
                    ok = assembler.applyWarpage(w, matE, matNu, configDir);
                    if (!ok) break;
                }
            } else {
                ok = assembler.applyWarpage(op.warpage, matE, matNu, configDir);
            }
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
        } else if (op.type == AssemblyOperation::WRAP) {
            ok = assembler.applyWrap(op.wrap, matE, matNu);
        } else if (op.type == AssemblyOperation::UPDATE) {
            // Resolve dynain path relative to config directory
            UpdateOperation updateOp = op.update;
            if (!updateOp.dynainFile.empty() &&
                updateOp.dynainFile.find('/') == std::string::npos &&
                updateOp.dynainFile.find('\\') == std::string::npos) {
                updateOp.dynainFile = configDir + "/" + updateOp.dynainFile;
            }
            ok = assembler.applyUpdate(updateOp);
        } else if (op.type == AssemblyOperation::DATABASE) {
            ok = assembler.applyDatabase(op.database);
        } else if (op.type == AssemblyOperation::CONTROL) {
            ok = assembler.applyControl(op.control);
        } else if (op.type == AssemblyOperation::GENERATE) {
            ok = assembler.applyGenerate(op.generate);
        } else if (op.type == AssemblyOperation::FILLET) {
            ok = assembler.applyFillet(op.fillet);
        } else if (op.type == AssemblyOperation::CNRB2SOLID) {
            ok = assembler.applyCnrb2Solid(op.cnrb2solid);
        } else if (op.type == AssemblyOperation::HFDAMP) {
            ok = assembler.applyHFDamp(op.hfdamp);
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
