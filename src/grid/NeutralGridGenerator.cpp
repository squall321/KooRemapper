#include "grid/NeutralGridGenerator.h"

namespace KooRemapper {

NeutralGridGenerator::NeutralGridGenerator()
    : elemSizeI_(1.0), elemSizeJ_(1.0), elemSizeK_(1.0)
    , totalSizeI_(0.0), totalSizeJ_(0.0), totalSizeK_(0.0)
{}

Mesh NeutralGridGenerator::generate(const Mesh& bentMesh, const EdgeCalculator& edgeCalc) {
    int dimI = edgeCalc.getDimI();
    int dimJ = edgeCalc.getDimJ();
    int dimK = edgeCalc.getDimK();

    // Use neutral (average) edge lengths
    double sizeI = edgeCalc.getNeutralLengthI();
    double sizeJ = edgeCalc.getNeutralLengthJ();
    double sizeK = edgeCalc.getNeutralLengthK();

    return generate(dimI, dimJ, dimK, sizeI, sizeJ, sizeK);
}

Mesh NeutralGridGenerator::generate(int dimI, int dimJ, int dimK,
                                     double sizeI, double sizeJ, double sizeK) {
    Mesh mesh;

    // Calculate element sizes
    elemSizeI_ = (dimI > 0) ? sizeI / dimI : 1.0;
    elemSizeJ_ = (dimJ > 0) ? sizeJ / dimJ : 1.0;
    elemSizeK_ = (dimK > 0) ? sizeK / dimK : 1.0;

    totalSizeI_ = sizeI;
    totalSizeJ_ = sizeJ;
    totalSizeK_ = sizeK;

    // Generate nodes and elements
    generateNodes(mesh, dimI, dimJ, dimK);
    generateElements(mesh, dimI, dimJ, dimK);

    mesh.setGridDimensions(dimI, dimJ, dimK);

    return mesh;
}

void NeutralGridGenerator::generateNodes(Mesh& mesh, int dimI, int dimJ, int dimK) {
    // Generate (dimI+1) x (dimJ+1) x (dimK+1) nodes
    for (int i = 0; i <= dimI; ++i) {
        for (int j = 0; j <= dimJ; ++j) {
            for (int k = 0; k <= dimK; ++k) {
                int nodeId = getNodeId(i, j, k, dimJ, dimK);

                // Position centered around origin in y and z, starting from 0 in x
                double x = i * elemSizeI_;
                double y = (j - dimJ / 2.0) * elemSizeJ_;
                double z = (k - dimK / 2.0) * elemSizeK_;

                mesh.addNode(nodeId, x, y, z);
            }
        }
    }
}

void NeutralGridGenerator::generateElements(Mesh& mesh, int dimI, int dimJ, int dimK) {
    // Generate dimI x dimJ x dimK elements
    for (int i = 0; i < dimI; ++i) {
        for (int j = 0; j < dimJ; ++j) {
            for (int k = 0; k < dimK; ++k) {
                int elemId = getElementId(i, j, k, dimJ, dimK);

                // 8 nodes of the hexahedron
                // Node ordering follows LS-DYNA convention
                std::array<int, 8> nodeIds = {
                    getNodeId(i, j, k, dimJ, dimK),         // 0
                    getNodeId(i+1, j, k, dimJ, dimK),       // 1
                    getNodeId(i+1, j+1, k, dimJ, dimK),     // 2
                    getNodeId(i, j+1, k, dimJ, dimK),       // 3
                    getNodeId(i, j, k+1, dimJ, dimK),       // 4
                    getNodeId(i+1, j, k+1, dimJ, dimK),     // 5
                    getNodeId(i+1, j+1, k+1, dimJ, dimK),   // 6
                    getNodeId(i, j+1, k+1, dimJ, dimK)      // 7
                };

                mesh.addElement(elemId, 1, nodeIds);

                // Set grid index for this element
                Element* elem = mesh.getElement(elemId);
                if (elem) {
                    elem->setGridIndex(i, j, k);
                }
            }
        }
    }
}

} // namespace KooRemapper
