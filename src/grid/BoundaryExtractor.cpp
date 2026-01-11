#include "grid/BoundaryExtractor.h"
#include <set>
#include <algorithm>

namespace KooRemapper {

BoundaryExtractor::BoundaryExtractor()
    : dimI_(0), dimJ_(0), dimK_(0)
{
    cornerNodes_.fill(0);
}

void BoundaryExtractor::extract(const Mesh& mesh) {
    // Clear previous data
    faceI0_.clear(); faceIM_.clear();
    faceJ0_.clear(); faceJN_.clear();
    faceK0_.clear(); faceKP_.clear();

    if (!mesh.gridDimensionsSet) {
        return;
    }

    dimI_ = mesh.dimI;
    dimJ_ = mesh.dimJ;
    dimK_ = mesh.dimK;

    // Categorize elements by their boundary position
    for (const auto& [id, elem] : mesh.elements) {
        if (!elem.indexAssigned) continue;

        if (elem.i == 0) faceI0_.push_back(&elem);
        if (elem.i == dimI_ - 1) faceIM_.push_back(&elem);
        if (elem.j == 0) faceJ0_.push_back(&elem);
        if (elem.j == dimJ_ - 1) faceJN_.push_back(&elem);
        if (elem.k == 0) faceK0_.push_back(&elem);
        if (elem.k == dimK_ - 1) faceKP_.push_back(&elem);
    }

    // Build node grid and extract corner/edge nodes
    buildNodeGrid(mesh);
    extractCornerNodes();
    extractEdgeNodes();
}

void BoundaryExtractor::buildNodeGrid(const Mesh& mesh) {
    // For structured grid, we need (dimI+1) x (dimJ+1) x (dimK+1) nodes
    int ni = dimI_ + 1;
    int nj = dimJ_ + 1;
    int nk = dimK_ + 1;

    // Initialize grid with -1 (no node)
    nodeGrid_.resize(ni);
    for (int i = 0; i < ni; ++i) {
        nodeGrid_[i].resize(nj);
        for (int j = 0; j < nj; ++j) {
            nodeGrid_[i][j].resize(nk, -1);
        }
    }

    // Map element corner nodes to grid positions
    // Each element at (i,j,k) contributes 8 nodes at corners
    for (const auto& [id, elem] : mesh.elements) {
        if (!elem.indexAssigned) continue;

        int ei = elem.i;
        int ej = elem.j;
        int ek = elem.k;

        // Node mapping for hexahedron:
        // Local node 0 -> (i, j, k)
        // Local node 1 -> (i+1, j, k)
        // Local node 2 -> (i+1, j+1, k)
        // Local node 3 -> (i, j+1, k)
        // Local node 4 -> (i, j, k+1)
        // Local node 5 -> (i+1, j, k+1)
        // Local node 6 -> (i+1, j+1, k+1)
        // Local node 7 -> (i, j+1, k+1)

        std::array<std::array<int, 3>, 8> offsets = {{
            {0, 0, 0}, {1, 0, 0}, {1, 1, 0}, {0, 1, 0},
            {0, 0, 1}, {1, 0, 1}, {1, 1, 1}, {0, 1, 1}
        }};

        for (int n = 0; n < 8; ++n) {
            int gi = ei + offsets[n][0];
            int gj = ej + offsets[n][1];
            int gk = ek + offsets[n][2];

            if (gi < ni && gj < nj && gk < nk) {
                nodeGrid_[gi][gj][gk] = elem.nodeIds[n];
            }
        }
    }
}

void BoundaryExtractor::extractCornerNodes() {
    int ni = dimI_;
    int nj = dimJ_;
    int nk = dimK_;

    // 8 corners of the grid
    // Corner 0: (0, 0, 0)
    // Corner 1: (dimI, 0, 0)
    // Corner 2: (dimI, dimJ, 0)
    // Corner 3: (0, dimJ, 0)
    // Corner 4: (0, 0, dimK)
    // Corner 5: (dimI, 0, dimK)
    // Corner 6: (dimI, dimJ, dimK)
    // Corner 7: (0, dimJ, dimK)

    if (nodeGrid_.size() > 0 && nodeGrid_[0].size() > 0 && nodeGrid_[0][0].size() > 0) {
        cornerNodes_[0] = nodeGrid_[0][0][0];
        cornerNodes_[1] = nodeGrid_[ni][0][0];
        cornerNodes_[2] = nodeGrid_[ni][nj][0];
        cornerNodes_[3] = nodeGrid_[0][nj][0];
        cornerNodes_[4] = nodeGrid_[0][0][nk];
        cornerNodes_[5] = nodeGrid_[ni][0][nk];
        cornerNodes_[6] = nodeGrid_[ni][nj][nk];
        cornerNodes_[7] = nodeGrid_[0][nj][nk];
    }
}

void BoundaryExtractor::extractEdgeNodes() {
    int ni = dimI_;
    int nj = dimJ_;
    int nk = dimK_;

    // 12 edges of the hexahedral grid
    // Edges along i-axis (4 edges)
    // Edge 0: j=0, k=0 (i varies 0 to dimI)
    edgeNodes_[0].axis = 0;
    edgeNodes_[0].nodeIds.clear();
    for (int i = 0; i <= ni; ++i) {
        edgeNodes_[0].nodeIds.push_back(nodeGrid_[i][0][0]);
    }

    // Edge 1: j=dimJ, k=0
    edgeNodes_[1].axis = 0;
    edgeNodes_[1].nodeIds.clear();
    for (int i = 0; i <= ni; ++i) {
        edgeNodes_[1].nodeIds.push_back(nodeGrid_[i][nj][0]);
    }

    // Edge 2: j=0, k=dimK
    edgeNodes_[2].axis = 0;
    edgeNodes_[2].nodeIds.clear();
    for (int i = 0; i <= ni; ++i) {
        edgeNodes_[2].nodeIds.push_back(nodeGrid_[i][0][nk]);
    }

    // Edge 3: j=dimJ, k=dimK
    edgeNodes_[3].axis = 0;
    edgeNodes_[3].nodeIds.clear();
    for (int i = 0; i <= ni; ++i) {
        edgeNodes_[3].nodeIds.push_back(nodeGrid_[i][nj][nk]);
    }

    // Edges along j-axis (4 edges)
    // Edge 4: i=0, k=0
    edgeNodes_[4].axis = 1;
    edgeNodes_[4].nodeIds.clear();
    for (int j = 0; j <= nj; ++j) {
        edgeNodes_[4].nodeIds.push_back(nodeGrid_[0][j][0]);
    }

    // Edge 5: i=dimI, k=0
    edgeNodes_[5].axis = 1;
    edgeNodes_[5].nodeIds.clear();
    for (int j = 0; j <= nj; ++j) {
        edgeNodes_[5].nodeIds.push_back(nodeGrid_[ni][j][0]);
    }

    // Edge 6: i=0, k=dimK
    edgeNodes_[6].axis = 1;
    edgeNodes_[6].nodeIds.clear();
    for (int j = 0; j <= nj; ++j) {
        edgeNodes_[6].nodeIds.push_back(nodeGrid_[0][j][nk]);
    }

    // Edge 7: i=dimI, k=dimK
    edgeNodes_[7].axis = 1;
    edgeNodes_[7].nodeIds.clear();
    for (int j = 0; j <= nj; ++j) {
        edgeNodes_[7].nodeIds.push_back(nodeGrid_[ni][j][nk]);
    }

    // Edges along k-axis (4 edges)
    // Edge 8: i=0, j=0
    edgeNodes_[8].axis = 2;
    edgeNodes_[8].nodeIds.clear();
    for (int k = 0; k <= nk; ++k) {
        edgeNodes_[8].nodeIds.push_back(nodeGrid_[0][0][k]);
    }

    // Edge 9: i=dimI, j=0
    edgeNodes_[9].axis = 2;
    edgeNodes_[9].nodeIds.clear();
    for (int k = 0; k <= nk; ++k) {
        edgeNodes_[9].nodeIds.push_back(nodeGrid_[ni][0][k]);
    }

    // Edge 10: i=0, j=dimJ
    edgeNodes_[10].axis = 2;
    edgeNodes_[10].nodeIds.clear();
    for (int k = 0; k <= nk; ++k) {
        edgeNodes_[10].nodeIds.push_back(nodeGrid_[0][nj][k]);
    }

    // Edge 11: i=dimI, j=dimJ
    edgeNodes_[11].axis = 2;
    edgeNodes_[11].nodeIds.clear();
    for (int k = 0; k <= nk; ++k) {
        edgeNodes_[11].nodeIds.push_back(nodeGrid_[ni][nj][k]);
    }
}

std::vector<int> BoundaryExtractor::getNodesOnFaceI0() const {
    std::set<int> nodes;
    for (const auto* elem : faceI0_) {
        // Face i=0 uses local nodes 0,3,7,4
        nodes.insert(elem->nodeIds[0]);
        nodes.insert(elem->nodeIds[3]);
        nodes.insert(elem->nodeIds[7]);
        nodes.insert(elem->nodeIds[4]);
    }
    return std::vector<int>(nodes.begin(), nodes.end());
}

std::vector<int> BoundaryExtractor::getNodesOnFaceIM() const {
    std::set<int> nodes;
    for (const auto* elem : faceIM_) {
        // Face i=max uses local nodes 1,2,6,5
        nodes.insert(elem->nodeIds[1]);
        nodes.insert(elem->nodeIds[2]);
        nodes.insert(elem->nodeIds[6]);
        nodes.insert(elem->nodeIds[5]);
    }
    return std::vector<int>(nodes.begin(), nodes.end());
}

std::vector<int> BoundaryExtractor::getNodesOnFaceJ0() const {
    std::set<int> nodes;
    for (const auto* elem : faceJ0_) {
        // Face j=0 uses local nodes 0,1,5,4
        nodes.insert(elem->nodeIds[0]);
        nodes.insert(elem->nodeIds[1]);
        nodes.insert(elem->nodeIds[5]);
        nodes.insert(elem->nodeIds[4]);
    }
    return std::vector<int>(nodes.begin(), nodes.end());
}

std::vector<int> BoundaryExtractor::getNodesOnFaceJN() const {
    std::set<int> nodes;
    for (const auto* elem : faceJN_) {
        // Face j=max uses local nodes 3,2,6,7
        nodes.insert(elem->nodeIds[3]);
        nodes.insert(elem->nodeIds[2]);
        nodes.insert(elem->nodeIds[6]);
        nodes.insert(elem->nodeIds[7]);
    }
    return std::vector<int>(nodes.begin(), nodes.end());
}

std::vector<int> BoundaryExtractor::getNodesOnFaceK0() const {
    std::set<int> nodes;
    for (const auto* elem : faceK0_) {
        // Face k=0 uses local nodes 0,1,2,3
        nodes.insert(elem->nodeIds[0]);
        nodes.insert(elem->nodeIds[1]);
        nodes.insert(elem->nodeIds[2]);
        nodes.insert(elem->nodeIds[3]);
    }
    return std::vector<int>(nodes.begin(), nodes.end());
}

std::vector<int> BoundaryExtractor::getNodesOnFaceKP() const {
    std::set<int> nodes;
    for (const auto* elem : faceKP_) {
        // Face k=max uses local nodes 4,5,6,7
        nodes.insert(elem->nodeIds[4]);
        nodes.insert(elem->nodeIds[5]);
        nodes.insert(elem->nodeIds[6]);
        nodes.insert(elem->nodeIds[7]);
    }
    return std::vector<int>(nodes.begin(), nodes.end());
}

} // namespace KooRemapper
