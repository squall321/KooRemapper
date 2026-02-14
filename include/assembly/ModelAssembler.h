#pragma once

#include "assembly/AssemblyConfig.h"
#include "core/Mesh.h"
#include "core/Vector3D.h"
#include "analysis/ElementAnalyzer.h"
#include <vector>
#include <set>
#include <map>
#include <array>
#include <string>

namespace KooRemapper {

class ModelAssembler {
public:
    ModelAssembler() : maxNodeId_(0), maxElementId_(0),
                       maxPartId_(0), maxSectionId_(0), maxMaterialId_(0),
                       replacedParts_(0), squeezedParts_(0), restackedParts_(0), bentParts_(0), indentedParts_(0), formStrainParts_(0),
                       dynamicRelaxation_(false), dynainEmbed_(false) {}

    bool loadBaseModel(const std::string& filename);
    bool applyReplace(const ReplaceOperation& op, double E, double nu,
                      const std::string& configDir);
    bool applySqueeze(const SqueezeOperation& op, double E, double nu);
    bool applyRestack(const RestackOperation& op, double E, double nu);
    bool applyBend(const BendOperation& op, double E, double nu,
                   const std::string& configDir);
    bool applyIndent(const IndentOperation& op, double E, double nu);
    bool applyFormStrain(const FormStrainOperation& op);
    bool writeOutput(const std::string& outputPrefix);

    const std::vector<ElementResult>& getAccumulatedResults() const {
        return accumulatedResults_;
    }
    const std::string& getErrorMessage() const { return errorMessage_; }
    int getReplacedPartCount() const { return replacedParts_; }
    int getSqueezedPartCount() const { return squeezedParts_; }
    int getRestackedPartCount() const { return restackedParts_; }
    int getBentPartCount() const { return bentParts_; }
    int getIndentedPartCount() const { return indentedParts_; }
    int getFormStrainPartCount() const { return formStrainParts_; }
    int getNodeCount() const { return static_cast<int>(baseMesh_.getNodeCount()); }
    int getElementCount() const { return static_cast<int>(baseMesh_.getElementCount()); }
    int getPartCount() const { return static_cast<int>(baseMesh_.getPartCount()); }
    int getAddedNodeCount() const { return static_cast<int>(addedNodes_.size()); }
    int getAddedElementCount() const { return static_cast<int>(addedElements_.size()); }
    void setDynamicRelaxation(bool enabled) { dynamicRelaxation_ = enabled; }
    void setDynainEmbed(bool enabled) { dynainEmbed_ = enabled; }

    // Info strings for console output
    std::vector<std::string> infoMessages;

private:
    struct AddedNode { int id; double x, y, z; };
    struct AddedElement {
        int id; int pid;
        std::array<int, 8> nodeIds;
        ElementType type;
        bool isTshell = false;
    };
    struct AddedShellElement {
        int id; int pid;
        std::array<int, 4> nodeIds;
    };

    // Base model
    Mesh baseMesh_;
    std::vector<std::string> rawLines_;

    // Tracking changes
    std::set<int> removedNodeIds_;
    std::set<int> removedElementIds_;
    std::vector<AddedNode> addedNodes_;
    std::vector<AddedElement> addedElements_;
    std::vector<AddedShellElement> addedShellElements_;
    std::map<int, Vector3D> modifiedNodePositions_;

    // Keyword blocks to insert before *END (MAT, PART, SECTION cards)
    std::vector<std::string> addedKeywordBlocks_;

    // Dynain accumulation
    std::vector<ElementResult> accumulatedResults_;

    // ID management
    int maxNodeId_;
    int maxElementId_;
    int maxPartId_;
    int maxSectionId_;
    int maxMaterialId_;

    // Counters
    int replacedParts_;
    int squeezedParts_;
    int restackedParts_;
    int bentParts_;
    int indentedParts_;
    int formStrainParts_;

    std::string errorMessage_;

    // Dynamic relaxation
    bool dynamicRelaxation_;
    bool dynainEmbed_;

    // Restack helpers
    int detectExtrusionAxis(const std::vector<const Element*>& elems) const;
    double getAxisCoord(const Vector3D& v, int axis) const;
    void setAxisCoord(double& x, double& y, double& z, int axis, double val) const;

    // Utility
    std::set<int> getPartElementIds(int pid) const;
    std::set<int> getPartNodeIds(int pid) const;
    std::set<int> getPartExclusiveNodeIds(int pid) const;
    int parseNodeIdFromLine(const std::string& line) const;
    int parseElementIdFromLine(const std::string& line) const;
    std::string formatNodeLine(int id, double x, double y, double z) const;
    std::string formatElementLine(const AddedElement& elem) const;
    std::string formatShellElementLine(const AddedShellElement& elem) const;
    bool isKeywordLine(const std::string& line) const;
    bool isCommentLine(const std::string& line) const;
};

} // namespace KooRemapper
