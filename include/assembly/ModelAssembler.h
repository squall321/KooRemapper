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
                       tet10ConvertedCount_(0), hex20ConvertedCount_(0),
                       quad8ConvertedCount_(0), tria6ConvertedCount_(0),
                       tet10Elform_(17),
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
    bool applyTet10Convert(const Tet10ConvertOperation& op);
    bool applyRefine(const RefineOperation& op);
    bool applyElform(const ElformOperation& op);
    bool applyDisconnect(const DisconnectOperation& op);
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
    int getTet10ConvertedCount() const { return tet10ConvertedCount_; }
    int getHex20ConvertedCount() const { return hex20ConvertedCount_; }
    int getQuad8ConvertedCount() const { return quad8ConvertedCount_; }
    int getTria6ConvertedCount() const { return tria6ConvertedCount_; }
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
    int tet10ConvertedCount_;
    int hex20ConvertedCount_;
    int quad8ConvertedCount_;
    int tria6ConvertedCount_;

    // Quadratic element conversion data
    std::map<int, std::array<int, 10>> tet10Elements_;  // elemId → 10-node connectivity
    std::map<int, std::array<int, 20>> hex20Elements_;  // elemId → 20-node connectivity
    std::map<int, std::array<int, 8>> quad8Elements_;   // elemId → 8-node connectivity
    std::map<int, std::array<int, 6>> tria6Elements_;   // elemId → 6-node connectivity
    std::map<std::pair<int,int>, int> edgeMidNodeMap_;   // sorted(nA,nB) → midNodeId (persists across calls)
    std::map<int, int> solidSectionElforms_;     // SECID → target ELFORM for *SECTION_SOLID
    std::map<int, int> shellSectionElforms_;     // SECID → target ELFORM for *SECTION_SHELL
    int tet10Elform_;                             // legacy (unused, kept for compat)

    // Refine dedup maps
    std::map<std::tuple<int,int,int,int>, int> faceCenterNodeMap_;  // sorted 4-tuple → nodeId
    std::map<std::pair<std::pair<int,int>, int>, int> edgeThirdNodeMap_;  // (sorted(nA,nB), idx) → nodeId

    // Elform downgrade tracking
    std::set<int> downgradeElementIds_;  // Element IDs that need downgrade (quadratic→linear)

    // Disconnect: element connectivity rewrite (CZM/MEFEM modes)
    std::map<int, std::array<int,8>> modifiedElementNodes_;  // solid elemId → new nodeIds
    std::map<int, std::array<int,4>> modifiedShellElementNodes_;  // shell elemId → new nodeIds
    std::set<int> periSectionIds_;  // Section IDs to convert to *SECTION_SOLID_PERI

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
    std::string formatTet10ElementLine(int eid, int pid, const std::array<int, 10>& nodes) const;
    std::string formatHex20ElementLine(int eid, int pid, const std::array<int, 20>& nodes) const;
    std::string formatQuad8ElementLine(int eid, int pid, const std::array<int, 8>& nodes) const;
    std::string formatTria6ElementLine(int eid, int pid, const std::array<int, 6>& nodes) const;
    int parsePartIdFromLine(const std::string& line) const;
};

} // namespace KooRemapper
