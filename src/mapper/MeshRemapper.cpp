#include "mapper/MeshRemapper.h"
#include <chrono>
#include <cmath>
#include <algorithm>
#include <limits>

namespace KooRemapper {

MeshRemapper::MeshRemapper()
    : bentMesh_(nullptr), flatMesh_(nullptr), flipI_(false), flipJ_(false), flipK_(false)
{}

void MeshRemapper::setBentMesh(const Mesh* mesh) {
    bentMesh_ = mesh;
}

void MeshRemapper::setFlatMesh(const Mesh* mesh) {
    flatMesh_ = mesh;
}

bool MeshRemapper::performMapping() {
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
    reportProgress(45);

    // Step 4: Map nodes
    if (!step4_MapNodes()) {
        return false;
    }
    reportProgress(70);

    // Step 5: Copy elements
    if (!step5_CopyElements()) {
        return false;
    }
    reportProgress(85);

    // Step 6: Validate result
    if (!step6_ValidateResult()) {
        return false;
    }
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

    for (const auto& pair : nodes) {
        const Node& flatNode = pair.second;

        // Convert flat position to parametric coordinates (0-1)
        // Simple arc-length based calculation
        double u = 0.0, v = 0.0, w = 0.0;

        if (flatSizeI > 0) {
            u = (flatNode.position.x - minBound.x) / flatSizeI;
            u = std::max(0.0, std::min(1.0, u));
        }
        if (flatSizeJ > 0) {
            v = (flatNode.position.y - minBound.y) / flatSizeJ;
            v = std::max(0.0, std::min(1.0, v));
        }
        if (flatSizeK > 0) {
            w = (flatNode.position.z - minBound.z) / flatSizeK;
            w = std::max(0.0, std::min(1.0, w));
        }

        // Apply flip to match FlatMeshGenerator's coordinate system
        // FlatMeshGenerator flips j/k when bent mesh's radial direction goes inward
        // We must apply the same flip here for consistent mapping
        if (flipI_) {
            u = 1.0 - u;
        }
        if (flipJ_) {
            v = 1.0 - v;
        }
        if (flipK_) {
            w = 1.0 - w;
        }

        // Map to bent position using edge-based interpolation
        // EdgeInterpolator now uses arc-length based interpolation,
        // ensuring physical correspondence between flat and bent meshes
        Vector3D bentPosition = paramMapper_.mapToPhysical(u, v, w);

        // Add node to result mesh
        Node mappedNode(flatNode.id, bentPosition);
        mappedNode.setMappedPosition(bentPosition);
        resultMesh_.addNode(mappedNode);

        stats_.nodesProcessed++;
    }

    return true;
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
    // This must match FlatMeshGenerator's logic exactly
    // Analyze bent mesh corners to determine if i/j/k directions need flipping
    //
    // Goal: In flat mesh, outer layer (larger Y in bent mesh) should have
    // larger coordinate value. FlatMeshGenerator applies flipJ/flipK when
    // the bent mesh's j or k direction goes toward smaller Y (inward).
    // We must apply the same flip here for roundtrip consistency.

    flipI_ = false;
    flipJ_ = false;
    flipK_ = false;

    const auto& corners = paramMapper_.getCorners();

    // Corner 0: (i=0, j=0, k=0)
    // Corner 1: (i=max, j=0, k=0)  - i direction
    // Corner 3: (i=0, j=max, k=0)  - j direction
    // Corner 4: (i=0, j=0, k=max)  - k direction
    Vector3D c000 = corners[0];
    Vector3D cI00 = corners[1];  // i+ direction from c000
    Vector3D c0J0 = corners[3];  // j+ direction from c000
    Vector3D c00K = corners[4];  // k+ direction from c000

    Vector3D iDir = cI00 - c000;
    Vector3D jDir = c0J0 - c000;
    Vector3D kDir = c00K - c000;

    // Check i direction - flip if i+ goes toward smaller X (negative X direction)
    // FlatMeshGenerator generates flat mesh with X increasing along i direction
    // So if bent mesh has i+ going toward smaller X, we need to flip
    if (iDir.x < 0) {
        flipI_ = true;
    }

    // Check j direction
    if (std::abs(jDir.y) > std::abs(jDir.z)) {
        // j direction is Y-dominant (radial direction)
        // If jDir.y < 0, j+ goes toward smaller Y (inward)
        // FlatMeshGenerator flips in this case, so we must too
        if (jDir.y < 0) {
            flipJ_ = true;
        }
    }

    // Check k direction
    if (std::abs(kDir.y) > std::abs(kDir.z)) {
        // k direction is Y-dominant (radial direction)
        if (kDir.y < 0) {
            flipK_ = true;
        }
    }
}

} // namespace KooRemapper
