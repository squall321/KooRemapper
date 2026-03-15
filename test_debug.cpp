#include <iostream>
#include "parser/KFileReader.h"
#include "grid/ConnectivityAnalyzer.h"
#include "grid/StructuredGridIndexer.h"
#include "grid/BoundaryExtractor.h"

using namespace KooRemapper;

int main() {
    KFileReader reader;
    Mesh mesh = reader.readFile("test_data/curved_bent.k");
    
    std::cout << "Loaded: " << mesh.getNodeCount() << " nodes, " 
              << mesh.getElementCount() << " elements\n";
    
    ConnectivityAnalyzer connectivity;
    connectivity.buildConnectivity(mesh);
    
    std::cout << "Is structured: " << connectivity.isStructuredGrid() << "\n";
    std::cout << "Error: " << connectivity.getErrorMessage() << "\n";
    
    StructuredGridIndexer indexer;
    bool indexed = indexer.assignIndices(mesh, connectivity);
    
    std::cout << "Indexed: " << indexed << "\n";
    std::cout << "Dims: " << indexer.getDimI() << " x " << indexer.getDimJ() 
              << " x " << indexer.getDimK() << "\n";
    std::cout << "gridDimensionsSet: " << mesh.gridDimensionsSet << "\n";
    
    BoundaryExtractor boundary;
    boundary.extract(mesh);
    
    auto corners = boundary.getCornerNodes();
    std::cout << "Corner nodes: ";
    for (int i = 0; i < 8; ++i) {
        std::cout << corners[i] << " ";
    }
    std::cout << "\n";
    
    // Check dims
    std::cout << "Boundary dims: " << boundary.getDimI() << " x " 
              << boundary.getDimJ() << " x " << boundary.getDimK() << "\n";
    
    return 0;
}
