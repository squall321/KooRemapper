#pragma once

#include "core/Mesh.h"
#include "grid/EdgeCalculator.h"

namespace KooRemapper {

/**
 * Generates a neutral (flat, regular) grid based on bent grid dimensions
 */
class NeutralGridGenerator {
public:
    NeutralGridGenerator();
    ~NeutralGridGenerator() = default;

    /**
     * Generate a neutral grid based on the bent mesh dimensions
     * @param bentMesh The bent structured mesh (for dimensions)
     * @param edgeCalc Edge calculator (for average sizes)
     * @return New flat mesh with uniform element sizes
     */
    Mesh generate(const Mesh& bentMesh, const EdgeCalculator& edgeCalc);

    /**
     * Generate a neutral grid with specified dimensions and sizes
     */
    Mesh generate(int dimI, int dimJ, int dimK,
                  double sizeI, double sizeJ, double sizeK);

    /**
     * Get the element sizes used
     */
    double getElementSizeI() const { return elemSizeI_; }
    double getElementSizeJ() const { return elemSizeJ_; }
    double getElementSizeK() const { return elemSizeK_; }

    /**
     * Get total dimensions
     */
    double getTotalSizeI() const { return totalSizeI_; }
    double getTotalSizeJ() const { return totalSizeJ_; }
    double getTotalSizeK() const { return totalSizeK_; }

private:
    double elemSizeI_, elemSizeJ_, elemSizeK_;
    double totalSizeI_, totalSizeJ_, totalSizeK_;

    /**
     * Generate nodes for a regular grid
     */
    void generateNodes(Mesh& mesh, int dimI, int dimJ, int dimK);

    /**
     * Generate elements for a regular grid
     */
    void generateElements(Mesh& mesh, int dimI, int dimJ, int dimK);

    /**
     * Get node ID from grid position
     */
    int getNodeId(int i, int j, int k, int dimJ, int dimK) const {
        return i * (dimJ + 1) * (dimK + 1) + j * (dimK + 1) + k + 1;
    }

    /**
     * Get element ID from grid position
     */
    int getElementId(int i, int j, int k, int dimJ, int dimK) const {
        return i * dimJ * dimK + j * dimK + k + 1;
    }
};

} // namespace KooRemapper
