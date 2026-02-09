#pragma once

#include <array>

namespace KooRemapper {

/**
 * QUAD4 shell element (4-node quadrilateral)
 *
 * Node numbering:
 *     3 -------- 2
 *     |          |
 *     |          |
 *     0 -------- 1
 *
 * Edge definitions:
 *   Edge 0: node 0 -> node 1 (bottom)
 *   Edge 1: node 1 -> node 2 (right)
 *   Edge 2: node 2 -> node 3 (top)
 *   Edge 3: node 3 -> node 0 (left)
 */
struct ShellElement {
    static constexpr int NUM_NODES = 4;
    static constexpr int NUM_EDGES = 4;

    int id;
    int partId;
    std::array<int, NUM_NODES> nodeIds;

    ShellElement()
        : id(0), partId(1), nodeIds{} {}

    ShellElement(int id, int partId, const std::array<int, NUM_NODES>& nodes)
        : id(id), partId(partId), nodeIds(nodes) {}

    // Get the two node IDs for a given edge (0-3)
    std::array<int, 2> getEdgeNodes(int edgeIdx) const {
        int n0 = edgeIdx;
        int n1 = (edgeIdx + 1) % NUM_NODES;
        return { nodeIds[n0], nodeIds[n1] };
    }

    // Get edge as sorted pair (for adjacency lookup)
    static std::pair<int, int> makeEdgeKey(int a, int b) {
        return (a < b) ? std::pair<int,int>{a, b} : std::pair<int,int>{b, a};
    }

    // Get sorted edge key for edge index
    std::pair<int, int> getEdgeKey(int edgeIdx) const {
        auto nodes = getEdgeNodes(edgeIdx);
        return makeEdgeKey(nodes[0], nodes[1]);
    }

    bool containsNode(int nodeId) const {
        for (int i = 0; i < NUM_NODES; ++i) {
            if (nodeIds[i] == nodeId) return true;
        }
        return false;
    }

    // Get local index of a node (0-3), returns -1 if not found
    int getLocalIndex(int nodeId) const {
        for (int i = 0; i < NUM_NODES; ++i) {
            if (nodeIds[i] == nodeId) return i;
        }
        return -1;
    }

    bool operator==(const ShellElement& other) const { return id == other.id; }
    bool operator!=(const ShellElement& other) const { return id != other.id; }
    bool operator<(const ShellElement& other) const { return id < other.id; }
};

} // namespace KooRemapper
