#include "assembly/ModelAssembler.h"
#include "assembly/DeflectionGrid.h"
#include "assembly/FormulaEvaluator.h"
#include "assembly/ClosedLoop.h"
#include "assembly/IndentProfile.h"
#include "assembly/ShellCurvature.h"
#include "assembly/WarpageGrid.h"
#include "parser/KFileReader.h"
#include "parser/ShellReader.h"
#include "parser/DynainWriter.h"
#include "mapper/ShellMapper.h"
#include "analysis/ElementAnalyzer.h"
#include "analysis/StrainTensor.h"
#include "analysis/StressTensor.h"
#include "analysis/MaterialModel.h"
#include "validation/ElementQualityChecker.h"
#include "validation/IntersectionDetector.h"
#include <fstream>
#include <sstream>
#include <iomanip>
#include <iostream>
#include <algorithm>
#include <limits>
#include <cmath>

namespace KooRemapper {

bool ModelAssembler::loadBaseModel(const std::string& filename) {
    // 1. Parse with KFileReader for structural queries
    KFileReader reader;
    try {
        baseMesh_ = reader.readFile(filename);
    } catch (const std::exception& e) {
        errorMessage_ = "Failed to load base model: " + std::string(e.what());
        return false;
    }

    // 2. Read raw lines for text preservation
    rawLines_.clear();
    std::ifstream file(filename);
    if (!file.is_open()) {
        errorMessage_ = "Cannot open base model for raw read: " + filename;
        return false;
    }
    std::string line;
    while (std::getline(file, line)) {
        if (!line.empty() && line.back() == '\r') {
            line.pop_back();
        }
        rawLines_.push_back(line);
    }
    file.close();

    // 3. Track max IDs
    maxNodeId_ = baseMesh_.getMaxNodeId();
    maxElementId_ = baseMesh_.getMaxElementId();

    maxPartId_ = 0;
    maxSectionId_ = 0;
    for (const auto& [pid, part] : baseMesh_.parts) {
        if (pid > maxPartId_) maxPartId_ = pid;
        if (part.sectionId > maxSectionId_) maxSectionId_ = part.sectionId;
    }
    maxMaterialId_ = 0;
    for (const auto& [mid, mat] : baseMesh_.materials) {
        if (mid > maxMaterialId_) maxMaterialId_ = mid;
    }

    return true;
}

bool ModelAssembler::loadRawOnly(const std::string& filename) {
    rawLines_.clear();
    std::ifstream file(filename);
    if (!file.is_open()) {
        errorMessage_ = "Cannot open model: " + filename;
        return false;
    }
    std::string line;
    while (std::getline(file, line)) {
        if (!line.empty() && line.back() == '\r') line.pop_back();
        rawLines_.push_back(line);
    }
    file.close();
    return true;
}

bool ModelAssembler::applyReplace(const ReplaceOperation& op, double E, double nu,
                                   const std::string& configDir) {
    // Resolve paths relative to config directory
    auto resolvePath = [&](const std::string& path) -> std::string {
        if (path.empty()) return path;
        // If absolute path, return as-is
        if (path.size() >= 2 && path[1] == ':') return path;  // Windows absolute
        if (path[0] == '/' || path[0] == '\\') return path;
        if (configDir.empty()) return path;
        return configDir + "/" + path;
    };

    std::string detailFlatPath = resolvePath(op.detailFlat);
    std::string shellBentPath = resolvePath(op.shellBent);

    // 1. Identify target part's elements and exclusive nodes
    std::set<int> partElemIds = getPartElementIds(op.targetPid);
    if (partElemIds.empty()) {
        errorMessage_ = "Part " + std::to_string(op.targetPid) + " not found in base model";
        return false;
    }

    std::set<int> partExclusiveNodes = getPartExclusiveNodeIds(op.targetPid);

    // 2. Load bent shell
    ShellReader shellReader;
    ShellMesh bentShell;
    try {
        bentShell = shellReader.readFile(shellBentPath);
    } catch (const std::exception& e) {
        errorMessage_ = "Failed to load bent shell: " + std::string(e.what());
        return false;
    }

    // 3. Load flat detail mesh
    KFileReader kReader;
    Mesh flatMesh;
    try {
        flatMesh = kReader.readFile(detailFlatPath);
    } catch (const std::exception& e) {
        errorMessage_ = "Failed to load detail flat mesh: " + std::string(e.what());
        return false;
    }

    // 4. Run ShellMapper: flat → mapped
    ShellMapper mapper;
    if (!mapper.build(bentShell)) {
        errorMessage_ = "Failed to build shell mapper: " + mapper.getErrorMessage();
        return false;
    }

    // Auto-detect thickness from flat mesh Z-range
    auto [bbMin, bbMax] = flatMesh.getBoundingBox();
    double thickness = bbMax.z - bbMin.z;

    Mesh mappedMesh;
    if (!mapper.mapMesh(flatMesh, mappedMesh, thickness)) {
        errorMessage_ = "Mapping failed: " + mapper.getErrorMessage();
        return false;
    }

    // 5. Renumber mapped mesh IDs
    int nodeIdOffset = maxNodeId_;
    int elemIdOffset = maxElementId_;

    // Build old→new node ID map
    std::map<int, int> nodeRenumber;
    for (const auto& [oldId, node] : mappedMesh.nodes) {
        nodeRenumber[oldId] = oldId + nodeIdOffset;
    }

    // Add nodes
    for (const auto& [oldId, node] : mappedMesh.nodes) {
        int newId = nodeRenumber[oldId];
        const Vector3D& pos = node.isMapped ? node.mappedPosition : node.position;
        addedNodes_.push_back({newId, pos.x, pos.y, pos.z});
    }

    // Add elements with renumbered node IDs and target PID
    for (const auto& [oldId, elem] : mappedMesh.elements) {
        AddedElement ae;
        ae.id = oldId + elemIdOffset;
        ae.pid = op.targetPid;
        ae.type = elem.type;
        for (int i = 0; i < 8; ++i) {
            auto it = nodeRenumber.find(elem.nodeIds[i]);
            ae.nodeIds[i] = (it != nodeRenumber.end()) ? it->second : elem.nodeIds[i];
        }
        addedElements_.push_back(ae);
    }

    // 6. Register removals
    removedElementIds_.insert(partElemIds.begin(), partElemIds.end());
    removedNodeIds_.insert(partExclusiveNodes.begin(), partExclusiveNodes.end());

    // 7. Prestress (optional)
    if (op.prestress) {
        // flatMesh = reference, mappedMesh = deformed (with mapped positions)
        // Create deformed mesh with mapped positions as actual positions
        Mesh defMesh;
        for (const auto& [id, node] : mappedMesh.nodes) {
            const Vector3D& pos = node.isMapped ? node.mappedPosition : node.position;
            defMesh.addNode(id, pos.x, pos.y, pos.z);
        }
        for (const auto& [id, elem] : mappedMesh.elements) {
            defMesh.addElement(elem);
        }
        // Copy part and material info from base mesh
        for (const auto& [pid, part] : baseMesh_.parts) {
            defMesh.addPart(part);
        }
        for (const auto& [mid, mat] : baseMesh_.materials) {
            defMesh.addMaterial(mat);
        }
        // Also copy to flatMesh for material lookup
        for (const auto& [pid, part] : baseMesh_.parts) {
            flatMesh.addPart(part);
        }
        for (const auto& [mid, mat] : baseMesh_.materials) {
            flatMesh.addMaterial(mat);
        }
        // Set all elements to target PID for material lookup
        for (auto& [id, elem] : flatMesh.elements) {
            elem.partId = op.targetPid;
        }
        for (auto& [id, elem] : defMesh.elements) {
            elem.partId = op.targetPid;
        }

        ElementAnalyzer analyzer;
        analyzer.setStrainType(StrainType::GREEN_LAGRANGE);
        if (E > 0 && nu > 0) {
            MaterialModel mat = MaterialModel::isotropicElastic(E, nu);
            analyzer.setMaterial(mat);
        } else {
            analyzer.setUsePartMaterials(true);
        }

        MeshAnalysisResult prestressResult = analyzer.analyzeMesh(flatMesh, defMesh);

        // Renumber element IDs in results and accumulate
        for (auto& er : prestressResult.elementResults) {
            if (er.isValid && prestressResult.hasMaterial) {
                er.elementId += elemIdOffset;
                accumulatedResults_.push_back(er);
            }
        }

        infoMessages.push_back("  Prestress: " +
            std::to_string(prestressResult.validElements) + " elements");
    }

    // 8. Update max IDs
    maxNodeId_ = nodeIdOffset + static_cast<int>(mappedMesh.getNodeCount());
    maxElementId_ = elemIdOffset + static_cast<int>(mappedMesh.getElementCount());

    replacedParts_++;

    infoMessages.push_back("  Replace Part " + std::to_string(op.targetPid) +
        ": removed " + std::to_string(partElemIds.size()) + " elements, " +
        std::to_string(partExclusiveNodes.size()) + " nodes; " +
        "added " + std::to_string(mappedMesh.getElementCount()) + " elements, " +
        std::to_string(mappedMesh.getNodeCount()) + " nodes");

    return true;
}

bool ModelAssembler::applySqueeze(const SqueezeOperation& op, double E, double nu) {
    // --- Gather nodes/elements from both base model and added (replaced) data ---

    // 1a. Base model nodes/elements (excluding already-removed ones from prior replace)
    std::set<int> basePartNodeIds;
    std::set<int> basePartElemIds;
    for (const auto& [eid, elem] : baseMesh_.getElements()) {
        if (elem.partId == op.targetPid && removedElementIds_.count(eid) == 0) {
            basePartElemIds.insert(eid);
            for (int i = 0; i < Element::NUM_NODES; ++i) {
                if (removedNodeIds_.count(elem.nodeIds[i]) == 0) {
                    basePartNodeIds.insert(elem.nodeIds[i]);
                }
            }
        }
    }

    // 1b. Added nodes/elements (from prior replace on this part)
    std::map<int, size_t> addedNodeIndex;  // nodeId → index in addedNodes_
    for (size_t i = 0; i < addedNodes_.size(); ++i) {
        addedNodeIndex[addedNodes_[i].id] = i;
    }

    std::set<int> addedPartElemIds;
    std::set<int> addedPartNodeIds;
    for (const auto& ae : addedElements_) {
        if (ae.pid == op.targetPid) {
            addedPartElemIds.insert(ae.id);
            for (int nid : ae.nodeIds) {
                addedPartNodeIds.insert(nid);
            }
        }
    }

    // 1c. Merge all
    std::set<int> allNodeIds = basePartNodeIds;
    allNodeIds.insert(addedPartNodeIds.begin(), addedPartNodeIds.end());
    int totalElements = static_cast<int>(basePartElemIds.size() + addedPartElemIds.size());

    if (allNodeIds.empty()) {
        errorMessage_ = "Part " + std::to_string(op.targetPid) + " not found for squeeze";
        return false;
    }

    // Helper: get node position (from addedNodes_ or baseMesh_)
    auto getNodePos = [&](int nid, double& x, double& y, double& z) -> bool {
        auto it = addedNodeIndex.find(nid);
        if (it != addedNodeIndex.end()) {
            x = addedNodes_[it->second].x;
            y = addedNodes_[it->second].y;
            z = addedNodes_[it->second].z;
            return true;
        }
        const auto* node = baseMesh_.getNode(nid);
        if (!node) return false;
        x = node->position.x;
        y = node->position.y;
        z = node->position.z;
        return true;
    };

    // 2. Compute bounding box center
    double minX = std::numeric_limits<double>::max();
    double minY = std::numeric_limits<double>::max();
    double minZ = std::numeric_limits<double>::max();
    double maxX = std::numeric_limits<double>::lowest();
    double maxY = std::numeric_limits<double>::lowest();
    double maxZ = std::numeric_limits<double>::lowest();

    for (int nid : allNodeIds) {
        double x, y, z;
        if (!getNodePos(nid, x, y, z)) continue;
        if (x < minX) minX = x;
        if (y < minY) minY = y;
        if (z < minZ) minZ = z;
        if (x > maxX) maxX = x;
        if (y > maxY) maxY = y;
        if (z > maxZ) maxZ = z;
    }

    double centerX = (minX + maxX) * 0.5;
    double centerY = (minY + maxY) * 0.5;
    double centerZ = (minZ + maxZ) * 0.5;

    // 3. Compute new positions
    for (int nid : allNodeIds) {
        double x, y, z;
        if (!getNodePos(nid, x, y, z)) continue;

        double newX = centerX + (x - centerX) * (1.0 + op.eps_x);
        double newY = centerY + (y - centerY) * (1.0 + op.eps_y);
        double newZ = centerZ + (z - centerZ) * (1.0 + op.eps_z);

        auto it = addedNodeIndex.find(nid);
        if (it != addedNodeIndex.end()) {
            // Modify addedNodes_ directly
            addedNodes_[it->second].x = newX;
            addedNodes_[it->second].y = newY;
            addedNodes_[it->second].z = newZ;
        } else {
            modifiedNodePositions_[nid] = Vector3D(newX, newY, newZ);
        }
    }

    // 4. Compute reverse stress for dynain
    bool hasYamlMat = (E > 0 && nu > 0 && nu < 0.5);
    bool hasKFileMat = (baseMesh_.getMaterialCount() > 0);

    // Helper: resolve material for this part
    auto getPartMaterial = [&](double& matE, double& matNu) {
        matE = 0; matNu = 0;
        if (hasYamlMat) {
            matE = E; matNu = nu;
        } else if (hasKFileMat) {
            auto partIt = baseMesh_.parts.find(op.targetPid);
            if (partIt != baseMesh_.parts.end()) {
                const MaterialData* matData = baseMesh_.getMaterial(partIt->second.materialId);
                if (matData && matData->E > 0) {
                    matE = matData->E;
                    matNu = matData->nu;
                }
            }
        }
    };

    // 4a. Base model elements
    for (int eid : basePartElemIds) {
        const auto* elem = baseMesh_.getElement(eid);
        if (!elem) continue;

        double matE = 0, matNu = 0;
        if (hasYamlMat) {
            matE = E; matNu = nu;
        } else if (hasKFileMat) {
            const MaterialData* matData = baseMesh_.getElementMaterial(*elem);
            if (matData && matData->E > 0) {
                matE = matData->E;
                matNu = matData->nu;
            }
        }
        if (matE <= 0) continue;

        StrainTensor reverseStrain(-op.eps_x, -op.eps_y, -op.eps_z, 0.0, 0.0, 0.0);
        StressTensor stress = StressTensor::fromStrain(reverseStrain, matE, matNu);

        ElementResult er;
        er.elementId = elem->id;
        er.stress = stress;
        er.strain = reverseStrain;
        er.isValid = true;
        er.vonMisesStress = stress.vonMises();
        er.vonMisesStrain = reverseStrain.vonMisesStrain();
        accumulatedResults_.push_back(er);
    }

    // 4b. Added elements (from prior replace)
    for (int eid : addedPartElemIds) {
        double matE = 0, matNu = 0;
        getPartMaterial(matE, matNu);
        if (matE <= 0) continue;

        StrainTensor reverseStrain(-op.eps_x, -op.eps_y, -op.eps_z, 0.0, 0.0, 0.0);
        StressTensor stress = StressTensor::fromStrain(reverseStrain, matE, matNu);

        ElementResult er;
        er.elementId = eid;
        er.stress = stress;
        er.strain = reverseStrain;
        er.isValid = true;
        er.vonMisesStress = stress.vonMises();
        er.vonMisesStrain = reverseStrain.vonMisesStrain();
        accumulatedResults_.push_back(er);
    }

    squeezedParts_++;

    std::ostringstream oss;
    oss << std::fixed << std::setprecision(4);
    oss << "  Squeeze Part " << op.targetPid << ": eps = ("
        << op.eps_x << ", " << op.eps_y << ", " << op.eps_z << "), "
        << allNodeIds.size() << " nodes, "
        << totalElements << " elements";
    infoMessages.push_back(oss.str());

    return true;
}

// --- Restack helpers ---

double ModelAssembler::getAxisCoord(const Vector3D& v, int axis) const {
    if (axis == 0) return v.x;
    if (axis == 1) return v.y;
    return v.z;
}

void ModelAssembler::setAxisCoord(double& x, double& y, double& z, int axis, double val) const {
    if (axis == 0) x = val;
    else if (axis == 1) y = val;
    else z = val;
}

int ModelAssembler::detectExtrusionAxis(const std::vector<const Element*>& elems) const {
    int bestAxis = -1;
    int bestGroupCount = static_cast<int>(elems.size()) + 1;

    for (int axis = 0; axis < 3; axis++) {
        std::vector<double> coords;
        for (const auto* elem : elems) {
            Vector3D centroid = baseMesh_.getElementCentroid(*elem);
            coords.push_back(getAxisCoord(centroid, axis));
        }
        std::sort(coords.begin(), coords.end());

        double range = coords.back() - coords.front();
        if (range < 1e-10) continue;

        double tol = range / (static_cast<double>(coords.size()) * 2.0);

        // Group by proximity
        int groupCount = 1;
        int groupSize = 1;
        int firstGroupSize = 0;
        bool uniform = true;
        double prevCoord = coords[0];

        for (size_t i = 1; i < coords.size(); i++) {
            if (coords[i] - prevCoord > tol) {
                if (firstGroupSize == 0) firstGroupSize = groupSize;
                else if (groupSize != firstGroupSize) { uniform = false; break; }
                groupCount++;
                groupSize = 1;
            } else {
                groupSize++;
            }
            prevCoord = coords[i];
        }
        // Check last group
        if (firstGroupSize == 0) firstGroupSize = groupSize;
        else if (groupSize != firstGroupSize) uniform = false;

        if (uniform && groupCount > 1 &&
            static_cast<int>(elems.size()) % groupCount == 0 &&
            groupCount < bestGroupCount) {
            bestAxis = axis;
            bestGroupCount = groupCount;
        }
    }
    return bestAxis;
}

bool ModelAssembler::applyRestack(const RestackOperation& op, double E, double nu) {
    // 1. Collect target part elements
    std::vector<const Element*> partElems;
    for (const auto& [eid, elem] : baseMesh_.getElements()) {
        if (elem.partId == op.targetPid && removedElementIds_.count(eid) == 0) {
            partElems.push_back(&elem);
        }
    }
    if (partElems.empty()) {
        errorMessage_ = "Part " + std::to_string(op.targetPid) + " not found for restack";
        return false;
    }

    // 2. Detect extrusion direction
    int axis = -1;
    if (op.direction == "x") axis = 0;
    else if (op.direction == "y") axis = 1;
    else if (op.direction == "z") axis = 2;
    else axis = detectExtrusionAxis(partElems);

    if (axis < 0) {
        errorMessage_ = "Part " + std::to_string(op.targetPid) +
            ": not an extruded mesh (could not detect extrusion axis)";
        return false;
    }

    std::string axisName = (axis == 0) ? "X" : (axis == 1) ? "Y" : "Z";

    // 3. Collect all nodes of this part
    std::set<int> partNodeIds;
    for (const auto* elem : partElems) {
        for (int n = 0; n < 8; n++) {
            partNodeIds.insert(elem->nodeIds[n]);
        }
    }

    // 4. Build node columns
    // Group nodes by their 2D projection perpendicular to extrusion axis
    struct Column {
        std::vector<std::pair<double, int>> coordAndId; // (axis_coord, nodeId) sorted
    };

    // tolerance for 2D grouping
    double axisMin = std::numeric_limits<double>::max();
    double axisMax = std::numeric_limits<double>::lowest();
    for (int nid : partNodeIds) {
        const auto* node = baseMesh_.getNode(nid);
        if (!node) continue;
        double c = getAxisCoord(node->position, axis);
        if (c < axisMin) axisMin = c;
        if (c > axisMax) axisMax = c;
    }
    double originalThickness = axisMax - axisMin;
    if (originalThickness < 1e-12) {
        errorMessage_ = "Part " + std::to_string(op.targetPid) + ": zero thickness along " + axisName;
        return false;
    }

    // Get perpendicular coordinates for grouping
    int perpAxis1 = (axis + 1) % 3;
    int perpAxis2 = (axis + 2) % 3;

    // Group nodes into columns by perpendicular coords
    struct NodeInfo {
        int id;
        double perpCoord1, perpCoord2, axisCoord;
    };
    std::vector<NodeInfo> nodeInfos;
    for (int nid : partNodeIds) {
        const auto* node = baseMesh_.getNode(nid);
        if (!node) continue;
        NodeInfo ni;
        ni.id = nid;
        ni.perpCoord1 = getAxisCoord(node->position, perpAxis1);
        ni.perpCoord2 = getAxisCoord(node->position, perpAxis2);
        ni.axisCoord = getAxisCoord(node->position, axis);
        nodeInfos.push_back(ni);
    }

    double perpTol = originalThickness * 0.001;

    std::vector<Column> columns;
    std::map<int, int> nodeToColumn; // nodeId → column index
    std::map<int, int> nodeToPlane;  // nodeId → plane index within column

    // Use sorted-map lookup keyed by quantized perp coords: O(N log N) vs O(N²)
    std::map<std::pair<long long, long long>, int> columnLookup;
    for (auto& ni : nodeInfos) {
        long long k1 = static_cast<long long>(std::round(ni.perpCoord1 / perpTol));
        long long k2 = static_cast<long long>(std::round(ni.perpCoord2 / perpTol));
        auto key = std::make_pair(k1, k2);
        auto it = columnLookup.find(key);
        int foundCol;
        if (it != columnLookup.end()) {
            foundCol = it->second;
        } else {
            foundCol = static_cast<int>(columns.size());
            columns.push_back(Column());
            columnLookup[key] = foundCol;
        }
        columns[foundCol].coordAndId.push_back({ni.axisCoord, ni.id});
        nodeToColumn[ni.id] = foundCol;
    }

    // Sort each column by axis coordinate and assign plane indices
    for (auto& col : columns) {
        std::sort(col.coordAndId.begin(), col.coordAndId.end());
        for (int p = 0; p < static_cast<int>(col.coordAndId.size()); p++) {
            nodeToPlane[col.coordAndId[p].second] = p;
        }
    }

    // 5. Verify: all columns have same node count
    int nodesPerColumn = static_cast<int>(columns[0].coordAndId.size());
    for (const auto& col : columns) {
        if (static_cast<int>(col.coordAndId.size()) != nodesPerColumn) {
            errorMessage_ = "Part " + std::to_string(op.targetPid) +
                ": non-uniform column heights - not a valid extrusion";
            return false;
        }
    }
    int oldLayerCount = nodesPerColumn - 1;

    // 6. Extract footprint from bottom layer
    // Each footprint entry: 4 column indices in correct HEX8 winding order
    struct FootprintQuad {
        std::array<int, 4> colIdx; // column indices for bottom face, in order
    };
    std::vector<FootprintQuad> footprint;

    for (const auto* elem : partElems) {
        // Only process elements in the bottom layer (all bottom-face nodes at plane 0)
        int bottomCount = 0;
        for (int n = 0; n < 8; n++) {
            int plane = nodeToPlane[elem->nodeIds[n]];
            if (plane == 0) bottomCount++;
        }
        if (bottomCount != 4) continue; // Not in bottom layer

        // Identify bottom face nodes (plane 0) and top face nodes (plane 1)
        // Preserve the ordering: bottom = local 0,1,2,3 or whatever maps to plane 0
        std::array<int, 4> bottomNodes, topNodes;
        int bIdx = 0, tIdx = 0;
        std::array<int, 4> bottomLocalPos, topLocalPos;

        for (int n = 0; n < 8; n++) {
            int plane = nodeToPlane[elem->nodeIds[n]];
            if (plane == 0) {
                bottomLocalPos[bIdx] = n;
                bottomNodes[bIdx] = elem->nodeIds[n];
                bIdx++;
            } else {
                topLocalPos[tIdx] = n;
                topNodes[tIdx] = elem->nodeIds[n];
                tIdx++;
            }
        }

        // Map to column indices and verify column pairing
        FootprintQuad fq;
        for (int b = 0; b < 4; b++) {
            fq.colIdx[b] = nodeToColumn[bottomNodes[b]];
        }
        footprint.push_back(fq);
    }

    if (footprint.empty()) {
        errorMessage_ = "Part " + std::to_string(op.targetPid) + ": could not extract footprint";
        return false;
    }

    // 7. Prepare new layers
    int newLayerCount = static_cast<int>(op.layers.size());
    double sumThickness = 0;
    for (const auto& layer : op.layers) sumThickness += layer.thickness;

    // Resolve numElements per layer (element_size auto or explicit num_elements)
    std::vector<int> numElemsPerLayer(newLayerCount, 1);
    for (int i = 0; i < newLayerCount; i++) {
        int n = op.layers[i].numElements;
        if (n > 0) {
            numElemsPerLayer[i] = n;
        } else if (op.elementSize > 0.0) {
            numElemsPerLayer[i] = std::max(1, static_cast<int>(std::round(op.layers[i].thickness / op.elementSize)));
        }
    }
    int totalElements = 0;
    for (int n : numElemsPerLayer) totalElements += n;

    // Build MID placeholder → actual ID mapping
    std::map<std::string, int> midMapping;
    for (const auto& layer : op.layers) {
        // Scan for MIDxxx patterns
        size_t pos = 0;
        while ((pos = layer.materialCard.find("MID", pos)) != std::string::npos) {
            size_t start = pos;
            pos += 3;
            if (pos < layer.materialCard.size() && std::isdigit(layer.materialCard[pos])) {
                size_t end = pos;
                while (end < layer.materialCard.size() && std::isdigit(layer.materialCard[end])) end++;
                std::string placeholder = layer.materialCard.substr(start, end - start);
                if (midMapping.find(placeholder) == midMapping.end()) {
                    midMapping[placeholder] = ++maxMaterialId_;
                }
                pos = end;
            }
        }
    }

    // 8. Generate new node planes
    // totalElements+1 planes for the whole column.
    // plane boundaries: each layer boundary is at cumulative thickness fractions;
    // within a layer with numElements=N, N-1 intermediate planes are evenly spaced.
    struct NewColumn {
        std::vector<int> nodeIds; // totalElements+1 entries
    };
    std::vector<NewColumn> newColumns(columns.size());

    // Precompute the fraction (0..1) for each of the totalElements+1 planes
    std::vector<double> planeFrac(totalElements + 1);
    planeFrac[0] = 0.0;
    {
        int planeIdx = 0;
        double cumThick = 0.0;
        for (int li = 0; li < newLayerCount; li++) {
            double lt = op.layers[li].thickness;
            int ne = numElemsPerLayer[li];
            for (int e = 1; e <= ne; e++) {
                planeFrac[++planeIdx] = (cumThick + lt * e / ne) / sumThickness;
            }
            cumThick += lt;
        }
    }

    std::set<int> bottomPlaneNodes, topPlaneNodes;
    for (int c = 0; c < static_cast<int>(columns.size()); c++) {
        auto& newCol = newColumns[c];
        newCol.nodeIds.resize(totalElements + 1);

        int bottomNodeId = columns[c].coordAndId[0].second;
        int topNodeId = columns[c].coordAndId[nodesPerColumn - 1].second;
        bottomPlaneNodes.insert(bottomNodeId);
        topPlaneNodes.insert(topNodeId);

        const auto* bottomNode = baseMesh_.getNode(bottomNodeId);
        const auto* topNode = baseMesh_.getNode(topNodeId);

        newCol.nodeIds[0] = bottomNodeId;
        newCol.nodeIds[totalElements] = topNodeId;

        // Create intermediate planes
        for (int p = 1; p < totalElements; p++) {
            double frac = planeFrac[p];
            double nx = bottomNode->position.x + frac * (topNode->position.x - bottomNode->position.x);
            double ny = bottomNode->position.y + frac * (topNode->position.y - bottomNode->position.y);
            double nz = bottomNode->position.z + frac * (topNode->position.z - bottomNode->position.z);

            int newId = ++maxNodeId_;
            newCol.nodeIds[p] = newId;
            addedNodes_.push_back({newId, nx, ny, nz});
        }
    }

    // Build colNodeXYZ lookup: nodeId → {x,y,z} for all plane nodes across all columns.
    // Used to create independent duplicate nodes for shell layers (so shell is not
    // topologically attached to adjacent solids and tied contacts work on both sides).
    std::unordered_map<int, std::array<double,3>> colNodeXYZ;
    colNodeXYZ.reserve(static_cast<int>(columns.size()) * (totalElements + 1));
    for (int c = 0; c < static_cast<int>(columns.size()); c++) {
        const auto* bn = baseMesh_.getNode(columns[c].coordAndId[0].second);
        const auto* tn = baseMesh_.getNode(columns[c].coordAndId[nodesPerColumn - 1].second);
        double bx = bn->position.x, by = bn->position.y, bz = bn->position.z;
        double tx = tn->position.x, ty = tn->position.y, tz = tn->position.z;
        for (int p = 0; p <= totalElements; p++) {
            double frac = planeFrac[p];
            colNodeXYZ[newColumns[c].nodeIds[p]] = {
                bx + frac * (tx - bx),
                by + frac * (ty - by),
                bz + frac * (tz - bz)
            };
        }
    }

    // 9. Remove old elements and intermediate (exclusive) nodes
    std::set<int> partExclusive = getPartExclusiveNodeIds(op.targetPid);
    for (const auto* elem : partElems) {
        removedElementIds_.insert(elem->id);
    }
    // Remove exclusive intermediate nodes (keep bottom and top plane nodes)
    for (int nid : partExclusive) {
        if (bottomPlaneNodes.count(nid) == 0 && topPlaneNodes.count(nid) == 0) {
            removedNodeIds_.insert(nid);
        }
    }

    // 10. Generate new elements and keyword cards per layer

    std::set<int> emittedMids; // Track which MIDs have already been written
    std::vector<std::pair<int, std::string>> layerPidEtype; // (pid, effectiveEtype) per layer

    int totalNewElems = 0;
    for (int layerIdx = 0; layerIdx < newLayerCount; layerIdx++) {
        const auto& layerDef = op.layers[layerIdx];

        // Per-layer element type (fallback to operation-level)
        std::string layerEtype = layerDef.elementType.empty() ? op.elementType : layerDef.elementType;
        bool isShell  = (layerEtype == "shell");
        bool isTshell = (layerEtype == "tshell");

        // Assign new PID and SECID for this layer
        int newPid = ++maxPartId_;
        int newSecId = ++maxSectionId_;
        layerPidEtype.push_back({newPid, layerEtype});

        // Resolve material card with actual MID
        std::string matCard = layerDef.materialCard;
        int actualMid = 0;
        for (const auto& [placeholder, mid] : midMapping) {
            size_t pos = 0;
            while ((pos = matCard.find(placeholder, pos)) != std::string::npos) {
                std::string midStr = std::to_string(mid);
                // Right-justify the MID in the same field width
                while (midStr.size() < placeholder.size()) midStr = " " + midStr;
                matCard.replace(pos, placeholder.size(), midStr);
                actualMid = mid;
                pos += midStr.size();
            }
        }

        // Find which MID is used in this layer's card
        if (actualMid == 0) {
            for (const auto& [placeholder, mid] : midMapping) {
                if (layerDef.materialCard.find(placeholder) != std::string::npos) {
                    actualMid = mid;
                    break;
                }
            }
        }

        // Generate keyword block for this layer
        std::ostringstream kwBlock;

        // Material card - only emit once per unique MID (skip duplicates)
        if (emittedMids.find(actualMid) == emittedMids.end()) {
            kwBlock << matCard << "\n";
            emittedMids.insert(actualMid);
        }

        // Section card
        if (isShell) {
            kwBlock << "*SECTION_SHELL\n";
            kwBlock << "$#  secid    elform      shrf       nip     propt\n";
            kwBlock << std::setw(10) << newSecId << "         2       1.0         2       0.0\n";
            kwBlock << "$#     t1        t2        t3        t4      nloc\n";
            kwBlock << std::setw(10) << std::fixed << std::setprecision(6) << layerDef.thickness
                    << std::setw(10) << std::fixed << std::setprecision(6) << layerDef.thickness
                    << std::setw(10) << std::fixed << std::setprecision(6) << layerDef.thickness
                    << std::setw(10) << std::fixed << std::setprecision(6) << layerDef.thickness
                    << "       0.0\n";  // NLOC=0: mid-plane reference → shell nodes at mid-Z, spans [pBot_Z, pTop_Z]
        } else if (isTshell) {
            kwBlock << "*SECTION_TSHELL\n";
            kwBlock << "$#  secid    elform\n";
            kwBlock << std::setw(10) << newSecId << "         1\n";
        } else {
            kwBlock << "*SECTION_SOLID\n";
            kwBlock << "$#  secid    elform\n";
            kwBlock << std::setw(10) << newSecId << "         1\n";
        }

        // Part card
        std::string partTitle = layerDef.title.empty()
            ? ("Restack Layer " + std::to_string(layerIdx + 1))
            : layerDef.title;
        kwBlock << "*PART\n";
        kwBlock << partTitle << "\n";
        kwBlock << "$#     pid     secid       mid\n";
        kwBlock << std::setw(10) << newPid << std::setw(10) << newSecId << std::setw(10) << actualMid << "\n";

        addedKeywordBlocks_.push_back(kwBlock.str());

        // Generate elements (numElemsPerLayer[layerIdx] sub-elements in thickness)
        int planeBase = 0;
        for (int li = 0; li < layerIdx; li++) planeBase += numElemsPerLayer[li];

        // Shell layers: create new nodes at the MID-PLANE of the thickness slot.
        // Nodes are independent (not shared with adjacent solids) and sit visually
        // between the solid layers above and below.  NLOC=0 (mid-plane ref in
        // SECTION_SHELL) means the shell spans exactly [pBot_Z, pTop_Z].
        // Tied contacts on both interfaces use OFFSET to bridge the half-thickness gap.
        // Map: column index → mid-plane nodeId  (per sub-element e)
        std::unordered_map<int, int> shellDupMap;

        for (int e = 0; e < numElemsPerLayer[layerIdx]; e++) {
            int pBot = planeBase + e;
            int pTop = planeBase + e + 1;
            double fracMid = (planeFrac[pBot] + planeFrac[pTop]) * 0.5;
            shellDupMap.clear();  // new plane → new set of mid-plane nodes

            for (const auto& fq : footprint) {
                if (isShell) {
                    AddedShellElement se;
                    se.id = ++maxElementId_;
                    se.pid = newPid;
                    for (int n = 0; n < 4; n++) {
                        int colIdx = fq.colIdx[n];
                        auto it = shellDupMap.find(colIdx);
                        if (it == shellDupMap.end()) {
                            // Create node at mid-plane Z of this shell slot
                            const auto* bn = baseMesh_.getNode(columns[colIdx].coordAndId[0].second);
                            const auto* tn = baseMesh_.getNode(columns[colIdx].coordAndId[nodesPerColumn - 1].second);
                            double nx = bn->position.x + fracMid * (tn->position.x - bn->position.x);
                            double ny = bn->position.y + fracMid * (tn->position.y - bn->position.y);
                            double nz = bn->position.z + fracMid * (tn->position.z - bn->position.z);
                            int dupId = ++maxNodeId_;
                            addedNodes_.push_back({dupId, nx, ny, nz});
                            shellDupMap[colIdx] = dupId;
                            it = shellDupMap.find(colIdx);
                        }
                        se.nodeIds[n] = it->second;
                    }
                    addedShellElements_.push_back(se);
                } else {
                    AddedElement ae;
                    ae.id = ++maxElementId_;
                    ae.pid = newPid;
                    ae.type = ElementType::HEX8;
                    ae.isTshell = isTshell;
                    for (int n = 0; n < 4; n++) {
                        ae.nodeIds[n]     = newColumns[fq.colIdx[n]].nodeIds[pBot];
                        ae.nodeIds[n + 4] = newColumns[fq.colIdx[n]].nodeIds[pTop];
                    }
                    addedElements_.push_back(ae);
                }
                totalNewElems++;
            }
        }
    }

    // 11. Thickness mismatch → squeeze initial stress
    double thicknessDiff = std::abs(sumThickness - originalThickness);
    double thicknessTol = originalThickness * 1e-6;
    bool hasMismatch = thicknessDiff > thicknessTol;

    if (hasMismatch) {
        double eps_axis = (originalThickness / sumThickness) - 1.0;
        double eps[3] = {0, 0, 0};
        eps[axis] = eps_axis;

        // For each new element, compute reverse stress
        // We need material E/nu for each layer
        for (int layerIdx = 0; layerIdx < newLayerCount; layerIdx++) {
            // Get material E,nu from YAML global material
            double matE = E, matNu = nu;
            if (matE <= 0) continue;

            StrainTensor reverseStrain(-eps[0], -eps[1], -eps[2], 0.0, 0.0, 0.0);
            StressTensor stress = StressTensor::fromStrain(reverseStrain, matE, matNu);

            // Apply to all elements in this layer
            int startElem = static_cast<int>(footprint.size()) * layerIdx;
            for (int e = 0; e < static_cast<int>(footprint.size()); e++) {
                // Find the element ID for this layer's element
                int elemIdx = static_cast<int>(addedElements_.size()) - totalNewElems + startElem + e;
                if (elemIdx < 0 || elemIdx >= static_cast<int>(addedElements_.size())) continue;

                ElementResult er;
                er.elementId = addedElements_[elemIdx].id;
                er.stress = stress;
                er.strain = reverseStrain;
                er.isValid = true;
                er.vonMisesStress = stress.vonMises();
                er.vonMisesStrain = reverseStrain.vonMisesStrain();
                accumulatedResults_.push_back(er);
            }
        }

        std::ostringstream sqMsg;
        sqMsg << std::fixed << std::setprecision(4);
        sqMsg << "  Thickness mismatch: target=" << sumThickness
              << " original=" << originalThickness
              << " squeeze_eps=" << ((originalThickness / sumThickness) - 1.0);
        infoMessages.push_back(sqMsg.str());
    }

    restackedParts_++;

    // 12. Auto-generate *CONTACT_TIED_SURFACE_TO_SURFACE_OFFSET for shell-adjacent interfaces
    // Rule: if at least one side is "shell" (not tshell/solid) → tied contact needed
    //       slave = shell layer, master = the other layer
    int tiedCount = 0;
    for (int i = 0; i + 1 < static_cast<int>(layerPidEtype.size()); i++) {
        bool iIsShell  = (layerPidEtype[i].second == "shell");
        bool i1IsShell = (layerPidEtype[i + 1].second == "shell");
        if (!iIsShell && !i1IsShell) continue;  // both solid/tshell → conformal, skip

        // slave = shell side, master = other side (if both shell: lower=slave, upper=master)
        int slavePid  = iIsShell ? layerPidEtype[i].first     : layerPidEtype[i + 1].first;
        int masterPid = iIsShell ? layerPidEtype[i + 1].first : layerPidEtype[i].first;

        std::ostringstream ct;
        ct << "*CONTACT_TIED_SURFACE_TO_SURFACE_OFFSET\n";
        ct << "$#     ssid      msid     sstyp     mstyp    sboxid    mboxid       spr       mpr\n";
        ct << std::setw(10) << slavePid
           << std::setw(10) << masterPid
           << "         3         3         0         0         1         1\n";  // sstyp/mstyp=3: part (PID), not part set
        // Card 2 is mandatory (LS-DYNA Vol_I). All defaults (FS=FD=DC=VC=VDC=0, PENCHK=0, BT=0, DT=1e20)
        ct << "$#       fs        fd        dc        vc       vdc    penchk        bt        dt\n";
        ct << "       0.0       0.0       0.0       0.0       0.0         0       0.0  1.0000E+20\n";
        // Card 3 is mandatory (LS-DYNA Vol_I). SFSA=SFSB=SFSAT=SFSBT=FSF=VSF=1, SAST=SBST=0(auto)
        ct << "$#     sfsa      sfsb      sast      sbst     sfsat     sfsbt       fsf       vsf\n";
        ct << "       1.0       1.0       0.0       0.0       1.0       1.0       1.0       1.0\n";
        addedKeywordBlocks_.push_back(ct.str());
        tiedCount++;
    }

    std::ostringstream msg;
    msg << "  Restack Part " << op.targetPid << " (" << axisName << "-axis): "
        << oldLayerCount << " layers -> " << newLayerCount << " layers ("
        << totalElements << " elements), "
        << footprint.size() << " elements/layer, "
        << columns.size() << " columns";
    if (tiedCount > 0)
        msg << ", " << tiedCount << " tied contact(s)";
    infoMessages.push_back(msg.str());

    return true;
}

bool ModelAssembler::applyBend(const BendOperation& op, double E, double nu,
                                const std::string& configDir) {
    // Resolve file paths relative to config directory
    auto resolvePath = [&](const std::string& path) -> std::string {
        if (path.empty()) return path;
        if (path.size() >= 2 && path[1] == ':') return path;  // Windows absolute
        if (path[0] == '/' || path[0] == '\\') return path;
        if (configDir.empty()) return path;
        return configDir + "/" + path;
    };

    // 1. Determine axis mapping from plane
    int inAxis1, inAxis2, normalAxis;
    if (op.plane == "xy") {
        inAxis1 = 0; inAxis2 = 1; normalAxis = 2;  // x1=X, x2=Y, normal=Z
    } else if (op.plane == "yz") {
        inAxis1 = 1; inAxis2 = 2; normalAxis = 0;  // x1=Y, x2=Z, normal=X
    } else {  // zx
        inAxis1 = 2; inAxis2 = 0; normalAxis = 1;  // x1=Z, x2=X, normal=Y
    }

    // 2. Gather nodes/elements (same pattern as applySqueeze)
    std::set<int> basePartNodeIds;
    std::set<int> basePartElemIds;
    for (const auto& [eid, elem] : baseMesh_.getElements()) {
        if (elem.partId == op.targetPid && removedElementIds_.count(eid) == 0) {
            basePartElemIds.insert(eid);
            for (int i = 0; i < Element::NUM_NODES; ++i) {
                if (removedNodeIds_.count(elem.nodeIds[i]) == 0) {
                    basePartNodeIds.insert(elem.nodeIds[i]);
                }
            }
        }
    }

    std::map<int, size_t> addedNodeIndex;
    for (size_t i = 0; i < addedNodes_.size(); ++i) {
        addedNodeIndex[addedNodes_[i].id] = i;
    }

    std::set<int> addedPartElemIds;
    std::set<int> addedPartNodeIds;
    for (const auto& ae : addedElements_) {
        if (ae.pid == op.targetPid) {
            addedPartElemIds.insert(ae.id);
            for (int nid : ae.nodeIds) {
                addedPartNodeIds.insert(nid);
            }
        }
    }

    std::set<int> allNodeIds = basePartNodeIds;
    allNodeIds.insert(addedPartNodeIds.begin(), addedPartNodeIds.end());
    int totalElements = static_cast<int>(basePartElemIds.size() + addedPartElemIds.size());

    if (allNodeIds.empty()) {
        errorMessage_ = "Part " + std::to_string(op.targetPid) + " not found for bend";
        return false;
    }

    // Helper: get/set node position
    auto getNodePos = [&](int nid, double& x, double& y, double& z) -> bool {
        // Check modified positions first
        auto modIt = modifiedNodePositions_.find(nid);
        if (modIt != modifiedNodePositions_.end()) {
            x = modIt->second.x;
            y = modIt->second.y;
            z = modIt->second.z;
            return true;
        }
        auto it = addedNodeIndex.find(nid);
        if (it != addedNodeIndex.end()) {
            x = addedNodes_[it->second].x;
            y = addedNodes_[it->second].y;
            z = addedNodes_[it->second].z;
            return true;
        }
        const auto* node = baseMesh_.getNode(nid);
        if (!node) return false;
        x = node->position.x;
        y = node->position.y;
        z = node->position.z;
        return true;
    };

    auto getCoord = [](double x, double y, double z, int axis) -> double {
        if (axis == 0) return x;
        if (axis == 1) return y;
        return z;
    };

    // 3. Compute bounding box
    double bbMin[3] = { std::numeric_limits<double>::max(),
                        std::numeric_limits<double>::max(),
                        std::numeric_limits<double>::max() };
    double bbMax[3] = { std::numeric_limits<double>::lowest(),
                        std::numeric_limits<double>::lowest(),
                        std::numeric_limits<double>::lowest() };

    for (int nid : allNodeIds) {
        double x, y, z;
        if (!getNodePos(nid, x, y, z)) continue;
        double c[3] = {x, y, z};
        for (int a = 0; a < 3; a++) {
            if (c[a] < bbMin[a]) bbMin[a] = c[a];
            if (c[a] > bbMax[a]) bbMax[a] = c[a];
        }
    }

    double x1Min = bbMin[inAxis1], x1Max = bbMax[inAxis1];
    double x2Min = bbMin[inAxis2], x2Max = bbMax[inAxis2];
    double nMin  = bbMin[normalAxis], nMax = bbMax[normalAxis];
    double nMid  = (nMin + nMax) * 0.5;  // neutral surface
    double L1 = x1Max - x1Min;
    double L2 = x2Max - x2Min;

    if (L1 < 1e-12 || L2 < 1e-12) {
        errorMessage_ = "Part " + std::to_string(op.targetPid) + ": zero extent in plane " + op.plane;
        return false;
    }

    // 4. Prepare deflection grid(s) based on source
    DeflectionGrid grid;          // Primary grid (or midplane for dat_pair)
    DeflectionGrid gridTop;       // Top surface (dat_pair only)
    DeflectionGrid gridBottom;    // Bottom surface (dat_pair only)
    bool useDatPair = (op.source == "dat_pair");

    if (op.source == "dat") {
        std::string datPath = resolvePath(op.datFile);
        if (!grid.loadFromFile(datPath)) {
            errorMessage_ = "Failed to load deflection grid: " + grid.getErrorMessage();
            return false;
        }
        grid.setRange(x1Min, x1Max, x2Min, x2Max);

    } else if (op.source == "dat_pair") {
        std::string topPath = resolvePath(op.datTop);
        std::string bottomPath = resolvePath(op.datBottom);

        if (!gridTop.loadFromFile(topPath)) {
            errorMessage_ = "Failed to load top grid: " + gridTop.getErrorMessage();
            return false;
        }
        if (!gridBottom.loadFromFile(bottomPath)) {
            errorMessage_ = "Failed to load bottom grid: " + gridBottom.getErrorMessage();
            return false;
        }

        if (gridTop.getRows() != gridBottom.getRows() ||
            gridTop.getCols() != gridBottom.getCols()) {
            errorMessage_ = "Top and bottom grids must have same dimensions";
            return false;
        }

        gridTop.setRange(x1Min, x1Max, x2Min, x2Max);
        gridBottom.setRange(x1Min, x1Max, x2Min, x2Max);

        // Compute midplane grid for curvature
        int nR = gridTop.getRows();
        int nC = gridTop.getCols();
        double dx1 = L1 / (nC - 1);
        double dx2 = L2 / (nR - 1);

        std::vector<std::vector<double>> midData(nR, std::vector<double>(nC, 0.0));
        for (int r = 0; r < nR; r++) {
            for (int c = 0; c < nC; c++) {
                double x1 = x1Min + c * dx1;
                double x2 = x2Max - r * dx2;  // row 0 = x2Max
                double wTop = gridTop.getDeflection(x1, x2);
                double wBot = gridBottom.getDeflection(x1, x2);
                midData[r][c] = (wTop + wBot) * 0.5;
            }
        }
        grid.setData(midData);
        grid.setRange(x1Min, x1Max, x2Min, x2Max);

    } else if (op.source == "formula") {
        // Evaluate formula on a 101x101 grid
        const int gridRes = 101;
        FormulaEvaluator evaluator;
        evaluator.setVariable("L1", L1);
        evaluator.setVariable("L2", L2);

        std::vector<std::vector<double>> gridData(gridRes, std::vector<double>(gridRes, 0.0));

        try {
            for (int r = 0; r < gridRes; r++) {
                double x2 = x2Max - r * L2 / (gridRes - 1);  // row 0 = x2Max
                evaluator.setVariable("x2", x2 - x2Min);     // x2 relative to min
                for (int c = 0; c < gridRes; c++) {
                    double x1 = x1Min + c * L1 / (gridRes - 1);
                    evaluator.setVariable("x1", x1 - x1Min);  // x1 relative to min
                    gridData[r][c] = evaluator.evaluate(op.expression);
                }
            }
        } catch (const std::exception& e) {
            errorMessage_ = "Formula evaluation error: " + std::string(e.what());
            return false;
        }

        grid.setData(gridData);
        grid.setRange(x1Min, x1Max, x2Min, x2Max);
    }

    // 5. Compute bending stress BEFORE deformation (use original positions)
    bool hasYamlMat = (E > 0 && nu > 0 && nu < 0.5);

    auto getPartMaterial = [&](double& matE, double& matNu) {
        matE = 0; matNu = 0;
        if (hasYamlMat) {
            matE = E; matNu = nu;
        } else {
            auto partIt = baseMesh_.parts.find(op.targetPid);
            if (partIt != baseMesh_.parts.end()) {
                const MaterialData* matData = baseMesh_.getMaterial(partIt->second.materialId);
                if (matData && matData->E > 0) {
                    matE = matData->E;
                    matNu = matData->nu;
                }
            }
        }
    };

    auto computeBendStress = [&](int eid, const int* nodeIds, int numNodes) {
        // Compute element centroid from ORIGINAL (pre-bend) positions
        double cx = 0, cy = 0, cz = 0;
        int validNodes = 0;
        for (int n = 0; n < numNodes; n++) {
            double nx, ny, nz;
            if (!getNodePos(nodeIds[n], nx, ny, nz)) continue;
            cx += nx; cy += ny; cz += nz;
            validNodes++;
        }
        if (validNodes == 0) return;
        cx /= validNodes; cy /= validNodes; cz /= validNodes;

        double cc[3] = {cx, cy, cz};
        double x1_c = cc[inAxis1];
        double x2_c = cc[inAxis2];
        double n_c  = cc[normalAxis];
        double d = n_c - nMid;

        // Get curvature at element center
        double k11, k22, k12;
        grid.getCurvature(x1_c, x2_c, k11, k22, k12);

        // Bending strain (plate theory)
        // strain_11 = -d * kappa_11, but kappa already has sign convention kappa = -d2w/dx2
        // so strain_11 = -d * kappa_11 = -d * (-d2w/dx1^2) = d * d2w/dx1^2
        // Actually with our sign convention kappa = -d2w/dx^2:
        //   eps = -d * kappa = -d * (-d2w/dx^2) = d * d2w/dx^2
        // This gives tension (+) on the side away from center of curvature, which is correct.
        double eps_11 = -d * k11;
        double eps_22 = -d * k22;
        double gamma_12 = -2.0 * d * k12;

        // Map local bending strain to global 6-component strain
        // inAxis1 → 11 direction, inAxis2 → 22 direction
        double eps[6] = {0, 0, 0, 0, 0, 0};  // xx, yy, zz, xy, yz, xz

        // Normal strains
        if (inAxis1 == 0) eps[0] = eps_11;       // xx
        else if (inAxis1 == 1) eps[1] = eps_11;   // yy
        else eps[2] = eps_11;                      // zz

        if (inAxis2 == 0) eps[0] = eps_22;
        else if (inAxis2 == 1) eps[1] = eps_22;
        else eps[2] = eps_22;

        // Shear strain: gamma_12 maps to the shear between inAxis1 and inAxis2
        if ((inAxis1 == 0 && inAxis2 == 1) || (inAxis1 == 1 && inAxis2 == 0))
            eps[3] = gamma_12;  // xy
        else if ((inAxis1 == 1 && inAxis2 == 2) || (inAxis1 == 2 && inAxis2 == 1))
            eps[4] = gamma_12;  // yz
        else
            eps[5] = gamma_12;  // xz

        StrainTensor strain(eps[0], eps[1], eps[2], eps[3], eps[4], eps[5]);

        // Material
        double matE, matNu;
        if (hasYamlMat) {
            matE = E; matNu = nu;
        } else {
            // Try element-specific material from base mesh
            const auto* elem = baseMesh_.getElement(eid);
            if (elem) {
                const MaterialData* matData = baseMesh_.getElementMaterial(*elem);
                if (matData && matData->E > 0) {
                    matE = matData->E;
                    matNu = matData->nu;
                } else {
                    getPartMaterial(matE, matNu);
                }
            } else {
                getPartMaterial(matE, matNu);
            }
        }
        if (matE <= 0) return;

        // Stress sign convention
        StressTensor stress;
        if (op.mode == "deform") {
            // Reverse stress (like squeeze): holds bent shape during DR
            StrainTensor reverseStrain = strain * (-1.0);
            stress = StressTensor::fromStrain(reverseStrain, matE, matNu);
        } else {
            // Forward stress: drives flat→bent during DR
            stress = StressTensor::fromStrain(strain, matE, matNu);
        }

        ElementResult er;
        er.elementId = eid;
        er.stress = stress;
        er.strain = strain;
        er.isValid = true;
        er.vonMisesStress = stress.vonMises();
        er.vonMisesStrain = strain.vonMisesStrain();
        accumulatedResults_.push_back(er);
    };

    // 5a. Base model elements
    for (int eid : basePartElemIds) {
        const auto* elem = baseMesh_.getElement(eid);
        if (!elem) continue;
        computeBendStress(eid, elem->nodeIds.data(), Element::NUM_NODES);
    }

    // 5b. Added elements
    for (const auto& ae : addedElements_) {
        if (ae.pid == op.targetPid) {
            computeBendStress(ae.id, ae.nodeIds.data(), 8);
        }
    }

    // 6. Apply node displacements AFTER stress computation (deform mode only)
    if (op.mode == "deform") {
        for (int nid : allNodeIds) {
            double x, y, z;
            if (!getNodePos(nid, x, y, z)) continue;

            double c[3] = {x, y, z};
            double x1_coord = c[inAxis1];
            double x2_coord = c[inAxis2];
            double n_coord = c[normalAxis];
            double d = n_coord - nMid;

            double w, dw_dx1, dw_dx2;
            if (useDatPair) {
                double thickness = nMax - nMin;
                double t_frac = (thickness > 1e-12) ? (n_coord - nMin) / thickness : 0.5;
                double wTop = gridTop.getDeflection(x1_coord, x2_coord);
                double wBot = gridBottom.getDeflection(x1_coord, x2_coord);
                w = wBot * (1.0 - t_frac) + wTop * t_frac;
                grid.getSlope(x1_coord, x2_coord, dw_dx1, dw_dx2);
            } else {
                w = grid.getDeflection(x1_coord, x2_coord);
                grid.getSlope(x1_coord, x2_coord, dw_dx1, dw_dx2);
            }

            double delta[3] = {0, 0, 0};
            delta[normalAxis] = w;
            delta[inAxis1]    = -d * dw_dx1;
            delta[inAxis2]    = -d * dw_dx2;

            double newX = x + delta[0];
            double newY = y + delta[1];
            double newZ = z + delta[2];

            auto it = addedNodeIndex.find(nid);
            if (it != addedNodeIndex.end()) {
                addedNodes_[it->second].x = newX;
                addedNodes_[it->second].y = newY;
                addedNodes_[it->second].z = newZ;
            } else {
                modifiedNodePositions_[nid] = Vector3D(newX, newY, newZ);
            }
        }
    }

    bentParts_++;

    std::string planeName;
    if (op.plane == "xy") planeName = "XY";
    else if (op.plane == "yz") planeName = "YZ";
    else planeName = "ZX";

    std::ostringstream msg;
    msg << "  Bend Part " << op.targetPid
        << " (" << planeName << " plane, " << op.mode << ", " << op.source << "): "
        << allNodeIds.size() << " nodes, " << totalElements << " elements";
    infoMessages.push_back(msg.str());

    return true;
}

bool ModelAssembler::writeOutput(const std::string& outputPrefix) {
    std::string outputFile = outputPrefix + ".k";
    std::string dynainFile = outputPrefix + ".dynain";

    // Get dynain basename for *INCLUDE
    std::string dynainBasename = dynainFile;
    size_t slashPos = dynainBasename.find_last_of("/\\");
    if (slashPos != std::string::npos) {
        dynainBasename = dynainBasename.substr(slashPos + 1);
    }

    // Pre-scan: detect existing DR-related keywords
    bool hasDR = false;
    bool hasTermination = false;
    if (dynamicRelaxation_) {
        for (const auto& rawLine : rawLines_) {
            std::string upper = rawLine;
            size_t s = upper.find_first_not_of(" \t");
            if (s != std::string::npos) upper = upper.substr(s);
            std::transform(upper.begin(), upper.end(), upper.begin(), [](unsigned char c){ return (char)std::toupper(c); });
            if (upper.substr(0, 32) == "*CONTROL_DYNAMIC_RELAXATION") hasDR = true;
            if (upper.substr(0, 22) == "*CONTROL_TERMINATION") hasTermination = true;
        }
    }

    // Merge stress results: same element from multiple operations → sum stresses
    if (accumulatedResults_.size() > 1) {
        std::map<int, ElementResult> merged;
        for (const auto& er : accumulatedResults_) {
            if (!er.isValid) continue;
            auto it = merged.find(er.elementId);
            if (it != merged.end()) {
                it->second.stress += er.stress;
                it->second.strain += er.strain;
                if (er.isShell) {
                    it->second.isShell = true;
                    it->second.shellThickness = er.shellThickness;
                    it->second.stressTop += er.stressTop;
                    it->second.stressBottom += er.stressBottom;
                    it->second.epsTop = std::max(it->second.epsTop, er.epsTop);
                    it->second.epsBottom = std::max(it->second.epsBottom, er.epsBottom);
                }
                it->second.vonMisesStress = it->second.stress.vonMises();
                it->second.vonMisesStrain = it->second.strain.vonMisesStrain();
            } else {
                merged[er.elementId] = er;
            }
        }
        // Replace with merged results
        accumulatedResults_.clear();
        accumulatedResults_.reserve(merged.size());
        for (auto& [eid, er] : merged) {
            accumulatedResults_.push_back(std::move(er));
        }
    }

    // Process raw lines
    std::ostringstream output;

    enum class Section { NONE, NODE, ELEMENT, SHELL_ELEMENT };
    Section currentSection = Section::NONE;
    bool nodesInserted = false;
    bool elementsInserted = false;
    bool shellElementsHandled = false;     // track shell element section processing
    bool skippingReplacedSection = false;  // for skipping old TERMINATION data
    bool inSectionSolid = false;           // tracking *SECTION_SOLID for ELFORM rewrite
    int sectionSolidDataLine = 0;          // data line counter within *SECTION_SOLID
    bool inSectionShell = false;           // tracking *SECTION_SHELL for ELFORM rewrite
    int sectionShellDataLine = 0;          // data line counter within *SECTION_SHELL
    bool inDowngradeElement = false;        // true while inside a multi-line element being downgraded
    bool skipSectionSolidPeri = false;     // true when skipping SECTION_SOLID to be replaced by PERI

    for (size_t i = 0; i < rawLines_.size(); ++i) {
        const std::string& line = rawLines_[i];
        std::string trimmed = line;
        size_t start = trimmed.find_first_not_of(" \t");
        if (start != std::string::npos) {
            trimmed = trimmed.substr(start);
        } else {
            trimmed = "";
        }

        // Skip old section data (comment + data lines) until next keyword
        if (skippingReplacedSection) {
            if (!trimmed.empty() && trimmed[0] == '*' && !isCommentLine(line)) {
                skippingReplacedSection = false;
                // Fall through to process this keyword line normally
            } else {
                continue;  // Skip comment and data lines of replaced section
            }
        }

        // Detect keyword transitions
        if (!trimmed.empty() && trimmed[0] == '*' && !isCommentLine(line)) {
            // Before leaving current section, insert added content
            if (currentSection == Section::NODE && !nodesInserted) {
                for (const auto& an : addedNodes_) {
                    output << formatNodeLine(an.id, an.x, an.y, an.z) << "\n";
                }
                nodesInserted = true;
            }
            if (currentSection == Section::ELEMENT && !elementsInserted) {
                // Only insert non-tshell (solid) elements here; tshell go before *END
                for (const auto& ae : addedElements_) {
                    if (!ae.isTshell) output << formatElementLine(ae) << "\n";
                }
                elementsInserted = true;
            }

            // Detect section type
            std::string upper = trimmed;
            std::transform(upper.begin(), upper.end(), upper.begin(), [](unsigned char c){ return (char)std::toupper(c); });

            // Handle *CONTROL_TERMINATION replacement for DR
            if (dynamicRelaxation_ && hasTermination &&
                upper.substr(0, 20) == "*CONTROL_TERMINATION") {
                // Replace with DR-compatible termination (endtim=0 for DR-only)
                output << "*CONTROL_TERMINATION\n";
                output << "$#  endtim    endcyc     dtmin    endeng    endmas     nosol\n";
                output << "       0.0         0       0.0       0.0       0.01e+20         0\n";
                skippingReplacedSection = true;
                currentSection = Section::NONE;
                continue;
            }

            // Track *SECTION_SOLID for ELFORM rewriting
            if (upper.find("*SECTION_SOLID") == 0 && upper.find("*SECTION_SOLID_") == std::string::npos) {
                inSectionSolid = true;
                sectionSolidDataLine = 0;
                skipSectionSolidPeri = false;
                // Peridynamics: lookahead to check SECID and replace keyword line
                if (!periSectionIds_.empty()) {
                    for (size_t j = i + 1; j < rawLines_.size(); ++j) {
                        const std::string& nxt = rawLines_[j];
                        if (isCommentLine(nxt) || nxt.find_first_not_of(" \t") == std::string::npos) continue;
                        if (!nxt.empty() && nxt[0] == '*') break;
                        try {
                            int secId = std::stoi(nxt.substr(0, 10));
                            if (periSectionIds_.count(secId)) {
                                skipSectionSolidPeri = true;
                                goto continueMainLoop;  // Skip *SECTION_SOLID keyword line entirely
                            }
                        } catch (...) {}
                        break;
                    }
                }
            } else if (inSectionSolid && upper[0] == '*') {
                inSectionSolid = false;
                skipSectionSolidPeri = false;
            }

            // Track *SECTION_SHELL for ELFORM rewriting
            if (upper.find("*SECTION_SHELL") == 0 && upper.find("*SECTION_SHELL_") == std::string::npos) {
                inSectionShell = true;
                sectionShellDataLine = 0;
            } else if (inSectionShell && upper[0] == '*') {
                inSectionShell = false;
            }

            if (upper.substr(0, 5) == "*NODE") {
                currentSection = Section::NODE;
            } else if (upper.substr(0, 14) == "*ELEMENT_SOLID") {
                currentSection = Section::ELEMENT;
            } else if (upper.find("*ELEMENT_SHELL") == 0) {
                currentSection = Section::SHELL_ELEMENT;
                shellElementsHandled = true;
            } else if (upper.substr(0, 4) == "*END") {
                currentSection = Section::NONE;

                // Insert remaining additions if not yet done
                if (!nodesInserted) {
                    output << "*NODE\n";
                    for (const auto& an : addedNodes_) {
                        output << formatNodeLine(an.id, an.x, an.y, an.z) << "\n";
                    }
                    nodesInserted = true;
                }
                if (!elementsInserted) {
                    // Separate solid vs tshell elements
                    bool hasSolid = false, hasTshell = false;
                    for (const auto& ae : addedElements_) {
                        if (ae.isTshell) hasTshell = true;
                        else hasSolid = true;
                    }
                    if (hasSolid) {
                        output << "*ELEMENT_SOLID\n";
                        for (const auto& ae : addedElements_) {
                            if (!ae.isTshell) output << formatElementLine(ae) << "\n";
                        }
                    }
                    if (hasTshell) {
                        output << "*ELEMENT_TSHELL\n";
                        for (const auto& ae : addedElements_) {
                            if (ae.isTshell) output << formatElementLine(ae) << "\n";
                        }
                    }
                    if (!hasSolid && !hasTshell && !addedElements_.empty()) {
                        output << "*ELEMENT_SOLID\n";
                        for (const auto& ae : addedElements_) {
                            output << formatElementLine(ae) << "\n";
                        }
                    }
                    elementsInserted = true;
                }

                // Insert shell elements if any
                if (!addedShellElements_.empty()) {
                    output << "*ELEMENT_SHELL\n";
                    for (const auto& se : addedShellElements_) {
                        output << formatShellElementLine(se) << "\n";
                    }
                }

                // Insert keyword blocks (MAT/SECTION/PART from restack)
                for (const auto& block : addedKeywordBlocks_) {
                    output << block;
                }

                // Insert dynain before *END
                if (!accumulatedResults_.empty()) {
                    if (dynainEmbed_) {
                        // Separate solid and shell results
                        std::vector<const ElementResult*> solidResults, shellResults;
                        for (const auto& er : accumulatedResults_) {
                            if (!er.isValid) continue;
                            if (er.isShell) shellResults.push_back(&er);
                            else solidResults.push_back(&er);
                        }

                        // Embed *INITIAL_STRESS_SOLID for solid elements
                        if (!solidResults.empty()) {
                            output << "*INITIAL_STRESS_SOLID\n";
                            bool firstElem = true;
                            output << std::scientific << std::setprecision(3);
                            for (const auto* er : solidResults) {
                                if (firstElem) {
                                    output << "$#    eid    nint   nhisv   large     ics   ncomp\n";
                                }
                                output << std::setw(10) << er->elementId
                                       << std::setw(8) << 1
                                       << std::setw(8) << 0
                                       << std::setw(8) << 0
                                       << std::setw(8) << 0
                                       << std::setw(8) << 0 << "\n";
                                if (firstElem) {
                                    output << "$#  sigxx     sigyy     sigzz     sigxy     sigyz     sigxz       eps\n";
                                    firstElem = false;
                                }
                                output << std::setw(10) << er->stress.xx
                                       << std::setw(10) << er->stress.yy
                                       << std::setw(10) << er->stress.zz
                                       << std::setw(10) << er->stress.xy
                                       << std::setw(10) << er->stress.yz
                                       << std::setw(10) << er->stress.xz
                                       << std::setw(10) << 0.0 << "\n";
                            }
                        }

                        // Embed *INITIAL_STRESS_SHELL for shell elements
                        if (!shellResults.empty()) {
                            output << "*INITIAL_STRESS_SHELL\n";
                            bool firstElem = true;
                            output << std::scientific << std::setprecision(3);
                            for (const auto* er : shellResults) {
                                if (firstElem) {
                                    output << "$#    eid  nplane  nthick   nhisv  ntensr   large  nthint  nthhsv\n";
                                }
                                // Card 1: EID(10) NPLANE(8) NTHICK(8) NHISV(8) NTENSR(8) LARGE(8) NTHINT(8) NTHHSV(8)
                                output << std::setw(10) << er->elementId
                                       << std::setw(8) << 1   // NPLANE
                                       << std::setw(8) << 2   // NTHICK (top + bottom)
                                       << std::setw(8) << 0   // NHISV
                                       << std::setw(8) << 0   // NTENSR
                                       << std::setw(8) << 0   // LARGE
                                       << std::setw(8) << 0   // NTHINT
                                       << std::setw(8) << 0   // NTHHSV
                                       << "\n";
                                if (firstElem) {
                                    output << "$#     T     sigxx     sigyy     sigzz     sigxy     sigyz     sigzx       eps\n";
                                    firstElem = false;
                                }
                                // Card 2 (bottom, T=-1.0)
                                output << std::setw(10) << -1.0
                                       << std::setw(10) << er->stressBottom.xx
                                       << std::setw(10) << er->stressBottom.yy
                                       << std::setw(10) << er->stressBottom.zz
                                       << std::setw(10) << er->stressBottom.xy
                                       << std::setw(10) << er->stressBottom.yz
                                       << std::setw(10) << er->stressBottom.xz
                                       << std::setw(10) << er->epsBottom << "\n";
                                // Card 3 (top, T=+1.0)
                                output << std::setw(10) << 1.0
                                       << std::setw(10) << er->stressTop.xx
                                       << std::setw(10) << er->stressTop.yy
                                       << std::setw(10) << er->stressTop.zz
                                       << std::setw(10) << er->stressTop.xy
                                       << std::setw(10) << er->stressTop.yz
                                       << std::setw(10) << er->stressTop.xz
                                       << std::setw(10) << er->epsTop << "\n";
                            }
                        }
                    } else {
                        // Separate file with *INCLUDE
                        output << "*INCLUDE\n";
                        output << dynainBasename << "\n";
                    }
                }

                // Insert IGA *INCLUDE references before *END
                for (const auto& igaf : igaFiles_) {
                    output << "*INCLUDE\n";
                    output << " " << igaf.basename << "\n";
                }

                // Insert DR keywords before *END if requested
                if (dynamicRelaxation_) {
                    if (!hasDR) {
                        output << "*CONTROL_DYNAMIC_RELAXATION\n";
                        output << "$#  nrcyck    drtol   drfctr   drterm   tssfdr   irelal    edttl    idrflg\n";
                        output << "       250 0.001000       0.0       0.0       0.0         0       0.0         0\n";
                    }
                    if (!hasTermination) {
                        output << "*CONTROL_TERMINATION\n";
                        output << "$#  endtim    endcyc     dtmin    endeng    endmas     nosol\n";
                        output << "       0.0         0       0.0       0.0       0.01e+20         0\n";
                    }
                }

                output << line << "\n";
                continue;
            } else {
                currentSection = Section::NONE;
            }

            output << line << "\n";
            continue;
        }

        // Comment/empty lines: pass through (skip if inside peri section)
        if (isCommentLine(line) || trimmed.empty()) {
            if (!skipSectionSolidPeri) output << line << "\n";
            continue;
        }

        // Section-specific filtering
        if (currentSection == Section::NODE) {
            int nodeId = parseNodeIdFromLine(line);
            if (nodeId > 0) {
                if (removedNodeIds_.count(nodeId) > 0) {
                    continue;  // Skip removed node
                }
                if (modifiedNodePositions_.count(nodeId) > 0) {
                    // Write modified position
                    const auto& pos = modifiedNodePositions_[nodeId];
                    output << formatNodeLine(nodeId, pos.x, pos.y, pos.z) << "\n";
                    continue;
                }
            }
            output << line << "\n";
        }
        else if (currentSection == Section::ELEMENT) {
            // Detect if this line is an element header (eid+pid, short line)
            // vs a continuation line (node IDs, many tokens)
            int tokenCount = 0;
            {
                std::istringstream iss(line);
                std::string tok;
                while (iss >> tok) tokenCount++;
            }
            bool isElementHeader = (tokenCount >= 2 && tokenCount <= 3);

            // If we're inside a downgraded multi-line element, skip continuation lines
            if (inDowngradeElement) {
                if (isElementHeader) {
                    // New element header → end of previous downgraded element
                    inDowngradeElement = false;
                    // Fall through to process this new element header
                } else {
                    // Continuation line of downgraded element → skip
                    continue;
                }
            }

            int elemId = parseElementIdFromLine(line);
            if (elemId > 0 && removedElementIds_.count(elemId) > 0) {
                continue;  // Skip removed element
            }

            // Downgrade: quadratic→linear (output single-line, skip continuation)
            if (isElementHeader && elemId > 0 && downgradeElementIds_.count(elemId)) {
                auto eit = baseMesh_.elements.find(elemId);
                if (eit != baseMesh_.elements.end()) {
                    const auto& elem = eit->second;
                    std::ostringstream oss;
                    oss << std::setw(8) << elemId << std::setw(8) << elem.partId;

                    // Determine if target is TET-type ELFORM (13/10/60)
                    bool isTet = (elem.type == ElementType::TET4);
                    if (!isTet) {
                        // Check via target ELFORM in solidSectionElforms_
                        auto pit = baseMesh_.parts.find(elem.partId);
                        if (pit != baseMesh_.parts.end()) {
                            auto sit = solidSectionElforms_.find(pit->second.sectionId);
                            if (sit != solidSectionElforms_.end()) {
                                int tgtEf = sit->second;
                                isTet = (tgtEf == 13 || tgtEf == 10 || tgtEf == 60);
                            }
                        }
                    }

                    if (isTet) {
                        // TET4: output n1-n4, then duplicate n4 for n5-n8
                        for (int n = 0; n < 4; ++n) oss << std::setw(8) << elem.nodeIds[n];
                        for (int n = 0; n < 4; ++n) oss << std::setw(8) << elem.nodeIds[3];
                    } else {
                        // HEX8/QUAD4: output first 8 node IDs
                        for (int n = 0; n < 8; ++n) oss << std::setw(8) << elem.nodeIds[n];
                    }

                    output << oss.str() << "\n";
                    inDowngradeElement = true;  // Skip subsequent continuation lines
                    continue;
                }
            }

            // TET10 conversion: replace single-line TET4 with 2-line TET10
            if (elemId > 0 && tet10Elements_.count(elemId)) {
                int pid = parsePartIdFromLine(line);
                output << formatTet10ElementLine(elemId, pid, tet10Elements_[elemId]) << "\n";
                continue;
            }
            // HEX20 conversion: replace single-line HEX8 with 3-line HEX20
            if (elemId > 0 && hex20Elements_.count(elemId)) {
                int pid = parsePartIdFromLine(line);
                output << formatHex20ElementLine(elemId, pid, hex20Elements_[elemId]) << "\n";
                continue;
            }
            // Disconnect: modified element nodes (CZM/MEFEM)
            if (elemId > 0 && modifiedElementNodes_.count(elemId)) {
                int pid = parsePartIdFromLine(line);
                const auto& newNodes = modifiedElementNodes_[elemId];
                std::ostringstream oss;
                oss << std::setw(8) << elemId << std::setw(8) << pid;
                for (int n = 0; n < 8; ++n) oss << std::setw(8) << newNodes[n];
                output << oss.str() << "\n";
                continue;
            }
            output << line << "\n";
        }
        else if (currentSection == Section::SHELL_ELEMENT) {
            int elemId = parseElementIdFromLine(line);
            if (elemId > 0 && removedElementIds_.count(elemId) > 0) {
                continue;
            }
            // Shell downgrade: QUAD8→QUAD4 or TRIA6→TRIA3
            // Parse from raw line since baseMesh_ may have wrong n4 for TRIA6
            if (elemId > 0 && downgradeElementIds_.count(elemId)) {
                // Parse all tokens from raw line
                std::vector<int> tokens;
                {
                    std::istringstream iss(line);
                    std::string tok;
                    while (iss >> tok) {
                        try { tokens.push_back(std::stoi(tok)); } catch (...) { break; }
                    }
                }
                if (tokens.size() >= 6) {
                    int eid = tokens[0], pid = tokens[1];
                    // TRIA6: 10 tokens with last 2 being 0
                    bool isTria = (tokens.size() >= 10 && tokens[8] == 0 && tokens[9] == 0);
                    std::ostringstream oss;
                    oss << std::setw(8) << eid << std::setw(8) << pid;
                    if (isTria) {
                        // Output n1 n2 n3 n3 (TRIA3)
                        oss << std::setw(8) << tokens[2] << std::setw(8) << tokens[3]
                            << std::setw(8) << tokens[4] << std::setw(8) << tokens[4];
                    } else {
                        // Output n1 n2 n3 n4 (QUAD4)
                        for (int n = 2; n < 6; ++n) oss << std::setw(8) << tokens[n];
                    }
                    output << oss.str() << "\n";
                    continue;
                }
            }
            // QUAD8 conversion: replace QUAD4 line
            if (elemId > 0 && quad8Elements_.count(elemId)) {
                int pid = parsePartIdFromLine(line);
                output << formatQuad8ElementLine(elemId, pid, quad8Elements_[elemId]) << "\n";
                continue;
            }
            // TRIA6 conversion: replace TRIA3 line
            if (elemId > 0 && tria6Elements_.count(elemId)) {
                int pid = parsePartIdFromLine(line);
                output << formatTria6ElementLine(elemId, pid, tria6Elements_[elemId]) << "\n";
                continue;
            }
            // Disconnect: modified shell element nodes (CZM/MEFEM)
            if (elemId > 0 && modifiedShellElementNodes_.count(elemId)) {
                int pid = parsePartIdFromLine(line);
                const auto& nn = modifiedShellElementNodes_[elemId];
                std::ostringstream oss;
                oss << std::setw(8) << elemId << std::setw(8) << pid;
                for (int n = 0; n < 4; ++n) oss << std::setw(8) << nn[n];
                output << oss.str() << "\n";
                continue;
            }
            output << line << "\n";
        }
        else {
            // *SECTION_SOLID ELFORM rewrite for TET10/HEX20 conversion
            if (inSectionSolid && !isCommentLine(line) && !line.empty() &&
                line.find_first_not_of(" \t") != std::string::npos &&
                (!solidSectionElforms_.empty() || !periSectionIds_.empty())) {
                sectionSolidDataLine++;
                if (sectionSolidDataLine == 1) {
                    try {
                        int secId = std::stoi(line.substr(0, 10));
                        // Peridynamics: skip this section (SECTION_SOLID_PERI added via addedKeywordBlocks_)
                        if (periSectionIds_.count(secId)) {
                            skipSectionSolidPeri = true;
                            continue;  // Skip data line 1
                        }
                        auto sit = solidSectionElforms_.find(secId);
                        if (sit != solidSectionElforms_.end()) {
                            std::string modified = line;
                            if (modified.size() < 20) modified.resize(20, ' ');
                            std::ostringstream ef;
                            ef << std::setw(10) << sit->second;
                            modified.replace(10, 10, ef.str());
                            output << modified << "\n";
                            continue;
                        }
                    } catch (...) {}
                }
            }
            // *SECTION_SHELL ELFORM rewrite for QUAD8/TRIA6 conversion
            if (inSectionShell && !isCommentLine(line) && !line.empty() &&
                line.find_first_not_of(" \t") != std::string::npos &&
                !shellSectionElforms_.empty()) {
                sectionShellDataLine++;
                if (sectionShellDataLine == 1) {
                    try {
                        int secId = std::stoi(line.substr(0, 10));
                        auto sit = shellSectionElforms_.find(secId);
                        if (sit != shellSectionElforms_.end()) {
                            std::string modified = line;
                            if (modified.size() < 20) modified.resize(20, ' ');
                            std::ostringstream ef;
                            ef << std::setw(10) << sit->second;
                            modified.replace(10, 10, ef.str());
                            output << modified << "\n";
                            continue;
                        }
                    } catch (...) {}
                }
            }
            if (!skipSectionSolidPeri) {
                output << line << "\n";
            }
        }
        continueMainLoop:;
    }

    // Write output file
    std::ofstream outFile(outputFile, std::ios::binary);
    if (!outFile.is_open()) {
        errorMessage_ = "Cannot write output: " + outputFile;
        return false;
    }
    outFile << output.str();
    outFile.close();

    // Write accumulated dynain (separate file only if not embedded)
    if (!accumulatedResults_.empty() && !dynainEmbed_) {
        // Check if we have any shell results
        bool hasShellResults = false;
        bool hasSolidResults = false;
        for (const auto& er : accumulatedResults_) {
            if (!er.isValid) continue;
            if (er.isShell) hasShellResults = true;
            else hasSolidResults = true;
        }

        if (hasShellResults) {
            // Write combined dynain file manually (solid + shell)
            std::ostringstream dynBuf;
            dynBuf << std::fixed;
            dynBuf << "*KEYWORD\n";
            dynBuf << "$\n";
            dynBuf << "$ LS-DYNA Initial Stress File (dynain)\n";
            dynBuf << "$ Generated by KooRemapper (assemble)\n";
            dynBuf << "$\n";

            dynBuf << std::scientific << std::setprecision(3);

            // Solid section
            if (hasSolidResults) {
                dynBuf << "*INITIAL_STRESS_SOLID\n";
                bool firstElem = true;
                for (const auto& er : accumulatedResults_) {
                    if (!er.isValid || er.isShell) continue;
                    if (firstElem) {
                        dynBuf << "$#    eid    nint   nhisv   large     ics   ncomp\n";
                    }
                    dynBuf << std::setw(10) << er.elementId
                           << std::setw(8) << 1 << std::setw(8) << 0
                           << std::setw(8) << 0 << std::setw(8) << 0
                           << std::setw(8) << 0 << "\n";
                    if (firstElem) {
                        dynBuf << "$#  sigxx     sigyy     sigzz     sigxy     sigyz     sigxz       eps\n";
                        firstElem = false;
                    }
                    dynBuf << std::setw(10) << er.stress.xx
                           << std::setw(10) << er.stress.yy
                           << std::setw(10) << er.stress.zz
                           << std::setw(10) << er.stress.xy
                           << std::setw(10) << er.stress.yz
                           << std::setw(10) << er.stress.xz
                           << std::setw(10) << 0.0 << "\n";
                }
            }

            // Shell section
            dynBuf << "*INITIAL_STRESS_SHELL\n";
            bool firstShell = true;
            for (const auto& er : accumulatedResults_) {
                if (!er.isValid || !er.isShell) continue;
                if (firstShell) {
                    dynBuf << "$#    eid  nplane  nthick   nhisv  ntensr   large  nthint  nthhsv\n";
                }
                dynBuf << std::setw(10) << er.elementId
                       << std::setw(8) << 1 << std::setw(8) << 2
                       << std::setw(8) << 0 << std::setw(8) << 0
                       << std::setw(8) << 0 << std::setw(8) << 0
                       << std::setw(8) << 0 << "\n";
                if (firstShell) {
                    dynBuf << "$#     T     sigxx     sigyy     sigzz     sigxy     sigyz     sigzx       eps\n";
                    firstShell = false;
                }
                // Bottom (T=-1)
                dynBuf << std::setw(10) << -1.0
                       << std::setw(10) << er.stressBottom.xx
                       << std::setw(10) << er.stressBottom.yy
                       << std::setw(10) << er.stressBottom.zz
                       << std::setw(10) << er.stressBottom.xy
                       << std::setw(10) << er.stressBottom.yz
                       << std::setw(10) << er.stressBottom.xz
                       << std::setw(10) << er.epsBottom << "\n";
                // Top (T=+1)
                dynBuf << std::setw(10) << 1.0
                       << std::setw(10) << er.stressTop.xx
                       << std::setw(10) << er.stressTop.yy
                       << std::setw(10) << er.stressTop.zz
                       << std::setw(10) << er.stressTop.xy
                       << std::setw(10) << er.stressTop.yz
                       << std::setw(10) << er.stressTop.xz
                       << std::setw(10) << er.epsTop << "\n";
            }

            dynBuf << "*END\n";

            std::ofstream dynFile(dynainFile, std::ios::binary);
            if (!dynFile.is_open()) {
                errorMessage_ = "Cannot write dynain: " + dynainFile;
                return false;
            }
            dynFile << dynBuf.str();
            dynFile.close();
        } else {
            // Solid-only: use existing DynainWriter
            MeshAnalysisResult finalResult;
            finalResult.elementResults = accumulatedResults_;
            finalResult.hasMaterial = true;
            finalResult.validElements = static_cast<int>(accumulatedResults_.size());

            DynainWriter dynainWriter;
            if (!dynainWriter.writeFile(dynainFile, finalResult, StrainType::ENGINEERING,
                                         "", "assemble")) {
                errorMessage_ = "Failed to write dynain: " + dynainWriter.getErrorMessage();
                return false;
            }
        }
    }

    // Write IGA .k include files
    for (const auto& igaf : igaFiles_) {
        std::ofstream igaOut(igaf.fullpath, std::ios::binary);
        if (!igaOut.is_open()) {
            errorMessage_ = "Cannot write IGA file: " + igaf.fullpath;
            return false;
        }
        igaOut << igaf.content;
        igaOut.close();
    }

    return true;
}

// --- Utility methods ---

std::set<int> ModelAssembler::getPartElementIds(int pid) const {
    std::set<int> result;
    for (const auto& [eid, elem] : baseMesh_.getElements()) {
        if (elem.partId == pid) {
            result.insert(eid);
        }
    }
    return result;
}

std::set<int> ModelAssembler::getPartNodeIds(int pid) const {
    std::set<int> result;
    for (const auto& [eid, elem] : baseMesh_.getElements()) {
        if (elem.partId == pid) {
            for (int i = 0; i < Element::NUM_NODES; ++i) {
                result.insert(elem.nodeIds[i]);
            }
        }
    }
    return result;
}

std::set<int> ModelAssembler::getPartExclusiveNodeIds(int pid) const {
    // Get all nodes used by this part
    std::set<int> partNodes = getPartNodeIds(pid);

    // Get all nodes used by OTHER parts
    std::set<int> otherNodes;
    for (const auto& [eid, elem] : baseMesh_.getElements()) {
        if (elem.partId != pid) {
            for (int i = 0; i < Element::NUM_NODES; ++i) {
                otherNodes.insert(elem.nodeIds[i]);
            }
        }
    }

    // Exclusive = partNodes - otherNodes
    std::set<int> exclusive;
    for (int nid : partNodes) {
        if (otherNodes.count(nid) == 0) {
            exclusive.insert(nid);
        }
    }
    return exclusive;
}

int ModelAssembler::parseNodeIdFromLine(const std::string& line) const {
    // Extract first integer from line (handles variable field widths: 8, 10, 16 chars)
    if (line.empty()) return -1;
    try {
        size_t start = 0;
        while (start < line.size() && std::isspace(line[start])) start++;
        if (start >= line.size() || !std::isdigit(line[start])) return -1;
        size_t end = start;
        while (end < line.size() && std::isdigit(line[end])) end++;
        return std::stoi(line.substr(start, end - start));
    } catch (...) {
        return -1;
    }
}

int ModelAssembler::parseElementIdFromLine(const std::string& line) const {
    // Extract first integer from line (handles variable field widths)
    if (line.empty()) return -1;
    try {
        size_t start = 0;
        while (start < line.size() && std::isspace(line[start])) start++;
        if (start >= line.size() || !std::isdigit(line[start])) return -1;
        size_t end = start;
        while (end < line.size() && std::isdigit(line[end])) end++;
        return std::stoi(line.substr(start, end - start));
    } catch (...) {
        return -1;
    }
}

std::string ModelAssembler::formatNodeLine(int id, double x, double y, double z) const {
    std::ostringstream oss;
    oss << std::setw(8) << id
        << std::setw(16) << std::scientific << std::setprecision(9) << x
        << std::setw(16) << std::scientific << std::setprecision(9) << y
        << std::setw(16) << std::scientific << std::setprecision(9) << z;
    return oss.str();
}

std::string ModelAssembler::formatElementLine(const AddedElement& elem) const {
    std::ostringstream oss;
    oss << std::setw(8) << elem.id
        << std::setw(8) << elem.pid;
    for (int i = 0; i < 8; ++i) {
        oss << std::setw(8) << elem.nodeIds[i];
    }
    return oss.str();
}

std::string ModelAssembler::formatShellElementLine(const AddedShellElement& elem) const {
    std::ostringstream oss;
    oss << std::setw(8) << elem.id
        << std::setw(8) << elem.pid;
    for (int i = 0; i < 4; ++i) {
        oss << std::setw(8) << elem.nodeIds[i];
    }
    return oss.str();
}

bool ModelAssembler::isKeywordLine(const std::string& line) const {
    std::string trimmed = line;
    size_t start = trimmed.find_first_not_of(" \t");
    if (start == std::string::npos) return false;
    return trimmed[start] == '*' && !isCommentLine(line);
}

bool ModelAssembler::isCommentLine(const std::string& line) const {
    size_t start = line.find_first_not_of(" \t");
    if (start == std::string::npos) return false;
    return line[start] == '$';
}

bool ModelAssembler::applyIndent(const IndentOperation& op, double E, double nu) {
    // 1. Determine axis mapping from plane + direction
    int inAxis1, inAxis2, normalAxis;
    if (op.plane == "xy") {
        inAxis1 = 0; inAxis2 = 1; normalAxis = 2;
    } else if (op.plane == "yz") {
        inAxis1 = 1; inAxis2 = 2; normalAxis = 0;
    } else {  // zx
        inAxis1 = 2; inAxis2 = 0; normalAxis = 1;
    }

    // Parse direction sign
    double dirSign = (op.direction[0] == '-') ? -1.0 : 1.0;

    // 2. Build ClosedLoop from shape points
    ClosedLoop loop;
    std::vector<Vec2> loopPts;
    loopPts.reserve(op.points.size());
    for (const auto& pt : op.points) {
        loopPts.push_back({pt.x1, pt.x2});
    }
    if (op.shapeType == "spline") {
        loop.setSpline(loopPts, 20);
    } else {
        loop.setPolygon(loopPts);
    }

    // 3. Build IndentProfile
    IndentProfile profile(op.depth, op.r1, op.r2);
    double transWidth = profile.transitionWidth();

    // 4. AABB for pre-filtering
    double loopX1Min, loopX1Max, loopX2Min, loopX2Max;
    loop.getAABB(loopX1Min, loopX1Max, loopX2Min, loopX2Max);
    double filterX1Min = loopX1Min - transWidth;
    double filterX1Max = loopX1Max + transWidth;
    double filterX2Min = loopX2Min - transWidth;
    double filterX2Max = loopX2Max + transWidth;

    // 5. Gather nodes (same pattern as applyBend)
    std::set<int> basePartNodeIds;
    for (const auto& [eid, elem] : baseMesh_.getElements()) {
        if (elem.partId == op.targetPid && removedElementIds_.count(eid) == 0) {
            for (int i = 0; i < Element::NUM_NODES; ++i) {
                if (removedNodeIds_.count(elem.nodeIds[i]) == 0) {
                    basePartNodeIds.insert(elem.nodeIds[i]);
                }
            }
        }
    }

    std::map<int, size_t> addedNodeIndex;
    for (size_t i = 0; i < addedNodes_.size(); ++i) {
        addedNodeIndex[addedNodes_[i].id] = i;
    }

    std::set<int> addedPartNodeIds;
    for (const auto& ae : addedElements_) {
        if (ae.pid == op.targetPid) {
            for (int nid : ae.nodeIds) {
                addedPartNodeIds.insert(nid);
            }
        }
    }

    std::set<int> allNodeIds = basePartNodeIds;
    allNodeIds.insert(addedPartNodeIds.begin(), addedPartNodeIds.end());

    if (allNodeIds.empty()) {
        errorMessage_ = "Part " + std::to_string(op.targetPid) + " not found for indent";
        return false;
    }

    // Helper: get node position
    auto getNodePos = [&](int nid, double& x, double& y, double& z) -> bool {
        auto modIt = modifiedNodePositions_.find(nid);
        if (modIt != modifiedNodePositions_.end()) {
            x = modIt->second.x; y = modIt->second.y; z = modIt->second.z;
            return true;
        }
        auto it = addedNodeIndex.find(nid);
        if (it != addedNodeIndex.end()) {
            x = addedNodes_[it->second].x;
            y = addedNodes_[it->second].y;
            z = addedNodes_[it->second].z;
            return true;
        }
        const auto* node = baseMesh_.getNode(nid);
        if (!node) return false;
        x = node->position.x; y = node->position.y; z = node->position.z;
        return true;
    };

    auto getCoord = [](double x, double y, double z, int axis) -> double {
        if (axis == 0) return x;
        if (axis == 1) return y;
        return z;
    };

    // 6. Compute bounding box for through-thickness
    double nMin = std::numeric_limits<double>::max();
    double nMax = std::numeric_limits<double>::lowest();
    for (int nid : allNodeIds) {
        double x, y, z;
        if (!getNodePos(nid, x, y, z)) continue;
        double n = getCoord(x, y, z, normalAxis);
        if (n < nMin) nMin = n;
        if (n > nMax) nMax = n;
    }
    double thickness = nMax - nMin;

    // 6b. Detect shell part and determine shell thickness
    bool isShellPart = false;
    for (const auto& [eid, elem] : baseMesh_.getElements()) {
        if (elem.partId == op.targetPid && elem.type == ElementType::QUAD4 &&
            removedElementIds_.count(eid) == 0) {
            isShellPart = true;
            break;
        }
    }
    // Also check addedShellElements_
    if (!isShellPart) {
        for (const auto& ase : addedShellElements_) {
            if (ase.pid == op.targetPid) {
                isShellPart = true;
                break;
            }
        }
    }

    double shellThk = 0.0;
    if (isShellPart) {
        // Priority 1: YAML shell_thickness
        shellThk = op.shellThickness;
        // Priority 2: *SECTION_SHELL from K-file
        if (shellThk <= 0.0) {
            auto partIt = baseMesh_.parts.find(op.targetPid);
            if (partIt != baseMesh_.parts.end()) {
                auto secIt = baseMesh_.shellSections.find(partIt->second.sectionId);
                if (secIt != baseMesh_.shellSections.end()) {
                    shellThk = secIt->second.thickness;
                }
            }
        }
        if (shellThk <= 0.0 && op.stress) {
            errorMessage_ = "Shell thickness required for stress. Use shell_thickness in YAML or *SECTION_SHELL in K-file.";
            return false;
        }
    }

    // Pre-validation warnings
    if (thickness > 1e-12) {
        double k = std::abs(op.depth) / (op.r1 + op.r2);
        if (k > 1.0) {
            infoMessages.push_back("  [WARN] Steep fillet: k = |depth|/(r1+r2) = " +
                std::to_string(k) + " > 1.0");
        }
        if (std::abs(op.depth) > thickness * 0.8) {
            errorMessage_ = "Indent depth (" + std::to_string(op.depth) +
                ") exceeds 80% of part thickness (" + std::to_string(thickness) + ")";
            return false;
        }
    }

    // 7. Compute bending stress (BEFORE deformation, like bend)
    bool doStress = op.stress && (thickness > 1e-12 || (isShellPart && shellThk > 0));
    if (doStress) {
        double nMid = (nMin + nMax) * 0.5;  // neutral surface
        bool hasYamlMat = (E > 0 && nu > 0 && nu < 0.5);
        // For shell: effective half-thickness for curvature capping
        double halfThk = isShellPart ? (shellThk * 0.5) : (thickness * 0.5);

        auto getPartMaterial = [&](double& matE, double& matNu) {
            matE = 0; matNu = 0;
            if (hasYamlMat) {
                matE = E; matNu = nu;
            } else {
                auto partIt = baseMesh_.parts.find(op.targetPid);
                if (partIt != baseMesh_.parts.end()) {
                    const MaterialData* matData = baseMesh_.getMaterial(partIt->second.materialId);
                    if (matData && matData->E > 0) {
                        matE = matData->E;
                        matNu = matData->nu;
                    }
                }
            }
        };

        // Helper: compute kappa decomposition and strain from d_neutral
        auto computeStrainFromCurvature = [&](double hpp, const Vec2& gradient,
                                               double d_neutral, StrainTensor& outStrain) {
            double kappa_11 = -hpp * gradient.x * gradient.x;
            double kappa_22 = -hpp * gradient.y * gradient.y;
            double kappa_12 = -hpp * gradient.x * gradient.y;

            double eps_11 = -d_neutral * kappa_11;
            double eps_22 = -d_neutral * kappa_22;
            double gamma_12 = -2.0 * d_neutral * kappa_12;

            double eps[6] = {0, 0, 0, 0, 0, 0};
            if (inAxis1 == 0) eps[0] = eps_11;
            else if (inAxis1 == 1) eps[1] = eps_11;
            else eps[2] = eps_11;

            if (inAxis2 == 0) eps[0] = eps_22;
            else if (inAxis2 == 1) eps[1] = eps_22;
            else eps[2] = eps_22;

            if ((inAxis1 == 0 && inAxis2 == 1) || (inAxis1 == 1 && inAxis2 == 0))
                eps[3] = gamma_12;
            else if ((inAxis1 == 1 && inAxis2 == 2) || (inAxis1 == 2 && inAxis2 == 1))
                eps[4] = gamma_12;
            else
                eps[5] = gamma_12;

            outStrain = StrainTensor(eps[0], eps[1], eps[2], eps[3], eps[4], eps[5]);
        };

        auto computeIndentStress = [&](int eid, const int* nodeIds, int numNodes, bool elemIsShell) {
            // Compute element centroid from ORIGINAL (pre-indent) positions
            double cx = 0, cy = 0, cz = 0;
            int validNodes = 0;
            for (int n = 0; n < numNodes; n++) {
                double nx, ny, nz;
                if (!getNodePos(nodeIds[n], nx, ny, nz)) continue;
                cx += nx; cy += ny; cz += nz;
                validNodes++;
            }
            if (validNodes == 0) return;
            cx /= validNodes; cy /= validNodes; cz /= validNodes;

            double cc[3] = {cx, cy, cz};
            double c1 = cc[inAxis1];
            double c2 = cc[inAxis2];

            // AABB pre-filter on centroid
            if (c1 < filterX1Min || c1 > filterX1Max ||
                c2 < filterX2Min || c2 > filterX2Max) return;

            // Signed distance + gradient direction
            Vec2 gradient;
            double sd = loop.signedDistanceWithGradient({c1, c2}, gradient);
            if (sd >= transWidth) return;

            // Curvature h''(d) at centroid
            double hpp = profile.getCurvature(sd);
            if (std::abs(hpp) < 1e-15) return;

            // Cap curvature so max bending strain <= 5%
            double strainLimit = 0.05;
            double hppMax = strainLimit / halfThk;
            if (hpp > hppMax) hpp = hppMax;
            else if (hpp < -hppMax) hpp = -hppMax;

            // Material
            double matE, matNu;
            if (hasYamlMat) {
                matE = E; matNu = nu;
            } else {
                const auto* elem = baseMesh_.getElement(eid);
                if (elem) {
                    const MaterialData* matData = baseMesh_.getElementMaterial(*elem);
                    if (matData && matData->E > 0) {
                        matE = matData->E;
                        matNu = matData->nu;
                    } else {
                        getPartMaterial(matE, matNu);
                    }
                } else {
                    getPartMaterial(matE, matNu);
                }
            }
            if (matE <= 0) return;

            if (elemIsShell) {
                // Shell: compute top (T=+1, d=+shellThk/2) and bottom (T=-1, d=-shellThk/2)
                double dTop = shellThk * 0.5;
                double dBot = -shellThk * 0.5;

                StrainTensor strainTop, strainBot;
                computeStrainFromCurvature(hpp, gradient, dTop, strainTop);
                computeStrainFromCurvature(hpp, gradient, dBot, strainBot);

                // Reverse stress (holds indented shape during DR)
                StressTensor stressTop = StressTensor::fromStrain(strainTop * (-1.0), matE, matNu);
                StressTensor stressBot = StressTensor::fromStrain(strainBot * (-1.0), matE, matNu);

                ElementResult er;
                er.elementId = eid;
                er.isShell = true;
                er.shellThickness = shellThk;
                er.stressTop = stressTop;
                er.stressBottom = stressBot;
                er.strain = strainTop;  // store top strain as representative
                er.stress = stressTop;  // store top stress as representative
                er.isValid = true;
                er.vonMisesStress = stressTop.vonMises();
                er.vonMisesStrain = strainTop.vonMisesStrain();
                accumulatedResults_.push_back(er);
            } else {
                // Solid: original logic
                double nc = cc[normalAxis];
                double d_neutral = nc - nMid;

                StrainTensor strain;
                computeStrainFromCurvature(hpp, gradient, d_neutral, strain);

                StrainTensor reverseStrain = strain * (-1.0);
                StressTensor stress = StressTensor::fromStrain(reverseStrain, matE, matNu);

                ElementResult er;
                er.elementId = eid;
                er.stress = stress;
                er.strain = strain;
                er.isValid = true;
                er.vonMisesStress = stress.vonMises();
                er.vonMisesStrain = strain.vonMisesStrain();
                accumulatedResults_.push_back(er);
            }
        };

        // Base model elements
        for (const auto& [eid, elem] : baseMesh_.getElements()) {
            if (elem.partId == op.targetPid && removedElementIds_.count(eid) == 0) {
                bool elemShell = (elem.type == ElementType::QUAD4);
                computeIndentStress(eid, elem.nodeIds.data(), Element::NUM_NODES, elemShell);
            }
        }
        // Added solid elements
        for (const auto& ae : addedElements_) {
            if (ae.pid == op.targetPid) {
                computeIndentStress(ae.id, ae.nodeIds.data(), 8, false);
            }
        }
        // Added shell elements
        for (const auto& ase : addedShellElements_) {
            if (ase.pid == op.targetPid) {
                // Convert 4-node array to int* for compatibility
                std::array<int, 8> nids = {ase.nodeIds[0], ase.nodeIds[1],
                    ase.nodeIds[2], ase.nodeIds[3], ase.nodeIds[0], ase.nodeIds[1],
                    ase.nodeIds[2], ase.nodeIds[3]};
                computeIndentStress(ase.id, nids.data(), 4, true);
            }
        }
    }

    // 8. Apply indent to each node
    int movedNodes = 0;
    for (int nid : allNodeIds) {
        double x, y, z;
        if (!getNodePos(nid, x, y, z)) continue;

        double x1 = getCoord(x, y, z, inAxis1);
        double x2 = getCoord(x, y, z, inAxis2);
        double n  = getCoord(x, y, z, normalAxis);

        // AABB pre-filter
        if (x1 < filterX1Min || x1 > filterX1Max ||
            x2 < filterX2Min || x2 > filterX2Max) {
            continue;
        }

        // Signed distance
        double d = loop.signedDistance({x1, x2});
        if (d >= transWidth) continue;

        // Profile displacement
        double hSurface = profile.getDisplacement(d);
        if (std::abs(hSurface) < 1e-15) continue;

        // Through-thickness interpolation
        double tFrac;
        if (thickness < 1e-12) {
            tFrac = 1.0;
        } else if (dirSign < 0.0) {
            // Negative direction (e.g. -z): indent surface = max side
            tFrac = (n - nMin) / thickness;
        } else {
            // Positive direction (e.g. +z): indent surface = min side
            tFrac = (nMax - n) / thickness;
        }
        tFrac = std::max(0.0, std::min(1.0, tFrac));

        double h = hSurface * (op.bottomRatio + (1.0 - op.bottomRatio) * tFrac);

        // Apply displacement: node.coord[normalAxis] -= h * dirSign
        double disp = -h * dirSign;

        // Update node position
        double newX = x, newY = y, newZ = z;
        if (normalAxis == 0) newX += disp;
        else if (normalAxis == 1) newY += disp;
        else newZ += disp;

        // Store modified position
        auto it = addedNodeIndex.find(nid);
        if (it != addedNodeIndex.end()) {
            addedNodes_[it->second].x = newX;
            addedNodes_[it->second].y = newY;
            addedNodes_[it->second].z = newZ;
        } else {
            modifiedNodePositions_[nid] = Vector3D(newX, newY, newZ);
        }
        ++movedNodes;
    }

    ++indentedParts_;
    infoMessages.push_back("  Indent PID " + std::to_string(op.targetPid) +
        ": depth=" + std::to_string(op.depth) +
        " r1=" + std::to_string(op.r1) +
        " r2=" + std::to_string(op.r2) +
        " (" + std::to_string(movedNodes) + " nodes moved)");

    return true;
}

bool ModelAssembler::applyFormStrain(const FormStrainOperation& op) {
    // Formstrain: compute plastic strain from mesh curvature for shell parts
    // Auto-detect eligible parts: QUAD4 elements + SECTION_SHELL + MAT_024 with SIGY > 0

    int totalElements = 0;
    int processedParts = 0;

    if (op.targetPid > 0) {
        // Single part mode
        auto partIt = baseMesh_.parts.find(op.targetPid);
        if (partIt == baseMesh_.parts.end()) {
            errorMessage_ = "FormStrain: target PID " + std::to_string(op.targetPid) + " not found";
            return false;
        }

        const auto& part = partIt->second;

        // Get material for SIGY
        auto matIt = baseMesh_.materials.find(part.materialId);
        if (matIt == baseMesh_.materials.end() || matIt->second.sigy <= 0) {
            infoMessages.push_back("  FormStrain: PID " + std::to_string(op.targetPid) +
                " has no yield stress (SIGY) - skipped");
            return true;
        }

        double E = matIt->second.E;
        double sigy = matIt->second.sigy;

        // Get thickness
        double thickness = op.shellThickness;
        if (thickness <= 0) {
            auto secIt = baseMesh_.shellSections.find(part.sectionId);
            if (secIt != baseMesh_.shellSections.end()) {
                thickness = secIt->second.thickness;
            }
        }
        if (thickness <= 0) {
            infoMessages.push_back("  FormStrain: PID " + std::to_string(op.targetPid) +
                " has no shell thickness - skipped");
            return true;
        }

        ShellCurvature curvCalc;
        auto results = curvCalc.compute(baseMesh_, op.targetPid, thickness, sigy, E, op.minCurvature);

        if (curvCalc.getNormalWarnings() > 0) {
            infoMessages.push_back("  FormStrain: WARNING - " +
                std::to_string(curvCalc.getNormalWarnings()) +
                " inconsistent normal pairs detected in PID " + std::to_string(op.targetPid));
        }

        // Convert to ElementResult with EPS
        for (const auto& cr : results) {
            ElementResult er;
            er.elementId = cr.elementId;
            er.isValid = true;
            er.isShell = true;
            er.shellThickness = thickness;
            er.epsTop = cr.plasticStrain;
            er.epsBottom = cr.plasticStrain;
            // stress = 0 (springback relaxed state)
            accumulatedResults_.push_back(er);
        }

        totalElements += static_cast<int>(results.size());
        if (!results.empty()) processedParts++;

        infoMessages.push_back("  FormStrain PID " + std::to_string(op.targetPid) +
            ": t=" + std::to_string(thickness) + " SIGY=" + std::to_string(sigy) +
            " E=" + std::to_string(E) +
            " → " + std::to_string(results.size()) + " elements with EPS");

    } else {
        // Auto-detect mode: scan all parts
        for (const auto& [pid, part] : baseMesh_.parts) {
            // Check: shell section exists?
            auto secIt = baseMesh_.shellSections.find(part.sectionId);
            if (secIt == baseMesh_.shellSections.end()) continue;

            double thickness = op.shellThickness;
            if (thickness <= 0) {
                thickness = secIt->second.thickness;
            }
            if (thickness <= 0) continue;

            // Check: material with SIGY?
            auto matIt = baseMesh_.materials.find(part.materialId);
            if (matIt == baseMesh_.materials.end()) continue;
            if (matIt->second.sigy <= 0) continue;

            double E = matIt->second.E;
            double sigy = matIt->second.sigy;

            ShellCurvature curvCalc;
            auto results = curvCalc.compute(baseMesh_, pid, thickness, sigy, E, op.minCurvature);

            if (curvCalc.getNormalWarnings() > 0) {
                infoMessages.push_back("  FormStrain: WARNING - " +
                    std::to_string(curvCalc.getNormalWarnings()) +
                    " inconsistent normal pairs in PID " + std::to_string(pid));
            }

            for (const auto& cr : results) {
                ElementResult er;
                er.elementId = cr.elementId;
                er.isValid = true;
                er.isShell = true;
                er.shellThickness = thickness;
                er.epsTop = cr.plasticStrain;
                er.epsBottom = cr.plasticStrain;
                accumulatedResults_.push_back(er);
            }

            if (!results.empty()) {
                processedParts++;
                totalElements += static_cast<int>(results.size());
                infoMessages.push_back("  FormStrain PID " + std::to_string(pid) +
                    ": t=" + std::to_string(thickness) + " SIGY=" + std::to_string(sigy) +
                    " → " + std::to_string(results.size()) + " elements with EPS");
            }
        }
    }

    formStrainParts_ += processedParts;

    if (processedParts == 0) {
        infoMessages.push_back("  FormStrain: no eligible shell parts found (need SECTION_SHELL + MAT_024 with SIGY > 0)");
    } else {
        infoMessages.push_back("  FormStrain total: " + std::to_string(processedParts) +
            " parts, " + std::to_string(totalElements) + " elements with plastic strain");
    }

    return true;
}

bool ModelAssembler::applyTet10Convert(const Tet10ConvertOperation& op) {
    // Build shared edge map: sorted(nA, nB) → midNodeId
    auto getOrCreateMidNode = [&](int nA, int nB) -> int {
        auto key = std::make_pair(std::min(nA, nB), std::max(nA, nB));
        auto it = edgeMidNodeMap_.find(key);
        if (it != edgeMidNodeMap_.end()) {
            return it->second;
        }
        int newId = ++maxNodeId_;
        const auto& posA = baseMesh_.nodes.at(nA).position;
        const auto& posB = baseMesh_.nodes.at(nB).position;
        addedNodes_.push_back({newId,
            (posA.x + posB.x) * 0.5,
            (posA.y + posB.y) * 0.5,
            (posA.z + posB.z) * 0.5});
        edgeMidNodeMap_[key] = newId;
        return newId;
    };
    size_t midNodesBefore = edgeMidNodeMap_.size();

    // --- TET4 → TET10 ---
    if (op.convertType == "tet10") {
        int elform = (op.elform > 0) ? op.elform : 17;

        std::vector<std::pair<int, const Element*>> targets;
        std::set<int> targetParts;
        for (const auto& [eid, elem] : baseMesh_.elements) {
            if (elem.type != ElementType::TET4) continue;
            if (op.targetPid > 0 && elem.partId != op.targetPid) continue;
            targets.push_back({eid, &elem});
            targetParts.insert(elem.partId);
        }
        if (targets.empty()) {
            infoMessages.push_back("  TET10: no TET4 elements found" +
                (op.targetPid > 0 ? " in part " + std::to_string(op.targetPid) : ""));
            return true;
        }
        for (const auto& [eid, elem] : targets) {
            int n1=elem->nodeIds[0], n2=elem->nodeIds[1], n3=elem->nodeIds[2], n4=elem->nodeIds[3];
            tet10Elements_[eid] = {n1, n2, n3, n4,
                getOrCreateMidNode(n1,n2), getOrCreateMidNode(n2,n3), getOrCreateMidNode(n3,n1),
                getOrCreateMidNode(n1,n4), getOrCreateMidNode(n2,n4), getOrCreateMidNode(n3,n4)};
        }
        for (int pid : targetParts) {
            auto it = baseMesh_.parts.find(pid);
            if (it != baseMesh_.parts.end() && it->second.sectionId > 0)
                solidSectionElforms_[it->second.sectionId] = elform;
        }
        tet10ConvertedCount_ = static_cast<int>(targets.size());
        infoMessages.push_back("  TET10: converted " + std::to_string(tet10ConvertedCount_) +
            " elements, added " + std::to_string(edgeMidNodeMap_.size() - midNodesBefore) +
            " mid-edge nodes, ELFORM -> " + std::to_string(elform));
    }
    // --- HEX8 → HEX20 ---
    else if (op.convertType == "hex20") {
        int elform = (op.elform > 0) ? op.elform : 23;

        std::vector<std::pair<int, const Element*>> targets;
        std::set<int> targetParts;
        for (const auto& [eid, elem] : baseMesh_.elements) {
            if (elem.type != ElementType::HEX8) continue;
            if (op.targetPid > 0 && elem.partId != op.targetPid) continue;
            targets.push_back({eid, &elem});
            targetParts.insert(elem.partId);
        }
        if (targets.empty()) {
            infoMessages.push_back("  HEX20: no HEX8 elements found" +
                (op.targetPid > 0 ? " in part " + std::to_string(op.targetPid) : ""));
            return true;
        }
        for (const auto& [eid, elem] : targets) {
            const auto& n = elem->nodeIds;
            // LS-DYNA HEX20 mid-edge node convention:
            // Bottom face edges: N9=mid(1,2), N10=mid(2,3), N11=mid(3,4), N12=mid(4,1)
            // Top face edges:    N13=mid(5,6), N14=mid(6,7), N15=mid(7,8), N16=mid(8,5)
            // Vertical edges:    N17=mid(1,5), N18=mid(2,6), N19=mid(3,7), N20=mid(4,8)
            hex20Elements_[eid] = {
                n[0], n[1], n[2], n[3], n[4], n[5], n[6], n[7],
                getOrCreateMidNode(n[0],n[1]), getOrCreateMidNode(n[1],n[2]),
                getOrCreateMidNode(n[2],n[3]), getOrCreateMidNode(n[3],n[0]),
                getOrCreateMidNode(n[4],n[5]), getOrCreateMidNode(n[5],n[6]),
                getOrCreateMidNode(n[6],n[7]), getOrCreateMidNode(n[7],n[4]),
                getOrCreateMidNode(n[0],n[4]), getOrCreateMidNode(n[1],n[5]),
                getOrCreateMidNode(n[2],n[6]), getOrCreateMidNode(n[3],n[7])
            };
        }
        for (int pid : targetParts) {
            auto it = baseMesh_.parts.find(pid);
            if (it != baseMesh_.parts.end() && it->second.sectionId > 0)
                solidSectionElforms_[it->second.sectionId] = elform;
        }
        hex20ConvertedCount_ = static_cast<int>(targets.size());
        infoMessages.push_back("  HEX20: converted " + std::to_string(hex20ConvertedCount_) +
            " elements, added " + std::to_string(edgeMidNodeMap_.size() - midNodesBefore) +
            " mid-edge nodes, ELFORM -> " + std::to_string(elform));
    }
    // --- QUAD4 → QUAD8 ---
    else if (op.convertType == "quad8") {
        int elform = (op.elform > 0) ? op.elform : 23;

        std::vector<std::pair<int, const Element*>> targets;
        std::set<int> targetParts;
        for (const auto& [eid, elem] : baseMesh_.elements) {
            if (elem.type != ElementType::QUAD4) continue;
            // Skip TRIA3 (stored as QUAD4 with n4==n3 or n4==0)
            if (elem.nodeIds[3] == elem.nodeIds[2] || elem.nodeIds[3] == 0) continue;
            if (op.targetPid > 0 && elem.partId != op.targetPid) continue;
            targets.push_back({eid, &elem});
            targetParts.insert(elem.partId);
        }
        if (targets.empty()) {
            infoMessages.push_back("  QUAD8: no QUAD4 elements found" +
                (op.targetPid > 0 ? " in part " + std::to_string(op.targetPid) : ""));
            return true;
        }
        for (const auto& [eid, elem] : targets) {
            const auto& n = elem->nodeIds;
            // QUAD8 mid-edge: N5=mid(1,2), N6=mid(2,3), N7=mid(3,4), N8=mid(4,1)
            quad8Elements_[eid] = {
                n[0], n[1], n[2], n[3],
                getOrCreateMidNode(n[0],n[1]), getOrCreateMidNode(n[1],n[2]),
                getOrCreateMidNode(n[2],n[3]), getOrCreateMidNode(n[3],n[0])
            };
        }
        for (int pid : targetParts) {
            auto it = baseMesh_.parts.find(pid);
            if (it != baseMesh_.parts.end() && it->second.sectionId > 0)
                shellSectionElforms_[it->second.sectionId] = elform;
        }
        quad8ConvertedCount_ = static_cast<int>(targets.size());
        infoMessages.push_back("  QUAD8: converted " + std::to_string(quad8ConvertedCount_) +
            " elements, added " + std::to_string(edgeMidNodeMap_.size() - midNodesBefore) +
            " mid-edge nodes, ELFORM -> " + std::to_string(elform));
    }
    // --- TRIA3 → TRIA6 ---
    else if (op.convertType == "tria6") {
        int elform = (op.elform > 0) ? op.elform : 24;

        std::vector<std::pair<int, const Element*>> targets;
        std::set<int> targetParts;
        for (const auto& [eid, elem] : baseMesh_.elements) {
            if (elem.type != ElementType::QUAD4) continue;
            // TRIA3: stored as QUAD4 with n4==n3 or n4==0
            if (elem.nodeIds[3] != elem.nodeIds[2] && elem.nodeIds[3] != 0) continue;
            if (op.targetPid > 0 && elem.partId != op.targetPid) continue;
            targets.push_back({eid, &elem});
            targetParts.insert(elem.partId);
        }
        if (targets.empty()) {
            infoMessages.push_back("  TRIA6: no TRIA3 elements found" +
                (op.targetPid > 0 ? " in part " + std::to_string(op.targetPid) : ""));
            return true;
        }
        for (const auto& [eid, elem] : targets) {
            const auto& n = elem->nodeIds;
            // TRIA6 mid-edge: N4=mid(1,2), N5=mid(2,3), N6=mid(3,1)
            tria6Elements_[eid] = {
                n[0], n[1], n[2],
                getOrCreateMidNode(n[0],n[1]), getOrCreateMidNode(n[1],n[2]),
                getOrCreateMidNode(n[2],n[0])
            };
        }
        for (int pid : targetParts) {
            auto it = baseMesh_.parts.find(pid);
            if (it != baseMesh_.parts.end() && it->second.sectionId > 0)
                shellSectionElforms_[it->second.sectionId] = elform;
        }
        tria6ConvertedCount_ = static_cast<int>(targets.size());
        infoMessages.push_back("  TRIA6: converted " + std::to_string(tria6ConvertedCount_) +
            " elements, added " + std::to_string(edgeMidNodeMap_.size() - midNodesBefore) +
            " mid-edge nodes, ELFORM -> " + std::to_string(elform));
    }
    else {
        errorMessage_ = "Unknown convert type: " + op.convertType;
        return false;
    }

    return true;
}

bool ModelAssembler::applyRefine(const RefineOperation& op) {
    if (op.ratio != 2 && op.ratio != 3) {
        errorMessage_ = "Refine ratio must be 2 or 3, got " + std::to_string(op.ratio);
        return false;
    }

    // Helper: get or create edge midpoint node (reuses edgeMidNodeMap_)
    auto getOrCreateMidNode = [&](int nA, int nB) -> int {
        auto key = std::make_pair(std::min(nA, nB), std::max(nA, nB));
        auto it = edgeMidNodeMap_.find(key);
        if (it != edgeMidNodeMap_.end()) return it->second;
        int newId = ++maxNodeId_;
        const auto& pA = baseMesh_.nodes.at(nA).position;
        const auto& pB = baseMesh_.nodes.at(nB).position;
        addedNodes_.push_back({newId, (pA.x+pB.x)*0.5, (pA.y+pB.y)*0.5, (pA.z+pB.z)*0.5});
        edgeMidNodeMap_[key] = newId;
        return newId;
    };

    // Helper: get or create edge third-point node (idx=0: 1/3 from nA, idx=1: 2/3 from nA)
    auto getOrCreateThirdNode = [&](int nA, int nB, int idx) -> int {
        auto edgeKey = std::make_pair(std::min(nA, nB), std::max(nA, nB));
        // Normalize: if nA > nB, flip idx (so third-point is always relative to sorted order)
        int normalIdx = (nA < nB) ? idx : (1 - idx);
        auto key = std::make_pair(edgeKey, normalIdx);
        auto it = edgeThirdNodeMap_.find(key);
        if (it != edgeThirdNodeMap_.end()) return it->second;
        int newId = ++maxNodeId_;
        const auto& pA = baseMesh_.nodes.at(nA).position;
        const auto& pB = baseMesh_.nodes.at(nB).position;
        double t = (idx == 0) ? (1.0/3.0) : (2.0/3.0);
        addedNodes_.push_back({newId,
            pA.x + t*(pB.x-pA.x), pA.y + t*(pB.y-pA.y), pA.z + t*(pB.z-pA.z)});
        edgeThirdNodeMap_[key] = newId;
        return newId;
    };

    // Helper: get or create face center node (for shared faces between HEX elements)
    auto getOrCreateFaceCenter = [&](int n1, int n2, int n3, int n4) -> int {
        std::array<int,4> arr = {n1,n2,n3,n4};
        std::sort(arr.begin(), arr.end());
        auto key = std::make_tuple(arr[0], arr[1], arr[2], arr[3]);
        auto it = faceCenterNodeMap_.find(key);
        if (it != faceCenterNodeMap_.end()) return it->second;
        int newId = ++maxNodeId_;
        const auto& p1 = baseMesh_.nodes.at(n1).position;
        const auto& p2 = baseMesh_.nodes.at(n2).position;
        const auto& p3 = baseMesh_.nodes.at(n3).position;
        const auto& p4 = baseMesh_.nodes.at(n4).position;
        addedNodes_.push_back({newId,
            (p1.x+p2.x+p3.x+p4.x)*0.25, (p1.y+p2.y+p3.y+p4.y)*0.25,
            (p1.z+p2.z+p3.z+p4.z)*0.25});
        faceCenterNodeMap_[key] = newId;
        return newId;
    };

    // Helper: create a unique node (no dedup needed - body centers, face interiors)
    auto createNode = [&](double x, double y, double z) -> int {
        int newId = ++maxNodeId_;
        addedNodes_.push_back({newId, x, y, z});
        return newId;
    };

    // Helper: get node position (original nodes only)
    auto pos = [&](int nid) -> Vector3D {
        return baseMesh_.nodes.at(nid).position;
    };

    // Helper: add a sub-hex element
    auto addHex = [&](int pid, int n1, int n2, int n3, int n4, int n5, int n6, int n7, int n8) {
        int eid = ++maxElementId_;
        addedElements_.push_back({eid, pid, {n1,n2,n3,n4,n5,n6,n7,n8}, ElementType::HEX8, false});
    };

    // Helper: add a sub-tet element (stored as degenerate hex)
    auto addTet = [&](int pid, int n1, int n2, int n3, int n4) {
        int eid = ++maxElementId_;
        addedElements_.push_back({eid, pid, {n1,n2,n3,n4,n4,n4,n4,n4}, ElementType::TET4, false});
    };

    // Helper: add a sub-quad shell element
    auto addQuad = [&](int pid, int n1, int n2, int n3, int n4) {
        int eid = ++maxElementId_;
        addedShellElements_.push_back({eid, pid, {n1,n2,n3,n4}});
    };

    // Helper: add a sub-tri shell element (N4=N3 convention)
    auto addTri = [&](int pid, int n1, int n2, int n3) {
        int eid = ++maxElementId_;
        addedShellElements_.push_back({eid, pid, {n1,n2,n3,n3}});
    };

    // Collect target elements by type
    struct TargetElem { int eid; const Element* elem; };
    std::vector<TargetElem> quadTargets, triTargets, hexTargets, tetTargets;

    for (const auto& [eid, elem] : baseMesh_.elements) {
        if (op.targetPid > 0 && elem.partId != op.targetPid) continue;
        if (removedElementIds_.count(eid)) continue;

        if (elem.type == ElementType::QUAD4) {
            bool isTri = (elem.nodeIds[3] == elem.nodeIds[2] || elem.nodeIds[3] == 0);
            if (isTri)
                triTargets.push_back({eid, &elem});
            else
                quadTargets.push_back({eid, &elem});
        } else if (elem.type == ElementType::HEX8) {
            hexTargets.push_back({eid, &elem});
        } else if (elem.type == ElementType::TET4) {
            if (op.ratio == 3) continue; // TET4 1:3 not supported
            tetTargets.push_back({eid, &elem});
        }
    }

    int totalRefined = 0;
    size_t nodesBefore = addedNodes_.size();

    // ==================== RATIO 1:2 ====================
    if (op.ratio == 2) {
        // --- QUAD4 1:2 → 4 quads ---
        for (const auto& t : quadTargets) {
            const auto& n = t.elem->nodeIds;
            int pid = t.elem->partId;
            removedElementIds_.insert(t.eid);

            int m01 = getOrCreateMidNode(n[0], n[1]);
            int m12 = getOrCreateMidNode(n[1], n[2]);
            int m23 = getOrCreateMidNode(n[2], n[3]);
            int m30 = getOrCreateMidNode(n[3], n[0]);
            // Face center (unique per element for shells - no shared faces)
            auto p0 = pos(n[0]), p1 = pos(n[1]), p2 = pos(n[2]), p3 = pos(n[3]);
            int c = createNode((p0.x+p1.x+p2.x+p3.x)*0.25,
                               (p0.y+p1.y+p2.y+p3.y)*0.25,
                               (p0.z+p1.z+p2.z+p3.z)*0.25);

            addQuad(pid, n[0], m01, c, m30);
            addQuad(pid, m01, n[1], m12, c);
            addQuad(pid, c, m12, n[2], m23);
            addQuad(pid, m30, c, m23, n[3]);
            totalRefined++;
        }

        // --- TRIA3 1:2 → 4 tris ---
        for (const auto& t : triTargets) {
            const auto& n = t.elem->nodeIds;
            int pid = t.elem->partId;
            removedElementIds_.insert(t.eid);

            int m01 = getOrCreateMidNode(n[0], n[1]);
            int m12 = getOrCreateMidNode(n[1], n[2]);
            int m20 = getOrCreateMidNode(n[2], n[0]);

            addTri(pid, n[0], m01, m20);
            addTri(pid, m01, n[1], m12);
            addTri(pid, m20, m12, n[2]);
            addTri(pid, m01, m12, m20);
            totalRefined++;
        }

        // --- TET4 1:2 → 8 tets (Bey method, m03-m12 diagonal) ---
        for (const auto& t : tetTargets) {
            const auto& n = t.elem->nodeIds;
            int pid = t.elem->partId;
            removedElementIds_.insert(t.eid);

            int m01 = getOrCreateMidNode(n[0], n[1]);
            int m02 = getOrCreateMidNode(n[0], n[2]);
            int m03 = getOrCreateMidNode(n[0], n[3]);
            int m12 = getOrCreateMidNode(n[1], n[2]);
            int m13 = getOrCreateMidNode(n[1], n[3]);
            int m23 = getOrCreateMidNode(n[2], n[3]);

            // 4 corner tets
            addTet(pid, n[0], m01, m02, m03);
            addTet(pid, m01, n[1], m12, m13);
            addTet(pid, m02, m12, n[2], m23);
            addTet(pid, m03, m13, m23, n[3]);
            // 4 interior tets (octahedron split along m03-m12 diagonal)
            addTet(pid, m01, m12, m02, m03);
            addTet(pid, m01, m12, m03, m13);
            addTet(pid, m12, m23, m03, m02);
            addTet(pid, m12, m23, m13, m03);
            totalRefined++;
        }

        // --- HEX8 1:2 → 8 hexes ---
        for (const auto& t : hexTargets) {
            const auto& n = t.elem->nodeIds;
            int pid = t.elem->partId;
            removedElementIds_.insert(t.eid);

            // 12 edge midpoints
            int e01 = getOrCreateMidNode(n[0], n[1]);
            int e12 = getOrCreateMidNode(n[1], n[2]);
            int e23 = getOrCreateMidNode(n[2], n[3]);
            int e30 = getOrCreateMidNode(n[3], n[0]);
            int e45 = getOrCreateMidNode(n[4], n[5]);
            int e56 = getOrCreateMidNode(n[5], n[6]);
            int e67 = getOrCreateMidNode(n[6], n[7]);
            int e74 = getOrCreateMidNode(n[7], n[4]);
            int e04 = getOrCreateMidNode(n[0], n[4]);
            int e15 = getOrCreateMidNode(n[1], n[5]);
            int e26 = getOrCreateMidNode(n[2], n[6]);
            int e37 = getOrCreateMidNode(n[3], n[7]);

            // 6 face centers (shared between adjacent elements)
            int fb  = getOrCreateFaceCenter(n[0], n[1], n[2], n[3]); // bottom
            int ft  = getOrCreateFaceCenter(n[4], n[5], n[6], n[7]); // top
            int fim = getOrCreateFaceCenter(n[0], n[3], n[7], n[4]); // i- (x-)
            int fip = getOrCreateFaceCenter(n[1], n[2], n[6], n[5]); // i+ (x+)
            int fjm = getOrCreateFaceCenter(n[0], n[1], n[5], n[4]); // j- (y-)
            int fjp = getOrCreateFaceCenter(n[3], n[2], n[6], n[7]); // j+ (y+)

            // 1 body center (unique)
            auto p0=pos(n[0]), p1=pos(n[1]), p2=pos(n[2]), p3=pos(n[3]);
            auto p4=pos(n[4]), p5=pos(n[5]), p6=pos(n[6]), p7=pos(n[7]);
            int bc = createNode(
                (p0.x+p1.x+p2.x+p3.x+p4.x+p5.x+p6.x+p7.x)*0.125,
                (p0.y+p1.y+p2.y+p3.y+p4.y+p5.y+p6.y+p7.y)*0.125,
                (p0.z+p1.z+p2.z+p3.z+p4.z+p5.z+p6.z+p7.z)*0.125);

            // 8 sub-hexes (one per corner)
            addHex(pid, n[0], e01,  fb,  e30,  e04,  fjm,  bc,  fim);
            addHex(pid, e01,  n[1], e12,  fb,  fjm,  e15,  fip,  bc);
            addHex(pid, fb,   e12,  n[2], e23,  bc,  fip,  e26,  fjp);
            addHex(pid, e30,  fb,   e23,  n[3], fim,  bc,  fjp,  e37);
            addHex(pid, e04,  fjm,  bc,   fim,  n[4], e45,  ft,  e74);
            addHex(pid, fjm,  e15,  fip,  bc,   e45,  n[5], e56,  ft);
            addHex(pid, bc,   fip,  e26,  fjp,  ft,   e56,  n[6], e67);
            addHex(pid, fim,  bc,   fjp,  e37,  e74,  ft,   e67,  n[7]);
            totalRefined++;
        }
    }
    // ==================== RATIO 1:3 ====================
    else if (op.ratio == 3) {
        // --- QUAD4 1:3 → 9 quads ---
        for (const auto& t : quadTargets) {
            const auto& n = t.elem->nodeIds;
            int pid = t.elem->partId;
            removedElementIds_.insert(t.eid);

            // Edge third-points (shared via edgeThirdNodeMap_)
            int t01a = getOrCreateThirdNode(n[0], n[1], 0);
            int t01b = getOrCreateThirdNode(n[0], n[1], 1);
            int t12a = getOrCreateThirdNode(n[1], n[2], 0);
            int t12b = getOrCreateThirdNode(n[1], n[2], 1);
            int t23a = getOrCreateThirdNode(n[2], n[3], 0);
            int t23b = getOrCreateThirdNode(n[2], n[3], 1);
            int t30a = getOrCreateThirdNode(n[3], n[0], 0);
            int t30b = getOrCreateThirdNode(n[3], n[0], 1);

            // 4 interior nodes via bilinear interpolation
            auto p0=pos(n[0]), p1=pos(n[1]), p2=pos(n[2]), p3=pos(n[3]);
            auto bilinear = [&](double s, double t_) -> Vector3D {
                return Vector3D(
                    (1-s)*(1-t_)*p0.x + s*(1-t_)*p1.x + s*t_*p2.x + (1-s)*t_*p3.x,
                    (1-s)*(1-t_)*p0.y + s*(1-t_)*p1.y + s*t_*p2.y + (1-s)*t_*p3.y,
                    (1-s)*(1-t_)*p0.z + s*(1-t_)*p1.z + s*t_*p2.z + (1-s)*t_*p3.z);
            };
            auto v00 = bilinear(1.0/3, 1.0/3);
            auto v10 = bilinear(2.0/3, 1.0/3);
            auto v01 = bilinear(1.0/3, 2.0/3);
            auto v11 = bilinear(2.0/3, 2.0/3);
            int i00 = createNode(v00.x, v00.y, v00.z);
            int i10 = createNode(v10.x, v10.y, v10.z);
            int i01 = createNode(v01.x, v01.y, v01.z);
            int i11 = createNode(v11.x, v11.y, v11.z);

            // 9 sub-quads (3×3 grid, row-major bottom→top)
            addQuad(pid, n[0],  t01a, i00,  t30a);
            addQuad(pid, t01a, t01b, i10,  i00);
            addQuad(pid, t01b, n[1],  t12a, i10);
            addQuad(pid, t30a, i00,  i01,  t30b);
            addQuad(pid, i00,  i10,  i11,  i01);
            addQuad(pid, i10,  t12a, t12b, i11);
            addQuad(pid, t30b, i01,  t23b, n[3]);
            addQuad(pid, i01,  i11,  t23a, t23b);
            addQuad(pid, i11,  t12b, n[2],  t23a);
            totalRefined++;
        }

        // --- TRIA3 1:3 → 9 tris ---
        for (const auto& t : triTargets) {
            const auto& n = t.elem->nodeIds;
            int pid = t.elem->partId;
            removedElementIds_.insert(t.eid);

            // Edge third-points
            int t01a = getOrCreateThirdNode(n[0], n[1], 0);
            int t01b = getOrCreateThirdNode(n[0], n[1], 1);
            int t12a = getOrCreateThirdNode(n[1], n[2], 0);
            int t12b = getOrCreateThirdNode(n[1], n[2], 1);
            int t20a = getOrCreateThirdNode(n[2], n[0], 0);
            int t20b = getOrCreateThirdNode(n[2], n[0], 1);

            // Centroid (unique)
            auto p0=pos(n[0]), p1=pos(n[1]), p2=pos(n[2]);
            int ctr = createNode((p0.x+p1.x+p2.x)/3.0,
                                 (p0.y+p1.y+p2.y)/3.0,
                                 (p0.z+p1.z+p2.z)/3.0);

            // 3 corner tris
            addTri(pid, n[0],  t01a, t20b);
            addTri(pid, t01b, n[1],  t12a);
            addTri(pid, t20a, t12b, n[2]);

            // 6 inner tris (fan around centroid)
            addTri(pid, t01a, t01b, ctr);
            addTri(pid, t01b, t12a, ctr);
            addTri(pid, t12a, t12b, ctr);
            addTri(pid, t12b, t20a, ctr);
            addTri(pid, t20a, t20b, ctr);
            addTri(pid, t20b, t01a, ctr);
            totalRefined++;
        }

        // --- HEX8 1:3 → 27 hexes ---
        // Face interior dedup: canonical bilinear ensures consistent node sharing
        // Key: (sorted_face_4tuple, canonical_sub_index) → nodeId
        std::map<std::pair<std::tuple<int,int,int,int>,int>, int> faceInteriorMap;

        // Helper: get or create face interior node with canonical dedup
        // c0,c1,c2,c3: face corners in element's cyclic order
        // s,t: bilinear params in element's face space (1/3 or 2/3)
        auto getOrCreateFaceInterior = [&](int c0, int c1, int c2, int c3,
                                            double s, double t_) -> int {
            // Compute canonical cyclic ordering (start from min ID, go toward smaller neighbor)
            std::array<int,4> cyclic = {c0, c1, c2, c3};
            int minIdx = 0;
            for (int i = 1; i < 4; ++i)
                if (cyclic[i] < cyclic[minIdx]) minIdx = i;
            bool forward = (cyclic[(minIdx+1)%4] < cyclic[(minIdx+3)%4]);
            std::array<int,4> canonical;
            for (int i = 0; i < 4; ++i)
                canonical[i] = forward ? cyclic[(minIdx+i)%4] : cyclic[(minIdx+4-i)%4];

            // Find where each element corner maps in canonical ordering
            int elemToCan[4];
            for (int i = 0; i < 4; ++i)
                for (int j = 0; j < 4; ++j)
                    if (canonical[j] == cyclic[i]) elemToCan[i] = j;

            // Affine transform (s,t) from element face space to canonical face space
            static const double cST[4][2] = {{0,0},{1,0},{1,1},{0,1}};
            double cs = cST[elemToCan[0]][0], ct = cST[elemToCan[0]][1];
            double a = cST[elemToCan[1]][0]-cs, d = cST[elemToCan[1]][1]-ct;
            double b = cST[elemToCan[3]][0]-cs, e = cST[elemToCan[3]][1]-ct;
            double sp = a*s + b*t_ + cs;
            double tp = d*s + e*t_ + ct;

            // Canonical sub-index from canonical (s',t')
            int si = (sp > 0.4) ? 1 : 0;
            int ti = (tp > 0.4) ? 1 : 0;
            int subIdx = si + 2*ti;

            // Dedup key
            std::array<int,4> sortedF = canonical;
            std::sort(sortedF.begin(), sortedF.end());
            auto fKey = std::make_tuple(sortedF[0], sortedF[1], sortedF[2], sortedF[3]);
            auto fullKey = std::make_pair(fKey, subIdx);
            auto fit = faceInteriorMap.find(fullKey);
            if (fit != faceInteriorMap.end()) return fit->second;

            // Compute position from canonical bilinear (bit-exact for shared faces)
            auto p0=pos(canonical[0]), p1=pos(canonical[1]),
                 p2=pos(canonical[2]), p3=pos(canonical[3]);
            double x = (1-sp)*(1-tp)*p0.x + sp*(1-tp)*p1.x + sp*tp*p2.x + (1-sp)*tp*p3.x;
            double y = (1-sp)*(1-tp)*p0.y + sp*(1-tp)*p1.y + sp*tp*p2.y + (1-sp)*tp*p3.y;
            double z = (1-sp)*(1-tp)*p0.z + sp*(1-tp)*p1.z + sp*tp*p2.z + (1-sp)*tp*p3.z;
            int newId = createNode(x, y, z);
            faceInteriorMap[fullKey] = newId;
            return newId;
        };

        for (const auto& t : hexTargets) {
            const auto& n = t.elem->nodeIds;
            int pid = t.elem->partId;
            removedElementIds_.insert(t.eid);

            // Get corner positions for trilinear (body interior only)
            Vector3D p[8];
            for (int i = 0; i < 8; ++i) p[i] = pos(n[i]);

            auto trilinear = [&](double r, double s, double t_) -> Vector3D {
                double w[8] = {
                    (1-r)*(1-s)*(1-t_), r*(1-s)*(1-t_), r*s*(1-t_), (1-r)*s*(1-t_),
                    (1-r)*(1-s)*t_,     r*(1-s)*t_,     r*s*t_,     (1-r)*s*t_
                };
                Vector3D result(0,0,0);
                for (int i = 0; i < 8; ++i) {
                    result.x += w[i] * p[i].x;
                    result.y += w[i] * p[i].y;
                    result.z += w[i] * p[i].z;
                }
                return result;
            };

            // cornerMap: (ci,cj,ck) → HEX8 node index
            static const int cornerMap[2][2][2] = {
                {{0, 4}, {3, 7}},
                {{1, 5}, {2, 6}}
            };

            // Build 4×4×4 grid of node IDs
            int grid[4][4][4];
            double thirds[4] = {0.0, 1.0/3.0, 2.0/3.0, 1.0};

            for (int gi = 0; gi < 4; ++gi) {
                for (int gj = 0; gj < 4; ++gj) {
                    for (int gk = 0; gk < 4; ++gk) {
                        bool iB = (gi == 0 || gi == 3);
                        bool jB = (gj == 0 || gj == 3);
                        bool kB = (gk == 0 || gk == 3);

                        if (iB && jB && kB) {
                            // Corner node
                            int ci=(gi==0)?0:1, cj=(gj==0)?0:1, ck=(gk==0)?0:1;
                            grid[gi][gj][gk] = n[cornerMap[ci][cj][ck]];
                        }
                        else if (iB && jB && !kB) {
                            int ci=(gi==0)?0:1, cj=(gj==0)?0:1;
                            grid[gi][gj][gk] = getOrCreateThirdNode(
                                n[cornerMap[ci][cj][0]], n[cornerMap[ci][cj][1]], gk-1);
                        }
                        else if (iB && !jB && kB) {
                            int ci=(gi==0)?0:1, ck=(gk==0)?0:1;
                            grid[gi][gj][gk] = getOrCreateThirdNode(
                                n[cornerMap[ci][0][ck]], n[cornerMap[ci][1][ck]], gj-1);
                        }
                        else if (!iB && jB && kB) {
                            int cj=(gj==0)?0:1, ck=(gk==0)?0:1;
                            grid[gi][gj][gk] = getOrCreateThirdNode(
                                n[cornerMap[0][cj][ck]], n[cornerMap[1][cj][ck]], gi-1);
                        }
                        else if (iB && !jB && !kB) {
                            // Face interior: i=const face
                            int ci = (gi==0)?0:1;
                            grid[gi][gj][gk] = getOrCreateFaceInterior(
                                n[cornerMap[ci][0][0]], n[cornerMap[ci][1][0]],
                                n[cornerMap[ci][1][1]], n[cornerMap[ci][0][1]],
                                thirds[gj], thirds[gk]);
                        }
                        else if (!iB && jB && !kB) {
                            // Face interior: j=const face
                            int cj = (gj==0)?0:1;
                            grid[gi][gj][gk] = getOrCreateFaceInterior(
                                n[cornerMap[0][cj][0]], n[cornerMap[1][cj][0]],
                                n[cornerMap[1][cj][1]], n[cornerMap[0][cj][1]],
                                thirds[gi], thirds[gk]);
                        }
                        else if (!iB && !jB && kB) {
                            // Face interior: k=const face
                            int ck = (gk==0)?0:1;
                            grid[gi][gj][gk] = getOrCreateFaceInterior(
                                n[cornerMap[0][0][ck]], n[cornerMap[1][0][ck]],
                                n[cornerMap[1][1][ck]], n[cornerMap[0][1][ck]],
                                thirds[gi], thirds[gj]);
                        }
                        else {
                            // Body interior (unique, no dedup)
                            auto v = trilinear(thirds[gi], thirds[gj], thirds[gk]);
                            grid[gi][gj][gk] = createNode(v.x, v.y, v.z);
                        }
                    }
                }
            }

            // 3×3×3 = 27 sub-hexes
            for (int si = 0; si < 3; ++si) {
                for (int sj = 0; sj < 3; ++sj) {
                    for (int sk = 0; sk < 3; ++sk) {
                        addHex(pid,
                            grid[si][sj][sk],     grid[si+1][sj][sk],
                            grid[si+1][sj+1][sk], grid[si][sj+1][sk],
                            grid[si][sj][sk+1],   grid[si+1][sj][sk+1],
                            grid[si+1][sj+1][sk+1], grid[si][sj+1][sk+1]);
                    }
                }
            }
            totalRefined++;
        }

        // TET4 1:3 not supported - already filtered out above
    }

    if (totalRefined == 0) {
        infoMessages.push_back("  Refine 1:" + std::to_string(op.ratio) +
            ": no eligible elements found" +
            (op.targetPid > 0 ? " in part " + std::to_string(op.targetPid) : ""));
        return true;
    }

    size_t nodesAdded = addedNodes_.size() - nodesBefore;
    infoMessages.push_back("  Refine 1:" + std::to_string(op.ratio) +
        ": refined " + std::to_string(totalRefined) + " elements, added " +
        std::to_string(nodesAdded) + " nodes");

    return true;
}

std::string ModelAssembler::formatTet10ElementLine(int eid, int pid, const std::array<int, 10>& nodes) const {
    std::ostringstream oss;
    // Card 1: EID PID
    oss << std::setw(8) << eid << std::setw(8) << pid << "\n";
    // Card 2: N1-N10
    for (int i = 0; i < 10; ++i) {
        oss << std::setw(8) << nodes[i];
    }
    return oss.str();
}

std::string ModelAssembler::formatHex20ElementLine(int eid, int pid, const std::array<int, 20>& nodes) const {
    std::ostringstream oss;
    // Card 1: EID PID
    oss << std::setw(8) << eid << std::setw(8) << pid << "\n";
    // Card 2: N1-N10 (first 10 nodes)
    for (int i = 0; i < 10; ++i) {
        oss << std::setw(8) << nodes[i];
    }
    oss << "\n";
    // Card 3: N11-N20 (remaining 10 nodes)
    for (int i = 10; i < 20; ++i) {
        oss << std::setw(8) << nodes[i];
    }
    return oss.str();
}

std::string ModelAssembler::formatQuad8ElementLine(int eid, int pid, const std::array<int, 8>& nodes) const {
    std::ostringstream oss;
    // Single line: EID PID N1-N8
    oss << std::setw(8) << eid << std::setw(8) << pid;
    for (int i = 0; i < 8; ++i) {
        oss << std::setw(8) << nodes[i];
    }
    return oss.str();
}

std::string ModelAssembler::formatTria6ElementLine(int eid, int pid, const std::array<int, 6>& nodes) const {
    std::ostringstream oss;
    // Single line: EID PID N1-N6 N7(0) N8(0)
    oss << std::setw(8) << eid << std::setw(8) << pid;
    for (int i = 0; i < 6; ++i) {
        oss << std::setw(8) << nodes[i];
    }
    oss << std::setw(8) << 0 << std::setw(8) << 0;
    return oss.str();
}

bool ModelAssembler::applyElform(const ElformOperation& op) {
    // ELFORM alias mapping: string → int
    static const std::map<std::string, int> solidElformAliases = {
        // HEX8 linear
        {"constant_stress", 1},
        {"fully_integrated", 2},
        {"fully_integrated_qm", 3},
        {"fully_integrated_nodal", -1},
        {"fully_integrated_reduced", -2},
        // TET4 linear
        {"tet4", 13},
        {"tet4_10pt", 10},
        {"tet4_60", 60},
        // Quadratic
        {"tet10", 17},
        {"tet10_16", 16},
        {"hex20", 23}
    };

    static const std::map<std::string, int> shellElformAliases = {
        // QUAD4 linear
        {"belytschko_tsay", 2},
        {"fully_integrated_shell", 16},
        {"hughes_liu", 1},
        // Quadratic
        {"quad8", 23},
        {"tria6", 24}
    };

    // Parse target_elform (may be int string or alias)
    int targetElform = 0;
    bool isShell = false;
    try {
        targetElform = std::stoi(op.targetElform);
    } catch (...) {
        // Try alias lookup
        auto sit = solidElformAliases.find(op.targetElform);
        if (sit != solidElformAliases.end()) {
            targetElform = sit->second;
            isShell = false;
        } else {
            auto hit = shellElformAliases.find(op.targetElform);
            if (hit != shellElformAliases.end()) {
                targetElform = hit->second;
                isShell = true;
            } else {
                errorMessage_ = "Unknown ELFORM alias: " + op.targetElform;
                return false;
            }
        }
    }

    // Determine element type (solid vs shell) if not inferred from alias
    // For numeric ELFORM, we infer from value:
    //   23 is ambiguous (HEX20 or QUAD8), default to solid unless part has shells
    //   For now, check target part types
    if (!isShell && targetElform > 0) {
        // Auto-detect: check if target parts have shell elements
        std::vector<int> targetParts;
        if (op.targetPid == 0) {
            for (const auto& [pid, part] : baseMesh_.parts) {
                targetParts.push_back(pid);
            }
        } else {
            targetParts.push_back(op.targetPid);
        }

        // Check if any target part has shell elements
        for (int pid : targetParts) {
            for (const auto& [eid, elem] : baseMesh_.elements) {
                if (elem.partId == pid && elem.type == ElementType::QUAD4) {
                    isShell = true;
                    break;
                }
            }
            if (isShell) break;
        }
    }

    // Determine operation mode based on target ELFORM and base model format
    enum class Mode { SAME_ORDER, UPGRADE, DOWNGRADE };
    Mode mode = Mode::SAME_ORDER;

    // Quadratic ELFORMs trigger upgrade
    const std::set<int> quadraticElforms = {17, 16, 23, 24};
    const std::set<int> linearElforms = {1, 2, 3, -1, -2, 10, 13, 60, 4, 16};

    // Detect if base model has quadratic elements
    // Solid: multi-line format (2-3 tokens per header line)
    // Shell: QUAD8=10 tokens (eid+pid+8nodes), TRIA6=10 tokens (eid+pid+6nodes+0+0)
    bool hasQuadraticSolid = false;
    bool hasQuadraticShell = false;
    bool inSolidSection = false;
    bool inShellSection = false;
    for (const auto& line : rawLines_) {
        std::string trimmed = line;
        size_t start = trimmed.find_first_not_of(" \t");
        if (start != std::string::npos) trimmed = trimmed.substr(start);
        else trimmed.clear();

        if (trimmed.find("*ELEMENT_SOLID") == 0) {
            inSolidSection = true; inShellSection = false;
        } else if (trimmed.find("*ELEMENT_SHELL") == 0) {
            inShellSection = true; inSolidSection = false;
        } else if (!trimmed.empty() && trimmed[0] == '*') {
            inSolidSection = false; inShellSection = false;
        } else if ((inSolidSection || inShellSection) && !trimmed.empty() && trimmed[0] != '$') {
            int tokenCount = 0;
            std::istringstream iss(line);
            std::string token;
            while (iss >> token) tokenCount++;

            if (inSolidSection && tokenCount >= 2 && tokenCount <= 3) {
                hasQuadraticSolid = true;
            }
            if (inShellSection && tokenCount >= 9) {
                // QUAD4=6 tokens, QUAD8/TRIA6=10 tokens
                hasQuadraticShell = true;
            }
        }
    }

    if (quadraticElforms.count(targetElform)) {
        mode = Mode::UPGRADE;
    } else if (linearElforms.count(targetElform) && (hasQuadraticSolid || (isShell && hasQuadraticShell))) {
        mode = Mode::DOWNGRADE;
    }
    // Otherwise mode stays SAME_ORDER

    // Collect target parts and their sections
    std::vector<int> targetParts;
    if (op.targetPid == 0) {
        for (const auto& [pid, part] : baseMesh_.parts) {
            targetParts.push_back(pid);
        }
    } else {
        if (baseMesh_.parts.find(op.targetPid) == baseMesh_.parts.end()) {
            errorMessage_ = "elform: part " + std::to_string(op.targetPid) + " not found";
            return false;
        }
        targetParts.push_back(op.targetPid);
    }

    // Register target ELFORM in section maps
    for (int pid : targetParts) {
        auto it = baseMesh_.parts.find(pid);
        if (it != baseMesh_.parts.end() && it->second.sectionId > 0) {
            if (isShell) {
                shellSectionElforms_[it->second.sectionId] = targetElform;
            } else {
                solidSectionElforms_[it->second.sectionId] = targetElform;
            }
        }
    }

    // Handle different modes
    if (mode == Mode::SAME_ORDER) {
        // Case A: Only ELFORM change, no element connectivity change
        infoMessages.push_back("  ELFORM: changed to " + std::to_string(targetElform) +
                               " for " + std::to_string(targetParts.size()) + " part(s)");
        return true;
    }
    else if (mode == Mode::UPGRADE) {
        // Case B: Linear → Quadratic (reuse applyTet10Convert logic)
        Tet10ConvertOperation convOp;
        convOp.targetPid = op.targetPid;
        convOp.elform = targetElform;

        // Determine convert type from target ELFORM
        if (targetElform == 17 || targetElform == 16) {
            convOp.convertType = "tet10";
        } else if (targetElform == 23 && !isShell) {
            convOp.convertType = "hex20";
        } else if (targetElform == 23 && isShell) {
            convOp.convertType = "quad8";
        } else if (targetElform == 24) {
            convOp.convertType = "tria6";
        } else {
            errorMessage_ = "elform: unsupported upgrade ELFORM " + std::to_string(targetElform);
            return false;
        }

        return applyTet10Convert(convOp);
    }
    else if (mode == Mode::DOWNGRADE) {
        // Case C: Quadratic → Linear (mark elements for downgrade)
        // Collect elements from target parts
        int downgradeCount = 0;
        for (int pid : targetParts) {
            for (const auto& [eid, elem] : baseMesh_.elements) {
                if (elem.partId == pid) {
                    downgradeElementIds_.insert(eid);
                    downgradeCount++;
                }
            }
        }

        infoMessages.push_back("  ELFORM: downgrade to " + std::to_string(targetElform) +
                               " (" + std::to_string(downgradeCount) + " elements)");
        return true;
    }

    return true;
}

// ============================================================================
// Disconnect operation
// ============================================================================
bool ModelAssembler::applyDisconnect(const DisconnectOperation& op) {
    // --- Build active element map (baseMesh_ not-removed + addedElements_ not-removed) ---
    struct ElemData {
        int pid;
        std::array<int, 8> nodeIds;
        bool isTet;
        bool fromAdded;   // true = from addedElements_
        int addedIdx;     // index into addedElements_ (if fromAdded)
    };
    std::map<int, ElemData> activeElems;

    auto isTetNodeIds = [](const std::array<int,8>& nids) -> bool {
        return nids[4] == nids[3] && nids[5] == nids[3] &&
               nids[6] == nids[3] && nids[7] == nids[3];
    };

    for (const auto& [eid, elem] : baseMesh_.elements) {
        if (removedElementIds_.count(eid)) continue;
        if (elem.type == ElementType::QUAD4) continue;
        bool isTet = (elem.type == ElementType::TET4 || isTetNodeIds(elem.nodeIds));
        activeElems[eid] = {elem.partId, elem.nodeIds, isTet, false, -1};
    }
    for (int i = 0; i < static_cast<int>(addedElements_.size()); ++i) {
        const auto& ae = addedElements_[i];
        if (removedElementIds_.count(ae.id)) continue;
        if (ae.isTshell) continue;
        bool isTet = isTetNodeIds(ae.nodeIds);
        activeElems[ae.id] = {ae.pid, ae.nodeIds, isTet, true, i};
    }

    // Helper: get node position from baseMesh_ or addedNodes_
    auto getNodeXYZ = [&](int nid, double& x, double& y, double& z) {
        auto it = baseMesh_.nodes.find(nid);
        if (it != baseMesh_.nodes.end()) {
            x = it->second.position.x; y = it->second.position.y; z = it->second.position.z;
            return;
        }
        for (const auto& an : addedNodes_) {
            if (an.id == nid) { x = an.x; y = an.y; z = an.z; return; }
        }
        x = y = z = 0.0;
    };

    // Helper: get HEX8 face nodes from nodeIds array
    auto getHexFaceNodes = [](const std::array<int,8>& nids, int faceIdx) -> std::array<int,4> {
        auto ln = Element::getFaceLocalNodes(faceIdx);
        return {nids[ln[0]], nids[ln[1]], nids[ln[2]], nids[ln[3]]};
    };

    // Helper: update element connectivity (baseMesh_ or addedElements_)
    auto updateElemNodes = [&](int eid, const std::array<int,8>& newNodes) {
        auto& ed = activeElems.at(eid);
        ed.nodeIds = newNodes;
        if (ed.fromAdded) {
            addedElements_[ed.addedIdx].nodeIds = newNodes;
        } else {
            modifiedElementNodes_[eid] = newNodes;
        }
    };

    // --- Shell (QUAD4) active element map ---
    struct ShellElemData {
        int pid;
        std::array<int, 8> nodeIds;  // 8 for TSHELL, only 4 used for regular shells
        bool fromAdded;
        int addedIdx;
    };
    std::map<int, ShellElemData> activeShellElems;

    for (const auto& [eid, elem] : baseMesh_.elements) {
        if (removedElementIds_.count(eid)) continue;
        if (elem.type != ElementType::QUAD4) continue;
        activeShellElems[eid] = {elem.partId,
            {elem.nodeIds[0], elem.nodeIds[1], elem.nodeIds[2], elem.nodeIds[3]},
            false, -1};
    }
    for (int i = 0; i < static_cast<int>(addedShellElements_.size()); ++i) {
        const auto& ae = addedShellElements_[i];
        if (removedElementIds_.count(ae.id)) continue;
        activeShellElems[ae.id] = {ae.pid, ae.nodeIds, true, i};
    }

    auto updateShellElemNodes = [&](int eid, const std::array<int,8>& newNodes) {
        auto& sed = activeShellElems.at(eid);
        sed.nodeIds = newNodes;
        if (sed.fromAdded) {
            addedShellElements_[sed.addedIdx].nodeIds = newNodes;
        } else {
            // modifiedShellElementNodes_ expects array<int,4>, only copy first 4
            std::array<int, 4> nodes4 = {newNodes[0], newNodes[1], newNodes[2], newNodes[3]};
            modifiedShellElementNodes_[eid] = nodes4;
        }
    };

    // --- Step 1: Collect target elements ---
    std::vector<int> targetElems;
    for (const auto& [eid, ed] : activeElems) {
        if (op.targetPid != 0 && ed.pid != op.targetPid) continue;
        targetElems.push_back(eid);
    }
    std::vector<int> targetShellElems;
    for (const auto& [eid, sed] : activeShellElems) {
        if (op.targetPid != 0 && sed.pid != op.targetPid) continue;
        targetShellElems.push_back(eid);
    }

    if (targetElems.empty() && targetShellElems.empty()) {
        errorMessage_ = "disconnect: no elements found for target";
        return false;
    }

    // --- Step 2: Build face adjacency ---
    using FaceKey = std::array<int, 4>;
    struct FaceEntry { int elemId; int faceIdx; };
    std::map<FaceKey, std::vector<FaceEntry>> faceToElements;

    auto makeFaceKey = [](const std::array<int, 4>& faceNodes) -> FaceKey {
        FaceKey key = faceNodes;
        std::sort(key.begin(), key.end());
        return key;
    };

    for (int eid : targetElems) {
        const auto& ed = activeElems.at(eid);
        if (ed.isTet) {
            int n[4] = {ed.nodeIds[0], ed.nodeIds[1], ed.nodeIds[2], ed.nodeIds[3]};
            std::array<std::array<int,3>, 4> tetFaces = {{
                {n[0], n[2], n[1]}, {n[0], n[1], n[3]},
                {n[1], n[2], n[3]}, {n[0], n[3], n[2]}
            }};
            for (int f = 0; f < 4; ++f) {
                FaceKey key = {tetFaces[f][0], tetFaces[f][1], tetFaces[f][2], tetFaces[f][2]};
                std::sort(key.begin(), key.end());
                faceToElements[key].push_back({eid, f});
            }
        } else {
            for (int f = 0; f < Element::NUM_FACES; ++f) {
                auto faceNodes = getHexFaceNodes(ed.nodeIds, f);
                FaceKey key = makeFaceKey(faceNodes);
                faceToElements[key].push_back({eid, f});
            }
        }
    }

    // --- Step 2b: Shell face adjacency (QUAD4 shell: all 4 nodes = face key) ---
    // Two QUAD4 shell elements sharing all 4 nodes (coincident faces) = interface
    struct ShellSharedFace {
        int elem1;
        int elem2;
        FaceKey faceKey;  // sorted 4 node IDs
        bool interPart;
    };
    std::vector<ShellSharedFace> shellSharedFaces;
    {
        std::map<FaceKey, std::vector<int>> shellFaceToElems;  // faceKey → [elemIds]
        for (int eid : targetShellElems) {
            const auto& sed = activeShellElems.at(eid);
            FaceKey key = {sed.nodeIds[0], sed.nodeIds[1], sed.nodeIds[2], sed.nodeIds[3]};
            std::sort(key.begin(), key.end());
            shellFaceToElems[key].push_back(eid);
        }
        for (const auto& [faceKey, elems] : shellFaceToElems) {
            if (elems.size() == 2) {
                int pid1 = activeShellElems.at(elems[0]).pid;
                int pid2 = activeShellElems.at(elems[1]).pid;
                shellSharedFaces.push_back({elems[0], elems[1], faceKey, pid1 != pid2});
            }
        }
    }

    // --- Step 3: Identify shared solid faces ---
    struct SharedFace {
        int elem1, face1;
        int elem2, face2;
        FaceKey faceKey;
        bool interPart;
    };
    std::vector<SharedFace> sharedFaces;

    for (const auto& [faceKey, entries] : faceToElements) {
        if (entries.size() == 2) {
            int pid1 = activeElems.at(entries[0].elemId).pid;
            int pid2 = activeElems.at(entries[1].elemId).pid;
            sharedFaces.push_back({
                entries[0].elemId, entries[0].faceIdx,
                entries[1].elemId, entries[1].faceIdx,
                faceKey, pid1 != pid2
            });
        }
    }

    // --- Mode dispatch ---
    if (op.mode == "full") {
        // ===== MODE 1: Full Disconnect (Peridynamics) =====
        int newNodeCount = 0;
        for (int eid : targetElems) {
            const auto& ed = activeElems.at(eid);
            int nodeCount = ed.isTet ? 4 : 8;
            std::array<int, 8> newNodeIds;

            for (int n = 0; n < nodeCount; ++n) {
                int origId = ed.nodeIds[n];
                double x, y, z;
                getNodeXYZ(origId, x, y, z);
                int newId = ++maxNodeId_;
                addedNodes_.push_back({newId, x, y, z});
                newNodeIds[n] = newId;
                newNodeCount++;
            }
            if (ed.isTet) {
                for (int n = 4; n < 8; ++n) newNodeIds[n] = newNodeIds[3];
            }

            removedElementIds_.insert(eid);
            ElementType etype = ed.isTet ? ElementType::TET4 : ElementType::HEX8;
            addedElements_.push_back({eid, ed.pid, newNodeIds, etype, false});
        }

        // Register sections for SECTION_SOLID_PERI conversion
        std::set<int> seenSecIds;
        for (int eid : targetElems) {
            const auto& ed = activeElems.at(eid);
            auto pit = baseMesh_.parts.find(ed.pid);
            if (pit != baseMesh_.parts.end() && pit->second.sectionId > 0) {
                int secId = pit->second.sectionId;
                periSectionIds_.insert(secId);
                if (!seenSecIds.count(secId)) {
                    seenSecIds.insert(secId);
                    std::ostringstream kw;
                    kw << "$# SECTION_SOLID_PERI generated by disconnect (full)\n";
                    kw << "$#  secid    elform\n";
                    kw << std::setw(10) << secId << std::setw(10) << 48 << "\n";
                    kw << "$#      dr     ptype\n";
                    kw << "      1.01         1\n";
                    addedKeywordBlocks_.push_back("*SECTION_SOLID_PERI\n" + kw.str());
                }
            }
        }

        infoMessages.push_back("  Disconnect (full): " + std::to_string(targetElems.size()) +
                               " elements, " + std::to_string(newNodeCount) + " new nodes");
        return true;
    }
    else if (op.mode == "czm" || op.mode == "mefem") {
        // ===== MODE 2/3: Selective interface disconnect =====
        // --- Solid inter-part faces ---
        std::vector<SharedFace> interPartFaces;
        for (const auto& sf : sharedFaces) {
            if (sf.interPart) interPartFaces.push_back(sf);
        }

        // --- Shell inter-part faces ---
        std::vector<ShellSharedFace> shellInterPartFaces;
        for (const auto& sf : shellSharedFaces) {
            if (sf.interPart) shellInterPartFaces.push_back(sf);
        }

        if (interPartFaces.empty() && shellInterPartFaces.empty()) {
            errorMessage_ = "disconnect: no inter-part faces found (different PIDs sharing faces)";
            return false;
        }

        // Collect all interface node IDs
        std::set<int> interfaceNodeIds;
        for (const auto& sf : interPartFaces)
            for (int nid : sf.faceKey) interfaceNodeIds.insert(nid);
        for (const auto& sf : shellInterPartFaces)
            for (int nid : sf.faceKey) interfaceNodeIds.insert(nid);

        // Map: nodeId → set of PIDs using it
        std::map<int, std::set<int>> nodeToPartIds;

        for (int eid : targetElems) {
            const auto& ed = activeElems.at(eid);
            for (int n = 0; n < 8; ++n) {
                int nid = ed.nodeIds[n];
                if (interfaceNodeIds.count(nid)) nodeToPartIds[nid].insert(ed.pid);
            }
        }
        for (int eid : targetShellElems) {
            const auto& sed = activeShellElems.at(eid);
            for (int n = 0; n < 4; ++n) {
                int nid = sed.nodeIds[n];
                if (interfaceNodeIds.count(nid)) nodeToPartIds[nid].insert(sed.pid);
            }
        }

        // Create duplicate nodes: lowest PID keeps original, others get copies
        std::map<std::pair<int,int>, int> nodePartRemap;
        int dupNodeCount = 0;

        for (const auto& [nid, pids] : nodeToPartIds) {
            if (pids.size() <= 1) continue;
            int primaryPid = *pids.begin();
            for (int pid : pids) {
                if (pid == primaryPid) {
                    nodePartRemap[{nid, pid}] = nid;
                } else {
                    double x, y, z;
                    getNodeXYZ(nid, x, y, z);
                    int newId = ++maxNodeId_;
                    addedNodes_.push_back({newId, x, y, z});
                    nodePartRemap[{nid, pid}] = newId;
                    dupNodeCount++;
                }
            }
        }

        // Update solid element connectivity
        for (int eid : targetElems) {
            const auto& ed = activeElems.at(eid);
            bool modified = false;
            std::array<int, 8> newNodes = ed.nodeIds;
            for (int n = 0; n < 8; ++n) {
                int nid = ed.nodeIds[n];
                auto it = nodePartRemap.find({nid, ed.pid});
                if (it != nodePartRemap.end() && it->second != nid) {
                    newNodes[n] = it->second;
                    modified = true;
                }
            }
            if (modified) updateElemNodes(eid, newNodes);
        }
        // Update shell element connectivity
        for (int eid : targetShellElems) {
            const auto& sed = activeShellElems.at(eid);
            bool modified = false;
            std::array<int, 8> newNodes = sed.nodeIds;
            for (int n = 0; n < 4; ++n) {
                int nid = sed.nodeIds[n];
                auto it = nodePartRemap.find({nid, sed.pid});
                if (it != nodePartRemap.end() && it->second != nid) {
                    newNodes[n] = it->second;
                    modified = true;
                }
            }
            if (modified) updateShellElemNodes(eid, newNodes);
        }

        if (op.mode == "czm") {
            int cohPartId = op.cohesivePartId > 0 ? op.cohesivePartId : (++maxPartId_);
            int cohSecIdSolid = ++maxSectionId_;
            int cohSecIdShell = (shellInterPartFaces.empty()) ? cohSecIdSolid : (++maxSectionId_);
            int cohMatId = ++maxMaterialId_;
            int cohElemCount = 0;

            // --- Solid cohesive elements (ELFORM=19) ---
            for (const auto& sf : interPartFaces) {
                const auto& ed1 = activeElems.at(sf.elem1);
                const auto& ed2 = activeElems.at(sf.elem2);
                int pidLow  = std::min(ed1.pid, ed2.pid);
                int pidHigh = std::max(ed1.pid, ed2.pid);
                int elemLow = (ed1.pid == pidLow) ? sf.elem1 : sf.elem2;
                int faceLow = (ed1.pid == pidLow) ? sf.face1 : sf.face2;
                const auto& eLow = activeElems.at(elemLow);

                std::array<int, 4> bottomFaceNodes;
                if (!eLow.isTet) {
                    bottomFaceNodes = getHexFaceNodes(eLow.nodeIds, faceLow);
                } else {
                    int n[4] = {eLow.nodeIds[0], eLow.nodeIds[1], eLow.nodeIds[2], eLow.nodeIds[3]};
                    std::array<std::array<int,3>, 4> tetFaces = {{
                        {n[0], n[2], n[1]}, {n[0], n[1], n[3]},
                        {n[1], n[2], n[3]}, {n[0], n[3], n[2]}
                    }};
                    bottomFaceNodes = {tetFaces[faceLow][0], tetFaces[faceLow][1],
                                       tetFaces[faceLow][2], tetFaces[faceLow][2]};
                }

                std::array<int, 8> cohNodes;
                for (int i = 0; i < 4; ++i) {
                    int origNid = bottomFaceNodes[i];
                    auto itL = nodePartRemap.find({origNid, pidLow});
                    cohNodes[i]     = (itL != nodePartRemap.end()) ? itL->second : origNid;
                    auto itH = nodePartRemap.find({origNid, pidHigh});
                    cohNodes[4 + i] = (itH != nodePartRemap.end()) ? itH->second : origNid;
                }
                int cohEid = ++maxElementId_;
                addedElements_.push_back({cohEid, cohPartId, cohNodes, ElementType::HEX8, false});
                cohElemCount++;
            }

            // --- Shell cohesive elements (ELFORM=19, 8-node: bottom+top QUAD4) ---
            // For coincident QUAD4 shells from different parts:
            // Bottom (lower PID): original 4 nodes; Top (higher PID): 4 duplicate nodes
            for (const auto& sf : shellInterPartFaces) {
                const auto& sed1 = activeShellElems.at(sf.elem1);
                const auto& sed2 = activeShellElems.at(sf.elem2);
                int pidLow  = std::min(sed1.pid, sed2.pid);
                int pidHigh = std::max(sed1.pid, sed2.pid);
                int elemLow = (sed1.pid == pidLow) ? sf.elem1 : sf.elem2;
                const auto& seLow = activeShellElems.at(elemLow);

                // The face key is sorted; we need the actual ordered nodes from the lower element
                std::array<int, 8> cohNodes;
                for (int i = 0; i < 4; ++i) {
                    int origNid = seLow.nodeIds[i];
                    auto itL = nodePartRemap.find({origNid, pidLow});
                    cohNodes[i]     = (itL != nodePartRemap.end()) ? itL->second : origNid;
                    auto itH = nodePartRemap.find({origNid, pidHigh});
                    cohNodes[4 + i] = (itH != nodePartRemap.end()) ? itH->second : origNid;
                }
                int cohEid = ++maxElementId_;
                addedElements_.push_back({cohEid, cohPartId, cohNodes, ElementType::HEX8, false});
                cohElemCount++;
            }

            // Generate keyword blocks
            std::ostringstream kwBlock;
            kwBlock << "*MAT_COHESIVE_MIXED_MODE\n";
            kwBlock << "$#     mid        ro     roflg   intfail        en        et       gic      giic\n";
            kwBlock << std::setw(10) << cohMatId
                    << "     0.0         0       0.0     1.0E6     1.0E6       1.0       2.0\n";
            kwBlock << "$#      xmu         t         s       und       utd     gamma\n";
            kwBlock << "       1.0      50.0      30.0       0.0       0.0       1.0\n";
            if (!interPartFaces.empty()) {
                kwBlock << "*SECTION_SOLID\n";
                kwBlock << "$#  secid    elform\n";
                kwBlock << std::setw(10) << cohSecIdSolid << std::setw(10) << 19 << "\n";
            }
            if (!shellInterPartFaces.empty() && cohSecIdShell != cohSecIdSolid) {
                kwBlock << "*SECTION_SOLID\n";
                kwBlock << "$#  secid    elform\n";
                kwBlock << std::setw(10) << cohSecIdShell << std::setw(10) << 19 << "\n";
            }
            int usedSecId = interPartFaces.empty() ? cohSecIdShell : cohSecIdSolid;
            kwBlock << "*PART\n";
            kwBlock << "Cohesive interface\n";
            kwBlock << "$#     pid     secid       mid\n";
            kwBlock << std::setw(10) << cohPartId << std::setw(10) << usedSecId
                    << std::setw(10) << cohMatId << "\n";
            addedKeywordBlocks_.push_back(kwBlock.str());

            int totalIfaces = static_cast<int>(interPartFaces.size() + shellInterPartFaces.size());
            infoMessages.push_back("  Disconnect (czm): " + std::to_string(totalIfaces) +
                                   " interface faces, " + std::to_string(dupNodeCount) +
                                   " new nodes, " + std::to_string(cohElemCount) + " cohesive elements");
        }
        else {
            // MEFEM mode
            int setIdBase = maxPartId_ + 1000;
            int constraintCount = 0;
            std::ostringstream kwBlock;

            for (const auto& [nid, pids] : nodeToPartIds) {
                if (pids.size() <= 1) continue;
                int setId = setIdBase + constraintCount;
                kwBlock << "*SET_NODE_LIST\n";
                kwBlock << "$#     sid\n";
                kwBlock << std::setw(10) << setId << "\n";
                kwBlock << "$#    nid1      nid2      nid3      nid4      nid5      nid6      nid7      nid8\n";

                std::vector<int> nodeGroup;
                for (int pid : pids) {
                    auto it = nodePartRemap.find({nid, pid});
                    if (it != nodePartRemap.end()) nodeGroup.push_back(it->second);
                }
                for (size_t i = 0; i < nodeGroup.size(); ++i) {
                    kwBlock << std::setw(10) << nodeGroup[i];
                    if ((i + 1) % 8 == 0 || i + 1 == nodeGroup.size()) kwBlock << "\n";
                }

                kwBlock << "*CONSTRAINED_TIED_NODES_FAILURE\n";
                kwBlock << "$#    nsid      eppf     etype\n";
                kwBlock << std::setw(10) << setId
                        << std::setw(10) << std::fixed << std::setprecision(3) << op.failureStrain
                        << std::setw(10) << 1 << "\n";
                constraintCount++;
            }

            addedKeywordBlocks_.push_back(kwBlock.str());
            int totalIfaces = static_cast<int>(interPartFaces.size() + shellInterPartFaces.size());
            infoMessages.push_back("  Disconnect (mefem): " + std::to_string(totalIfaces) +
                                   " interface faces, " + std::to_string(dupNodeCount) + " new nodes, " +
                                   std::to_string(constraintCount) + " tied node groups");
        }

        return true;
    }

    errorMessage_ = "disconnect: unknown mode '" + op.mode + "' (use full/czm/mefem)";
    return false;
}

int ModelAssembler::parsePartIdFromLine(const std::string& line) const {
    // Extract second integer field from element line (8-char fixed width)
    if (line.size() < 16) return -1;
    try {
        std::string field = line.substr(8, 8);
        size_t start = 0;
        while (start < field.size() && std::isspace(field[start])) start++;
        if (start >= field.size() || !std::isdigit(field[start])) return -1;
        return std::stoi(field.substr(start));
    } catch (...) {
        return -1;
    }
}

// ============================================================================
// IGA helpers
// ============================================================================

int ModelAssembler::findPartMid(int pid) const {
    // Scan rawLines_ for *PART section matching pid → extract MID (field index 2)
    bool inPart = false;
    bool needTitle = false;
    for (const auto& line : rawLines_) {
        // Detect keyword
        if (!line.empty() && line[0] == '*') {
            std::string upper = line;
            for (auto& c : upper) c = static_cast<char>(std::toupper(static_cast<unsigned char>(c)));
            if (upper.substr(0, 5) == "*PART" && upper.find("_") == std::string::npos) {
                inPart = true;
                needTitle = true;
                continue;
            }
            inPart = false;
            continue;
        }
        if (!inPart) continue;
        // Skip comments
        if (!line.empty() && line[0] == '$') continue;
        if (needTitle) {
            // Title line: skip it
            needTitle = false;
            continue;
        }
        // Data line: tokenize space-separated (fields can be variable width)
        std::istringstream iss(line);
        std::vector<int> fields;
        std::string tok;
        while (iss >> tok) {
            try { fields.push_back(std::stoi(tok)); } catch (...) { break; }
        }
        // fields: [pid, secid, mid, ...]
        if (fields.size() >= 3 && fields[0] == pid) {
            return fields[2];  // MID
        }
        inPart = false;  // Only one data line per *PART
    }
    return -1;  // Not found
}

std::string ModelAssembler::extractMaterialBlock(int origMid, int newMid) const {
    // Scan rawLines_ for *MAT_* keyword blocks, find the one with origMid, copy with newMid
    bool inMat = false;
    bool onFirstData = false;
    std::string result;
    std::string header;

    for (const auto& line : rawLines_) {
        if (!line.empty() && line[0] == '*') {
            if (inMat && !result.empty()) {
                // End of material block - return it
                return result;
            }
            inMat = false;
            onFirstData = false;
            result.clear();
            header.clear();

            std::string upper = line;
            for (auto& c : upper) c = static_cast<char>(std::toupper(static_cast<unsigned char>(c)));
            if (upper.substr(0, 5) == "*MAT_" || upper.substr(0, 4) == "*MAT") {
                inMat = true;
                onFirstData = true;
                header = line;
                continue;
            }
            continue;
        }
        if (!inMat) continue;
        if (!line.empty() && line[0] == '$') {
            // Comment inside material block - include it
            if (!result.empty()) result += line + "\n";
            else header += "\n" + line;  // comment before first data line → append to header
            continue;
        }
        if (onFirstData) {
            // First data line - check if MID matches
            // Try to parse first field (MID can be fixed-width or space-sep)
            int mid = -1;
            // Try space-sep first
            std::istringstream iss(line);
            std::string tok;
            if (iss >> tok) {
                try { mid = std::stoi(tok); } catch (...) {}
            }
            if (mid != origMid) {
                inMat = false;
                result.clear();
                continue;
            }
            // Found our material!
            result = header + "\n";
            // Write first data line with newMid substituted
            // Replace first field in line
            std::string newLine = line;
            size_t pos = 0;
            while (pos < newLine.size() && std::isspace(newLine[pos])) pos++;
            size_t end = pos;
            while (end < newLine.size() && std::isdigit(newLine[end])) end++;
            if (end > pos) {
                std::string midStr = std::to_string(newMid);
                // Preserve field width if possible
                int origWidth = static_cast<int>(end - pos);
                // Right-align in original width
                while (static_cast<int>(midStr.size()) < origWidth) midStr = " " + midStr;
                newLine.replace(pos, end - pos, midStr);
            }
            result += newLine + "\n";
            onFirstData = false;
            continue;
        }
        // Subsequent data lines - copy as-is
        result += line + "\n";
    }
    // End of file with material still open
    if (inMat && !result.empty()) {
        return result;
    }
    return "";  // Not found
}

std::string ModelAssembler::generateIGAContent(
    int newId, int newMid, int fepid,
    double xmin, double xmax, double ymin, double ymax, double zmin, double zmax,
    double rr, double rs, double rt,
    double offR, double offS, double offT,
    int ir, int styp, double tollg,
    int pr, int ps, int pt,
    int nisr, int niss, int nist,
    const std::string& matBlock) const
{
    std::ostringstream o;
    o << "*KEYWORD\n";
    o << "$ IGA solid wrapper for FE part " << fepid << "\n";
    o << "$ Generated by KooRemapper\n";
    o << "$---+----1----+----2----+----3----+----4----+----5----+----6----+----7----+----8\n";

    // PARAMETER_LOCAL
    o << "*PARAMETER_LOCAL\n";
    o << "$    PRMR1      VAL1\n";
    // Format: type+name (left, up to 8 chars), value (right-justified, 10 chars)
    auto pI = [&](const char* name, int val) {
        std::ostringstream pn; pn << "I" << name;
        o << std::left << std::setw(10) << pn.str()
          << std::right << std::setw(10) << val << "\n";
    };
    auto pR = [&](const char* name, double val) {
        std::ostringstream pn; pn << "R" << name;
        o << std::left << std::setw(10) << pn.str();
        // Use %g-style formatting (significant digits, no trailing zeros)
        std::ostringstream vs;
        vs << std::setprecision(7) << val;
        o << std::right << std::setw(10) << vs.str() << "\n";
    };
    pI("id",     newId);
    pI("mid",    newMid);
    pI("fepid",  fepid);
    pR("xmin",   xmin);
    pR("xmax",   xmax);
    pR("ymin",   ymin);
    pR("ymax",   ymax);
    pR("zmin",   zmin);
    pR("zmax",   zmax);
    pR("rr",     rr);
    pR("rs",     rs);
    pR("rt",     rt);
    pR("ofr",    offR);
    pR("ofs",    offS);
    pR("oft",    offT);
    pI("ir",     ir);
    pI("styp",   styp);
    pR("tollg",  tollg);

    // PARAMETER_EXPRESSION_LOCAL (extended bbox via separate offset params)
    o << "*PARAMETER_EXPRESSION_LOCAL\n";
    o << "rxminn, &xmin-&ofr\n";
    o << "rxmaxx, &xmax+&ofr\n";
    o << "ryminn, &ymin-&ofs\n";
    o << "rymaxx, &ymax+&ofs\n";
    o << "rzminn, &zmin-&oft\n";
    o << "rzmaxx, &zmax+&oft\n";

    // Material block (copied with newMid)
    if (!matBlock.empty()) {
        o << matBlock;
    } else {
        o << "$ WARNING: Source material not found - fill in manually\n";
        o << "*MAT_ELASTIC\n";
        o << "$#     mid        ro         e        pr        da        db  not used\n";
        o << std::setw(10) << newMid
          << std::setw(10) << "0.0"
          << std::setw(10) << "0.0"
          << std::setw(10) << "0.0" << "\n";
    }

    // IGA_DEV_STABILIZATION
    o << "*IGA_DEV_STABILIZATION\n";
    o << "$      sid      styp                                   tollg\n";
    o << std::setw(9) << "&id" << std::setw(9) << "&styp"
      << std::setw(43) << "&tollg" << "\n";

    // PART
    o << "*PART\n";
    o << "$#\n";
    o << "IGA_Part_" << fepid << "\n";
    o << "$#     pid     secid       mid     eosid      hgid      grav    adpopt      tmid\n";
    o << std::setw(9) << "&id" << std::setw(9) << "&id" << std::setw(9) << "&mid" << "\n";

    // SECTION_IGA_SOLID
    o << "*SECTION_IGA_SOLID\n";
    o << "$#   secid    elform        ir\n";
    o << std::setw(9) << "&id" << std::setw(9) << "0" << std::setw(9) << "&ir" << "\n";

    // IGA_DEV_VOLUME_XYZ
    o << "*IGA_DEV_VOLUME_XYZ\n";
    o << "$#     vid   patchid       pid      esid      fsid    TETMSH      MYTP\n";
    o << std::setw(9) << "&id" << std::setw(9) << "&id"
      << std::setw(9) << "" << std::setw(9) << "" << std::setw(9) << ""
      << std::setw(9) << "-1" << "\n";
    o << "$#     PID of existing FEA solid with tetmesh\n";
    o << std::setw(9) << "&fepid" << "\n";
    o << "$#   brid1     brid2     brid3     brid4     brid5     brid6     brid7     brid8\n";
    o << "\n";

    // IGA_SOLID
    o << "*IGA_SOLID\n";
    o << "$#     sid       pid      nisr      niss      nist       rid\n";
    o << std::setw(9) << "&id" << std::setw(9) << "&id"
      << std::setw(9) << nisr << std::setw(9) << niss << std::setw(9) << nist
      << std::setw(9) << "&id" << "\n";

    // IGA_3D_NURBS_XYZ
    o << "*IGA_3D_NURBS_XYZ\n";
    o << "$# patchid        nr        ns        nt        pr        ps        pt\n";
    o << std::setw(9) << "&id"
      << std::setw(9) << "2" << std::setw(9) << "2" << std::setw(9) << "2"
      << std::setw(9) << pr  << std::setw(9) << ps  << std::setw(9) << pt << "\n";
    o << "$#    unir      unis      unit\n";
    o << std::setw(9) << "1" << std::setw(9) << "1" << std::setw(9) << "1" << "\n";
    o << "$#            rfirst               rlast\n";
    o << std::setw(20) << "&rxminn" << std::setw(20) << "&rxmaxx" << "\n";
    o << "$#            sfirst               slast\n";
    o << std::setw(20) << "&ryminn" << std::setw(20) << "&rymaxx" << "\n";
    o << "$#            tfirst               tlast\n";
    o << std::setw(20) << "&rzminn" << std::setw(20) << "&rzmaxx" << "\n";
    o << "$#                 x                   y                   z                 wgt\n";
    // 8 corner control points (2×2×2)
    const char* xs[2] = {"&rxminn", "&rxmaxx"};
    const char* ys[2] = {"&ryminn", "&rymaxx"};
    const char* zs[2] = {"&rzminn", "&rzmaxx"};
    for (int k = 0; k < 2; ++k)
        for (int j = 0; j < 2; ++j)
            for (int i = 0; i < 2; ++i)
                o << std::setw(20) << xs[i] << std::setw(20) << ys[j]
                  << std::setw(20) << zs[k] << std::setw(20) << "1.0" << "\n";

    // IGA_REFINE_SOLID
    o << "*IGA_REFINE_SOLID\n";
    o << "$      rid      rtyp\n";
    o << std::setw(9) << "&id" << std::setw(9) << "2" << "\n";
    o << "$    hrtyp        rr        rs        rt\n";
    o << std::setw(9) << "2" << std::setw(9) << "&rr" << std::setw(9) << "&rs" << std::setw(9) << "&rt" << "\n";
    o << "$      itr       its       itt\n";
    o << std::setw(9) << "2" << std::setw(9) << "2" << std::setw(9) << "2" << "\n";

    o << "*END\n";
    return o.str();
}

bool ModelAssembler::applyIGA(const IGAOperation& op, const std::string& outputPrefix) {
    // Derive output basename (no directory, no extension)
    std::string basename = outputPrefix;
    size_t slash = basename.find_last_of("/\\");
    if (slash != std::string::npos) basename = basename.substr(slash + 1);
    // outputPrefix already has no extension, so basename is ready

    for (const auto& tgt : op.targets) {
        int pid = tgt.targetPid;

        // 1. Compute bounding box
        double xmin = std::numeric_limits<double>::max();
        double xmax = -std::numeric_limits<double>::max();
        double ymin = std::numeric_limits<double>::max();
        double ymax = -std::numeric_limits<double>::max();
        double zmin = std::numeric_limits<double>::max();
        double zmax = -std::numeric_limits<double>::max();

        auto nodeIds = getPartNodeIds(pid);
        // Always merge addedElements_ nodes (handles post-replace/restack cases)
        for (const auto& ae : addedElements_) {
            if (ae.pid != pid) continue;
            for (int ni = 0; ni < 8; ++ni) {
                int nid = ae.nodeIds[ni];
                if (nid <= 0) continue;
                nodeIds.insert(nid);
            }
        }
        if (nodeIds.empty()) {
            errorMessage_ = "IGA: part " + std::to_string(pid) + " has no elements";
            return false;
        }

        // Iterate all active nodes
        for (int nid : nodeIds) {
            Vector3D pos;
            // Check modifiedNodePositions_ first
            if (modifiedNodePositions_.count(nid)) {
                pos = modifiedNodePositions_.at(nid);
            } else {
                // Check addedNodes_
                bool found = false;
                for (const auto& an : addedNodes_) {
                    if (an.id == nid) { pos = {an.x, an.y, an.z}; found = true; break; }
                }
                if (!found) {
                    const Node* n = baseMesh_.getNode(nid);
                    if (!n) continue;
                    pos = n->position;
                }
            }
            if (pos.x < xmin) xmin = pos.x;
            if (pos.x > xmax) xmax = pos.x;
            if (pos.y < ymin) ymin = pos.y;
            if (pos.y > ymax) ymax = pos.y;
            if (pos.z < zmin) zmin = pos.z;
            if (pos.z > zmax) zmax = pos.z;
        }

        // 2. Element size per axis (used for NURBS refinement)
        double rr = (tgt.elementSizeR > 0.0) ? tgt.elementSizeR : tgt.elementSize;
        double rs = (tgt.elementSizeS > 0.0) ? tgt.elementSizeS : tgt.elementSize;
        double rt = (tgt.elementSizeT > 0.0) ? tgt.elementSizeT : tgt.elementSize;

        // 3. Compute bbox offset per axis (stored as separate Rofr/Rofs/Roft params)
        // Priority: bbox_scale_r/s/t > bbox_scale > offset >= 0 > auto (element_size)
        double lenR = xmax - xmin;
        double lenS = ymax - ymin;
        double lenT = zmax - zmin;

        auto computeOff = [&](double scaleAxis, double len, double elemSize) -> double {
            // Effective axis scale: per-axis > uniform scale > disabled
            double sc = (scaleAxis > 0.0) ? scaleAxis
                      : (tgt.bboxScale > 0.0) ? tgt.bboxScale : 0.0;
            if (sc > 0.0) {
                // offset = half of the extra length added by scaling
                return (sc - 1.0) / 2.0 * len;
            }
            if (tgt.offset >= 0.0) {
                return tgt.offset;       // fixed offset (uniform)
            }
            return elemSize;             // auto = element_size per axis
        };

        double offR = computeOff(tgt.bboxScaleR, lenR, rr);
        double offS = computeOff(tgt.bboxScaleS, lenS, rs);
        double offT = computeOff(tgt.bboxScaleT, lenT, rt);

        // 3. Allocate new IDs
        int newId = ++maxPartId_;
        if (newId > maxSectionId_) maxSectionId_ = newId;

        // 4. Find original MID and copy material
        int origMid = findPartMid(pid);
        int newMid = ++maxMaterialId_;
        std::string matBlock;
        if (origMid > 0) {
            matBlock = extractMaterialBlock(origMid, newMid);
        }

        // 5. Generate IGA file content
        std::string content = generateIGAContent(
            newId, newMid, pid,
            xmin, xmax, ymin, ymax, zmin, zmax,
            rr, rs, rt,
            offR, offS, offT,
            tgt.ir, tgt.styp, tgt.tollg,
            tgt.pr, tgt.ps, tgt.pt,
            tgt.nisr, tgt.niss, tgt.nist,
            matBlock);

        // 6. Build file paths
        std::string igaBasename = basename + "_iga_p" + std::to_string(pid) + ".k";
        std::string igaFullpath = outputPrefix + "_iga_p" + std::to_string(pid) + ".k";

        igaFiles_.push_back({igaFullpath, igaBasename, content});
        ++igaCount_;

        infoMessages.push_back("  IGA: part " + std::to_string(pid) +
            " → " + igaBasename +
            " (id=" + std::to_string(newId) +
            ", mid=" + std::to_string(newMid) +
            ", bb=[" + std::to_string(xmin) + "," + std::to_string(xmax) + "]×"
            "[" + std::to_string(ymin) + "," + std::to_string(ymax) + "]×"
            "[" + std::to_string(zmin) + "," + std::to_string(zmax) + "]"
            ", off=[" + std::to_string(offR) + "," + std::to_string(offS) + "," + std::to_string(offT) + "])");
    }
    return true;
}

bool ModelAssembler::applyWarpage(const WarpageOperation& op, double E, double nu, const std::string& configDir) {
    // 1. Input validation
    if (!validateWarpageOperation(op, configDir)) {
        return false;
    }

    // 2. Load warpage grid
    WarpageGrid grid;
    std::string datPath = op.datFile;
    // If relative path, make it relative to config directory
    if (!datPath.empty() && datPath[0] != '/' && !(datPath.size() > 1 && datPath[1] == ':')) {
        datPath = configDir + "/" + datPath;
    }

    if (!grid.loadFromFile(datPath, op.maskValue, op.noiseThreshold)) {
        errorMessage_ = "Failed to load warpage data: " + datPath;
        return false;
    }

    // 3. Unit conversion coefficient
    double unitScale = getUnitScale(op.unit);
    std::cout << "[INFO] Warpage unit scale: " << op.unit << " → " << unitScale << " mm\n";

    // 4. Collect part nodes
    auto nodeIds = getPartNodeIds(op.targetPid);
    // Include addedElements_ nodes
    for (const auto& ae : addedElements_) {
        if (ae.pid != op.targetPid) continue;
        for (int ni = 0; ni < 8; ++ni) {
            if (ae.nodeIds[ni] > 0) nodeIds.insert(ae.nodeIds[ni]);
        }
    }

    if (nodeIds.empty()) {
        errorMessage_ = "Warpage: part " + std::to_string(op.targetPid) + " has no nodes";
        return false;
    }

    // 5. Compute part bounding box
    double partXmin = 1e99, partXmax = -1e99;
    double partYmin = 1e99, partYmax = -1e99;
    double partZmin = 1e99, partZmax = -1e99;

    for (int nid : nodeIds) {
        Vector3D pos = getNodePosition(nid);
        partXmin = std::min(partXmin, pos.x);
        partXmax = std::max(partXmax, pos.x);
        partYmin = std::min(partYmin, pos.y);
        partYmax = std::max(partYmax, pos.y);
        partZmin = std::min(partZmin, pos.z);
        partZmax = std::max(partZmax, pos.z);
    }

    // 6. Determine data bbox
    double dataBboxXmin, dataBboxXmax, dataBboxYmin, dataBboxYmax;
    if (op.hasDataBbox) {
        dataBboxXmin = op.dataBboxXmin;
        dataBboxXmax = op.dataBboxXmax;
        dataBboxYmin = op.dataBboxYmin;
        dataBboxYmax = op.dataBboxYmax;
        std::cout << "[INFO] Using user-defined data_bbox: ["
                  << dataBboxXmin << ", " << dataBboxXmax << "] × ["
                  << dataBboxYmin << ", " << dataBboxYmax << "]\n";
    } else {
        dataBboxXmin = partXmin;
        dataBboxXmax = partXmax;
        dataBboxYmin = partYmin;
        dataBboxYmax = partYmax;
        std::cout << "[INFO] Using part bbox as data_bbox (1:1 mapping)\n";
    }

    // 7. Parse coordinate axes
    int axis1, axis2, deflAxis;
    parseAxes(op.plane, op.deflectionAxis, axis1, axis2, deflAxis);

    // 8. Compute curvatures
    grid.computeCurvatures();

    // 9. Debug export
    if (op.debug) {
        grid.exportDebugData(op.debugPrefix);
    }

    // 10. Mode-specific processing
    if (op.mode == "deform") {
        // Direct deformation: move nodes
        for (int nid : nodeIds) {
            Vector3D pos = getNodePosition(nid);

            // Normalized coordinates
            double u = (pos[axis1] - dataBboxXmin) / (dataBboxXmax - dataBboxXmin);
            double v = (pos[axis2] - dataBboxYmin) / (dataBboxYmax - dataBboxYmin);

            // Outside data_bbox handling
            double w = 0.0;
            if (u < 0 || u > 1 || v < 0 || v > 1) {
                if (op.outsideBehavior == "clamp") {
                    u = std::clamp(u, 0.0, 1.0);
                    v = std::clamp(v, 0.0, 1.0);
                    w = grid.interpolate(u, v) * unitScale * op.morphFactor;
                } else if (op.outsideBehavior == "extrapolate") {
                    if (!warnedExtrapolation_) {
                        std::cerr << "[WARNING] Warpage: extrapolating outside data_bbox\n";
                        warnedExtrapolation_ = true;
                    }
                    w = grid.interpolate(u, v) * unitScale * op.morphFactor;
                } else {
                    w = 0.0; // "zero"
                }
            } else {
                w = grid.interpolate(u, v) * unitScale * op.morphFactor;
            }

            // Apply deflection
            pos[deflAxis] += w * deflSign_;
            modifiedNodePositions_[nid] = pos;
        }

        std::cout << "[INFO] Applied deform mode - nodes moved\n";

    } else if (op.mode == "prestress") {
        // Reverse initial stress calculation
        calculateWarpagePrestress(op, grid,
                                 dataBboxXmin, dataBboxXmax,
                                 dataBboxYmin, dataBboxYmax,
                                 unitScale, axis1, axis2, deflAxis,
                                 E, nu);

        // Transfer elementStresses_ to accumulatedResults_
        for (const auto& [eid, stressTensor] : elementStresses_) {
            ElementResult er;
            er.isValid = true;
            er.elementId = eid;
            er.isShell = false;  // Warpage currently only supports solid elements

            // Convert stress tensor to element result format
            er.stress = stressTensor;
            er.stressTop = stressTensor;
            er.stressBottom = stressTensor;  // Uniform through thickness (TODO: vary with z)
            er.vonMisesStress = stressTensor.vonMises();

            accumulatedResults_.push_back(er);
        }

        std::cout << "[INFO] Applied prestress mode - initial stress generated\n";
    }

    // 11. Validation
    validateWarpageResults(op, grid);

    ++warpageParts_;
    return true;
}

bool ModelAssembler::validateWarpageOperation(const WarpageOperation& op, const std::string& configDir) {
    std::vector<std::string> errors;

    // Required parameters
    if (op.targetPid <= 0) {
        errors.push_back("target_pid must be > 0");
    }
    if (op.datFile.empty()) {
        errors.push_back("dat_file is required");
    }

    // plane validation
    if (op.plane != "xy" && op.plane != "yz" && op.plane != "zx") {
        errors.push_back("plane must be xy, yz, or zx");
    }

    // deflection_axis validation
    std::set<std::string> validAxes = {"+x", "-x", "+y", "-y", "+z", "-z", "x", "y", "z"};
    if (validAxes.find(op.deflectionAxis) == validAxes.end()) {
        errors.push_back("deflection_axis must be one of: +x, -x, +y, -y, +z, -z");
    }

    // unit validation
    std::set<std::string> validUnits = {"um", "mm", "m"};
    if (validUnits.find(op.unit) == validUnits.end()) {
        errors.push_back("unit must be one of: um, mm, m");
    }

    // morph_factor validation
    if (op.morphFactor <= 0.0) {
        errors.push_back("morph_factor must be > 0");
    }
    if (op.morphFactor > 10.0) {
        std::cerr << "[WARNING] morph_factor > 10.0 may cause excessive warpage\n";
    }

    // mode validation
    if (op.mode != "prestress" && op.mode != "deform") {
        errors.push_back("mode must be prestress or deform");
    }

    // outside_behavior validation
    std::set<std::string> validBehaviors = {"zero", "clamp", "extrapolate"};
    if (validBehaviors.find(op.outsideBehavior) == validBehaviors.end()) {
        errors.push_back("outside_behavior must be zero, clamp, or extrapolate");
    }

    // data_bbox validation
    if (op.hasDataBbox) {
        if (op.dataBboxXmax <= op.dataBboxXmin) {
            errors.push_back("data_bbox: x_max must be > x_min");
        }
        if (op.dataBboxYmax <= op.dataBboxYmin) {
            errors.push_back("data_bbox: y_max must be > y_min");
        }
    }

    // Output errors
    if (!errors.empty()) {
        errorMessage_ = "Warpage validation failed:\n";
        for (const auto& err : errors) {
            errorMessage_ += "  - " + err + "\n";
        }
        return false;
    }

    return true;
}

void ModelAssembler::calculateWarpagePrestress(
    const WarpageOperation& op,
    const WarpageGrid& grid,
    double dataBboxXmin, double dataBboxXmax,
    double dataBboxYmin, double dataBboxYmax,
    double unitScale,
    int axis1, int axis2, int deflAxis,
    double E, double nu)
{
    if (E <= 0) {
        std::cerr << "[ERROR] Material E not defined for prestress mode\n";
        return;
    }

    double factor = E / (1 - nu*nu);
    std::cout << "[INFO] Material: E=" << E << ", nu=" << nu << "\n";
    std::cout << "[DEBUG] useFiniteStrain = " << (op.useFiniteStrain ? "TRUE" : "FALSE") << "\n";

    // Process each element
    for (auto& [eid, elem] : baseMesh_.getElements()) {
        if (elem.partId != op.targetPid) continue;

        // Compute element centroid
        Vector3D centroid(0, 0, 0);
        int nodeCount = 0;
        for (int ni = 0; ni < 8; ++ni) {
            int nid = elem.nodeIds[ni];
            if (nid <= 0) continue;
            Vector3D pos = getNodePosition(nid);
            centroid = centroid + pos;
            nodeCount++;
        }
        if (nodeCount == 0) continue;
        centroid = centroid * (1.0 / nodeCount);

        // Normalized coordinates
        double u = (centroid[axis1] - dataBboxXmin) / (dataBboxXmax - dataBboxXmin);
        double v = (centroid[axis2] - dataBboxYmin) / (dataBboxYmax - dataBboxYmin);

        if (u < 0 || u > 1 || v < 0 || v > 1) {
            if (op.outsideBehavior != "clamp" && op.outsideBehavior != "extrapolate") {
                continue; // zero behavior
            }
            if (op.outsideBehavior == "clamp") {
                u = std::clamp(u, 0.0, 1.0);
                v = std::clamp(v, 0.0, 1.0);
            }
        }

        // Grid indices
        int i = static_cast<int>(v * (grid.rows() - 1));
        int j = static_cast<int>(u * (grid.cols() - 1));
        i = std::clamp(i, 0, grid.rows() - 1);
        j = std::clamp(j, 0, grid.cols() - 1);

        // Curvatures in physical units
        double physicalLenX = dataBboxXmax - dataBboxXmin;
        double physicalLenY = dataBboxYmax - dataBboxYmin;

        double scaledKappaXX = grid.getCurvatureXX(i, j) * unitScale / (physicalLenX * physicalLenX) * op.morphFactor;
        double scaledKappaYY = grid.getCurvatureYY(i, j) * unitScale / (physicalLenY * physicalLenY) * op.morphFactor;
        double scaledKappaXY = grid.getCurvatureXY(i, j) * unitScale / (physicalLenX * physicalLenY) * op.morphFactor;

        // Distance from neutral surface
        double thickness = getElementThickness(elem);
        double z_neutral = thickness / 2.0;

        // Strains
        double eps_xx, eps_yy, eps_xy;

        if (op.useFiniteStrain) {
            // von Kármán plate theory: finite strain with geometric nonlinearity
            // ε_xx = (1/2)(∂w/∂x)² - z·κ_xx
            // ε_yy = (1/2)(∂w/∂y)² - z·κ_yy
            // γ_xy = (∂w/∂x)(∂w/∂y) - 2z·κ_xy

            double gradX = grid.getGradientX(i, j) * unitScale / physicalLenX * op.morphFactor;
            double gradY = grid.getGradientY(i, j) * unitScale / physicalLenY * op.morphFactor;

            // Debug output for first element
            static bool firstTime = true;
            if (firstTime && eid == 1) {
                std::cout << "[DEBUG] Finite strain enabled\n";
                std::cout << "[DEBUG] Element 1: gradX=" << gradX << ", gradY=" << gradY << "\n";
                std::cout << "[DEBUG] Membrane strain: eps_mem=" << (0.5*gradX*gradX) << "\n";
                std::cout << "[DEBUG] Bending strain: eps_bend=" << (z_neutral*scaledKappaXX*deflSign_) << "\n";
                firstTime = false;
            }

            // Membrane strain (nonlinear) + bending strain (linear)
            eps_xx = 0.5 * gradX * gradX - z_neutral * scaledKappaXX * deflSign_;
            eps_yy = 0.5 * gradY * gradY - z_neutral * scaledKappaYY * deflSign_;
            eps_xy = gradX * gradY - z_neutral * scaledKappaXY * deflSign_;
        } else {
            // Kirchhoff-Love plate theory: small strain (bending only)
            // ε = z·κ
            eps_xx = z_neutral * scaledKappaXX * deflSign_;
            eps_yy = z_neutral * scaledKappaYY * deflSign_;
            eps_xy = z_neutral * scaledKappaXY * deflSign_;
        }

        // Stresses (plane stress)
        double sig_xx = factor * (eps_xx + nu * eps_yy);
        double sig_yy = factor * (eps_yy + nu * eps_xx);
        double sig_xy = (E / (1 + nu)) * eps_xy;

        // Reverse sign
        sig_xx = -sig_xx;
        sig_yy = -sig_yy;
        sig_xy = -sig_xy;

        // Create stress tensor
        StressTensor stress;
        stress.xx = sig_xx;
        stress.yy = sig_yy;
        stress.zz = 0.0;  // Plane stress
        stress.xy = sig_xy;
        stress.yz = 0.0;
        stress.xz = 0.0;

        // Accumulate
        if (elementStresses_.count(eid)) {
            elementStresses_[eid] = elementStresses_[eid] + stress;
        } else {
            elementStresses_[eid] = stress;
        }
    }
}

double ModelAssembler::getUnitScale(const std::string& unit) const {
    static const std::map<std::string, double> scaleMap = {
        {"um", 1.0e-3},   // μm → mm
        {"mm", 1.0},      // mm → mm
        {"m",  1.0e3}     // m → mm
    };

    auto it = scaleMap.find(unit);
    if (it == scaleMap.end()) {
        std::cerr << "[WARNING] Unknown unit '" << unit << "', using um\n";
        return 1.0e-3;
    }

    return it->second;
}

void ModelAssembler::parseAxes(const std::string& plane,
                                const std::string& deflAxis,
                                int& axis1, int& axis2, int& deflection) const
{
    // plane → axis1, axis2
    if (plane == "xy") {
        axis1 = 0; axis2 = 1;  // X, Y
    } else if (plane == "yz") {
        axis1 = 1; axis2 = 2;  // Y, Z
    } else if (plane == "zx") {
        axis1 = 2; axis2 = 0;  // Z, X
    } else {
        throw std::runtime_error("Invalid plane: " + plane);
    }

    // deflection_axis → deflection, sign
    deflSign_ = 1.0;
    if (deflAxis == "+z" || deflAxis == "z") {
        deflection = 2;
    } else if (deflAxis == "-z") {
        deflection = 2; deflSign_ = -1.0;
    } else if (deflAxis == "+x" || deflAxis == "x") {
        deflection = 0;
    } else if (deflAxis == "-x") {
        deflection = 0; deflSign_ = -1.0;
    } else if (deflAxis == "+y" || deflAxis == "y") {
        deflection = 1;
    } else if (deflAxis == "-y") {
        deflection = 1; deflSign_ = -1.0;
    } else {
        throw std::runtime_error("Invalid deflection_axis: " + deflAxis);
    }

    // Validate perpendicularity
    if (deflection == axis1 || deflection == axis2) {
        throw std::runtime_error("deflection_axis must be perpendicular to plane");
    }
}

double ModelAssembler::getElementThickness(const Element& elem) const {
    // Estimate thickness from element bbox Z range
    double zmin = 1e99, zmax = -1e99;
    for (int i = 0; i < 8; ++i) {
        int nid = elem.nodeIds[i];
        if (nid <= 0) continue;
        Vector3D pos = getNodePosition(nid);
        zmin = std::min(zmin, pos.z);
        zmax = std::max(zmax, pos.z);
    }

    double thickness = zmax - zmin;
    if (thickness < 1e-6) {
        // Shell-like thin element: use shell thickness
        return getShellThickness(elem.partId);
    }

    return thickness;
}

void ModelAssembler::validateWarpageResults(const WarpageOperation& op, const WarpageGrid& grid) const {
    // Curvature range check
    auto [minK, maxK] = grid.getCurvatureRange();
    double avgK = grid.getAverageCurvature();

    std::cout << "[INFO] Warpage curvature range: [" << minK << ", " << maxK << "]\n";
    std::cout << "[INFO] Average curvature: " << avgK << "\n";

    if (std::abs(maxK) > 1e6) {
        std::cerr << "[WARNING] Extremely high curvature detected (κ_max = " << maxK << ")\n";
        std::cerr << "          This may indicate data issues or very sharp warpage.\n";
    }

    // Stress range check (prestress mode)
    if (op.mode == "prestress") {
        double maxStress = 0.0;
        for (const auto& [eid, stress] : elementStresses_) {
            double vonMises = stress.vonMises();
            maxStress = std::max(maxStress, vonMises);
        }

        std::cout << "[INFO] Max von Mises prestress: " << maxStress << " MPa\n";
    }

    // Displacement range check (deform mode)
    if (op.mode == "deform") {
        double maxDisp = 0.0;
        for (const auto& [nid, pos] : modifiedNodePositions_) {
            const Node* n = baseMesh_.getNode(nid);
            if (n) {
                Vector3D origPos = n->position;
                double disp = (pos - origPos).magnitude();
                maxDisp = std::max(maxDisp, disp);
            }
        }
        std::cout << "[INFO] Max node displacement: " << maxDisp << "\n";
    }
}

void ModelAssembler::exportStressDistribution(const std::string& filename) const {
    std::ofstream csv(filename);
    csv << "ElementID,Centroid_X,Centroid_Y,Centroid_Z,Sigma_XX,Sigma_YY,Sigma_ZZ,VonMises\n";

    for (const auto& [eid, stress] : elementStresses_) {
        auto it = baseMesh_.getElements().find(eid);
        if (it == baseMesh_.getElements().end()) continue;

        // Compute centroid
        Vector3D centroid(0, 0, 0);
        int nodeCount = 0;
        for (int ni = 0; ni < 8; ++ni) {
            int nid = it->second.nodeIds[ni];
            if (nid <= 0) continue;
            Vector3D pos = getNodePosition(nid);
            centroid = centroid + pos;
            nodeCount++;
        }
        if (nodeCount > 0) {
            centroid = centroid * (1.0 / nodeCount);
        }

        double vonMises = stress.vonMises();

        csv << eid << ","
            << centroid.x << "," << centroid.y << "," << centroid.z << ","
            << stress.xx << "," << stress.yy << "," << stress.zz << ","
            << vonMises << "\n";
    }

    std::cout << "[INFO] Exported stress distribution: " << filename << "\n";
}

Vector3D ModelAssembler::getNodePosition(int nid) const {
    // Check modifiedNodePositions_ first
    if (modifiedNodePositions_.count(nid)) {
        return modifiedNodePositions_.at(nid);
    }

    // Check addedNodes_
    for (const auto& an : addedNodes_) {
        if (an.id == nid) {
            return Vector3D(an.x, an.y, an.z);
        }
    }

    // Base mesh
    const Node* n = baseMesh_.getNode(nid);
    if (n) {
        return n->position;
    }

    return Vector3D(0, 0, 0);
}

double ModelAssembler::getShellThickness(int pid) const {
    // Find SECID for this PID from rawLines_
    int secid = 0;
    for (size_t i = 0; i < rawLines_.size(); ++i) {
        const std::string& line = rawLines_[i];
        if (line.find("*PART") == 0) {
            // Skip title line
            ++i;
            if (i >= rawLines_.size()) break;

            // Data line: PID SECID ...
            const std::string& dataLine = rawLines_[i];
            if (dataLine.empty() || dataLine[0] == '$') continue;

            std::istringstream iss(dataLine);
            int foundPid = 0;
            int foundSecid = 0;
            iss >> foundPid >> foundSecid;

            if (foundPid == pid) {
                secid = foundSecid;
                break;
            }
        }
    }

    if (secid == 0) return 1.0;  // Default thickness

    // Find *SECTION_SHELL with this SECID
    for (size_t i = 0; i < rawLines_.size(); ++i) {
        const std::string& line = rawLines_[i];
        if (line.find("*SECTION_SHELL") == 0) {
            ++i;
            if (i >= rawLines_.size()) break;

            // Data line: SECID ELFORM SHRF NIP PROPT QR/IRID ICOMP SETYP
            const std::string& dataLine = rawLines_[i];
            if (dataLine.empty() || dataLine[0] == '$') continue;

            std::istringstream iss(dataLine);
            int foundSecid = 0;
            iss >> foundSecid;

            if (foundSecid == secid) {
                // Next line: T1 T2 T3 T4 NLOC
                ++i;
                if (i >= rawLines_.size()) break;
                const std::string& t_line = rawLines_[i];
                if (t_line.empty() || t_line[0] == '$') continue;

                std::istringstream tiss(t_line);
                double t1 = 0.0;
                tiss >> t1;
                return t1;
            }
        }
    }

    return 1.0;  // Default
}

// ========== OFFSET OPERATION ==========

bool ModelAssembler::applyOffset(const OffsetOperation& op, double E, double nu) {
    std::cout << "[INFO] Applying offset operation on PID " << op.sourcePid << "\n";

    // Check for dual offset mode
    bool isDualOffset = (op.prestressMode == "dual_offset");
    if (isDualOffset) {
        return applyDualOffsetPrestress(op, E, nu);
    }

    // Check for multi-material mode
    bool isMultiMaterial = !op.materialCards.empty();
    if (isMultiMaterial) {
        std::cout << "[INFO] Multi-material mode: " << op.materialCards.size() << " layers\n";
        return applyMultiMaterialOffset(op, E, nu);
    }

    // Normal offset mode
    // 1. Validation - check if any elements exist with this PID
    bool foundPid = false;
    for (const auto& pair : baseMesh_.getElements()) {
        if (pair.second.partId == op.sourcePid) {
            foundPid = true;
            break;
        }
    }
    if (!foundPid) {
        // Also check addedElements_
        for (const auto& elem : addedElements_) {
            if (elem.pid == op.sourcePid) {
                foundPid = true;
                break;
            }
        }
    }
    if (!foundPid) {
        errorMessage_ = "Source PID " + std::to_string(op.sourcePid) + " not found";
        return false;
    }

    // 2. Auto-assign IDs (placeholder - will implement getNextPartId later)
    int actualPid = (op.newPid > 0) ? op.newPid : (++maxPartId_);
    int actualSecid = (op.newSecid > 0) ? op.newSecid : (++maxSectionId_);
    int actualMid = (op.newMid > 0) ? op.newMid : (++maxMaterialId_);

    std::cout << "[INFO] New IDs: PID=" << actualPid
              << ", SECID=" << actualSecid
              << ", MID=" << actualMid << "\n";

    // 3. Extract source surface
    std::vector<ShellElement> sourceSurface;
    extractSourceSurface(op.sourcePid, sourceSurface);

    if (sourceSurface.empty()) {
        errorMessage_ = "No surface elements found in source PID "
                       + std::to_string(op.sourcePid);
        return false;
    }

    std::cout << "[INFO] Extracted " << sourceSurface.size()
              << " surface elements\n";

    // 3.5 Apply region filtering
    filterSurfaceByRegion(sourceSurface, op.region);

    if (sourceSurface.empty()) {
        errorMessage_ = "No surface elements remain after region filtering";
        return false;
    }

    // 4. Parse offset direction
    // "both" mode: shell becomes mid-plane, extrude ±thickness/2
    bool isBothMode = (op.offsetDirection == "both");
    if (isBothMode) {
        std::cout << "[INFO] Both-side offset: shell as mid-plane, thickness="
                  << op.thickness << " mm (±" << op.thickness / 2.0 << ")\n";
    }

    // For "both" mode, treat as +normal internally
    std::string effectiveDirection = isBothMode ? "+normal" : op.offsetDirection;
    Vector3D offsetDir = parseOffsetDirection(effectiveDirection, sourceSurface);
    std::cout << "[INFO] Offset direction: ("
              << offsetDir.x << ", " << offsetDir.y << ", " << offsetDir.z << ")\n";

    // Check if using local normals
    bool usingLocalNormals = (op.useLocalNormals || isBothMode) &&
                             (effectiveDirection == "+normal" || effectiveDirection == "normal" ||
                              effectiveDirection == "-normal");
    if (usingLocalNormals) {
        std::cout << "[INFO] Using local normals (per-node averaged)\n";
    }

    // "both" mode: shift source surface nodes by -thickness/2 along normal
    if (isBothMode) {
        double halfThickness = op.thickness / 2.0;
        std::map<int, Vector3D> perNodeNormals = computePerNodeNormals(sourceSurface);
        std::map<int, int> shiftedNodeMap;  // origNid -> newNid

        for (const auto& shell : sourceSurface) {
            for (int i = 0; i < 4; ++i) {
                int origNid = shell.nodeIds[i];
                if (origNid <= 0 || shiftedNodeMap.count(origNid)) continue;

                int newNid = ++maxNodeId_;
                Vector3D origPos = getNodePosition(origNid);
                Vector3D normal = perNodeNormals.count(origNid)
                    ? perNodeNormals[origNid] : offsetDir;
                Vector3D shiftedPos = origPos - normal * halfThickness;

                AddedNode an;
                an.id = newNid;
                an.x = shiftedPos.x;
                an.y = shiftedPos.y;
                an.z = shiftedPos.z;
                addedNodes_.push_back(an);
                shiftedNodeMap[origNid] = newNid;
            }
        }

        // Replace surface node IDs with shifted nodes
        for (auto& shell : sourceSurface) {
            for (int i = 0; i < 4; ++i) {
                if (shell.nodeIds[i] > 0 && shiftedNodeMap.count(shell.nodeIds[i])) {
                    shell.nodeIds[i] = shiftedNodeMap[shell.nodeIds[i]];
                }
            }
        }
        std::cout << "[INFO] Shifted " << shiftedNodeMap.size()
                  << " nodes by -" << halfThickness << " mm (bottom face)\n";
    }

    // 5. Create offset geometry based on element type
    std::vector<AddedElement> offsetElements;

    if (op.elementType == "solid") {
        size_t startCount = addedElements_.size();

        // Check if using variable thickness
        bool usingVariableThickness = !op.thicknessFormula.empty();

        if (usingVariableThickness) {
            // Compute per-node thickness from formula
            std::map<int, double> perNodeThickness =
                computePerNodeThickness(sourceSurface, op.thicknessFormula, op.thickness);

            std::cout << "[INFO] Using variable thickness formula\n";

            // Use variable thickness extrusion (with global or local normals)
            if (usingLocalNormals) {
                // Compute per-node normals
                std::map<int, Vector3D> perNodeNormals = computePerNodeNormals(sourceSurface);

                // Apply sign for -normal direction
                if (effectiveDirection == "-normal") {
                    for (auto& pair : perNodeNormals) {
                        pair.second = pair.second * -1.0;
                    }
                }

                std::cout << "[INFO] Using local normals + variable thickness (combined)\n";

                // Use COMBINED overload: both per-node directions AND per-node thickness
                extrudeToSolid(sourceSurface, perNodeNormals, perNodeThickness,
                              op.numLayers, actualPid, actualSecid);
            } else {
                // Variable thickness with global direction
                extrudeToSolid(sourceSurface, offsetDir, perNodeThickness,
                              op.numLayers, actualPid, actualSecid);
            }

        } else if (usingLocalNormals) {
            // Compute per-node normals
            std::map<int, Vector3D> perNodeNormals = computePerNodeNormals(sourceSurface);

            // Apply sign for -normal direction
            if (effectiveDirection == "-normal") {
                for (auto& pair : perNodeNormals) {
                    pair.second = pair.second * -1.0;
                }
            }

            // Use local normal extrusion
            extrudeToSolid(sourceSurface, perNodeNormals, op.thickness,
                          op.numLayers, actualPid, actualSecid);
        } else {
            // Use global direction extrusion
            extrudeToSolid(sourceSurface, offsetDir, op.thickness,
                          op.numLayers, actualPid, actualSecid);
        }

        // Collect newly created elements for connection mode processing
        for (size_t i = startCount; i < addedElements_.size(); ++i) {
            offsetElements.push_back(addedElements_[i]);
        }

    } else if (op.elementType == "tshell") {
        double thickness = (op.shellThickness > 0) ? op.shellThickness : op.thickness;
        extrudeToTShell(sourceSurface, offsetDir, thickness,
                       op.numLayers, actualPid, actualSecid);
        std::cout << "[INFO] TSHELL extrusion completed\n";

    } else if (op.elementType == "shell") {
        double thickness = (op.shellThickness > 0) ? op.shellThickness : op.thickness;
        double offset = (op.shellOffset >= 0) ? op.shellOffset : (thickness / 2.0);
        createOffsetShell(sourceSurface, offsetDir, offset,
                         actualPid, actualSecid, thickness);
        std::cout << "[INFO] Shell offset completed\n";

    } else {
        errorMessage_ = "Unknown element_type: " + op.elementType;
        return false;
    }

    // 6. Apply connection mode (only for solid elements)
    if (op.elementType == "solid") {
        if (op.connectionMode == "tied") {
            applyConnectionTied(sourceSurface, offsetElements);

        } else if (op.connectionMode == "czm") {
            // Need to update addedElements_ with modified connectivity
            size_t startIdx = addedElements_.size() - offsetElements.size();
            for (size_t i = 0; i < offsetElements.size(); ++i) {
                addedElements_[startIdx + i] = offsetElements[i];
            }
            applyConnectionCZM(sourceSurface, offsetElements, op);

            // Update again after CZM modifications
            for (size_t i = 0; i < offsetElements.size(); ++i) {
                addedElements_[startIdx + i] = offsetElements[i];
            }

        } else if (op.connectionMode == "contact") {
            // Need to update addedElements_ with modified connectivity
            size_t startIdx = addedElements_.size() - offsetElements.size();
            for (size_t i = 0; i < offsetElements.size(); ++i) {
                addedElements_[startIdx + i] = offsetElements[i];
            }
            applyConnectionContact(sourceSurface, offsetElements, op.sourcePid, actualPid);

            // Update again after contact modifications
            for (size_t i = 0; i < offsetElements.size(); ++i) {
                addedElements_[startIdx + i] = offsetElements[i];
            }
        }
    }

    // 7. Create PART keyword
    createPartKeyword(actualPid, actualSecid, actualMid, op.partTitle);

    // 8. Create SECTION keyword
    if (op.elementType == "solid") {
        createSectionSolid(actualSecid);
    } else if (op.elementType == "tshell") {
        double thickness = (op.shellThickness > 0) ? op.shellThickness : op.thickness;
        int elform = 16;  // Default TSHELL4 (user can override with ELFORM operation)
        createSectionTShell(actualSecid, thickness, elform);
    } else if (op.elementType == "shell") {
        double thickness = (op.shellThickness > 0) ? op.shellThickness : op.thickness;
        createSectionShell(actualSecid, thickness);
    }

    // 9. Insert material card
    if (!op.materialCard.empty()) {
        insertMaterialCard(op.materialCard, actualMid);
    }

    // Element quality check
    if (!addedElements_.empty()) {
        std::cout << "[INFO] Checking element quality...\n";
        ElementQualityChecker qualityChecker;
        ElementQualityChecker::QualitySummary summary;
        summary.totalElements = static_cast<int>(addedElements_.size());

        for (const auto& elem : addedElements_) {
            // Get node positions
            std::array<Vector3D, 8> nodePositions;
            for (int i = 0; i < 8; ++i) {
                int nid = elem.nodeIds[i];
                bool found = false;

                // Check added nodes (vector)
                for (const auto& node : addedNodes_) {
                    if (node.id == nid) {
                        nodePositions[i] = Vector3D(node.x, node.y, node.z);
                        found = true;
                        break;
                    }
                }

                // Check base mesh if not found
                if (!found) {
                    auto baseNode = baseMesh_.nodes.find(nid);
                    if (baseNode != baseMesh_.nodes.end()) {
                        nodePositions[i] = baseNode->second.position;
                    }
                }
            }

            auto metrics = qualityChecker.checkHex8(nodePositions);

            if (metrics.aspectRatio > ElementQualityChecker::ASPECT_RATIO_ERROR) {
                summary.veryPoorAspectRatio++;
            } else if (metrics.aspectRatio > ElementQualityChecker::ASPECT_RATIO_WARN) {
                summary.poorAspectRatio++;
            }

            if (metrics.minJacobian <= ElementQualityChecker::MIN_JACOBIAN_ERROR) {
                summary.negativeJacobian++;
            } else if (metrics.minJacobian < ElementQualityChecker::MIN_JACOBIAN_WARN) {
                summary.poorJacobian++;
            }

            if (metrics.maxWarping > ElementQualityChecker::MAX_WARPING_ERROR) {
                summary.severeWarping++;
            } else if (metrics.maxWarping > ElementQualityChecker::MAX_WARPING_WARN) {
                summary.poorWarping++;
            }

            summary.maxAspectRatio = std::max(summary.maxAspectRatio, metrics.aspectRatio);
            summary.minJacobian = std::min(summary.minJacobian, metrics.minJacobian);
            summary.maxWarping = std::max(summary.maxWarping, metrics.maxWarping);
        }

        // Report quality issues
        if (summary.negativeJacobian > 0) {
            std::cout << "[ERROR] " << summary.negativeJacobian << " elements with negative/zero Jacobian!\n";
            std::cout << "        Minimum Jacobian: " << summary.minJacobian << "\n";
        }

        if (summary.veryPoorAspectRatio > 0) {
            std::cout << "[WARNING] " << summary.veryPoorAspectRatio << " elements with aspect ratio > "
                      << ElementQualityChecker::ASPECT_RATIO_ERROR << "\n";
        } else if (summary.poorAspectRatio > 0) {
            std::cout << "[WARNING] " << summary.poorAspectRatio << " elements with aspect ratio > "
                      << ElementQualityChecker::ASPECT_RATIO_WARN << "\n";
        }
        if (summary.maxAspectRatio > 1.0) {
            std::cout << "          Max aspect ratio: " << std::fixed << std::setprecision(2)
                      << summary.maxAspectRatio << "\n";
        }

        if (summary.severeWarping > 0) {
            std::cout << "[WARNING] " << summary.severeWarping << " elements with warping > "
                      << ElementQualityChecker::MAX_WARPING_ERROR << "°\n";
        } else if (summary.poorWarping > 0) {
            std::cout << "[WARNING] " << summary.poorWarping << " elements with warping > "
                      << ElementQualityChecker::MAX_WARPING_WARN << "°\n";
        }
        if (summary.maxWarping > 0.1) {
            std::cout << "          Max warping: " << std::fixed << std::setprecision(1)
                      << summary.maxWarping << "°\n";
        }

        if (summary.negativeJacobian == 0 && summary.poorJacobian == 0) {
            std::cout << "[OK] All elements have acceptable Jacobian (min: "
                      << std::fixed << std::setprecision(3) << summary.minJacobian << ")\n";
        }

        // Self-intersection check (only for +normal/-normal/both directions with concave surfaces)
        if (effectiveDirection == "+normal" || effectiveDirection == "-normal") {
            std::cout << "[INFO] Checking for self-intersections...\n";
            IntersectionDetector intersectionDetector;

            // Collect element geometries
            std::vector<std::array<Vector3D, 8>> elementGeometries;
            elementGeometries.reserve(addedElements_.size());

            for (const auto& elem : addedElements_) {
                std::array<Vector3D, 8> nodePositions;
                for (int i = 0; i < 8; ++i) {
                    int nid = elem.nodeIds[i];
                    bool found = false;

                    for (const auto& node : addedNodes_) {
                        if (node.id == nid) {
                            nodePositions[i] = Vector3D(node.x, node.y, node.z);
                            found = true;
                            break;
                        }
                    }

                    if (!found) {
                        auto baseNode = baseMesh_.nodes.find(nid);
                        if (baseNode != baseMesh_.nodes.end()) {
                            nodePositions[i] = baseNode->second.position;
                        }
                    }
                }
                elementGeometries.push_back(nodePositions);
            }

            // Quick check using bounding boxes
            int potentialIntersections = intersectionDetector.countPotentialIntersections(
                elementGeometries, op.thickness * 0.01);

            if (potentialIntersections > 0) {
                std::cout << "[WARNING] Potential self-intersections detected: "
                          << potentialIntersections << " overlapping element pairs\n";
                std::cout << "          This may occur with concave surfaces and +normal offset\n";
                std::cout << "          Suggestions:\n";
                std::cout << "            - Use fixed direction (±x/±y/±z) instead of ±normal\n";
                std::cout << "            - Reduce offset distance (current: "
                          << std::fixed << std::setprecision(2) << op.thickness << " mm)\n";
                std::cout << "            - Use region selection to exclude concave areas\n";
            } else {
                std::cout << "[OK] No self-intersections detected\n";
            }
        }
    }

    std::cout << "[INFO] Offset operation completed\n";
    return true;
}

// ========== PHASE 5: SURFACE EXTRACTION ==========

void ModelAssembler::extractSourceSurface(int sourcePid,
                                         std::vector<ShellElement>& surfaceShells) {

    // First check if source PID has shell elements in addedShellElements_
    bool hasShells = false;

    for (const auto& shell : addedShellElements_) {
        if (shell.pid == sourcePid) {
            ShellElement s;
            s.id = shell.id;
            s.partId = shell.pid;
            for (int i = 0; i < 4; ++i) {
                s.nodeIds[i] = shell.nodeIds[i];
            }
            surfaceShells.push_back(s);
            hasShells = true;
        }
    }

    if (hasShells) {
        std::cout << "[INFO] Extracted " << surfaceShells.size()
                  << " shell elements from source\n";
        return;
    }

    // If no shells, extract outer surface from solid elements
    std::cout << "[INFO] Extracting outer surface from solid elements\n";

    // Build face→element map
    // Map: sorted key → (count, original winding order)
    std::map<std::array<int,4>, std::pair<int, std::array<int,4>>> faceToElem;

    // Process baseMesh elements
    for (const auto& pair : baseMesh_.getElements()) {
        const Element& elem = pair.second;
        if (elem.partId != sourcePid) continue;

        // Get number of faces (6 for HEX8, 4 for TET4)
        int numFaces = (elem.nodeIds[4] == elem.nodeIds[7]) ? 4 : 6;

        for (int fi = 0; fi < numFaces; ++fi) {
            auto faceNodes = elem.getFaceNodeIds(fi);

            // Store original winding order
            std::array<int,4> originalWinding = {faceNodes[0], faceNodes[1],
                                                  faceNodes[2], faceNodes[3]};

            // Sort for canonical key
            std::sort(faceNodes.begin(), faceNodes.end());
            std::array<int,4> key = {faceNodes[0], faceNodes[1],
                                     faceNodes[2], faceNodes[3]};

            if (faceToElem.find(key) == faceToElem.end()) {
                faceToElem[key] = {1, originalWinding};
            } else {
                faceToElem[key].first++;
            }
        }
    }

    // Also process addedElements_
    for (const auto& elem : addedElements_) {
        if (elem.pid != sourcePid) continue;

        Element e;
        e.nodeIds = elem.nodeIds;
        e.type = elem.type;

        int numFaces = (e.nodeIds[4] == e.nodeIds[7]) ? 4 : 6;

        for (int fi = 0; fi < numFaces; ++fi) {
            auto faceNodes = e.getFaceNodeIds(fi);

            // Store original winding order
            std::array<int,4> originalWinding = {faceNodes[0], faceNodes[1],
                                                  faceNodes[2], faceNodes[3]};

            std::sort(faceNodes.begin(), faceNodes.end());
            std::array<int,4> key = {faceNodes[0], faceNodes[1],
                                     faceNodes[2], faceNodes[3]};

            if (faceToElem.find(key) == faceToElem.end()) {
                faceToElem[key] = {1, originalWinding};
            } else {
                faceToElem[key].first++;
            }
        }
    }

    // Faces with count=1 are outer surface
    for (const auto& mapPair : faceToElem) {
        if (mapPair.second.first == 1) {
            const std::array<int,4>& originalWinding = mapPair.second.second;
            ShellElement shell;
            shell.id = 0;  // Temporary
            shell.partId = sourcePid;
            // Use original winding order, not sorted key
            shell.nodeIds[0] = originalWinding[0];
            shell.nodeIds[1] = originalWinding[1];
            shell.nodeIds[2] = originalWinding[2];
            shell.nodeIds[3] = originalWinding[3];
            surfaceShells.push_back(shell);
        }
    }

    std::cout << "[INFO] Extracted " << surfaceShells.size()
              << " surface faces from solid\n";
}

// ========== PHASE 6: HELPER METHODS ==========

Vector3D ModelAssembler::computeElementNormal(const ShellElement& shell) {
    Vector3D p0 = getNodePosition(shell.nodeIds[0]);
    Vector3D p1 = getNodePosition(shell.nodeIds[1]);
    Vector3D p2 = getNodePosition(shell.nodeIds[2]);

    Vector3D v1 = p1 - p0;
    Vector3D v2 = p2 - p0;
    Vector3D normal = v1.cross(v2);

    double len = normal.magnitude();
    if (len > 1e-10) {
        return normal * (1.0 / len);
    }
    return Vector3D(0, 0, 1);
}

Vector3D ModelAssembler::computeAverageNormal(const std::vector<ShellElement>& shells) {
    Vector3D sum(0, 0, 0);
    for (const auto& shell : shells) {
        sum = sum + computeElementNormal(shell);
    }
    double len = sum.magnitude();
    if (len > 1e-10) {
        return sum * (1.0 / len);
    }
    return Vector3D(0, 0, 1);
}

std::map<int, Vector3D> ModelAssembler::computePerNodeNormals(const std::vector<ShellElement>& shells) {
    // For each node, collect all adjacent shell normals and average them
    std::map<int, std::vector<Vector3D>> nodeToNormals;

    for (const auto& shell : shells) {
        Vector3D shellNormal = computeElementNormal(shell);

        // Add this shell's normal to all its nodes
        for (int i = 0; i < 4; ++i) {
            int nid = shell.nodeIds[i];
            if (nid > 0) {  // Valid node ID
                nodeToNormals[nid].push_back(shellNormal);
            }
        }
    }

    // Average the normals for each node
    std::map<int, Vector3D> perNodeNormals;
    for (const auto& pair : nodeToNormals) {
        int nid = pair.first;
        const std::vector<Vector3D>& normals = pair.second;

        Vector3D sum(0, 0, 0);
        for (const auto& n : normals) {
            sum = sum + n;
        }

        double len = sum.magnitude();
        if (len > 1e-10) {
            perNodeNormals[nid] = sum * (1.0 / len);
        } else {
            perNodeNormals[nid] = Vector3D(0, 0, 1);
        }
    }

    return perNodeNormals;
}

void ModelAssembler::filterSurfaceByRegion(std::vector<ShellElement>& surface,
                                           const RegionSelection& region) {
    if (!region.useBoundingBox &&
        region.nodeIds.empty() && region.elementIds.empty() &&
        region.nodeIdMin == 0 && region.elementIdMin == 0) {
        // No filtering needed
        return;
    }

    size_t originalSize = surface.size();
    std::vector<ShellElement> filtered;

    for (const auto& shell : surface) {
        bool keep = true;

        // Bounding box filter
        if (region.useBoundingBox) {
            // Check if shell centroid is within bounding box
            Vector3D centroid(0, 0, 0);
            int validNodes = 0;

            for (int i = 0; i < 4; ++i) {
                if (shell.nodeIds[i] > 0) {
                    Vector3D pos = getNodePosition(shell.nodeIds[i]);
                    centroid = centroid + pos;
                    validNodes++;
                }
            }

            if (validNodes > 0) {
                centroid = centroid * (1.0 / validNodes);

                if (centroid.x < region.xMin || centroid.x > region.xMax ||
                    centroid.y < region.yMin || centroid.y > region.yMax ||
                    centroid.z < region.zMin || centroid.z > region.zMax) {
                    keep = false;
                }
            }
        }

        // Node ID filter
        if (keep && !region.nodeIds.empty()) {
            bool hasMatchingNode = false;
            for (int i = 0; i < 4; ++i) {
                int nid = shell.nodeIds[i];
                if (std::find(region.nodeIds.begin(), region.nodeIds.end(), nid) != region.nodeIds.end()) {
                    hasMatchingNode = true;
                    break;
                }
            }
            if (!hasMatchingNode) keep = false;
        }

        // Node ID range filter
        if (keep && (region.nodeIdMin > 0 || region.nodeIdMax > 0)) {
            bool inRange = false;
            for (int i = 0; i < 4; ++i) {
                int nid = shell.nodeIds[i];
                if ((region.nodeIdMin == 0 || nid >= region.nodeIdMin) &&
                    (region.nodeIdMax == 0 || nid <= region.nodeIdMax)) {
                    inRange = true;
                    break;
                }
            }
            if (!inRange) keep = false;
        }

        // Element ID filter
        if (keep && !region.elementIds.empty()) {
            if (std::find(region.elementIds.begin(), region.elementIds.end(), shell.id) == region.elementIds.end()) {
                keep = false;
            }
        }

        // Element ID range filter
        if (keep && (region.elementIdMin > 0 || region.elementIdMax > 0)) {
            if ((region.elementIdMin > 0 && shell.id < region.elementIdMin) ||
                (region.elementIdMax > 0 && shell.id > region.elementIdMax)) {
                keep = false;
            }
        }

        if (keep) {
            filtered.push_back(shell);
        }
    }

    surface = filtered;

    if (filtered.size() != originalSize) {
        std::cout << "[INFO] Region filter: " << originalSize << " → "
                  << filtered.size() << " surface elements\n";
    }
}

std::map<int, double> ModelAssembler::computePerNodeThickness(
    const std::vector<ShellElement>& surface,
    const std::string& formula,
    double baseThickness) {

    std::map<int, double> perNodeThickness;

    if (formula.empty()) {
        // No formula - use base thickness for all nodes
        for (const auto& shell : surface) {
            for (int i = 0; i < 4; ++i) {
                int nid = shell.nodeIds[i];
                if (nid > 0) {
                    perNodeThickness[nid] = baseThickness;
                }
            }
        }
        return perNodeThickness;
    }

    // Evaluate formula for each unique node
    FormulaEvaluator evaluator;

    // Collect all unique node IDs
    std::set<int> uniqueNodes;
    for (const auto& shell : surface) {
        for (int i = 0; i < 4; ++i) {
            if (shell.nodeIds[i] > 0) {
                uniqueNodes.insert(shell.nodeIds[i]);
            }
        }
    }

    // Evaluate thickness formula for each node position
    for (int nid : uniqueNodes) {
        Vector3D pos = getNodePosition(nid);

        // Set variables for formula: x, y, z
        evaluator.setVariable("x", pos.x);
        evaluator.setVariable("y", pos.y);
        evaluator.setVariable("z", pos.z);

        try {
            double t = evaluator.evaluate(formula);
            if (t <= 0.0) {
                std::cout << "[WARNING] Node " << nid << " thickness formula gave "
                          << t << " ≤ 0, using base thickness " << baseThickness << "\n";
                t = baseThickness;
            }
            perNodeThickness[nid] = t;
        } catch (const std::exception& e) {
            std::cout << "[ERROR] Thickness formula evaluation failed for node " << nid
                      << ": " << e.what() << "\n";
            perNodeThickness[nid] = baseThickness;
        }
    }

    return perNodeThickness;
}

Vector3D ModelAssembler::parseOffsetDirection(const std::string& direction,
                                              const std::vector<ShellElement>& surface) {
    if (direction == "+normal" || direction == "normal") {
        return computeAverageNormal(surface);
    } else if (direction == "-normal") {
        return computeAverageNormal(surface) * -1.0;
    } else if (direction == "+x") {
        return Vector3D(1, 0, 0);
    } else if (direction == "-x") {
        return Vector3D(-1, 0, 0);
    } else if (direction == "+y") {
        return Vector3D(0, 1, 0);
    } else if (direction == "-y") {
        return Vector3D(0, -1, 0);
    } else if (direction == "+z") {
        return Vector3D(0, 0, 1);
    } else if (direction == "-z") {
        return Vector3D(0, 0, -1);
    }
    return Vector3D(0, 0, 1);
}

bool ModelAssembler::isTria3(const ShellElement& shell) {
    return (shell.nodeIds[2] == shell.nodeIds[3]) || (shell.nodeIds[3] == 0);
}

Vector3D ModelAssembler::computeElementCenter(const Element& elem) const {
    Vector3D sum(0, 0, 0);
    int count = 0;

    for (int i = 0; i < 8; ++i) {
        if (elem.nodeIds[i] > 0) {
            sum = sum + getNodePosition(elem.nodeIds[i]);
            count++;
        }
    }

    if (count == 0) {
        return Vector3D(0, 0, 0);
    }

    return sum * (1.0 / count);
}

// ========== PHASE 7: EXTRUDE TO SOLID ==========

void ModelAssembler::extrudeToSolid(const std::vector<ShellElement>& surface,
                                   const Vector3D& direction,
                                   double thickness, int numLayers,
                                   int newPid, int newSecid) {
    double layerThickness = thickness / numLayers;

    // Create nodes for each layer
    std::map<int, std::vector<int>> bottomToTopNodes;  // [layerIdx][origNodeId] -> newNodeId

    // Layer 0 = bottom (original surface nodes)
    for (const auto& shell : surface) {
        for (int i = 0; i < 4; ++i) {
            int origNid = shell.nodeIds[i];
            if (bottomToTopNodes[0].empty()) {
                bottomToTopNodes[0].resize(maxNodeId_ + 10000);
            }
            if (bottomToTopNodes[0][origNid] == 0) {
                bottomToTopNodes[0][origNid] = origNid;  // Use original nodes
            }
        }
    }

    // Create offset layers
    for (int layer = 1; layer <= numLayers; ++layer) {
        bottomToTopNodes[layer].resize(maxNodeId_ + 10000);

        for (const auto& shell : surface) {
            for (int i = 0; i < 4; ++i) {
                int origNid = shell.nodeIds[i];

                if (bottomToTopNodes[layer][origNid] == 0) {
                    // Create new node
                    int newNid = ++maxNodeId_;
                    Vector3D origPos = getNodePosition(origNid);
                    Vector3D newPos = origPos + direction * (layerThickness * layer);

                    AddedNode an;
                    an.id = newNid;
                    an.x = newPos.x;
                    an.y = newPos.y;
                    an.z = newPos.z;
                    addedNodes_.push_back(an);

                    bottomToTopNodes[layer][origNid] = newNid;
                }
            }
        }
    }

    // Determine if we need to flip winding based on offset direction
    // For negative offset (direction vector points "inward"), flip winding
    // Check dominant component: if largest absolute value component is negative, flip
    double absX = std::abs(direction.x);
    double absY = std::abs(direction.y);
    double absZ = std::abs(direction.z);
    double maxAbs = std::max({absX, absY, absZ});
    bool isNegativeDirection = false;
    if (maxAbs == absX && direction.x < 0) isNegativeDirection = true;
    if (maxAbs == absY && direction.y < 0) isNegativeDirection = true;
    if (maxAbs == absZ && direction.z < 0) isNegativeDirection = true;

    // Create solid elements
    for (const auto& shell : surface) {
        for (int layer = 0; layer < numLayers; ++layer) {
            AddedElement elem;
            elem.id = ++maxElementId_;
            elem.pid = newPid;
            elem.type = ElementType::HEX8;

            // For negative direction, swap layer indices so bottom is actually below top
            int bottomLayer = isNegativeDirection ? (layer + 1) : layer;
            int topLayer = isNegativeDirection ? layer : (layer + 1);

            // Bottom face
            for (int i = 0; i < 4; ++i) {
                int origNid = shell.nodeIds[i];
                elem.nodeIds[i] = bottomToTopNodes[bottomLayer][origNid];
            }

            // Top face
            for (int i = 0; i < 4; ++i) {
                int origNid = shell.nodeIds[i];
                elem.nodeIds[i+4] = bottomToTopNodes[topLayer][origNid];
            }

            // Handle TRIA3 (degenerate quad)
            if (isTria3(shell)) {
                elem.nodeIds[3] = elem.nodeIds[2];
                elem.nodeIds[7] = elem.nodeIds[6];
            }

            addedElements_.push_back(elem);
        }
    }

    std::cout << "[INFO] Created " << addedElements_.size()
              << " solid elements in " << numLayers << " layers\n";
}

// Overload for dual offset prestress (returns elements for stress calculation)
void ModelAssembler::extrudeToSolid(const std::vector<ShellElement>& surface,
                                   const Vector3D& direction,
                                   double thickness, int numLayers,
                                   int newPid, int newSecid,
                                   std::vector<AddedElement>& outElements) {
    double layerThickness = thickness / numLayers;

    // Create nodes for each layer
    std::map<int, std::vector<int>> bottomToTopNodes;

    // Layer 0 = bottom (original surface nodes)
    for (const auto& shell : surface) {
        for (int i = 0; i < 4; ++i) {
            int origNid = shell.nodeIds[i];
            if (bottomToTopNodes[0].empty()) {
                bottomToTopNodes[0].resize(maxNodeId_ + 10000);
            }
            if (bottomToTopNodes[0][origNid] == 0) {
                bottomToTopNodes[0][origNid] = origNid;
            }
        }
    }

    // Create offset layers
    for (int layer = 1; layer <= numLayers; ++layer) {
        bottomToTopNodes[layer].resize(maxNodeId_ + 10000);

        for (const auto& shell : surface) {
            for (int i = 0; i < 4; ++i) {
                int origNid = shell.nodeIds[i];

                if (bottomToTopNodes[layer][origNid] == 0) {
                    int newNid = ++maxNodeId_;
                    Vector3D origPos = getNodePosition(origNid);
                    Vector3D newPos = origPos + direction * (layerThickness * layer);

                    AddedNode an;
                    an.id = newNid;
                    an.x = newPos.x;
                    an.y = newPos.y;
                    an.z = newPos.z;
                    addedNodes_.push_back(an);

                    bottomToTopNodes[layer][origNid] = newNid;
                }
            }
        }
    }

    // Determine if we need to flip winding based on offset direction
    // For negative offset (direction vector points "inward"), flip winding
    // Check dominant component: if largest absolute value component is negative, flip
    double absX = std::abs(direction.x);
    double absY = std::abs(direction.y);
    double absZ = std::abs(direction.z);
    double maxAbs = std::max({absX, absY, absZ});
    bool isNegativeDirection = false;
    if (maxAbs == absX && direction.x < 0) isNegativeDirection = true;
    if (maxAbs == absY && direction.y < 0) isNegativeDirection = true;
    if (maxAbs == absZ && direction.z < 0) isNegativeDirection = true;

    // Create solid elements
    for (const auto& shell : surface) {
        bool flipWinding = !isNegativeDirection;  // TEST: Try opposite

        for (int layer = 0; layer < numLayers; ++layer) {
            AddedElement elem;
            elem.id = ++maxElementId_;
            elem.pid = newPid;
            elem.type = ElementType::HEX8;

            if (!flipWinding) {
                // Normal case: shell is bottom, extrude upward
                // Bottom face (nodes 0-3): current layer
                elem.nodeIds[0] = bottomToTopNodes[layer][shell.nodeIds[0]];
                elem.nodeIds[1] = bottomToTopNodes[layer][shell.nodeIds[1]];
                elem.nodeIds[2] = bottomToTopNodes[layer][shell.nodeIds[2]];
                elem.nodeIds[3] = bottomToTopNodes[layer][shell.nodeIds[3]];

                // Top face (nodes 4-7): next layer
                elem.nodeIds[4] = bottomToTopNodes[layer+1][shell.nodeIds[0]];
                elem.nodeIds[5] = bottomToTopNodes[layer+1][shell.nodeIds[1]];
                elem.nodeIds[6] = bottomToTopNodes[layer+1][shell.nodeIds[2]];
                elem.nodeIds[7] = bottomToTopNodes[layer+1][shell.nodeIds[3]];
            } else {
                // Flipped case: shell is top, extrude downward
                // Bottom face (nodes 0-3): next layer, reversed winding
                elem.nodeIds[0] = bottomToTopNodes[layer+1][shell.nodeIds[0]];
                elem.nodeIds[1] = bottomToTopNodes[layer+1][shell.nodeIds[3]];
                elem.nodeIds[2] = bottomToTopNodes[layer+1][shell.nodeIds[2]];
                elem.nodeIds[3] = bottomToTopNodes[layer+1][shell.nodeIds[1]];

                // Top face (nodes 4-7): current layer, reversed winding
                elem.nodeIds[4] = bottomToTopNodes[layer][shell.nodeIds[0]];
                elem.nodeIds[5] = bottomToTopNodes[layer][shell.nodeIds[3]];
                elem.nodeIds[6] = bottomToTopNodes[layer][shell.nodeIds[2]];
                elem.nodeIds[7] = bottomToTopNodes[layer][shell.nodeIds[1]];
            }

            // Handle TRIA3
            if (isTria3(shell)) {
                elem.nodeIds[3] = elem.nodeIds[2];
                elem.nodeIds[7] = elem.nodeIds[6];
            }

            outElements.push_back(elem);
        }
    }

    std::cout << "[INFO] Created " << outElements.size()
              << " solid elements in " << numLayers << " layers\n";
}

// Overload for local normals (per-node directions)
void ModelAssembler::extrudeToSolid(const std::vector<ShellElement>& surface,
                                   const std::map<int, Vector3D>& perNodeDirections,
                                   double thickness, int numLayers,
                                   int newPid, int newSecid) {
    double layerThickness = thickness / numLayers;

    // Create nodes for each layer with per-node directions
    std::map<int, std::vector<int>> bottomToTopNodes;  // [layerIdx][origNodeId] -> newNodeId

    // Layer 0 = bottom (original surface nodes)
    for (const auto& shell : surface) {
        for (int i = 0; i < 4; ++i) {
            int origNid = shell.nodeIds[i];
            if (bottomToTopNodes[0].empty()) {
                bottomToTopNodes[0].resize(maxNodeId_ + 10000);
            }
            if (bottomToTopNodes[0][origNid] == 0) {
                bottomToTopNodes[0][origNid] = origNid;  // Use original nodes
            }
        }
    }

    // Create offset layers with per-node directions
    for (int layer = 1; layer <= numLayers; ++layer) {
        bottomToTopNodes[layer].resize(maxNodeId_ + 10000);

        for (const auto& shell : surface) {
            for (int i = 0; i < 4; ++i) {
                int origNid = shell.nodeIds[i];

                if (bottomToTopNodes[layer][origNid] == 0) {
                    // Create new node using THIS node's local normal
                    int newNid = ++maxNodeId_;
                    Vector3D origPos = getNodePosition(origNid);

                    // Look up the per-node direction
                    Vector3D nodeDirection = Vector3D(0, 0, 1);  // Default
                    auto it = perNodeDirections.find(origNid);
                    if (it != perNodeDirections.end()) {
                        nodeDirection = it->second;
                    }

                    Vector3D newPos = origPos + nodeDirection * (layerThickness * layer);

                    AddedNode an;
                    an.id = newNid;
                    an.x = newPos.x;
                    an.y = newPos.y;
                    an.z = newPos.z;
                    addedNodes_.push_back(an);

                    bottomToTopNodes[layer][origNid] = newNid;
                }
            }
        }
    }

    // Create solid elements (same as standard version)
    for (const auto& shell : surface) {
        // Check average per-node direction against shell normal
        Vector3D shellNormal = computeElementNormal(shell);
        Vector3D avgDirection(0, 0, 0);
        int dirCount = 0;
        for (int i = 0; i < 4; ++i) {
            auto it = perNodeDirections.find(shell.nodeIds[i]);
            if (it != perNodeDirections.end()) {
                avgDirection = avgDirection + it->second;
                dirCount++;
            }
        }
        if (dirCount > 0) {
            avgDirection = avgDirection * (1.0 / dirCount);
        }
        double alignment = shellNormal.x * avgDirection.x +
                          shellNormal.y * avgDirection.y +
                          shellNormal.z * avgDirection.z;

        // If average direction is opposite to normal (alignment < 0), flip winding
        bool flipWinding = (alignment < 0.0);

        for (int layer = 0; layer < numLayers; ++layer) {
            AddedElement elem;
            elem.id = ++maxElementId_;
            elem.pid = newPid;
            elem.type = ElementType::HEX8;

            if (!flipWinding) {
                // Normal case
                for (int i = 0; i < 4; ++i) {
                    int origNid = shell.nodeIds[i];
                    elem.nodeIds[i] = bottomToTopNodes[layer][origNid];
                }

                for (int i = 0; i < 4; ++i) {
                    int origNid = shell.nodeIds[i];
                    elem.nodeIds[i+4] = bottomToTopNodes[layer+1][origNid];
                }
            } else {
                // Flipped case
                elem.nodeIds[0] = bottomToTopNodes[layer+1][shell.nodeIds[0]];
                elem.nodeIds[1] = bottomToTopNodes[layer+1][shell.nodeIds[3]];
                elem.nodeIds[2] = bottomToTopNodes[layer+1][shell.nodeIds[2]];
                elem.nodeIds[3] = bottomToTopNodes[layer+1][shell.nodeIds[1]];

                elem.nodeIds[4] = bottomToTopNodes[layer][shell.nodeIds[0]];
                elem.nodeIds[5] = bottomToTopNodes[layer][shell.nodeIds[3]];
                elem.nodeIds[6] = bottomToTopNodes[layer][shell.nodeIds[2]];
                elem.nodeIds[7] = bottomToTopNodes[layer][shell.nodeIds[1]];
            }

            // Handle TRIA3
            if (isTria3(shell)) {
                elem.nodeIds[3] = elem.nodeIds[2];
                elem.nodeIds[7] = elem.nodeIds[6];
            }

            addedElements_.push_back(elem);
        }
    }

    std::cout << "[INFO] Created " << addedElements_.size()
              << " solid elements in " << numLayers << " layers (local normals)\n";
}

// Overload for variable thickness (per-node thickness values)
void ModelAssembler::extrudeToSolid(const std::vector<ShellElement>& surface,
                                   const Vector3D& direction,
                                   const std::map<int, double>& perNodeThickness,
                                   int numLayers,
                                   int newPid, int newSecid) {

    // Create nodes for each layer with per-node variable thickness
    std::map<int, std::vector<int>> bottomToTopNodes;  // [layerIdx][origNodeId] -> newNodeId

    // Layer 0 = bottom (original surface nodes)
    for (const auto& shell : surface) {
        for (int i = 0; i < 4; ++i) {
            int origNid = shell.nodeIds[i];
            if (bottomToTopNodes[0].empty()) {
                bottomToTopNodes[0].resize(maxNodeId_ + 10000);
            }
            if (bottomToTopNodes[0][origNid] == 0) {
                bottomToTopNodes[0][origNid] = origNid;
            }
        }
    }

    // Create offset layers with per-node thickness
    for (int layer = 1; layer <= numLayers; ++layer) {
        bottomToTopNodes[layer].resize(maxNodeId_ + 10000);

        for (const auto& shell : surface) {
            for (int i = 0; i < 4; ++i) {
                int origNid = shell.nodeIds[i];

                if (bottomToTopNodes[layer][origNid] == 0) {
                    int newNid = ++maxNodeId_;
                    Vector3D origPos = getNodePosition(origNid);

                    // Get THIS node's thickness
                    double nodeThickness = 1.0;  // Default
                    auto it = perNodeThickness.find(origNid);
                    if (it != perNodeThickness.end()) {
                        nodeThickness = it->second;
                    }

                    double layerThickness = nodeThickness / numLayers;
                    Vector3D newPos = origPos + direction * (layerThickness * layer);

                    AddedNode an;
                    an.id = newNid;
                    an.x = newPos.x;
                    an.y = newPos.y;
                    an.z = newPos.z;
                    addedNodes_.push_back(an);

                    bottomToTopNodes[layer][origNid] = newNid;
                }
            }
        }
    }

    // Create solid elements (same as standard version)
    for (const auto& shell : surface) {
        // Check if offset direction is aligned with shell normal
        Vector3D shellNormal = computeElementNormal(shell);
        double alignment = shellNormal.x * direction.x +
                          shellNormal.y * direction.y +
                          shellNormal.z * direction.z;

        // If direction is opposite to normal (alignment < 0), flip winding
        bool flipWinding = (alignment < 0.0);

        for (int layer = 0; layer < numLayers; ++layer) {
            AddedElement elem;
            elem.id = ++maxElementId_;
            elem.pid = newPid;
            elem.type = ElementType::HEX8;

            if (!flipWinding) {
                for (int i = 0; i < 4; ++i) {
                    int origNid = shell.nodeIds[i];
                    elem.nodeIds[i] = bottomToTopNodes[layer][origNid];
                }

                for (int i = 0; i < 4; ++i) {
                    int origNid = shell.nodeIds[i];
                    elem.nodeIds[i+4] = bottomToTopNodes[layer+1][origNid];
                }
            } else {
                elem.nodeIds[0] = bottomToTopNodes[layer+1][shell.nodeIds[0]];
                elem.nodeIds[1] = bottomToTopNodes[layer+1][shell.nodeIds[3]];
                elem.nodeIds[2] = bottomToTopNodes[layer+1][shell.nodeIds[2]];
                elem.nodeIds[3] = bottomToTopNodes[layer+1][shell.nodeIds[1]];

                elem.nodeIds[4] = bottomToTopNodes[layer][shell.nodeIds[0]];
                elem.nodeIds[5] = bottomToTopNodes[layer][shell.nodeIds[3]];
                elem.nodeIds[6] = bottomToTopNodes[layer][shell.nodeIds[2]];
                elem.nodeIds[7] = bottomToTopNodes[layer][shell.nodeIds[1]];
            }

            if (isTria3(shell)) {
                elem.nodeIds[3] = elem.nodeIds[2];
                elem.nodeIds[7] = elem.nodeIds[6];
            }

            addedElements_.push_back(elem);
        }
    }

    std::cout << "[INFO] Created " << addedElements_.size()
              << " solid elements in " << numLayers << " layers (variable thickness)\n";
}

// Overload for BOTH local normals AND variable thickness
void ModelAssembler::extrudeToSolid(const std::vector<ShellElement>& surface,
                                   const std::map<int, Vector3D>& perNodeDirections,
                                   const std::map<int, double>& perNodeThickness,
                                   int numLayers,
                                   int newPid, int newSecid) {

    // Create nodes for each layer with BOTH per-node directions AND per-node thickness
    std::map<int, std::vector<int>> bottomToTopNodes;  // [layerIdx][origNodeId] -> newNodeId

    // Layer 0 = bottom (original surface nodes)
    for (const auto& shell : surface) {
        for (int i = 0; i < 4; ++i) {
            int origNid = shell.nodeIds[i];
            if (bottomToTopNodes[0].empty()) {
                bottomToTopNodes[0].resize(maxNodeId_ + 10000);
            }
            if (bottomToTopNodes[0][origNid] == 0) {
                bottomToTopNodes[0][origNid] = origNid;  // Use original nodes
            }
        }
    }

    // Create offset layers with per-node directions AND per-node thickness
    for (int layer = 1; layer <= numLayers; ++layer) {
        bottomToTopNodes[layer].resize(maxNodeId_ + 10000);

        for (const auto& shell : surface) {
            for (int i = 0; i < 4; ++i) {
                int origNid = shell.nodeIds[i];

                if (bottomToTopNodes[layer][origNid] == 0) {
                    int newNid = ++maxNodeId_;
                    Vector3D origPos = getNodePosition(origNid);

                    // Get THIS node's direction
                    Vector3D nodeDirection = Vector3D(0, 0, 1);  // Default
                    auto itDir = perNodeDirections.find(origNid);
                    if (itDir != perNodeDirections.end()) {
                        nodeDirection = itDir->second;
                    }

                    // Get THIS node's thickness
                    double nodeThickness = 1.0;  // Default
                    auto itThick = perNodeThickness.find(origNid);
                    if (itThick != perNodeThickness.end()) {
                        nodeThickness = itThick->second;
                    }

                    double layerThickness = nodeThickness / numLayers;
                    Vector3D newPos = origPos + nodeDirection * (layerThickness * layer);

                    AddedNode an;
                    an.id = newNid;
                    an.x = newPos.x;
                    an.y = newPos.y;
                    an.z = newPos.z;
                    addedNodes_.push_back(an);

                    bottomToTopNodes[layer][origNid] = newNid;
                }
            }
        }
    }

    // Create solid elements (same as standard version)
    for (const auto& shell : surface) {
        // Check average per-node direction against shell normal
        Vector3D shellNormal = computeElementNormal(shell);
        Vector3D avgDirection(0, 0, 0);
        int dirCount = 0;
        for (int i = 0; i < 4; ++i) {
            auto it = perNodeDirections.find(shell.nodeIds[i]);
            if (it != perNodeDirections.end()) {
                avgDirection = avgDirection + it->second;
                dirCount++;
            }
        }
        if (dirCount > 0) {
            avgDirection = avgDirection * (1.0 / dirCount);
        }
        double alignment = shellNormal.x * avgDirection.x +
                          shellNormal.y * avgDirection.y +
                          shellNormal.z * avgDirection.z;

        // If average direction is opposite to normal (alignment < 0), flip winding
        bool flipWinding = (alignment < 0.0);

        for (int layer = 0; layer < numLayers; ++layer) {
            AddedElement elem;
            elem.id = ++maxElementId_;
            elem.pid = newPid;
            elem.type = ElementType::HEX8;

            if (!flipWinding) {
                // Normal case
                for (int i = 0; i < 4; ++i) {
                    int origNid = shell.nodeIds[i];
                    elem.nodeIds[i] = bottomToTopNodes[layer][origNid];
                }

                for (int i = 0; i < 4; ++i) {
                    int origNid = shell.nodeIds[i];
                    elem.nodeIds[i+4] = bottomToTopNodes[layer+1][origNid];
                }
            } else {
                // Flipped case
                elem.nodeIds[0] = bottomToTopNodes[layer+1][shell.nodeIds[0]];
                elem.nodeIds[1] = bottomToTopNodes[layer+1][shell.nodeIds[3]];
                elem.nodeIds[2] = bottomToTopNodes[layer+1][shell.nodeIds[2]];
                elem.nodeIds[3] = bottomToTopNodes[layer+1][shell.nodeIds[1]];

                elem.nodeIds[4] = bottomToTopNodes[layer][shell.nodeIds[0]];
                elem.nodeIds[5] = bottomToTopNodes[layer][shell.nodeIds[3]];
                elem.nodeIds[6] = bottomToTopNodes[layer][shell.nodeIds[2]];
                elem.nodeIds[7] = bottomToTopNodes[layer][shell.nodeIds[1]];
            }

            // Handle TRIA3
            if (isTria3(shell)) {
                elem.nodeIds[3] = elem.nodeIds[2];
                elem.nodeIds[7] = elem.nodeIds[6];
            }

            addedElements_.push_back(elem);
        }
    }

    std::cout << "[INFO] Created " << addedElements_.size()
              << " solid elements in " << numLayers << " layers (local normals + variable thickness)\n";
}

// ========== PHASE 6: HELPER METHODS ==========

std::string ModelAssembler::formatPartBlock(int pid, int secid, int mid, const std::string& title) {
    std::ostringstream oss;
    oss << "*PART\n";
    oss << title << "\n";
    oss << std::setw(10) << pid
        << std::setw(10) << secid
        << std::setw(10) << mid << "\n";
    return oss.str();
}

std::string ModelAssembler::formatCzmSectionBlock(int secid) {
    std::ostringstream oss;
    oss << "*SECTION_SOLID\n";
    oss << "$#   secid    elform       aet\n";
    oss << std::setw(10) << secid
        << std::setw(10) << 20  // ELFORM=20 (zero-thickness cohesive)
        << "\n";
    oss << "$ Zero-thickness cohesive - duplicate nodes at same position\n";
    return oss.str();
}

void ModelAssembler::insertMaterialCard(const std::string& materialCard, int actualMid) {
    std::string processed = materialCard;

    std::stringstream ss;
    ss << std::setw(10) << actualMid;
    std::string midStr = ss.str();

    size_t pos = processed.find("@MID@");
    while (pos != std::string::npos) {
        processed.replace(pos, 5, midStr);
        pos = processed.find("@MID@", pos + midStr.length());
    }

    addedKeywordBlocks_.push_back(processed);
    std::cout << "[INFO] Inserted material card with MID=" << actualMid << "\n";
}

void ModelAssembler::createPartKeyword(int pid, int secid, int mid, const std::string& title) {
    std::ostringstream oss;
    oss << "*PART\n";
    oss << title << "\n";
    oss << std::setw(10) << pid
        << std::setw(10) << secid
        << std::setw(10) << mid << "\n";
    addedKeywordBlocks_.push_back(oss.str());
}

void ModelAssembler::createSectionSolid(int secid) {
    std::ostringstream oss;
    oss << "*SECTION_SOLID\n";
    oss << "$#   secid    elform       aet\n";
    oss << std::setw(10) << secid
        << std::setw(10) << 1  // ELFORM=1 (constant stress solid)
        << "\n";
    addedKeywordBlocks_.push_back(oss.str());
}

void ModelAssembler::createSectionTShell(int secid, double thickness, int elform) {
    std::ostringstream oss;
    oss << "*SECTION_TSHELL\n";
    oss << "$#   secid    elform      shrf       nip     propt   qr/irid     icomp     setyp\n";
    oss << std::setw(10) << secid
        << std::setw(10) << elform  // 16=TSHELL4, 17=TSHELL3
        << std::setw(10) << 0.0
        << std::setw(10) << 3
        << "\n";
    oss << "$#      t1        t2        t3        t4      nloc     marea      idof    edgset\n";
    oss << std::scientific << std::setprecision(3);
    oss << std::setw(10) << thickness
        << std::setw(10) << thickness
        << std::setw(10) << thickness
        << std::setw(10) << thickness
        << "\n";
    addedKeywordBlocks_.push_back(oss.str());
}

void ModelAssembler::createSectionShell(int secid, double thickness) {
    std::ostringstream oss;
    oss << "*SECTION_SHELL\n";
    oss << "$#   secid    elform      shrf       nip     propt   qr/irid     icomp     setyp\n";
    oss << std::setw(10) << secid
        << std::setw(10) << 2  // ELFORM=2 (fully integrated QUAD)
        << std::setw(10) << 0.0
        << std::setw(10) << 3
        << "\n";
    oss << "$#      t1        t2        t3        t4      nloc     marea      idof    edgset\n";
    oss << std::scientific << std::setprecision(3);
    oss << std::setw(10) << thickness
        << std::setw(10) << thickness
        << std::setw(10) << thickness
        << std::setw(10) << thickness
        << "\n";
    addedKeywordBlocks_.push_back(oss.str());
}

Vector3D ModelAssembler::computeShellNormal(const ShellElement& shell) {
    // Same as computeElementNormal
    return computeElementNormal(shell);
}

// ========== PHASE 8: TSHELL EXTRUDE ==========

void ModelAssembler::extrudeToTShell(const std::vector<ShellElement>& surface,
                                    const Vector3D& direction,
                                    double thickness, int numLayers,
                                    int newPid, int newSecid) {
    double layerThickness = thickness / numLayers;

    std::cout << "[INFO] Extruding to TSHELL: " << numLayers
              << " layers, thickness=" << layerThickness << " mm each\n";

    // Create offset node layers
    std::map<int, std::vector<int>> nodeLayerMap;

    for (const auto& shell : surface) {
        for (int nid : shell.nodeIds) {
            if (nid <= 0) continue;
            if (nodeLayerMap.count(nid)) continue;

            Vector3D basePos = getNodePosition(nid);
            std::vector<int> layerNodes;

            for (int layer = 0; layer <= numLayers; ++layer) {
                int newNid = ++maxNodeId_;
                Vector3D offsetPos = basePos + direction * (layer * layerThickness);

                AddedNode an;
                an.id = newNid;
                an.x = offsetPos.x;
                an.y = offsetPos.y;
                an.z = offsetPos.z;
                addedNodes_.push_back(an);
                layerNodes.push_back(newNid);
            }

            nodeLayerMap[nid] = layerNodes;
        }
    }

    // Create TSHELL elements
    for (const auto& shell : surface) {
        bool isTria = isTria3(shell);

        for (int layer = 0; layer < numLayers; ++layer) {
            AddedShellElement tshell;
            tshell.id = ++maxShellElementId_;
            tshell.pid = newPid;
            tshell.elform = isTria ? 17 : 16;  // TSHELL3 : TSHELL4

            if (isTria) {
                // TSHELL3: 6 nodes (3 bottom + 3 top)
                tshell.nodeIds[0] = nodeLayerMap[shell.nodeIds[0]][layer];
                tshell.nodeIds[1] = nodeLayerMap[shell.nodeIds[1]][layer];
                tshell.nodeIds[2] = nodeLayerMap[shell.nodeIds[2]][layer];
                tshell.nodeIds[3] = nodeLayerMap[shell.nodeIds[0]][layer+1];
                tshell.nodeIds[4] = nodeLayerMap[shell.nodeIds[1]][layer+1];
                tshell.nodeIds[5] = nodeLayerMap[shell.nodeIds[2]][layer+1];
                tshell.nodeIds[6] = 0;
                tshell.nodeIds[7] = 0;
            } else {
                // TSHELL4: 8 nodes (4 bottom + 4 top)
                tshell.nodeIds[0] = nodeLayerMap[shell.nodeIds[0]][layer];
                tshell.nodeIds[1] = nodeLayerMap[shell.nodeIds[1]][layer];
                tshell.nodeIds[2] = nodeLayerMap[shell.nodeIds[2]][layer];
                tshell.nodeIds[3] = nodeLayerMap[shell.nodeIds[3]][layer];
                tshell.nodeIds[4] = nodeLayerMap[shell.nodeIds[0]][layer+1];
                tshell.nodeIds[5] = nodeLayerMap[shell.nodeIds[1]][layer+1];
                tshell.nodeIds[6] = nodeLayerMap[shell.nodeIds[2]][layer+1];
                tshell.nodeIds[7] = nodeLayerMap[shell.nodeIds[3]][layer+1];
            }

            addedShellElements_.push_back(tshell);
        }
    }

    std::cout << "[INFO] Created " << addedShellElements_.size()
              << " TSHELL elements\n";
}

// ========== PHASE 9: SHELL OFFSET ==========

void ModelAssembler::createOffsetShell(const std::vector<ShellElement>& surface,
                                      const Vector3D& direction,
                                      double offset,
                                      int newPid, int newSecid,
                                      double shellThickness) {
    std::cout << "[INFO] Creating offset shell at distance=" << offset
              << " mm, thickness=" << shellThickness << " mm\n";

    // Create new nodes at offset position
    std::map<int, int> oldToNewNode;

    for (const auto& shell : surface) {
        for (int nid : shell.nodeIds) {
            if (nid <= 0) continue;
            if (oldToNewNode.count(nid)) continue;

            Vector3D basePos = getNodePosition(nid);
            Vector3D offsetPos = basePos + direction * offset;

            int newNid = ++maxNodeId_;
            AddedNode an;
            an.id = newNid;
            an.x = offsetPos.x;
            an.y = offsetPos.y;
            an.z = offsetPos.z;
            addedNodes_.push_back(an);
            oldToNewNode[nid] = newNid;
        }
    }

    // Create shell elements
    for (const auto& shell : surface) {
        AddedShellElement newShell;
        newShell.id = ++maxShellElementId_;
        newShell.pid = newPid;
        newShell.elform = 2;  // Standard QUAD4/TRIA3

        for (size_t i = 0; i < 4; ++i) {
            if (shell.nodeIds[i] > 0) {
                newShell.nodeIds[i] = oldToNewNode[shell.nodeIds[i]];
            } else {
                newShell.nodeIds[i] = 0;
            }
        }
        // Initialize remaining nodes for TSHELL compatibility
        for (size_t i = 4; i < 8; ++i) {
            newShell.nodeIds[i] = 0;
        }

        addedShellElements_.push_back(newShell);
    }

    std::cout << "[INFO] Created " << oldToNewNode.size() << " nodes, "
              << addedShellElements_.size() << " shell elements\n";
}

// ========== PHASE 11: CONNECTION MODES ==========

void ModelAssembler::applyConnectionTied(
    const std::vector<ShellElement>& sourceSurface,
    const std::vector<AddedElement>& offsetElements) {
    // Already implemented - tied mode is default behavior
    // Source surface nodes are directly used as offset layer bottom nodes
    std::cout << "[INFO] Connection mode: tied (node sharing)\n";
}

void ModelAssembler::applyConnectionCZM(
    const std::vector<ShellElement>& sourceSurface,
    std::vector<AddedElement>& offsetElements,
    const OffsetOperation& op) {

    int czmPid = op.czmPartId > 0 ? op.czmPartId : ++maxPartId_;
    int czmSecid = czmPid;
    int czmMid = op.czmMid > 0 ? op.czmMid : ++maxMaterialId_;

    std::cout << "[INFO] Connection mode: czm (cohesive elements, PID=" << czmPid << ")\n";

    // 1. Duplicate nodes for source surface
    std::map<int, int> origNodeToDupNode;
    for (const auto& shell : sourceSurface) {
        for (int i = 0; i < 4; ++i) {
            int nid = shell.nodeIds[i];
            if (nid <= 0) continue;
            if (origNodeToDupNode.find(nid) == origNodeToDupNode.end()) {
                int newNid = ++maxNodeId_;
                Vector3D pos = getNodePosition(nid);

                AddedNode an;
                an.id = newNid;
                an.x = pos.x;
                an.y = pos.y;
                an.z = pos.z;
                addedNodes_.push_back(an);

                origNodeToDupNode[nid] = newNid;
            }
        }
    }

    // 2. Replace offset layer bottom nodes with duplicates
    for (auto& elem : offsetElements) {
        for (int i = 0; i < 4; ++i) {
            if (origNodeToDupNode.find(elem.nodeIds[i]) != origNodeToDupNode.end()) {
                elem.nodeIds[i] = origNodeToDupNode[elem.nodeIds[i]];
            }
        }
    }

    // 3. Create cohesive elements
    for (const auto& shell : sourceSurface) {
        AddedElement cohElem;
        cohElem.id = ++maxElementId_;
        cohElem.pid = czmPid;
        cohElem.type = ElementType::HEX8;

        // Bottom face: original nodes
        cohElem.nodeIds[0] = shell.nodeIds[0];
        cohElem.nodeIds[1] = shell.nodeIds[1];
        cohElem.nodeIds[2] = shell.nodeIds[2];
        cohElem.nodeIds[3] = shell.nodeIds[3];

        // Top face: duplicate nodes
        cohElem.nodeIds[4] = origNodeToDupNode[shell.nodeIds[0]];
        cohElem.nodeIds[5] = origNodeToDupNode[shell.nodeIds[1]];
        cohElem.nodeIds[6] = origNodeToDupNode[shell.nodeIds[2]];
        cohElem.nodeIds[7] = origNodeToDupNode[shell.nodeIds[3]];

        addedElements_.push_back(cohElem);
    }

    // 4. CZM keywords
    std::string partBlock = formatPartBlock(czmPid, czmSecid, czmMid, "CZM_Layer");
    std::string sectionBlock = formatCzmSectionBlock(czmSecid);
    std::string materialBlock = op.czmMaterialCard;

    // Replace @MID@ placeholder
    size_t pos = 0;
    while ((pos = materialBlock.find("@MID@", pos)) != std::string::npos) {
        materialBlock.replace(pos, 5, std::to_string(czmMid));
        pos += std::to_string(czmMid).length();
    }

    addedKeywordBlocks_.push_back(partBlock);
    addedKeywordBlocks_.push_back(sectionBlock);
    addedKeywordBlocks_.push_back(materialBlock);

    std::cout << "[INFO] Created " << sourceSurface.size() << " CZM elements\n";
}

void ModelAssembler::applyConnectionContact(
    const std::vector<ShellElement>& sourceSurface,
    std::vector<AddedElement>& offsetElements,
    int sourcePid, int newPid) {

    std::cout << "[INFO] Connection mode: contact (separate nodes)\n";

    // Duplicate nodes for offset layer bottom
    std::map<int, int> origNodeToNewNode;

    for (auto& elem : offsetElements) {
        for (int i = 0; i < 4; ++i) {
            int origNid = elem.nodeIds[i];

            if (origNodeToNewNode.find(origNid) == origNodeToNewNode.end()) {
                int newNid = ++maxNodeId_;
                Vector3D pos = getNodePosition(origNid);

                AddedNode an;
                an.id = newNid;
                an.x = pos.x;
                an.y = pos.y;
                an.z = pos.z;
                addedNodes_.push_back(an);

                origNodeToNewNode[origNid] = newNid;
            }

            elem.nodeIds[i] = origNodeToNewNode[origNid];
        }
    }

    // Add contact hint
    std::ostringstream contactHint;
    contactHint << "$\n"
                << "$ ==================== CONTACT DEFINITION REQUIRED ====================\n"
                << "$ The offset layer uses connection_mode: contact\n"
                << "$ Add contact definition manually, for example:\n"
                << "$\n"
                << "$ *CONTACT_AUTOMATIC_SURFACE_TO_SURFACE\n"
                << "$ $#     cid                                                         title\n"
                << "$       999                                          Offset_Contact_Auto\n"
                << "$ $#    ssid      msid     sstyp     mstyp    sboxid    mboxid       spr       mpr\n"
                << "$  " << std::setw(8) << sourcePid
                << std::setw(10) << newPid
                << "         2         2         0         0         0         0\n"
                << "$ $#      fs        fd        dc        vc       vdc    penchk        bt        dt\n"
                << "$      0.00      0.00      0.00      0.00      0.00         0      0.00  1.00E+20\n"
                << "$ ======================================================================\n"
                << "$\n";

    addedKeywordBlocks_.push_back(contactHint.str());

    std::cout << "[INFO] Created " << origNodeToNewNode.size() << " duplicate nodes\n";
}

// ========== MULTI-MATERIAL OFFSET ==========

bool ModelAssembler::applyMultiMaterialOffset(const OffsetOperation& op, double E, double nu) {
    std::cout << "[INFO] Multi-material offset with " << op.materialCards.size() << " layers\n";

    // Multi-material offset: each layer gets a different material
    // Strategy: Create each layer sequentially with numLayers=1
    int numLayers = static_cast<int>(op.materialCards.size());
    double layerThickness = op.thickness / numLayers;

    int previousLayerPid = op.sourcePid;  // Track previous layer's PID

    for (int layerIdx = 0; layerIdx < numLayers; ++layerIdx) {
        std::cout << "[INFO] Creating layer " << (layerIdx + 1) << "/" << numLayers << "\n";

        // Create modified operation for this layer
        OffsetOperation layerOp = op;
        layerOp.thickness = layerThickness;
        layerOp.numLayers = 1;
        layerOp.materialCard = op.materialCards[layerIdx];
        layerOp.materialCards.clear();  // Prevent recursion

        // For first layer, use original source
        // For subsequent layers, use previous layer's top surface as source
        layerOp.sourcePid = previousLayerPid;

        // Auto-assign IDs for this layer
        if (layerIdx == 0) {
            // First layer uses specified IDs or auto
            layerOp.newPid = (op.newPid > 0) ? op.newPid : (++maxPartId_);
            layerOp.newSecid = (op.newSecid > 0) ? op.newSecid : (++maxSectionId_);
            layerOp.newMid = (op.newMid > 0) ? op.newMid : (++maxMaterialId_);
        } else {
            // Subsequent layers always auto-increment
            layerOp.newPid = ++maxPartId_;
            layerOp.newSecid = ++maxSectionId_;
            layerOp.newMid = ++maxMaterialId_;
        }

        // Apply single-layer offset
        bool success = applyOffset(layerOp, E, nu);
        if (!success) {
            return false;
        }

        // Update previous layer PID for next iteration
        previousLayerPid = layerOp.newPid;
    }

    std::cout << "[INFO] Multi-material offset completed: " << numLayers << " layers\n";
    return true;
}

// ========== PHASE 12: DUAL OFFSET PRESTRESS ==========

bool ModelAssembler::applyDualOffsetPrestress(const OffsetOperation& op, double E, double nu) {
    std::cout << "[INFO] Applying dual offset prestress mode\n";
    std::cout << "[INFO] Inner offset: " << op.innerOffset
              << " mm, Outer offset: " << op.outerOffset << " mm\n";

    // 1. Validation
    bool foundPid = false;
    for (const auto& pair : baseMesh_.getElements()) {
        if (pair.second.partId == op.sourcePid) {
            foundPid = true;
            break;
        }
    }
    if (!foundPid) {
        errorMessage_ = "Source PID " + std::to_string(op.sourcePid) + " not found";
        return false;
    }

    // 2. Auto-assign IDs
    int actualPid = (op.newPid > 0) ? op.newPid : (++maxPartId_);
    int actualSecid = (op.newSecid > 0) ? op.newSecid : (++maxSectionId_);
    int actualMid = (op.newMid > 0) ? op.newMid : (++maxMaterialId_);

    // 3. Extract source surface
    std::vector<ShellElement> sourceSurface;
    extractSourceSurface(op.sourcePid, sourceSurface);

    if (sourceSurface.empty()) {
        errorMessage_ = "No surface elements found in source PID "
                       + std::to_string(op.sourcePid);
        return false;
    }

    Vector3D outwardDir = computeAverageNormal(sourceSurface);

    // 4. Connection mode - create duplicate nodes at inner offset position
    std::map<int, int> origToBottomNode;
    std::map<int, Vector3D> deformedPositions;

    if (op.connectionMode == "czm" || op.connectionMode == "contact") {
        // Duplicate nodes at inner offset (deformed state)
        for (const auto& shell : sourceSurface) {
            for (int i = 0; i < 4; ++i) {
                int origNid = shell.nodeIds[i];
                if (origNid <= 0) continue;
                if (origToBottomNode.find(origNid) == origToBottomNode.end()) {
                    int newNid = ++maxNodeId_;
                    Vector3D origPos = getNodePosition(origNid);
                    Vector3D normal = computeShellNormal(shell);

                    // Deformed position (inner offset)
                    Vector3D innerPos = origPos + normal * op.innerOffset;

                    AddedNode an;
                    an.id = newNid;
                    an.x = innerPos.x;
                    an.y = innerPos.y;
                    an.z = innerPos.z;
                    addedNodes_.push_back(an);

                    origToBottomNode[origNid] = newNid;
                    deformedPositions[newNid] = innerPos;
                }
            }
        }
    } else {
        // Tied: Use original nodes directly
        for (const auto& shell : sourceSurface) {
            for (int i = 0; i < 4; ++i) {
                int origNid = shell.nodeIds[i];
                if (origNid <= 0) continue;
                if (origToBottomNode.find(origNid) == origToBottomNode.end()) {
                    Vector3D origPos = getNodePosition(origNid);
                    Vector3D normal = computeShellNormal(shell);

                    origToBottomNode[origNid] = origNid;  // Identity
                    deformedPositions[origNid] = origPos + normal * op.innerOffset;
                }
            }
        }
    }

    // 5. Update surface to use bottom nodes
    std::vector<ShellElement> modifiedSurface = sourceSurface;
    for (auto& shell : modifiedSurface) {
        for (int i = 0; i < 4; ++i) {
            if (shell.nodeIds[i] > 0) {
                shell.nodeIds[i] = origToBottomNode[shell.nodeIds[i]];
            }
        }
    }

    // 6. Extrude to reference (outer) configuration
    std::vector<AddedElement> refElements;
    double thickness = op.outerOffset - op.innerOffset;
    extrudeToSolid(modifiedSurface, outwardDir, thickness,
                   op.numLayers, actualPid, actualSecid, refElements);

    // 7. Calculate prestress
    MaterialModel mat = MaterialModel::isotropicElastic(E, nu);
    calculateDualOffsetPrestress(refElements, deformedPositions, mat);

    // 8. Add elements to accumulator
    for (auto& elem : refElements) {
        addedElements_.push_back(elem);
    }

    // 9. Create CZM/Contact
    if (op.connectionMode == "czm") {
        createCzmElementsForDualOffset(sourceSurface, origToBottomNode, op);
    } else if (op.connectionMode == "contact") {
        addContactHint(op.sourcePid, actualPid);
    }

    // 10. Create keywords
    createPartKeyword(actualPid, actualSecid, actualMid, op.partTitle);
    createSectionSolid(actualSecid);
    if (!op.materialCard.empty()) {
        insertMaterialCard(op.materialCard, actualMid);
    }

    std::cout << "[INFO] Dual offset prestress completed\n";
    return true;
}

void ModelAssembler::calculateDualOffsetPrestress(
    const std::vector<AddedElement>& refElements,
    const std::map<int, Vector3D>& deformedPositions,
    const MaterialModel& mat) {

    std::cout << "[INFO] Calculating dual offset prestress...\n";

    for (const auto& elem : refElements) {
        // Reference (outer) positions
        Vector3D refNodes[8];
        for (int i = 0; i < 8; ++i) {
            refNodes[i] = getNodePosition(elem.nodeIds[i]);
        }

        // Deformed (inner) positions
        Vector3D defNodes[8];
        for (int i = 0; i < 4; ++i) {
            // Bottom face: deformed positions
            auto it = deformedPositions.find(elem.nodeIds[i]);
            if (it != deformedPositions.end()) {
                defNodes[i] = it->second;
            } else {
                defNodes[i] = refNodes[i];  // Fallback
            }
        }
        for (int i = 4; i < 8; ++i) {
            // Top face: proportional deformation
            int bottomIdx = i - 4;
            Vector3D displacement = defNodes[bottomIdx] - refNodes[bottomIdx];
            defNodes[i] = refNodes[i] + displacement;
        }

        // Full 3D strain calculation
        // Reference configuration vectors
        Vector3D dr_ref = (refNodes[1] - refNodes[0] + refNodes[2] - refNodes[3] +
                          refNodes[5] - refNodes[4] + refNodes[6] - refNodes[7]) * 0.125;
        Vector3D ds_ref = (refNodes[3] - refNodes[0] + refNodes[2] - refNodes[1] +
                          refNodes[7] - refNodes[4] + refNodes[6] - refNodes[5]) * 0.125;
        Vector3D dt_ref = (refNodes[4] - refNodes[0] + refNodes[5] - refNodes[1] +
                          refNodes[6] - refNodes[2] + refNodes[7] - refNodes[3]) * 0.125;

        // Deformed configuration vectors
        Vector3D dr_def = (defNodes[1] - defNodes[0] + defNodes[2] - defNodes[3] +
                          defNodes[5] - defNodes[4] + defNodes[6] - defNodes[7]) * 0.125;
        Vector3D ds_def = (defNodes[3] - defNodes[0] + defNodes[2] - defNodes[1] +
                          defNodes[7] - defNodes[4] + defNodes[6] - defNodes[5]) * 0.125;
        Vector3D dt_def = (defNodes[4] - defNodes[0] + defNodes[5] - defNodes[1] +
                          defNodes[6] - defNodes[2] + defNodes[7] - defNodes[3]) * 0.125;

        // Metric tensor (small strain approximation)
        double eps_xx = 0.5 * (dr_def.dot(dr_def) / dr_ref.dot(dr_ref) - 1.0);
        double eps_yy = 0.5 * (ds_def.dot(ds_def) / ds_ref.dot(ds_ref) - 1.0);
        double eps_zz = 0.5 * (dt_def.dot(dt_def) / dt_ref.dot(dt_ref) - 1.0);

        double dr_mag = dr_ref.magnitude();
        double ds_mag = ds_ref.magnitude();
        double dt_mag = dt_ref.magnitude();

        double eps_xy = 0.5 * (dr_def.dot(ds_def) / (dr_mag * ds_mag) -
                               dr_ref.dot(ds_ref) / (dr_mag * ds_mag));
        double eps_yz = 0.5 * (ds_def.dot(dt_def) / (ds_mag * dt_mag) -
                               ds_ref.dot(dt_ref) / (ds_mag * dt_mag));
        double eps_xz = 0.5 * (dr_def.dot(dt_def) / (dr_mag * dt_mag) -
                               dr_ref.dot(dt_ref) / (dr_mag * dt_mag));

        // Convert strain to stress
        StrainTensor strain;
        strain.xx = eps_xx;
        strain.yy = eps_yy;
        strain.zz = eps_zz;
        strain.xy = eps_xy;
        strain.yz = eps_yz;
        strain.xz = eps_xz;
        StressTensor stress = mat.computeStress(strain);

        // Store result
        ElementResult er;
        er.isValid = true;
        er.elementId = elem.id;
        er.isShell = false;
        er.stress = stress;
        er.vonMisesStress = stress.vonMises();

        accumulatedResults_.push_back(er);
    }

    std::cout << "[INFO] Prestress calculated for " << refElements.size() << " elements\n";
}

void ModelAssembler::createCzmElementsForDualOffset(
    const std::vector<ShellElement>& sourceSurface,
    const std::map<int, int>& origToBottomNode,
    const OffsetOperation& op) {

    int czmPid = op.czmPartId > 0 ? op.czmPartId : ++maxPartId_;
    int czmSecid = czmPid;
    int czmMid = ++maxMaterialId_;

    std::cout << "[INFO] Creating CZM elements for dual offset (PID=" << czmPid << ")\n";

    // Create cohesive elements
    for (const auto& shell : sourceSurface) {
        AddedElement cohElem;
        cohElem.id = ++maxElementId_;
        cohElem.pid = czmPid;
        cohElem.type = ElementType::HEX8;

        // Bottom face: original nodes
        cohElem.nodeIds[0] = shell.nodeIds[0];
        cohElem.nodeIds[1] = shell.nodeIds[1];
        cohElem.nodeIds[2] = shell.nodeIds[2];
        cohElem.nodeIds[3] = shell.nodeIds[3];

        // Top face: duplicated nodes
        auto it0 = origToBottomNode.find(shell.nodeIds[0]);
        auto it1 = origToBottomNode.find(shell.nodeIds[1]);
        auto it2 = origToBottomNode.find(shell.nodeIds[2]);
        auto it3 = origToBottomNode.find(shell.nodeIds[3]);

        cohElem.nodeIds[4] = (it0 != origToBottomNode.end()) ? it0->second : shell.nodeIds[0];
        cohElem.nodeIds[5] = (it1 != origToBottomNode.end()) ? it1->second : shell.nodeIds[1];
        cohElem.nodeIds[6] = (it2 != origToBottomNode.end()) ? it2->second : shell.nodeIds[2];
        cohElem.nodeIds[7] = (it3 != origToBottomNode.end()) ? it3->second : shell.nodeIds[3];

        addedElements_.push_back(cohElem);
    }

    // CZM keywords
    std::string partBlock = formatPartBlock(czmPid, czmSecid, czmMid, "CZM_DualOffset");
    std::string sectionBlock = formatCzmSectionBlock(czmSecid);
    std::string materialBlock = op.czmMaterialCard;

    // Replace @MID@ placeholder
    size_t pos = 0;
    while ((pos = materialBlock.find("@MID@", pos)) != std::string::npos) {
        materialBlock.replace(pos, 5, std::to_string(czmMid));
        pos += std::to_string(czmMid).length();
    }

    addedKeywordBlocks_.push_back(partBlock);
    addedKeywordBlocks_.push_back(sectionBlock);
    addedKeywordBlocks_.push_back(materialBlock);

    std::cout << "[INFO] Created " << sourceSurface.size()
              << " CZM elements for dual offset\n";
}

void ModelAssembler::addContactHint(int sourcePid, int offsetPid) {
    std::ostringstream contactHint;
    contactHint << "$\n"
                << "$ ==================== CONTACT DEFINITION REQUIRED ====================\n"
                << "$ Dual offset prestress with contact mode\n"
                << "$ Add contact definition manually:\n"
                << "$\n"
                << "$ *CONTACT_AUTOMATIC_SURFACE_TO_SURFACE\n"
                << "$ $#     cid                                                         title\n"
                << "$       999                                    DualOffset_Contact_Auto\n"
                << "$ $#    ssid      msid     sstyp     mstyp    sboxid    mboxid       spr       mpr\n"
                << "$  " << std::setw(8) << sourcePid
                << std::setw(10) << offsetPid
                << "         2         2         0         0         0         0\n"
                << "$ $#      fs        fd        dc        vc       vdc    penchk        bt        dt\n"
                << "$      0.00      0.00      0.00      0.00      0.00         0      0.00  1.00E+20\n"
                << "$ ======================================================================\n"
                << "$\n";

    addedKeywordBlocks_.push_back(contactHint.str());
}

// ============================================================
//  applyMatswap helpers (anonymous namespace - internal only)
// ============================================================
namespace {

static std::string mw_trim(const std::string& s) {
    size_t a = 0, b = s.size();
    while (a < b && std::isspace((unsigned char)s[a])) ++a;
    while (b > a && std::isspace((unsigned char)s[b-1])) --b;
    return s.substr(a, b - a);
}
static std::vector<std::string> mw_tok10(const std::string& line) {
    std::vector<std::string> v;
    for (size_t i = 0; i < line.size(); i += 10)
        v.push_back(mw_trim(line.substr(i, std::min((size_t)10, line.size()-i))));
    return v;
}
static std::string mw_upper(std::string s) {
    for (auto& c : s) c = (char)std::toupper((unsigned char)c);
    return s;
}
static std::string mw_idType(const std::string& name) {
    std::string u = mw_upper(name);
    if (u.size() >= 5 && u.substr(0,5) == "SECID") return "SECID";
    if (u.size() >= 4 && u.substr(0,4) == "HGID")  return "HGID";
    if (u.size() >= 4 && u.substr(0,4) == "LCID")  return "LCID";
    if (u.size() >= 3 && u.substr(0,3) == "MID")   return "MID";
    if (u.size() >= 3 && u.substr(0,3) == "PID")   return "PID";
    return "";
}

struct MwParam { char type; std::string name; int ivalue; };
struct MwBundle {
    std::vector<MwParam>    params;
    std::vector<std::string> cards;
    int bundlePid=0, bundleSecid=0, bundleMid=0, bundleHgid=0;
};
struct MwPartInfo { int pid=0,secid=0,mid=0,hgid=0,dataLine=-1; };

static int mw_resolveInt(const std::string& tok, const std::vector<MwParam>& params) {
    if (!tok.empty() && tok[0]=='&') {
        std::string nm = mw_upper(tok.substr(1));
        for (const auto& p : params) if (mw_upper(p.name)==nm) return p.ivalue;
        return 0;
    }
    try { return std::stoi(tok); } catch(...){ return 0; }
}

static MwBundle mw_parseBundle(const std::string& path) {
    MwBundle bnd;
    std::ifstream f(path);
    if (!f.is_open()) throw std::runtime_error("Cannot open bundle: " + path);
    enum Sec { OTHER, PARAM, PART } sec = OTHER;
    bool partTitle=false, partData=false;
    std::string ln;
    while (std::getline(f, ln)) {
        if (!ln.empty() && ln.back()=='\r') ln.pop_back();
        std::string tr = mw_trim(ln);
        if (tr.empty()) { if (sec==OTHER) bnd.cards.push_back(ln); continue; }
        if (tr[0]=='*') {
            std::string up = mw_upper(tr);
            if (up=="*PARAMETER" || up.rfind("*PARAMETER_",0)==0)
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
            auto toks = mw_tok10(ln);
            for (size_t i=0; i+1<toks.size(); i+=2) {
                const auto& nf = toks[i];
                if (nf.size()<2) continue;
                MwParam p;
                p.type = (char)std::toupper((unsigned char)nf[0]);
                p.name = mw_trim(nf.substr(1));
                p.ivalue = 0;
                if (p.name.empty()) continue;
                try {
                    if      (p.type=='I') p.ivalue = std::stoi(toks[i+1]);
                    else if (p.type=='R') p.ivalue = (int)std::stod(toks[i+1]);
                } catch(...) {}
                bnd.params.push_back(p);
            }
        } else if (sec==PART) {
            if (!partTitle) { partTitle=true; continue; }
            if (!partData) {
                auto toks = mw_tok10(ln);
                if (toks.size()>=5) {
                    bnd.bundlePid   = mw_resolveInt(toks[0], bnd.params);
                    bnd.bundleSecid = mw_resolveInt(toks[1], bnd.params);
                    bnd.bundleMid   = mw_resolveInt(toks[2], bnd.params);
                    bnd.bundleHgid  = mw_resolveInt(toks[4], bnd.params);
                }
                partData=true;
            }
        } else {
            bnd.cards.push_back(ln);
        }
    }
    return bnd;
}

static int mw_scanMaxId(const std::vector<std::string>& lines, const std::string& prefix) {
    int maxId=0;
    bool active=false; bool hasTitle=false; bool titleDone=false;
    for (const auto& ln : lines) {
        std::string tr = mw_trim(ln);
        if (tr.empty()) continue;
        if (tr[0]=='*') {
            std::string up = mw_upper(tr);
            if (up.rfind(mw_upper(prefix),0)==0) {
                active=true;
                hasTitle=(up.find("_TITLE")!=std::string::npos);
                titleDone=!hasTitle;
            } else { active=false; }
            continue;
        }
        if (!active||tr[0]=='$') continue;
        if (!titleDone) { titleDone=true; continue; }
        auto toks = mw_tok10(ln);
        if (!toks.empty()) { try{int id=std::stoi(toks[0]);if(id>maxId)maxId=id;}catch(...){} }
        active=false;
    }
    return maxId;
}

static MwPartInfo mw_getPartInfo(const std::vector<std::string>& lines, int targetPid) {
    MwPartInfo info;
    bool inPart=false; bool titleDone=false;
    for (int i=0; i<(int)lines.size(); ++i) {
        std::string tr = mw_trim(lines[i]);
        if (tr.empty()) continue;
        if (tr[0]=='*') {
            std::string up=mw_upper(tr);
            inPart=(up=="*PART"||up=="*PART_TITLE"); titleDone=false; continue;
        }
        if (!inPart||tr[0]=='$') continue;
        if (!titleDone) { titleDone=true; continue; }
        auto toks = mw_tok10(lines[i]);
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

// Check if an ID is used by any PART whose PID is NOT in excludeSet
static bool mw_isSharedExcludeSet(const std::vector<std::string>& lines,
                                    int fieldIdx, int targetId,
                                    const std::set<int>& excludeSet) {
    bool inPart=false; bool titleDone=false;
    for (const auto& ln : lines) {
        std::string tr = mw_trim(ln);
        if (tr.empty()) continue;
        if (tr[0]=='*') {
            std::string up=mw_upper(tr);
            inPart=(up=="*PART"||up=="*PART_TITLE"); titleDone=false; continue;
        }
        if (!inPart||tr[0]=='$') continue;
        if (!titleDone) { titleDone=true; continue; }
        auto toks = mw_tok10(ln);
        if ((int)toks.size()>fieldIdx) {
            try {
                int pid=std::stoi(toks[0]);
                if (!excludeSet.count(pid) && std::stoi(toks[fieldIdx])==targetId) return true;
            } catch(...) {}
        }
        titleDone=false; // ready for next title+data pair in same *PART block
    }
    return false;
}

static std::vector<std::string> mw_removeBlock(const std::vector<std::string>& lines,
                                                 const std::string& prefix, int targetId) {
    std::vector<bool> rm(lines.size(), false);
    for (int i=0; i<(int)lines.size(); ) {
        std::string tr = mw_trim(lines[i]);
        if (tr.empty()||tr[0]!='*') { ++i; continue; }
        std::string up = mw_upper(tr);
        if (up.rfind(mw_upper(prefix),0)!=0) { ++i; continue; }
        bool hasTitle=(up.find("_TITLE")!=std::string::npos);
        int titlesLeft=hasTitle?1:0; int id=-1;
        for (int j=i+1; j<(int)lines.size(); ++j) {
            std::string jt = mw_trim(lines[j]);
            if (jt.empty()||jt[0]=='$') continue;
            if (jt[0]=='*') break;
            if (titlesLeft-->0) continue;
            auto toks=mw_tok10(lines[j]);
            if (!toks.empty()) { try{id=std::stoi(toks[0]);}catch(...){} }
            break;
        }
        if (id!=targetId) { ++i; continue; }
        int start=i, end=i+1;
        while (end<(int)lines.size()) {
            std::string et=mw_trim(lines[end]);
            if (!et.empty()&&et[0]=='*') break;
            ++end;
        }
        for (int k=start;k<end;++k) rm[k]=true;
        i=end;
    }
    std::vector<std::string> out;
    for (int i=0;i<(int)lines.size();++i) if(!rm[i]) out.push_back(lines[i]);
    return out;
}

static std::string mw_resolveLine(const std::string& line,
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
            r.replace(pos,patLen,repl); pos+=repl.size();
        }
    }
    return r;
}

static std::string mw_updatePartLine(const std::string& ln, int newSecid, int newMid, int newHgid) {
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

static std::vector<int> mw_getAllPartPids(const std::vector<std::string>& lines) {
    std::vector<int> pids;
    bool inPart=false; bool titleDone=false;
    for (const auto& ln : lines) {
        std::string tr = mw_trim(ln);
        if (tr.empty()) continue;
        if (tr[0]=='*') {
            std::string up=mw_upper(tr);
            inPart=(up=="*PART"||up=="*PART_TITLE"); titleDone=false; continue;
        }
        if (!inPart||tr[0]=='$') continue;
        if (!titleDone) { titleDone=true; continue; }
        auto toks = mw_tok10(ln);
        if (!toks.empty()) { try{ pids.push_back(std::stoi(toks[0])); }catch(...){} }
        titleDone=false; // ready for next title+data pair in same *PART block
    }
    return pids;
}

// Find all PIDs whose MID field (toks[2]) is in targetMids
static std::vector<int> mw_getPidsByMid(const std::vector<std::string>& lines,
                                          const std::set<int>& targetMids) {
    std::vector<int> pids;
    bool inPart=false; bool titleDone=false;
    for (const auto& ln : lines) {
        std::string tr = mw_trim(ln);
        if (tr.empty()) continue;
        if (tr[0]=='*') {
            std::string up=mw_upper(tr);
            inPart=(up=="*PART"||up=="*PART_TITLE"); titleDone=false; continue;
        }
        if (!inPart||tr[0]=='$') continue;
        if (!titleDone) { titleDone=true; continue; }
        auto toks = mw_tok10(ln);
        if (toks.size()>=3) {
            try {
                int pid=std::stoi(toks[0]);
                int mid=std::stoi(toks[2]);
                if (targetMids.count(mid)) pids.push_back(pid);
            } catch(...) {}
        }
        titleDone=false;
    }
    return pids;
}

} // anonymous namespace (matswap helpers)

// ============================================================
//  ModelAssembler::applyMatswap
// ============================================================
bool ModelAssembler::applyMatswap(const MatswapOperation& op, const std::string& configDir) {
    // 1. Resolve bundle path relative to configDir
    std::string bundlePath = op.bundleFile;
    if (!configDir.empty() && !bundlePath.empty() &&
        bundlePath[0] != '/' && bundlePath[0] != '\\' &&
        !(bundlePath.size() >= 2 && bundlePath[1] == ':')) {
        bundlePath = configDir + "/" + bundlePath;
    }

    // 2. Parse bundle
    MwBundle bundle;
    try { bundle = mw_parseBundle(bundlePath); }
    catch (const std::exception& e) {
        errorMessage_ = std::string("matswap: ") + e.what();
        return false;
    }
    infoMessages.push_back("[matswap] bundle: " + bundlePath +
                           "  params=" + std::to_string(bundle.params.size()) +
                           "  cards=" + std::to_string(bundle.cards.size()));

    // 3. Determine target PIDs  (pid/pids/swap_all or mid/mids)
    bool midMode = !op.mids.empty();
    std::vector<int> targetPids;
    if (midMode) {
        std::set<int> targetMids(op.mids.begin(), op.mids.end());
        targetPids = mw_getPidsByMid(rawLines_, targetMids);
        infoMessages.push_back("[matswap] mid-mode: found " + std::to_string(targetPids.size()) +
                               " part(s) using MID(s) specified (SECTION kept)");
    } else if (op.swapAll) {
        targetPids = mw_getAllPartPids(rawLines_);
        infoMessages.push_back("[matswap] swap_all: " + std::to_string(targetPids.size()) + " parts");
    } else {
        targetPids = op.pids;
    }
    if (targetPids.empty()) {
        errorMessage_ = "matswap: no target PIDs (specify pid/pids/mid/mids or swap_all: true)";
        return false;
    }

    std::set<int> targetPidSet(targetPids.begin(), targetPids.end());

    // 4. Get current PART info for each target PID
    std::map<int, MwPartInfo> partInfos;
    for (int pid : targetPids) {
        MwPartInfo info = mw_getPartInfo(rawLines_, pid);
        if (info.dataLine < 0) {
            errorMessage_ = "matswap: PID " + std::to_string(pid) + " not found in model";
            return false;
        }
        partInfos[pid] = info;
        infoMessages.push_back("[matswap] PID " + std::to_string(pid) +
                               " -> MID=" + std::to_string(info.mid) +
                               " SECID=" + std::to_string(info.secid) +
                               " HGID=" + std::to_string(info.hgid));
    }

    // 5. Collect unique old IDs across all targets
    std::set<int> oldMids, oldSecids, oldHgids;
    for (const auto& [pid, info] : partInfos) {
        if (info.mid   > 0) oldMids.insert(info.mid);
        if (info.secid > 0) oldSecids.insert(info.secid);
        if (info.hgid  > 0) oldHgids.insert(info.hgid);
    }

    // 6. Scan model for max IDs
    int maxHGID  = mw_scanMaxId(rawLines_, "*HOURGLASS");
    int maxLCID  = mw_scanMaxId(rawLines_, "*DEFINE_CURVE");
    int maxSECID = mw_scanMaxId(rawLines_, "*SECTION");
    int maxMID   = mw_scanMaxId(rawLines_, "*MAT_");

    // Reuse orphan MID if all target parts share a single MID that is orphaned
    int reuseableMid = -1;
    if (oldMids.size() == 1) {
        int onlyMid = *oldMids.begin();
        if (!mw_isSharedExcludeSet(rawLines_, 2, onlyMid, targetPidSet))
            reuseableMid = onlyMid;
    }

    // 7. Build remap table
    std::map<std::string,int> remap;
    for (const auto& p : bundle.params) {
        if (p.type!='I' && p.type!='R') continue;
        std::string idt = mw_idType(p.name);
        int newVal;
        if      (idt=="HGID")  newVal = ++maxHGID;
        else if (idt=="LCID")  newVal = ++maxLCID;
        else if (idt=="SECID") newVal = ++maxSECID;
        else if (idt=="MID")   newVal = (reuseableMid>0) ? reuseableMid : ++maxMID;
        else if (idt=="PID")   continue;
        else                   newVal = p.ivalue;
        remap[p.name] = newVal;
        infoMessages.push_back("[matswap]   &" + p.name + " (" + idt + ") " +
                               std::to_string(p.ivalue) + " -> " + std::to_string(newVal));
    }

    // Sorted remap (longer names first to avoid prefix collisions)
    std::vector<std::pair<std::string,int>> sortedRemap(remap.begin(), remap.end());
    std::sort(sortedRemap.begin(), sortedRemap.end(),
              [](const auto& a, const auto& b){ return a.first.size() > b.first.size(); });

    // 8. Resolve bundle cards to concrete numbers
    std::vector<std::string> resolvedCards;
    for (const auto& c : bundle.cards)
        resolvedCards.push_back(mw_resolveLine(c, sortedRemap));

    // 9. Remove orphaned old keyword blocks
    for (int mid : oldMids) {
        if (!mw_isSharedExcludeSet(rawLines_, 2, mid, targetPidSet)) {
            rawLines_ = mw_removeBlock(rawLines_, "*MAT_", mid);
            infoMessages.push_back("[matswap] Removed *MAT_ MID=" + std::to_string(mid));
        }
    }
    if (!midMode) {
        // SECTION swap only for PID-based targeting
        for (int secid : oldSecids) {
            if (!mw_isSharedExcludeSet(rawLines_, 1, secid, targetPidSet)) {
                rawLines_ = mw_removeBlock(rawLines_, "*SECTION", secid);
                infoMessages.push_back("[matswap] Removed *SECTION SECID=" + std::to_string(secid));
            }
        }
    }
    for (int hgid : oldHgids) {
        if (!mw_isSharedExcludeSet(rawLines_, 4, hgid, targetPidSet)) {
            rawLines_ = mw_removeBlock(rawLines_, "*HOURGLASS", hgid);
            infoMessages.push_back("[matswap] Removed *HOURGLASS HGID=" + std::to_string(hgid));
        }
    }

    // 10. Determine new IDs from remap for PART update
    int newSecid=-1, newMid=-1, newHgid=-1;
    for (const auto& p : bundle.params) {
        if (!remap.count(p.name)) continue;
        std::string idt = mw_idType(p.name);
        if (idt=="SECID" && newSecid<0) newSecid=remap.at(p.name);
        if (idt=="MID"   && newMid  <0) newMid  =remap.at(p.name);
        if (idt=="HGID"  && newHgid <0) newHgid =remap.at(p.name);
    }

    // 11. Update all target PART data lines
    for (int pid : targetPids) {
        MwPartInfo info2 = mw_getPartInfo(rawLines_, pid);
        if (info2.dataLine >= 0) {
            // mid-mode: keep original SECID
            int appliedSecid = (!midMode && newSecid>=0) ? newSecid : info2.secid;
            int appliedMid   = (newMid  >=0) ? newMid   : info2.mid;
            int appliedHgid  = (newHgid >=0) ? newHgid  : info2.hgid;
            rawLines_[info2.dataLine] = mw_updatePartLine(
                rawLines_[info2.dataLine], appliedSecid, appliedMid, appliedHgid);
            infoMessages.push_back("[matswap] Updated PID " + std::to_string(pid) +
                                   " -> SECID=" + std::to_string(appliedSecid) +
                                   " MID=" + std::to_string(appliedMid) +
                                   " HGID=" + std::to_string(appliedHgid));
        }
    }

    // 12. Insert resolved bundle cards before *END in rawLines_
    //     mid-mode: filter out *SECTION_* blocks (ELFORM stays unchanged)
    if (midMode) {
        std::vector<std::string> filtered;
        bool inSection = false;
        for (const auto& c : resolvedCards) {
            std::string up = mw_upper(mw_trim(c));
            if (!up.empty() && up[0]=='*') inSection = (up.rfind("*SECTION",0)==0);
            if (!inSection) filtered.push_back(c);
        }
        resolvedCards = std::move(filtered);
    }
    std::vector<std::string> newLines;
    bool inserted = false;
    for (const auto& ln : rawLines_) {
        if (!inserted && mw_upper(mw_trim(ln)) == "*END") {
            for (const auto& c : resolvedCards) newLines.push_back(c);
            inserted = true;
        }
        newLines.push_back(ln);
    }
    if (!inserted)
        for (const auto& c : resolvedCards) newLines.push_back(c);
    rawLines_ = std::move(newLines);

    infoMessages.push_back("[matswap] Done: " + std::to_string(targetPids.size()) + " part(s) swapped");
    return true;
}

// ============================================================
//  applyMatdb helpers (anonymous namespace - internal only)
// ============================================================

// ── Minimal JSON parser ──────────────────────────────────────
struct MdJsonValue {
    enum Type { NUL, BOOL, NUMBER, STRING, ARRAY, OBJECT };
    Type type = NUL;
    double num = 0;
    bool bval = false;
    std::string str;
    std::vector<MdJsonValue> arr;
    std::vector<std::pair<std::string, MdJsonValue>> obj;

    const MdJsonValue* get(const std::string& key) const {
        if (type != OBJECT) return nullptr;
        for (auto& p : obj) if (p.first == key) return &p.second;
        return nullptr;
    }
    std::string asStr(const std::string& def = "") const { return type == STRING ? str : def; }
    double asNum(double def = 0) const { return type == NUMBER ? num : def; }
    int asInt(int def = 0) const { return type == NUMBER ? (int)num : def; }
};

static void md_skipWs(const std::string& s, size_t& p) {
    while (p < s.size() && std::isspace((unsigned char)s[p])) ++p;
}

static MdJsonValue md_parseValue(const std::string& s, size_t& p);

static std::string md_parseString(const std::string& s, size_t& p) {
    if (p >= s.size() || s[p] != '"') return "";
    ++p;
    std::string r;
    while (p < s.size() && s[p] != '"') {
        if (s[p] == '\\' && p + 1 < s.size()) {
            ++p;
            switch (s[p]) {
                case 'n': r += '\n'; break;
                case 't': r += '\t'; break;
                case '"': r += '"'; break;
                case '\\': r += '\\'; break;
                case '/': r += '/'; break;
                default: r += '\\'; r += s[p]; break;
            }
        } else {
            r += s[p];
        }
        ++p;
    }
    if (p < s.size()) ++p; // skip closing "
    return r;
}

static MdJsonValue md_parseObject(const std::string& s, size_t& p) {
    MdJsonValue v; v.type = MdJsonValue::OBJECT;
    ++p; // skip {
    md_skipWs(s, p);
    while (p < s.size() && s[p] != '}') {
        md_skipWs(s, p);
        std::string key = md_parseString(s, p);
        md_skipWs(s, p);
        if (p < s.size() && s[p] == ':') ++p;
        md_skipWs(s, p);
        v.obj.push_back({key, md_parseValue(s, p)});
        md_skipWs(s, p);
        if (p < s.size() && s[p] == ',') ++p;
    }
    if (p < s.size()) ++p; // skip }
    return v;
}

static MdJsonValue md_parseArray(const std::string& s, size_t& p) {
    MdJsonValue v; v.type = MdJsonValue::ARRAY;
    ++p; // skip [
    md_skipWs(s, p);
    while (p < s.size() && s[p] != ']') {
        v.arr.push_back(md_parseValue(s, p));
        md_skipWs(s, p);
        if (p < s.size() && s[p] == ',') ++p;
        md_skipWs(s, p);
    }
    if (p < s.size()) ++p; // skip ]
    return v;
}

static MdJsonValue md_parseValue(const std::string& s, size_t& p) {
    md_skipWs(s, p);
    if (p >= s.size()) return {};
    if (s[p] == '"') { MdJsonValue v; v.type = MdJsonValue::STRING; v.str = md_parseString(s, p); return v; }
    if (s[p] == '{') return md_parseObject(s, p);
    if (s[p] == '[') return md_parseArray(s, p);
    if (s[p] == 't') { MdJsonValue v; v.type = MdJsonValue::BOOL; v.bval = true; p += std::min((size_t)4, s.size()-p); return v; }
    if (s[p] == 'f') { MdJsonValue v; v.type = MdJsonValue::BOOL; v.bval = false; p += std::min((size_t)5, s.size()-p); return v; }
    if (s[p] == 'n') { p += std::min((size_t)4, s.size()-p); return {}; }
    // number (guard against unexpected characters)
    if (s[p] != '-' && !std::isdigit((unsigned char)s[p])) { ++p; return {}; }
    MdJsonValue v; v.type = MdJsonValue::NUMBER;
    size_t start = p;
    if (s[p] == '-') ++p;
    while (p < s.size() && (std::isdigit((unsigned char)s[p]) || s[p] == '.' || s[p] == 'e' || s[p] == 'E' || s[p] == '+' || s[p] == '-')) {
        if ((s[p] == '+' || s[p] == '-') && p > start && s[p-1] != 'e' && s[p-1] != 'E') break;
        ++p;
    }
    if (p == start) return {};
    try { v.num = std::stod(s.substr(start, p - start)); } catch (...) { return {}; }
    return v;
}

static MdJsonValue md_parseJson(const std::string& text) {
    size_t p = 0;
    return md_parseValue(text, p);
}

// ── DB data structures ───────────────────────────────────────
struct MdDbMaterial {
    int dbMid = 0;
    std::string name;
    std::string tag;
    std::string category;
    std::string defaultMatType;
    std::map<std::string, std::string> cardsStructural; // matType → card text
    std::string cardThermal;
    std::string cardThermalExpansion;
};

struct MdMaterialDatabase {
    std::map<int, MdDbMaterial> materials;
};

static MdMaterialDatabase md_loadDatabase(const std::string& jsonPath) {
    MdMaterialDatabase db;
    std::ifstream f(jsonPath);
    if (!f.is_open()) return db;
    std::string text((std::istreambuf_iterator<char>(f)), std::istreambuf_iterator<char>());
    f.close();

    MdJsonValue root = md_parseJson(text);
    auto* mats = root.get("materials");
    if (!mats || mats->type != MdJsonValue::OBJECT) return db;

    for (auto& kv : mats->obj) {
        int mid = 0;
        try { mid = std::stoi(kv.first); } catch (...) { continue; }
        auto& jm = kv.second;
        MdDbMaterial m;
        m.dbMid = mid;
        m.name = jm.get("name") ? jm.get("name")->asStr() : "";
        m.tag = jm.get("tag") ? jm.get("tag")->asStr() : "";
        m.category = jm.get("category") ? jm.get("category")->asStr() : "";
        m.defaultMatType = jm.get("mat_type") ? jm.get("mat_type")->asStr() : "MAT_ELASTIC";
        m.cardThermal = jm.get("card_thermal") ? jm.get("card_thermal")->asStr() : "";
        m.cardThermalExpansion = jm.get("card_thermal_expansion") ? jm.get("card_thermal_expansion")->asStr() : "";
        auto* cs = jm.get("cards_structural");
        if (cs && cs->type == MdJsonValue::OBJECT) {
            for (auto& ck : cs->obj)
                m.cardsStructural[ck.first] = ck.second.asStr();
        }
        db.materials[mid] = std::move(m);
    }
    return db;
}

// ── MAT block scanning ──────────────────────────────────────
struct MdMatBlock {
    int mid = 0;
    std::string keyword;      // e.g. "*MAT_ELASTIC_TITLE"
    std::string titleText;    // title line (for name matching)
    int startLine = 0;
    int endLine = 0;
};

static std::vector<MdMatBlock> md_scanMatBlocks(const std::vector<std::string>& lines) {
    std::vector<MdMatBlock> blocks;
    for (int i = 0; i < (int)lines.size(); ++i) {
        std::string t = mw_trim(lines[i]);
        if (t.empty() || t[0] != '*') continue;
        std::string u = mw_upper(t);
        if (u.substr(0, 5) != "*MAT_") continue;
        // Exclude *MAT_THERMAL_*, *MAT_ADD_*
        if (u.find("*MAT_THERMAL_") == 0 || u.find("*MAT_ADD_") == 0) continue;

        bool hasTitle = (u.find("_TITLE") != std::string::npos);
        MdMatBlock blk;
        blk.keyword = u;
        blk.startLine = i;

        int j = i + 1;
        bool gotTitle = false;
        while (j < (int)lines.size()) {
            std::string lt = mw_trim(lines[j]);
            if (lt.empty() || lt[0] == '$') { ++j; continue; }
            if (lt[0] == '*') break;
            if (hasTitle && !gotTitle) {
                blk.titleText = lt;
                gotTitle = true;
                ++j;
                continue;
            }
            // first data line → extract MID
            auto toks = mw_tok10(lines[j]);
            if (!toks.empty()) {
                try { blk.mid = std::stoi(toks[0]); } catch (...) {}
            }
            // find end of block
            int end = j + 1;
            while (end < (int)lines.size()) {
                std::string et = mw_trim(lines[end]);
                if (!et.empty() && et[0] == '*') break;
                ++end;
            }
            blk.endLine = end;
            blocks.push_back(blk);
            break;
        }
    }
    return blocks;
}

// ── Matching ─────────────────────────────────────────────────
static std::string md_lowerStr(std::string s) {
    for (auto& c : s) c = (char)std::tolower((unsigned char)c);
    return s;
}

static int md_autoMatchDb(const std::string& titleText, int modelMid,
                           const MdMaterialDatabase& db) {
    if (titleText.empty()) {
        // try direct MID lookup
        auto it = db.materials.find(modelMid);
        return it != db.materials.end() ? modelMid : 0;
    }
    std::string tl = md_lowerStr(titleText);
    // 1. match by name (substring, case-insensitive, longest match wins)
    int bestMid = 0;
    size_t bestLen = 0;
    for (auto& kv : db.materials) {
        if (kv.second.name.empty()) continue;
        std::string nl = md_lowerStr(kv.second.name);
        if (nl.size() > bestLen && tl.find(nl) != std::string::npos) {
            bestLen = nl.size();
            bestMid = kv.first;
        }
    }
    if (bestMid > 0) return bestMid;
    // 2. match by tag (longest match wins)
    bestLen = 0;
    for (auto& kv : db.materials) {
        if (kv.second.tag.empty()) continue;
        std::string tgl = md_lowerStr(kv.second.tag);
        if (tgl.size() > bestLen && tl.find(tgl) != std::string::npos) {
            bestLen = tgl.size();
            bestMid = kv.first;
        }
    }
    if (bestMid > 0) return bestMid;
    // 3. direct MID lookup
    auto it = db.materials.find(modelMid);
    return it != db.materials.end() ? modelMid : 0;
}

static int md_matchRule(const MdMatBlock& blk, const MatdbMaterialRule& rule,
                         const MdMaterialDatabase& db) {
    if (rule.match.empty() && rule.mid <= 0) return 0;  // empty rule → no match
    if (rule.mid > 0) {
        if (blk.mid == rule.mid) {
            auto it = db.materials.find(rule.mid);
            return it != db.materials.end() ? rule.mid : 0;
        }
        return 0;
    }
    if (rule.match == "*" || rule.match == "all") {
        return md_autoMatchDb(blk.titleText, blk.mid, db);
    }
    // substring match: rule.match vs titleText
    std::string ml = md_lowerStr(rule.match);
    std::string tl = md_lowerStr(blk.titleText);
    if (!tl.empty() && tl.find(ml) != std::string::npos) {
        // find DB entry with matching name/tag
        for (auto& kv : db.materials) {
            if (md_lowerStr(kv.second.name).find(ml) != std::string::npos ||
                md_lowerStr(kv.second.tag).find(ml) != std::string::npos)
                return kv.first;
        }
    }
    // also try: match against DB name/tag directly (user types DB name, any title)
    for (auto& kv : db.materials) {
        if (md_lowerStr(kv.second.name) == ml || md_lowerStr(kv.second.tag) == ml) {
            // verify this DB entry matches the model block (check both name and tag)
            if (!blk.titleText.empty() &&
                (tl.find(md_lowerStr(kv.second.name)) != std::string::npos ||
                 tl.find(md_lowerStr(kv.second.tag)) != std::string::npos))
                return kv.first;
            // if no title, match by MID
            if (blk.mid == kv.first) return kv.first;
        }
    }
    return 0;
}

// ── MAT type normalization ───────────────────────────────────
static std::string md_normalizeMatType(const std::string& input) {
    std::string u = mw_upper(mw_trim(input));
    if (u == "MAT_001" || u == "MAT_1") return "MAT_ELASTIC";
    if (u == "MAT_020" || u == "MAT_20") return "MAT_RIGID";
    if (u == "MAT_024" || u == "MAT_24") return "MAT_PIECEWISE_LINEAR_PLASTICITY";
    if (u == "MAT_027" || u == "MAT_27") return "MAT_MOONEY-RIVLIN_RUBBER";
    if (u == "MAT_006" || u == "MAT_6") return "MAT_VISCOELASTIC";
    if (u == "MAT_076" || u == "MAT_76") return "MAT_GENERAL_VISCOELASTIC";
    return u;
}

// ── Card ID substitution ─────────────────────────────────────
static std::vector<std::string> md_splitLines(const std::string& s) {
    std::vector<std::string> lines;
    std::istringstream iss(s);
    std::string ln;
    while (std::getline(iss, ln)) lines.push_back(ln);
    return lines;
}

static std::string md_setField(const std::string& line, int startCol, int width, int value) {
    std::string r = line;
    while ((int)r.size() < startCol + width) r += ' ';
    std::string vs = std::to_string(value);
    if ((int)vs.size() > width) vs = vs.substr(vs.size() - width);
    std::string padded = std::string(width - (int)vs.size(), ' ') + vs;
    r.replace(startCol, width, padded);
    return r;
}

static std::vector<std::string> md_substituteCardMid(const std::string& cardText, int newMid) {
    auto lines = md_splitLines(cardText);
    bool foundKeyword = false;
    bool hasTitle = false;
    bool skippedTitle = false;

    // Detect if _TITLE variant
    if (!lines.empty()) {
        std::string u = mw_upper(mw_trim(lines[0]));
        if (u.find("_TITLE") != std::string::npos) hasTitle = true;
    }

    for (int i = 0; i < (int)lines.size(); ++i) {
        std::string t = mw_trim(lines[i]);
        if (!foundKeyword) {
            if (!t.empty() && t[0] == '*') { foundKeyword = true; }
            continue;
        }
        if (t.empty() || t[0] == '$') continue;
        if (hasTitle && !skippedTitle) {
            skippedTitle = true;
            continue;
        }
        // This is the first data line — field 0 = MID (bytes 0-9)
        lines[i] = md_setField(lines[i], 0, 10, newMid);
        break;
    }

    // Also update $HWCOLOR MATERIAL line if present
    for (auto& ln : lines) {
        std::string t = mw_trim(ln);
        if (t.substr(0, 18) == "$HWCOLOR MATERIAL " || t.substr(0, 18) == "$HWCOLOR MATERIAL\t") {
            // Format: $HWCOLOR MATERIAL     <MID>    <COLOR>
            // Field after "MATERIAL" at col 18, width 10
            ln = md_setField(ln, 18, 10, newMid);
        }
    }

    return lines;
}

static std::vector<std::string> md_substituteCardTmid(const std::string& cardText, int newTmid) {
    auto lines = md_splitLines(cardText);
    bool foundKeyword = false;
    bool hasTitle = false;
    bool skippedTitle = false;

    if (!lines.empty()) {
        std::string u = mw_upper(mw_trim(lines[0]));
        if (u.find("_TITLE") != std::string::npos) hasTitle = true;
    }

    for (int i = 0; i < (int)lines.size(); ++i) {
        std::string t = mw_trim(lines[i]);
        if (!foundKeyword) {
            if (!t.empty() && t[0] == '*') { foundKeyword = true; }
            continue;
        }
        if (t.empty() || t[0] == '$') continue;
        if (hasTitle && !skippedTitle) { skippedTitle = true; continue; }
        // TMID = field 0 (bytes 0-9)
        lines[i] = md_setField(lines[i], 0, 10, newTmid);
        break;
    }
    return lines;
}

static std::vector<std::string> md_substituteCardPid(const std::string& cardText, int newPid) {
    auto lines = md_splitLines(cardText);
    bool foundKeyword = false;

    for (int i = 0; i < (int)lines.size(); ++i) {
        std::string t = mw_trim(lines[i]);
        if (!foundKeyword) {
            if (!t.empty() && t[0] == '*') { foundKeyword = true; }
            continue;
        }
        if (t.empty() || t[0] == '$') continue;
        // PID = field 0 (bytes 0-9)
        lines[i] = md_setField(lines[i], 0, 10, newPid);
        break;
    }
    return lines;
}

static std::string md_updatePartTmid(const std::string& partDataLine, int tmid) {
    return md_setField(partDataLine, 70, 10, tmid);
}

// end matdb helpers

// ── applyMatdb() main ────────────────────────────────────────
bool ModelAssembler::applyMatdb(const MatdbOperation& op, const std::string& configDir) {
    // infoMessages is a public member of ModelAssembler (no underscore)

    // 1. Resolve database path
    std::string dbPath = op.databasePath;
    if (dbPath.empty()) dbPath = "materials/material_db.json";
    if (dbPath.find('/') == std::string::npos && dbPath.find('\\') == std::string::npos) {
        if (!configDir.empty()) dbPath = configDir + "/" + dbPath;
    }

    // 2. Load database
    MdMaterialDatabase db = md_loadDatabase(dbPath);
    if (db.materials.empty()) {
        errorMessage_ = "[matdb] ERROR: Cannot load database from: " + dbPath;
        return false;
    }
    infoMessages.push_back("[matdb] Loaded " + std::to_string(db.materials.size()) + " materials from DB");

    // 3. Scan model *MAT blocks
    auto matBlocks = md_scanMatBlocks(rawLines_);
    if (matBlocks.empty()) {
        infoMessages.push_back("[matdb] WARNING: No *MAT_ blocks found in model");
        return true;
    }
    infoMessages.push_back("[matdb] Found " + std::to_string(matBlocks.size()) + " MAT blocks in model");

    // 4. Match each MAT block to DB
    struct MatchInfo {
        int modelMid;
        int dbMid;
        std::string matType;
        bool thermal;
        int blockIdx;
    };
    std::vector<MatchInfo> matches;
    std::set<int> matchedMids;

    for (int bi = 0; bi < (int)matBlocks.size(); ++bi) {
        auto& blk = matBlocks[bi];
        int dbMid = 0;
        std::string matType = md_normalizeMatType(op.globalMatType);
        bool thermal = op.globalThermal;

        if (!op.rules.empty()) {
            for (auto& rule : op.rules) {
                int m = md_matchRule(blk, rule, db);
                if (m > 0) {
                    dbMid = m;
                    if (!rule.matType.empty()) matType = md_normalizeMatType(rule.matType);
                    if (rule.thermalOverride >= 0) thermal = (rule.thermalOverride != 0);
                    break;
                }
            }
        } else {
            dbMid = md_autoMatchDb(blk.titleText, blk.mid, db);
        }

        if (dbMid <= 0) {
            infoMessages.push_back("[matdb] WARNING: No DB match for MID=" +
                std::to_string(blk.mid) + " (" + blk.titleText + ")");
            continue;
        }

        // Validate mat_type exists in DB
        auto dit = db.materials.find(dbMid);
        if (dit == db.materials.end()) continue;
        if (dit->second.cardsStructural.find(matType) == dit->second.cardsStructural.end()) {
            errorMessage_ = "[matdb] ERROR: DB MID=" + std::to_string(dbMid) +
                " (" + dit->second.name + ") has no card for " + matType +
                ". Available: ";
            for (auto& ck : dit->second.cardsStructural)
                errorMessage_ += ck.first + " ";
            return false;
        }

        // Check thermal card availability
        if (thermal && dit->second.cardThermal.empty()) {
            infoMessages.push_back("[matdb] WARNING: No thermal card for DB MID=" +
                std::to_string(dbMid) + ", skipping thermal for this material");
            thermal = false;
        }

        matches.push_back({blk.mid, dbMid, matType, thermal, bi});
        matchedMids.insert(blk.mid);
    }

    if (matches.empty()) {
        infoMessages.push_back("[matdb] WARNING: No materials matched");
        return true;
    }

    // 6. Remove old MAT blocks (mark with sentinel, reverse order)
    // Also remove existing thermal blocks for matched MIDs
    const std::string DEL = "\x01""DEL";
    for (int bi = (int)matBlocks.size() - 1; bi >= 0; --bi) {
        auto& blk = matBlocks[bi];
        if (matchedMids.find(blk.mid) == matchedMids.end()) continue;
        for (int li = blk.startLine; li < blk.endLine && li < (int)rawLines_.size(); ++li)
            rawLines_[li] = DEL;
    }

    // Remove existing *MAT_THERMAL_* and *MAT_ADD_THERMAL_EXPANSION for matched MIDs
    for (int i = 0; i < (int)rawLines_.size(); ++i) {
        std::string t = mw_trim(rawLines_[i]);
        if (t.empty() || t[0] != '*') continue;
        std::string u = mw_upper(t);
        bool isThermal = (u.find("*MAT_THERMAL_") == 0);
        bool isExpansion = (u.find("*MAT_ADD_THERMAL_EXPANSION") == 0);
        if (!isThermal && !isExpansion) continue;

        bool hasT = (u.find("_TITLE") != std::string::npos);
        int j = i + 1;
        bool st = false;
        while (j < (int)rawLines_.size()) {
            std::string lt = mw_trim(rawLines_[j]);
            if (lt.empty() || lt[0] == '$') { ++j; continue; }
            if (lt[0] == '*') break;
            if (hasT && !st) { st = true; ++j; continue; }
            auto toks = mw_tok10(rawLines_[j]);
            if (!toks.empty()) {
                int id = 0;
                try { id = std::stoi(toks[0]); } catch (...) {}
                if (matchedMids.count(id) || isExpansion) {
                    // thermal: id=TMID → check matchedMids directly
                    // expansion: id=PID → resolve PID→MID
                    bool shouldRemove = false;
                    if (isThermal) {
                        shouldRemove = matchedMids.count(id) > 0;
                    } else {
                        // expansion: id is PID, find its MID
                        auto info = mw_getPartInfo(rawLines_, id);
                        if (info.dataLine >= 0) {
                            auto ptoks = mw_tok10(rawLines_[info.dataLine]);
                            if (ptoks.size() > 2) {
                                int pmid = 0;
                                try { pmid = std::stoi(ptoks[2]); } catch (...) {}
                                shouldRemove = matchedMids.count(pmid) > 0;
                            }
                        }
                    }
                    if (shouldRemove) {
                        int end = j + 1;
                        while (end < (int)rawLines_.size()) {
                            std::string et = mw_trim(rawLines_[end]);
                            if (!et.empty() && et[0] == '*') break;
                            ++end;
                        }
                        for (int li = i; li < end; ++li) rawLines_[li] = DEL;
                    }
                }
            }
            break;
        }
    }

    // 7. Build new cards to insert
    std::vector<std::string> insertCards;
    int structCount = 0, thermalCount = 0, expansionCount = 0;

    for (auto& mi : matches) {
        auto& dbMat = db.materials[mi.dbMid];

        // Structural card
        auto structLines = md_substituteCardMid(dbMat.cardsStructural[mi.matType], mi.modelMid);
        for (auto& sl : structLines) insertCards.push_back(sl);
        ++structCount;

        // Thermal cards
        if (mi.thermal) {
            // *MAT_THERMAL_ISOTROPIC
            if (!dbMat.cardThermal.empty()) {
                auto thermalLines = md_substituteCardTmid(dbMat.cardThermal, mi.modelMid);
                for (auto& tl : thermalLines) insertCards.push_back(tl);
                ++thermalCount;
            }

            // *MAT_ADD_THERMAL_EXPANSION — one per PID
            if (!dbMat.cardThermalExpansion.empty()) {
                auto pids = mw_getPidsByMid(rawLines_, {mi.modelMid});
                for (int pid : pids) {
                    auto expLines = md_substituteCardPid(dbMat.cardThermalExpansion, pid);
                    for (auto& el : expLines) insertCards.push_back(el);
                    ++expansionCount;
                }
            }

            // Update *PART TMID field
            auto pids = mw_getPidsByMid(rawLines_, {mi.modelMid});
            for (int pid : pids) {
                auto info = mw_getPartInfo(rawLines_, pid);
                if (info.dataLine >= 0)
                    rawLines_[info.dataLine] = md_updatePartTmid(rawLines_[info.dataLine], mi.modelMid);
            }
        }
    }

    // 8. Remove sentinel-marked lines from deletions
    std::vector<std::string> cleanLines;
    cleanLines.reserve(rawLines_.size());
    for (auto& ln : rawLines_) {
        if (ln != DEL) cleanLines.push_back(ln);
    }
    rawLines_ = std::move(cleanLines);

    // 9. Insert new cards before *END
    std::vector<std::string> newLines;
    newLines.reserve(rawLines_.size() + insertCards.size());
    bool inserted = false;
    for (auto& ln : rawLines_) {
        if (!inserted) {
            std::string u = mw_upper(mw_trim(ln));
            if (u == "*END") {
                for (auto& c : insertCards) newLines.push_back(c);
                inserted = true;
            }
        }
        newLines.push_back(ln);
    }
    if (!inserted)
        for (auto& c : insertCards) newLines.push_back(c);
    rawLines_ = std::move(newLines);

    infoMessages.push_back("[matdb] Replaced " + std::to_string(structCount) + " structural MAT cards (" +
        md_normalizeMatType(op.globalMatType) + ")");
    if (thermalCount > 0)
        infoMessages.push_back("[matdb] Inserted " + std::to_string(thermalCount) + " thermal + " +
            std::to_string(expansionCount) + " expansion cards, TMID updated");

    return true;
}

// ============================================================================
//  applyLoad helpers
// ============================================================================

namespace {

struct LdFaceInfo {
    std::array<int,4> nodeIds;
    double verts[4][3];
    double normal[3];
    double area;
    double centroid[3];
    int nVerts; // 3 or 4
};

static double ld_mag(const double v[3]) {
    return std::sqrt(v[0]*v[0] + v[1]*v[1] + v[2]*v[2]);
}

static double ld_dot(const double a[3], const double b[3]) {
    return a[0]*b[0] + a[1]*b[1] + a[2]*b[2];
}

// Extract outer surface faces from baseMesh_ elements for given PID
static std::vector<std::array<int,4>> ld_extractSurface(
        const KooRemapper::Mesh& mesh, int pid) {
    std::vector<std::array<int,4>> faces;
    std::map<std::array<int,4>, std::pair<int, std::array<int,4>>> faceMap;

    for (const auto& [eid, elem] : mesh.getElements()) {
        if (elem.partId != pid) continue;
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
            if (it == faceMap.end()) faceMap[key] = {1, winding};
            else it->second.first++;
        }
    }
    for (const auto& [key, val] : faceMap) {
        if (val.first == 1) faces.push_back(val.second);
    }
    return faces;
}

// Build face info with normals and areas
static std::vector<LdFaceInfo> ld_buildFaceInfo(
        const std::vector<std::array<int,4>>& faces,
        const KooRemapper::Mesh& mesh) {
    std::vector<LdFaceInfo> infos;
    infos.reserve(faces.size());
    for (const auto& f : faces) {
        LdFaceInfo fi;
        fi.nodeIds = f;
        bool isTri = (f[3] == f[2] || f[3] == 0);
        fi.nVerts = isTri ? 3 : 4;

        bool valid = true;
        for (int k = 0; k < fi.nVerts; ++k) {
            const auto* nd = mesh.getNode(f[k]);
            if (!nd) { valid = false; break; }
            fi.verts[k][0] = nd->position.x;
            fi.verts[k][1] = nd->position.y;
            fi.verts[k][2] = nd->position.z;
        }
        if (!valid) continue;

        // For triangles, copy v2 to v3
        if (isTri) {
            fi.verts[3][0] = fi.verts[2][0];
            fi.verts[3][1] = fi.verts[2][1];
            fi.verts[3][2] = fi.verts[2][2];
        }

        // Normal via cross product of diagonals (works for tri and quad)
        double d1[3] = {fi.verts[2][0]-fi.verts[0][0], fi.verts[2][1]-fi.verts[0][1], fi.verts[2][2]-fi.verts[0][2]};
        double d2[3] = {fi.verts[3][0]-fi.verts[1][0], fi.verts[3][1]-fi.verts[1][1], fi.verts[3][2]-fi.verts[1][2]};
        fi.normal[0] = d1[1]*d2[2] - d1[2]*d2[1];
        fi.normal[1] = d1[2]*d2[0] - d1[0]*d2[2];
        fi.normal[2] = d1[0]*d2[1] - d1[1]*d2[0];

        double mag = ld_mag(fi.normal);
        fi.area = mag * 0.5;
        if (mag > 1e-30) {
            fi.normal[0] /= mag;
            fi.normal[1] /= mag;
            fi.normal[2] /= mag;
        }

        // Centroid
        fi.centroid[0] = fi.centroid[1] = fi.centroid[2] = 0;
        for (int k = 0; k < fi.nVerts; ++k) {
            fi.centroid[0] += fi.verts[k][0];
            fi.centroid[1] += fi.verts[k][1];
            fi.centroid[2] += fi.verts[k][2];
        }
        fi.centroid[0] /= fi.nVerts;
        fi.centroid[1] /= fi.nVerts;
        fi.centroid[2] /= fi.nVerts;

        infos.push_back(fi);
    }
    return infos;
}

// Filter faces by direction+angle tolerance
static std::vector<int> ld_filterByDirection(
        const std::vector<LdFaceInfo>& infos,
        const double dir[3], double angleTolDeg) {
    std::vector<int> indices;
    double dirMag = ld_mag(dir);
    if (dirMag < 1e-30) return indices;
    double udir[3] = {dir[0]/dirMag, dir[1]/dirMag, dir[2]/dirMag};
    double cosLimit = std::cos(angleTolDeg * 3.14159265358979323846 / 180.0);

    for (int i = 0; i < (int)infos.size(); ++i) {
        double dot = ld_dot(infos[i].normal, udir);
        // Select faces whose normals are within angle tolerance of the direction
        // Use absolute dot to catch both orientations
        if (std::abs(dot) >= cosLimit) {
            indices.push_back(i);
        }
    }
    return indices;
}

// Resolve part name -> PID from rawLines
static int ld_resolvePid(const std::vector<std::string>& rawLines,
                          int pid, const std::string& partName) {
    if (pid > 0) return pid;
    if (partName.empty()) return 0;

    std::string upperName = partName;
    std::transform(upperName.begin(), upperName.end(), upperName.begin(),
                   [](unsigned char c) { return (char)std::toupper(c); });

    bool inPart = false;
    bool needTitle = true;
    bool titleMatched = false;
    for (const auto& line : rawLines) {
        if (!line.empty() && line[0] == '*') {
            std::string up = line;
            for (auto& c : up) c = (char)std::toupper((unsigned char)c);
            if (up.find("*PART") == 0 && (up.size() == 5 || up[5] == '\r' || up[5] == '_')) {
                inPart = true;
                needTitle = true;
                titleMatched = false;
                continue;
            }
            inPart = false;
            continue;
        }
        if (!inPart) continue;
        if (!line.empty() && line[0] == '$') continue;
        if (needTitle) {
            std::string upperTitle = line;
            std::transform(upperTitle.begin(), upperTitle.end(), upperTitle.begin(),
                           [](unsigned char c) { return (char)std::toupper(c); });
            titleMatched = (upperTitle.find(upperName) != std::string::npos);
            needTitle = false;
            continue;
        }
        // Data line
        if (titleMatched) {
            std::istringstream iss(line);
            int foundPid = 0;
            if (iss >> foundPid) return foundPid;
        }
        inPart = false;
    }
    return 0;
}

// Find max *DEFINE_CURVE ID
static int ld_findMaxCurveId(const std::vector<std::string>& rawLines) {
    int maxId = 0;
    bool inCurve = false;
    bool needData = false;
    for (const auto& line : rawLines) {
        if (!line.empty() && line[0] == '*') {
            std::string up = line;
            for (auto& c : up) c = (char)std::toupper((unsigned char)c);
            if (up.find("*DEFINE_CURVE") == 0) {
                inCurve = true;
                needData = true;
                continue;
            }
            inCurve = false;
            continue;
        }
        if (!inCurve || !needData) continue;
        if (!line.empty() && line[0] == '$') continue;
        needData = false;
        inCurve = false;
        std::istringstream iss(line);
        int id = 0;
        if (iss >> id && id > maxId) maxId = id;
    }
    return maxId;
}

// Find max *SET_SEGMENT ID
static int ld_findMaxSetSegmentId(const std::vector<std::string>& rawLines) {
    int maxId = 0;
    bool inSet = false;
    bool needData = false;
    for (const auto& line : rawLines) {
        if (!line.empty() && line[0] == '*') {
            std::string up = line;
            for (auto& c : up) c = (char)std::toupper((unsigned char)c);
            if (up.find("*SET_SEGMENT") == 0) {
                inSet = true;
                needData = true;
                continue;
            }
            inSet = false;
            continue;
        }
        if (!inSet || !needData) continue;
        if (!line.empty() && line[0] == '$') continue;
        needData = false;
        inSet = false;
        std::istringstream iss(line);
        int id = 0;
        if (iss >> id && id > maxId) maxId = id;
    }
    return maxId;
}

// Generate *DEFINE_CURVE card
static std::string ld_generateDefineCurve(int lcid,
        const std::vector<KooRemapper::LoadCurvePoint>& points) {
    std::ostringstream ss;
    ss << "*DEFINE_CURVE\n";
    ss << "$#    lcid      sidr       sfa       sfo      offa      offo    dattyp     lcint\n";
    char buf[128];
    snprintf(buf, sizeof(buf), "%10d%10d%10s%10s%10s%10s%10d%10d",
             lcid, 0, "1.0", "1.0", "0.0", "0.0", 0, 0);
    ss << buf << "\n";
    ss << "$#                a1                  o1\n";
    for (const auto& pt : points) {
        snprintf(buf, sizeof(buf), "%20.10E%20.10E", pt.time, pt.value);
        ss << buf << "\n";
    }
    return ss.str();
}

// Generate *SET_SEGMENT_TITLE card
static std::string ld_generateSetSegment(int setId,
        const std::vector<std::array<int,4>>& faces,
        const std::string& title = "") {
    std::ostringstream ss;
    if (title.empty())
        ss << "*SET_SEGMENT\n";
    else
        ss << "*SET_SEGMENT_TITLE\n" << title << "\n";
    ss << "$#     sid       da1       da2       da3       da4\n";
    char buf[90];
    snprintf(buf, sizeof(buf), "%10d  0.000000  0.000000  0.000000  0.000000", setId);
    ss << buf << "\n";
    ss << "$#      n1        n2        n3        n4\n";
    for (const auto& f : faces) {
        snprintf(buf, sizeof(buf), "%10d%10d%10d%10d", f[0], f[1], f[2], f[3]);
        ss << buf << "\n";
    }
    return ss.str();
}

// Generate *LOAD_SEGMENT_SET card
static std::string ld_generateLoadSegmentSet(int ssid, int lcid, double sf) {
    std::ostringstream ss;
    ss << "*LOAD_SEGMENT_SET\n";
    ss << "$#    ssid      lcid        sf        at\n";
    char buf[90];
    snprintf(buf, sizeof(buf), "%10d%10d%10.4f%10.1f", ssid, lcid, sf, 0.0);
    ss << buf << "\n";
    return ss.str();
}

// Find tied contacts involving a PID, return their segment set IDs
// foundPartBased: set true when contact uses SSTYP=3 (part ID, no segment set)
static std::vector<int> ld_findTiedContactSegSets(
        const std::vector<std::string>& rawLines,
        int pid, int contactId, bool& foundPartBased) {
    std::vector<int> ssids;
    foundPartBased = false;
    bool inContact = false;
    bool isTied = false;
    bool hasTitle = false;
    bool needTitle = false;
    int cardNum = 0;
    int ssid=0, msid=0, sstyp=0, mstyp=0;
    int contactCounter = 0;
    std::string contactTitle;

    auto processContact = [&]() {
        if (!isTied) return;
        bool matchSlave = false, matchMaster = false;
        if (contactId > 0) {
            if (contactCounter == contactId) { matchSlave = true; matchMaster = true; }
        } else {
            if (sstyp == 3 && ssid == pid) matchSlave = true;
            if (mstyp == 3 && msid == pid) matchMaster = true;
            // SSTYP=0: check title for PID reference (e.g. "AUTO_PID10_PID11")
            if (!matchSlave && !matchMaster && !contactTitle.empty()) {
                std::string pidStr = "PID" + std::to_string(pid);
                if (contactTitle.find(pidStr) != std::string::npos) {
                    matchSlave = true;
                    matchMaster = true;
                }
            }
        }
        if (matchSlave) {
            if (sstyp == 0 || sstyp == 2) ssids.push_back(ssid);
            else if (sstyp == 3) foundPartBased = true;
        }
        if (matchMaster) {
            if (mstyp == 0 || mstyp == 2) ssids.push_back(msid);
            else if (mstyp == 3) foundPartBased = true;
        }
    };

    for (int i = 0; i < (int)rawLines.size(); ++i) {
        const auto& line = rawLines[i];
        if (!line.empty() && line[0] == '*') {
            if (inContact) processContact();

            std::string up = line;
            for (auto& c : up) c = (char)std::toupper((unsigned char)c);
            if (up.find("*CONTACT_") == 0) {
                inContact = true;
                isTied = (up.find("TIED") != std::string::npos);
                hasTitle = (up.find("_TITLE") != std::string::npos ||
                            up.find("_ID") != std::string::npos);
                needTitle = hasTitle;
                cardNum = 0;
                ssid = msid = sstyp = mstyp = 0;
                contactCounter++;
                contactTitle.clear();
                continue;
            }
            inContact = false;
            continue;
        }
        if (!inContact) continue;
        if (!line.empty() && line[0] == '$') continue;
        if (needTitle) {
            contactTitle = line;
            // Trim
            while (!contactTitle.empty() && (contactTitle.back() == ' ' || contactTitle.back() == '\r'))
                contactTitle.pop_back();
            needTitle = false;
            continue;
        }
        cardNum++;
        if (cardNum == 1) {
            auto tok = [&](int start, int len) -> int {
                if (start >= (int)line.size()) return 0;
                std::string s = line.substr(start, std::min(len, (int)line.size()-start));
                try { return std::stoi(s); } catch(...) { return 0; }
            };
            ssid  = tok(0, 10);
            msid  = tok(10, 10);
            sstyp = tok(20, 10);
            mstyp = tok(30, 10);
        }
    }
    if (inContact) processContact();
    return ssids;
}

// Parse existing segment set faces from rawLines
static std::vector<std::array<int,4>> ld_parseSetSegmentFaces(
        const std::vector<std::string>& rawLines, int setId) {
    std::vector<std::array<int,4>> faces;
    bool inSet = false;
    bool needTitle = false;
    bool needData = true;
    bool foundHeader = false;
    for (const auto& line : rawLines) {
        if (!line.empty() && line[0] == '*') {
            std::string up = line;
            for (auto& c : up) c = (char)std::toupper((unsigned char)c);
            if (up.find("*SET_SEGMENT") == 0) {
                if (inSet && foundHeader) return faces;
                inSet = true;
                needTitle = (up.find("_TITLE") != std::string::npos);
                needData = true;
                foundHeader = false;
                continue;
            }
            if (inSet && foundHeader) return faces;
            inSet = false;
            continue;
        }
        if (!inSet) continue;
        if (!line.empty() && line[0] == '$') continue;
        if (needTitle) { needTitle = false; continue; }
        if (needData) {
            std::istringstream iss(line);
            int sid = 0;
            if (iss >> sid && sid == setId) foundHeader = true;
            needData = false;
            continue;
        }
        if (!foundHeader) { inSet = false; continue; }
        auto tok = [&](int start, int len) -> int {
            if (start >= (int)line.size()) return 0;
            std::string s = line.substr(start, std::min(len, (int)line.size()-start));
            try { return std::stoi(s); } catch(...) { return 0; }
        };
        int n1 = tok(0,10), n2 = tok(10,10), n3 = tok(20,10), n4 = tok(30,10);
        if (n1 > 0 && n2 > 0 && n3 > 0) {
            faces.push_back({n1, n2, n3, n4});
        }
    }
    return faces;
}

} // anonymous namespace

// ── applyLoad() main ────────────────────────────────────────
bool ModelAssembler::applyLoad(const LoadOperation& op) {
    if (op.loads.empty()) {
        std::cout << "[load] No load cases specified\n";
        return true;
    }

    int nextSetId = ld_findMaxSetSegmentId(rawLines_) + 1;
    int nextCurveId = ld_findMaxCurveId(rawLines_) + 1;
    std::vector<std::string> insertBlocks;
    int loadCount = 0;

    for (int li = 0; li < (int)op.loads.size(); ++li) {
        const auto& lc = op.loads[li];

        // 1. Resolve PID
        int pid = ld_resolvePid(rawLines_, lc.pid, lc.partName);
        if (pid <= 0) {
            std::cerr << "[load] ERROR: Cannot resolve part (pid=" << lc.pid
                      << ", name=" << lc.partName << ")\n";
            return false;
        }

        // 2. Direction vector validation
        double dir[3] = {lc.direction[0], lc.direction[1], lc.direction[2]};
        double dirMag = ld_mag(dir);
        bool hasDirection = (dirMag > 1e-30);

        if (lc.mode != "normal_pressure" && !hasDirection) {
            std::cerr << "[load] ERROR: direction required for mode '" << lc.mode << "'\n";
            return false;
        }

        // Normalize direction
        double udir[3] = {0,0,0};
        if (hasDirection) {
            udir[0] = dir[0]/dirMag;
            udir[1] = dir[1]/dirMag;
            udir[2] = dir[2]/dirMag;
        }

        // 3. Get segments based on select mode
        std::vector<std::array<int,4>> selectedFaces;
        std::vector<LdFaceInfo> selectedFaceInfos;
        int existingSetId = 0;

        if (lc.select == "set") {
            if (lc.setId <= 0) {
                std::cerr << "[load] ERROR: set_id required for select=set\n";
                return false;
            }
            existingSetId = lc.setId;
            if (lc.mode == "force") {
                selectedFaces = ld_parseSetSegmentFaces(rawLines_, lc.setId);
                selectedFaceInfos = ld_buildFaceInfo(selectedFaces, baseMesh_);
            }

        } else if (lc.select == "tied") {
            bool foundPartBased = false;
            auto ssids = ld_findTiedContactSegSets(rawLines_, pid, lc.contactId, foundPartBased);
            if (!ssids.empty()) {
                for (int sid : ssids) {
                    auto faces = ld_parseSetSegmentFaces(rawLines_, sid);
                    selectedFaces.insert(selectedFaces.end(), faces.begin(), faces.end());
                }
            }

            // Also scan addedKeywordBlocks_ for contacts created in same pipeline
            if (ssids.empty() && !foundPartBased && !addedKeywordBlocks_.empty()) {
                std::vector<std::string> extraLines;
                for (const auto& block : addedKeywordBlocks_) {
                    std::istringstream bss(block);
                    std::string bline;
                    while (std::getline(bss, bline)) extraLines.push_back(bline);
                }
                bool foundPartBased2 = false;
                auto ssids2 = ld_findTiedContactSegSets(extraLines, pid, lc.contactId, foundPartBased2);
                if (!ssids2.empty()) {
                    for (int sid : ssids2) {
                        auto faces = ld_parseSetSegmentFaces(extraLines, sid);
                        std::cerr << "[load] DEBUG: segment set " << sid << " has " << faces.size() << " faces\n";
                        selectedFaces.insert(selectedFaces.end(), faces.begin(), faces.end());
                    }
                } else if (foundPartBased2) {
                    foundPartBased = true;
                }
                if (!ssids2.empty()) ssids.insert(ssids.end(), ssids2.begin(), ssids2.end());
            }

            if (!ssids.empty()) {
                // Already collected faces above
            } else if (foundPartBased) {
                // Part-based tied (SSTYP=3): extract surface of this PID
                selectedFaces = ld_extractSurface(baseMesh_, pid);
            } else {
                std::cerr << "[load] WARNING: No tied contacts found for PID=" << pid
                          << ", extracting surface directly\n";
                selectedFaces = ld_extractSurface(baseMesh_, pid);
            }
            // Apply direction+angle filter on tied segments
            selectedFaceInfos = ld_buildFaceInfo(selectedFaces, baseMesh_);
            if (hasDirection) {
                auto indices = ld_filterByDirection(selectedFaceInfos, dir, lc.angle);
                if (indices.empty()) {
                    std::cerr << "[load] WARNING: No segments match direction filter for PID="
                              << pid << ", skipping\n";
                    continue;
                }
                std::vector<std::array<int,4>> filtered;
                std::vector<LdFaceInfo> filteredInfos;
                for (int idx : indices) {
                    filtered.push_back(selectedFaces[idx]);
                    filteredInfos.push_back(selectedFaceInfos[idx]);
                }
                selectedFaces = std::move(filtered);
                selectedFaceInfos = std::move(filteredInfos);
            }

        } else {
            // direction mode (default)
            auto allFaces = ld_extractSurface(baseMesh_, pid);
            if (allFaces.empty()) {
                std::cerr << "[load] WARNING: No surface faces found for PID=" << pid << "\n";
                continue;
            }
            auto allInfos = ld_buildFaceInfo(allFaces, baseMesh_);
            if (hasDirection) {
                auto indices = ld_filterByDirection(allInfos, dir, lc.angle);
                if (indices.empty()) {
                    std::cerr << "[load] WARNING: No segments match direction filter for PID="
                              << pid << ", skipping\n";
                    continue;
                }
                for (int idx : indices) {
                    selectedFaces.push_back(allFaces[idx]);
                    selectedFaceInfos.push_back(allInfos[idx]);
                }
            } else {
                // No direction (e.g. normal_pressure) → use all surface faces
                selectedFaces = std::move(allFaces);
                selectedFaceInfos = std::move(allInfos);
            }
        }

        // 4. Compute scale factor (SF)
        double sf = lc.value;

        if (lc.mode == "force") {
            if (selectedFaceInfos.empty()) {
                std::cerr << "[load] ERROR: No face info for force calculation (PID=" << pid << ")\n";
                return false;
            }
            double totalProjArea = 0.0;
            for (const auto& fi : selectedFaceInfos) {
                double dot = ld_dot(fi.normal, udir);
                totalProjArea += fi.area * std::abs(dot);
            }
            if (totalProjArea < 1e-30) {
                std::cerr << "[load] ERROR: Projected area is zero for PID=" << pid << "\n";
                return false;
            }
            sf = lc.value / totalProjArea;
            std::cout << "[load] Force mode: F=" << lc.value << " N, proj_area="
                      << totalProjArea << ", pressure=" << sf << " MPa\n";
        }

        // 5. Generate DEFINE_CURVE
        int lcid = nextCurveId++;
        std::vector<LoadCurvePoint> curveData = lc.curve;
        if (curveData.empty()) {
            curveData.push_back({0.0, 1.0});
            curveData.push_back({1.0e10, 1.0});
        }
        insertBlocks.push_back(ld_generateDefineCurve(lcid, curveData));

        // 6. Generate SET_SEGMENT (only if we need a new one)
        int ssid = existingSetId;
        if (ssid == 0) {
            ssid = nextSetId++;
            std::string title = "Load_PID" + std::to_string(pid) + "_" + lc.mode;
            insertBlocks.push_back(ld_generateSetSegment(ssid, selectedFaces, title));
        }

        // 7. Generate LOAD_SEGMENT_SET
        insertBlocks.push_back(ld_generateLoadSegmentSet(ssid, lcid, sf));
        loadCount++;

        std::cout << "[load] PID=" << pid << " mode=" << lc.mode
                  << " select=" << lc.select
                  << " segments=" << (existingSetId > 0 ? 0 : (int)selectedFaces.size())
                  << " SF=" << sf << "\n";
    }

    // 8. Insert all blocks before *END
    if (!insertBlocks.empty()) {
        std::vector<std::string> newLines;
        newLines.reserve(rawLines_.size() + insertBlocks.size() * 10);
        bool inserted = false;
        for (const auto& line : rawLines_) {
            std::string up = line;
            for (auto& c : up) c = (char)std::toupper((unsigned char)c);
            while (!up.empty() && (up.back() == ' ' || up.back() == '\r')) up.pop_back();
            if (!inserted && up == "*END") {
                for (const auto& block : insertBlocks) {
                    std::istringstream bs(block);
                    std::string bline;
                    while (std::getline(bs, bline)) {
                        newLines.push_back(bline);
                    }
                }
                inserted = true;
            }
            newLines.push_back(line);
        }
        if (!inserted) {
            for (const auto& block : insertBlocks) {
                std::istringstream bs(block);
                std::string bline;
                while (std::getline(bs, bline)) {
                    newLines.push_back(bline);
                }
            }
        }
        rawLines_ = std::move(newLines);
    }

    infoMessages.push_back("[load] Applied " + std::to_string(loadCount) + " load case(s)");
    return true;
}

// ============================================================================
// Contact assemble helpers
// ============================================================================
namespace {

struct CaFaceInfo {
    std::array<int,4> nodeIds;
    double verts[4][3];
    double normal[3];
    double area;
    double centroid[3];
    double radius;     // max distance from centroid to any vertex
    int nVerts;
    int pid;
    int sourceIndex;   // index in original faces vector
};

struct CaCellKey {
    int ix, iy, iz;
    bool operator==(const CaCellKey& o) const {
        return ix == o.ix && iy == o.iy && iz == o.iz;
    }
};

struct CaCellKeyHash {
    size_t operator()(const CaCellKey& k) const {
        size_t h = size_t(k.ix) * 73856093ULL;
        h ^= size_t(k.iy) * 19349663ULL;
        h ^= size_t(k.iz) * 83492791ULL;
        return h;
    }
};

struct CaContactPair {
    int pidA, pidB;
    int faceA, faceB;
    double gap;
};

// Build face info with radius/pid for contact detection
static std::vector<CaFaceInfo> ca_buildFaceInfo(
        const std::vector<std::array<int,4>>& faces,
        const KooRemapper::Mesh& mesh, int pid) {
    std::vector<CaFaceInfo> infos;
    infos.reserve(faces.size());
    for (int fi = 0; fi < (int)faces.size(); ++fi) {
        const auto& f = faces[fi];
        CaFaceInfo ci;
        ci.nodeIds = f;
        ci.pid = pid;
        ci.sourceIndex = fi;
        bool isTri = (f[3] == f[2] || f[3] == 0);
        ci.nVerts = isTri ? 3 : 4;

        bool valid = true;
        for (int k = 0; k < ci.nVerts; ++k) {
            const auto* nd = mesh.getNode(f[k]);
            if (!nd) { valid = false; break; }
            ci.verts[k][0] = nd->position.x;
            ci.verts[k][1] = nd->position.y;
            ci.verts[k][2] = nd->position.z;
        }
        if (!valid) continue;
        if (isTri) { ci.verts[3][0]=ci.verts[2][0]; ci.verts[3][1]=ci.verts[2][1]; ci.verts[3][2]=ci.verts[2][2]; }

        // Normal via diagonal cross product
        double d1[3] = {ci.verts[2][0]-ci.verts[0][0], ci.verts[2][1]-ci.verts[0][1], ci.verts[2][2]-ci.verts[0][2]};
        double d2[3] = {ci.verts[3][0]-ci.verts[1][0], ci.verts[3][1]-ci.verts[1][1], ci.verts[3][2]-ci.verts[1][2]};
        ci.normal[0] = d1[1]*d2[2] - d1[2]*d2[1];
        ci.normal[1] = d1[2]*d2[0] - d1[0]*d2[2];
        ci.normal[2] = d1[0]*d2[1] - d1[1]*d2[0];
        double mag = ld_mag(ci.normal);
        ci.area = mag * 0.5;
        if (mag > 1e-30) { ci.normal[0]/=mag; ci.normal[1]/=mag; ci.normal[2]/=mag; }
        if (ci.area < 1e-20) continue;

        // Centroid
        ci.centroid[0]=ci.centroid[1]=ci.centroid[2]=0;
        for (int k = 0; k < ci.nVerts; ++k) {
            ci.centroid[0]+=ci.verts[k][0]; ci.centroid[1]+=ci.verts[k][1]; ci.centroid[2]+=ci.verts[k][2];
        }
        ci.centroid[0]/=ci.nVerts; ci.centroid[1]/=ci.nVerts; ci.centroid[2]/=ci.nVerts;

        // Radius: max distance from centroid to any vertex
        ci.radius = 0;
        for (int k = 0; k < ci.nVerts; ++k) {
            double dx = ci.verts[k][0]-ci.centroid[0];
            double dy = ci.verts[k][1]-ci.centroid[1];
            double dz = ci.verts[k][2]-ci.centroid[2];
            double dist = std::sqrt(dx*dx+dy*dy+dz*dz);
            if (dist > ci.radius) ci.radius = dist;
        }
        infos.push_back(ci);
    }
    return infos;
}

static double ca_averageFaceSize(const std::vector<CaFaceInfo>& faces) {
    if (faces.empty()) return 1.0;
    double sum = 0;
    for (const auto& f : faces) sum += std::sqrt(f.area);
    return sum / faces.size();
}

// 4-stage narrow phase check (same algorithm as ct_narrowPhaseCheck)
static bool ca_narrowPhaseCheck(
        const CaFaceInfo& fA, const CaFaceInfo& fB,
        double gapTol, double cosThresh, double& gapOut) {
    // Stage 1: centroid distance pre-filter
    double dx=fA.centroid[0]-fB.centroid[0], dy=fA.centroid[1]-fB.centroid[1], dz=fA.centroid[2]-fB.centroid[2];
    double centDist = std::sqrt(dx*dx+dy*dy+dz*dz);
    if (centDist > fA.radius + fB.radius + gapTol) return false;

    // Stage 2: normal parallelism
    double absDot = std::abs(ld_dot(fA.normal, fB.normal));
    if (absDot < cosThresh) return false;

    // Stage 3: bilateral vertex-to-plane projection
    double minGap = 1e30;
    // A → B plane
    for (int k = 0; k < fA.nVerts; ++k) {
        double diff[3] = {fA.verts[k][0]-fB.centroid[0], fA.verts[k][1]-fB.centroid[1], fA.verts[k][2]-fB.centroid[2]};
        double gap_k = std::abs(ld_dot(diff, fB.normal));
        double dotN = ld_dot(diff, fB.normal);
        double px = fA.verts[k][0] - fB.normal[0]*dotN;
        double py = fA.verts[k][1] - fB.normal[1]*dotN;
        double pz = fA.verts[k][2] - fB.normal[2]*dotN;
        double pdx=px-fB.centroid[0], pdy=py-fB.centroid[1], pdz=pz-fB.centroid[2];
        double projDist = std::sqrt(pdx*pdx+pdy*pdy+pdz*pdz);
        if (projDist < fB.radius + gapTol) {
            if (gap_k < minGap) minGap = gap_k;
        }
    }
    // B → A plane
    for (int k = 0; k < fB.nVerts; ++k) {
        double diff[3] = {fB.verts[k][0]-fA.centroid[0], fB.verts[k][1]-fA.centroid[1], fB.verts[k][2]-fA.centroid[2]};
        double gap_k = std::abs(ld_dot(diff, fA.normal));
        double dotN = ld_dot(diff, fA.normal);
        double px = fB.verts[k][0] - fA.normal[0]*dotN;
        double py = fB.verts[k][1] - fA.normal[1]*dotN;
        double pz = fB.verts[k][2] - fA.normal[2]*dotN;
        double pdx=px-fA.centroid[0], pdy=py-fA.centroid[1], pdz=pz-fA.centroid[2];
        double projDist = std::sqrt(pdx*pdx+pdy*pdy+pdz*pdz);
        if (projDist < fA.radius + gapTol) {
            if (gap_k < minGap) minGap = gap_k;
        }
    }
    if (minGap > gapTol) return false;
    gapOut = minGap;
    return true;
}

// Detect contacting faces between two parts using spatial hash grid
static std::vector<CaContactPair> ca_detectContacting(
        const std::vector<std::array<int,4>>& facesA,
        const std::vector<std::array<int,4>>& facesB,
        const KooRemapper::Mesh& mesh,
        int pidA, int pidB,
        double gapTolerance, double normalAngleDeg) {
    auto infoA = ca_buildFaceInfo(facesA, mesh, pidA);
    auto infoB = ca_buildFaceInfo(facesB, mesh, pidB);
    if (infoA.empty() || infoB.empty()) return {};

    double avgSize = (ca_averageFaceSize(infoA) + ca_averageFaceSize(infoB)) * 0.5;
    double cellSize = std::max(avgSize, gapTolerance * 2.0);
    cellSize = std::max(cellSize, 1e-10);
    double cosThresh = std::cos(normalAngleDeg * 3.14159265358979323846 / 180.0);

    // Build grid from B (master)
    std::unordered_map<CaCellKey, std::vector<int>, CaCellKeyHash> grid;
    for (int j = 0; j < (int)infoB.size(); ++j) {
        const auto& fi = infoB[j];
        double minX=fi.verts[0][0], maxX=minX, minY=fi.verts[0][1], maxY=minY, minZ=fi.verts[0][2], maxZ=minZ;
        for (int k=1; k<fi.nVerts; ++k) {
            if (fi.verts[k][0]<minX) minX=fi.verts[k][0]; if (fi.verts[k][0]>maxX) maxX=fi.verts[k][0];
            if (fi.verts[k][1]<minY) minY=fi.verts[k][1]; if (fi.verts[k][1]>maxY) maxY=fi.verts[k][1];
            if (fi.verts[k][2]<minZ) minZ=fi.verts[k][2]; if (fi.verts[k][2]>maxZ) maxZ=fi.verts[k][2];
        }
        int ixMin=(int)std::floor(minX/cellSize), ixMax=(int)std::floor(maxX/cellSize);
        int iyMin=(int)std::floor(minY/cellSize), iyMax=(int)std::floor(maxY/cellSize);
        int izMin=(int)std::floor(minZ/cellSize), izMax=(int)std::floor(maxZ/cellSize);
        for (int ix=ixMin; ix<=ixMax; ++ix)
            for (int iy=iyMin; iy<=iyMax; ++iy)
                for (int iz=izMin; iz<=izMax; ++iz)
                    grid[{ix,iy,iz}].push_back(j);
    }

    // Query with A (slave)
    std::set<std::pair<int,int>> candidates;
    for (int i = 0; i < (int)infoA.size(); ++i) {
        const auto& fi = infoA[i];
        double minX=fi.verts[0][0], maxX=minX, minY=fi.verts[0][1], maxY=minY, minZ=fi.verts[0][2], maxZ=minZ;
        for (int k=1; k<fi.nVerts; ++k) {
            if (fi.verts[k][0]<minX) minX=fi.verts[k][0]; if (fi.verts[k][0]>maxX) maxX=fi.verts[k][0];
            if (fi.verts[k][1]<minY) minY=fi.verts[k][1]; if (fi.verts[k][1]>maxY) maxY=fi.verts[k][1];
            if (fi.verts[k][2]<minZ) minZ=fi.verts[k][2]; if (fi.verts[k][2]>maxZ) maxZ=fi.verts[k][2];
        }
        int ixMin=(int)std::floor(minX/cellSize)-1, ixMax=(int)std::floor(maxX/cellSize)+1;
        int iyMin=(int)std::floor(minY/cellSize)-1, iyMax=(int)std::floor(maxY/cellSize)+1;
        int izMin=(int)std::floor(minZ/cellSize)-1, izMax=(int)std::floor(maxZ/cellSize)+1;
        for (int ix=ixMin; ix<=ixMax; ++ix)
            for (int iy=iyMin; iy<=iyMax; ++iy)
                for (int iz=izMin; iz<=izMax; ++iz) {
                    auto it = grid.find({ix,iy,iz});
                    if (it == grid.end()) continue;
                    for (int j : it->second) candidates.insert({i,j});
                }
    }

    // Narrow phase
    std::vector<CaContactPair> results;
    for (const auto& [i, j] : candidates) {
        double gap;
        if (ca_narrowPhaseCheck(infoA[i], infoB[j], gapTolerance, cosThresh, gap)) {
            results.push_back({pidA, pidB, infoA[i].sourceIndex, infoB[j].sourceIndex, gap});
        }
    }
    return results;
}

// Get LS-DYNA contact keyword from preset name
static std::string ca_getContactKeyword(const std::string& type) {
    std::string t = type;
    for (auto& c : t) c = (char)std::tolower((unsigned char)c);
    if (t == "auto" || t == "automatic" || t.empty()) return "AUTOMATIC_SURFACE_TO_SURFACE";
    if (t == "tied") return "TIED_SURFACE_TO_SURFACE";
    if (t == "mortar") return "AUTOMATIC_SURFACE_TO_SURFACE_MORTAR";
    if (t == "tied_mortar") return "TIED_SURFACE_TO_SURFACE_MORTAR";
    if (t == "single") return "AUTOMATIC_SINGLE_SURFACE";
    if (t == "eroding") return "ERODING_SURFACE_TO_SURFACE";
    if (t == "forming") return "FORMING_SURFACE_TO_SURFACE";
    // Custom: uppercase as-is
    std::string upper = type;
    for (auto& c : upper) c = (char)std::toupper((unsigned char)c);
    return upper;
}

// Generate *CONTACT card (Cards 1-3 only, no optional cards)
static std::string ca_generateContact(const std::string& contactType,
        const std::string& title,
        int ssid, int msid, int sstyp, int mstyp,
        double friction) {
    std::ostringstream ss;
    std::string kw = "*CONTACT_" + contactType;
    if (!title.empty()) kw += "_TITLE";
    ss << kw << "\n";
    if (!title.empty()) ss << title << "\n";

    char buf[90];
    // Card 1
    ss << "$#    ssid      msid     sstyp     mstyp    sboxid    mboxid       spr       mpr\n";
    snprintf(buf, sizeof(buf), "%10d%10d%10d%10d%10d%10d%10d%10d",
             ssid, msid, sstyp, mstyp, 0, 0, 0, 0);
    ss << buf << "\n";
    // Card 2
    double fs = (friction >= 0) ? friction : 0.0;
    ss << "$#      fs        fd        dc        vc       vdc    penchk        bt        dt\n";
    snprintf(buf, sizeof(buf), "%10.2f%10.2f%10.2f%10.2f%10.2f%10d%10.2f%10.3E",
             fs, 0.0, 0.0, 0.0, 0.0, 0, 0.0, 1.0e20);
    ss << buf << "\n";
    // Card 3
    ss << "$#    sfsa      sfsb      sast      sbst     sfsat     sfsbt       fsf       vsf\n";
    snprintf(buf, sizeof(buf), "%10.2f%10.2f%10.2f%10.2f%10.2f%10.2f%10.2f%10.2f",
             1.0, 1.0, 0.0, 0.0, 1.0, 1.0, 0.0, 0.0);
    ss << buf << "\n";
    return ss.str();
}

// Get all part PIDs and titles from rawLines
static std::vector<std::pair<int, std::string>> ca_getPartList(
        const std::vector<std::string>& rawLines) {
    std::vector<std::pair<int, std::string>> parts;
    for (int i = 0; i < (int)rawLines.size(); ++i) {
        const auto& line = rawLines[i];
        if (line.empty() || line[0] != '*') continue;
        std::string up = line;
        for (auto& c : up) c = (char)std::toupper((unsigned char)c);
        if (up.find("*PART") != 0) continue;
        if (up.find("*PART_CONTACT") == 0) continue;
        // Find title and data lines
        std::string title;
        int pid = 0;
        for (int j = i + 1; j < (int)rawLines.size() && j < i + 10; ++j) {
            const auto& dl = rawLines[j];
            if (dl.empty()) continue;
            if (dl[0] == '*') break;
            if (dl[0] == '$') continue;
            if (title.empty()) {
                title = dl;
                // trim
                size_t start = title.find_first_not_of(" \t\r\n");
                size_t end = title.find_last_not_of(" \t\r\n");
                if (start != std::string::npos) title = title.substr(start, end - start + 1);
                else title.clear();
                continue;
            }
            // Data line: PID is first field
            try { pid = std::stoi(dl.substr(0, 10)); } catch(...) {}
            break;
        }
        if (pid > 0) parts.push_back({pid, title});
    }
    return parts;
}

// Filter PIDs by include/exclude keywords (case-insensitive substring match)
static std::vector<int> ca_filterPids(
        const std::vector<std::pair<int, std::string>>& partList,
        const std::vector<std::string>& includeKeys,
        const std::vector<std::string>& excludeKeys) {
    std::vector<int> result;
    for (const auto& [pid, title] : partList) {
        std::string upTitle = title;
        for (auto& c : upTitle) c = (char)std::tolower((unsigned char)c);

        // Check include (if specified, at least one must match)
        if (!includeKeys.empty()) {
            bool found = false;
            for (const auto& key : includeKeys) {
                std::string lowKey = key;
                for (auto& c : lowKey) c = (char)std::tolower((unsigned char)c);
                if (upTitle.find(lowKey) != std::string::npos) { found = true; break; }
            }
            if (!found) continue;
        }
        // Check exclude (if any matches, skip)
        bool excluded = false;
        for (const auto& key : excludeKeys) {
            std::string lowKey = key;
            for (auto& c : lowKey) c = (char)std::tolower((unsigned char)c);
            if (upTitle.find(lowKey) != std::string::npos) { excluded = true; break; }
        }
        if (excluded) continue;
        result.push_back(pid);
    }
    return result;
}

// Check if a PID pair already has a contact (lightweight rawLines scan)
static bool ca_pairHasExistingContact(
        const std::vector<std::string>& rawLines,
        int pidA, int pidB, const std::string& mode) {
    bool inContact = false;
    bool isTied = false;
    bool hasTitle = false;
    bool needTitle = false;
    int cardNum = 0;
    int ssid=0, msid=0, sstyp=0, mstyp=0;

    auto checkPair = [&]() -> bool {
        if (!inContact) return false;
        if (mode == "tied" && !isTied) return false;
        // SSTYP=3: direct PID match
        if (sstyp == 3 && mstyp == 3) {
            if ((ssid == pidA && msid == pidB) || (ssid == pidB && msid == pidA))
                return true;
        }
        return false;
    };

    for (int i = 0; i < (int)rawLines.size(); ++i) {
        const auto& line = rawLines[i];
        if (!line.empty() && line[0] == '*') {
            if (inContact && checkPair()) return true;
            std::string up = line;
            for (auto& c : up) c = (char)std::toupper((unsigned char)c);
            if (up.find("*CONTACT_") == 0) {
                inContact = true;
                isTied = (up.find("TIED") != std::string::npos);
                hasTitle = (up.find("_TITLE") != std::string::npos || up.find("_ID") != std::string::npos);
                needTitle = hasTitle;
                cardNum = 0;
                ssid = msid = sstyp = mstyp = 0;
                continue;
            }
            inContact = false;
            continue;
        }
        if (!inContact) continue;
        if (!line.empty() && line[0] == '$') continue;
        if (needTitle) { needTitle = false; continue; }
        cardNum++;
        if (cardNum == 1) {
            auto tok = [&](int start, int len) -> int {
                if (start >= (int)line.size()) return 0;
                std::string s = line.substr(start, std::min(len, (int)line.size()-start));
                try { return std::stoi(s); } catch(...) { return 0; }
            };
            ssid = tok(0, 10); msid = tok(10, 10);
            sstyp = tok(20, 10); mstyp = tok(30, 10);
        }
    }
    if (inContact && checkPair()) return true;
    return false;
}

// Subtract tied faces from detected faces
static std::vector<std::array<int,4>> ca_subtractFaces(
        const std::vector<std::array<int,4>>& allFaces,
        const std::vector<std::array<int,4>>& tiedFaces) {
    std::set<std::array<int,4>> tiedSet;
    for (const auto& f : tiedFaces) {
        auto key = f; std::sort(key.begin(), key.end());
        tiedSet.insert(key);
    }
    std::vector<std::array<int,4>> result;
    for (const auto& f : allFaces) {
        auto key = f; std::sort(key.begin(), key.end());
        if (!tiedSet.count(key)) result.push_back(f);
    }
    return result;
}

} // anonymous namespace

// ============================================================================
// applyContact
// ============================================================================
bool ModelAssembler::applyContact(const ContactOperation& op) {
    if (op.actions.empty()) {
        std::cout << "[contact] No contact actions specified\n";
        return true;
    }

    int nextSetId = ld_findMaxSetSegmentId(rawLines_) + 1;
    std::vector<std::string> insertBlocks;
    int contactCount = 0;

    for (int ai = 0; ai < (int)op.actions.size(); ++ai) {
        const auto& act = op.actions[ai];

        if (act.action == "create") {
            // --- CREATE ---
            std::string contactKw = ca_getContactKeyword(act.type);
            int ssid = 0, msid = 0, sstyp = 0, mstyp = 0;

            // Resolve slave side
            std::vector<int> slavePids;
            if (act.slave.pid > 0) slavePids.push_back(act.slave.pid);
            if (!act.slave.pids.empty()) slavePids = act.slave.pids;

            // Resolve master side
            std::vector<int> masterPids;
            if (act.master.pid > 0) masterPids.push_back(act.master.pid);
            if (!act.master.pids.empty()) masterPids = act.master.pids;

            bool useFacing = (act.slave.facing && act.master.facing &&
                              slavePids.size() == 1 && masterPids.size() == 1);

            if (useFacing && act.slave.asSegment && act.master.asSegment) {
                // Facing filter: extract surfaces, detect contacting, keep only facing faces
                auto sFacesAll = ld_extractSurface(baseMesh_, slavePids[0]);
                auto mFacesAll = ld_extractSurface(baseMesh_, masterPids[0]);
                if (sFacesAll.empty() || mFacesAll.empty()) {
                    std::cerr << "[contact] WARNING: No surface for facing filter (slave:"
                              << slavePids[0] << " master:" << masterPids[0] << ")\n";
                } else {
                    auto pairs = ca_detectContacting(sFacesAll, mFacesAll, baseMesh_,
                        slavePids[0], masterPids[0], act.tolerance, act.normalAngle);
                    if (pairs.empty()) {
                        std::cerr << "[contact] WARNING: No facing segments between PID "
                                  << slavePids[0] << " and PID " << masterPids[0] << "\n";
                    } else {
                        std::set<int> sIdxSet, mIdxSet;
                        for (const auto& p : pairs) { sIdxSet.insert(p.faceA); mIdxSet.insert(p.faceB); }
                        std::vector<std::array<int,4>> sFaces, mFaces;
                        for (int idx : sIdxSet) sFaces.push_back(sFacesAll[idx]);
                        for (int idx : mIdxSet) mFaces.push_back(mFacesAll[idx]);

                        ssid = nextSetId++;
                        insertBlocks.push_back(ld_generateSetSegment(ssid, sFaces,
                            "Slave_PID" + std::to_string(slavePids[0]) + "_facing"));
                        sstyp = 0;
                        msid = nextSetId++;
                        insertBlocks.push_back(ld_generateSetSegment(msid, mFaces,
                            "Master_PID" + std::to_string(masterPids[0]) + "_facing"));
                        mstyp = 0;
                    }
                }
            } else if (act.slave.asSegment || act.master.asSegment) {
                // Extract surface for sides requesting as_segment
                if (act.slave.asSegment && !slavePids.empty()) {
                    std::vector<std::array<int,4>> allFaces;
                    for (int pid : slavePids) {
                        auto f = ld_extractSurface(baseMesh_, pid);
                        allFaces.insert(allFaces.end(), f.begin(), f.end());
                    }
                    ssid = nextSetId++;
                    insertBlocks.push_back(ld_generateSetSegment(ssid, allFaces,
                        "Slave_PID" + std::to_string(slavePids[0])));
                    sstyp = 0;
                } else if (!slavePids.empty()) {
                    ssid = slavePids[0]; sstyp = 3;
                }
                if (act.master.asSegment && !masterPids.empty()) {
                    std::vector<std::array<int,4>> allFaces;
                    for (int pid : masterPids) {
                        auto f = ld_extractSurface(baseMesh_, pid);
                        allFaces.insert(allFaces.end(), f.begin(), f.end());
                    }
                    msid = nextSetId++;
                    insertBlocks.push_back(ld_generateSetSegment(msid, allFaces,
                        "Master_PID" + std::to_string(masterPids[0])));
                    mstyp = 0;
                } else if (!masterPids.empty()) {
                    msid = masterPids[0]; mstyp = 3;
                }
            } else {
                // Direct PID reference (SSTYP=3)
                if (!slavePids.empty()) { ssid = slavePids[0]; sstyp = 3; }
                if (!masterPids.empty()) { msid = masterPids[0]; mstyp = 3; }
            }

            if (ssid > 0) {
                std::string title = act.title;
                if (title.empty() && !slavePids.empty() && !masterPids.empty()) {
                    title = "PID" + std::to_string(slavePids[0]) + "_to_PID" + std::to_string(masterPids[0]);
                }
                insertBlocks.push_back(ca_generateContact(contactKw, title,
                    ssid, msid, sstyp, mstyp, act.friction));
                contactCount++;
                std::cout << "[contact] Created " << contactKw
                          << " (slave=" << ssid << " master=" << msid << ")\n";
            }

        } else if (act.action == "detect") {
            // --- DETECT ---
            auto partList = ca_getPartList(rawLines_);
            std::vector<int> targetPids;

            if (act.scope == "all") {
                // All parts
                for (const auto& [pid, title] : partList) targetPids.push_back(pid);
            } else if (!act.includeKeys.empty() || !act.excludeKeys.empty()) {
                targetPids = ca_filterPids(partList, act.includeKeys, act.excludeKeys);
            } else if (act.slave.pid > 0 && act.master.pid > 0) {
                // Explicit pair mode
                auto sFaces = ld_extractSurface(baseMesh_, act.slave.pid);
                auto mFaces = ld_extractSurface(baseMesh_, act.master.pid);
                auto pairs = ca_detectContacting(sFaces, mFaces, baseMesh_,
                    act.slave.pid, act.master.pid, act.tolerance, act.normalAngle);
                std::cout << "[contact] Detected " << pairs.size() << " facing pairs between PID "
                          << act.slave.pid << " and PID " << act.master.pid << "\n";
                if (act.autoCreate && !pairs.empty()) {
                    std::set<int> sIdxSet, mIdxSet;
                    for (const auto& p : pairs) { sIdxSet.insert(p.faceA); mIdxSet.insert(p.faceB); }
                    std::vector<std::array<int,4>> sf, mf;
                    for (int idx : sIdxSet) sf.push_back(sFaces[idx]);
                    for (int idx : mIdxSet) mf.push_back(mFaces[idx]);

                    int sid1 = nextSetId++;
                    insertBlocks.push_back(ld_generateSetSegment(sid1, sf,
                        "Detect_Slave_PID" + std::to_string(act.slave.pid)));
                    int sid2 = nextSetId++;
                    insertBlocks.push_back(ld_generateSetSegment(sid2, mf,
                        "Detect_Master_PID" + std::to_string(act.master.pid)));

                    std::string contactKw = ca_getContactKeyword(act.type);
                    std::string title = act.titlePrefix.empty() ? "" :
                        act.titlePrefix + "_PID" + std::to_string(act.slave.pid) +
                        "_PID" + std::to_string(act.master.pid);
                    insertBlocks.push_back(ca_generateContact(contactKw, title,
                        sid1, sid2, 0, 0, act.friction));
                    contactCount++;
                }
                continue;
            } else {
                std::cerr << "[contact] ERROR: detect needs scope, include/exclude, or slave+master PIDs\n";
                return false;
            }

            if (targetPids.size() < 2) {
                std::cerr << "[contact] WARNING: Less than 2 parts for detection, skipping\n";
                continue;
            }

            // Extract surfaces for all target PIDs
            std::map<int, std::vector<std::array<int,4>>> pidFaces;
            for (int pid : targetPids) {
                auto faces = ld_extractSurface(baseMesh_, pid);
                if (!faces.empty()) pidFaces[pid] = std::move(faces);
            }

            // All-pairs detection
            int detectedPairs = 0;
            std::vector<int> pids;
            for (const auto& [pid, faces] : pidFaces) pids.push_back(pid);

            for (int i = 0; i < (int)pids.size(); ++i) {
                for (int j = i + 1; j < (int)pids.size(); ++j) {
                    int pidA = pids[i], pidB = pids[j];

                    // Skip existing check
                    if (!act.skipExisting.empty()) {
                        if (ca_pairHasExistingContact(rawLines_, pidA, pidB, act.skipExisting))
                            continue;
                    }

                    auto pairs = ca_detectContacting(pidFaces[pidA], pidFaces[pidB],
                        baseMesh_, pidA, pidB, act.tolerance, act.normalAngle);
                    if (pairs.empty()) continue;

                    detectedPairs++;
                    std::set<int> sIdxSet, mIdxSet;
                    for (const auto& p : pairs) { sIdxSet.insert(p.faceA); mIdxSet.insert(p.faceB); }
                    std::vector<std::array<int,4>> sf, mf;
                    for (int idx : sIdxSet) sf.push_back(pidFaces[pidA][idx]);
                    for (int idx : mIdxSet) mf.push_back(pidFaces[pidB][idx]);

                    // Subtract existing tied faces if requested
                    if (act.subtractExisting && !sf.empty()) {
                        // TODO: parse existing tied segment sets for this pair
                        // For now, skip subtraction in assemble mode
                    }

                    std::cout << "[contact] Detected PID " << pidA << " <-> PID " << pidB
                              << " (" << sf.size() << "+" << mf.size() << " segments)\n";

                    if (act.autoCreate) {
                        int sid1 = nextSetId++;
                        insertBlocks.push_back(ld_generateSetSegment(sid1, sf,
                            "Detect_Slave_PID" + std::to_string(pidA)));
                        int sid2 = nextSetId++;
                        insertBlocks.push_back(ld_generateSetSegment(sid2, mf,
                            "Detect_Master_PID" + std::to_string(pidB)));

                        std::string contactKw = ca_getContactKeyword(act.type);
                        std::string title;
                        if (!act.titlePrefix.empty())
                            title = act.titlePrefix + "_PID" + std::to_string(pidA) + "_PID" + std::to_string(pidB);
                        insertBlocks.push_back(ca_generateContact(contactKw, title,
                            sid1, sid2, 0, 0, act.friction));
                        contactCount++;
                    }
                }
            }
            std::cout << "[contact] Detected " << detectedPairs << " contacting pairs from "
                      << pids.size() << " parts\n";

        } else {
            std::cerr << "[contact] ERROR: Unknown action '" << act.action
                      << "' (assemble supports: create, detect)\n";
            return false;
        }
    }

    // Insert all blocks before *END
    if (!insertBlocks.empty()) {
        std::vector<std::string> newLines;
        newLines.reserve(rawLines_.size() + insertBlocks.size() * 20);
        for (const auto& line : rawLines_) {
            std::string up = line;
            for (auto& c : up) c = (char)std::toupper((unsigned char)c);
            if (up.find("*END") == 0) {
                for (const auto& block : insertBlocks) {
                    std::istringstream bs(block);
                    std::string bline;
                    while (std::getline(bs, bline)) newLines.push_back(bline);
                }
            }
            newLines.push_back(line);
        }
        rawLines_ = std::move(newLines);
    }

    infoMessages.push_back("[contact] Applied " + std::to_string(contactCount) + " contact(s)");
    return true;
}

// ═══════════════════════════════════════════════════════════
//  Boundary (SPC) helpers  — bc_ prefix
// ═══════════════════════════════════════════════════════════
namespace {

// Resolve DOF preset string → 6 DOF values
static void bc_resolveDof(const BoundaryCase& bc, int dof[6]) {
    std::string d = bc.dof;
    for (auto& c : d) c = (char)std::tolower((unsigned char)c);
    if      (d == "all")     { dof[0]=1; dof[1]=1; dof[2]=1; dof[3]=1; dof[4]=1; dof[5]=1; }
    else if (d == "xyz")     { dof[0]=1; dof[1]=1; dof[2]=1; dof[3]=0; dof[4]=0; dof[5]=0; }
    else if (d == "x")       { dof[0]=1; dof[1]=0; dof[2]=0; dof[3]=0; dof[4]=0; dof[5]=0; }
    else if (d == "y")       { dof[0]=0; dof[1]=1; dof[2]=0; dof[3]=0; dof[4]=0; dof[5]=0; }
    else if (d == "z")       { dof[0]=0; dof[1]=0; dof[2]=1; dof[3]=0; dof[4]=0; dof[5]=0; }
    else if (d == "xy")      { dof[0]=1; dof[1]=1; dof[2]=0; dof[3]=0; dof[4]=0; dof[5]=0; }
    else if (d == "xz")      { dof[0]=1; dof[1]=0; dof[2]=1; dof[3]=0; dof[4]=0; dof[5]=0; }
    else if (d == "yz")      { dof[0]=0; dof[1]=1; dof[2]=1; dof[3]=0; dof[4]=0; dof[5]=0; }
    else if (d == "rx")      { dof[0]=0; dof[1]=0; dof[2]=0; dof[3]=1; dof[4]=0; dof[5]=0; }
    else if (d == "ry")      { dof[0]=0; dof[1]=0; dof[2]=0; dof[3]=0; dof[4]=1; dof[5]=0; }
    else if (d == "rz")      { dof[0]=0; dof[1]=0; dof[2]=0; dof[3]=0; dof[4]=0; dof[5]=1; }
    else if (d == "custom")  { dof[0]=bc.dofx; dof[1]=bc.dofy; dof[2]=bc.dofz;
                               dof[3]=bc.dofrx; dof[4]=bc.dofry; dof[5]=bc.dofrz; }
    else                     { dof[0]=1; dof[1]=1; dof[2]=1; dof[3]=1; dof[4]=1; dof[5]=1; }
}

// Collect unique node IDs from face quads
static std::vector<int> bc_collectNodes(const std::vector<std::array<int,4>>& faces) {
    std::set<int> nodeSet;
    for (const auto& f : faces) {
        for (int i = 0; i < 4; ++i) {
            if (f[i] > 0) nodeSet.insert(f[i]);
        }
    }
    return std::vector<int>(nodeSet.begin(), nodeSet.end());
}

// Find max existing *SET_NODE ID in rawLines
static int bc_findMaxSetNodeId(const std::vector<std::string>& rawLines) {
    int maxId = 0;
    bool inSetNode = false;
    bool needData = true;
    bool needTitle = false;
    for (const auto& line : rawLines) {
        if (!line.empty() && line[0] == '*') {
            std::string up = line;
            for (auto& c : up) c = (char)std::toupper((unsigned char)c);
            if (up.find("*SET_NODE") == 0) {
                inSetNode = true;
                needTitle = (up.find("_TITLE") != std::string::npos);
                needData = true;
                continue;
            }
            inSetNode = false;
            continue;
        }
        if (!inSetNode) continue;
        if (!line.empty() && line[0] == '$') continue;
        if (needTitle) { needTitle = false; continue; }
        if (needData) {
            std::istringstream iss(line);
            int sid = 0;
            if (iss >> sid && sid > maxId) maxId = sid;
            needData = false;
            inSetNode = false;
            continue;
        }
    }
    return maxId;
}

// Generate *SET_NODE_LIST_TITLE card
static std::string bc_generateSetNode(int sid, const std::vector<int>& nodeIds,
        const std::string& title = "") {
    std::ostringstream ss;
    if (title.empty())
        ss << "*SET_NODE_LIST\n";
    else
        ss << "*SET_NODE_LIST_TITLE\n" << title << "\n";
    char buf[90];
    snprintf(buf, sizeof(buf), "%10d", sid);
    ss << "$#     sid\n" << buf << "\n";
    ss << "$#    nid1      nid2      nid3      nid4      nid5      nid6      nid7      nid8\n";
    for (int i = 0; i < (int)nodeIds.size(); i += 8) {
        for (int j = i; j < std::min(i + 8, (int)nodeIds.size()); ++j) {
            snprintf(buf, sizeof(buf), "%10d", nodeIds[j]);
            ss << buf;
        }
        ss << "\n";
    }
    return ss.str();
}

// Generate *BOUNDARY_SPC_SET card
static std::string bc_generateSpcSet(int nsid, const int dof[6]) {
    std::ostringstream ss;
    ss << "*BOUNDARY_SPC_SET\n";
    ss << "$#  NSID/NID       CID      DOFX      DOFY      DOFZ     DOFRX     DOFRY     DOFRZ\n";
    char buf[90];
    snprintf(buf, sizeof(buf), "%10d%10d%10d%10d%10d%10d%10d%10d",
             nsid, 0, dof[0], dof[1], dof[2], dof[3], dof[4], dof[5]);
    ss << buf << "\n";
    return ss.str();
}

} // anonymous namespace

// ── applyBoundary() main ────────────────────────────────────────
bool ModelAssembler::applyBoundary(const BoundaryOperation& op) {
    if (op.boundaries.empty()) {
        std::cout << "[boundary] No boundary cases specified\n";
        return true;
    }

    int maxSetNodeId = bc_findMaxSetNodeId(rawLines_);
    int nextSetId = maxSetNodeId + 1;
    std::vector<std::string> insertBlocks;
    int bcCount = 0;

    for (const auto& bc : op.boundaries) {
        int pid = ld_resolvePid(rawLines_, bc.pid, bc.partName);
        if (pid <= 0) {
            std::cerr << "[boundary] ERROR: Cannot resolve part (pid="
                      << bc.pid << " name='" << bc.partName << "')\n";
            return false;
        }

        // Direction vector
        double dir[3] = {bc.direction[0], bc.direction[1], bc.direction[2]};
        double dirMag = ld_mag(dir);
        bool hasDirection = (dirMag > 1e-30);
        if (hasDirection) {
            dir[0] /= dirMag; dir[1] /= dirMag; dir[2] /= dirMag;
        }

        std::vector<int> nodeIds;
        int usedSetId = 0;

        if (bc.select == "set") {
            if (bc.setId <= 0) {
                std::cerr << "[boundary] ERROR: set_id required for select=set\n";
                return false;
            }
            usedSetId = bc.setId;

        } else {
            // direction mode (default)
            auto allFaces = ld_extractSurface(baseMesh_, pid);
            if (allFaces.empty()) {
                std::cerr << "[boundary] WARNING: No surface faces for PID=" << pid << ", skipping\n";
                continue;
            }
            std::vector<std::array<int,4>> selectedFaces;
            if (hasDirection) {
                auto faceInfos = ld_buildFaceInfo(allFaces, baseMesh_);
                auto indices = ld_filterByDirection(faceInfos, dir, bc.angle);
                if (indices.empty()) {
                    std::cerr << "[boundary] WARNING: No faces match direction filter for PID="
                              << pid << ", skipping\n";
                    continue;
                }
                for (int idx : indices) selectedFaces.push_back(allFaces[idx]);
            } else {
                selectedFaces = std::move(allFaces);
            }
            nodeIds = bc_collectNodes(selectedFaces);
            if (nodeIds.empty()) {
                std::cerr << "[boundary] WARNING: No nodes collected for PID=" << pid << ", skipping\n";
                continue;
            }

            // Generate SET_NODE
            usedSetId = nextSetId++;
            std::string title = "BC_PID" + std::to_string(pid) + "_" + bc.dof;
            insertBlocks.push_back(bc_generateSetNode(usedSetId, nodeIds, title));
        }

        // Resolve DOF
        int dof[6] = {};
        bc_resolveDof(bc, dof);

        // Generate SPC
        insertBlocks.push_back(bc_generateSpcSet(usedSetId, dof));
        bcCount++;

        int nodeCount = bc.select == "set" ? 0 : (int)nodeIds.size();
        std::cout << "[boundary] PID=" << pid << " dof=" << bc.dof
                  << " select=" << bc.select << " nodes=" << nodeCount << "\n";
    }

    // Insert before *END
    if (!insertBlocks.empty()) {
        std::vector<std::string> newLines;
        newLines.reserve(rawLines_.size() + insertBlocks.size() * 10);
        for (const auto& line : rawLines_) {
            std::string up = line;
            for (auto& c : up) c = (char)std::toupper((unsigned char)c);
            if (up.find("*END") == 0) {
                for (const auto& block : insertBlocks) {
                    std::istringstream bs(block);
                    std::string bline;
                    while (std::getline(bs, bline)) newLines.push_back(bline);
                }
            }
            newLines.push_back(line);
        }
        rawLines_ = std::move(newLines);
    }

    infoMessages.push_back("[boundary] Applied " + std::to_string(bcCount) + " boundary condition(s)");
    return true;
}

// ══════════════════════════════════════════════════════════════════════════════
// RBE (Rigid Body Element) - CONSTRAINED_INTERPOLATION / CONSTRAINED_NODAL_RIGID_BODY
// ══════════════════════════════════════════════════════════════════════════════

namespace {

// Find max existing *CONSTRAINED_NODAL_RIGID_BODY PID
static int rbe_findMaxCnrbPid(const std::vector<std::string>& rawLines) {
    int maxPid = 0;
    bool inCnrb = false;
    bool needTitle = false;
    bool needData = true;
    for (const auto& line : rawLines) {
        if (!line.empty() && line[0] == '*') {
            std::string up = line;
            for (auto& c : up) c = (char)std::toupper((unsigned char)c);
            if (up.find("*CONSTRAINED_NODAL_RIGID_BODY") == 0) {
                inCnrb = true;
                needTitle = (up.find("_TITLE") != std::string::npos);
                needData = true;
                continue;
            }
            inCnrb = false;
            continue;
        }
        if (!inCnrb) continue;
        if (!line.empty() && line[0] == '$') continue;
        if (needTitle) { needTitle = false; continue; }
        if (needData) {
            std::istringstream iss(line);
            int pid = 0;
            if (iss >> pid && pid > maxPid) maxPid = pid;
            needData = false;
            inCnrb = false;
        }
    }
    return maxPid;
}

// Find max existing *CONSTRAINED_INTERPOLATION ICID
static int rbe_findMaxIcid(const std::vector<std::string>& rawLines) {
    int maxIcid = 0;
    bool inCI = false;
    bool needData = true;
    for (const auto& line : rawLines) {
        if (!line.empty() && line[0] == '*') {
            std::string up = line;
            for (auto& c : up) c = (char)std::toupper((unsigned char)c);
            if (up.find("*CONSTRAINED_INTERPOLATION") == 0 &&
                up.find("SPOTWELD") == std::string::npos) {
                inCI = true;
                needData = true;
                continue;
            }
            inCI = false;
            continue;
        }
        if (!inCI) continue;
        if (!line.empty() && line[0] == '$') continue;
        if (needData) {
            std::istringstream iss(line);
            int icid = 0;
            if (iss >> icid && icid > maxIcid) maxIcid = icid;
            needData = false;
            inCI = false;
        }
    }
    return maxIcid;
}

// Generate *CONSTRAINED_INTERPOLATION card (RBE3)
// Card 1: ICID, DNID, DDOF, CIDD, ITYP, IDNSW, FGM
// Card 2 per independent node: INID, IDOF, TWGHTX (others default to TWGHTX)
static std::string rbe_generateConstrainedInterpolation(
        int icid, int dnid, const std::vector<int>& independentNodes) {
    std::ostringstream ss;
    ss << "*CONSTRAINED_INTERPOLATION\n";
    ss << "$#    icid      dnid      ddof      cidd      ityp     idnsw       fgm\n";
    char buf[120];
    snprintf(buf, sizeof(buf), "%10d%10d%10d%10d%10d%10d%10d",
             icid, dnid, 123456, 0, 0, 0, 0);
    ss << buf << "\n";
    ss << "$#    inid      idof    twghtx    twghty    twghtz    rwghtx    rwghty    rwghtz\n";
    for (int nid : independentNodes) {
        snprintf(buf, sizeof(buf), "%10d%10d%10s",
                 nid, 123456, "1.0");
        ss << buf << "\n";
    }
    return ss.str();
}

// Generate *CONSTRAINED_NODAL_RIGID_BODY_TITLE card (RBE2)
// Card 1: PID, CID, NSID, PNODE, IPRT, DRFLAG, RRFLAG
static std::string rbe_generateCnrb(int pid, int nsid, const std::string& title) {
    std::ostringstream ss;
    ss << "*CONSTRAINED_NODAL_RIGID_BODY_TITLE\n";
    ss << title << "\n";
    ss << "$#     pid       cid      nsid     pnode      iprt    drflag    rrflag\n";
    char buf[120];
    snprintf(buf, sizeof(buf), "%10d%10d%10d%10d%10d%10d%10d",
             pid, 0, nsid, 0, 0, 0, 0);
    ss << buf << "\n";
    return ss.str();
}

} // anonymous namespace

// ── applyRbe() main ─────────────────────────────────────────────────────────

bool ModelAssembler::applyRbe(const RbeOperation& op) {
    if (op.constraints.empty()) {
        std::cout << "[rbe] No RBE constraints specified\n";
        return true;
    }

    int maxSetNodeId = bc_findMaxSetNodeId(rawLines_);
    int nextSetId = maxSetNodeId + 1;
    int nextCnrbPid = rbe_findMaxCnrbPid(rawLines_) + 1;
    int nextIcid = rbe_findMaxIcid(rawLines_) + 1;
    std::vector<std::string> insertBlocks;
    int rbeCount = 0;
    int nodesCreated = 0;

    for (const auto& rc : op.constraints) {
        int pid = ld_resolvePid(rawLines_, rc.pid, rc.partName);
        if (pid <= 0) {
            std::cerr << "[rbe] ERROR: Cannot resolve part (pid="
                      << rc.pid << " name='" << rc.partName << "')\n";
            return false;
        }

        // Extract surface faces
        auto allFaces = ld_extractSurface(baseMesh_, pid);
        if (allFaces.empty()) {
            std::cerr << "[rbe] WARNING: No surface faces for PID=" << pid << ", skipping\n";
            continue;
        }

        // Filter by direction if needed
        std::vector<std::array<int,4>> selectedFaces;
        std::vector<LdFaceInfo> selectedFaceInfos;

        if (rc.select == "direction") {
            double dir[3] = {rc.direction[0], rc.direction[1], rc.direction[2]};
            double dirMag = ld_mag(dir);
            if (dirMag < 1e-30) {
                std::cerr << "[rbe] ERROR: Zero direction vector for PID=" << pid << "\n";
                return false;
            }
            dir[0] /= dirMag; dir[1] /= dirMag; dir[2] /= dirMag;

            auto faceInfos = ld_buildFaceInfo(allFaces, baseMesh_);
            auto indices = ld_filterByDirection(faceInfos, dir, rc.angle);
            if (indices.empty()) {
                std::cerr << "[rbe] WARNING: No faces match direction filter for PID="
                          << pid << ", skipping\n";
                continue;
            }
            for (int idx : indices) {
                selectedFaces.push_back(allFaces[idx]);
                selectedFaceInfos.push_back(faceInfos[idx]);
            }
        } else {
            // select == "all"
            selectedFaces = allFaces;
            selectedFaceInfos = ld_buildFaceInfo(allFaces, baseMesh_);
        }

        if (rc.mode == "spider") {
            // ── Spider mode: one centroid → one constraint ──
            auto nodeIds = bc_collectNodes(selectedFaces);
            if (nodeIds.empty()) continue;

            // Compute centroid of all surface nodes
            double cx = 0, cy = 0, cz = 0;
            int validCount = 0;
            for (int nid : nodeIds) {
                const auto* nd = baseMesh_.getNode(nid);
                if (!nd) continue;
                cx += nd->position.x;
                cy += nd->position.y;
                cz += nd->position.z;
                validCount++;
            }
            if (validCount == 0) continue;
            cx /= validCount; cy /= validCount; cz /= validCount;

            // Create centroid node
            int centroidNid = ++maxNodeId_;
            addedNodes_.push_back({centroidNid, cx, cy, cz});
            nodesCreated++;

            if (rc.type == "rbe3") {
                // CONSTRAINED_INTERPOLATION: centroid=dependent, surface nodes=independent
                insertBlocks.push_back(rbe_generateConstrainedInterpolation(
                    nextIcid++, centroidNid, nodeIds));
            } else {
                // rbe2: SET_NODE (centroid + all surface nodes) + CNRB
                std::vector<int> allNodes;
                allNodes.push_back(centroidNid);
                allNodes.insert(allNodes.end(), nodeIds.begin(), nodeIds.end());
                int setId = nextSetId++;
                std::string setTitle = "RBE2_PID" + std::to_string(pid) + "_spider";
                insertBlocks.push_back(bc_generateSetNode(setId, allNodes, setTitle));
                std::string cnrbTitle = "RBE2_PID" + std::to_string(pid) + "_spider";
                insertBlocks.push_back(rbe_generateCnrb(nextCnrbPid++, setId, cnrbTitle));
            }
            rbeCount++;

            std::cout << "[rbe] PID=" << pid << " mode=spider type=" << rc.type
                      << " nodes=" << (int)nodeIds.size()
                      << " centroid=(" << cx << ", " << cy << ", " << cz << ")\n";

        } else {
            // ── Face mode: per-face centroid → per-face constraint ──
            int faceConstraints = 0;
            for (int fi = 0; fi < (int)selectedFaceInfos.size(); ++fi) {
                const auto& finfo = selectedFaceInfos[fi];
                const auto& face = selectedFaces[fi];

                // Create centroid node for this face
                int centroidNid = ++maxNodeId_;
                addedNodes_.push_back({centroidNid,
                    finfo.centroid[0], finfo.centroid[1], finfo.centroid[2]});
                nodesCreated++;

                // Collect corner node IDs
                std::vector<int> cornerNodes;
                for (int k = 0; k < finfo.nVerts; ++k) {
                    if (face[k] > 0) cornerNodes.push_back(face[k]);
                }

                if (rc.type == "rbe3") {
                    insertBlocks.push_back(rbe_generateConstrainedInterpolation(
                        nextIcid++, centroidNid, cornerNodes));
                } else {
                    // rbe2
                    std::vector<int> allNodes;
                    allNodes.push_back(centroidNid);
                    allNodes.insert(allNodes.end(), cornerNodes.begin(), cornerNodes.end());
                    int setId = nextSetId++;
                    std::string setTitle = "RBE2_PID" + std::to_string(pid)
                                         + "_face" + std::to_string(fi);
                    insertBlocks.push_back(bc_generateSetNode(setId, allNodes, setTitle));
                    insertBlocks.push_back(rbe_generateCnrb(nextCnrbPid++, setId, setTitle));
                }
                faceConstraints++;
            }
            rbeCount += faceConstraints;

            std::cout << "[rbe] PID=" << pid << " mode=face type=" << rc.type
                      << " faces=" << faceConstraints << "\n";
        }
    }

    // Insert before *END
    if (!insertBlocks.empty()) {
        std::vector<std::string> newLines;
        newLines.reserve(rawLines_.size() + insertBlocks.size() * 10);
        for (const auto& line : rawLines_) {
            std::string up = line;
            for (auto& c : up) c = (char)std::toupper((unsigned char)c);
            if (up.find("*END") == 0) {
                for (const auto& block : insertBlocks) {
                    std::istringstream bs(block);
                    std::string bline;
                    while (std::getline(bs, bline)) newLines.push_back(bline);
                }
            }
            newLines.push_back(line);
        }
        rawLines_ = std::move(newLines);
    }

    infoMessages.push_back("[rbe] Created " + std::to_string(rbeCount)
        + " constraint(s), " + std::to_string(nodesCreated) + " centroid node(s)");
    return true;
}

// ── applyWrap() ─────────────────────────────────────────────────────────────

bool ModelAssembler::applyWrap(const WrapOperation& op, double E, double nu) {
    if (op.targetPids.empty()) {
        errorMessage_ = "wrap: no target PIDs specified";
        return false;
    }
    if (op.tension == 0.0) {
        errorMessage_ = "wrap: tension must be non-zero";
        return false;
    }

    // Axis mapping
    int axisMain, axis1, axis2;
    if (op.axis == "x") { axisMain = 0; axis1 = 1; axis2 = 2; }
    else if (op.axis == "y") { axisMain = 1; axis1 = 0; axis2 = 2; }
    else { axisMain = 2; axis1 = 0; axis2 = 1; } // z default

    // Build node index for addedNodes_
    std::map<int, size_t> addedNodeIndex;
    for (size_t i = 0; i < addedNodes_.size(); ++i)
        addedNodeIndex[addedNodes_[i].id] = i;

    auto getNodePos = [&](int nid, double& x, double& y, double& z) -> bool {
        auto it = addedNodeIndex.find(nid);
        if (it != addedNodeIndex.end()) {
            x = addedNodes_[it->second].x;
            y = addedNodes_[it->second].y;
            z = addedNodes_[it->second].z;
            return true;
        }
        const auto* node = baseMesh_.getNode(nid);
        if (!node) return false;
        x = node->position.x; y = node->position.y; z = node->position.z;
        return true;
    };

    auto getCoord = [&](double x, double y, double z, int ax) -> double {
        if (ax == 0) return x; if (ax == 1) return y; return z;
    };

    // Collect elements per PID (base + added)
    struct LayerInfo {
        int pid;
        std::vector<int> elemIds;          // element IDs
        std::vector<bool> isAdded;         // true if from addedElements_
        std::vector<size_t> addedIdx;      // index into addedElements_ (if isAdded)
        double avgRadius = 0.0;
    };
    std::vector<LayerInfo> layers(op.targetPids.size());
    for (size_t li = 0; li < op.targetPids.size(); ++li)
        layers[li].pid = op.targetPids[li];

    // Auto-center: accumulate all node coords
    double sumA = 0, sumB = 0;
    int centerCount = 0;

    for (auto& layer : layers) {
        // Base mesh elements
        for (const auto& [eid, elem] : baseMesh_.getElements()) {
            if (elem.partId == layer.pid && removedElementIds_.count(eid) == 0) {
                layer.elemIds.push_back(eid);
                layer.isAdded.push_back(false);
                layer.addedIdx.push_back(0);
                if (op.autoCenter) {
                    for (int i = 0; i < Element::NUM_NODES; ++i) {
                        double x, y, z;
                        if (getNodePos(elem.nodeIds[i], x, y, z)) {
                            sumA += getCoord(x, y, z, axis1);
                            sumB += getCoord(x, y, z, axis2);
                            centerCount++;
                        }
                    }
                }
            }
        }
        // Added elements
        for (size_t ai = 0; ai < addedElements_.size(); ++ai) {
            if (addedElements_[ai].pid == layer.pid) {
                layer.elemIds.push_back(addedElements_[ai].id);
                layer.isAdded.push_back(true);
                layer.addedIdx.push_back(ai);
                if (op.autoCenter) {
                    for (int nid : addedElements_[ai].nodeIds) {
                        double x, y, z;
                        if (getNodePos(nid, x, y, z)) {
                            sumA += getCoord(x, y, z, axis1);
                            sumB += getCoord(x, y, z, axis2);
                            centerCount++;
                        }
                    }
                }
            }
        }
    }

    double cA = op.autoCenter ? (centerCount > 0 ? sumA / centerCount : 0.0) : op.centerA;
    double cB = op.autoCenter ? (centerCount > 0 ? sumB / centerCount : 0.0) : op.centerB;

    // Compute per-layer average radius
    for (auto& layer : layers) {
        double rSum = 0; int rCount = 0;
        for (size_t ei = 0; ei < layer.elemIds.size(); ++ei) {
            // Get element node IDs
            const int* nodeIds;
            int nNodes = 8;
            if (layer.isAdded[ei]) {
                nodeIds = addedElements_[layer.addedIdx[ei]].nodeIds.data();
            } else {
                const auto& elem = baseMesh_.getElements().at(layer.elemIds[ei]);
                nodeIds = elem.nodeIds.data();
            }
            for (int i = 0; i < nNodes; ++i) {
                double x, y, z;
                if (!getNodePos(nodeIds[i], x, y, z)) continue;
                double a = getCoord(x, y, z, axis1) - cA;
                double b = getCoord(x, y, z, axis2) - cB;
                rSum += std::sqrt(a*a + b*b);
                rCount++;
            }
        }
        layer.avgRadius = rCount > 0 ? rSum / rCount : 1.0;
    }

    // Validate layer ordering (inner → outer)
    for (size_t i = 1; i < layers.size(); ++i) {
        if (layers[i].avgRadius < layers[i-1].avgRadius) {
            infoMessages.push_back("[wrap] WARNING: PID " + std::to_string(layers[i].pid)
                + " (R=" + std::to_string(layers[i].avgRadius)
                + ") has smaller radius than PID " + std::to_string(layers[i-1].pid)
                + " (R=" + std::to_string(layers[i-1].avgRadius) + "). Check layer order.");
        }
    }

    int N = static_cast<int>(layers.size());
    int totalElements = 0;

    // Compute stress per element
    for (int k = 0; k < N; ++k) {
        auto& layer = layers[k];
        double R = layer.avgRadius;

        for (size_t ei = 0; ei < layer.elemIds.size(); ++ei) {
            const int* nodeIds;
            int nNodes = 8;
            if (layer.isAdded[ei]) {
                nodeIds = addedElements_[layer.addedIdx[ei]].nodeIds.data();
            } else {
                const auto& elem = baseMesh_.getElements().at(layer.elemIds[ei]);
                nodeIds = elem.nodeIds.data();
            }

            // Element centroid and radial thickness
            double cx1 = 0, cx2 = 0;
            double rMin = 1e30, rMax = -1e30;
            int validN = 0;
            for (int i = 0; i < nNodes; ++i) {
                double x, y, z;
                if (!getNodePos(nodeIds[i], x, y, z)) continue;
                double a = getCoord(x, y, z, axis1) - cA;
                double b = getCoord(x, y, z, axis2) - cB;
                double r = std::sqrt(a*a + b*b);
                if (r < rMin) rMin = r;
                if (r > rMax) rMax = r;
                cx1 += a; cx2 += b;
                validN++;
            }
            if (validN == 0) continue;
            cx1 /= validN; cx2 /= validN;

            double t_elem = rMax - rMin;
            if (t_elem < 1.0e-12) t_elem = 1.0e-6; // avoid div by zero

            double theta = std::atan2(cx2, cx1);
            double sinT = std::sin(theta), cosT = std::cos(theta);

            // Hoop tension (uniform through thickness)
            double sigma_theta = op.tension / t_elem;

            // Radial compression (layer-dependent)
            double sigma_r = -op.tension / R * static_cast<double>(N - k) / static_cast<double>(N);

            // Axial = 0
            // Transform cylindrical → Cartesian
            // axis1-axis1, axis2-axis2, axisMain, axis1-axis2 shear
            double s11 = sigma_theta * sinT*sinT + sigma_r * cosT*cosT;
            double s22 = sigma_theta * cosT*cosT + sigma_r * sinT*sinT;
            double s12 = (sigma_theta - sigma_r) * sinT * cosT;
            double sMain = 0.0;

            // Map to xx, yy, zz, xy, yz, xz
            double sxx = 0, syy = 0, szz = 0, sxy = 0, syz = 0, sxz = 0;
            if (axisMain == 2) { // z-axis winding
                sxx = s11; syy = s22; szz = sMain; sxy = s12;
            } else if (axisMain == 0) { // x-axis winding: perp = y,z
                syy = s11; szz = s22; sxx = sMain; syz = s12;
            } else { // y-axis winding: perp = x,z
                sxx = s11; szz = s22; syy = sMain; sxz = s12;
            }

            StressTensor stress(sxx, syy, szz, sxy, syz, sxz);

            ElementResult er;
            er.elementId = layer.elemIds[ei];
            er.stress = stress;
            er.strain = StrainTensor(); // prescribed stress, no strain needed
            er.isValid = true;
            er.vonMisesStress = stress.vonMises();
            er.vonMisesStrain = 0.0;
            accumulatedResults_.push_back(er);
            totalElements++;
        }
    }

    std::ostringstream oss;
    oss << "[wrap] " << N << " layers, tension=" << op.tension
        << " N/mm, axis=" << op.axis
        << ", center=(" << cA << "," << cB << ")"
        << ", " << totalElements << " elements";
    infoMessages.push_back(oss.str());

    return true;
}

// ========== DATABASE: Insert *DATABASE_* output control keywords ==========

bool ModelAssembler::applyGenerate(const GenerateOperation& op) {
    if (op.shape != "box" && !op.shape.empty()) {
        errorMessage_ = "generate: unknown shape '" + op.shape + "' (only 'box' supported)";
        return false;
    }

    int nx = op.nx, ny = op.ny, nz = op.nz;
    if (nx < 1 || ny < 1 || nz < 1) {
        errorMessage_ = "generate: nx/ny/nz must be >= 1";
        return false;
    }
    int npx = nx + 1, npy = ny + 1, npz = nz + 1;
    double dx = op.lx / nx, dy = op.ly / ny, dz = op.lz / nz;
    int mid = op.mid > 0 ? op.mid : 1;
    int secid = op.secid > 0 ? op.secid : 1;
    int pid = op.pid > 0 ? op.pid : 1;
    std::string title = op.partTitle.empty() ? "Box" : op.partTitle;

    auto nid = [&](int ix, int iy, int iz) -> int {
        return iz * (npx * npy) + iy * npx + ix + 1;
    };

    // Format helpers
    auto fmt10d = [](double v) -> std::string {
        char buf[32];
        if (v == 0.0)
            snprintf(buf, sizeof(buf), "       0.0");
        else if (std::abs(v) < 1e-4 || std::abs(v) >= 1e8)
            snprintf(buf, sizeof(buf), "%10.4E", v);
        else
            snprintf(buf, sizeof(buf), "%10g", v);
        std::string s(buf);
        while (s.size() < 10) s = " " + s;
        return s.substr(s.size() - 10);
    };

    // Build rawLines_
    rawLines_.clear();
    rawLines_.push_back("$ Generated by KooRemapper assemble (generate box)");
    rawLines_.push_back("*KEYWORD");
    rawLines_.push_back("*MAT_ELASTIC");
    rawLines_.push_back("$#     mid        ro         e        pr        da        db  not used");
    {
        char buf[128];
        snprintf(buf, sizeof(buf), "%10d%s%s%s%10.1f%10.1f%10.1f",
                 mid, fmt10d(op.rho).c_str(), fmt10d(op.E).c_str(), fmt10d(op.nu).c_str(),
                 0.0, 0.0, 0.0);
        rawLines_.push_back(std::string(buf));
    }
    rawLines_.push_back("*SECTION_SOLID");
    rawLines_.push_back("$#   secid    elform       aet");
    {
        char buf[64];
        snprintf(buf, sizeof(buf), "%10d%10d%10d", secid, 1, 0);
        rawLines_.push_back(std::string(buf));
    }
    rawLines_.push_back("*PART");
    rawLines_.push_back(title);
    {
        char buf[64];
        snprintf(buf, sizeof(buf), "%10d%10d%10d", pid, secid, mid);
        rawLines_.push_back(std::string(buf));
    }
    rawLines_.push_back("*NODE");
    for (int iz = 0; iz < npz; iz++)
        for (int iy = 0; iy < npy; iy++)
            for (int ix = 0; ix < npx; ix++) {
                char buf[128];
                snprintf(buf, sizeof(buf), "%8d%16.7E%16.7E%16.7E",
                         nid(ix,iy,iz), ix*dx, iy*dy, iz*dz);
                rawLines_.push_back(std::string(buf));
            }
    rawLines_.push_back("*ELEMENT_SOLID");
    int eid = 1;
    for (int iz = 0; iz < nz; iz++)
        for (int iy = 0; iy < ny; iy++)
            for (int ix = 0; ix < nx; ix++, eid++) {
                std::array<int,8> n = {
                    nid(ix,   iy,   iz),   nid(ix+1, iy,   iz),
                    nid(ix+1, iy+1, iz),   nid(ix,   iy+1, iz),
                    nid(ix,   iy,   iz+1), nid(ix+1, iy,   iz+1),
                    nid(ix+1, iy+1, iz+1), nid(ix,   iy+1, iz+1)
                };
                char buf[128];
                snprintf(buf, sizeof(buf), "%8d%8d%8d%8d%8d%8d%8d%8d%8d%8d",
                         eid, pid, n[0], n[1], n[2], n[3], n[4], n[5], n[6], n[7]);
                rawLines_.push_back(std::string(buf));
            }
    rawLines_.push_back("*END");

    // Populate baseMesh_ directly (no file I/O needed)
    baseMesh_.clear();
    baseMesh_.addMaterial(mid, op.E, op.nu, op.rho);
    baseMesh_.addPart(pid, secid, mid, title);
    for (int iz = 0; iz < npz; iz++)
        for (int iy = 0; iy < npy; iy++)
            for (int ix = 0; ix < npx; ix++)
                baseMesh_.addNode(nid(ix,iy,iz), ix*dx, iy*dy, iz*dz);
    eid = 1;
    for (int iz = 0; iz < nz; iz++)
        for (int iy = 0; iy < ny; iy++)
            for (int ix = 0; ix < nx; ix++, eid++) {
                std::array<int,8> n = {
                    nid(ix,   iy,   iz),   nid(ix+1, iy,   iz),
                    nid(ix+1, iy+1, iz),   nid(ix,   iy+1, iz),
                    nid(ix,   iy,   iz+1), nid(ix+1, iy,   iz+1),
                    nid(ix+1, iy+1, iz+1), nid(ix,   iy+1, iz+1)
                };
                baseMesh_.addElement(eid, pid, n);
            }
    baseMesh_.setGridDimensions(nx, ny, nz);

    // Update ID trackers
    maxNodeId_    = npx * npy * npz;
    maxElementId_ = nx * ny * nz;
    maxPartId_    = pid;
    maxSectionId_ = secid;
    maxMaterialId_= mid;

    int totalNodes = npx * npy * npz;
    int totalElems = nx * ny * nz;
    infoMessages.push_back("[generate] box " +
        std::to_string(op.lx) + "x" + std::to_string(op.ly) + "x" + std::to_string(op.lz) +
        " mm, " + std::to_string(totalNodes) + " nodes, " + std::to_string(totalElems) + " elements");
    return true;
}

bool ModelAssembler::applyControl(const ControlOperation& op) {
    // Right-align a value in a 10-char fixed-width field
    auto fmt10d = [](double v) -> std::string {
        char buf[32];
        if (v == 0.0) {
            snprintf(buf, sizeof(buf), "       0.0");
        } else if (std::abs(v) < 0.001 || std::abs(v) >= 1e7) {
            snprintf(buf, sizeof(buf), "%10.4E", v);
        } else {
            snprintf(buf, sizeof(buf), "%10g", v);
        }
        std::string s(buf);
        while (s.size() < 10) s = " " + s;
        return s.substr(s.size() - 10);
    };
    auto fmt10i = [](int v) -> std::string {
        char buf[16];
        snprintf(buf, sizeof(buf), "%10d", v);
        return std::string(buf).substr(0, 10);
    };
    auto setField = [](std::string& line, int fi, const std::string& val10) {
        size_t needed = (size_t)(fi + 1) * 10;
        if (line.size() < needed) line.resize(needed, ' ');
        line.replace((size_t)fi * 10, 10, val10.substr(0, 10));
    };

    // Find keyword line in rawLines_ (case-insensitive, exact keyword match)
    auto findKeyword = [&](const std::string& kw) -> int {
        for (size_t i = 0; i < rawLines_.size(); i++) {
            std::string up = rawLines_[i];
            for (auto& c : up) c = (char)toupper((unsigned char)c);
            // strip trailing whitespace
            while (!up.empty() && (up.back() == ' ' || up.back() == '\t' || up.back() == '\r')) up.pop_back();
            if (up == kw) return (int)i;
        }
        return -1;
    };
    // First data line (non-comment, non-keyword) after keyword index
    auto findDataLine = [&](int kwIdx) -> int {
        for (int j = kwIdx + 1; j < (int)rawLines_.size() && j < kwIdx + 10; j++) {
            if (rawLines_[j].empty()) continue;
            char c = rawLines_[j][0];
            if (c == '$' || c == '*') continue;
            return j;
        }
        return -1;
    };

    int affected = 0;

    // --- *CONTROL_TERMINATION ---
    if (op.endtime > 0.0) {
        int ki = findKeyword("*CONTROL_TERMINATION");
        if (ki >= 0) {
            int di = findDataLine(ki);
            if (di >= 0) { setField(rawLines_[di], 0, fmt10d(op.endtime)); affected++; }
        } else {
            std::string card = "*CONTROL_TERMINATION\n";
            card += fmt10d(op.endtime) + fmt10i(0) + "       0.0       0.0       0.0" + fmt10i(0) + "\n";
            addedKeywordBlocks_.push_back(card);
            affected++;
        }
    }

    // --- *CONTROL_TIMESTEP ---
    if (op.tssfac > 0.0 || op.setDt2ms) {
        int ki = findKeyword("*CONTROL_TIMESTEP");
        if (ki >= 0) {
            int di = findDataLine(ki);
            if (di >= 0) {
                if (op.tssfac > 0.0) setField(rawLines_[di], 1, fmt10d(op.tssfac));
                if (op.setDt2ms)     setField(rawLines_[di], 4, fmt10d(op.dt2ms));
                affected++;
            }
        } else {
            std::string card = "*CONTROL_TIMESTEP\n";
            std::string line = "       0.0";  // DTINIT
            line += (op.tssfac > 0.0 ? fmt10d(op.tssfac) : "      0.90");  // TSSFAC
            line += fmt10i(0);                // ISDO
            line += "       0.0";            // TSLIMT
            line += (op.setDt2ms ? fmt10d(op.dt2ms) : "       0.0");  // DT2MS
            line += fmt10i(0) + fmt10i(0) + fmt10i(0);  // LCTM ERODE MS1ST
            card += line + "\n";
            addedKeywordBlocks_.push_back(card);
            affected++;
        }
    }

    // --- *CONTROL_ENERGY ---
    if (op.hgen || op.rwen || op.slnten || op.rylen) {
        int ki = findKeyword("*CONTROL_ENERGY");
        if (ki >= 0) {
            int di = findDataLine(ki);
            if (di >= 0) {
                if (op.hgen)   setField(rawLines_[di], 0, fmt10i(op.hgen));
                if (op.rwen)   setField(rawLines_[di], 1, fmt10i(op.rwen));
                if (op.slnten) setField(rawLines_[di], 2, fmt10i(op.slnten));
                if (op.rylen)  setField(rawLines_[di], 3, fmt10i(op.rylen));
                affected++;
            }
        } else {
            std::string card = "*CONTROL_ENERGY\n";
            card += fmt10i(op.hgen   ? op.hgen   : 2);
            card += fmt10i(op.rwen   ? op.rwen   : 2);
            card += fmt10i(op.slnten ? op.slnten : 1);
            card += fmt10i(op.rylen  ? op.rylen  : 1);
            card += "\n";
            addedKeywordBlocks_.push_back(card);
            affected++;
        }
    }

    // --- *CONTROL_HOURGLASS ---
    if (op.ihq > 0) {
        int ki = findKeyword("*CONTROL_HOURGLASS");
        if (ki >= 0) {
            int di = findDataLine(ki);
            if (di >= 0) {
                setField(rawLines_[di], 0, fmt10i(op.ihq));
                setField(rawLines_[di], 1, fmt10d(op.qh));
                affected++;
            }
        } else {
            std::string card = "*CONTROL_HOURGLASS\n";
            card += fmt10i(op.ihq) + fmt10d(op.qh) + "\n";
            addedKeywordBlocks_.push_back(card);
            affected++;
        }
    }

    // --- *CONTROL_BULK_VISCOSITY ---
    if (op.q1 != 0.0 || op.q2 != 0.0) {
        int ki = findKeyword("*CONTROL_BULK_VISCOSITY");
        if (ki >= 0) {
            int di = findDataLine(ki);
            if (di >= 0) {
                if (op.q1) setField(rawLines_[di], 0, fmt10d(op.q1));
                if (op.q2) setField(rawLines_[di], 1, fmt10d(op.q2));
                if (op.bulkType) setField(rawLines_[di], 2, fmt10i(op.bulkType));
                affected++;
            }
        } else {
            std::string card = "*CONTROL_BULK_VISCOSITY\n";
            card += fmt10d(op.q1) + fmt10d(op.q2) + fmt10i(op.bulkType) + "\n";
            addedKeywordBlocks_.push_back(card);
            affected++;
        }
    }

    infoMessages.push_back("[control] " + std::to_string(affected) + " control card(s) applied");
    return true;
}

bool ModelAssembler::applyDatabase(const DatabaseOperation& op) {
    // Preset definitions (mirrors db_getPresets in main.cpp)
    struct DbPreset {
        std::string name;
        std::vector<std::string> ascii;
        std::vector<std::string> binary;
        bool extent;
    };
    static const DbPreset PRESETS[] = {
        {"all",
         {"glstat","matsum","nodout","elout","rcforc","sleout","spcforc","nodfor",
          "rwforc","secforc","jntforc","bndout","abstat","swforc","ssstat","deforc",
          "disbout","ncforc","tprint","massout"},
         {"d3plot","d3thdt","d3dump","runrsf"}, true},
        {"drop",
         {"glstat","matsum","nodout","elout","rcforc","sleout","spcforc","rwforc",
          "nodfor","secforc","bndout","ncforc"},
         {"d3plot","d3thdt","d3dump"}, true},
        {"crash",
         {"glstat","matsum","nodout","elout","rcforc","sleout","spcforc","rwforc",
          "nodfor","secforc","swforc","ncforc","abstat"},
         {"d3plot","d3thdt","d3dump"}, true},
        {"static",
         {"glstat","matsum","nodout","elout","spcforc","nodfor","bndout","secforc"},
         {"d3plot","d3thdt"}, true},
        {"thermal",
         {"glstat","matsum","nodout","elout","spcforc","tprint","bndout"},
         {"d3plot","d3thdt"}, true},
        {"forming",
         {"glstat","matsum","nodout","elout","rcforc","sleout","spcforc","nodfor",
          "secforc","ncforc","swforc"},
         {"d3plot","d3thdt","d3dump"}, true},
        {"modal",
         {"glstat","matsum","nodout","elout","spcforc"},
         {"d3plot"}, false},
        {"minimal",
         {"glstat","matsum"},
         {"d3plot"}, false},
    };

    // Resolve which keywords to enable
    std::set<std::string> enabledAscii(op.enabledAscii.begin(), op.enabledAscii.end());
    std::set<std::string> enabledBinary(op.enabledBinary.begin(), op.enabledBinary.end());
    bool extentBinary = op.extentBinary;

    if (!op.preset.empty()) {
        for (const auto& p : PRESETS) {
            if (p.name == op.preset) {
                enabledAscii.insert(p.ascii.begin(), p.ascii.end());
                enabledBinary.insert(p.binary.begin(), p.binary.end());
                if (p.extent) extentBinary = true;
                break;
            }
        }
    }

    if (enabledAscii.empty() && enabledBinary.empty()) {
        errorMessage_ = "database: no keywords enabled (check preset name)";
        return false;
    }

    double dt = op.dt > 0 ? op.dt : 0.001;
    double dtPlot = op.dtPlot > 0 ? op.dtPlot : dt * 10.0;
    double dtThdt = op.dtThdt > 0 ? op.dtThdt : dt;

    // Scan rawLines_ for already-existing *DATABASE_ keywords
    std::set<std::string> existing;
    for (const auto& line : rawLines_) {
        std::string up = line;
        for (auto& c : up) c = (char)toupper((unsigned char)c);
        std::string tr = up;
        while (!tr.empty() && std::isspace((unsigned char)tr.front())) tr.erase(tr.begin());
        if (tr.find("*DATABASE_") == 0) {
            size_t e = tr.find_first_of(" \t\r\n");
            existing.insert(e != std::string::npos ? tr.substr(0, e) : tr);
        }
    }

    // ASCII keyword → *DATABASE_XXX map
    static const std::pair<const char*, const char*> ASCII_KW[] = {
        {"glstat",  "*DATABASE_GLSTAT"},  {"matsum",  "*DATABASE_MATSUM"},
        {"nodout",  "*DATABASE_NODOUT"},  {"elout",   "*DATABASE_ELOUT"},
        {"rcforc",  "*DATABASE_RCFORC"},  {"sleout",  "*DATABASE_SLEOUT"},
        {"spcforc", "*DATABASE_SPCFORC"}, {"nodfor",  "*DATABASE_NODFOR"},
        {"rwforc",  "*DATABASE_RWFORC"},  {"secforc", "*DATABASE_SECFORC"},
        {"jntforc", "*DATABASE_JNTFORC"}, {"bndout",  "*DATABASE_BNDOUT"},
        {"abstat",  "*DATABASE_ABSTAT"},  {"swforc",  "*DATABASE_SWFORC"},
        {"ssstat",  "*DATABASE_SSSTAT"},  {"deforc",  "*DATABASE_DEFORC"},
        {"disbout", "*DATABASE_DISBOUT"}, {"ncforc",  "*DATABASE_NCFORC"},
        {"tprint",  "*DATABASE_TPRINT"},  {"massout", "*DATABASE_MASSOUT"},
    };
    static const std::pair<const char*, const char*> BINARY_KW[] = {
        {"d3plot",  "*DATABASE_BINARY_D3PLOT"},
        {"d3thdt",  "*DATABASE_BINARY_D3THDT"},
        {"d3dump",  "*DATABASE_BINARY_D3DUMP"},
        {"runrsf",  "*DATABASE_BINARY_RUNRSF"},
        {"intfor",  "*DATABASE_BINARY_INTFOR"},
        {"d3drlf",  "*DATABASE_BINARY_D3DRLF"},
    };

    std::ostringstream blk;
    blk << "$\n$ === DATABASE OUTPUT CONTROL (KooRemapper) ===\n$\n";
    char buf[128];
    int inserted = 0;

    for (const auto& [name, kw] : ASCII_KW) {
        if (!enabledAscii.count(name)) continue;
        std::string kwUp = kw;
        for (auto& c : kwUp) c = (char)toupper((unsigned char)c);
        if (existing.count(kwUp)) continue;
        blk << kw << "\n";
        blk << "$#        dt    binary      lcur     ioopt\n";
        snprintf(buf, sizeof(buf), "%10.4g%10d%10d%10d\n", dt, 0, 0, 1);
        blk << buf;
        ++inserted;
    }
    for (const auto& [name, kw] : BINARY_KW) {
        if (!enabledBinary.count(name)) continue;
        std::string kwUp = kw;
        for (auto& c : kwUp) c = (char)toupper((unsigned char)c);
        if (existing.count(kwUp)) continue;
        double interval = dt;
        if (std::string(name) == "d3plot") interval = dtPlot;
        else if (std::string(name) == "d3thdt") interval = dtThdt;
        blk << kw << "\n";
        blk << "$#        dt      lcdt      beam     npltc    psetid\n";
        snprintf(buf, sizeof(buf), "%10.4g%10d%10d%10d%10d\n", interval, 0, 0, 0, 0);
        blk << buf;
        ++inserted;
    }
    if (extentBinary && !existing.count("*DATABASE_EXTENT_BINARY")) {
        blk << "*DATABASE_EXTENT_BINARY\n";
        blk << "$#   neiph     neips    maxint    strflg    sigflg    epsflg    rltflg    engflg\n";
        snprintf(buf, sizeof(buf), "%10d%10d%10d%10d%10d%10d%10d%10d\n",
                 op.neiph, 0, 3, op.strflg, op.sigflg, op.epsflg, 1, 1);
        blk << buf;
        blk << "$#  cmpflg    ieverp    beamip     dcomp      shge     stssz    n3thdt   ialemat\n";
        blk << "         0         0         0         1         1         0         0         0\n";
        ++inserted;
    }
    blk << "$\n$ === END DATABASE OUTPUT CONTROL ===\n$\n";

    addedKeywordBlocks_.push_back(blk.str());

    std::ostringstream msg;
    msg << "[database] " << inserted << " keywords inserted (preset: "
        << (op.preset.empty() ? "custom" : op.preset) << ")";
    infoMessages.push_back(msg.str());
    return true;
}

// ========== UPDATE: Apply node coordinates from dynain/k-file ==========

bool ModelAssembler::applyUpdate(const UpdateOperation& op) {
    std::ifstream f(op.dynainFile);
    if (!f.is_open()) {
        errorMessage_ = "update: cannot open dynain file: " + op.dynainFile;
        return false;
    }

    // Parse *NODE block from dynain file
    std::map<int, Vector3D> dynainNodes;
    bool inNodeSection = false;
    std::string line;

    while (std::getline(f, line)) {
        if (!line.empty() && line.back() == '\r') line.pop_back();
        std::string upper = line;
        for (auto& c : upper) c = (char)toupper((unsigned char)c);
        std::string trimmed = upper;
        while (!trimmed.empty() && std::isspace((unsigned char)trimmed.front())) trimmed.erase(trimmed.begin());

        // Detect keyword transitions
        if (!trimmed.empty() && trimmed[0] == '*') {
            if (trimmed.substr(0, 5) == "*NODE") {
                inNodeSection = true;
                continue;
            } else {
                inNodeSection = false;
                // Don't break — there may be multiple *NODE blocks
                continue;
            }
        }

        if (!inNodeSection) continue;

        // Skip comments
        if (!trimmed.empty() && trimmed[0] == '$') continue;

        // Parse node line: NID, X, Y, Z  (fixed 8 or 16-char fields, or free-format)
        // Use same approach as KFileReader: try fixed-width first, fallback to free-format
        int nid = 0;
        double x = 0, y = 0, z = 0;

        // Try to parse as space/comma-separated tokens
        std::istringstream iss(line);
        if (iss >> nid >> x >> y >> z) {
            if (nid > 0) {
                dynainNodes[nid] = Vector3D(x, y, z);
            }
        }
    }
    f.close();

    if (dynainNodes.empty()) {
        errorMessage_ = "update: no *NODE data found in " + op.dynainFile;
        return false;
    }

    std::cout << "[INFO] Parsed " << dynainNodes.size() << " nodes from dynain\n";

    // Update matching nodes
    int updatedBase = 0;
    int updatedAdded = 0;

    // Build addedNodes index for fast lookup
    std::map<int, size_t> addedNodeIdx;
    for (size_t i = 0; i < addedNodes_.size(); ++i) {
        addedNodeIdx[addedNodes_[i].id] = i;
    }

    for (const auto& [nid, pos] : dynainNodes) {
        // Check addedNodes_ first (from prior operations)
        auto ait = addedNodeIdx.find(nid);
        if (ait != addedNodeIdx.end()) {
            addedNodes_[ait->second].x = pos.x;
            addedNodes_[ait->second].y = pos.y;
            addedNodes_[ait->second].z = pos.z;
            ++updatedAdded;
            continue;
        }

        // Check base mesh nodes
        const auto* node = baseMesh_.getNode(nid);
        if (node) {
            modifiedNodePositions_[nid] = pos;
            ++updatedBase;
        }
        // Nodes not in model are silently skipped
    }

    int total = updatedBase + updatedAdded;
    int skipped = (int)dynainNodes.size() - total;
    std::cout << "[INFO] Updated " << total << " nodes ("
              << updatedBase << " base + " << updatedAdded << " added)";
    if (skipped > 0) {
        std::cout << ", " << skipped << " not in model (skipped)";
    }
    std::cout << "\n";

    std::ostringstream oss;
    oss << "[update] " << total << "/" << dynainNodes.size() << " nodes updated from "
        << op.dynainFile;
    infoMessages.push_back(oss.str());

    return true;
}

// ========== getAllPartIds ==========

std::vector<int> ModelAssembler::getAllPartIds() const {
    std::set<int> pids;
    for (auto& [eid, elem] : baseMesh_.elements) {
        if (!removedElementIds_.count(eid)) pids.insert(elem.partId);
    }
    for (auto& elem : addedElements_) pids.insert(elem.pid);
    return std::vector<int>(pids.begin(), pids.end());
}

// ========== FILLET: Round edges of a structured HEX8 mesh face ==========

bool ModelAssembler::applyFillet(const FilletOperation& op) {
    if (op.faces.empty()) {
        errorMessage_ = "fillet: no face(s) specified";
        return false;
    }

    // Resolve which PIDs to process
    std::vector<int> pidsToProcess;
    if (!op.targetPids.empty()) {
        pidsToProcess = op.targetPids;
    } else if (op.targetPid == 0) {
        // all structured (HEX8) parts
        for (auto& [eid, elem] : baseMesh_.elements) {
            if (!removedElementIds_.count(eid) && elem.type == ElementType::HEX8)
                pidsToProcess.push_back(elem.partId);
        }
        for (auto& elem : addedElements_)
            if (elem.type == ElementType::HEX8) pidsToProcess.push_back(elem.pid);
        // deduplicate
        std::sort(pidsToProcess.begin(), pidsToProcess.end());
        pidsToProcess.erase(std::unique(pidsToProcess.begin(), pidsToProcess.end()), pidsToProcess.end());
    } else {
        pidsToProcess = {op.targetPid};
    }

    if (pidsToProcess.empty()) {
        errorMessage_ = "fillet: no structured HEX8 parts found";
        return false;
    }

    int totalMovedAll = 0;
    for (int pid : pidsToProcess) {
        FilletOperation singleOp = op;
        singleOp.targetPid  = pid;
        singleOp.targetPids = {};

    // Collect nodes belonging to target PID (base + added elements)
    std::set<int> partNodes;
    for (auto& [eid, elem] : baseMesh_.elements) {
        if (removedElementIds_.count(eid)) continue;
        if (elem.partId != singleOp.targetPid) continue;
        if (elem.type != ElementType::HEX8) {
            errorMessage_ = "fillet: non-HEX8 element found in PID "
                            + std::to_string(singleOp.targetPid) + ". Structured mesh required.";
            return false;
        }
        for (int nid : elem.nodeIds) if (nid > 0) partNodes.insert(nid);
    }
    for (auto& elem : addedElements_) {
        if (elem.pid != singleOp.targetPid) continue;
        for (int nid : elem.nodeIds) if (nid > 0) partNodes.insert(nid);
    }
    if (partNodes.empty()) continue;

    // Get current node position (modifiedNodePositions_ takes priority)
    auto getPos = [&](int nid) -> Vector3D {
        auto it = modifiedNodePositions_.find(nid);
        if (it != modifiedNodePositions_.end()) return it->second;
        auto nit = baseMesh_.nodes.find(nid);
        if (nit != baseMesh_.nodes.end()) return nit->second.position;
        for (auto& n : addedNodes_) if (n.id == nid) return {n.x, n.y, n.z};
        return {0, 0, 0};
    };

    // Set node position
    auto setPos = [&](int nid, const Vector3D& p) {
        modifiedNodePositions_[nid] = p;
        for (auto& n : addedNodes_) {
            if (n.id == nid) { n.x = p.x; n.y = p.y; n.z = p.z; break; }
        }
    };

    // Bounding box of target part
    double xmin =  1e18, xmax = -1e18;
    double ymin =  1e18, ymax = -1e18;
    double zmin =  1e18, zmax = -1e18;
    for (int nid : partNodes) {
        auto p = getPos(nid);
        xmin = std::min(xmin, p.x); xmax = std::max(xmax, p.x);
        ymin = std::min(ymin, p.y); ymax = std::max(ymax, p.y);
        zmin = std::min(zmin, p.z); zmax = std::max(zmax, p.z);
    }

    const double R = op.radius;
    int totalMoved = 0;

    for (const auto& faceStr : op.faces) {
        // Normalise
        std::string face = faceStr;
        for (auto& c : face) c = (char)tolower((unsigned char)c);

        int moved = 0;
        for (int nid : partNodes) {
            auto p = getPos(nid);
            double x = p.x, y = p.y, z = p.z;

            // Per-face: determine main axis and side axes
            // main_val: coordinate along face normal
            // main_ref: face position along that axis
            // main_sign: +1 for _max face, -1 for _min face
            // s1, s2: the two tangential coordinates
            double main_val, main_ref, main_sign;
            double s1, s1min, s1max;
            double s2, s2min, s2max;

            if (face == "z_max") {
                main_val = z; main_ref = zmax; main_sign = +1;
                s1 = x; s1min = xmin; s1max = xmax;
                s2 = y; s2min = ymin; s2max = ymax;
            } else if (face == "z_min") {
                main_val = z; main_ref = zmin; main_sign = -1;
                s1 = x; s1min = xmin; s1max = xmax;
                s2 = y; s2min = ymin; s2max = ymax;
            } else if (face == "x_max") {
                main_val = x; main_ref = xmax; main_sign = +1;
                s1 = y; s1min = ymin; s1max = ymax;
                s2 = z; s2min = zmin; s2max = zmax;
            } else if (face == "x_min") {
                main_val = x; main_ref = xmin; main_sign = -1;
                s1 = y; s1min = ymin; s1max = ymax;
                s2 = z; s2min = zmin; s2max = zmax;
            } else if (face == "y_max") {
                main_val = y; main_ref = ymax; main_sign = +1;
                s1 = x; s1min = xmin; s1max = xmax;
                s2 = z; s2min = zmin; s2max = zmax;
            } else if (face == "y_min") {
                main_val = y; main_ref = ymin; main_sign = -1;
                s1 = x; s1min = xmin; s1max = xmax;
                s2 = z; s2min = zmin; s2max = zmax;
            } else {
                errorMessage_ = "fillet: unknown face '" + faceStr + "'";
                return false;
            }

            // Is this node within R of the face (inward)?
            bool inMainZone = (main_sign > 0) ? (main_val > main_ref - R)
                                              : (main_val < main_ref + R);
            if (!inMainZone) continue;

            // Proximity to each side edge
            bool near_s1max = (s1 > s1max - R);
            bool near_s1min = (s1 < s1min + R);
            bool near_s2max = (s2 > s2max - R);
            bool near_s2min = (s2 < s2min + R);
            if (!near_s1max && !near_s1min && !near_s2max && !near_s2min) continue;

            // Arc/sphere centre in each direction
            double cmain = main_ref - main_sign * R;
            double cs1 = near_s1max ? (s1max - R) : (near_s1min ? (s1min + R) : s1);
            double cs2 = near_s2max ? (s2max - R) : (near_s2min ? (s2min + R) : s2);

            double dm = main_val - cmain;
            double d1 = s1 - cs1;
            double d2 = s2 - cs2;

            double new_main, new_s1, new_s2;
            double len;

            bool use_s1 = (near_s1max || near_s1min);
            bool use_s2 = (near_s2max || near_s2min);

            if (use_s1 && use_s2) {
                // Spherical corner
                len = std::sqrt(dm*dm + d1*d1 + d2*d2);
                if (len < 1e-12) continue;
                new_main = cmain + R * dm / len;
                new_s1   = cs1   + R * d1 / len;
                new_s2   = cs2   + R * d2 / len;
            } else if (use_s1) {
                // Cylindrical arc in main-s1 plane
                len = std::sqrt(dm*dm + d1*d1);
                if (len < 1e-12) continue;
                new_main = cmain + R * dm / len;
                new_s1   = cs1   + R * d1 / len;
                new_s2   = s2;
            } else {
                // Cylindrical arc in main-s2 plane
                len = std::sqrt(dm*dm + d2*d2);
                if (len < 1e-12) continue;
                new_main = cmain + R * dm / len;
                new_s1   = s1;
                new_s2   = cs2   + R * d2 / len;
            }

            // Reconstruct 3D position from (main, s1, s2) back to (x, y, z)
            Vector3D newPos;
            if (face == "z_max" || face == "z_min") {
                newPos = {new_s1, new_s2, new_main};
            } else if (face == "x_max" || face == "x_min") {
                newPos = {new_main, new_s1, new_s2};
            } else {  // y_max / y_min
                newPos = {new_s1, new_main, new_s2};
            }

            setPos(nid, newPos);
            moved++;
        }
        totalMoved += moved;
    }
        totalMovedAll += totalMoved;
    } // end pid loop

    std::ostringstream oss;
    oss << "[fillet] " << totalMovedAll << " nodes moved across "
        << pidsToProcess.size() << " part(s), R=" << op.radius
        << " face(s):";
    for (auto& f : op.faces) oss << " " << f;
    infoMessages.push_back(oss.str());
    return true;
}

} // namespace KooRemapper
