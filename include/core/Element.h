#pragma once

#include <array>
#include <vector>
#include <utility>

namespace KooRemapper {

/**
 * Element type enumeration
 */
enum class ElementType {
    HEX8,       // 8-node hexahedron
    HEX20,      // 20-node hexahedron
    TET4,       // 4-node tetrahedron
    TET10,      // 10-node tetrahedron
    UNKNOWN
};

/**
 * Element class representing an 8-node hexahedral element
 *
 * Node numbering convention (LS-DYNA):
 *
 *        7 -------- 6
 *       /|         /|
 *      / |        / |
 *     4 -------- 5  |
 *     |  |       |  |
 *     |  3 ------|- 2
 *     | /        | /
 *     |/         |/
 *     0 -------- 1
 *
 * Face definitions:
 *   Face 0 (i-): nodes 0,3,7,4
 *   Face 1 (i+): nodes 1,2,6,5
 *   Face 2 (j-): nodes 0,1,5,4
 *   Face 3 (j+): nodes 3,2,6,7
 *   Face 4 (k-): nodes 0,1,2,3
 *   Face 5 (k+): nodes 4,5,6,7
 */
class Element {
public:
    static constexpr int NUM_NODES = 8;
    static constexpr int NUM_FACES = 6;
    static constexpr int NODES_PER_FACE = 4;

    int id;                         // Element ID (from k-file)
    int partId;                     // Part ID
    std::array<int, NUM_NODES> nodeIds;  // Node IDs (8 nodes for hexahedron)
    ElementType type;               // Element type

    // Structured grid indices (computed later)
    int i, j, k;                    // Position in structured grid
    bool indexAssigned;             // Flag indicating if i,j,k have been assigned

    // Constructors
    Element()
        : id(0), partId(1), nodeIds{}, type(ElementType::HEX8), i(-1), j(-1), k(-1), indexAssigned(false) {}

    Element(int id, int partId, const std::array<int, NUM_NODES>& nodes)
        : id(id), partId(partId), nodeIds(nodes), type(ElementType::HEX8), i(-1), j(-1), k(-1), indexAssigned(false) {}

    // Copy and move
    Element(const Element& other) = default;
    Element& operator=(const Element& other) = default;
    Element(Element&& other) noexcept = default;
    Element& operator=(Element&& other) noexcept = default;

    // Set structured grid index
    void setGridIndex(int i_, int j_, int k_) {
        i = i_;
        j = j_;
        k = k_;
        indexAssigned = true;
    }

    // Get face node indices (local indices 0-7)
    static std::array<int, NODES_PER_FACE> getFaceLocalNodes(int faceIndex) {
        // Face definitions based on LS-DYNA convention
        static const std::array<std::array<int, NODES_PER_FACE>, NUM_FACES> faceNodes = {{
            {0, 3, 7, 4},  // Face 0 (i-)
            {1, 2, 6, 5},  // Face 1 (i+)
            {0, 1, 5, 4},  // Face 2 (j-)
            {3, 2, 6, 7},  // Face 3 (j+)
            {0, 1, 2, 3},  // Face 4 (k-)
            {4, 5, 6, 7}   // Face 5 (k+)
        }};

        if (faceIndex >= 0 && faceIndex < NUM_FACES) {
            return faceNodes[faceIndex];
        }
        return {0, 0, 0, 0};
    }

    // Get face node IDs (actual node IDs)
    std::array<int, NODES_PER_FACE> getFaceNodeIds(int faceIndex) const {
        auto localNodes = getFaceLocalNodes(faceIndex);
        return {
            nodeIds[localNodes[0]],
            nodeIds[localNodes[1]],
            nodeIds[localNodes[2]],
            nodeIds[localNodes[3]]
        };
    }

    // Get opposite face index
    static int getOppositeFace(int faceIndex) {
        // 0 <-> 1 (i- <-> i+)
        // 2 <-> 3 (j- <-> j+)
        // 4 <-> 5 (k- <-> k+)
        if (faceIndex % 2 == 0) {
            return faceIndex + 1;
        } else {
            return faceIndex - 1;
        }
    }

    // Get axis for face (0=i, 1=j, 2=k)
    static int getFaceAxis(int faceIndex) {
        return faceIndex / 2;
    }

    // Get direction for face (-1 for minus face, +1 for plus face)
    static int getFaceDirection(int faceIndex) {
        return (faceIndex % 2 == 0) ? -1 : 1;
    }

    // Check if element contains a node
    bool containsNode(int nodeId) const {
        for (int idx = 0; idx < NUM_NODES; ++idx) {
            if (nodeIds[idx] == nodeId) {
                return true;
            }
        }
        return false;
    }

    // Get edge node pairs (12 edges)
    static std::array<std::pair<int, int>, 12> getEdgeLocalNodes() {
        return {{
            // Bottom face edges (k-)
            {0, 1}, {1, 2}, {2, 3}, {3, 0},
            // Top face edges (k+)
            {4, 5}, {5, 6}, {6, 7}, {7, 4},
            // Vertical edges
            {0, 4}, {1, 5}, {2, 6}, {3, 7}
        }};
    }

    // Comparison operators (by ID)
    bool operator==(const Element& other) const {
        return id == other.id;
    }

    bool operator!=(const Element& other) const {
        return id != other.id;
    }

    bool operator<(const Element& other) const {
        return id < other.id;
    }
};

} // namespace KooRemapper
