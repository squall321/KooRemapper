#include "mapper/FlatMeshGenerator.h"
#include <cmath>
#include <algorithm>
#include <limits>

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

    // Generate nodes in same order as ExampleMeshGenerator: k -> j -> i (innermost)
    // This ensures node ordering matches what ParametricMapper expects
    int nodeId = 1;
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

    // For bent -> unfold -> remap to work correctly:
    // - ParametricMapper uses bent mesh corners for transfinite interpolation
    // - MeshRemapper uses: v = (y - minY) / sizeY, w = (z - minZ) / sizeZ
    //
    // CRITICAL: The flat mesh Y, Z must be derived from bent mesh CORNER nodes
    // at i=0, NOT from the bounding box. The bounding box may include nodes
    // at other i positions which have different Y, Z due to mesh curvature.
    //
    // Bent mesh corners at i=0:
    //   corner 0 (j=0, k=0): Y0, Z0
    //   corner 3 (j=N, k=0): Y1, Z1
    //   corner 4 (j=0, k=P): Y2, Z2
    //   corner 7 (j=N, k=P): Y3, Z3
    //
    // Flat mesh Y, Z should interpolate between these corner values.

    // Get corner nodes from first cross-section (i=0)
    // These corners define the Y,Z coordinate ranges that ParametricMapper expects
    //
    // ParametricMapper uses:
    //   v = (y - minY) / sizeY  -> j direction interpolation
    //   w = (z - minZ) / sizeZ  -> k direction interpolation
    //
    // For bent -> unfold -> remap to return original bent mesh:
    // - Flat mesh Y range must match bent mesh corner Y range at i=0
    // - Flat mesh Z range must match bent mesh corner Z range at i=0
    // - Node at grid position (i, j, k) in flat mesh must have:
    //     v = j/dimJ -> y = minY + (j/dimJ) * sizeY
    //     w = k/dimK -> z = minZ + (k/dimK) * sizeZ
    //
    // Corner mapping (bent mesh at i=0):
    //   (j=0, k=0) -> corner00
    //   (j=N, k=0) -> corner10
    //   (j=0, k=P) -> corner01
    //   (j=N, k=P) -> corner11

    const Node* c00 = getNodeAt(0, 0, 0);
    const Node* c10 = getNodeAt(0, dimJ_, 0);
    const Node* c01 = getNodeAt(0, 0, dimK_);
    const Node* c11 = getNodeAt(0, dimJ_, dimK_);

    Vector3D corner00 = c00 ? c00->position : Vector3D(0, -flatLengthJ_/2, -flatLengthK_/2);
    Vector3D corner10 = c10 ? c10->position : Vector3D(0, flatLengthJ_/2, -flatLengthK_/2);
    Vector3D corner01 = c01 ? c01->position : Vector3D(0, -flatLengthJ_/2, flatLengthK_/2);
    Vector3D corner11 = c11 ? c11->position : Vector3D(0, flatLengthJ_/2, flatLengthK_/2);

    // Compute Y range (for j direction) and Z range (for k direction)
    // We need the min and max of all 4 corners for each axis
    double minY = std::min({corner00.y, corner10.y, corner01.y, corner11.y});
    double maxY = std::max({corner00.y, corner10.y, corner01.y, corner11.y});
    double minZ = std::min({corner00.z, corner10.z, corner01.z, corner11.z});
    double maxZ = std::max({corner00.z, corner10.z, corner01.z, corner11.z});

    double sizeY = maxY - minY;
    double sizeZ = maxZ - minZ;

    // Ensure non-zero size
    if (sizeY < 1e-10) sizeY = flatLengthJ_;
    if (sizeZ < 1e-10) sizeZ = flatLengthK_;

    for (int k = 0; k <= dimK_; ++k) {
        for (int j = 0; j <= dimJ_; ++j) {
            // For v = j/dimJ to map correctly:
            //   y = minY + (j/dimJ) * sizeY
            // For w = k/dimK to map correctly:
            //   z = minZ + (k/dimK) * sizeZ
            double jRatio = static_cast<double>(j) / dimJ_;
            double kRatio = static_cast<double>(k) / dimK_;

            double y = minY + jRatio * sizeY;
            double z = minZ + kRatio * sizeZ;

            for (int i = 0; i <= dimI_; ++i) {
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

                Node node(nodeId++, Vector3D(x, y, z));
                flatMesh.addNode(node);
            }
        }
    }

    // Generate elements in same order as ExampleMeshGenerator: k -> j -> i
    int elemId = 1;
    for (int k = 0; k < dimK_; ++k) {
        for (int j = 0; j < dimJ_; ++j) {
            for (int i = 0; i < dimI_; ++i) {
                Element elem;
                elem.id = elemId++;
                elem.partId = 1;
                elem.type = ElementType::HEX8;

                // Calculate node IDs using the same formula as ExampleMeshGenerator
                int base = 1 + i + j * nodesPerRow + k * nodesPerSlice;

                // HEX8 node ordering matching ExampleMeshGenerator
                elem.nodeIds[0] = base;
                elem.nodeIds[1] = base + 1;
                elem.nodeIds[2] = base + 1 + nodesPerRow;
                elem.nodeIds[3] = base + nodesPerRow;
                elem.nodeIds[4] = base + nodesPerSlice;
                elem.nodeIds[5] = base + 1 + nodesPerSlice;
                elem.nodeIds[6] = base + 1 + nodesPerRow + nodesPerSlice;
                elem.nodeIds[7] = base + nodesPerRow + nodesPerSlice;

                // Assign structured indices
                elem.i = i;
                elem.j = j;
                elem.k = k;
                elem.indexAssigned = true;

                flatMesh.addElement(elem);
            }
        }
    }

    // Add part
    Part part;
    part.id = 1;
    part.name = "unfolded_part";
    flatMesh.addPart(part);

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
