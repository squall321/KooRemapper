#pragma once
#include "contact_defs.h"
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

// ── Public ct_* API ────────────────────────────────────────────────────────────

std::vector<ContactDef> ct_parseContacts(const std::vector<std::string>& lines);

std::vector<SetDef> ct_parseSets(const std::vector<std::string>& lines);

// `_GENERATE` 범위를 **덱에 정의된 ID** 로 좁혀 `SetDef::ids` 를 채운다.
// ⚠ 파싱 직후 반드시 한 번 부른다. 안 부르면 `_GENERATE` 세트의 멤버가 **빈 채로 남는다**
// (일부러 그렇다 — 범위는 한계값이라 그대로 펼치면 없는 개체를 만들어 낸다).
void ct_resolveSetRanges(std::vector<SetDef>& sets, const KooRemapper::Mesh& mesh);

// 그 ID 가 이 세트에 드는가 — 정의 목록이 없어도 답할 수 있다(메시를 안 읽는 op 용).
bool ct_setContains(const SetDef& s, int id);

int ct_findMaxSetId(const std::vector<SetDef>& sets);

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

std::pair<std::vector<std::array<int,4>>, std::vector<std::array<int,4>>>
ct_getExistingTiedSegments(int pidA, int pidB,
        const std::vector<ContactDef>& contacts,
        const std::vector<SetDef>& sets,
        const KooRemapper::Mesh& mesh, double tol, double nAngle);

ct_ContactPreset ct_getPreset(const std::string& contactType);

bool ct_pairHasExisting(int pidA, int pidB,
        const std::vector<ContactDef>& contacts,
        const std::vector<SetDef>& sets,
        const std::string& mode);

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

void ct_modifyContactCard1(std::vector<std::string>& lines,
        const ContactDef& c,
        int newSsid, int newMsid, int newSstyp, int newMstyp);

void ct_modifyContactFs(std::vector<std::string>& lines,
        const ContactDef& c, double fs);

void ct_modifyOptionalCards(std::vector<std::string>& lines,
        ContactDef& original, const ContactDef& updated);

void ct_removeBlock(std::vector<std::string>& lines, int startLine, int endLine);

std::string ct_stypName(int styp);

void ct_analyze(const std::vector<ContactDef>& contacts,
        const std::vector<SetDef>& sets,
        const KooRemapper::Mesh& mesh,
        KooRemapper::ConsoleOutput& console);
