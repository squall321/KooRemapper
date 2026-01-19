#include "grid/BoundaryExtractor.h"
#include "core/Vector3D.h"
#include <set>
#include <algorithm>
#include <map>
#include <cmath>

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

    // Build element lookup by (i,j,k)
    std::map<std::tuple<int,int,int>, const Element*> elemLookup;
    for (const auto& [id, elem] : mesh.elements) {
        if (elem.indexAssigned) {
            elemLookup[{elem.i, elem.j, elem.k}] = &elem;
        }
    }

    // First pass: compute element centroids for geometry-based node selection
    std::map<std::tuple<int,int,int>, Vector3D> elemCentroids;
    for (const auto& [id, elem] : mesh.elements) {
        if (elem.indexAssigned) {
            Vector3D centroid(0, 0, 0);
            for (int n = 0; n < 8; ++n) {
                const Node* node = mesh.getNode(elem.nodeIds[n]);
                if (node) {
                    centroid += node->position;
                }
            }
            centroid /= 8.0;
            elemCentroids[{elem.i, elem.j, elem.k}] = centroid;
        }
    }

    // Build node-to-elements reverse index for O(1) lookup
    std::map<int, std::vector<std::tuple<int,int,int>>> nodeToElems;
    for (const auto& [id, elem] : mesh.elements) {
        if (elem.indexAssigned) {
            for (int n = 0; n < 8; ++n) {
                nodeToElems[elem.nodeIds[n]].push_back({elem.i, elem.j, elem.k});
            }
        }
    }

    // For each grid node position (gi,gj,gk), find the correct node ID
    for (int gi = 0; gi < ni; ++gi) {
        for (int gj = 0; gj < nj; ++gj) {
            for (int gk = 0; gk < nk; ++gk) {
                // Collect adjacent elements (elements that have this grid node as a corner)
                std::vector<const Element*> adjacentElems;

                for (int di = 0; di <= 1; ++di) {
                    for (int dj = 0; dj <= 1; ++dj) {
                        for (int dk = 0; dk <= 1; ++dk) {
                            int ei = gi - di;
                            int ej = gj - dj;
                            int ek = gk - dk;

                            if (ei < 0 || ej < 0 || ek < 0) continue;
                            if (ei >= dimI_ || ej >= dimJ_ || ek >= dimK_) continue;

                            auto it = elemLookup.find({ei, ej, ek});
                            if (it != elemLookup.end()) {
                                adjacentElems.push_back(it->second);
                            }
                        }
                    }
                }

                if (adjacentElems.empty()) {
                    continue;
                }

                // Find nodes shared by ALL adjacent elements
                std::set<int> sharedNodes(adjacentElems[0]->nodeIds.begin(),
                                          adjacentElems[0]->nodeIds.end());

                for (size_t e = 1; e < adjacentElems.size(); ++e) {
                    std::set<int> elemNodes(adjacentElems[e]->nodeIds.begin(),
                                            adjacentElems[e]->nodeIds.end());
                    std::set<int> intersection;
                    std::set_intersection(sharedNodes.begin(), sharedNodes.end(),
                                          elemNodes.begin(), elemNodes.end(),
                                          std::inserter(intersection, intersection.begin()));
                    sharedNodes = intersection;
                }

                if (sharedNodes.size() == 1) {
                    // Perfect - exactly one shared node
                    nodeGrid_[gi][gj][gk] = *sharedNodes.begin();
                }
                else if (sharedNodes.size() > 1) {
                    // Multiple shared nodes - use COMBINED connectivity + geometry approach
                    // First filter by connectivity, then use geometry as tiebreaker

                    int expectedCount = static_cast<int>(adjacentElems.size());

                    // Compute average centroid of adjacent elements
                    Vector3D avgCentroid(0, 0, 0);
                    for (const Element* elem : adjacentElems) {
                        auto centIt = elemCentroids.find({elem->i, elem->j, elem->k});
                        if (centIt != elemCentroids.end()) {
                            avgCentroid += centIt->second;
                        }
                    }
                    avgCentroid /= static_cast<double>(adjacentElems.size());

                    // Determine which corner direction this grid node represents
                    // relative to the adjacent elements
                    // Grid node at (gi,gj,gk) corresponds to node position in each adjacent element:
                    // - If gi == elem->i, node is at i- side (lower i bound of element)
                    // - If gi > elem->i (i.e., gi == elem->i + 1), node is at i+ side (upper i bound)
                    // For corner (0,0,0) with only element (0,0,0) adjacent: gi==0, elem->i==0, so i- side
                    // For corner (dimI,dimJ,dimK) with only element (dimI-1,dimJ-1,dimK-1): gi>elem->i, so i+ side
                    double iSign = 0, jSign = 0, kSign = 0;
                    for (const Element* elem : adjacentElems) {
                        // This node is at i+ side if gi > elem->i, otherwise i- side
                        iSign += (gi > elem->i) ? 1.0 : -1.0;
                        jSign += (gj > elem->j) ? 1.0 : -1.0;
                        kSign += (gk > elem->k) ? 1.0 : -1.0;
                    }
                    // Normalize
                    double numElems = static_cast<double>(adjacentElems.size());
                    iSign /= numElems;
                    jSign /= numElems;
                    kSign /= numElems;

                    int bestNode = -1;
                    double bestScore = -1e30;

                    for (int nodeId : sharedNodes) {
                        double score = 0.0;

                        // Connectivity score
                        auto nodeIt = nodeToElems.find(nodeId);
                        if (nodeIt != nodeToElems.end()) {
                            int adjacentCount = 0;
                            int totalCount = static_cast<int>(nodeIt->second.size());

                            for (const auto& [ei, ej, ek] : nodeIt->second) {
                                bool isAdjacent = false;
                                for (const Element* adjElem : adjacentElems) {
                                    if (adjElem->i == ei && adjElem->j == ej && adjElem->k == ek) {
                                        isAdjacent = true;
                                        break;
                                    }
                                }
                                if (isAdjacent) {
                                    adjacentCount++;
                                }
                            }

                            int nonAdjacentCount = totalCount - adjacentCount;

                            if (adjacentCount == expectedCount && nonAdjacentCount == 0) {
                                score += 10000.0;
                            } else if (adjacentCount == expectedCount) {
                                score += 1000.0 - nonAdjacentCount * 10.0;
                            } else {
                                score += adjacentCount * 100.0 - nonAdjacentCount * 10.0;
                            }
                        }

                        // Geometry score - prefer node in the expected direction
                        const Node* node = mesh.getNode(nodeId);
                        if (node) {
                            Vector3D diff = node->position - avgCentroid;

                            // Score based on alignment with expected corner direction
                            // iSign > 0 means we want nodes with higher x relative to centroid
                            score += diff.x * iSign * 0.1;
                            score += diff.y * jSign * 0.1;
                            score += diff.z * kSign * 0.1;
                        }

                        if (score > bestScore) {
                            bestScore = score;
                            bestNode = nodeId;
                        }
                    }

                    if (bestNode > 0) {
                        nodeGrid_[gi][gj][gk] = bestNode;
                    }
                }
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
