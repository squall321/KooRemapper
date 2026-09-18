#pragma once

#include "assembly/AssemblyConfig.h"
#include "core/Mesh.h"
#include "core/Vector3D.h"
#include "core/ShellElement.h"
#include "analysis/ElementAnalyzer.h"
#include "analysis/StressTensor.h"
#include "analysis/MaterialModel.h"
#include <vector>
#include <set>
#include <map>
#include <array>
#include <string>

// Knowledge graph (lat.md):
//   @lat: [[modules/assembly]]

namespace KooRemapper {

class ModelAssembler {
public:
    ModelAssembler() : maxNodeId_(0), maxElementId_(0), maxShellElementId_(0),
                       maxPartId_(0), maxSectionId_(0), maxMaterialId_(0), maxSetId_(0),
                       replacedParts_(0), squeezedParts_(0), restackedParts_(0), bentParts_(0), indentedParts_(0), formStrainParts_(0),
                       tet10ConvertedCount_(0), hex20ConvertedCount_(0),
                       quad8ConvertedCount_(0), tria6ConvertedCount_(0),
                       tet10Elform_(17),
                       warpageParts_(0),
                       dynamicRelaxation_(false), dynainEmbed_(false),
                       warnedExtrapolation_(false), deflSign_(1.0) {}

    bool loadBaseModel(const std::string& filename);
    bool loadRawOnly(const std::string& filename);
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
    bool applyExtractSurface(const ExtractSurfaceOperation& op);
    bool applyIGA(const IGAOperation& op, const std::string& outputPrefix);
    bool applyWarpage(const WarpageOperation& op, double E, double nu,
                      const std::string& configDir);
    bool applyOffset(const OffsetOperation& op, double E, double nu);
    bool applyMatswap(const MatswapOperation& op, const std::string& configDir);
    bool applyMatdb(const MatdbOperation& op, const std::string& configDir);
    bool applyLoad(const LoadOperation& op);
    bool applyContact(const ContactOperation& op);
    bool applyBoundary(const BoundaryOperation& op);
    bool applyRbe(const RbeOperation& op);
    bool applyWrap(const WrapOperation& op, double E, double nu);
    bool applyGenerate(const GenerateOperation& op);
    bool applyUpdate(const UpdateOperation& op);
    bool applyDatabase(const DatabaseOperation& op);
    bool applyControl(const ControlOperation& op);
    bool applyFillet(const FilletOperation& op);
    bool applyCnrb2Solid(const Cnrb2SolidOperation& op);
    bool applyHFDamp(const HFDampOperation& op);
    bool applyBattery(const BatteryOperation& op, const std::string& configDir);
    bool applySplit(const SplitOperation& op);
    bool applyMerge(const MergeOperation& op);
    bool applyStrip(const StripOperation& op);
    // Returns all distinct part IDs currently in the model (base + added elements)
    std::vector<int> getAllPartIds() const;
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
    int getIGACount() const { return igaCount_; }
    int getWarpagePartCount() const { return warpageParts_; }
    void setDynamicRelaxation(bool enabled) { dynamicRelaxation_ = enabled; }
    void setDynainEmbed(bool enabled) { dynainEmbed_ = enabled; }

    // Info strings for console output
    std::vector<std::string> infoMessages;

    // restack·merge 가 비운 PID·지운 EID·지운 노드를 아직 가리키고 있는 카드 한 건.
    // grade: auto(규칙표의 '자동으로 옮긴다' 대상) | manual(보고만) |
    //        unknown(화이트리스트 키워드인데 칸 자리가 확정되지 않음) | maybe(화이트리스트 밖)
    struct PidRefFinding {
        std::string axis;      // "PID" | "EID" | "NODE"
        std::string keyword;   // 그 줄이 속한 키워드
        int line = 0;          // 원본 덱 줄 번호(1 부터)
        std::string text;      // 원문
        std::string grade;
        std::string advice;
    };
    const std::vector<PidRefFinding>& getPidRefFindings() const { return pidRefFindings_; }
    // pid_refs: strict(기본) | warn — strict 는 옮기지 못한 참조가 남으면 덱을 쓴 뒤 rc=1 로 끝낸다
    void setPidRefPolicy(const std::string& policy) { pidRefPolicy_ = policy; }
    const std::string& getPidRefPolicy() const { return pidRefPolicy_; }

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
        std::array<int, 8> nodeIds;  // 8 for TSHELL, use only 4 for regular shell
        int elform = 2;  // Default QUAD4/TRIA3
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
    int maxShellElementId_;
    int maxPartId_;
    int maxSectionId_;
    int maxMaterialId_;
    int maxSetId_;       // max *SET_* ID across all set types (SEGMENT, NODE, PART, etc.)

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
    int warpageParts_;

    // Element stresses (for bend, indent, warpage prestress modes)
    std::map<int, StressTensor> elementStresses_;

    // Warpage state
    mutable bool warnedExtrapolation_;
    mutable double deflSign_;

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

