#pragma once

#include "core/Mesh.h"
#include "core/Element.h"
#include "analysis/StrainTensor.h"
#include "analysis/StressTensor.h"
#include "analysis/MaterialModel.h"
#include <vector>
#include <optional>
#include <functional>

namespace KooRemapper {

/**
 * Result of element analysis
 */
struct ElementResult {
    int elementId;
    Vector3D center;           // Element centroid
    
    StrainTensor strain;       // Average strain
    StressTensor stress;       // Average stress (if material provided)
    
    double vonMisesStrain;
    double vonMisesStress;
    double maxPrincipalStrain;
    double minPrincipalStrain;
    double maxPrincipalStress;
    double minPrincipalStress;
    
    bool isValid;              // True if computation succeeded
    std::string errorMessage;  // Error description if !isValid

    ElementResult() 
        : elementId(0), vonMisesStrain(0), vonMisesStress(0)
        , maxPrincipalStrain(0), minPrincipalStrain(0)
        , maxPrincipalStress(0), minPrincipalStress(0)
        , isValid(true) {}
};

/**
 * Mesh-level analysis result
 */
struct MeshAnalysisResult {
    std::vector<ElementResult> elementResults;
    
    // Statistics
    double minVonMisesStrain;
    double maxVonMisesStrain;
    double avgVonMisesStrain;
    
    double minVonMisesStress;
    double maxVonMisesStress;
    double avgVonMisesStress;
    
    int validElements;
    int invalidElements;
    
    bool hasMaterial;
    
    MeshAnalysisResult()
        : minVonMisesStrain(0), maxVonMisesStrain(0), avgVonMisesStrain(0)
        , minVonMisesStress(0), maxVonMisesStress(0), avgVonMisesStress(0)
        , validElements(0), invalidElements(0), hasMaterial(false) {}
};

/**
 * Element-level strain and stress analyzer
 * 
 * Computes strain from reference and deformed mesh configurations,
 * and optionally stress using provided material model.
 */
class ElementAnalyzer {
public:
    ElementAnalyzer();
    ~ElementAnalyzer() = default;

    /**
     * Set default material model for stress calculation
     * Used when element's part doesn't have a material defined
     */
    void setMaterial(const MaterialModel& material);

    /**
     * Clear default material (compute strain only)
     */
    void clearMaterial();
    
    /**
     * Enable per-part material lookup from mesh
     * When enabled, uses mesh's part->material mapping for each element
     */
    void setUsePartMaterials(bool use) { usePartMaterials_ = use; }

    /**
     * Set strain type (Engineering or Green-Lagrange)
     */
    void setStrainType(StrainType type) { strainType_ = type; }

    /**
     * Set number of Gauss points for integration (1 or 8)
     */
    void setGaussPoints(int n) { numGaussPoints_ = (n == 8) ? 8 : 1; }

    /**
     * Analyze a single element
     * 
     * @param elem      Element definition
     * @param refMesh   Reference (undeformed) mesh
     * @param defMesh   Deformed mesh
     * @return Analysis result for this element
     */
    ElementResult analyzeElement(
        const Element& elem,
        const Mesh& refMesh,
        const Mesh& defMesh
    );

    /**
     * Analyze entire mesh
     * 
     * @param refMesh   Reference mesh
     * @param defMesh   Deformed mesh (must have same topology)
     * @param progress  Optional progress callback (0-100)
     * @return Analysis results for all elements
     */
    MeshAnalysisResult analyzeMesh(
        const Mesh& refMesh,
        const Mesh& defMesh,
        std::function<void(int)> progress = nullptr
    );

    /**
     * Validate mesh pair (same topology)
     */
    static bool validateMeshPair(const Mesh& mesh1, const Mesh& mesh2, std::string& error);

private:
    std::optional<MaterialModel> material_;  // Default material
    StrainType strainType_;
    int numGaussPoints_;
    bool usePartMaterials_;  // Use per-part materials from mesh

    // Helper methods
    ElementResult analyzeHex8(
        const Element& elem,
        const std::array<Vector3D, 8>& refNodes,
        const std::array<Vector3D, 8>& defNodes,
        const MaterialModel* elemMaterial
    );

    ElementResult analyzeTet4(
        const Element& elem,
        const std::array<Vector3D, 4>& refNodes,
        const std::array<Vector3D, 4>& defNodes,
        const MaterialModel* elemMaterial
    );
    
    // Get material for element (checks part materials first if enabled)
    const MaterialModel* getMaterialForElement(const Element& elem, const Mesh& refMesh) const;

    void computeStatistics(MeshAnalysisResult& result);
};

} // namespace KooRemapper

