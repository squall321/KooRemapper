#pragma once
#include "contact_defs.h"
#include "set_members.h"
#include <string>
#include <vector>
#include <map>
#include <array>
#include <utility>

// Knowledge graph (lat.md):
//   @lat: [[modules/commands]]
//   @lat: [[commands/contact]]

namespace KooRemapper { class Mesh; class ConsoleOutput; }

// ── Structs needed by callers ─────────────────────────────────────────────────

struct ct_ContactPair {
    int pidA, pidB;
    int faceA, faceB;
    double gap;
};

struct ct_PairResult {
    int pidA, pidB;
    std::vector<std::array<int,4>> contactFacesA;
    std::vector<std::array<int,4>> contactFacesB;
    double gapMin, gapMax, gapAvg;
    int pairCount;
};

struct ct_PartSelection {
    std::vector<int> targetPids;
    std::vector<int> counterPids;
};

struct ct_ContactPreset {
    std::string keyword;       // LS-DYNA keyword suffix
    bool needMasterSide;       // false for single_surface
};

// 형마다 Card 3 뒤에 오는 필수 카드 수(매뉴얼 Vol_I *CONTACT 카드 순서). known=false 면 수를 확정할 수 없다 —
// 파서는 선택 카드를 읽지 않고, 만드는 쪽은 그 형을 거절한다(조용히 불완전한 키워드를 내지 않는다).
struct ct_CardSpec {
    int card4 = 0;             // AUTOMATIC_…_TIEBREAK 은 OPTION 에 따라 더 붙는다(파서가 센다)
    int thrm = 0;              // THRM 1 (THERMAL)
    int orfr = 0;              // ORFR 1-4 (ORTHO_FRICTION)
    bool tiebreakAuto = false; // AUTOMATIC_…_TIEBREAK — Card 4: OPTION NFLS SFLS PARAM ERATEN ERATES CT2CN CN
    bool damping = false;      // …_TIEBREAK_DAMPING — OPTION ±9 · ±11 이면 Card 4.1a
    bool eroding = false;      // ERODING_* — Card 4: ISYM EROSOP IADJ
    bool known = true;
    std::string why;
};

// ── Public ct_* API ────────────────────────────────────────────────────────────

ct_CardSpec ct_cardSpec(const std::string& type);

std::vector<ContactDef> ct_parseContacts(const std::vector<std::string>& lines);

std::vector<SetDef> ct_parseSets(const std::vector<std::string>& lines);

// `_GENERATE` 범위를 **덱에 정의된 ID** 로 좁혀 `SetDef::ids` 를 채운다.
// ⚠ 파싱 직후 반드시 한 번 부른다. 안 부르면 `_GENERATE` 세트의 멤버가 **빈 채로 남는다**
// (일부러 그렇다 — 범위는 한계값이라 그대로 펼치면 없는 개체를 만들어 낸다).
void ct_resolveSetRanges(std::vector<SetDef>& sets, const KooRemapper::Mesh& mesh);

// 세트 멤버를 푸는 일(`ct_setMembers`·`ct_setHas`·`ct_setContains`)은 `set_members.h` 의 정본이 한다.

int ct_findMaxSetId(const std::vector<SetDef>& sets);
// 덱의 `*CONTACT_*_ID` CID 최대값 — 새 접촉 CID 를 그 위로 발행한다.
int ct_findMaxContactId(const std::vector<std::string>& lines);

std::vector<std::array<int,4>> ct_extractSurface(
        const KooRemapper::Mesh& mesh, int pid);

std::vector<std::array<int,4>> ct_mergeFaces(
        const std::vector<std::vector<std::array<int,4>>>& perPidFaces);

std::vector<std::array<int,4>> ct_subtractFaces(
        const std::vector<std::array<int,4>>& a,
        const std::vector<std::array<int,4>>& b);

std::map<int, std::vector<std::array<int,4>>> ct_extractAllSurfaces(
        const KooRemapper::Mesh& mesh, const std::vector<int>& pids);

ct_PartSelection ct_selectParts(
        const KooRemapper::Mesh& mesh,
        const std::string& scope,
        const std::vector<std::string>& includeKeys,
        const std::vector<std::string>& excludeKeys);

std::vector<ct_ContactPair> ct_detectContacting(
        const std::vector<std::array<int,4>>& facesA,
        const std::vector<std::array<int,4>>& facesB,
        const KooRemapper::Mesh& mesh,
        int pidA, int pidB,
        double gapTolerance = 0.1,
        double normalAngleDeg = 45.0);

