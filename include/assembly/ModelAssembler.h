#pragma once

#include "validation/ReferenceIntegrity.h"

#include "parser/DeckNewline.h"
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
        std::string axis;      // "PID" | "EID" | "NODE" | "ALL"(덱 전체에 걸린 한계)
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

    // 자기 구현으로 덱을 쓰는 경로(단독 merge)도 assemble 과 똑같은 참조 처리를 쓰게 하는 진입점.
    // lines 를 그 자리에서 고치고(옮길 수 있는 참조 이관), 덱 머리에 넣을 $ 블록을 headerBlock 에,
    // 새로 만든 키워드 블록을 addedBlocks 에 담는다. 콘솔 보고는 이 안에서 한다.
    // 옮기지 못한 자리가 남고 정책이 strict 면 false — 호출자는 덱을 쓴 뒤 rc=1 로 끝낸다.
    bool processDeadReferences(std::vector<std::string>& lines,
                               const std::set<int>& deadPids,
                               const std::set<int>& deadEids,
                               const std::set<int>& deadNodes,
                               const std::vector<int>& newPids,
                               const std::string& opName,
                               const std::string& policy,
                               std::vector<std::string>& addedBlocks,
                               std::string& headerBlock,
                               std::vector<std::string>& consoleLines);

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
    // 입력 덱의 개행. 읽을 때 기억했다가 최종 출력에서 되붙인다 — 리더가 CR 을 떼므로
    // 이것이 없으면 CRLF 덱이 조용히 LF 로 바뀐다(구조 카운트는 전부 정상이라 안 보인다).
    DeckNewline deckNewline_ = DeckNewline::LF;

    // Tracking changes
    std::set<int> removedNodeIds_;
    std::set<int> removedElementIds_;
    std::vector<AddedNode> addedNodes_;
    std::vector<AddedElement> addedElements_;
    std::vector<AddedShellElement> addedShellElements_;
    std::map<int, Vector3D> modifiedNodePositions_;

    // restack 이 이번 실행에서 만든 층 PID — 한 assemble 안에서 restack 을 여러 번 할 때
    // 사용자가 지정한 PID 가 앞 op 의 새 층과 겹치는지 본다(baseMesh_ 에는 없는 파트다).
    std::set<int> restackCreatedPids_;

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
    // restack 이 지운 중간면 노드를 좌표가 똑같은 새 층 노드로 바꾼다(*SET_NODE_LIST 만).
    // subst 는 '좌표가 tol 안에서 딱 하나 일치' 로 확정한 것만 담는다 — 애매하면 옮기지 않는다.
    void migrateDeadNodeSets(const std::map<int, int>& subst,
                             std::set<size_t>& handled,
                             std::vector<PidRefFinding>& moved);
    // 이관하지 못하고 남은 '지운 노드를 가리키는 자리' 를 실제로 정리한다.
    // LS-DYNA 는 세트에 정의되지 않은 노드가 있으면 하드 에러로 멈춘다(현장 실측 Error 10233 —
    // 이 문구는 R16 매뉴얼 세 권 어디에도 없어 매뉴얼 근거로는 쓸 수 없다). 남겨 두면 안 된다.
    // subst 에 있는 노드는 지우지 않고 그 자리에서 새 층 노드로 바꾼다 — 옮길 수 있는데도
    // 줄을 지우면 하중·초기속도가 조용히 사라진다(모델이 달라진다).
    void cleanupDeadNodeRefs(const std::set<int>& deadNodes,
                             const std::map<int, int>& subst,
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
    // rawLines_ 에서 *SET_* SID 를 훑어 maxSetId_ 를 채운다(loadBaseModel 과 단독 경로 공용)
    void initMaxSetIdFromRawLines();
    // 덱 머리에 넣을 $ KOOREMAPPER-PIDREF 블록(발견이 없으면 빈 문자열)
    std::string buildPidRefHeaderBlock() const;
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
    // fw = 그 줄이 들어갈 섹션의 정수 칸 폭(8 / 10 / 20). 덱이 i10 인데 8 칸으로 쓰면
    // LS-DYNA 가 새 노드·새 요소를 통째로 다르게 읽는다(Vol_I 19342-19360).
    std::string formatNodeLine(int id, double x, double y, double z, int fw) const;
    std::string formatElementLine(const AddedElement& elem, int fw) const;
    std::string formatShellElementLine(const AddedShellElement& elem, int fw) const;
    bool isKeywordLine(const std::string& line) const;
    bool isCommentLine(const std::string& line) const;
    std::string formatTet10ElementLine(int eid, int pid, const std::array<int, 10>& nodes, int fw) const;
    std::string formatHex20ElementLine(int eid, int pid, const std::array<int, 20>& nodes, int fw) const;
    std::string formatQuad8ElementLine(int eid, int pid, const std::array<int, 8>& nodes, int fw) const;
    std::string formatTria6ElementLine(int eid, int pid, const std::array<int, 6>& nodes, int fw) const;
    // ⚠ 폭을 받는다. 예전에는 `substr(8, 8)` 로 못 박혀 있어 **I10 덱에서 EID 의 끝자리를
    // PID 로 읽었다**(실측: PID 77 → 1). 8칸 덱에서는 fw=8 이라 결과가 한 글자도 안 바뀐다.
    int parsePartIdFromLine(const std::string& line, int fw) const;
    // 못 읽으면 메시가 아는 PID 로 되돌린다 — 예전에는 -1 이 그대로 덱에 찍혔다.
    int partIdForCard(const std::string& line, int fw, int elemId) const;

    // 고정폭 칸에 안 들어가는 ID 를 만났나. `std::setw` 은 **자르지 않고 칸을 늘리므로**,
    // 그대로 두면 다음 칸을 침범한 덱이 rc=0 으로 나간다(실측: 8칸 덱에서 노드 16줄이
    // 엄격 재독 시 고유 9개로 뭉쳤다). 여기 기록해 두고 writeOutput 이 rc≠0 으로 받는다.
    mutable std::string widthOverflow_;
    void noteWidth(int v, int fw, const char* what) const;
};

// 요소·파트의 **절대 참조**를 본다 — 요소가 없는 파트를, 파트가 없는 섹션·재질을 가리키나.
//
// ⚠ 왜 `ReferenceIntegrity.cpp` 가 아니라 여기인가 — 요소 카드의 **경계와 PID 칸**을 정하는
// 판정(`ecBuildIndex`)이 이 번역 단위에 있다. 그것을 베껴 가면 같은 판정이 둘이 되고, 둘이
// 갈리면 한쪽은 틀린 채로 초록이 된다(이 리포는 `*INCLUDE` 판정이 셋으로 갈려 이미 당했다).
// 베끼지 않으려고 검사를 판정 곁에 둔다.
//
// 강건성 원칙은 `validation/ReferenceIntegrity.h` 의 것과 같다 — 칸 뜻이 확실한 카드만 보고,
// 애매하면 `notChecked` 로 세고, ID 0 은 dangling 이 아니며, `*INCLUDE` 가 있으면 단정하지 않는다.
ReferenceReport checkElementPartReferences(const std::vector<std::string>& lines);

} // namespace KooRemapper
