# Module: src/grid/

Extract structured-grid topology from an unstructured input mesh.

| File | Role |
|------|------|
| [BoundaryExtractor.cpp](../../src/grid/BoundaryExtractor.cpp) | identifies free faces / boundary loops |
| [ConnectivityAnalyzer.cpp](../../src/grid/ConnectivityAnalyzer.cpp) | adjacency, node→element maps |
| [EdgeCalculator.cpp](../../src/grid/EdgeCalculator.cpp) | edge enumeration, lengths |
| [NeutralGridGenerator.cpp](../../src/grid/NeutralGridGenerator.cpp) | "neutral" intermediate grid for mapping |
| [StructuredGridIndexer.cpp](../../src/grid/StructuredGridIndexer.cpp) | BFS-based (i,j,k) assignment |

## Algorithm anchor

- [[theory/structured-grid#Structured grid BFS indexing]] — BFS indexing for arc/width/thickness layout.

TODO: edge-walk traversal rules; how the algorithm picks a seed face.