    // IGA include files
    struct IGAFile { std::string fullpath; std::string basename; std::string content; };
    std::vector<IGAFile> igaFiles_;
    int igaCount_ = 0;

    std::string errorMessage_;

    // Dynamic relaxation
    bool dynamicRelaxation_;
    bool dynainEmbed_;

    // 옮길 수 있는 죽은 PID 참조를 실제로 옮길 때 쓰는 값들
    struct PidRefMigrateCtx {
        bool isMerge = false;                     // merge 는 새 PID 가 하나뿐이라 층 선택이 없다
        std::vector<int> newPids;                 // restack: 층 PID(적층 축 최소측부터), merge: 새 PID 하나
        std::vector<std::string> layerEtypes;     // 층별 solid|tshell|shell
        std::vector<double> layerLo, layerHi;     // 층별 적층 축 범위
        int axis = -1;                            // 0=X 1=Y 2=Z
        double tol = 0.0;                         // 적층 축 비교 허용 오차
    };
    // 옮길 수 있는 참조를 실제로 옮긴다(세트 전 층 확장·tied 층 선택·세트 복제).
    // rawLines_ 를 그 자리에서 고치고, 옮긴 줄 번호를 handled 에, 보고할 내용을 moved 에 담는다.
    void migrateDeadReferences(const std::set<int>& deadPids,
                               const PidRefMigrateCtx& ctx,
                               std::set<size_t>& handled,
                               std::vector<PidRefFinding>& moved);
    // 죽은 PID/EID/노드를 가리키는 카드를 3축으로 훑어 pidRefFindings_ 에 모으고 콘솔에 요약한다.
    // skip 에 든 줄은 이미 옮긴 자리라 다시 보고하지 않고, moved 는 같은 보고에 섞어 준다.
    void scanDeadReferences(const std::string& opName,
                            const std::set<int>& deadPids,
                            const std::set<int>& deadEids,
                            const std::set<int>& deadNodes,
                            const std::vector<int>& newPids,
                            const std::set<size_t>& skip,
                            std::vector<PidRefFinding> moved);
    // 찾은 것을 pidRefFindings_ 에 담고 콘솔에 요약한다(스캔이 없을 때도 쓴다)
    void reportPidRefFindings(const std::string& opName,
                              std::vector<PidRefFinding>& found,
                              const std::set<int>& deadPids,
                              const std::vector<int>& newPids);
    // 접촉 상대측(STYP,ID)의 노드를 모아 적층 축 최소·최대를 돌려준다. 못 읽으면 false + 이유
    bool pidRefSideAxisRange(int styp, int id, int axis,
                             double& lo, double& hi, std::string& why) const;
    // 상대측 범위 [lo,hi] 가 층 하나로만 정해지면 그 층 번호, 아니면 -1 + 이유
    int pidRefPickLayer(const PidRefMigrateCtx& ctx, double lo, double hi, std::string& why) const;
    // 이관이 고친 줄(줄 인덱스 → 대체 줄들, 빈 벡터는 삭제). 스캔이 끝난 뒤에 rawLines_ 에 반영한다 —
    // 스캔과 보고가 쓰는 줄 번호는 이관 전 덱 기준이어야 하기 때문이다.
    std::map<size_t, std::vector<std::string>> pidRefRewrites_;
    void applyPidRefRewrites();
    std::vector<PidRefFinding> pidRefFindings_;
    std::string pidRefPolicy_ = "strict";

    // Restack helpers
    int detectExtrusionAxis(const std::vector<const Element*>& elems) const;
    double getAxisCoord(const Vector3D& v, int axis) const;
    void setAxisCoord(double& x, double& y, double& z, int axis, double val) const;

    // IGA helpers
    int findPartMid(int pid) const;
    std::string extractMaterialBlock(int origMid, int newMid) const;
    std::string generateIGAContent(int newId, int newMid, int fepid,
        double xmin, double xmax, double ymin, double ymax, double zmin, double zmax,
        double rr, double rs, double rt,
        double offR, double offS, double offT,
        int ir, int styp, double tollg,
        int pr, int ps, int pt,
        int nisr, int niss, int nist,
        const std::string& matBlock) const;

    // Warpage helpers
    bool validateWarpageOperation(const WarpageOperation& op, const std::string& configDir);
    void calculateWarpagePrestress(const WarpageOperation& op,
                                   const class WarpageGrid& grid,
                                   double dataBboxXmin, double dataBboxXmax,
                                   double dataBboxYmin, double dataBboxYmax,
                                   double unitScale,
                                   int axis1, int axis2, int deflAxis,
                                   double E, double nu);
    double getUnitScale(const std::string& unit) const;
    void parseAxes(const std::string& plane,
                  const std::string& deflAxis,
                  int& axis1, int& axis2, int& deflection) const;
    double getElementThickness(const Element& elem) const;
    void validateWarpageResults(const WarpageOperation& op, const class WarpageGrid& grid) const;
    void exportStressDistribution(const std::string& filename) const;
    Vector3D getNodePosition(int nid) const;
    double getShellThickness(int pid) const;

