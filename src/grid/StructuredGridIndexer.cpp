#include "grid/StructuredGridIndexer.h"
#include <algorithm>
#include <queue>
#include <tuple>
#include <set>

namespace KooRemapper {

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
}

bool StructuredGridIndexer::assignIndices(Mesh& mesh,
                                          const ConnectivityAnalyzer& connectivity) {
    errorMessage_.clear();
    dimI_ = dimJ_ = dimK_ = 0;

    if (mesh.elements.empty()) {
        errorMessage_ = "Mesh has no elements";
        return false;
    }

    // Reset all indices
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

    // Determine initial directions
    if (!determineInitialDirections(mesh, startElem, connectivity)) {
        return false;
    }

    // Propagate indices via BFS
    if (!propagateIndices(mesh, startElem, connectivity)) {
        return false;
    }

    // Calculate dimensions
    calculateDimensions(mesh);

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

} // namespace KooRemapper
