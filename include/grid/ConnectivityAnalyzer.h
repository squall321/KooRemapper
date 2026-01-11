#pragma once

#include "core/Mesh.h"
#include <map>
#include <vector>
#include <array>
#include <string>
#include <set>
#include <algorithm>

namespace KooRemapper {

/**
 * Structure representing a face of an element
 */
struct Face {
    std::array<int, 4> nodeIds;     // Node IDs (sorted for comparison)
    int elementId;                   // Element that owns this face
    int localFaceIndex;              // Local face index (0-5)

    Face() : nodeIds{}, elementId(0), localFaceIndex(0) {}
    Face(const std::array<int, 4>& nodes, int elemId, int faceIdx)
        : elementId(elemId), localFaceIndex(faceIdx) {
        // Copy and sort node IDs for consistent hashing
        nodeIds = nodes;
        std::sort(nodeIds.begin(), nodeIds.end());
    }

    // Create unique key for face identification
    std::string getKey() const {
        return std::to_string(nodeIds[0]) + "_" +
               std::to_string(nodeIds[1]) + "_" +
               std::to_string(nodeIds[2]) + "_" +
               std::to_string(nodeIds[3]);
    }

    bool operator==(const Face& other) const {
        return nodeIds == other.nodeIds;
    }
};

/**
 * Neighbor information for an element
 */
struct ElementNeighbor {
    int neighborElementId;
    int throughFace;        // Local face index of this element
    int neighborFace;       // Local face index of neighbor element
};

/**
 * Analyzes mesh connectivity through shared faces
 */
class ConnectivityAnalyzer {
public:
    ConnectivityAnalyzer();
    ~ConnectivityAnalyzer() = default;

    /**
     * Build connectivity information for the mesh
     */
    void buildConnectivity(const Mesh& mesh);

    /**
     * Get neighbors of an element
     * @param elementId Element ID
     * @return Vector of neighbor information
     */
    std::vector<ElementNeighbor> getNeighbors(int elementId) const;

    /**
     * Get number of neighbors for an element
     */
    int getNeighborCount(int elementId) const;

    /**
     * Check if two elements are neighbors
     */
    bool areNeighbors(int elemId1, int elemId2) const;

    /**
     * Get the shared face between two neighboring elements
     * @return Local face index of elem1, or -1 if not neighbors
     */
    int getSharedFace(int elemId1, int elemId2) const;

    /**
     * Find corner elements (elements with exactly 3 neighbors)
     * These are at corners of a structured grid
     */
    std::vector<int> findCornerElements() const;

    /**
     * Find edge elements (elements with exactly 4 neighbors)
     */
    std::vector<int> findEdgeElements() const;

    /**
     * Find face elements (elements with exactly 5 neighbors)
     */
    std::vector<int> findFaceElements() const;

    /**
     * Find interior elements (elements with 6 neighbors)
     */
    std::vector<int> findInteriorElements() const;

    /**
     * Get all boundary faces (faces with no neighbor)
     */
    std::vector<Face> getBoundaryFaces() const;

    /**
     * Check if mesh forms a valid structured grid
     * (all elements connected, proper neighbor counts)
     */
    bool isStructuredGrid() const { return isStructured_; }

    /**
     * Get error message if any
     */
    const std::string& getErrorMessage() const { return errorMessage_; }

private:
    // Element ID -> list of neighbors
    std::map<int, std::vector<ElementNeighbor>> elementNeighbors_;

    // Face key -> pair of (element ID, local face index)
    std::map<std::string, std::vector<std::pair<int, int>>> faceMap_;

    // Boundary faces
    std::vector<Face> boundaryFaces_;

    bool isStructured_;
    std::string errorMessage_;

    // Build face map from mesh
    void buildFaceMap(const Mesh& mesh);

    // Find neighbors using face map
    void findNeighbors();

    // Validate structured grid properties
    void validateStructuredGrid(const Mesh& mesh);
};

} // namespace KooRemapper