    // Post-fillet Laplacian smoothing: relax interior nodes
    void laplacianSmoothInterior(const std::vector<int>& pids, int iterations);

    // Post-fillet Jacobian fix: split negative-J HEX8 → TET4 or remove
    void fixNegativeJacobianElements(const std::vector<int>& pids);

    // Offset operation helpers
    void extractSourceSurface(int sourcePid, std::vector<ShellElement>& surfaceShells);
    Vector3D parseOffsetDirection(const std::string& direction,
                                  const std::vector<ShellElement>& surface);
    void extrudeToSolid(const std::vector<ShellElement>& surface,
                       const Vector3D& direction,
                       double thickness, int numLayers,
                       int newPid, int newSecid);
    // Overload for dual offset prestress (returns elements)
    void extrudeToSolid(const std::vector<ShellElement>& surface,
                       const Vector3D& direction,
                       double thickness, int numLayers,
                       int newPid, int newSecid,
                       std::vector<AddedElement>& outElements);
    // Overload for local normals (per-node directions)
    void extrudeToSolid(const std::vector<ShellElement>& surface,
                       const std::map<int, Vector3D>& perNodeDirections,
                       double thickness, int numLayers,
                       int newPid, int newSecid);
    // Overload for variable thickness (per-node thickness + optional directions)
    void extrudeToSolid(const std::vector<ShellElement>& surface,
                       const Vector3D& direction,
                       const std::map<int, double>& perNodeThickness,
                       int numLayers,
                       int newPid, int newSecid);
    // Overload for BOTH local normals AND variable thickness
    void extrudeToSolid(const std::vector<ShellElement>& surface,
                       const std::map<int, Vector3D>& perNodeDirections,
                       const std::map<int, double>& perNodeThickness,
                       int numLayers,
                       int newPid, int newSecid);
    void extrudeToTShell(const std::vector<ShellElement>& surface,
                        const Vector3D& direction,
                        double thickness, int numLayers,
                        int newPid, int newSecid);
    void createOffsetShell(const std::vector<ShellElement>& surface,
                          const Vector3D& direction,
                          double offset,
                          int newPid, int newSecid,
                          double shellThickness);
    Vector3D computeElementNormal(const ShellElement& shell);
    Vector3D computeShellNormal(const ShellElement& shell);
    Vector3D computeAverageNormal(const std::vector<ShellElement>& shells);
    std::map<int, Vector3D> computePerNodeNormals(const std::vector<ShellElement>& shells);
    std::map<int, double> computePerNodeThickness(const std::vector<ShellElement>& surface,
                                                   const std::string& formula, double baseThickness);
    void filterSurfaceByRegion(std::vector<ShellElement>& surface, const RegionSelection& region);
    Vector3D computeFaceCentroid(const Element& elem, int faceIndex);
    Vector3D computeElementCenter(const Element& elem) const;
    Vector3D computeOutwardNormal(const Element& elem, int faceIndex);
    bool isTria3(const ShellElement& shell);
    bool isElementInverted(const Element& elem);
    double computeJacobian(const Element& elem, double r, double s, double t);
    int getNextPartId();
    int getNextSectionId();
    int getNextMaterialId();
    void insertMaterialCard(const std::string& materialCard, int actualMid);
    void createPartKeyword(int pid, int secid, int mid, const std::string& title);
    void createSectionSolid(int secid);
    void createSectionTShell(int secid, double thickness, int elform);
    void createSectionShell(int secid, double thickness);
    std::string formatPartBlock(int pid, int secid, int mid, const std::string& title);
    std::string formatCzmSectionBlock(int secid);
    std::string formatSectionBlock(int secid);
    std::string formatTshellSectionBlock(int secid, double thickness);
    std::string formatShellSectionBlock(int secid, double thickness);
    void applyConnectionTied(const std::vector<ShellElement>& sourceSurface,
                            const std::vector<AddedElement>& offsetElements);
    void applyConnectionCZM(const std::vector<ShellElement>& sourceSurface,
                           std::vector<AddedElement>& offsetElements,
                           const OffsetOperation& op);
    void applyConnectionContact(const std::vector<ShellElement>& sourceSurface,
                               std::vector<AddedElement>& offsetElements,
                               int sourcePid, int newPid);
    bool applyMultiMaterialOffset(const OffsetOperation& op, double E, double nu);
    bool applyDualOffsetPrestress(const OffsetOperation& op, double E, double nu);
    void calculateDualOffsetPrestress(const std::vector<AddedElement>& refElements,
                                     const std::map<int, Vector3D>& deformedPositions,
                                     const MaterialModel& mat);
    void createCzmElementsForDualOffset(const std::vector<ShellElement>& sourceSurface,
                                       const std::map<int, int>& origToBottomNode,
                                       const OffsetOperation& op);
    void addContactHint(int sourcePid, int offsetPid);

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
