#include "grid/StructuredGridIndexer.h"
#include <algorithm>
#include <queue>
#include <tuple>
#include <set>
#include <cmath>

namespace KooRemapper {

StructuredGridIndexer::StructuredGridIndexer()
    : dimI_(0), dimJ_(0), dimK_(0), mesh_(nullptr)
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
    mesh_ = &mesh;  // Store mesh pointer for geometry queries

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

    // Propagate indices via BFS using geometry-based axis detection
    if (!propagateIndicesGeometry(mesh, startElem, connectivity)) {
        return false;
    }

    // Calculate dimensions
    calculateDimensions(mesh);

    // Update mesh dimensions
    mesh.setGridDimensions(dimI_, dimJ_, dimK_);

    mesh_ = nullptr;
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

    auto neighbors = connectivity.getNeighbors(startElem);
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

        auto neighbors = connectivity.getNeighbors(elemId);

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

    auto neighbors = connectivity.getNeighbors(startElem);
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

    // Now pair1 and pair2 are the most orthogonal pair
    // Assign them to the two world axes they're most aligned with
    // The third direction gets the remaining axis

    // For each direction, find its dominant world axis component
    auto getDominantAxis = [](const Vector3D& dir) -> int {
        double ax = std::abs(dir.x);
        double ay = std::abs(dir.y);
        double az = std::abs(dir.z);
        if (ax >= ay && ax >= az) return 0;
        if (ay >= ax && ay >= az) return 1;
        return 2;
    };

    std::array<int, 3> dirToAxis = {-1, -1, -1};
    std::array<bool, 3> axisUsed = {false, false, false};

    // Assign pair1 to its dominant axis
    int axis1 = getDominantAxis(directions[pair1]);
    dirToAxis[pair1] = axis1;
    axisUsed[axis1] = true;

    // Assign pair2 to its dominant axis (if not taken)
    int axis2 = getDominantAxis(directions[pair2]);
    if (axisUsed[axis2]) {
        // Find next best axis for pair2
        double scores[3] = {std::abs(directions[pair2].x),
                            std::abs(directions[pair2].y),
                            std::abs(directions[pair2].z)};
        double bestScore = -1.0;
        for (int a = 0; a < 3; ++a) {
            if (!axisUsed[a] && scores[a] > bestScore) {
                bestScore = scores[a];
                axis2 = a;
            }
        }
    }
    dirToAxis[pair2] = axis2;
    axisUsed[axis2] = true;

    // Third direction gets the remaining axis
    for (int a = 0; a < 3; ++a) {
        if (!axisUsed[a]) {
            dirToAxis[third] = a;
            break;
        }
    }

    // Build axisToDir (inverse mapping)
    std::array<int, 3> axisToDir = {-1, -1, -1};
    for (int d = 0; d < 3; ++d) {
        if (dirToAxis[d] >= 0) {
            axisToDir[dirToAxis[d]] = d;
        }
    }

    // Store axis directions
    for (int axis = 0; axis < 3; ++axis) {
        int dirIdx = axisToDir[axis];
        if (dirIdx >= 0) {
            axisDirections_[axis] = directions[dirIdx];
        } else {
            errorMessage_ = "Failed to assign axis " + std::to_string(axis);
            return false;
        }
    }