std::vector<ct_PairResult> ct_detectAllPairs(
        const std::map<int, std::vector<std::array<int,4>>>& surfacesByPid,
        const std::vector<int>& targetPids,
        const std::vector<int>& counterPids,
        const KooRemapper::Mesh& mesh,
        double gapTolerance,
        double normalAngleDeg);

// 세그먼트(정렬한 네 절점) → 그 면을 바깥면으로 가진 파트들. SET_SEGMENT 쪽 접촉을 파트 쌍으로 비교할 때 쓴다 —
// detect 가 만든 접촉은 전부 SET_SEGMENT 라 예전엔 skip_existing · subtract_existing 가 그것을 못 알아봤다.
using ct_SegOwners = std::map<std::array<int,4>, std::vector<int>>;
ct_SegOwners ct_segmentOwners(const std::map<int, std::vector<std::array<int,4>>>& surfacesByPid);

std::pair<std::vector<std::array<int,4>>, std::vector<std::array<int,4>>>
ct_getExistingTiedSegments(int pidA, int pidB,
        const std::vector<ContactDef>& contacts,
        const std::vector<SetDef>& sets,
        const KooRemapper::Mesh& mesh, double tol, double nAngle,
        const ct_SegOwners* owners = nullptr);

ct_ContactPreset ct_getPreset(const std::string& contactType);

bool ct_pairHasExisting(int pidA, int pidB,
        const std::vector<ContactDef>& contacts,
        const std::vector<SetDef>& sets,
        const std::string& mode,
        const ct_SegOwners* owners = nullptr);

std::string ct_generateSetSegment(int setId,
        const std::vector<std::array<int,4>>& faces,
        const std::string& title);

std::string ct_generateSetPart(int setId,
        const std::vector<int>& pids,
        const std::string& title);

std::string ct_generateSetNode(int setId,
        const std::vector<int>& nids,
        const std::string& title);

std::string ct_generateContact(const ContactDef& d);

// 형이 요구하는 필수 카드(TIEBREAK Card 4 · ERODING Card 4 · THRM 1)만 쓴다 — Card 3 바로 뒤 · 선택 카드 앞(매뉴얼 카드 순서).
// `ct_generateContact` 가 이것을 쓰고, assemble 의 contact 는 자기 Card 1-3 뒤에 이것을 붙인다.
std::string ct_writeMandatoryCards(const ContactDef& d);

// 필수 카드 규칙 — 형을 쓸 수 있는지 보고(못 쓰는 형 · ORFR · tiebreak OPTION 요구 · 13/14 · DAMPING ±9/±11 · SOFT 2 ·
// SINGLE/GENERAL 의 OPTION 6+ · 파손 OPTION 의 NFLS · SFLS), 되면 `d` 의 필수 카드 칸을 채운다. 안 되면 false 와 까닭(`err`).
bool ct_applyMandatory(const ct_MandatoryKeys& m, const std::string& keyword, ContactDef& d, std::string& err);

// Card 1 의 SSID · MSID · SSTYP · MSTYP 를 그 자리에서 고친다(음수 인자는 그대로 둔다). Card 1 이 없으면 false.
bool ct_modifyContactCard1(std::vector<std::string>& lines,
        const ContactDef& c,
        int newSsid, int newMsid, int newSstyp, int newMstyp);

// 카드 k(0=Card 1 · 1=Card 2 · 2=Card 3)의 칸 하나(0-기준)를 그 자리에서 고친다. 그 카드가 없으면 false.
bool ct_setCardField(std::vector<std::string>& lines, const ContactDef& c, int card, int field,
        const std::string& text);

void ct_modifyContactFs(std::vector<std::string>& lines,
        const ContactDef& c, double fs);

// 선택 카드(A…)만 다시 쓴다 — Card 4 · THRM · ORFR 는 그대로 둔다. 선택 카드 자리를 모르는 꼴(`layoutKnown=false`)이거나
// Card 3 이 없으면 **손대지 않고** false 와 까닭(`why`)을 돌려준다.
bool ct_modifyOptionalCards(std::vector<std::string>& lines,
        ContactDef& original, const ContactDef& updated, std::string* why = nullptr);

// 실수 칸 하나를 쓴다 — 예전 형식(`legacyFmt`)으로 쓴 글자가 같은 값이면 그 글자, 아니면 값을 지키는 가장 정밀한 표기.
std::string ct_real(double v, const char* legacyFmt);

void ct_removeBlock(std::vector<std::string>& lines, int startLine, int endLine);

std::string ct_stypName(int styp);

void ct_analyze(const std::vector<ContactDef>& contacts,
        const std::vector<SetDef>& sets,
        const KooRemapper::Mesh& mesh,
        KooRemapper::ConsoleOutput& console);
