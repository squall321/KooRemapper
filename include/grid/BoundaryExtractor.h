#pragma once

#include "core/Mesh.h"
#include <vector>
#include <map>

// Knowledge graph (lat.md):
//   @lat: [[modules/grid]]

namespace KooRemapper {

/**
 * Extracts the node grid and boundary (corner / edge) nodes from a structured grid
 */
class BoundaryExtractor {
public:
    BoundaryExtractor();
    ~BoundaryExtractor() = default;

    /**
     * Extract boundary information from indexed mesh
     */
    void extract(const Mesh& mesh);

    // ★ 결과는 전부 **값**(절점 ID · 격자 치수)이다 — 넘긴 메시를 가리키는 것을 들지 않는다.
    // 예전엔 경계면마다 요소 포인터 목록(getFaceI0..KP)과 그 절점 목록(getNodesOnFace*)도 냈는데,
    // 읽는 곳이 없었고 map 은 extract 에 넘긴 색인 사본을 step2 뒤에 풀어 그 포인터가 매달렸다.

    // Get 8 corner nodes
    std::array<int, 8> getCornerNodes() const { return cornerNodes_; }

    // Get 12 edge node lists
    // Returns node IDs along each edge
    struct EdgeNodes {
        std::vector<int> nodeIds;
        int axis;  // Which axis varies (0=i, 1=j, 2=k)
    };
    const std::array<EdgeNodes, 12>& getEdgeNodes() const { return edgeNodes_; }

    int getDimI() const { return dimI_; }
    int getDimJ() const { return dimJ_; }
    int getDimK() const { return dimK_; }

    /**
     * Look up the node ID at structured grid position (i, j, k).
     * Valid index range: i in [0, dimI], j in [0, dimJ], k in [0, dimK]
     * (i.e. (dimI+1) x (dimJ+1) x (dimK+1) NODE positions, vs. dimI x dimJ x dimK ELEMENT cells).
     *
     * Returns the node ID, or -1 if no node was assigned to that grid
     * position (sparse / partially-broken indexing).
     *
     * Used by ParametricMapper::gridLookupInterpolate to evaluate physical
     * positions at arbitrary parametric (u,v,w) by trilinearly blending
     * the 8 surrounding interior grid nodes -- this preserves cross-section
     * shape (e.g. teardrop) where 8-corner-only interpolation collapses.
     */
    int getNodeAtGrid(int i, int j, int k) const {
        if (i < 0 || i > dimI_ || j < 0 || j > dimJ_ || k < 0 || k > dimK_) return -1;
        if (nodeGrid_.empty()) return -1;
        return nodeGrid_[i][j][k];
    }

private:
    std::array<int, 8> cornerNodes_;
    std::array<EdgeNodes, 12> edgeNodes_;

    int dimI_, dimJ_, dimK_;

    // Build 3D node grid for quick lookup
    // nodeGrid[i][j][k] = node ID at that position
    std::vector<std::vector<std::vector<int>>> nodeGrid_;

    void buildNodeGrid(const Mesh& mesh);
    void extractCornerNodes();
    void extractEdgeNodes();
};

} // namespace KooRemapper
