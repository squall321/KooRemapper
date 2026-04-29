#include "mapper/FlatMeshGenerator.h"
#include <cmath>
#include <algorithm>
#include <limits>
#include <set>

namespace KooRemapper {

FlatMeshGenerator::FlatMeshGenerator()
    : flatLengthI_(0), flatLengthJ_(0), flatLengthK_(0)
    , dimI_(0), dimJ_(0), dimK_(0)
    , bentDimI_(0), bentDimJ_(0), bentDimK_(0)
{
    // Identity permutation until analyzeBentMesh overrides it.
    axisPerm_[0] = 0;
    axisPerm_[1] = 1;
    axisPerm_[2] = 2;
}

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

    // Raw indexer dimensions (bent axes, before permutation).
    bentDimI_ = indexer_.getDimI();
    bentDimJ_ = indexer_.getDimJ();
    bentDimK_ = indexer_.getDimK();

    // Extract boundary information
    boundary_.extract(analyzedMesh_);

    // Calculate edge properties
    edgeCalc_.calculateAllEdges(analyzedMesh_, boundary_);

    // -------------------------------------------------------------------------
    // Axis permutation: decide which bent-indexer axis (0=i, 1=j, 2=k) should
    // play the role of the flat-mesh arc (flat I), width (flat J), and
    // thickness (flat K).
    //
    // The indexer labels axes based on element connectivity and has no
    // guarantee that its "i" is the long arc direction. For meshes where
    // the arc is labeled as j or k, the old unfold produced a flat result
    // of wrong size/orientation (e.g. flat I = 0.115mm because bent i
    // was actually the thickness direction).
    //
    // Rule:
    //   flat I = bent axis with the LARGEST neutral edge length (arc).
    //   flat K = bent axis with the SMALLEST neutral edge length (thickness),
    //            unless sizes tie -- then pick the axis whose cross-section
    //            direction drifts more with arc position (bends with the
    //            strip) vs the width axis which stays world-frame-constant.
    //   flat J = the remaining axis (width).
    // -------------------------------------------------------------------------
    double bentLen[3] = {
        edgeCalc_.getNeutralLengthI(),
        edgeCalc_.getNeutralLengthJ(),
        edgeCalc_.getNeutralLengthK()
    };

    // Step A: arc axis = argmax bent neutral length
    int arcAxis = 0;
    if (bentLen[1] > bentLen[arcAxis]) arcAxis = 1;
    if (bentLen[2] > bentLen[arcAxis]) arcAxis = 2;

    // Step B: classify the remaining two axes as width vs thickness.
    int otherA = -1, otherB = -1;
    for (int a = 0; a < 3; ++a) {
        if (a == arcAxis) continue;
        if (otherA < 0) otherA = a;
        else otherB = a;
    }

    int widthAxis = otherA;
    int thickAxis = otherB;
    double lenA = bentLen[otherA];
    double lenB = bentLen[otherB];
    double maxLen = std::max(lenA, lenB);
    double rel = (maxLen > 1e-10) ? std::abs(lenA - lenB) / maxLen : 0.0;

