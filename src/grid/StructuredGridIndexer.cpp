#include "grid/StructuredGridIndexer.h"
#include <algorithm>
#include <queue>
#include <tuple>
#include <set>
#include <cmath>
#include <unordered_map>
#include <vector>

// Knowledge graph (lat.md):
//   @lat: [[modules/grid]]

namespace KooRemapper {

namespace {

// Hash for (i,j,k) grid index keys
struct GridIndexHash {
    size_t operator()(const std::tuple<int, int, int>& t) const {
        size_t h = static_cast<unsigned>(std::get<0>(t));
        h = h * 0x9E3779B97F4A7C15ULL ^ static_cast<unsigned>(std::get<1>(t));
        h = h * 0x9E3779B97F4A7C15ULL ^ static_cast<unsigned>(std::get<2>(t));
        return h;
    }
};

}  // namespace

StructuredGridIndexer::StructuredGridIndexer()
    : dimI_(0), dimJ_(0), dimK_(0)
{
    // Default axis-to-face mapping:
    // Face 0,1 -> i-axis (i-, i+)
    // Face 2,3 -> j-axis (j-, j+)
    // Face 4,5 -> k-axis (k-, k+)
    axisToFace_[0] = {0, 1};  // i-axis
    axisToFace_[1] = {2, 3};  // j-axis
    axisToFace_[2] = {4, 5};  // k-axis

    // Initialize axis directions to default
    axisDirections_[0] = Vector3D(1, 0, 0);  // i-axis default
    axisDirections_[1] = Vector3D(0, 1, 0);  // j-axis default
    axisDirections_[2] = Vector3D(0, 0, 1);  // k-axis default
}

bool StructuredGridIndexer::assignIndices(Mesh& mesh,
                                          const ConnectivityAnalyzer& connectivity) {
    errorMessage_.clear();
    dimI_ = dimJ_ = dimK_ = 0;

    if (mesh.elements.empty()) {
        errorMessage_ = "Mesh has no elements";
        return false;
    }

    // Check if all elements already have indices assigned
    bool allAssigned = true;
    for (const auto& [id, elem] : mesh.elements) {
        if (!elem.indexAssigned || elem.i < 0 || elem.j < 0 || elem.k < 0) {
            allAssigned = false;
            break;
        }
    }

    if (allAssigned) {
        // Use existing indices - just calculate dimensions
        calculateDimensions(mesh);
        mesh.setGridDimensions(dimI_, dimJ_, dimK_);
        return true;
    }

    // Reset all indices for re-computation
    for (auto& [id, elem] : mesh.elements) {
        elem.i = elem.j = elem.k = -1;
        elem.indexAssigned = false;
    }

    // Find starting corner
    int startElem = findStartCorner(mesh, connectivity);
    if (startElem < 0) {
        errorMessage_ = "Cannot find corner element to start indexing";
        return false;
    }

    // Determine initial directions using geometry-based approach
    if (!determineInitialDirectionsGeometry(mesh, startElem, connectivity)) {
        return false;
    }

    // Propagate indices via BFS, carrying the axis frame across shared faces
    if (!propagateIndicesTopology(mesh, startElem, connectivity)) {
        return false;
    }

    // Calculate dimensions
    calculateDimensions(mesh);

    // REQ-003: Fail fast on degenerate BFS results.
    // A correct structured grid has fill rate near 100% (dimI * dimJ * dimK
    // ≈ element count). When axis detection collapses two directions onto
    // the same world axis, BFS spreads elements across an impossibly large
    // grid space and fill rate drops to a few percent — better to abort
    // here than crash later inside the parametric mapper.
    {
        long long expected = (long long)dimI_ * dimJ_ * dimK_;
        long long actual   = (long long)mesh.elements.size();
        if (expected > 0 && (double)actual / (double)expected < 0.5) {
            errorMessage_ = "Grid indexing failed: fill rate " +
                std::to_string(100.0 * (double)actual / (double)expected) + "% " +
                "(dims=" + std::to_string(dimI_) + "x" +
                std::to_string(dimJ_) + "x" + std::to_string(dimK_) + ", " +
                "actual=" + std::to_string(actual) + " elements)";
            return false;
        }
    }

    // A grid slot holds exactly one element. When two elements land on the
    // same (i,j,k), everything that walks the grid slot by slot keeps one and
    // drops the other without a word (unfold wrote 53 of 100 elements with
    // rc 0 when propagation guessed axes from centroids). The topology walk
    // checks every face step against the slots already given, so this should
    // not fire any more; it stays as the back door.
    {
        std::set<std::tuple<int, int, int>> slots;
        for (const auto& [id, elem] : mesh.elements) {
            slots.insert({elem.i, elem.j, elem.k});
        }
        if (slots.size() != mesh.elements.size()) {
            errorMessage_ = "Grid indexing failed: " +
                std::to_string(mesh.elements.size() - slots.size()) + " of " +
                std::to_string(mesh.elements.size()) +
                " elements share an (i,j,k) slot with another element " +
                "(dims=" + std::to_string(dimI_) + "x" +
                std::to_string(dimJ_) + "x" + std::to_string(dimK_) + ")";
            return false;
        }
    }

    // REQ-003: Sort axes so the smallest-span dimension is K (thickness).
    // After this call, dimI >= dimJ >= dimK by convention; downstream
    // mapping code relies on K being the thinnest extent.
    reorderAxes(mesh);

    // Update mesh dimensions
    mesh.setGridDimensions(dimI_, dimJ_, dimK_);

    return true;
}

int StructuredGridIndexer::findStartCorner(const Mesh& mesh,
                                           const ConnectivityAnalyzer& connectivity) {
    auto corners = connectivity.findCornerElements();

    if (corners.empty()) {
        return -1;
    }

    // Return first corner found
    // Could be improved to select a specific corner (e.g., minimum coordinates)
    return corners[0];
}

bool StructuredGridIndexer::determineInitialDirections(const Mesh& mesh, int startElem,
                                                        const ConnectivityAnalyzer& connectivity) {
    // For a corner element, exactly 3 faces have neighbors
    // These 3 faces define the positive directions for i, j, k

    const auto& neighbors = connectivity.getNeighbors(startElem);
    if (neighbors.size() != 3) {
        errorMessage_ = "Start element is not a corner (has " +
                       std::to_string(neighbors.size()) + " neighbors instead of 3)";
        return false;
    }

    // Collect faces that have neighbors
    std::vector<int> neighborFaces;
    for (const auto& neighbor : neighbors) {
        neighborFaces.push_back(neighbor.throughFace);
    }

    // Sort faces to get consistent axis assignment
    std::sort(neighborFaces.begin(), neighborFaces.end());

    // Map faces to axes
    // We'll use the face pairs to determine axes
    // Lower face index in each pair is "negative", higher is "positive"
    std::set<int> faceSet(neighborFaces.begin(), neighborFaces.end());

    // Determine which axis direction each neighbor face represents
    // For starting corner at (0,0,0), neighbor faces should be positive directions
    int axisIdx = 0;
    for (int face : neighborFaces) {
        // The face that has neighbor is in positive direction
        int axis = face / 2;  // 0,1->0, 2,3->1, 4,5->2
        int isPositive = face % 2;  // 0->negative, 1->positive

        if (isPositive) {
            axisToFace_[axisIdx] = {face - 1, face};  // negative, positive
        } else {
            axisToFace_[axisIdx] = {face, face + 1};  // negative, positive
        }
        axisIdx++;
    }

    return true;
}

bool StructuredGridIndexer::propagateIndices(Mesh& mesh, int startElem,
                                             const ConnectivityAnalyzer& connectivity) {
    // BFS queue: (element ID, i, j, k)
    std::queue<std::tuple<int, int, int, int>> queue;

    // Start at origin
    Element* startElement = mesh.getElement(startElem);
    if (!startElement) {
        errorMessage_ = "Start element not found";
        return false;
    }

    startElement->setGridIndex(0, 0, 0);
    queue.push({startElem, 0, 0, 0});

    int processedCount = 0;

    while (!queue.empty()) {
        auto [elemId, i, j, k] = queue.front();
        queue.pop();

        const auto& neighbors = connectivity.getNeighbors(elemId);

        for (const auto& neighbor : neighbors) {
            Element* neighborElem = mesh.getElement(neighbor.neighborElementId);
            if (!neighborElem || neighborElem->indexAssigned) {
                continue;
            }

            // Determine index offset based on which face connects them
            int face = neighbor.throughFace;
            int axis = face / 2;      // 0=i, 1=j, 2=k
            int dir = (face % 2 == 0) ? -1 : 1;  // even=negative, odd=positive

            int ni = i, nj = j, nk = k;
            switch (axis) {
                case 0: ni += dir; break;
                case 1: nj += dir; break;
                case 2: nk += dir; break;
            }

            neighborElem->setGridIndex(ni, nj, nk);
            queue.push({neighbor.neighborElementId, ni, nj, nk});
            processedCount++;
        }
    }

    // Verify all elements were indexed
    for (const auto& [id, elem] : mesh.elements) {
        if (!elem.indexAssigned) {
            errorMessage_ = "Element " + std::to_string(id) + " was not indexed";
            return false;
        }
    }

    // Normalize indices to start from 0
    int minI = 0, minJ = 0, minK = 0;
    for (const auto& [id, elem] : mesh.elements) {
        minI = std::min(minI, elem.i);
        minJ = std::min(minJ, elem.j);
        minK = std::min(minK, elem.k);
    }

    for (auto& [id, elem] : mesh.elements) {
        elem.i -= minI;
        elem.j -= minJ;
        elem.k -= minK;
    }

    return true;
}

void StructuredGridIndexer::calculateDimensions(const Mesh& mesh) {
    dimI_ = dimJ_ = dimK_ = 0;

    for (const auto& [id, elem] : mesh.elements) {
        if (elem.indexAssigned) {
            dimI_ = std::max(dimI_, elem.i + 1);
            dimJ_ = std::max(dimJ_, elem.j + 1);
            dimK_ = std::max(dimK_, elem.k + 1);
        }
    }
}

void StructuredGridIndexer::reorderAxes(Mesh& mesh) {
    // Sort dimensions: dimK <= dimJ <= dimI
    std::array<std::pair<int, int>, 3> dims = {{
        {dimI_, 0},
        {dimJ_, 1},
        {dimK_, 2}
    }};

    std::sort(dims.begin(), dims.end(),
              [](const auto& a, const auto& b) { return a.first > b.first; });

    // dims[0] should be largest (new i)
    // dims[1] should be middle (new j)
    // dims[2] should be smallest (new k)

    // Build permutation
    std::array<int, 3> perm;  // perm[new_axis] = old_axis
    for (int i = 0; i < 3; ++i) {
        perm[i] = dims[i].second;
    }

    // Apply permutation to all elements
    for (auto& [id, elem] : mesh.elements) {
        std::array<int, 3> oldIdx = {elem.i, elem.j, elem.k};
        elem.i = oldIdx[perm[0]];
        elem.j = oldIdx[perm[1]];
        elem.k = oldIdx[perm[2]];
    }

    // Update dimensions
    dimI_ = dims[0].first;
    dimJ_ = dims[1].first;
    dimK_ = dims[2].first;

    mesh.setGridDimensions(dimI_, dimJ_, dimK_);
}

int StructuredGridIndexer::getAxisFromFace(int faceIndex) const {
    return faceIndex / 2;
}

int StructuredGridIndexer::getDirectionFromFace(int faceIndex) const {
    return (faceIndex % 2 == 0) ? -1 : 1;
}

Vector3D StructuredGridIndexer::calculateElementCentroid(const Mesh& mesh, int elemId) const {
    const Element* elem = mesh.getElement(elemId);
    if (!elem) return Vector3D(0, 0, 0);

    Vector3D centroid(0, 0, 0);
    int count = 0;
    for (int i = 0; i < 8; ++i) {
        const Node* node = mesh.getNode(elem->nodeIds[i]);
        if (node) {
            centroid += node->position;
            ++count;
        }
    }
    if (count > 0) {
        centroid /= static_cast<double>(count);
    }
    return centroid;
}

bool StructuredGridIndexer::determineInitialDirectionsGeometry(const Mesh& mesh, int startElem,
                                                                const ConnectivityAnalyzer& connectivity) {
    // For a corner element, exactly 3 faces have neighbors
    // Use geometry (element centroids) to determine axis directions

    const auto& neighbors = connectivity.getNeighbors(startElem);
    if (neighbors.size() != 3) {
        errorMessage_ = "Start element is not a corner (has " +
                       std::to_string(neighbors.size()) + " neighbors instead of 3)";
        return false;
    }

    // Calculate centroid of start element
    Vector3D startCentroid = calculateElementCentroid(mesh, startElem);

    // Calculate direction vectors to each neighbor
    std::array<Vector3D, 3> directions;
    for (int i = 0; i < 3; ++i) {
        Vector3D neighborCentroid = calculateElementCentroid(mesh, neighbors[i].neighborElementId);
        directions[i] = neighborCentroid - startCentroid;
        directions[i] = directions[i].normalized();
    }

    // For curved meshes, the three directions may all point in similar directions
    // (e.g., all have large Y component in an arc shape)
    // Instead of matching to world axes, we need to find the three MOST ORTHOGONAL directions

    // Find which pair of directions is most orthogonal (smallest absolute dot product)
    double minDot = 2.0;
    int pair1 = 0, pair2 = 1;
    for (int i = 0; i < 3; ++i) {
        for (int j = i + 1; j < 3; ++j) {
            double dot = std::abs(directions[i].dot(directions[j]));
            if (dot < minDot) {
                minDot = dot;
                pair1 = i;
                pair2 = j;
            }
        }
    }
    int third = 3 - pair1 - pair2;  // The remaining index

    // REQ-003: Direct assignment of the 3 orthogonal neighbor directions to
    // axes 0/1/2. The old getDominantAxis() world-X/Y/Z mapping failed on
    // curved meshes — when the arc direction had mixed Y/Z components, two
    // directions could collide on the same world axis, causing index
    // explosion in BFS (Q8 case: dims=1536×1533×396, fill rate 0.26%).
    //
    // Skipping the world-axis mapping is safe because reorderAxes() (called
    // from assignIndices() after BFS completes) places the smallest-span
    // dimension as K. The "k+ points inward / k+ points up" heuristic that
    // used to live here was only meaningful when the axis 0/1/2 mapping
    // matched world XYZ — once reorderAxes runs, that invariant is set
    // post-hoc by dimension order.
    axisDirections_[0] = directions[pair1];
    axisDirections_[1] = directions[pair2];
    axisDirections_[2] = directions[third];

    // REQ-003: Enforce a right-handed triad on axisDirections_. The centroid
    // walk needed it for its I × J = K fallback (arc30 dim_K split 1 → 2). The
    // topology walk that replaced it has no such fallback, but the flip stays:
    // it decides the sign the start corner gives axis 2, hence which end of
    // that axis the corner sits on -- dropping it would change indices of
    // meshes that were indexed correctly.
    Vector3D ij = axisDirections_[0].cross(axisDirections_[1]);
    if (ij.dot(axisDirections_[2]) < 0.0) {
        axisDirections_[2] = axisDirections_[2] * -1.0;
    }
    return true;
}

int StructuredGridIndexer::determineAxisFromDirection(const Vector3D& direction) const {
    // Compare direction with stored axis directions
    // Return the axis that best matches this direction

    double bestScore = -2.0;
    int bestAxis = 0;
    int bestSign = 1;

    for (int axis = 0; axis < 3; ++axis) {
        double dot = direction.dot(axisDirections_[axis]);
        double score = std::abs(dot);

        if (score > bestScore) {
            bestScore = score;
            bestAxis = axis;
            bestSign = (dot >= 0) ? 1 : -1;
        }
    }

    // Return axis * 2 + (sign == 1 ? 1 : 0) to encode both axis and direction
    // But for simple return, just return axis and handle sign separately
    return bestAxis;
}

int StructuredGridIndexer::determineDirectionSign(const Vector3D& direction, int axis) const {
    double dot = direction.dot(axisDirections_[axis]);
    return (dot >= 0) ? 1 : -1;
}

bool StructuredGridIndexer::propagateIndicesTopology(Mesh& mesh, int startElem,
                                                      const ConnectivityAnalyzer& connectivity) {
    // Every element carries a frame: for each of its six local faces, the grid
    // axis that face looks along and the sign. Crossing face f of A into face g
    // of B moves one slot along A's (axis, sign) for f. B's frame follows from
    // the shared face alone: g looks back (same axis, opposite sign), the face
    // opposite g looks on, and each of B's other four faces continues the face
    // of A that meets it along an edge of the shared face.
    //
    // Nothing geometric is consulted after the start corner. The walk this
    // replaced picked each neighbour's axis from the direction between element
    // centroids; on a fold, a tight wave or a thin layer the nearest axis is
    // the wrong one, and two elements landed on one slot (47 of 100 on a
    // folded 10x5x2 plate, 786 of 2000 on a teardrop) or the grid spread until
    // the fill-rate gate refused it. There is no fallback to that walk: a mesh
    // whose faces do not close as one block is refused, not guessed at.
    struct Frame {
        std::array<signed char, Element::NUM_FACES> axis;
        std::array<signed char, Element::NUM_FACES> sign;
    };
    struct Slot { Element* elem; Frame frame; };
    std::unordered_map<int, Slot> slots;
    slots.reserve(mesh.elements.size());
    for (auto& [id, elem] : mesh.elements) {
        slots.emplace(id, Slot{&elem, Frame{}});
    }

    auto startIt = slots.find(startElem);
    if (startIt == slots.end()) {
        errorMessage_ = "Start element not found";
        return false;
    }

    // Start frame: the reading the centroid walk made at the corner, kept so
    // that meshes it indexed correctly get the same (i,j,k) as before -- each
    // of the three neighbours takes the axis of axisDirections_ its direction
    // matches best, with the sign of that dot product.
    Frame& startFrame = startIt->second.frame;
    startFrame.axis.fill(-1);
    const Vector3D startCentroid = calculateElementCentroid(mesh, startElem);
    for (const auto& neighbor : connectivity.getNeighbors(startElem)) {
        Vector3D direction = calculateElementCentroid(mesh, neighbor.neighborElementId) - startCentroid;
        direction = direction.normalized();

        int bestAxis = 0;
        int bestSign = 1;
        double bestAbsDot = -1.0;
        for (int axis = 0; axis < 3; ++axis) {
            double dot = direction.dot(axisDirections_[axis]);
            double absDot = std::abs(dot);
            if (absDot > bestAbsDot) {
                bestAbsDot = absDot;
                bestAxis = axis;
                bestSign = (dot >= 0) ? 1 : -1;
            }
        }

        // Faces pair up as (i-,i+) (j-,j+) (k-,k+): f ^ 1 is the opposite face.
        const int face = neighbor.throughFace;
        startFrame.axis[face] = startFrame.axis[face ^ 1] = static_cast<signed char>(bestAxis);
        startFrame.sign[face] = static_cast<signed char>(bestSign);
        startFrame.sign[face ^ 1] = static_cast<signed char>(-bestSign);
    }
    {
        std::array<bool, 3> axisTaken = {false, false, false};
        for (int pair = 0; pair < 3; ++pair) {
            int axis = startFrame.axis[pair * 2];
            if (axis < 0 || axisTaken[axis]) {
                errorMessage_ = "Grid indexing failed: the three neighbours of start corner element " +
                    std::to_string(startElem) + " do not lie on three different axes";
                return false;
            }
            axisTaken[axis] = true;
        }
    }

    startIt->second.elem->setGridIndex(0, 0, 0);
    std::queue<int> queue;
    queue.push(startElem);

    const auto& faces = topo::facesOf(ElementType::HEX8);

    while (!queue.empty()) {
        int elemId = queue.front();
        queue.pop();

        const Slot& current = slots.find(elemId)->second;
        const Element& a = *current.elem;
        const Frame& fa = current.frame;

        for (const auto& neighbor : connectivity.getNeighbors(elemId)) {
            auto it = slots.find(neighbor.neighborElementId);
            if (it == slots.end()) continue;
            Element& b = *it->second.elem;
            const int f = neighbor.throughFace;
            const int g = neighbor.neighborFace;

            std::array<int, 3> want = {a.i, a.j, a.k};
            want[fa.axis[f]] += fa.sign[f];

            if (b.indexAssigned) {
                // Reached before by another path: both paths must agree.
                if (b.i != want[0] || b.j != want[1] || b.k != want[2]) {
                    errorMessage_ = "Grid indexing failed: element " + std::to_string(b.id) +
                        " sits at (" + std::to_string(b.i) + "," + std::to_string(b.j) + "," +
                        std::to_string(b.k) + ") but its neighbour " + std::to_string(a.id) +
                        " places it at (" + std::to_string(want[0]) + "," + std::to_string(want[1]) + "," +
                        std::to_string(want[2]) + ") -- the faces do not close as one structured block";
                    return false;
                }
                continue;
            }

            Frame& fb = it->second.frame;
            fb.axis[g] = fb.axis[g ^ 1] = fa.axis[f];
            fb.sign[g] = static_cast<signed char>(-fa.sign[f]);
            fb.sign[g ^ 1] = fa.sign[f];
            for (int h = 0; h < Element::NUM_FACES; ++h) {
                if (h == g || h == (g ^ 1)) continue;

                // The edge (two nodes) face h of B has on the shared face.
                std::array<int, 2> edge = {0, 0};
                int shared = 0;
                for (int x = 0; x < Element::NODES_PER_FACE; ++x) {
                    int node = b.nodeIds[faces[h].v[x]];
                    for (int y = 0; y < Element::NODES_PER_FACE; ++y) {
                        if (node == b.nodeIds[faces[g].v[y]]) {
                            if (shared < 2) edge[shared] = node;
                            ++shared;
                        }
                    }
                }
                if (shared != 2) {
                    errorMessage_ = "Grid indexing failed: element " + std::to_string(b.id) +
                        " is not a plain hexahedron (two of its neighbouring faces share " +
                        std::to_string(shared) + " nodes instead of 2)";
                    return false;
                }

                // The face of A, other than f, that holds that edge.
                int through = -1;
                for (int c = 0; c < Element::NUM_FACES && through < 0; ++c) {
                    if (c == f) continue;
                    bool has0 = false, has1 = false;
                    for (int q = 0; q < Element::NODES_PER_FACE; ++q) {
                        int node = a.nodeIds[faces[c].v[q]];
                        has0 = has0 || node == edge[0];
                        has1 = has1 || node == edge[1];
                    }
                    if (has0 && has1) through = c;
                }
                if (through < 0) {
                    errorMessage_ = "Grid indexing failed: elements " + std::to_string(a.id) + " and " +
                        std::to_string(b.id) + " do not meet edge to edge on their shared face";
                    return false;
                }
                fb.axis[h] = fa.axis[through];
                fb.sign[h] = fa.sign[through];
            }

            b.setGridIndex(want[0], want[1], want[2]);
            queue.push(neighbor.neighborElementId);
        }
    }

    // Verify all elements were indexed
    for (const auto& [id, elem] : mesh.elements) {
        if (!elem.indexAssigned) {
            errorMessage_ = "Element " + std::to_string(id) + " was not indexed";
            return false;
        }
    }

    // Normalize indices to start from 0
    int minI = 0, minJ = 0, minK = 0;
    for (const auto& [id, elem] : mesh.elements) {
        minI = std::min(minI, elem.i);
        minJ = std::min(minJ, elem.j);
        minK = std::min(minK, elem.k);
    }

    for (auto& [id, elem] : mesh.elements) {
        elem.i -= minI;
        elem.j -= minJ;
        elem.k -= minK;
    }

    return true;
}

void StructuredGridIndexer::swapAxes(Mesh& mesh, int axis1, int axis2) {
    for (auto& [id, elem] : mesh.elements) {
        std::array<int, 3> idx = {elem.i, elem.j, elem.k};
        std::swap(idx[axis1], idx[axis2]);
        elem.i = idx[0];
        elem.j = idx[1];
        elem.k = idx[2];
    }

    if (axis1 == 0 || axis2 == 0) {
        if (axis1 == 1 || axis2 == 1) {
            std::swap(dimI_, dimJ_);
        } else {
            std::swap(dimI_, dimK_);
        }
    } else {
        std::swap(dimJ_, dimK_);
    }
}

bool StructuredGridIndexer::reorderElementNodes(Mesh& mesh) {
    // Reorder nodes within each element so that the local order follows the grid:
    // - Nodes 0-3 are on the k- face (bottom), nodes 4-7 are on the k+ face (top)
    //   Bottom (k-): n0 at (i-,j-), n1 at (i+,j-), n2 at (i+,j+), n3 at (i-,j+)
    //   Top (k+):    n4 at (i-,j-), n5 at (i+,j-), n6 at (i+,j+), n7 at (i-,j+)
    //
    // The order is read off the topology: the face an element shares with its
    // grid neighbour at i+1 is its i+ face, and so on for the six sides (a side
    // with no neighbour is the face opposite the one that has; with none on
    // either side, the element beside it settles which is which); a corner is
    // the one node the three faces meeting there have in common.
    //
    // This used to be a geometric estimate -- local axes from the neighbours'
    // centroids, each node put in the octant its offset from the element
    // centroid pointed to. On a tight fold two nodes fall in one octant and the
    // wrong one took the corner: unfold then wrote elements with a node set the
    // input never had (15 of 250 on a teardrop, rc 0). map was spared only
    // because it reads the reference through the node grid the boundary
    // extractor builds from shared nodes, not through this order. There is no
    // fallback to that estimate: indices that do not agree with the faces are
    // refused.
    errorMessage_.clear();

    std::unordered_map<std::tuple<int,int,int>, const Element*, GridIndexHash> elemLookup;
    elemLookup.reserve(mesh.elements.size());
    for (const auto& [id, elem] : mesh.elements) {
        if (elem.indexAssigned) {
            elemLookup[{elem.i, elem.j, elem.k}] = &elem;
        }
    }

    const auto& faces = topo::facesOf(ElementType::HEX8);
    // LS-DYNA position -> side of the corner along (i,j,k): 0 = minus, 1 = plus
    static constexpr int CORNER_SIDES[8][3] = {
        {0,0,0}, {1,0,0}, {1,1,0}, {0,1,0},
        {0,0,1}, {1,0,1}, {1,1,1}, {0,1,1}
    };
    static constexpr char AXIS_NAMES[3] = {'i', 'j', 'k'};

    // How many nodes local face fa of a has in common with local face fb of b.
    auto commonNodes = [&faces](const Element& a, int fa, const Element& b, int fb) {
        int common = 0;
        for (int x = 0; x < Element::NODES_PER_FACE; ++x) {
            for (int y = 0; y < Element::NODES_PER_FACE; ++y) {
                if (a.nodeIds[faces[fa].v[x]] == b.nodeIds[faces[fb].v[y]]) { ++common; break; }
            }
        }
        return common;
    };
    auto neighborAt = [&elemLookup](const Element& elem, int axis, int side) -> const Element* {
        std::array<int, 3> at = {elem.i, elem.j, elem.k};
        at[axis] += side ? 1 : -1;
        auto it = elemLookup.find({at[0], at[1], at[2]});
        return it == elemLookup.end() ? nullptr : it->second;
    };

    // face[axis][side]: the local face of the element looking along that side
    // of the grid. Node ids stay untouched until every element has its faces --
    // the faces are local numbers in the order the element came in with.
    struct Sides { int face[3][2]; };
    std::unordered_map<int, Sides> sidesOf;
    sidesOf.reserve(mesh.elements.size());
    // An element with no grid neighbour on either side of an axis (the one
    // above a hole in a two-layer block): the pair of faces is known, which of
    // the two looks along minus is not yet.
    struct Open { int id; int axis; int pair; };
    std::vector<Open> open;

    for (const auto& [id, elem] : mesh.elements) {
        if (!elem.indexAssigned) continue;

        Sides sides = {{{-1, -1}, {-1, -1}, {-1, -1}}};
        for (int axis = 0; axis < 3; ++axis) {
            for (int side = 0; side < 2; ++side) {
                const Element* neighbor = neighborAt(elem, axis, side);
                if (!neighbor) continue;

                // A neighbour is read by its node set only.
                for (int f = 0; f < Element::NUM_FACES && sides.face[axis][side] < 0; ++f) {
                    int common = 0;
                    for (int x = 0; x < Element::NODES_PER_FACE; ++x) {
                        int node = elem.nodeIds[faces[f].v[x]];
                        for (int y = 0; y < 8; ++y) {
                            if (neighbor->nodeIds[y] == node) { ++common; break; }
                        }
                    }
                    if (common == Element::NODES_PER_FACE) sides.face[axis][side] = f;
                }
                if (sides.face[axis][side] < 0) {
                    errorMessage_ = "elements " + std::to_string(id) + " and " + std::to_string(neighbor->id) +
                        " are neighbours along " + AXIS_NAMES[axis] + " in the grid but share no face";
                    return false;
                }
            }
        }

        std::array<bool, 3> pairTaken = {false, false, false};
        int openAxis = -1;
        for (int axis = 0; axis < 3; ++axis) {
            int& minus = sides.face[axis][0];
            int& plus = sides.face[axis][1];
            if (minus < 0 && plus < 0) {
                if (openAxis >= 0) {
                    errorMessage_ = "element " + std::to_string(id) + " has no grid neighbour along " +
                        AXIS_NAMES[openAxis] + " nor along " + AXIS_NAMES[axis];
                    return false;
                }
                openAxis = axis;
                continue;
            }
            // Faces pair up as (0,1) (2,3) (4,5): f ^ 1 is the opposite face.
            if (minus < 0) minus = plus ^ 1;
            if (plus < 0) plus = minus ^ 1;
            if (plus != (minus ^ 1) || pairTaken[minus / 2]) {
                errorMessage_ = "the grid neighbours of element " + std::to_string(id) +
                    " do not sit on three pairs of opposite faces";
                return false;
            }
            pairTaken[minus / 2] = true;
        }
        if (openAxis >= 0) {
            open.push_back({id, openAxis, !pairTaken[0] ? 0 : !pairTaken[1] ? 1 : 2});
        }
        sidesOf.emplace(id, sides);
    }

    // The open side is settled from beside: across a face the two elements
    // share, the minus face of one continues the minus face of the other along
    // an edge of that shared face (the rule the index walk carries its frame
    // by). A neighbour that is open itself waits for its own turn.
    for (bool progress = true; progress && !open.empty(); ) {
        progress = false;
        for (size_t n = 0; n < open.size(); ) {
            const Open o = open[n];
            const Element& elem = mesh.elements.at(o.id);
            int minusFace = -1;
            for (int axis = 0; axis < 3; ++axis) {
                if (axis == o.axis) continue;
                for (int side = 0; side < 2; ++side) {
                    const Element* neighbor = neighborAt(elem, axis, side);
                    if (!neighbor) continue;
                    const int theirs = sidesOf.at(neighbor->id).face[o.axis][0];
                    if (theirs < 0) continue;
                    for (int mine = o.pair * 2; mine < o.pair * 2 + 2; ++mine) {
                        if (commonNodes(elem, mine, *neighbor, theirs) != 2) continue;
                        if (minusFace >= 0 && minusFace != mine) {
                            errorMessage_ = "the grid neighbours of element " + std::to_string(o.id) +
                                " disagree on which of its faces looks along -" + AXIS_NAMES[o.axis];
                            return false;
                        }
                        minusFace = mine;
                    }
                }
            }
            if (minusFace < 0) { ++n; continue; }
            Sides& sides = sidesOf.at(o.id);
            sides.face[o.axis][0] = minusFace;
            sides.face[o.axis][1] = minusFace ^ 1;
            open[n] = open.back();
            open.pop_back();
            progress = true;
        }
    }
    if (!open.empty()) {
        errorMessage_ = "element " + std::to_string(open.front().id) + " has no grid neighbour along " +
            AXIS_NAMES[open.front().axis] + ", and none beside it settles that side";
        return false;
    }

    for (auto& [id, elem] : mesh.elements) {
        if (!elem.indexAssigned) continue;
        const Sides& sides = sidesOf.at(id);
        const std::array<int, 8> nodeIds = elem.nodeIds;

        // Three faces from three different pairs meet in exactly one corner.
        for (int lsPos = 0; lsPos < 8; ++lsPos) {
            const auto& fi = faces[sides.face[0][CORNER_SIDES[lsPos][0]]];
            const auto& fj = faces[sides.face[1][CORNER_SIDES[lsPos][1]]];
            const auto& fk = faces[sides.face[2][CORNER_SIDES[lsPos][2]]];
            for (int x = 0; x < Element::NODES_PER_FACE; ++x) {
                const int local = fi.v[x];
                bool onJ = false, onK = false;
                for (int y = 0; y < Element::NODES_PER_FACE; ++y) {
                    onJ = onJ || fj.v[y] == local;
                    onK = onK || fk.v[y] == local;
                }
                if (onJ && onK) elem.nodeIds[lsPos] = nodeIds[local];
            }
        }
    }

    return true;
}

} // namespace KooRemapper
