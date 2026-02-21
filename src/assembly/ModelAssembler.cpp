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

    for (auto& ni : nodeInfos) {
        int foundCol = -1;
        for (int c = 0; c < static_cast<int>(columns.size()); c++) {
            int refId = columns[c].coordAndId[0].second;
            const auto* refNode = baseMesh_.getNode(refId);
            if (!refNode) continue;
            double refP1 = getAxisCoord(refNode->position, perpAxis1);
            double refP2 = getAxisCoord(refNode->position, perpAxis2);
            if (std::abs(ni.perpCoord1 - refP1) < perpTol &&
                std::abs(ni.perpCoord2 - refP2) < perpTol) {
                foundCol = c;
                break;
            }
        }
        if (foundCol < 0) {
            foundCol = static_cast<int>(columns.size());
            columns.push_back(Column());
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
    // For each column: keep bottom (plane 0) and top (plane oldLayerCount)
    // Create newLayerCount-1 intermediate nodes
    struct NewColumn {
        std::vector<int> nodeIds; // newLayerCount+1 entries: plane 0..newLayerCount
    };
    std::vector<NewColumn> newColumns(columns.size());

    std::set<int> bottomPlaneNodes, topPlaneNodes;
    for (int c = 0; c < static_cast<int>(columns.size()); c++) {
        auto& newCol = newColumns[c];
        newCol.nodeIds.resize(newLayerCount + 1);

        int bottomNodeId = columns[c].coordAndId[0].second;
        int topNodeId = columns[c].coordAndId[nodesPerColumn - 1].second;
        bottomPlaneNodes.insert(bottomNodeId);
        topPlaneNodes.insert(topNodeId);

        const auto* bottomNode = baseMesh_.getNode(bottomNodeId);
        const auto* topNode = baseMesh_.getNode(topNodeId);

        newCol.nodeIds[0] = bottomNodeId;
        newCol.nodeIds[newLayerCount] = topNodeId;

        // Create intermediate nodes
        double cumThick = 0;
        for (int p = 1; p < newLayerCount; p++) {
            cumThick += op.layers[p - 1].thickness;
            double frac = cumThick / sumThickness;

            // Interpolate position
            double nx = bottomNode->position.x + frac * (topNode->position.x - bottomNode->position.x);
            double ny = bottomNode->position.y + frac * (topNode->position.y - bottomNode->position.y);
            double nz = bottomNode->position.z + frac * (topNode->position.z - bottomNode->position.z);

            int newId = ++maxNodeId_;
            newCol.nodeIds[p] = newId;
            addedNodes_.push_back({newId, nx, ny, nz});
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
    bool isShell = (op.elementType == "shell");
    bool isTshell = (op.elementType == "tshell");

    std::set<int> emittedMids; // Track which MIDs have already been written

    int totalNewElems = 0;
    for (int layerIdx = 0; layerIdx < newLayerCount; layerIdx++) {
        const auto& layerDef = op.layers[layerIdx];

        // Assign new PID and SECID for this layer
        int newPid = ++maxPartId_;
        int newSecId = ++maxSectionId_;

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
            kwBlock << "$#     t1        t2        t3        t4\n";
            kwBlock << std::setw(10) << std::fixed << std::setprecision(6) << layerDef.thickness
                    << std::setw(10) << std::fixed << std::setprecision(6) << layerDef.thickness
                    << std::setw(10) << std::fixed << std::setprecision(6) << layerDef.thickness
                    << std::setw(10) << std::fixed << std::setprecision(6) << layerDef.thickness << "\n";
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
        kwBlock << "*PART\n";
        kwBlock << "Restack Layer " << (layerIdx + 1) << "\n";
        kwBlock << "$#     pid     secid       mid\n";
        kwBlock << std::setw(10) << newPid << std::setw(10) << newSecId << std::setw(10) << actualMid << "\n";

        addedKeywordBlocks_.push_back(kwBlock.str());

        // Generate elements
        for (const auto& fq : footprint) {
            if (isShell) {
                // Shell: 4-node element at mid-surface of this layer
                // Use bottom plane nodes of this layer
                AddedShellElement se;
                se.id = ++maxElementId_;
                se.pid = newPid;
                for (int n = 0; n < 4; n++) {
                    se.nodeIds[n] = newColumns[fq.colIdx[n]].nodeIds[layerIdx];
                }
                addedShellElements_.push_back(se);
            } else {
                // Solid/Tshell: 8-node element
                AddedElement ae;
                ae.id = ++maxElementId_;
                ae.pid = newPid;
                ae.type = ElementType::HEX8;
                ae.isTshell = isTshell;
                for (int n = 0; n < 4; n++) {
                    ae.nodeIds[n] = newColumns[fq.colIdx[n]].nodeIds[layerIdx];      // bottom face
                    ae.nodeIds[n + 4] = newColumns[fq.colIdx[n]].nodeIds[layerIdx + 1]; // top face
                }
                addedElements_.push_back(ae);
            }
            totalNewElems++;
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

    std::ostringstream msg;
    msg << "  Restack Part " << op.targetPid << " (" << axisName << "-axis): "
        << oldLayerCount << " layers -> " << newLayerCount << " layers, "
        << footprint.size() << " elements/layer, "
        << columns.size() << " columns";
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
            std::transform(upper.begin(), upper.end(), upper.begin(), ::toupper);
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
            std::transform(upper.begin(), upper.end(), upper.begin(), ::toupper);

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
    Vector3D offsetDir = parseOffsetDirection(op.offsetDirection, sourceSurface);
    std::cout << "[INFO] Offset direction: ("
              << offsetDir.x << ", " << offsetDir.y << ", " << offsetDir.z << ")\n";

    // Check if using local normals
    bool usingLocalNormals = op.useLocalNormals &&
                             (op.offsetDirection == "+normal" || op.offsetDirection == "normal" ||
                              op.offsetDirection == "-normal");
    if (usingLocalNormals) {
        std::cout << "[INFO] Using local normals (per-node averaged)\n";
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
                if (op.offsetDirection == "-normal") {
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
            if (op.offsetDirection == "-normal") {
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

        // Self-intersection check (only for +normal/-normal directions with concave surfaces)
        if (op.offsetDirection == "+normal" || op.offsetDirection == "-normal") {
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

    // Create solid elements
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
                // Normal case: shell is bottom, extrude upward
                // Bottom face (layer)
                for (int i = 0; i < 4; ++i) {
                    int origNid = shell.nodeIds[i];
                    elem.nodeIds[i] = bottomToTopNodes[layer][origNid];
                }

                // Top face (layer+1)
                for (int i = 0; i < 4; ++i) {
                    int origNid = shell.nodeIds[i];
                    elem.nodeIds[i+4] = bottomToTopNodes[layer+1][origNid];
                }
            } else {
                // Flipped case: shell is top, extrude downward
                // Bottom face (layer+1): reversed winding
                elem.nodeIds[0] = bottomToTopNodes[layer+1][shell.nodeIds[0]];
                elem.nodeIds[1] = bottomToTopNodes[layer+1][shell.nodeIds[3]];
                elem.nodeIds[2] = bottomToTopNodes[layer+1][shell.nodeIds[2]];
                elem.nodeIds[3] = bottomToTopNodes[layer+1][shell.nodeIds[1]];

                // Top face (layer): reversed winding
                elem.nodeIds[4] = bottomToTopNodes[layer][shell.nodeIds[0]];
                elem.nodeIds[5] = bottomToTopNodes[layer][shell.nodeIds[3]];
                elem.nodeIds[6] = bottomToTopNodes[layer][shell.nodeIds[2]];
                elem.nodeIds[7] = bottomToTopNodes[layer][shell.nodeIds[1]];
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

    // Create solid elements
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

} // namespace KooRemapper
