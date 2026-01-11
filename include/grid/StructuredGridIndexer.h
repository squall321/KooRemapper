#pragma once

#include "core/Mesh.h"
#include "grid/ConnectivityAnalyzer.h"
#include <queue>
#include <set>
#include <map>
#include <tuple>

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
     * Get error message
     */
    const std::string& getErrorMessage() const { return errorMessage_; }

private:
    int dimI_, dimJ_, dimK_;
    std::string errorMessage_;

    // Direction mapping: which local face corresponds to which axis direction
    // direction[axis] = {negative_face, positive_face}
    std::array<std::pair<int, int>, 3> axisToFace_;

    // Index lookup map
    std::map<std::tuple<int, int, int>, const Element*> indexedElements_;

    /**
     * Find a corner element to start indexing from
     */
    int findStartCorner(const Mesh& mesh, const ConnectivityAnalyzer& connectivity);

    /**
     * Determine initial axis directions from the starting corner
     */
    bool determineInitialDirections(const Mesh& mesh, int startElem,
                                    const ConnectivityAnalyzer& connectivity);

    /**
     * Propagate indices using BFS
     */
    bool propagateIndices(Mesh& mesh, int startElem,
                         const ConnectivityAnalyzer& connectivity);

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
