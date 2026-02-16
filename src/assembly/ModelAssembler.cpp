#include "assembly/ModelAssembler.h"
#include "assembly/DeflectionGrid.h"
#include "assembly/FormulaEvaluator.h"
#include "assembly/ClosedLoop.h"
#include "assembly/IndentProfile.h"
#include "assembly/ShellCurvature.h"
#include "parser/KFileReader.h"
#include "parser/ShellReader.h"
#include "parser/DynainWriter.h"
#include "mapper/ShellMapper.h"
#include "analysis/ElementAnalyzer.h"
#include "analysis/StrainTensor.h"
#include "analysis/StressTensor.h"
#include "analysis/MaterialModel.h"
#include <fstream>
#include <sstream>
#include <iomanip>
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
            } else if (inSectionSolid && upper[0] == '*') {
                inSectionSolid = false;
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

        // Comment/empty lines: pass through
        if (isCommentLine(line) || trimmed.empty()) {
            output << line << "\n";
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
            int elemId = parseElementIdFromLine(line);
            if (elemId > 0 && removedElementIds_.count(elemId) > 0) {
                continue;  // Skip removed element
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
            output << line << "\n";
        }
        else if (currentSection == Section::SHELL_ELEMENT) {
            int elemId = parseElementIdFromLine(line);
            if (elemId > 0 && removedElementIds_.count(elemId) > 0) {
                continue;
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
            output << line << "\n";
        }
        else {
            // *SECTION_SOLID ELFORM rewrite for TET10/HEX20 conversion
            if (inSectionSolid && !isCommentLine(line) && !line.empty() &&
                line.find_first_not_of(" \t") != std::string::npos &&
                !solidSectionElforms_.empty()) {
                sectionSolidDataLine++;
                if (sectionSolidDataLine == 1) {
                    try {
                        int secId = std::stoi(line.substr(0, 10));
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
            output << line << "\n";
        }
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

} // namespace KooRemapper
