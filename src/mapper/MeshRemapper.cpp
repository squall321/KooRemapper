#include "mapper/MeshRemapper.h"
#include <chrono>
#include <cmath>
#include <algorithm>
#include <limits>

namespace KooRemapper {

MeshRemapper::MeshRemapper()
    : bentMesh_(nullptr), flatMesh_(nullptr)
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
        errorMessage_ = "Bent mesh is not a valid structured grid: " +
                       connectivity_.getErrorMessage();
        return false;
    }

    // Assign structured indices
    if (!indexer_.assignIndices(tempMesh, connectivity_)) {
        errorMessage_ = "Failed to assign structured indices: " +
                       indexer_.getErrorMessage();
        return false;
    }

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
    indexer_.assignIndices(tempMesh, connectivity_);
    boundary_.extract(tempMesh);

    // Build parametric mapper
    paramMapper_.build(tempMesh, boundary_, edgeCalc_);

    if (!paramMapper_.isValid()) {
        errorMessage_ = "Failed to build parametric mapper";
        return false;
    }

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
    // Calculate Jacobians for all elements to check for invalid mappings
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
        // Using finite difference approximation
        Vector3D dxdu = (corners[1] + corners[2] + corners[5] + corners[6]) * 0.25 -
                        (corners[0] + corners[3] + corners[4] + corners[7]) * 0.25;
        Vector3D dxdv = (corners[2] + corners[3] + corners[6] + corners[7]) * 0.25 -
                        (corners[0] + corners[1] + corners[4] + corners[5]) * 0.25;
        Vector3D dxdw = (corners[4] + corners[5] + corners[6] + corners[7]) * 0.25 -
                        (corners[0] + corners[1] + corners[2] + corners[3]) * 0.25;

        // Jacobian determinant = dxdu . (dxdv x dxdw)
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

    // Mapping is valid even with some invalid elements (user can decide what to do)
    return true;
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

} // namespace KooRemapper
