#include "mapper/MeshRemapper.h"
#include <chrono>
#include <cmath>
#include <algorithm>
#include <limits>
#include <vector>
#include <mutex>
#include <cstdlib>
#include <cstdio>

#ifdef USE_OPENMP
#include <omp.h>
#endif

namespace KooRemapper {

MeshRemapper::MeshRemapper()
    : bentMesh_(nullptr), flatMesh_(nullptr), flipI_(false), flipJ_(false), flipK_(false),
      axisMapAuto_(true), useParallel_(true)
{
    axisMap_[0] = 0; axisMap_[1] = 1; axisMap_[2] = 2;  // identity default
}

void MeshRemapper::setBentMesh(const Mesh* mesh) {
    bentMesh_ = mesh;
}

void MeshRemapper::setFlatMesh(const Mesh* mesh) {
    flatMesh_ = mesh;
}

bool MeshRemapper::analyzeBentOnly() {
    errorMessage_.clear();
    if (!bentMesh_) {
        errorMessage_ = "Bent mesh not set";
        return false;
    }
    if (!step1_AnalyzeBentMesh()) return false;
    if (!step2_BuildParametricSpace()) return false;
    return true;
}

bool MeshRemapper::performMapping(bool useParallel) {
    useParallel_ = useParallel;

    auto startTime = std::chrono::high_resolution_clock::now();

    errorMessage_.clear();
    stats_ = MappingStats();

    // Validate inputs
    if (!bentMesh_) {
        errorMessage_ = "Bent mesh not set";
        return false;
    }
    if (!flatMesh_) {
        errorMessage_ = "Flat mesh not set";
        return false;
    }

    reportProgress(0);

    // Step 1: Analyze bent mesh structure
    if (!step1_AnalyzeBentMesh()) {
        return false;
    }
    reportProgress(15);

    // Step 2: Build parametric space
    if (!step2_BuildParametricSpace()) {
        return false;
    }
    reportProgress(30);

    // Step 3: Analyze flat mesh
    if (!step3_AnalyzeFlatMesh()) {
        return false;
    }

    // Step 3.5: Auto-detect axis mapping (detail XYZ -> bent ijk by sorted length)
    if (axisMapAuto_) {
        computeAxisMapping();
    }

    // Step 3.6: Source mesh diagnostics. Counts pre-map jacFlat sign
    // distribution so users know whether the source already had problems.
    analyzeSourceMesh();
    reportProgress(45);

    // Step 4: Map nodes (use parallel version if enabled)
#ifdef USE_OPENMP
    if (useParallel_) {
        if (!step4_MapNodesParallel()) {
            return false;
        }
    } else {
        if (!step4_MapNodes()) {
            return false;
        }
    }
#else
    if (!step4_MapNodes()) {
        return false;
    }
#endif
    reportProgress(70);

    // Step 5: Copy elements
    if (!step5_CopyElements()) {
        return false;
    }

    // Step 5.5: Per-element orientation preservation. correctOrientationBySample
    // (step3.5) applies a single global flip based on a 50-element majority vote.
    // That handles the uniform case -- meshes where all elements share the same
    // winding and all need (or none need) a sign flip. Mixed-orientation source
    // meshes (rare but valid in LS-DYNA) slip through. This step catches those
    // by checking every element individually and swapping connectivity where
    // the mapping inverted the sign.
    reorientMappedElements();

    // Step 5.7: Optional global mirror (--flip-x/y/z). Negates node coords
    // and swaps HEX8 connectivity if axis flip count is odd, so the result
    // stays right-handed in LS-DYNA HEX8 ordering. Reported Jacobian stats
    // in step6 reflect the post-flip mesh.
    if (flipOutX_ || flipOutY_ || flipOutZ_) {
        applyOutputFlip();
    }
    reportProgress(85);

    // Step 6: Validate result (use parallel version if enabled)
#ifdef USE_OPENMP
    if (useParallel_) {
        if (!step6_ValidateResultParallel()) {
            return false;
        }
    } else {
        if (!step6_ValidateResult()) {
            return false;
        }
    }
#else
    if (!step6_ValidateResult()) {
        return false;
    }
#endif
    reportProgress(100);

    auto endTime = std::chrono::high_resolution_clock::now();
    stats_.processingTimeMs = std::chrono::duration<double, std::milli>(
        endTime - startTime).count();

    return true;
}

bool MeshRemapper::step1_AnalyzeBentMesh() {
    // Need non-const copy for modification during indexing
    Mesh tempMesh = *bentMesh_;

    // Build connectivity
    connectivity_.buildConnectivity(tempMesh);

    if (!connectivity_.isStructuredGrid()) {
        // Provide detailed diagnostic info
        auto corners = connectivity_.findCornerElements();
        auto edges = connectivity_.findEdgeElements();
        auto faces = connectivity_.findFaceElements();
        auto interior = connectivity_.findInteriorElements();

        errorMessage_ = "Bent mesh is not a valid structured grid: " +
                       connectivity_.getErrorMessage() +
                       " (corners=" + std::to_string(corners.size()) +
                       ", edges=" + std::to_string(edges.size()) +
                       ", faces=" + std::to_string(faces.size()) +
                       ", interior=" + std::to_string(interior.size()) + ")";
        return false;
    }

    // Assign structured indices
    if (!indexer_.assignIndices(tempMesh, connectivity_)) {
        errorMessage_ = "Failed to assign structured indices: " +
                       indexer_.getErrorMessage();
        return false;
    }

    // Reorder element nodes based on geometry for consistent LS-DYNA ordering
    indexer_.reorderElementNodes(tempMesh);

    // Build index lookup
    indexer_.buildIndexLookup(tempMesh);

    // Extract boundary information
    boundary_.extract(tempMesh);

    // Calculate edge properties
    edgeCalc_.calculateAllEdges(tempMesh, boundary_);

    return true;
}

bool MeshRemapper::step2_BuildParametricSpace() {
    // Need non-const copy for modification during indexing
    Mesh tempMesh = *bentMesh_;

    // Re-run indexing for this mesh
    connectivity_.buildConnectivity(tempMesh);

    if (!indexer_.assignIndices(tempMesh, connectivity_)) {
        errorMessage_ = "Failed to build parametric mapper: indexing failed - " +
                       indexer_.getErrorMessage();
        return false;
    }

    // Reorder element nodes based on geometry for consistent LS-DYNA ordering
    indexer_.reorderElementNodes(tempMesh);

    boundary_.extract(tempMesh);

    // Check if grid dimensions are set
    if (!tempMesh.gridDimensionsSet) {
        errorMessage_ = "Failed to build parametric mapper: grid dimensions not set "
                       "(dimI=" + std::to_string(tempMesh.dimI) +
                       ", dimJ=" + std::to_string(tempMesh.dimJ) +
                       ", dimK=" + std::to_string(tempMesh.dimK) + ")";
        return false;
    }

    // Check corner nodes
    auto cornerNodes = boundary_.getCornerNodes();
    int validCorners = 0;
    std::string cornerDebug = "";
    for (int i = 0; i < 8; ++i) {
        if (cornerNodes[i] != 0 && tempMesh.getNode(cornerNodes[i]) != nullptr) {
            validCorners++;
        }
        cornerDebug += std::to_string(cornerNodes[i]) + " ";
    }

    if (validCorners != 8) {
        errorMessage_ = "Failed to build parametric mapper: only " +
                       std::to_string(validCorners) + "/8 corner nodes found "
                       "(dims=" + std::to_string(tempMesh.dimI) + "x" +
                       std::to_string(tempMesh.dimJ) + "x" +
                       std::to_string(tempMesh.dimK) + ", corners=[" + cornerDebug + "])";
        return false;
    }

    // Build parametric mapper
    paramMapper_.build(tempMesh, boundary_, edgeCalc_);

    if (!paramMapper_.isValid()) {
        errorMessage_ = "Failed to build parametric mapper: internal error";
        return false;
    }

    // Topology diagnostics from build(): closed-loop detection and edge
    // validation. Hard-fail if any axis is genuinely degenerate (coincident
    // corners AND collapsed edge interior) since the mapping cannot recover.
    // Closed-loop is informational only (valid for teardrop / fully-folded
    // bent meshes).
    if (paramMapper_.hasDegenerateEdges()) {
        errorMessage_ = "Bent mesh has degenerate parametric topology: " +
                       paramMapper_.getTopologyDiagnostic();
        return false;
    }
    topologyDiagnostic_ = paramMapper_.getTopologyDiagnostic();

    // Analyze layer orientation to determine flip flags
    // This must match FlatMeshGenerator's logic for roundtrip consistency
    analyzeLayerOrientation();

    return true;
}

bool MeshRemapper::step3_AnalyzeFlatMesh() {
    // Analyze the flat mesh to determine its bounding box
    flatAnalyzer_.analyze(*flatMesh_);

    return true;
}

bool MeshRemapper::step4_MapNodes() {
    // Create result mesh by copying structure
    resultMesh_.clear();
    resultMesh_.setName(flatMesh_->getName() + "_mapped");

    // Get bounding box of flat mesh
    Vector3D minBound, maxBound;
    flatMesh_->calculateBoundingBox(minBound, maxBound);

    // Use flat mesh dimensions for parametric mapping
    double flatSizeI = maxBound.x - minBound.x;
    double flatSizeJ = maxBound.y - minBound.y;
    double flatSizeK = maxBound.z - minBound.z;

    // Map each node from flat mesh to bent mesh
    // Arc-length based parametric mapping:
    //   - Flat mesh X coordinate represents arc-length position along bent mesh centerline
    //   - u = x / totalArcLength gives parametric position in [0, 1]
    //   - EdgeInterpolator uses arc-length based interpolation, so
    //     u maps directly to physical position on bent mesh edges
    //
    // This provides mathematical consistency:
    //   bent -> unfold -> remap = bent (exactly)
    //
    // No special handling needed for U-fold or any other geometry -
    // arc-length based mapping works uniformly for all shapes.
    
    const auto& nodes = flatMesh_->getNodes();
    stats_.nodesProcessed = 0;

    double xyzMin[3] = {minBound.x, minBound.y, minBound.z};
    double xyzSize[3] = {flatSizeI, flatSizeJ, flatSizeK};

    for (const auto& pair : nodes) {
        const Node& flatNode = pair.second;

        // Convert detail XYZ -> bent ijk parametric coordinates via axisMap_
        double xyz[3] = {flatNode.position.x, flatNode.position.y, flatNode.position.z};
        double ijkRatio[3] = {0.0, 0.0, 0.0};

        for (int d = 0; d < 3; ++d) {
            int targetIjk = axisMap_[d];
            if (xyzSize[d] > 0) {
                double r = (xyz[d] - xyzMin[d]) / xyzSize[d];
                r = std::max(0.0, std::min(1.0, r));
                ijkRatio[targetIjk] = r;
            }
        }

        double u = ijkRatio[0];
        double v = ijkRatio[1];
        double w = ijkRatio[2];

        // Apply flip (defined in ijk space) to match FlatMeshGenerator convention
        if (flipI_) u = 1.0 - u;
        if (flipJ_) v = 1.0 - v;
        if (flipK_) w = 1.0 - w;

        // Map to bent position using edge-based interpolation
        Vector3D bentPosition = paramMapper_.mapToPhysical(u, v, w);

        Node mappedNode(flatNode.id, bentPosition);
        mappedNode.setMappedPosition(bentPosition);
        resultMesh_.addNode(mappedNode);

        stats_.nodesProcessed++;
    }

    return true;
}

bool MeshRemapper::step4_MapNodesParallel() {
#ifdef USE_OPENMP
    // Create result mesh by copying structure
    resultMesh_.clear();
    resultMesh_.setName(flatMesh_->getName() + "_mapped");

    // Get bounding box of flat mesh
    Vector3D minBound, maxBound;
    flatMesh_->calculateBoundingBox(minBound, maxBound);

    // Use flat mesh dimensions for parametric mapping
    double flatSizeI = maxBound.x - minBound.x;
    double flatSizeJ = maxBound.y - minBound.y;
    double flatSizeK = maxBound.z - minBound.z;

    // Convert map to vector for parallel processing
    const auto& nodesMap = flatMesh_->getNodes();
    std::vector<std::pair<int, Node>> nodesList(nodesMap.begin(), nodesMap.end());
    int nodeCount = static_cast<int>(nodesList.size());

    // Pre-allocate result vector
    std::vector<Node> mappedNodes(nodeCount);

    double xyzMin[3] = {minBound.x, minBound.y, minBound.z};
    double xyzSize[3] = {flatSizeI, flatSizeJ, flatSizeK};
    int axisMapLocal[3] = {axisMap_[0], axisMap_[1], axisMap_[2]};
    bool flipILocal = flipI_, flipJLocal = flipJ_, flipKLocal = flipK_;

    // Parallel node mapping
    #pragma omp parallel for schedule(dynamic, 100)
    for (int i = 0; i < nodeCount; ++i) {
        const Node& flatNode = nodesList[i].second;

        double xyz[3] = {flatNode.position.x, flatNode.position.y, flatNode.position.z};
        double ijkRatio[3] = {0.0, 0.0, 0.0};

        for (int d = 0; d < 3; ++d) {
            int targetIjk = axisMapLocal[d];
            if (xyzSize[d] > 0) {
                double r = (xyz[d] - xyzMin[d]) / xyzSize[d];
                r = std::max(0.0, std::min(1.0, r));
                ijkRatio[targetIjk] = r;
            }
        }

        double u = ijkRatio[0];
        double v = ijkRatio[1];
        double w = ijkRatio[2];

        if (flipILocal) u = 1.0 - u;
        if (flipJLocal) v = 1.0 - v;
        if (flipKLocal) w = 1.0 - w;

        Vector3D bentPosition = paramMapper_.mapToPhysical(u, v, w);

        Node mappedNode(flatNode.id, bentPosition);
        mappedNode.setMappedPosition(bentPosition);
        mappedNodes[i] = mappedNode;
    }

    // Add all nodes to result mesh (sequential, but fast)
    for (const auto& node : mappedNodes) {
        resultMesh_.addNode(node);
    }

    stats_.nodesProcessed = static_cast<int>(nodeCount);
    return true;
#else
    // Fallback to sequential version if OpenMP not available
    return step4_MapNodes();
#endif
}

bool MeshRemapper::detectUFoldGeometry() const {
    // Detect U-fold by checking if start and end X coordinates of i-edges are similar
    // For U-fold, the mesh starts and ends at approximately the same X position
    const auto& corners = paramMapper_.getCorners();

    // Corner 0 is at (i=0, j=0, k=0), corner 1 is at (i=M, j=0, k=0)
    double startX = corners[0].x;
    double endX = corners[1].x;

    // If start and end X are close (relative to mesh size), it's a U-fold
    double meshSizeEstimate = std::max({
        std::abs(corners[1].x - corners[0].x),
        std::abs(corners[1].y - corners[0].y),
        std::abs(corners[1].z - corners[0].z),
        std::abs(corners[5].x - corners[0].x),
        std::abs(corners[5].z - corners[0].z)
    });

    if (meshSizeEstimate < 1e-10) return false;

    double xDiff = std::abs(endX - startX);

    // If X difference is less than 10% of mesh extent, likely U-fold
    return (xDiff / meshSizeEstimate) < 0.1;
}

bool MeshRemapper::step5_CopyElements() {
    // Copy elements from flat mesh (connectivity is preserved)
    const auto& elements = flatMesh_->getElements();
    stats_.elementsProcessed = 0;

    for (const auto& pair : elements) {
        const Element& flatElem = pair.second;

        // Create element with same connectivity
        Element mappedElem = flatElem;

        // Add to result mesh
        resultMesh_.addElement(mappedElem);

        stats_.elementsProcessed++;
    }

    // Copy parts
    for (const auto& pair : flatMesh_->getParts()) {
        resultMesh_.addPart(pair.second);
    }

    return true;
}

bool MeshRemapper::step6_ValidateResult() {
    // Calculate Jacobian statistics
    // Note: We do NOT fix negative Jacobians here because:
    // 1. The detail flat mesh has correct connectivity that should be preserved
    // 2. Flipping node order would change element orientation, affecting stress calculations
    // 3. If Jacobians are negative, it indicates a mapping direction issue that should be
    //    fixed in the coordinate system logic, not by modifying element connectivity
    stats_.invalidElements = 0;
    stats_.minJacobian = std::numeric_limits<double>::max();
    stats_.maxJacobian = std::numeric_limits<double>::lowest();
    double sumJacobian = 0.0;

    const auto& elements = resultMesh_.getElements();

    for (const auto& pair : elements) {
        const Element& elem = pair.second;

        // Get corner nodes
        std::array<Vector3D, 8> corners;
        bool valid = true;

        for (int idx = 0; idx < 8; ++idx) {
            const Node* node = resultMesh_.getNode(elem.nodeIds[idx]);
            if (!node) {
                valid = false;
                break;
            }
            corners[idx] = node->getEffectivePosition();
        }

        if (!valid) {
            stats_.invalidElements++;
            continue;
        }

        // Calculate Jacobian at element center
        Vector3D dxdu = (corners[1] + corners[2] + corners[5] + corners[6]) * 0.25 -
                        (corners[0] + corners[3] + corners[4] + corners[7]) * 0.25;
        Vector3D dxdv = (corners[2] + corners[3] + corners[6] + corners[7]) * 0.25 -
                        (corners[0] + corners[1] + corners[4] + corners[5]) * 0.25;
        Vector3D dxdw = (corners[4] + corners[5] + corners[6] + corners[7]) * 0.25 -
                        (corners[0] + corners[1] + corners[2] + corners[3]) * 0.25;

        double jacobian = dxdu.dot(dxdv.cross(dxdw));

        stats_.minJacobian = std::min(stats_.minJacobian, jacobian);
        stats_.maxJacobian = std::max(stats_.maxJacobian, jacobian);
        sumJacobian += jacobian;

        if (jacobian <= 0) {
            stats_.invalidElements++;
        }
    }

    if (!elements.empty()) {
        stats_.avgJacobian = sumJacobian / static_cast<double>(elements.size());
    }

    return true;
}

bool MeshRemapper::step6_ValidateResultParallel() {
#ifdef USE_OPENMP
    // Calculate Jacobian statistics using parallel reduction
    stats_.invalidElements = 0;
    stats_.minJacobian = std::numeric_limits<double>::max();
    stats_.maxJacobian = std::numeric_limits<double>::lowest();

    // Convert elements map to vector for parallel processing
    const auto& elementsMap = resultMesh_.getElements();
    std::vector<std::pair<int, Element>> elementsList(elementsMap.begin(), elementsMap.end());
    int elemCount = static_cast<int>(elementsList.size());

    // Global variables for reduction (MSVC OpenMP 2.0 doesn't support min/max reduction)
    double globalMinJac = std::numeric_limits<double>::max();
    double globalMaxJac = std::numeric_limits<double>::lowest();
    double globalSumJac = 0.0;
    int globalInvalid = 0;

    #pragma omp parallel
    {
        // Thread-local variables
        double threadMinJac = std::numeric_limits<double>::max();
        double threadMaxJac = std::numeric_limits<double>::lowest();
        double threadSumJac = 0.0;
        int threadInvalid = 0;

        #pragma omp for schedule(dynamic, 100)
        for (int i = 0; i < elemCount; ++i) {
            const Element& elem = elementsList[i].second;

            // Get corner nodes
            std::array<Vector3D, 8> corners;
            bool valid = true;

            for (int idx = 0; idx < 8; ++idx) {
                const Node* node = resultMesh_.getNode(elem.nodeIds[idx]);
                if (!node) {
                    valid = false;
                    break;
                }
                corners[idx] = node->getEffectivePosition();
            }

            if (!valid) {
                threadInvalid++;
                continue;
            }

            // Calculate Jacobian at element center
            Vector3D dxdu = (corners[1] + corners[2] + corners[5] + corners[6]) * 0.25 -
                            (corners[0] + corners[3] + corners[4] + corners[7]) * 0.25;
            Vector3D dxdv = (corners[2] + corners[3] + corners[6] + corners[7]) * 0.25 -
                            (corners[0] + corners[1] + corners[4] + corners[5]) * 0.25;
            Vector3D dxdw = (corners[4] + corners[5] + corners[6] + corners[7]) * 0.25 -
                            (corners[0] + corners[1] + corners[2] + corners[3]) * 0.25;

            double jacobian = dxdu.dot(dxdv.cross(dxdw));

            threadMinJac = std::min(threadMinJac, jacobian);
            threadMaxJac = std::max(threadMaxJac, jacobian);
            threadSumJac += jacobian;

            if (jacobian <= 0) {
                threadInvalid++;
            }
        }

        // Manual reduction using critical section
        #pragma omp critical
        {
            globalMinJac = std::min(globalMinJac, threadMinJac);
            globalMaxJac = std::max(globalMaxJac, threadMaxJac);
            globalSumJac += threadSumJac;
            globalInvalid += threadInvalid;
        }
    }

    stats_.minJacobian = globalMinJac;
    stats_.maxJacobian = globalMaxJac;
    stats_.invalidElements = globalInvalid;

    if (!elementsMap.empty()) {
        stats_.avgJacobian = globalSumJac / static_cast<double>(elementsMap.size());
    }

    return true;
#else
    // Fallback to sequential version if OpenMP not available
    return step6_ValidateResult();
#endif
}

void MeshRemapper::fixNegativeJacobians() {
    // Fix elements with negative Jacobian by reordering their nodes
    // For HEX8 elements, swapping the bottom and top faces inverts the Jacobian sign
    //
    // This is needed because the detail flat mesh may have element ordering
    // that produces negative Jacobians when mapped to bent geometry.
    //
    // Original: n0,n1,n2,n3 (bottom), n4,n5,n6,n7 (top)
    // Fixed:    n4,n5,n6,n7 (now bottom), n0,n1,n2,n3 (now top)

    auto& elements = resultMesh_.elements;

    for (auto& pair : elements) {
        Element& elem = pair.second;

        if (elem.type != ElementType::HEX8) continue;

        // Get corner positions
        std::array<Vector3D, 8> corners;
        bool valid = true;

        for (int idx = 0; idx < 8; ++idx) {
            const Node* node = resultMesh_.getNode(elem.nodeIds[idx]);
            if (!node) {
                valid = false;
                break;
            }
            corners[idx] = node->getEffectivePosition();
        }

        if (!valid) continue;

        // Calculate Jacobian
        Vector3D dxdu = (corners[1] + corners[2] + corners[5] + corners[6]) * 0.25 -
                        (corners[0] + corners[3] + corners[4] + corners[7]) * 0.25;
        Vector3D dxdv = (corners[2] + corners[3] + corners[6] + corners[7]) * 0.25 -
                        (corners[0] + corners[1] + corners[4] + corners[5]) * 0.25;
        Vector3D dxdw = (corners[4] + corners[5] + corners[6] + corners[7]) * 0.25 -
                        (corners[0] + corners[1] + corners[2] + corners[3]) * 0.25;

        double jacobian = dxdu.dot(dxdv.cross(dxdw));

        if (jacobian < 0) {
            // Swap bottom and top faces to invert Jacobian sign
            std::array<int, 8> oldNodes = elem.nodeIds;
            elem.nodeIds[0] = oldNodes[4];
            elem.nodeIds[1] = oldNodes[5];
            elem.nodeIds[2] = oldNodes[6];
            elem.nodeIds[3] = oldNodes[7];
            elem.nodeIds[4] = oldNodes[0];
            elem.nodeIds[5] = oldNodes[1];
            elem.nodeIds[6] = oldNodes[2];
            elem.nodeIds[7] = oldNodes[3];
        }
    }
}

void MeshRemapper::reportProgress(int percent) {
    if (progressCallback_) {
        progressCallback_(percent);
    }
}

double MeshRemapper::getNeutralSizeI() const {
    return edgeCalc_.getNeutralLengthI();
}

double MeshRemapper::getNeutralSizeJ() const {
    return edgeCalc_.getNeutralLengthJ();
}

double MeshRemapper::getNeutralSizeK() const {
    return edgeCalc_.getNeutralLengthK();
}

void MeshRemapper::analyzeLayerOrientation() {
    // Mirror FlatMeshGenerator's flip behavior so unfold -> map round-trips.
    //
    // FlatMeshGenerator picks (arcAxis, widthAxis, thickAxis) from neutral
    // edge lengths and decides flipJ/flipK from the physical Y direction of
    // its WIDTH and THICKNESS corner edges. To invert those flips during
    // mapping, we must flip the SAME bent axes here -- not bent-i/j/k
    // blindly. The legacy code assumed bent-i was always the arc (so
    // checking iDir.x made sense), which silently inverted thickness for
    // any closed-loop mesh whose indexer labels arc as j or k.

    flipI_ = false;
    flipJ_ = false;
    flipK_ = false;

    int arcAxis = paramMapper_.getArcAxis();
    double bentLen[3] = {
        edgeCalc_.getNeutralLengthI(),
        edgeCalc_.getNeutralLengthJ(),
        edgeCalc_.getNeutralLengthK()
    };

    // Cross-section: smaller of the two non-arc axes is thickness.
    int otherA = -1, otherB = -1;
    for (int a = 0; a < 3; ++a) {
        if (a == arcAxis) continue;
        if (otherA < 0) otherA = a;
        else otherB = a;
    }
    int widthAxis = otherA;
    int thickAxis = otherB;
    if (otherA >= 0 && otherB >= 0) {
        double lenA = bentLen[otherA];
        double lenB = bentLen[otherB];
        double maxLen = std::max(lenA, lenB);
        double rel = (maxLen > 1e-10) ? std::abs(lenA - lenB) / maxLen : 0.0;
        if (rel > 0.1) {
            if (lenA < lenB) { thickAxis = otherA; widthAxis = otherB; }
            else             { thickAxis = otherB; widthAxis = otherA; }
        }
        // For near-tied lengths, FlatMeshGenerator uses a stability cue across
        // arc samples. Replicating that here would require its private state;
        // for the round-trip-critical case (size disparity > 10%) we already
        // match. Tied cases fall back to the indexer's natural ordering,
        // which is what the old code effectively did.
    }

    const auto& corners = paramMapper_.getCorners();
    auto axisMaxCorner = [&](int axis) -> Vector3D {
        // Corner at the +max end of the chosen bent axis with the other two at 0:
        //   axis=0 (i+): corner 1, (M,0,0)
        //   axis=1 (j+): corner 3, (0,N,0)
        //   axis=2 (k+): corner 4, (0,0,P)
        if (axis == 0) return corners[1];
        if (axis == 1) return corners[3];
        return corners[4];
    };

    Vector3D c000 = corners[0];
    Vector3D widthDir = axisMaxCorner(widthAxis) - c000;
    Vector3D thickDir = axisMaxCorner(thickAxis) - c000;

    // Same predicate as FlatMeshGenerator::generateMesh: flip if the cross-
    // section axis's physical Y component dominates Z and points toward -Y.
    bool flipWidth = (std::abs(widthDir.y) > std::abs(widthDir.z)) && (widthDir.y < 0);
    bool flipThick = (std::abs(thickDir.y) > std::abs(thickDir.z)) && (thickDir.y < 0);

    bool flips[3] = {false, false, false};
    flips[widthAxis] = flipWidth;
    flips[thickAxis] = flipThick;
    // Arc axis stays false: FlatMeshGenerator never flips along the arc.
    flipI_ = flips[0];
    flipJ_ = flips[1];
    flipK_ = flips[2];
}

void MeshRemapper::computeAxisMapping() {
    // Match detail XYZ axes to bent ijk axes by sorted arc length.
    //
    // Use BENT mesh's ijk neutral edge lengths directly (NOT unfolded BB physical XYZ).
    // The bent mesh's ijk axes may not be aligned with physical XYZ — e.g. when k (thickness)
    // is along physical X. In that case the unfolded mesh's X length equals k length, not i length.
    // So unfolded BB ranks would mix up ijk identification.
    //
    // ijkSizes[d] is the arc length along the d-th ijk axis (0=i, 1=j, 2=k), directly
    // from edgeCalc_, which is independent of bent mesh orientation in physical space.

    double ijkSizes[3] = {
        edgeCalc_.getNeutralLengthI(),
        edgeCalc_.getNeutralLengthJ(),
        edgeCalc_.getNeutralLengthK()
    };

    Vector3D bMin, bMax;
    flatMesh_->calculateBoundingBox(bMin, bMax);
    double detailSizes[3] = {
        bMax.x - bMin.x,
        bMax.y - bMin.y,
        bMax.z - bMin.z
    };

    // Sort with relative tolerance so near-equal lengths preserve original order.
    auto rankSort = [](double s[3], int rank[3]) {
        rank[0] = 0; rank[1] = 1; rank[2] = 2;
        double maxLen = std::max({s[0], s[1], s[2]});
        double tol = std::max(1e-9, maxLen * 1e-4);  // 0.01% relative tolerance
        std::sort(rank, rank + 3, [&](int a, int b) {
            if (std::abs(s[a] - s[b]) <= tol) return a < b;  // tie -> keep original order
            return s[a] > s[b];
        });
    };

    int ijkRank[3], detailRank[3];
    rankSort(ijkSizes, ijkRank);
    rankSort(detailSizes, detailRank);

    // Same rank -> matched. detail axis detailRank[k] -> bent ijk axis ijkRank[k]
    for (int k = 0; k < 3; ++k) {
        axisMap_[detailRank[k]] = ijkRank[k];
    }

    // Orientation correction. The combined effect of axis permutation parity
    // PLUS the analyzeLayerOrientation flips can flip the mapped Jacobian sign
    // relative to the source (flat) element. Detect this by mapping one valid
    // HEX8 element from the flat mesh and comparing Jacobian signs in flat
    // vs. bent space. If they disagree, toggle one flip to restore matching
    // orientation -- this preserves positive Jacobian for any flat mesh whose
    // own elements are right-handed (the normal case).
    correctOrientationBySample();
}

void MeshRemapper::correctOrientationBySample() {
    // Find a representative HEX8 from the flat mesh to test orientation.
    if (!flatMesh_) return;
    const auto& flatElems = flatMesh_->getElements();

    auto computeJac = [](const std::array<Vector3D, 8>& c) {
        Vector3D dxdu = (c[1] + c[2] + c[5] + c[6]) * 0.25 -
                        (c[0] + c[3] + c[4] + c[7]) * 0.25;
        Vector3D dxdv = (c[2] + c[3] + c[6] + c[7]) * 0.25 -
                        (c[0] + c[1] + c[4] + c[5]) * 0.25;
        Vector3D dxdw = (c[4] + c[5] + c[6] + c[7]) * 0.25 -
                        (c[0] + c[1] + c[2] + c[3]) * 0.25;
        return dxdu.dot(dxdv.cross(dxdw));
    };

    Vector3D minBound, maxBound;
    flatMesh_->calculateBoundingBox(minBound, maxBound);
    double xyzMin[3] = {minBound.x, minBound.y, minBound.z};
    double xyzSize[3] = {maxBound.x - minBound.x,
                         maxBound.y - minBound.y,
                         maxBound.z - minBound.z};

    auto mapOne = [&](const Vector3D& flatPos) -> Vector3D {
        double xyz[3] = {flatPos.x, flatPos.y, flatPos.z};
        double ijkRatio[3] = {0.0, 0.0, 0.0};
        for (int d = 0; d < 3; ++d) {
            int targetIjk = axisMap_[d];
            if (xyzSize[d] > 0) {
                double r = (xyz[d] - xyzMin[d]) / xyzSize[d];
                r = std::max(0.0, std::min(1.0, r));
                ijkRatio[targetIjk] = r;
            }
        }
        double u = ijkRatio[0], v = ijkRatio[1], w = ijkRatio[2];
        if (flipI_) u = 1.0 - u;
        if (flipJ_) v = 1.0 - v;
        if (flipK_) w = 1.0 - w;
        return paramMapper_.mapToPhysical(u, v, w);
    };

    // Try several elements; majority vote in case some are degenerate.
    int posVotes = 0, negVotes = 0;
    int tried = 0;
    const int maxTry = 50;
    for (const auto& pair : flatElems) {
        if (tried >= maxTry) break;
        const Element& elem = pair.second;
        if (elem.type != ElementType::HEX8) continue;

        std::array<Vector3D, 8> flatCorners;
        std::array<Vector3D, 8> bentCorners;
        bool valid = true;
        for (int idx = 0; idx < 8; ++idx) {
            const Node* n = flatMesh_->getNode(elem.nodeIds[idx]);
            if (!n) { valid = false; break; }
            flatCorners[idx] = n->position;
        }
        if (!valid) continue;

        double jacFlat = computeJac(flatCorners);
        if (std::abs(jacFlat) < 1e-12) continue;  // skip degenerate

        for (int idx = 0; idx < 8; ++idx) {
            bentCorners[idx] = mapOne(flatCorners[idx]);
        }
        double jacBent = computeJac(bentCorners);
        if (std::abs(jacBent) < 1e-12) continue;

        bool sameSign = (jacFlat > 0) == (jacBent > 0);
        if (sameSign) ++posVotes;
        else          ++negVotes;
        ++tried;
    }

    bool toggled = false;
    char toggledAxis = '-';
    if (negVotes > posVotes) {
        // Choose which axis to flip. Any single flip restores even parity,
        // but for closed-loop meshes flipping the arc axis can introduce
        // wrap-around artifacts (the arc's seam is at param 0 and 1;
        // flipping inverts the seam direction). Prefer the shortest non-arc
        // axis (typically the thickness direction) because it is the least
        // sensitive to direction reversal -- a thickness flip just swaps
        // inside/outside surface labeling, which is harmless.
        int arcAxis = paramMapper_.getArcAxis();
        double bentLen[3] = {
            edgeCalc_.getNeutralLengthI(),
            edgeCalc_.getNeutralLengthJ(),
            edgeCalc_.getNeutralLengthK()
        };
        int chosen = -1;
        double shortestLen = 0.0;
        for (int a = 0; a < 3; ++a) {
            if (a == arcAxis) continue;
            if (chosen < 0 || bentLen[a] < shortestLen) {
                chosen = a;
                shortestLen = bentLen[a];
            }
        }
        if (chosen < 0) chosen = 0;  // fallback
        switch (chosen) {
            case 0: flipI_ = !flipI_; toggledAxis = 'i'; break;
            case 1: flipJ_ = !flipJ_; toggledAxis = 'j'; break;
            case 2: flipK_ = !flipK_; toggledAxis = 'k'; break;
        }
        toggled = true;
    }

    // Diagnostics: enable with KOO_MAP_DEBUG=1 env var to see exactly why a
    // mesh fails. Prints: axisMap permutation, all flip states, the sample
    // jacFlat/jacBent values, and the toggle decision. Without this, we
    // cannot tell whether the sample agreed (so no toggle was applied) but
    // the bulk of the mesh disagreed, or whether toggling didn't actually
    // restore positive Jacobians.
    const char* dbg = std::getenv("KOO_MAP_DEBUG");
    if (dbg && std::string(dbg) != "0") {
        std::fprintf(stderr,
            "[KOO_MAP_DEBUG] axisMap detail->bent: X->%d Y->%d Z->%d\n",
            axisMap_[0], axisMap_[1], axisMap_[2]);
        std::fprintf(stderr,
            "[KOO_MAP_DEBUG] flips after correction: I=%d J=%d K=%d (toggled=%d, axis=%c)\n",
            (int)flipI_, (int)flipJ_, (int)flipK_, (int)toggled, toggledAxis);
        std::fprintf(stderr,
            "[KOO_MAP_DEBUG] sample votes: same-sign=%d opp-sign=%d (tried=%d)\n",
            posVotes, negVotes, tried);

        // Bent topology dump: 8 corner positions + 8 parametric-cube
        // corner evaluations. If mapToPhysical at (u,v,w)=(0/1,0/1,0/1)
        // does NOT equal corners_[0..7], the parametric mapper is broken
        // for this topology.
        const auto& corners = paramMapper_.getCorners();
        std::fprintf(stderr,
            "[KOO_MAP_DEBUG] bent neutral lengths: i=%.4e j=%.4e k=%.4e arcAxis=%d\n",
            edgeCalc_.getNeutralLengthI(),
            edgeCalc_.getNeutralLengthJ(),
            edgeCalc_.getNeutralLengthK(),
            paramMapper_.getArcAxis());
        for (int c = 0; c < 8; ++c) {
            int ui = (c & 1) ? 1 : 0;  // bit 0 -> i
            int vi = (c & 2) ? 1 : 0;  // bit 1 -> j
            int wi = (c & 4) ? 1 : 0;  // bit 2 -> k
            // LS-DYNA hex corner index for (ui,vi,wi):
            //   0: (0,0,0) idx 0    1: (1,0,0) idx 1
            //   2: (0,1,0) idx 3    3: (1,1,0) idx 2
            //   4: (0,0,1) idx 4    5: (1,0,1) idx 5
            //   6: (0,1,1) idx 7    7: (1,1,1) idx 6
            int hexIdx;
            switch (c) {
                case 0: hexIdx = 0; break;
                case 1: hexIdx = 1; break;
                case 2: hexIdx = 3; break;
                case 3: hexIdx = 2; break;
                case 4: hexIdx = 4; break;
                case 5: hexIdx = 5; break;
                case 6: hexIdx = 7; break;
                case 7: hexIdx = 6; break;
                default: hexIdx = 0;
            }
            Vector3D paramPos = paramMapper_.mapToPhysical((double)ui, (double)vi, (double)wi);
            const Vector3D& cornerPos = corners[hexIdx];
            std::fprintf(stderr,
                "[KOO_MAP_DEBUG]   corner(uvw=%d%d%d) hex[%d]=(%.6e,%.6e,%.6e)  map(uvw)=(%.6e,%.6e,%.6e)\n",
                ui, vi, wi, hexIdx,
                cornerPos.x, cornerPos.y, cornerPos.z,
                paramPos.x,  paramPos.y,  paramPos.z);
        }
        // Mid-point evaluations: scan each parametric axis in isolation
        // (others held at 0) to see if the curve actually moves. If
        // mapToPhysical(0.5, 0, 0) ~= mapToPhysical(0, 0, 0), the i-axis
        // interpolation is collapsed -> Jacobian collapse explained.
        const double pts[3] = {0.0, 0.5, 1.0};
        for (int axis = 0; axis < 3; ++axis) {
            for (int s = 0; s < 3; ++s) {
                double u = (axis == 0) ? pts[s] : 0.0;
                double v = (axis == 1) ? pts[s] : 0.0;
                double w = (axis == 2) ? pts[s] : 0.0;
                Vector3D p = paramMapper_.mapToPhysical(u, v, w);
                std::fprintf(stderr,
                    "[KOO_MAP_DEBUG]   axis=%c sweep t=%.1f -> (%.6e,%.6e,%.6e)\n",
                    "ijk"[axis], pts[s], p.x, p.y, p.z);
            }
        }

        // Print first few sample jacFlat/jacBent pairs + dxdu/dv/dw vectors.
        // The dxd*_jac vectors expose WHICH parametric direction collapsed:
        // if |dxdu_jac| ~ machine eps but |dxdv_jac|, |dxdw_jac| are
        // reasonable, the i-axis mapping is broken (and likewise for j/k).
        auto computeJacWithVectors = [](const std::array<Vector3D, 8>& c,
                                        Vector3D& du, Vector3D& dv, Vector3D& dw) {
            du = (c[1] + c[2] + c[5] + c[6]) * 0.25 -
                 (c[0] + c[3] + c[4] + c[7]) * 0.25;
            dv = (c[2] + c[3] + c[6] + c[7]) * 0.25 -
                 (c[0] + c[1] + c[4] + c[5]) * 0.25;
            dw = (c[4] + c[5] + c[6] + c[7]) * 0.25 -
                 (c[0] + c[1] + c[2] + c[3]) * 0.25;
            return du.dot(dv.cross(dw));
        };
        auto vmag = [](const Vector3D& v) {
            return std::sqrt(v.x*v.x + v.y*v.y + v.z*v.z);
        };
        int printed = 0;
        for (const auto& pair : flatElems) {
            if (printed >= 5) break;
            const Element& elem = pair.second;
            if (elem.type != ElementType::HEX8) continue;
            std::array<Vector3D, 8> fc, bc;
            bool ok = true;
            for (int idx = 0; idx < 8; ++idx) {
                const Node* n = flatMesh_->getNode(elem.nodeIds[idx]);
                if (!n) { ok = false; break; }
                fc[idx] = n->position;
            }
            if (!ok) continue;
            Vector3D du_f, dv_f, dw_f;
            double jf = computeJacWithVectors(fc, du_f, dv_f, dw_f);
            for (int idx = 0; idx < 8; ++idx) bc[idx] = mapOne(fc[idx]);
            Vector3D du_b, dv_b, dw_b;
            double jb = computeJacWithVectors(bc, du_b, dv_b, dw_b);
            std::fprintf(stderr,
                "[KOO_MAP_DEBUG]   elem %d: jacFlat=%+.4e jacBent=%+.4e\n",
                pair.first, jf, jb);
            std::fprintf(stderr,
                "[KOO_MAP_DEBUG]     bent dxd*_jac magnitudes: u=%.4e v=%.4e w=%.4e\n",
                vmag(du_b), vmag(dv_b), vmag(dw_b));
            printed++;
        }
    }
}

void MeshRemapper::analyzeSourceMesh() {
    // Pre-map source mesh diagnostic: count HEX8 elements by Jacobian sign
    // in the source flat mesh. This tells the user whether their input
    // already had problems before mapping started, separating mesh-side
    // bugs from mapping-side bugs.
    stats_.sourceHex8Count = 0;
    stats_.sourcePosJacCount = 0;
    stats_.sourceNegJacCount = 0;
    stats_.sourceDegenerateCount = 0;
    stats_.sourceMinJac = std::numeric_limits<double>::max();
    stats_.sourceMaxJac = std::numeric_limits<double>::lowest();

    if (!flatMesh_) return;

    auto computeJac = [](const std::array<Vector3D, 8>& c) {
        Vector3D dxdu = (c[1] + c[2] + c[5] + c[6]) * 0.25 -
                        (c[0] + c[3] + c[4] + c[7]) * 0.25;
        Vector3D dxdv = (c[2] + c[3] + c[6] + c[7]) * 0.25 -
                        (c[0] + c[1] + c[4] + c[5]) * 0.25;
        Vector3D dxdw = (c[4] + c[5] + c[6] + c[7]) * 0.25 -
                        (c[0] + c[1] + c[2] + c[3]) * 0.25;
        return dxdu.dot(dxdv.cross(dxdw));
    };

    for (const auto& pair : flatMesh_->getElements()) {
        const Element& elem = pair.second;
        if (elem.type != ElementType::HEX8) continue;
        std::array<Vector3D, 8> c;
        bool ok = true;
        for (int i = 0; i < 8; ++i) {
            const Node* n = flatMesh_->getNode(elem.nodeIds[i]);
            if (!n) { ok = false; break; }
            c[i] = n->position;
        }
        if (!ok) continue;
        double j = computeJac(c);
        ++stats_.sourceHex8Count;
        if (std::abs(j) < 1e-15)      ++stats_.sourceDegenerateCount;
        else if (j > 0)               ++stats_.sourcePosJacCount;
        else                          ++stats_.sourceNegJacCount;
        if (j < stats_.sourceMinJac) stats_.sourceMinJac = j;
        if (j > stats_.sourceMaxJac) stats_.sourceMaxJac = j;
    }

    if (stats_.sourceHex8Count == 0) {
        stats_.sourceMinJac = 0;
        stats_.sourceMaxJac = 0;
    }
}

void MeshRemapper::reorientMappedElements() {
    // Per-element orientation preservation.
    //
    // For each HEX8 element, compare Jacobian sign in the source flat mesh
    // vs. the mapped result. If the signs disagree, the mapping inverted
    // orientation for this element -- swap n[0..3] <-> n[4..7] to restore
    // matching sign. A right-handed source element stays right-handed.
    //
    // Connectivity swap semantics:
    //   - Swapping bottom/top faces reverses local ζ (k) while ξ,η are
    //     preserved. This is a reflection, not a rotation.
    //   - Physical geometry of the element is unchanged (same 8 corner
    //     points, just relabeled). Jacobian magnitude is preserved.
    //
    // Stress / history-variable handling (for future workflows that
    // propagate stress through map -- currently the map pipeline does not
    // read or write *INITIAL_STRESS_SOLID):
    //   - LS-DYNA *INITIAL_STRESS_SOLID stores stress tensor components
    //     in GLOBAL coordinates. Global stress is invariant under element
    //     relabeling, so the numeric stress values stay unchanged.
    //   - For NINT = 1 (default hex), there is a single integration point
    //     at the centroid. Its physical location is identical before and
    //     after swap, so the 1 stress tuple stays unchanged.
    //   - For NINT > 1 (e.g. 2x2x2 Gauss), integration points live at
    //     natural-coord positions like (±1/sqrt3, ±1/sqrt3, ±1/sqrt3).
    //     Swap flips ζ, so the mapped NINT list must be reordered to pair
    //     each new integration-point position with the correct stress
    //     tuple. The pairing is: (ξ,η,+ζ_k) <-> (ξ,η,-ζ_k), which for
    //     Gauss-ordered 8-point lists swaps lower 4 with upper 4.
    //   - Currently stress is not attached to Element, so no action here.
    //     If added later, the reorder should happen at the same site
    //     where the connectivity swap is executed, using NINT from the
    //     element's section card.
    if (!flatMesh_) return;

    auto computeJac = [](const std::array<Vector3D, 8>& c) {
        Vector3D dxdu = (c[1] + c[2] + c[5] + c[6]) * 0.25 -
                        (c[0] + c[3] + c[4] + c[7]) * 0.25;
        Vector3D dxdv = (c[2] + c[3] + c[6] + c[7]) * 0.25 -
                        (c[0] + c[1] + c[4] + c[5]) * 0.25;
        Vector3D dxdw = (c[4] + c[5] + c[6] + c[7]) * 0.25 -
                        (c[0] + c[1] + c[2] + c[3]) * 0.25;
        return dxdu.dot(dxdv.cross(dxdw));
    };

    const auto& flatElems = flatMesh_->getElements();
    auto& resultElems = resultMesh_.elements;
    int reoriented = 0;

    for (auto& pair : resultElems) {
        Element& mapped = pair.second;
        if (mapped.type != ElementType::HEX8) continue;

        auto fIt = flatElems.find(pair.first);
        if (fIt == flatElems.end()) continue;
        const Element& flat = fIt->second;

        // jacFlat from source corner positions
        std::array<Vector3D, 8> fc;
        bool ok = true;
        for (int i = 0; i < 8; ++i) {
            const Node* n = flatMesh_->getNode(flat.nodeIds[i]);
            if (!n) { ok = false; break; }
            fc[i] = n->position;
        }
        if (!ok) continue;
        double jacFlat = computeJac(fc);
        if (std::abs(jacFlat) < 1e-15) continue;  // degenerate source, skip

        // jacBent from mapped corner positions (after step4)
        std::array<Vector3D, 8> bc;
        for (int i = 0; i < 8; ++i) {
            const Node* n = resultMesh_.getNode(mapped.nodeIds[i]);
            if (!n) { ok = false; break; }
            bc[i] = n->getEffectivePosition();
        }
        if (!ok) continue;
        double jacBent = computeJac(bc);
        if (std::abs(jacBent) < 1e-15) continue;  // degenerate mapped, leave alone

        // Two modes:
        //   - default (forcePositive_=false): preserve source sign. Swap
        //     only when mapping flipped sign relative to the source. A
        //     left-handed source stays left-handed.
        //   - force-positive: ignore source sign and swap whenever the
        //     mapped Jacobian is negative. Use this when the source mesh
        //     has unreliable winding and a strictly LS-DYNA-valid output
        //     is required.
        bool needSwap;
        if (forcePositive_) {
            needSwap = (jacBent < 0);
        } else {
            needSwap = ((jacFlat > 0) != (jacBent > 0));
        }
        if (!needSwap) continue;

        // Sign mismatch: swap bottom/top to restore desired orientation.
        std::array<int, 8> orig = mapped.nodeIds;
        mapped.nodeIds[0] = orig[4]; mapped.nodeIds[1] = orig[5];
        mapped.nodeIds[2] = orig[6]; mapped.nodeIds[3] = orig[7];
        mapped.nodeIds[4] = orig[0]; mapped.nodeIds[5] = orig[1];
        mapped.nodeIds[6] = orig[2]; mapped.nodeIds[7] = orig[3];
        ++reoriented;
    }

    stats_.reorientedElements = reoriented;
}

void MeshRemapper::applyOutputFlip() {
    // Mirror node coordinates along requested axes.
    auto& nodes = resultMesh_.nodes;
    for (auto& pair : nodes) {
        Node& n = pair.second;
        Vector3D pos = n.getEffectivePosition();
        if (flipOutX_) pos.x = -pos.x;
        if (flipOutY_) pos.y = -pos.y;
        if (flipOutZ_) pos.z = -pos.z;
        n.position = pos;
        n.setMappedPosition(pos);
    }

    // Each axis mirror reverses the local handedness. Two mirrors compose
    // to a rotation (handedness preserved); three mirrors flip again.
    // Compensate odd parity by swapping bottom/top face per HEX8.
    int parity = (int)flipOutX_ + (int)flipOutY_ + (int)flipOutZ_;
    if (parity % 2 == 1) {
        for (auto& pair : resultMesh_.elements) {
            Element& e = pair.second;
            if (e.type != ElementType::HEX8) continue;
            std::array<int, 8> orig = e.nodeIds;
            e.nodeIds[0] = orig[4]; e.nodeIds[1] = orig[5];
            e.nodeIds[2] = orig[6]; e.nodeIds[3] = orig[7];
            e.nodeIds[4] = orig[0]; e.nodeIds[5] = orig[1];
            e.nodeIds[6] = orig[2]; e.nodeIds[7] = orig[3];
        }
    }
}

} // namespace KooRemapper