    // CRITICAL: Ensure consistent k-axis direction for correct layer mapping
    // k=0 should be at the "outer" side (larger radius for arc/curved meshes)
    // k=max should be at the "inner" side (smaller radius)
    //
    // For arc/curved meshes, the "outer" side has larger Y values (further from center)
    // So k+ direction should point toward smaller Y (inward)
    //
    // We check the k-axis direction's Y component:
    // - If k+ points toward larger Y (outward), flip it so k+ points inward
    // - This ensures k=0 is outer, k=max is inner
    //
    // For flat meshes where k is typically Z (thickness), we want:
    // - k=0 at bottom (minZ), k=max at top (maxZ)
    // - So k+ should point toward larger Z
    //
    // Heuristic: If |kAxis.y| > |kAxis.z|, it's radial (Y-dominant)
    //            Otherwise it's thickness (Z-dominant)
    Vector3D& kAxis = axisDirections_[2];
    if (std::abs(kAxis.y) > std::abs(kAxis.z)) {
        // Radial direction (Y-dominant) - k+ should point inward (toward smaller Y)
        // This makes k=0 = outer, k=max = inner
        if (kAxis.y > 0) {
            kAxis = kAxis * -1.0;  // Flip so k+ points toward smaller Y
        }
    } else {
        // Thickness direction (Z-dominant) - k+ should point upward (toward larger Z)
        // This makes k=0 = bottom, k=max = top
        if (kAxis.z < 0) {
            kAxis = kAxis * -1.0;  // Flip so k+ points toward larger Z
        }
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

bool StructuredGridIndexer::propagateIndicesGeometry(Mesh& mesh, int startElem,
                                                      const ConnectivityAnalyzer& connectivity) {
    // BFS queue: element ID (i,j,k is stored in element itself)
    std::queue<int> queue;

    // Start at origin
    Element* startElement = mesh.getElement(startElem);
    if (!startElement) {
        errorMessage_ = "Start element not found";
        return false;
    }

    startElement->setGridIndex(0, 0, 0);
    queue.push(startElem);

    // For the start element, we need to assign initial axes based on neighbors
    // We'll use the axisDirections_ computed in determineInitialDirectionsGeometry
    // as the reference directions for the first neighbors

    int processedCount = 0;

    while (!queue.empty()) {
        int elemId = queue.front();
        queue.pop();

        Element* currentElem = mesh.getElement(elemId);
        if (!currentElem) continue;

        int i = currentElem->i;
        int j = currentElem->j;
        int k = currentElem->k;

        Vector3D currentCentroid = calculateElementCentroid(mesh, elemId);
        auto neighbors = connectivity.getNeighbors(elemId);

        // Build local axes from ALREADY INDEXED neighbors
        // For each indexed neighbor, we know what index change it represents
        std::array<Vector3D, 3> localAxes = {{Vector3D(0,0,0), Vector3D(0,0,0), Vector3D(0,0,0)}};
        std::array<bool, 3> axisFound = {false, false, false};

        for (const auto& neighbor : neighbors) {
            Element* neighborElem = mesh.getElement(neighbor.neighborElementId);
            if (!neighborElem || !neighborElem->indexAssigned) continue;

            // Calculate direction to this neighbor
            Vector3D neighborCentroid = calculateElementCentroid(mesh, neighbor.neighborElementId);
            Vector3D direction = neighborCentroid - currentCentroid;
            direction = direction.normalized();

            // Determine which axis this neighbor represents based on index difference
            int di = neighborElem->i - i;
            int dj = neighborElem->j - j;
            int dk = neighborElem->k - k;

            if (di != 0 && !axisFound[0]) {
                localAxes[0] = direction * static_cast<double>(di > 0 ? 1 : -1);
                axisFound[0] = true;
            } else if (dj != 0 && !axisFound[1]) {
                localAxes[1] = direction * static_cast<double>(dj > 0 ? 1 : -1);
                axisFound[1] = true;
            } else if (dk != 0 && !axisFound[2]) {
                localAxes[2] = direction * static_cast<double>(dk > 0 ? 1 : -1);
                axisFound[2] = true;
            }
        }

        // Fill in missing axes with global defaults
        for (int ax = 0; ax < 3; ++ax) {
            if (!axisFound[ax]) {
                localAxes[ax] = axisDirections_[ax];
            }
        }

        // Now process unindexed neighbors
        for (const auto& neighbor : neighbors) {
            Element* neighborElem = mesh.getElement(neighbor.neighborElementId);
            if (!neighborElem || neighborElem->indexAssigned) {
                continue;
            }

            // Calculate direction from current element to neighbor
            Vector3D neighborCentroid = calculateElementCentroid(mesh, neighbor.neighborElementId);
            Vector3D direction = neighborCentroid - currentCentroid;
            direction = direction.normalized();

            // Determine which axis this direction corresponds to using local axes
            int bestAxis = 0;
            int bestSign = 1;
            double bestAbsDot = -1.0;  // Start with -1 so any valid dot product wins

            for (int axis = 0; axis < 3; ++axis) {
                double dot = direction.dot(localAxes[axis]);
                double absDot = std::abs(dot);
                if (absDot > bestAbsDot) {
                    bestAbsDot = absDot;
                    bestAxis = axis;
                    bestSign = (dot >= 0) ? 1 : -1;
                }
            }

            int ni = i, nj = j, nk = k;
            switch (bestAxis) {
                case 0: ni += bestSign; break;
                case 1: nj += bestSign; break;
                case 2: nk += bestSign; break;
            }

            neighborElem->setGridIndex(ni, nj, nk);
            queue.push(neighbor.neighborElementId);
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

void StructuredGridIndexer::reorderElementNodes(Mesh& mesh) {
    // Reorder nodes within each element based on geometry so that:
    // - k-axis is the smallest dimension (thickness direction)
    // - Nodes 0-3 are on the k- face (bottom), nodes 4-7 are on the k+ face (top)
    // - On each face, nodes are ordered CCW when viewed from outside
    //   Bottom (k-): n0 at (i-,j-), n1 at (i+,j-), n2 at (i+,j+), n3 at (i-,j+)
    //   Top (k+):    n4 at (i-,j-), n5 at (i+,j-), n6 at (i+,j+), n7 at (i-,j+)

    // Build element lookup by (i,j,k) for neighbor queries
    std::map<std::tuple<int,int,int>, const Element*> elemLookup;
    for (const auto& [id, elem] : mesh.elements) {
        if (elem.indexAssigned) {
            elemLookup[{elem.i, elem.j, elem.k}] = &elem;
        }
    }

    for (auto& [id, elem] : mesh.elements) {
        if (!elem.indexAssigned) continue;

        // Get all 8 node positions
        std::array<Vector3D, 8> nodePos;
        std::array<int, 8> nodeIds = elem.nodeIds;
        bool valid = true;

        for (int n = 0; n < 8; ++n) {
            const Node* node = mesh.getNode(nodeIds[n]);
            if (!node) {
                valid = false;
                break;
            }
            nodePos[n] = node->position;
        }

        if (!valid) continue;

        // Calculate element centroid
        Vector3D centroid(0, 0, 0);
        for (int n = 0; n < 8; ++n) {
            centroid += nodePos[n];
        }
        centroid /= 8.0;

        // Determine LOCAL axis directions from neighboring elements' centroids
        // This handles curved meshes where global axis directions don't apply
        Vector3D iAxis(0, 0, 0), jAxis(0, 0, 0), kAxis(0, 0, 0);

        // Check neighbors in +/- i direction
        auto iPlus = elemLookup.find({elem.i + 1, elem.j, elem.k});
        auto iMinus = elemLookup.find({elem.i - 1, elem.j, elem.k});
        if (iPlus != elemLookup.end()) {
            iAxis += calculateElementCentroid(mesh, iPlus->second->id) - centroid;
        }
        if (iMinus != elemLookup.end()) {
            iAxis += centroid - calculateElementCentroid(mesh, iMinus->second->id);
        }
        if (iAxis.magnitude() > 1e-10) {
            iAxis = iAxis.normalized();
        } else {
            iAxis = axisDirections_[0];  // Fallback to global
        }

        // Check neighbors in +/- j direction
        auto jPlus = elemLookup.find({elem.i, elem.j + 1, elem.k});
        auto jMinus = elemLookup.find({elem.i, elem.j - 1, elem.k});
        if (jPlus != elemLookup.end()) {
            jAxis += calculateElementCentroid(mesh, jPlus->second->id) - centroid;
        }
        if (jMinus != elemLookup.end()) {
            jAxis += centroid - calculateElementCentroid(mesh, jMinus->second->id);
        }
        if (jAxis.magnitude() > 1e-10) {
            jAxis = jAxis.normalized();
        } else {
            jAxis = axisDirections_[1];  // Fallback to global
        }

        // Check neighbors in +/- k direction
        auto kPlus = elemLookup.find({elem.i, elem.j, elem.k + 1});
        auto kMinus = elemLookup.find({elem.i, elem.j, elem.k - 1});
        if (kPlus != elemLookup.end()) {
            kAxis += calculateElementCentroid(mesh, kPlus->second->id) - centroid;
        }
        if (kMinus != elemLookup.end()) {
            kAxis += centroid - calculateElementCentroid(mesh, kMinus->second->id);
        }
        if (kAxis.magnitude() > 1e-10) {
            kAxis = kAxis.normalized();
        } else {
            kAxis = axisDirections_[2];  // Fallback to global
        }

        // For each of the 8 nodes, determine which corner it belongs to
        // Corner index: (iSign > 0 ? 1 : 0) + (jSign > 0 ? 2 : 0) + (kSign > 0 ? 4 : 0)
        // This gives: 0=(---), 1=(+--), 2=(-+-), 3=(++-), 4=(--+), 5=(+-+), 6=(-++), 7=(+++)

        // LS-DYNA standard ordering maps to:
        // n0: (i-,j-,k-) -> corner 0
        // n1: (i+,j-,k-) -> corner 1
        // n2: (i+,j+,k-) -> corner 3
        // n3: (i-,j+,k-) -> corner 2
        // n4: (i-,j-,k+) -> corner 4
        // n5: (i+,j-,k+) -> corner 5
        // n6: (i+,j+,k+) -> corner 7
        // n7: (i-,j+,k+) -> corner 6

        std::array<int, 8> cornerToLSDyna = {0, 1, 3, 2, 4, 5, 7, 6};

        // For each node, find which corner it's closest to
        std::array<int, 8> nodeToCorner;
        std::array<double, 8> nodeScores;
        nodeScores.fill(-1e30);

        for (int n = 0; n < 8; ++n) {
            Vector3D relPos = nodePos[n] - centroid;

            double iDot = relPos.dot(iAxis);
            double jDot = relPos.dot(jAxis);
            double kDot = relPos.dot(kAxis);

            int corner = (iDot > 0 ? 1 : 0) + (jDot > 0 ? 2 : 0) + (kDot > 0 ? 4 : 0);
            double score = std::abs(iDot) + std::abs(jDot) + std::abs(kDot);

            nodeToCorner[n] = corner;
            nodeScores[n] = score;
        }

        // Build new node order: for each LS-DYNA position, find the node at that corner
        std::array<int, 8> newNodeIds;
        std::array<bool, 8> nodeUsed;
        nodeUsed.fill(false);

        for (int lsPos = 0; lsPos < 8; ++lsPos) {
            int targetCorner = cornerToLSDyna[lsPos];

            // Find best node for this corner (not yet used)
            int bestNode = -1;
            double bestScore = -1e30;

            for (int n = 0; n < 8; ++n) {
                if (nodeUsed[n]) continue;
                if (nodeToCorner[n] == targetCorner) {
                    if (nodeScores[n] > bestScore) {
                        bestScore = nodeScores[n];
                        bestNode = n;
                    }
                }
            }

            // If no exact match, find closest node
            if (bestNode < 0) {
                for (int n = 0; n < 8; ++n) {
                    if (nodeUsed[n]) continue;
                    // Calculate how well this node matches the target corner
                    Vector3D relPos = nodePos[n] - centroid;
                    double iDot = relPos.dot(iAxis);
                    double jDot = relPos.dot(jAxis);
                    double kDot = relPos.dot(kAxis);

                    // Target corner signs
                    int iTarget = (targetCorner & 1) ? 1 : -1;
                    int jTarget = (targetCorner & 2) ? 1 : -1;
                    int kTarget = (targetCorner & 4) ? 1 : -1;

                    double score = iDot * iTarget + jDot * jTarget + kDot * kTarget;
                    if (score > bestScore) {
                        bestScore = score;
                        bestNode = n;
                    }
                }
            }

            if (bestNode >= 0) {
                newNodeIds[lsPos] = nodeIds[bestNode];
                nodeUsed[bestNode] = true;
            } else {
                // Fallback - should not happen
                newNodeIds[lsPos] = nodeIds[lsPos];
            }
        }

        // Update element with reordered nodes
        elem.nodeIds = newNodeIds;
    }
}

} // namespace KooRemapper
