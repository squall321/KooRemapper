#pragma once

#include "core/Mesh.h"
#include "core/Vector3D.h"
#include "grid/ConnectivityAnalyzer.h"
#include <queue>
#include <set>
#include <map>
#include <tuple>
#include <array>

// Knowledge graph (lat.md):
//   @lat: [[modules/grid]]

namespace KooRemapper {

/**
 * Assigns i,j,k indices to elements in a structured grid
 * based on connectivity (not coordinates)
 */
class StructuredGridIndexer {
public:
    StructuredGridIndexer();
    ~StructuredGridIndexer() = default;

    /**
     * Assign i,j,k indices to all elements
     * @param mesh Mesh to index (elements will be modified)
     * @param connectivity Pre-computed connectivity
     * @return true if successful
     */
    bool assignIndices(Mesh& mesh, const ConnectivityAnalyzer& connectivity);

    /**
     * Get grid dimensions after indexing
     */
    int getDimI() const { return dimI_; }
    int getDimJ() const { return dimJ_; }
    int getDimK() const { return dimK_; }

    /**
     * Get element at grid index
     */
    const Element* getElementAt(int i, int j, int k) const {
        auto it = indexedElements_.find({i, j, k});
        if (it != indexedElements_.end()) {
            return it->second;
        }
        return nullptr;
    }

    /**
     * Build index lookup (call after assignIndices)
     */
    void buildIndexLookup(const Mesh& mesh) {
        indexedElements_.clear();
        for (const auto& [id, elem] : mesh.elements) {
            if (elem.indexAssigned) {
                indexedElements_[{elem.i, elem.j, elem.k}] = &elem;
            }
        }
    }

    /**
     * Reorder axes so that dimK <= dimJ <= dimI
     * (z-axis smallest, x-axis largest)
     */
    void reorderAxes(Mesh& mesh);

    /**
     * Reorder nodes within each element to match LS-DYNA standard ordering
     * based on geometry (element centroid and node positions).
     * Standard order: bottom face CCW (n0,n1,n2,n3), top face CCW (n4,n5,n6,n7)
     * where k-axis goes from bottom to top.
     */
    void reorderElementNodes(Mesh& mesh);

    /**
     * Get error message
     */
    const std::string& getErrorMessage() const { return errorMessage_; }

private:
    int dimI_, dimJ_, dimK_;
    std::string errorMessage_;

    // Direction mapping: which local face corresponds to which axis direction
    // direction[axis] = {negative_face, positive_face}
    std::array<std::pair<int, int>, 3> axisToFace_;

    // Geometry-based axis directions (normalized vectors)
    // axisDirections_[0] = i-axis direction, etc.
    std::array<Vector3D, 3> axisDirections_;

    // Mesh pointer for geometry queries during indexing
    const Mesh* mesh_;

    // Index lookup map
    std::map<std::tuple<int, int, int>, const Element*> indexedElements_;

    /**
     * Find a corner element to start indexing from
     */
    int findStartCorner(const Mesh& mesh, const ConnectivityAnalyzer& connectivity);

    /**
     * Determine initial axis directions from the starting corner (face-based, legacy)
     */
    bool determineInitialDirections(const Mesh& mesh, int startElem,
                                    const ConnectivityAnalyzer& connectivity);

    /**
     * Determine initial axis directions using geometry (element centroids)
     * This method does NOT depend on LS-DYNA standard node ordering
     */
    bool determineInitialDirectionsGeometry(const Mesh& mesh, int startElem,
                                            const ConnectivityAnalyzer& connectivity);

    /**
     * Propagate indices using BFS (face-based, legacy)
     */
    bool propagateIndices(Mesh& mesh, int startElem,
                         const ConnectivityAnalyzer& connectivity);

    /**
     * Propagate indices using BFS with geometry-based axis detection
     * This method does NOT depend on LS-DYNA standard node ordering
     */
    bool propagateIndicesGeometry(Mesh& mesh, int startElem,
                                  const ConnectivityAnalyzer& connectivity);

    /**
     * Calculate element centroid for geometry-based direction detection
     */
    Vector3D calculateElementCentroid(const Mesh& mesh, int elemId) const;

    /**
     * Determine which axis (0=i, 1=j, 2=k) a direction vector corresponds to
     */
    int determineAxisFromDirection(const Vector3D& direction) const;

    /**
     * Determine direction sign (+1 or -1) for a given axis
     */
    int determineDirectionSign(const Vector3D& direction, int axis) const;

    /**
     * Get axis from face index (0=i, 1=j, 2=k)
     */
    int getAxisFromFace(int faceIndex) const;

    /**
     * Get direction from face index (-1 or +1)
     */
    int getDirectionFromFace(int faceIndex) const;

    /**
     * Calculate dimensions from indexed mesh
     */
    void calculateDimensions(const Mesh& mesh);

    /**
     * Swap two axes in all element indices
     */
    void swapAxes(Mesh& mesh, int axis1, int axis2);
};

} // namespace KooRemapper