    if (rel > 0.1) {
        // Clear size difference: smaller is thickness.
        if (lenA < lenB) { thickAxis = otherA; widthAxis = otherB; }
        else             { thickAxis = otherB; widthAxis = otherA; }
    } else {
        // Tied sizes: use stability cue along the arc axis.
        // Sample cross-section direction at several arc positions; the axis
        // whose direction changes more (drift) is the thickness.
        int arcDim = indexer_.getDimI();
        if (arcAxis == 1) arcDim = indexer_.getDimJ();
        else if (arcAxis == 2) arcDim = indexer_.getDimK();

        const int numSamples = std::min(5, arcDim + 1);
        Vector3D refA, refB;
        bool first = true;
        double stabA = 1.0, stabB = 1.0;

        auto nodeAtArc = [&](int arcIdx, int aVal, int bVal) -> const Node* {
            int bentIdx[3] = {0, 0, 0};
            bentIdx[arcAxis] = arcIdx;
            bentIdx[otherA] = aVal;
            bentIdx[otherB] = bVal;
            // axisPerm_ not yet set -- bypass permutation.
            return getNodeAtBent(bentIdx[0], bentIdx[1], bentIdx[2]);
        };
        int dimA = (otherA == 0) ? bentDimI_ : (otherA == 1 ? bentDimJ_ : bentDimK_);
        int dimB = (otherB == 0) ? bentDimI_ : (otherB == 1 ? bentDimJ_ : bentDimK_);

        for (int s = 0; s < numSamples; ++s) {
            int ai = (numSamples > 1) ? (s * arcDim) / (numSamples - 1) : 0;
            if (ai > arcDim) ai = arcDim;
            const Node* n00 = nodeAtArc(ai, 0, 0);
            const Node* nA0 = nodeAtArc(ai, dimA, 0);
            const Node* n0B = nodeAtArc(ai, 0, dimB);
            if (!n00 || !nA0 || !n0B) continue;
            Vector3D dA = nA0->position - n00->position;
            Vector3D dB = n0B->position - n00->position;
            double ma = dA.magnitude();
            double mb = dB.magnitude();
            if (ma < 1e-10 || mb < 1e-10) continue;
            dA = dA * (1.0 / ma);
            dB = dB * (1.0 / mb);
            if (first) { refA = dA; refB = dB; first = false; }
            else {
                double dotA = std::abs(dA.x*refA.x + dA.y*refA.y + dA.z*refA.z);
                double dotB = std::abs(dB.x*refB.x + dB.y*refB.y + dB.z*refB.z);
                if (dotA < stabA) stabA = dotA;
                if (dotB < stabB) stabB = dotB;
            }
        }
        // Less stable (smaller dot product with reference) = thickness.
        if (stabA < stabB - 0.05) {
            thickAxis = otherA; widthAxis = otherB;
        } else {
            thickAxis = otherB; widthAxis = otherA;
        }
    }

    axisPerm_[0] = arcAxis;
    axisPerm_[1] = widthAxis;
    axisPerm_[2] = thickAxis;

    int bentDims[3] = {bentDimI_, bentDimJ_, bentDimK_};
    dimI_ = bentDims[axisPerm_[0]];
    dimJ_ = bentDims[axisPerm_[1]];
    dimK_ = bentDims[axisPerm_[2]];

    // Analyze cross-section axes (in flat-axis frame)
    analyzeCrossSectionAxes();

    return true;
}

// Helper: convert flat-axis (fi, fj, fk) -> bent indexer (bi, bj, bk) tuple.
// Not a member to keep header lean -- defined inline at each use.

void FlatMeshGenerator::calculateFlatDimensions() {
    // Compute arc-length along the centerline for X dimension
    auto arcLengths = computeCenterlineArcLengths();
    if (!arcLengths.empty()) {
        flatLengthI_ = arcLengths.back();
    }

    // Cross-section: pull neutral lengths per axis permutation.
    double bentLen[3] = {
        edgeCalc_.getNeutralLengthI(),
        edgeCalc_.getNeutralLengthJ(),
        edgeCalc_.getNeutralLengthK()
    };
    flatLengthJ_ = bentLen[axisPerm_[1]];
    flatLengthK_ = bentLen[axisPerm_[2]];
}

std::vector<double> FlatMeshGenerator::computeCenterlineArcLengths() {
    // Compute cumulative arc-length along the flat-I axis (= the ARC direction
    // in the bent mesh, whichever bent axis that happens to be).
    //
    // We walk node-by-node along 4 corner edges of the cross-section and
    // average their cumulative lengths. Walking nodes directly avoids any
    // dependence on EdgeCalculator's bent-axis edge ordering, which may
    // label the arc axis as bent-j or bent-k rather than bent-i.

    int numNodes = dimI_ + 1;
    std::vector<double> arcLengths(numNodes, 0.0);

    int cornerJK[4][2] = {
        {0,      0     },
        {dimJ_,  0     },
        {0,      dimK_ },
        {dimJ_,  dimK_ }
    };

    // getNodeAt already takes flat-axis indices and permutes internally.
    auto flatNode = [this](int fi, int fj, int fk) -> const Node* {
        return getNodeAt(fi, fj, fk);
    };

    std::vector<std::vector<double>> cums(4, std::vector<double>(numNodes, 0.0));
    std::vector<int> valid(4, 0);
    for (int c = 0; c < 4; ++c) {
        const Node* prev = flatNode(0, cornerJK[c][0], cornerJK[c][1]);
        cums[c][0] = 0.0;
        valid[c] = prev ? 1 : 0;
        double cum = 0.0;
        for (int i = 1; i < numNodes; ++i) {
            const Node* cur = flatNode(i, cornerJK[c][0], cornerJK[c][1]);
            if (prev && cur) {
                cum += (cur->position - prev->position).magnitude();
                valid[c] = i + 1;
            }
            cums[c][i] = cum;
            if (cur) prev = cur;
        }
    }

    for (int i = 0; i < numNodes; ++i) {
        double sum = 0.0;
        int n = 0;
        for (int c = 0; c < 4; ++c) {
            if (i < valid[c]) { sum += cums[c][i]; ++n; }
        }
        if (n > 0) arcLengths[i] = sum / n;
        else arcLengths[i] = (numNodes > 1)
            ? (static_cast<double>(i) / (numNodes - 1)) * flatLengthI_
            : 0.0;
    }

    return arcLengths;
}

