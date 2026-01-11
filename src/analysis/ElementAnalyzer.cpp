#include "analysis/ElementAnalyzer.h"
#include "analysis/DeformationGradient.h"
#include <limits>
#include <algorithm>

namespace KooRemapper {

ElementAnalyzer::ElementAnalyzer()
    : strainType_(StrainType::ENGINEERING)
    , numGaussPoints_(1)
{}

void ElementAnalyzer::setMaterial(const MaterialModel& material)
{
    material_ = material;
}

void ElementAnalyzer::clearMaterial()
{
    material_.reset();
}

bool ElementAnalyzer::validateMeshPair(const Mesh& mesh1, const Mesh& mesh2, std::string& error)
{
    // Check node count
    if (mesh1.getNodeCount() != mesh2.getNodeCount()) {
        error = "Node count mismatch: " + std::to_string(mesh1.getNodeCount()) 
              + " vs " + std::to_string(mesh2.getNodeCount());
        return false;
    }
    
    // Check element count
    if (mesh1.getElementCount() != mesh2.getElementCount()) {
        error = "Element count mismatch: " + std::to_string(mesh1.getElementCount())
              + " vs " + std::to_string(mesh2.getElementCount());
        return false;
    }
    
    // Check that all elements have matching node IDs
    const auto& elems1 = mesh1.getElements();
    const auto& elems2 = mesh2.getElements();
    
    for (const auto& [id, elem1] : elems1) {
        auto it = elems2.find(id);
        if (it == elems2.end()) {
            error = "Element " + std::to_string(id) + " not found in second mesh";
            return false;
        }
        
        const Element& elem2 = it->second;
        for (int i = 0; i < 8; ++i) {
            if (elem1.nodeIds[i] != elem2.nodeIds[i]) {
                error = "Element " + std::to_string(id) + " has different connectivity";
                return false;
            }
        }
    }
    
    return true;
}

ElementResult ElementAnalyzer::analyzeElement(
    const Element& elem,
    const Mesh& refMesh,
    const Mesh& defMesh)
{
    ElementResult result;
    result.elementId = elem.id;
    result.isValid = false;
    
    if (elem.type == ElementType::HEX8) {
        // Get node positions
        std::array<Vector3D, 8> refNodes, defNodes;
        
        for (int i = 0; i < 8; ++i) {
            const Node* refNode = refMesh.getNode(elem.nodeIds[i]);
            const Node* defNode = defMesh.getNode(elem.nodeIds[i]);
            
            if (!refNode || !defNode) {
                result.errorMessage = "Missing node " + std::to_string(elem.nodeIds[i]);
                return result;
            }
            
            refNodes[i] = refNode->getEffectivePosition();
            defNodes[i] = defNode->getEffectivePosition();
        }
        
        return analyzeHex8(elem, refNodes, defNodes);
    }
    else if (elem.type == ElementType::TET4) {
        // Get node positions
        std::array<Vector3D, 4> refNodes, defNodes;
        
        for (int i = 0; i < 4; ++i) {
            const Node* refNode = refMesh.getNode(elem.nodeIds[i]);
            const Node* defNode = defMesh.getNode(elem.nodeIds[i]);
            
            if (!refNode || !defNode) {
                result.errorMessage = "Missing node " + std::to_string(elem.nodeIds[i]);
                return result;
            }
            
            refNodes[i] = refNode->getEffectivePosition();
            defNodes[i] = defNode->getEffectivePosition();
        }
        
        return analyzeTet4(elem, refNodes, defNodes);
    }
    else {
        result.errorMessage = "Unsupported element type";
        return result;
    }
}

ElementResult ElementAnalyzer::analyzeHex8(
    const Element& elem,
    const std::array<Vector3D, 8>& refNodes,
    const std::array<Vector3D, 8>& defNodes)
{
    ElementResult result;
    result.elementId = elem.id;
    
    // Compute element center
    result.center = Vector3D(0, 0, 0);
    for (int i = 0; i < 8; ++i) {
        result.center += defNodes[i];
    }
    result.center = result.center / 8.0;
    
    try {
        // Get Gauss points
        auto gaussPoints = DeformationGradient::gaussPointsHex8(numGaussPoints_);
        
        // Accumulate strain at Gauss points
        StrainTensor avgStrain;
        double totalWeight = 0;
        
        for (const auto& gp : gaussPoints) {
            double xi = gp[0];
            double eta = gp[1];
            double zeta = gp[2];
            double weight = gp[3];
            
            // Compute deformation gradient
            Matrix3x3 F = DeformationGradient::computeHex8(
                refNodes, defNodes, xi, eta, zeta);
            
            // Compute strain
            StrainTensor strain = StrainTensor::fromDeformationGradient(F, strainType_);
            
            avgStrain += strain * weight;
            totalWeight += weight;
        }
        
        // Average
        if (totalWeight > 0) {
            avgStrain *= (1.0 / totalWeight);
        }
        
        result.strain = avgStrain;
        result.vonMisesStrain = avgStrain.vonMisesStrain();
        
        auto principalStrains = avgStrain.principalStrains();
        result.maxPrincipalStrain = principalStrains[0];
        result.minPrincipalStrain = principalStrains[2];
        
        // Compute stress if material is set
        if (material_.has_value()) {
            result.stress = material_->computeStress(avgStrain);
            result.vonMisesStress = result.stress.vonMises();
            
            auto principalStresses = result.stress.principalStresses();
            result.maxPrincipalStress = principalStresses[0];
            result.minPrincipalStress = principalStresses[2];
        }
        
        result.isValid = true;
    }
    catch (const std::exception& e) {
        result.isValid = false;
        result.errorMessage = e.what();
    }
    
    return result;
}

ElementResult ElementAnalyzer::analyzeTet4(
    const Element& elem,
    const std::array<Vector3D, 4>& refNodes,
    const std::array<Vector3D, 4>& defNodes)
{
    ElementResult result;
    result.elementId = elem.id;
    
    // Compute element center
    result.center = Vector3D(0, 0, 0);
    for (int i = 0; i < 4; ++i) {
        result.center += defNodes[i];
    }
    result.center = result.center / 4.0;
    
    try {
        // TET4 has constant strain
        Matrix3x3 F = DeformationGradient::computeTet4(refNodes, defNodes);
        
        result.strain = StrainTensor::fromDeformationGradient(F, strainType_);
        result.vonMisesStrain = result.strain.vonMisesStrain();
        
        auto principalStrains = result.strain.principalStrains();
        result.maxPrincipalStrain = principalStrains[0];
        result.minPrincipalStrain = principalStrains[2];
        
        // Compute stress if material is set
        if (material_.has_value()) {
            result.stress = material_->computeStress(result.strain);
            result.vonMisesStress = result.stress.vonMises();
            
            auto principalStresses = result.stress.principalStresses();
            result.maxPrincipalStress = principalStresses[0];
            result.minPrincipalStress = principalStresses[2];
        }
        
        result.isValid = true;
    }
    catch (const std::exception& e) {
        result.isValid = false;
        result.errorMessage = e.what();
    }
    
    return result;
}

MeshAnalysisResult ElementAnalyzer::analyzeMesh(
    const Mesh& refMesh,
    const Mesh& defMesh,
    std::function<void(int)> progress)
{
    MeshAnalysisResult result;
    result.hasMaterial = material_.has_value();
    
    const auto& elements = refMesh.getElements();
    size_t total = elements.size();
    size_t processed = 0;
    
    result.elementResults.reserve(total);
    
    for (const auto& [id, elem] : elements) {
        ElementResult elemResult = analyzeElement(elem, refMesh, defMesh);
        result.elementResults.push_back(elemResult);
        
        if (elemResult.isValid) {
            result.validElements++;
        } else {
            result.invalidElements++;
        }
        
        processed++;
        if (progress && total > 0) {
            progress(static_cast<int>(100 * processed / total));
        }
    }
    
    computeStatistics(result);
    
    return result;
}

void ElementAnalyzer::computeStatistics(MeshAnalysisResult& result)
{
    if (result.elementResults.empty()) return;
    
    result.minVonMisesStrain = std::numeric_limits<double>::max();
    result.maxVonMisesStrain = std::numeric_limits<double>::lowest();
    result.minVonMisesStress = std::numeric_limits<double>::max();
    result.maxVonMisesStress = std::numeric_limits<double>::lowest();
    
    double sumStrain = 0;
    double sumStress = 0;
    int validCount = 0;
    
    for (const auto& er : result.elementResults) {
        if (!er.isValid) continue;
        
        result.minVonMisesStrain = std::min(result.minVonMisesStrain, er.vonMisesStrain);
        result.maxVonMisesStrain = std::max(result.maxVonMisesStrain, er.vonMisesStrain);
        sumStrain += er.vonMisesStrain;
        
        if (result.hasMaterial) {
            result.minVonMisesStress = std::min(result.minVonMisesStress, er.vonMisesStress);
            result.maxVonMisesStress = std::max(result.maxVonMisesStress, er.vonMisesStress);
            sumStress += er.vonMisesStress;
        }
        
        validCount++;
    }
    
    if (validCount > 0) {
        result.avgVonMisesStrain = sumStrain / validCount;
        if (result.hasMaterial) {
            result.avgVonMisesStress = sumStress / validCount;
        }
    }
}

} // namespace KooRemapper

