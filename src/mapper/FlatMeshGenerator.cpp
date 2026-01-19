#include "mapper/FlatMeshGenerator.h"
#include <cmath>
#include <algorithm>
#include <limits>
#include <set>

namespace KooRemapper {

FlatMeshGenerator::FlatMeshGenerator()
    : flatLengthI_(0), flatLengthJ_(0), flatLengthK_(0)
    , dimI_(0), dimJ_(0), dimK_(0)
{}

Mesh FlatMeshGenerator::generateFlatMesh(const Mesh& bentMesh) {
    errorMessage_.clear();

    // Step 1: Analyze bent mesh structure
    if (!analyzeBentMesh(bentMesh)) {
        return Mesh();
    }

    // Step 2: Calculate flat dimensions
    calculateFlatDimensions();

    // Step 3: Generate the flat mesh
    return generateMesh();
}

bool FlatMeshGenerator::analyzeBentMesh(const Mesh& bentMesh) {
    // Store original mesh for preserving element connectivity
    originalMesh_ = bentMesh;

    // Make a copy for analysis (we need to modify it for indexing)
    analyzedMesh_ = bentMesh;

    // Build connectivity
    connectivity_.buildConnectivity(analyzedMesh_);

    if (!connectivity_.isStructuredGrid()) {
        errorMessage_ = "Input mesh is not a valid structured grid: " +
                       connectivity_.getErrorMessage();
        return false;
    }

    // Assign structured indices
    if (!indexer_.assignIndices(analyzedMesh_, connectivity_)) {
        errorMessage_ = "Failed to assign structured indices: " +
                       indexer_.getErrorMessage();
        return false;
    }

    // Reorder element nodes to match LS-DYNA standard ordering
    // This is critical for getNodeAt() to work correctly
    // Note: This modifies analyzedMesh_, but we preserve originalMesh_ for element connectivity
    indexer_.reorderElementNodes(analyzedMesh_);

    // Build index lookup
    indexer_.buildIndexLookup(analyzedMesh_);

    dimI_ = indexer_.getDimI();
    dimJ_ = indexer_.getDimJ();
    dimK_ = indexer_.getDimK();

    // Extract boundary information
    boundary_.extract(analyzedMesh_);

    // Calculate edge properties
    edgeCalc_.calculateAllEdges(analyzedMesh_, boundary_);

    // Analyze cross-section axes
    analyzeCrossSectionAxes();

    return true;
}

void FlatMeshGenerator::calculateFlatDimensions() {
    // Compute arc-length along the centerline for X dimension
    auto arcLengths = computeCenterlineArcLengths();
    if (!arcLengths.empty()) {
        flatLengthI_ = arcLengths.back();
    }

    // J dimension: use neutral length from edge calculator
    flatLengthJ_ = edgeCalc_.getNeutralLengthJ();

    // K dimension: use neutral length from edge calculator
    flatLengthK_ = edgeCalc_.getNeutralLengthK();
}

std::vector<double> FlatMeshGenerator::computeCenterlineArcLengths() {
    // Compute arc-lengths using the average of 4 i-edges
    // This ensures exact correspondence with EdgeInterpolator's arc-length based
    // interpolation, because both use the same edge arc-length data.
    //
    // The 4 i-edges are:
    //   Edge 0: j=0, k=0
    //   Edge 1: j=N, k=0
    //   Edge 2: j=0, k=P
    //   Edge 3: j=N, k=P
    //
    // For each i position, we compute the average cumulative arc-length
    // across these 4 edges. This gives us a "neutral" arc-length that
    // represents the average path length along the bent mesh.

    int numNodes = dimI_ + 1;
    std::vector<double> arcLengths;
    arcLengths.reserve(numNodes);

    // Get the 4 i-edges from EdgeCalculator
    const EdgeInfo& edge0 = edgeCalc_.getEdge(0);  // j=0, k=0
    const EdgeInfo& edge1 = edgeCalc_.getEdge(1);  // j=N, k=0
    const EdgeInfo& edge2 = edgeCalc_.getEdge(2);  // j=0, k=P
    const EdgeInfo& edge3 = edgeCalc_.getEdge(3);  // j=N, k=P

    // Compute cumulative arc-lengths for each edge
    auto computeCumulative = [](const EdgeInfo& edge) -> std::vector<double> {
        std::vector<double> cumulative;
        cumulative.reserve(edge.points.size());
        double sum = 0.0;
        cumulative.push_back(0.0);
        for (size_t i = 0; i < edge.segmentLengths.size(); ++i) {
            sum += edge.segmentLengths[i];
            cumulative.push_back(sum);
        }
        return cumulative;
    };

    std::vector<double> cum0 = computeCumulative(edge0);
    std::vector<double> cum1 = computeCumulative(edge1);
    std::vector<double> cum2 = computeCumulative(edge2);
    std::vector<double> cum3 = computeCumulative(edge3);

    // Compute average cumulative arc-length at each i position
    for (int i = 0; i < numNodes; ++i) {
        double avg = 0.0;
        int count = 0;

        if (i < static_cast<int>(cum0.size())) { avg += cum0[i]; count++; }
        if (i < static_cast<int>(cum1.size())) { avg += cum1[i]; count++; }
        if (i < static_cast<int>(cum2.size())) { avg += cum2[i]; count++; }
        if (i < static_cast<int>(cum3.size())) { avg += cum3[i]; count++; }

        if (count > 0) {
            arcLengths.push_back(avg / count);
        } else {
            // Fallback: use linear interpolation
            arcLengths.push_back(static_cast<double>(i) / dimI_ * flatLengthI_);
        }
    }

    return arcLengths;
}

const Node* FlatMeshGenerator::getNodeAt(int i, int j, int k) const {
    // Get node at grid position by finding element that has this corner
    // Node at (i,j,k) is corner 0 of element at (i,j,k)
    // or corner 1 of element at (i-1,j,k)
    // or corner 3 of element at (i,j-1,k)
    // or corner 4 of element at (i,j,k-1)
    // etc.

    // Try element at (i,j,k) using corner 0
    if (i < dimI_ && j < dimJ_ && k < dimK_) {
        const Element* elem = indexer_.getElementAt(i, j, k);
        if (elem) {
            return analyzedMesh_.getNode(elem->nodeIds[0]);
        }
    }

    // Try element at (i-1,j,k) using corner 1
    if (i > 0 && j < dimJ_ && k < dimK_) {
        const Element* elem = indexer_.getElementAt(i-1, j, k);
        if (elem) {
            return analyzedMesh_.getNode(elem->nodeIds[1]);
        }
    }

    // Try element at (i,j-1,k) using corner 3
    if (i < dimI_ && j > 0 && k < dimK_) {
        const Element* elem = indexer_.getElementAt(i, j-1, k);
        if (elem) {
            return analyzedMesh_.getNode(elem->nodeIds[3]);
        }
    }

    // Try element at (i,j,k-1) using corner 4
    if (i < dimI_ && j < dimJ_ && k > 0) {
        const Element* elem = indexer_.getElementAt(i, j, k-1);
        if (elem) {
            return analyzedMesh_.getNode(elem->nodeIds[4]);
        }
    }

    // Try element at (i-1,j-1,k) using corner 2
    if (i > 0 && j > 0 && k < dimK_) {
        const Element* elem = indexer_.getElementAt(i-1, j-1, k);
        if (elem) {
            return analyzedMesh_.getNode(elem->nodeIds[2]);
        }
    }

    // Try element at (i-1,j,k-1) using corner 5
    if (i > 0 && j < dimJ_ && k > 0) {
        const Element* elem = indexer_.getElementAt(i-1, j, k-1);
        if (elem) {
            return analyzedMesh_.getNode(elem->nodeIds[5]);
        }
    }

    // Try element at (i,j-1,k-1) using corner 7
    if (i < dimI_ && j > 0 && k > 0) {
        const Element* elem = indexer_.getElementAt(i, j-1, k-1);
        if (elem) {
            return analyzedMesh_.getNode(elem->nodeIds[7]);
        }
    }

    // Try element at (i-1,j-1,k-1) using corner 6
    if (i > 0 && j > 0 && k > 0) {
        const Element* elem = indexer_.getElementAt(i-1, j-1, k-1);
        if (elem) {
            return analyzedMesh_.getNode(elem->nodeIds[6]);
        }
    }

    return nullptr;
}

Mesh FlatMeshGenerator::generateMesh() {
    Mesh flatMesh;
    flatMesh.setName("flat_unfolded");

    // Compute arc-lengths for each i position
    auto arcLengths = computeCenterlineArcLengths();

    // Element size in j and k directions
    double elemSizeJ = flatLengthJ_ / dimJ_;
    double elemSizeK = flatLengthK_ / dimK_;

    // Determine which global axis corresponds to J and K
    // by analyzing the axis directions
    // jAxisDir_ and kAxisDir_ are the directions of J and K axes in bent mesh
    //
    // Standard flat mesh: X=i, Y=j, Z=k
    // But bent mesh may have different J/K orientations
    //
    // We need to generate flat mesh coordinates that will be correctly
    // mapped back to bent mesh coordinates by ParametricMapper
    //
    // ParametricMapper uses:
    //   u = (x - minX) / sizeX
    //   v = (y - minY) / sizeY
    //   w = (z - minZ) / sizeZ
    //
    // For bent -> flat -> remap to give back original bent,
    // the flat mesh coordinates at grid position (i, j, k) must satisfy:
    //   u(flat_node) = i / dimI
    //   v(flat_node) = j / dimJ
    //   w(flat_node) = k / dimK
    //
    // This means flat mesh must use same (i,j,k) -> (x,y,z) mapping
    // that ParametricMapper expects for the bent mesh reference

    // For correct roundtrip (bent -> unfold -> remap = bent), we must preserve
    // the original bent mesh node IDs. The flat mesh nodes are placed at
    // uniform grid positions, but their IDs must match the bent mesh so that
    // when we remap, the node positions end up back where they started.
    int nodesPerRow = dimI_ + 1;
    int nodesPerSlice = nodesPerRow * (dimJ_ + 1);

    // Generate flat mesh nodes by "unfolding" the bent mesh
    // For each bent mesh node at grid position (i, j, k):
    //   - X coordinate = uniform distribution of arc-length (matches i/dimI)
    //   - Y coordinate = uniform distribution matching j/dimJ
    //   - Z coordinate = uniform distribution matching k/dimK
    //
    // The key insight is that ParametricMapper uses:
    //   u = (x - minX) / sizeX  for i-direction
    //   v = (y - minY) / sizeY  for j-direction
    //   w = (z - minZ) / sizeZ  for k-direction
    //
    // For bent -> unfold -> remap to return original bent mesh,
    // we need the flat mesh coordinates to satisfy:
    //   u = i / dimI  →  x = i * (sizeX / dimI)
    //   v = j / dimJ  →  y = j * (sizeY / dimJ)
    //   w = k / dimK  →  z = k * (sizeZ / dimK)
    //
    // We use the bent mesh bounding box for Y and Z ranges to ensure
    // the parametric coordinates match exactly.

    // For roundtrip consistency (bent -> unfold -> remap = bent):
    // Flat mesh coordinates must satisfy:
    //   u = x / flatLengthI  -> maps to i-direction (arc-length)
    //   v = y / flatLengthJ  -> maps to j-direction
    //   w = z / flatLengthK  -> maps to k-direction
    //
    // IMPORTANT: ParametricMapper uses corners from BoundaryExtractor which follows
    // the indexer's j,k assignment. The flat mesh Y,Z must match this assignment.
    //
    // We analyze the first cross-section to determine if j corresponds to Y or Z
    // in the bent mesh coordinate system.

    // Get corner nodes to analyze j,k directions
    const Node* c00 = getNodeAt(0, 0, 0);
    const Node* c10 = getNodeAt(0, dimJ_, 0);
    const Node* c01 = getNodeAt(0, 0, dimK_);

    // Determine which grid axis (j or k) corresponds to radial (thickness) direction
    // In flat mesh, we want:
    //   - Y axis: the "width" direction (typically larger, e.g., 20mm)
    //   - Z axis: the "thickness" direction (typically smaller, e.g., radial thickness)
    //
    // For consistent layer mapping:
    //   - outer layer (k=0 in bent mesh) should map to Z=0 in flat mesh
    //   - inner layer (k=max in bent mesh) should map to Z=max in flat mesh
    //
    // Analyze corner positions to determine mapping
    bool swapJK = false;
    if (c00 && c10 && c01) {
        Vector3D jDir = c10->position - c00->position;
        Vector3D kDir = c01->position - c00->position;

        // j direction magnitude vs k direction magnitude
        // The smaller one is likely the thickness (radial) direction
        double jMag = jDir.magnitude();
        double kMag = kDir.magnitude();

        // If j is smaller than k, j is likely thickness -> should map to Z
        // So we swap: j -> Z, k -> Y
        if (jMag < kMag * 0.9) {  // 10% tolerance
            swapJK = true;
        }
    }

    // Track processed nodes to avoid duplicate assignments
    // (reorderElementNodes may cause same node to appear at multiple corners)
    std::set<int> processedNodes;

    // Layer ordering logic:
    // We want the flat mesh Y/Z coordinates to preserve the bent mesh's
    // "outer = larger Y" convention. This makes it intuitive for users to
    // create detail flat meshes with consistent layer positioning.
    //
    // In bent mesh:
    //   - Radial direction (typically Y-dominant): outer has larger Y
    //   - j or k axis corresponds to radial direction
    //
    // We check which grid axis is radial and flip if needed so that
    // "outer" (larger Y in bent mesh) maps to larger coordinate in flat mesh.
    bool flipJ = false;
    bool flipK = false;
    if (c00 && c10 && c01) {
        Vector3D jDir = c10->position - c00->position;
        Vector3D kDir = c01->position - c00->position;

        // Determine which direction is radial (Y-dominant)
        // and whether it needs flipping
        if (std::abs(jDir.y) > std::abs(jDir.z)) {
            // j direction is Y-dominant (radial direction)
            // If jDir.y < 0, j+ goes toward smaller Y (inward)
            // We want larger j to map to larger Y, so flip if jDir.y < 0
            if (jDir.y < 0) {
                flipJ = true;
            }
        }
        if (std::abs(kDir.y) > std::abs(kDir.z)) {
            // k direction is Y-dominant (radial direction)
            // If kDir.y < 0, k+ goes toward smaller Y (inward)
            if (kDir.y < 0) {
                flipK = true;
            }
        }
    }

    for (int k = 0; k <= dimK_; ++k) {
        for (int j = 0; j <= dimJ_; ++j) {
            double jRatio = static_cast<double>(j) / dimJ_;
            double kRatio = static_cast<double>(k) / dimK_;

            // Apply flip if needed to preserve outer=larger coordinate
            if (flipJ) {
                jRatio = 1.0 - jRatio;
            }
            if (flipK) {
                kRatio = 1.0 - kRatio;
            }

            double y, z;
            if (swapJK) {
                // j -> Z (thickness), k -> Y (width)
                y = kRatio * flatLengthK_;
                z = jRatio * flatLengthJ_;
            } else {
                // Standard: j -> Y, k -> Z
                y = jRatio * flatLengthJ_;
                z = kRatio * flatLengthK_;
            }

            for (int i = 0; i <= dimI_; ++i) {
                // Get the ORIGINAL bent mesh node ID at this grid position
                // This is critical for roundtrip correctness: bent -> unfold -> remap
                // must return the original bent mesh positions
                const Node* bentNode = getNodeAt(i, j, k);
                if (!bentNode) continue;  // Skip if no node at this position

                int nodeId = bentNode->id;

                // Skip if already processed (avoid duplicate assignments from reorderElementNodes)
                if (processedNodes.count(nodeId) > 0) continue;
                processedNodes.insert(nodeId);

                // X = actual arc-length position from bent mesh centerline
                // This ensures physical correspondence: flat mesh X maps to
                // bent mesh arc-length position via EdgeInterpolator's arc-length
                // based interpolation.
                //
                // Arc-length based mapping:
                //   u = x / flatLengthI = arcLengths[i] / totalArcLength
                //   EdgeInterpolator.interpolate(u) finds arc-length position
                //   which corresponds exactly to bent mesh node at index i
                double x = (i < static_cast<int>(arcLengths.size()))
                         ? arcLengths[i]
                         : (static_cast<double>(i) / dimI_) * flatLengthI_;

                Node node(nodeId, Vector3D(x, y, z));
                flatMesh.addNode(node);
            }
        }
    }

    // Generate elements preserving ORIGINAL bent mesh element IDs and node connectivity
    // We use indexer_.getElementAt() to find the element at each grid position (uses analyzed mesh),
    // but then get the ORIGINAL element connectivity from originalMesh_ (before node reordering)
    for (int k = 0; k < dimK_; ++k) {
        for (int j = 0; j < dimJ_; ++j) {
            for (int i = 0; i < dimI_; ++i) {
                // Get element at this grid position (from analyzed mesh)
                const Element* analyzedElem = indexer_.getElementAt(i, j, k);
                if (!analyzedElem) continue;

                // Get the ORIGINAL element with same ID (before node reordering)
                const Element* originalElem = originalMesh_.getElement(analyzedElem->id);
                if (!originalElem) continue;

                Element elem;
                elem.id = originalElem->id;  // Preserve original element ID
                elem.partId = originalElem->partId;  // Preserve original part ID
                elem.type = ElementType::HEX8;

                // Use ORIGINAL node connectivity (before reordering)
                // This is critical: the flat mesh must have the same element-node
                // connectivity as the original bent mesh
                elem.nodeIds = originalElem->nodeIds;

                // Assign structured indices
                elem.i = i;
                elem.j = j;
                elem.k = k;
                elem.indexAssigned = true;

                flatMesh.addElement(elem);
            }
        }
    }

    // Copy parts from original bent mesh
    for (const auto& pair : originalMesh_.getParts()) {
        flatMesh.addPart(pair.second);
    }

    // If no parts in original mesh, add a default part
    if (flatMesh.getParts().empty()) {
        Part part;
        part.id = 1;
        part.name = "unfolded_part";
        flatMesh.addPart(part);
    }

    return flatMesh;
}

void FlatMeshGenerator::analyzeCrossSectionAxes() {
    // Analyze the first cross-section (i=0) to determine J and K axis directions
    // in the bent mesh's local coordinate system

    // Get corner nodes of the first cross-section (i=0 face)
    const Node* n00 = getNodeAt(0, 0, 0);          // (i=0, j=0, k=0)
    const Node* n10 = getNodeAt(0, dimJ_, 0);      // (i=0, j=max, k=0)
    const Node* n01 = getNodeAt(0, 0, dimK_);      // (i=0, j=0, k=max)

    if (n00 && n10) {
        jAxisDir_ = n10->position - n00->position;
        if (jAxisDir_.magnitude() > 1e-10) {
            jAxisDir_.normalize();
        } else {
            jAxisDir_ = Vector3D(0, 1, 0);  // default
        }
    } else {
        jAxisDir_ = Vector3D(0, 1, 0);  // default
    }

    if (n00 && n01) {
        kAxisDir_ = n01->position - n00->position;
        if (kAxisDir_.magnitude() > 1e-10) {
            kAxisDir_.normalize();
        } else {
            kAxisDir_ = Vector3D(0, 0, 1);  // default
        }
    } else {
        kAxisDir_ = Vector3D(0, 0, 1);  // default
    }
}

} // namespace KooRemapper