const Node* FlatMeshGenerator::getNodeAt(int fi, int fj, int fk) const {
    // Permute flat-axis (fi, fj, fk) -> bent-axis (bi, bj, bk) and defer to
    // getNodeAtBent. This lets callers in generateMesh/detectApexShift/etc.
    // iterate in flat-axis coordinates (where dimI_ = arc, dimJ_ = width,
    // dimK_ = thickness) without knowing which bent-indexer axis each role
    // was assigned to.
    int flat[3] = {fi, fj, fk};
    int bent[3];
    bent[axisPerm_[0]] = flat[0];
    bent[axisPerm_[1]] = flat[1];
    bent[axisPerm_[2]] = flat[2];
    return getNodeAtBent(bent[0], bent[1], bent[2]);
}

const Node* FlatMeshGenerator::getNodeAtBent(int i, int j, int k) const {
    // Get node at raw bent-indexer grid position by finding an adjacent
    // element that has this corner. Bounds and indices are BENT-axis.
    // Node at (i,j,k) is corner 0 of element at (i,j,k),
    //              or corner 1 of element at (i-1,j,k), etc.

    // Try element at (i,j,k) using corner 0
    if (i < bentDimI_ && j < bentDimJ_ && k < bentDimK_) {
        const Element* elem = indexer_.getElementAt(i, j, k);
        if (elem) {
            return analyzedMesh_.getNode(elem->nodeIds[0]);
        }
    }

    // Try element at (i-1,j,k) using corner 1
    if (i > 0 && j < bentDimJ_ && k < bentDimK_) {
        const Element* elem = indexer_.getElementAt(i-1, j, k);
        if (elem) {
            return analyzedMesh_.getNode(elem->nodeIds[1]);
        }
    }

    // Try element at (i,j-1,k) using corner 3
    if (i < bentDimI_ && j > 0 && k < bentDimK_) {
        const Element* elem = indexer_.getElementAt(i, j-1, k);
        if (elem) {
            return analyzedMesh_.getNode(elem->nodeIds[3]);
        }
    }

    // Try element at (i,j,k-1) using corner 4
    if (i < bentDimI_ && j < bentDimJ_ && k > 0) {
        const Element* elem = indexer_.getElementAt(i, j, k-1);
        if (elem) {
            return analyzedMesh_.getNode(elem->nodeIds[4]);
        }
    }

    // Try element at (i-1,j-1,k) using corner 2
    if (i > 0 && j > 0 && k < bentDimK_) {
        const Element* elem = indexer_.getElementAt(i-1, j-1, k);
        if (elem) {
            return analyzedMesh_.getNode(elem->nodeIds[2]);
        }
    }

    // Try element at (i-1,j,k-1) using corner 5
    if (i > 0 && j < bentDimJ_ && k > 0) {
        const Element* elem = indexer_.getElementAt(i-1, j, k-1);
        if (elem) {
            return analyzedMesh_.getNode(elem->nodeIds[5]);
        }
    }

    // Try element at (i,j-1,k-1) using corner 7
    if (i < bentDimI_ && j > 0 && k > 0) {
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

    // Get corner nodes to analyze world orientation (flat-axis indices).
    const Node* c00 = getNodeAt(0, 0, 0);
    const Node* c10 = getNodeAt(0, dimJ_, 0);
    const Node* c01 = getNodeAt(0, 0, dimK_);

    // Width vs thickness is already decided by axisPerm_ in analyzeBentMesh
    // (flat-J = width, flat-K = thickness). No runtime swapJK needed here.
    const bool swapJK = false;

    // Layer ordering: orient the flat mesh so that the WIDTH axis (now on Y
    // after the optional swap) points toward +Y in world space when possible.
    // This matches the user's authoring convention so that hand-authored
    // detail flat meshes line up without manual rotation.
    bool flipJ = false;
    bool flipK = false;
    if (c00 && c10 && c01) {
        Vector3D jDir = c10->position - c00->position;
        Vector3D kDir = c01->position - c00->position;
        if (std::abs(jDir.y) > std::abs(jDir.z) && jDir.y < 0) flipJ = true;
        if (std::abs(kDir.y) > std::abs(kDir.z) && kDir.y < 0) flipK = true;
    }

    // -------------------------------------------------------------------------
    // Fold-apex centering for closed-loop bent meshes.
    //
    // When the bent mesh is a closed loop (e.g. a fully-wrapped teardrop), the
    // structured indexer's choice of i=0 is arbitrary -- it may land anywhere
    // around the loop. If i=0 happens to fall AT the fold apex (max curvature),
    // the unfold ends up asymmetric: apex at one end, seam in the middle.
    //
    // For visual symmetry we want the SEAM (low-curvature region) at the ends
    // of the flat strip and the APEX naturally in the middle. We achieve this
    // by cyclic-shifting i so that the lowest-curvature centerline point
    // becomes new i=0.
    //
    // For mostly-open geometries (fewer than 80% shared cross-section nodes),
    // detectApexShift() returns 0 and behavior is identical to before.
    // -------------------------------------------------------------------------
    int iShift = detectApexShift();
    auto physI = [this, iShift](int newI) -> int {
        if (iShift == 0) return newI;
        // For closed loops, original i=0 == original i=dimI_, so the cycle
        // length is dimI_ (not dimI_+1). new i=dimI_ wraps back to physical
        // layer at original i=iShift, which is what we placed at new i=0.
        return ((newI + iShift) % dimI_ + dimI_) % dimI_;
    };

    // Build shifted arc lengths if cyclic shift is active.
    if (iShift != 0 && !arcLengths.empty()) {
        double L = arcLengths.back();
        double anchor = arcLengths[iShift];
        std::vector<double> shifted(dimI_ + 1);
        for (int i = 0; i <= dimI_; ++i) {
            int oldEnd = (iShift + i) % dimI_;
            double cum = arcLengths[oldEnd] - anchor;
            if (cum < 0) cum += L;
            shifted[i] = cum;
        }
        // Ensure monotonic: last entry must be exactly L (wraps fully around).
        shifted[dimI_] = L;
        arcLengths = shifted;
    }

    // -------------------------------------------------------------------------
    // Pass 1: Build (i,j,k) -> nodeId map using each grid position's underlying
    // bent-mesh node ID. For closed-loop / folded geometries the same bent node
    // ID legitimately appears at multiple grid positions (e.g. teardrop seam at
    // i=0 and i=dimI). We keep the original ID at the first occurrence and mint
    // a fresh ID for every subsequent occurrence so that flat-space coordinates
    // stay unique. Without this, ~5 nodes get silently dropped on a teardrop
    // and the seam-spanning elements end up with negative Jacobian.
    // -------------------------------------------------------------------------
    auto gridKey = [this](int i, int j, int k) {
        return ((static_cast<long long>(i)) * (dimJ_ + 1) + j) * (dimK_ + 1) + k;
    };

    int maxNodeId = 0;
    for (const auto& pair : originalMesh_.getNodes()) {
        if (pair.first > maxNodeId) maxNodeId = pair.first;
    }

    std::map<long long, int> gridToNodeId;
    std::set<int> seenIds;
    int duplicatedNodeCount = 0;

    for (int k = 0; k <= dimK_; ++k) {
        for (int j = 0; j <= dimJ_; ++j) {
            for (int i = 0; i <= dimI_; ++i) {
                const Node* bentNode = getNodeAt(physI(i), j, k);
                if (!bentNode) continue;
                int origId = bentNode->id;
                int assignedId;
                if (seenIds.insert(origId).second) {
                    assignedId = origId;
                } else {
                    assignedId = ++maxNodeId;
                    duplicatedNodeCount++;
                }
                gridToNodeId[gridKey(i, j, k)] = assignedId;
            }
        }
    }

    // -------------------------------------------------------------------------
    // Pass 2: place every grid position as a flat-space node using the assigned
    // (possibly duplicated) ID. Coordinates are deterministic from (i,j,k):
    //   x = arcLengths[i]
    //   y/z = jRatio*flatJ / kRatio*flatK (with flip + jk swap)
    // -------------------------------------------------------------------------
    for (int k = 0; k <= dimK_; ++k) {
        double kRatio = static_cast<double>(k) / dimK_;
        if (flipK) kRatio = 1.0 - kRatio;
        for (int j = 0; j <= dimJ_; ++j) {
            double jRatio = static_cast<double>(j) / dimJ_;
            if (flipJ) jRatio = 1.0 - jRatio;

            double y, z;
            if (swapJK) {
                y = kRatio * flatLengthK_;
                z = jRatio * flatLengthJ_;
            } else {
                y = jRatio * flatLengthJ_;
                z = kRatio * flatLengthK_;
            }

            for (int i = 0; i <= dimI_; ++i) {
                auto it = gridToNodeId.find(gridKey(i, j, k));
                if (it == gridToNodeId.end()) continue;
                double x = (i < static_cast<int>(arcLengths.size()))
                         ? arcLengths[i]
                         : (static_cast<double>(i) / dimI_) * flatLengthI_;
                flatMesh.addNode(Node(it->second, Vector3D(x, y, z)));
            }
        }
    }

    // -------------------------------------------------------------------------
    // Pass 3: rebuild element connectivity from the grid lattice instead of
    // copying the bent mesh's original node order. This guarantees positive
    // Jacobian winding in flat coordinates regardless of how many times the
    // (jk-swap, flipJ, flipK) reflections accumulate, AND it routes seam
    // corners through the duplicated node IDs introduced in Pass 1.
    //
    // Standard LS-DYNA HEX8 corner offsets (CCW bottom face, then top face):
    //   0:(0,0,0) 1:(1,0,0) 2:(1,1,0) 3:(0,1,0)
    //   4:(0,0,1) 5:(1,0,1) 6:(1,1,1) 7:(0,1,1)
    // -------------------------------------------------------------------------
    static constexpr int CORNER_OFFSETS[8][3] = {
        {0,0,0}, {1,0,0}, {1,1,0}, {0,1,0},
        {0,0,1}, {1,0,1}, {1,1,1}, {0,1,1}
    };

    // Determine winding correction once: any single jk-swap or single axis flip
    // is a reflection in the flat coordinate system. If the parity is odd, a
    // standard-order HEX8 built from grid offsets would be inverted, so we
    // permute corners (swap node 1<->3 and 5<->7) to flip winding back.
    int parity = (flipJ ? 1 : 0) ^ (flipK ? 1 : 0) ^ (swapJK ? 1 : 0);
    static constexpr int FLIP_MAP[8] = {0, 3, 2, 1, 4, 7, 6, 5};

    int rebuiltElementCount = 0;
    for (int k = 0; k < dimK_; ++k) {
        for (int j = 0; j < dimJ_; ++j) {
            for (int i = 0; i < dimI_; ++i) {
                // Look up the element using ORIGINAL i (physI) so that closed-loop
                // shifts route to the right physical hex; the gridToNodeId lookup
                // below stays in NEW i coordinates because Pass 1 keyed it that way.
                // Permute (flat i, j, k) -> bent indexer axes before the element
                // lookup, since the indexer is keyed in bent-axis coordinates.
                int flatIdx[3] = {physI(i), j, k};
                int bentIdx[3];
                bentIdx[axisPerm_[0]] = flatIdx[0];
                bentIdx[axisPerm_[1]] = flatIdx[1];
                bentIdx[axisPerm_[2]] = flatIdx[2];
                const Element* analyzedElem = indexer_.getElementAt(bentIdx[0], bentIdx[1], bentIdx[2]);
                if (!analyzedElem) continue;
                const Element* originalElem = originalMesh_.getElement(analyzedElem->id);

                Element elem;
                elem.id = analyzedElem->id;
                elem.partId = originalElem ? originalElem->partId : analyzedElem->partId;
                elem.type = ElementType::HEX8;

                bool ok = true;
                for (int c = 0; c < 8; ++c) {
                    int sourceCorner = (parity == 1) ? FLIP_MAP[c] : c;
                    int di = CORNER_OFFSETS[sourceCorner][0];
                    int dj = CORNER_OFFSETS[sourceCorner][1];
                    int dk = CORNER_OFFSETS[sourceCorner][2];
                    auto it = gridToNodeId.find(gridKey(i + di, j + dj, k + dk));
                    if (it == gridToNodeId.end()) { ok = false; break; }
                    elem.nodeIds[c] = it->second;
                }
                if (!ok) continue;

                elem.i = i;
                elem.j = j;
                elem.k = k;
                elem.indexAssigned = true;
                flatMesh.addElement(elem);
                rebuiltElementCount++;
            }
        }
    }
    (void)duplicatedNodeCount;
    (void)rebuiltElementCount;

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

int FlatMeshGenerator::detectApexShift() {
    // Step 1: Test if mesh is a closed loop in i direction.
    // Closed if cross-section nodes at i=0 and i=dimI share the same IDs.
    int sharedCount = 0;
    int totalCount = 0;
    for (int j = 0; j <= dimJ_; ++j) {
        for (int k = 0; k <= dimK_; ++k) {
            const Node* n0 = getNodeAt(0, j, k);
            const Node* nN = getNodeAt(dimI_, j, k);
            if (!n0 || !nN) continue;
            totalCount++;
            if (n0->id == nN->id) sharedCount++;
        }
    }
    if (totalCount == 0) return 0;
    double sharedRatio = static_cast<double>(sharedCount) / totalCount;
    if (sharedRatio < 0.8) return 0;  // Not a closed loop -- no shift.

    // Step 2: Compute centerline (cross-section centroid per i layer).
    // For closed loop, dimI_ distinct physical layers (i=0 == i=dimI_).
    std::vector<Vector3D> centerline(dimI_);
    for (int i = 0; i < dimI_; ++i) {
        Vector3D sum;
        int count = 0;
        for (int j = 0; j <= dimJ_; ++j) {
            for (int k = 0; k <= dimK_; ++k) {
                const Node* n = getNodeAt(i, j, k);
                if (n) { sum = sum + n->position; count++; }
            }
        }
        if (count > 0) centerline[i] = sum * (1.0 / count);
    }

    // Step 3: Compute discrete curvature (tangent angle change) cyclically.
    std::vector<double> curvature(dimI_, 0.0);
    for (int i = 0; i < dimI_; ++i) {
        Vector3D prev = centerline[(i - 1 + dimI_) % dimI_];
        Vector3D curr = centerline[i];
        Vector3D next = centerline[(i + 1) % dimI_];
        Vector3D t1 = curr - prev;
        Vector3D t2 = next - curr;
        double m1 = t1.magnitude();
        double m2 = t2.magnitude();
        if (m1 < 1e-10 || m2 < 1e-10) continue;
        t1 = t1 * (1.0 / m1);
        t2 = t2 * (1.0 / m2);
        double cosAng = t1.x * t2.x + t1.y * t2.y + t1.z * t2.z;
        if (cosAng > 1.0) cosAng = 1.0;
        if (cosAng < -1.0) cosAng = -1.0;
        curvature[i] = std::acos(cosAng);
    }

    // Step 4: Find lowest-curvature point. Smooth slightly with a 3-point
    // average so a single noisy node doesn't dominate the choice.
    int bestI = 0;
    double bestScore = std::numeric_limits<double>::max();
    for (int i = 0; i < dimI_; ++i) {
        double score = curvature[(i - 1 + dimI_) % dimI_]
                     + curvature[i]
                     + curvature[(i + 1) % dimI_];
        if (score < bestScore) {
            bestScore = score;
            bestI = i;
        }
    }
    return bestI;  // 0 means no shift needed; otherwise cyclic-shift amount.
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
