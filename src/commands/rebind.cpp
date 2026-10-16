// 재메시 뒤 덧붙인 블록의 절점 번호를 (파트 이름, 좌표)로 새 덱 번호에 다시 묶는다 — StepForge 경계 11행 · Q12
//
// 왜 (2026-10-16). StepForge 덱은 메시 잡마다 파트 순서대로 **전역 재번호**해 통째로 다시 쓴다. 우리가 그 덱 위에
// 덧붙인 세트·SPC·이력·CNRB 는 다음 메시 잡에서 번호가 어긋난다(저쪽 `BOUNDARY-DYNAFORGE.md` §3-6). 재결속은 우리
// 몫으로 확정됐고 입력 꼴은 저쪽 답이 정했다 — 구간 표(`range_diff`) + 좌표 기준, `coord_sha` 는 검증 관문(Q12).
//
// v1 의 규율(추천안 — `docs/01-plan/features/rebind-after-remesh.plan.md`).
//   · 짝은 옛 절점의 (그 절점을 쓰는 파트 **이름**, 좌표 `%16.9e`×3)와 **정확히** 같은 새 절점이다. 공차를 두지 않는다 —
//     다시 굽지 않은 파트는 좌표가 바이트 그대로이고(저쪽 `coords.same`), 가장 가까운 절점으로 옮기면 물리가 조용히 바뀐다.
//     맞닿은 두 파트는 같은 자리에 절점을 따로 두므로(저쪽 덱은 파트마다 절점이 따로다) 파트 이름으로 가른다.
//   · 칸 자리는 정본 하나(`parser/NodeRefs`)다. 정본이 칸 뜻을 단정하지 못한 자리 · 요소나 파트를 가리키는 카드가
//     있으면 **거절**한다(「모르는 칸은 거절」).
//   · 블록이 스스로 정의한 번호가 새 덱과 겹치면 거절한다. 못 푼 것이 하나라도 있으면 쓰지 않는다(rc 1).
#include "commands/rebind.h"

#include "cli/ConsoleOutput.h"
#include "core/Mesh.h"
#include "parser/CardFields.h"
#include "parser/DeckNewline.h"
#include "parser/DeckScan.h"
#include "parser/DeckWriter.h"
#include "parser/ElementCardLayout.h"
#include "parser/FragmentMap.h"    // coordSha — 저쪽 `coord_sha` 와 같은 값(실물 조각 4/4 로 확인)
#include "parser/IncludeScan.h"
#include "parser/KFileReader.h"
#include "parser/NodeRefs.h"
#include "util/FigureSvg.h"        // secondOrderSolidPids — 절점 칸을 앞 8개만 저장하는 파트는 소속을 다 못 본다
#include "util/StrictJson.h"

#include <algorithm>
#include <array>
#include <cstdio>
#include <fstream>
#include <iterator>
#include <map>
#include <set>
#include <sstream>
#include <unordered_map>
#include <vector>

namespace KooRemapper {
namespace rebind {
namespace {

using cards::has;
using cards::starts;
using cards::toInt;

bool readLines(const std::string& path, std::vector<std::string>& L) {
    std::ifstream f(path);
    if (!f.is_open()) return false;
    for (std::string ln; std::getline(f, ln);) {
        if (!ln.empty() && ln.back() == '\r') ln.pop_back();
        L.push_back(ln);
    }
    return true;
}

bool isKeywordLine(const std::string& l) {
    const size_t g = l.find_first_not_of(" \t");
    return g != std::string::npos && l[g] == '*';
}
bool isDataLine(const std::string& l) {
    const size_t g = l.find_first_not_of(" \t");
    return g != std::string::npos && l[g] != '*' && l[g] != '$';
}
std::string kwOf(const std::string& line) { return deckscan::kwBare(deckscan::keywordToken(line)); }

// 좌표 열쇠 — `coord_sha` 의 표기(`%16.9e`)와 같다. 그래야 「좌표가 그대로인가」를 저쪽과 같은 뜻으로 묻는다.
std::string coordKey(const Vector3D& p) {
    char b[80];
    std::snprintf(b, sizeof(b), "%16.9e%16.9e%16.9e", p.x, p.y, p.z);
    return b;
}

// 덱 하나 — 절점의 소속 파트 이름과 좌표, 파트별 절점, 블록이 겹치면 안 되는 번호들.
struct Deck {
    std::string path;
    std::vector<std::string> lines;
    int fw = 8;
    Mesh mesh;
    std::unordered_map<int, std::string> qualifier;   // 절점 → 그것을 쓰는 파트 제목들(정렬 · \x1f 로 잇는다)
    std::map<int, std::set<int>> partNodes;           // PID → 절점
    std::map<std::string, int> pidByTitle;            // 제목 → PID(겹치면 -1)
    std::set<int> elemIds, pids, curveIds, coordIds;
    std::map<std::string, std::set<int>> setIds;      // 종류(NODE·SEGMENT·PART …) → SID
};

// `*SET_<종류>…` 에서 종류만 — `ReferenceIntegrity` 의 네임스페이스와 같은 뜻(옵션 접미사를 뗀다).
std::string setKind(const std::string& kw) {
    std::string ns = kw.substr(5);
    for (const char* suf : {"_TITLE", "_COLLECT", "_GENERATE_INCREMENT", "_GENERATE", "_GENERAL", "_INTERSECT",
                            "_ADD", "_COLUMN", "_LIST_SMOOTH", "_LIST"}) {
        const std::string s(suf);
        for (size_t at = ns.find(s); at != std::string::npos; at = ns.find(s)) ns.erase(at, s.size());
    }
    return ns;
}

// 블록의 첫 정의 카드(제목 줄 다음) 첫 칸 — SID·LCID·CID 를 모으는 데 쓴다.
bool firstCardFirstField(const std::vector<std::string>& L, size_t kwLine, int titleLines, int& id) {
    int skip = titleLines;
    for (size_t j = kwLine + 1; j < L.size() && !isKeywordLine(L[j]); ++j) {
        if (!isDataLine(L[j]) && L[j].find_first_not_of(" \t") != std::string::npos) continue;   // 주석
        if (skip > 0) { --skip; continue; }
        return cards::firstFieldId(L[j], id);
    }
    return false;
}

void collectDefinedIds(const std::vector<std::string>& L, std::map<std::string, std::set<int>>& sets,
                       std::set<int>& curves, std::set<int>& coords) {
    for (size_t i = 0; i < L.size(); ++i) {
        if (!isKeywordLine(L[i])) continue;
        const std::string kw = kwOf(L[i]);
        int id = 0;
        if (starts(kw, "*SET_")) {
            if (firstCardFirstField(L, i, cards::titleLines(kw), id) && id > 0) sets[setKind(kw)].insert(id);
        } else if (starts(kw, "*DEFINE_CURVE")) {
            if (firstCardFirstField(L, i, cards::titleLines(kw), id) && id > 0) curves.insert(id);
        } else if (starts(kw, "*DEFINE_COORDINATE_")) {
            if (firstCardFirstField(L, i, cards::titleLines(kw), id) && id > 0) coords.insert(id);
        }
    }
}

bool loadDeck(const std::string& path, const char* role, Deck& d, std::string& err) {
    d.path = path;
    if (!readLines(path, d.lines)) { err = std::string(role) + " 를 열 수 없다: " + path; return false; }
    if (include_scan::scan(d.lines).count > 0) {
        err = std::string(role) + " 에 `*INCLUDE` 가 있다 — v1 은 한 파일 덱만 받는다(저쪽 덱은 한 파일이다): " + path;
        return false;
    }
    d.fw = deckFieldWidth(d.lines);
    KFileReader reader;
    d.mesh = reader.readFile(path);
    if (d.mesh.getNodeCount() == 0) { err = std::string(role) + " 에서 절점을 읽지 못했다: " + path; return false; }
    const auto bad2nd = figure::secondOrderSolidPids(d.mesh);
    if (!bad2nd.empty()) {
        err = std::string(role) + " — " + figure::secondOrderSolidWhy(bad2nd) +
              ". 리더가 절점 칸의 앞 8개만 저장해 절점의 소속 파트를 다 못 본다";
        return false;
    }
    std::map<int, std::string> title;
    for (const auto& [pid, p] : d.mesh.getParts()) {
        title[pid] = cards::trim(p.name);
        d.pids.insert(pid);
        auto it = d.pidByTitle.find(title[pid]);
        if (it == d.pidByTitle.end()) d.pidByTitle[title[pid]] = pid;
        else it->second = -1;                                     // 같은 제목이 둘 — 이름으로 가를 수 없다
    }
    std::unordered_map<int, std::set<std::string>> owners;
    for (const auto& [eid, e] : d.mesh.getElements()) {
        d.elemIds.insert(eid);
        d.pids.insert(e.partId);
        for (int n : e.nodeIds) {
            if (n <= 0) continue;
            d.partNodes[e.partId].insert(n);
            auto t = title.find(e.partId);
            owners[n].insert(t == title.end() ? "#" + std::to_string(e.partId) : t->second);
        }
    }
    for (auto& [n, s] : owners) {
        std::string q;
        for (const auto& t : s) { if (!q.empty()) q += '\x1f'; q += t; }
        d.qualifier[n] = q;
    }
    collectDefinedIds(d.lines, d.setIds, d.curveIds, d.coordIds);
    return true;
}

std::string partShaOf(const Deck& d, int pid) {
    std::vector<std::array<double, 3>> xyz;
    auto it = d.partNodes.find(pid);
    if (it == d.partNodes.end()) return std::string();
    for (int n : it->second) {
        auto nt = d.mesh.getNodes().find(n);
        if (nt == d.mesh.getNodes().end()) continue;
        xyz.push_back({nt->second.position.x, nt->second.position.y, nt->second.position.z});
    }
    return fragment::coordSha(xyz);
}

// 블록이 가져도 되는 카드 — 절점 참조를 정본이 읽는 갈래(바꿔 쓴다) · 우리 세트만 가리키는 갈래 · 메시 번호가 없는 정의.
// 그 밖(접촉 · `*SET_PART`·`*SET_SHELL` · 요소 · 파트 …)은 요소·파트 번호를 가리켜 v1 이 옮기지 못한다.
bool allowedKeyword(const std::string& kw, std::string& why) {
    if (kw == "*KEYWORD" || kw == "*END" || kw == "*TITLE" || kw == "*COMMENT" || kw == "*NODE") return true;
    if (starts(kw, "*SET_NODE")) {
        const auto kind = deckscan::classifySetNode(kw);
        if (kind != deckscan::SetKind::OPAQUE || has(kw, "_ADD")) return true;
        if (has(kw, "_GENERAL")) return true;    // 줄마다 OPTION 을 따로 본다(아래)
        why = "옛 번호의 범위·교집합이라 절점마다 옮길 수 없다";
        return false;
    }
    if (starts(kw, "*SET_SEGMENT")) {
        if (has(kw, "_GENERAL") || has(kw, "_INTERSECT")) { why = "옵션 줄이 파트·상자를 가리킨다"; return false; }
        return true;
    }
    static const char* const kExact[] = {
        "*BOUNDARY_SPC_NODE", "*LOAD_NODE_POINT", "*INITIAL_VELOCITY_NODE", "*CONSTRAINED_EXTRA_NODES_NODE",
        "*ELEMENT_MASS", "*BOUNDARY_PRESCRIBED_MOTION_NODE", "*DATABASE_HISTORY_NODE",
        "*CONSTRAINED_NODAL_RIGID_BODY", "*DEFINE_COORDINATE_NODES",
        // 우리 세트만 가리킨다(NSID) — 세트 번호는 우리 것이라 그대로다
        "*BOUNDARY_SPC_SET", "*LOAD_NODE_SET", "*DATABASE_HISTORY_NODE_SET", "*INITIAL_VELOCITY",
        "*DEFINE_CURVE", "*DEFINE_CURVE_TITLE",
    };
    for (const char* k : kExact)
        if (kw == k) return true;
    why = "요소·파트 번호나 v1 이 모르는 칸을 가질 수 있다";
    return false;
}

struct Unresolved { size_t line; std::string kw; int node; std::string why; };

}  // namespace

int run(const Input& in, ConsoleOutput& console) {
    const std::string tag = "[rebind_entities_after_remesh] ";
    std::string err;

    Deck oldD, newD;
    if (!loadDeck(in.oldDeck, "old_deck", oldD, err) || !loadDeck(in.newDeck, "new_deck", newD, err)) {
        console.error(tag + err);
        return 1;
    }
    if (oldD.fw != newD.fw) {
        console.error(tag + "두 덱의 정수 칸 폭이 다르다(old " + std::to_string(oldD.fw) + " · new " +
                      std::to_string(newD.fw) + ") — 블록을 어느 폭으로 쓸지 정할 수 없다");
        return 1;
    }
    std::vector<std::string> E;
    if (!readLines(in.entities, E)) { console.error(tag + "entities 를 열 수 없다: " + in.entities); return 1; }
    if (include_scan::scan(E).count > 0) { console.error(tag + "entities 에 `*INCLUDE` 가 있다 — 블록만 든 파일을 달라"); return 1; }
    {
        bool hasKw = false;
        for (const auto& l : E) if (isKeywordLine(l) && kwOf(l) == "*KEYWORD") { hasKw = true; break; }
        if (hasKw && deckFieldWidth(E) != newD.fw) {
            console.error(tag + "entities 의 `*KEYWORD` 폭(" + std::to_string(deckFieldWidth(E)) + ")이 덱(" +
                          std::to_string(newD.fw) + ")과 다르다");
            return 1;
        }
    }
    const int fw = newD.fw;

    // ── 1. 블록이 가져도 되는 카드인가 ────────────────────────────────────────
    std::vector<std::string> refused;
    for (size_t i = 0; i < E.size(); ++i) {
        if (!isKeywordLine(E[i])) continue;
        const std::string kw = kwOf(E[i]);
        std::string why;
        if (!allowedKeyword(kw, why)) {
            refused.push_back("line " + std::to_string(i + 1) + " " + kw + " — " + why);
            continue;
        }
        if (starts(kw, "*SET_NODE") && has(kw, "_GENERAL")) {
            // OPTION 이 NODE·DNODE 인 줄만 받는다 — PART·BOX·SET 등은 메시 파트·상자를 가리킨다
            size_t k = 0;
            const size_t skip = static_cast<size_t>(cards::titleLines(kw)) + 1;
            for (size_t j = i + 1; j < E.size() && !isKeywordLine(E[j]); ++j) {
                if (!isDataLine(E[j])) continue;
                if (k++ < skip) continue;
                const auto f = deckscan::cardFields(E[j], 10);
                const std::string opt = f.empty() ? std::string() : cards::upper(f[0]);
                if (opt != "NODE" && opt != "DNODE")
                    refused.push_back("line " + std::to_string(j + 1) + " " + kw + " — OPTION " + opt +
                                      " 은 절점이 아닌 것을 가리킨다");
            }
        }
    }

    // ── 2. 블록이 스스로 정의한 번호 — 새 덱과 겹치면 안 된다 ──────────────────
    std::map<int, Vector3D> ownNodes;          // 블록의 `*NODE`
    std::set<int> ownMassEids, ownCnrbPids;
    std::map<std::string, std::set<int>> ownSets;
    std::set<int> ownCurves, ownCoords;
    collectDefinedIds(E, ownSets, ownCurves, ownCoords);
    for (size_t i = 0; i < E.size(); ++i) {
        if (!isKeywordLine(E[i])) continue;
        const std::string kw = kwOf(E[i]);
        const int kfw = keywordFieldWidth(E[i], fw);
        for (size_t j = i + 1; j < E.size() && !isKeywordLine(E[j]); ++j) {
            if (!isDataLine(E[j])) continue;
            if (kw == "*NODE") {
                int nid = 0;
                double xyz[3];
                if (deckscan::readNodeLine(E[j], kfw, nid, xyz) && nid > 0) ownNodes[nid] = Vector3D(xyz[0], xyz[1], xyz[2]);
            } else if (kw == "*ELEMENT_MASS") {
                const auto f = deckscan::cardFields(E[j], kfw);
                int eid = 0;
                if (!f.empty() && toInt(f[0], eid) && eid > 0) ownMassEids.insert(eid);
            } else if (kw == "*CONSTRAINED_NODAL_RIGID_BODY") {
                const auto f = deckscan::cardFields(E[j], fw >= 20 ? 20 : 10);
                int pid = 0;
                if (!f.empty() && toInt(f[0], pid) && pid > 0) ownCnrbPids.insert(pid);
            }
        }
    }
    std::vector<std::string> clashes;
    auto clash = [&clashes](const std::string& what, const std::set<int>& own, const std::set<int>& deck) {
        std::vector<int> hit;
        std::set_intersection(own.begin(), own.end(), deck.begin(), deck.end(), std::back_inserter(hit));
        if (hit.empty()) return;
        std::string s = what + " " + std::to_string(hit.size()) + "개 — ";
        for (size_t k = 0; k < hit.size() && k < 5; ++k) s += (k ? ", " : "") + std::to_string(hit[k]);
        clashes.push_back(s);
    };
    {
        std::set<int> ownNodeIds, newNodeIds;
        for (const auto& [n, p] : ownNodes) { (void)p; ownNodeIds.insert(n); }
        for (const auto& [n, nd] : newD.mesh.getNodes()) { (void)nd; newNodeIds.insert(n); }
        clash("절점(블록의 `*NODE`)", ownNodeIds, newNodeIds);
    }
    clash("요소(`*ELEMENT_MASS` EID)", ownMassEids, newD.elemIds);
    clash("파트(CNRB PID)", ownCnrbPids, newD.pids);
    clash("곡선(LCID)", ownCurves, newD.curveIds);
    clash("좌표계(CID)", ownCoords, newD.coordIds);
    for (const auto& [kind, sids] : ownSets) {
        auto it = newD.setIds.find(kind);
        if (it != newD.setIds.end()) clash("세트(*SET_" + kind + " SID)", sids, it->second);
    }

    // ── 3. 구간 표 — 두 덱이 그 표의 이전·이후인가(`coord_sha` 를 다시 잰다) ──────────
    std::set<std::string> resizedParts;
    std::vector<std::string> tableBad;
    if (!in.rangeDiff.empty()) {
        std::ifstream jf(in.rangeDiff, std::ios::binary);
        if (!jf.is_open()) { console.error(tag + "range_diff 를 열 수 없다: " + in.rangeDiff); return 1; }
        std::stringstream ss;
        ss << jf.rdbuf();
        json::Value root;
        if (!json::parse(ss.str(), root, err)) { console.error(tag + "range_diff JSON — " + err); return 1; }
        const json::Value* parts = root.get("parts");
        if (root.type != json::Value::Type::Object || !parts || parts->type != json::Value::Type::Array) {
            console.error(tag + "range_diff 에 `parts` 배열이 없다 — 저쪽 구간 표(§3-6)의 꼴이 아니다");
            return 1;
        }
        int checked = 0;
        for (const auto& row : parts->arr) {
            const json::Value* name = row.get("part");
            const json::Value* co = row.get("coords");
            if (!name || name->type != json::Value::Type::String || !co || co->type != json::Value::Type::Object) {
                console.error(tag + "range_diff 의 행에 `part`·`coords` 가 없다");
                return 1;
            }
            const json::Value* rz = row.get("resized");
            if (rz && rz->type == json::Value::Type::Bool && rz->b) resizedParts.insert(name->s);
            for (const auto& side : {std::make_pair("before", &oldD), std::make_pair("after", &newD)}) {
                const json::Value* sha = co->get(side.first);
                if (!sha || sha->type != json::Value::Type::String) continue;   // null — 그쪽 판에 없다
                const Deck& d = *side.second;
                auto pt = d.pidByTitle.find(name->s);
                if (pt == d.pidByTitle.end() || pt->second < 0) {
                    tableBad.push_back(std::string(side.first) + " — 파트 「" + name->s + "」 를 " +
                                       (side.second == &oldD ? "old_deck" : "new_deck") + " 에서 " +
                                       (pt == d.pidByTitle.end() ? "못 찾았다" : "가를 수 없다(제목이 둘)"));
                    continue;
                }
                const std::string got = partShaOf(d, pt->second);
                ++checked;
                if (got != sha->s)
                    tableBad.push_back(std::string(side.first) + " — 파트 「" + name->s + "」 coord_sha 표 " + sha->s +
                                       " · 덱 " + got);
            }
        }
        console.info(tag + "구간 표 대조 — coord_sha " + std::to_string(checked) + "개를 두 덱에서 다시 쟀다" +
                     (resizedParts.empty() ? "" : " · 다시 구운 파트 " + std::to_string(resizedParts.size()) + "개"));
    }

    // ── 4. 절점 참조 — 정본이 읽는 칸 · 단정하지 못한 자리가 있으면 거절 ─────────────
    const auto sc = noderefs::find(E, fw);
    if (sc.notChecked > 0) {
        std::string ks;
        for (const auto& k : sc.notCheckedKeywords) ks += (ks.empty() ? "" : ", ") + k;
        refused.push_back("칸 뜻을 단정하지 못한 절점 자리 " + std::to_string(sc.notChecked) + "곳(" + ks + ")");
    }

    // 새 덱 색인 — (파트 제목들, 좌표) → 절점. 겹치면 -1(여럿).
    std::unordered_map<std::string, int> newIdx;
    for (const auto& [n, nd] : newD.mesh.getNodes()) {
        auto q = newD.qualifier.find(n);
        const std::string k = (q == newD.qualifier.end() ? std::string() : q->second) + '\x1e' + coordKey(nd.position);
        auto it = newIdx.find(k);
        if (it == newIdx.end()) newIdx[k] = n;
        else it->second = -1;
    }

    std::vector<Unresolved> unresolved;
    std::map<size_t, std::vector<std::pair<const noderefs::Ref*, int>>> edits;   // 줄 → (칸, 새 번호)
    std::map<std::string, int> movedBy;    // 키워드 → 바꾼 칸 수
    int unchanged = 0, own = 0;
    for (const auto& r : sc.refs) {
        const std::string kw = noderefs::keywordOf(E, r);
        if (ownNodes.count(r.value)) { ++own; continue; }            // 블록이 스스로 정의한 절점
        auto on = oldD.mesh.getNodes().find(r.value);
        if (on == oldD.mesh.getNodes().end()) {
            unresolved.push_back({r.line, kw, r.value, "old_deck 에도 블록에도 없는 절점이다"});
            continue;
        }
        auto q = oldD.qualifier.find(r.value);
        const std::string qual = q == oldD.qualifier.end() ? std::string() : q->second;
        auto it = newIdx.find(qual + '\x1e' + coordKey(on->second.position));
        if (it == newIdx.end() || it->second < 0) {
            std::string why = it == newIdx.end() ? "new_deck 에 같은 파트·같은 자리 절점이 없다"
                                                 : "new_deck 에 같은 파트·같은 자리 절점이 여럿이다";
            if (!qual.empty()) {
                const std::string first = qual.substr(0, qual.find('\x1f'));
                why += " (파트 「" + first + "」" + (resizedParts.count(first) ? " — 구간 표: 다시 구웠다(resized)" : "") + ")";
            }
            unresolved.push_back({r.line, kw, r.value, why});
            continue;
        }
        if (r.col < 0) {
            unresolved.push_back({r.line, kw, r.value, "자유형식·칸이 어긋난 줄이라 제자리에 바꿔 쓸 수 없다"});
            continue;
        }
        if (static_cast<int>(std::to_string(it->second).size()) > r.width) {
            unresolved.push_back({r.line, kw, r.value, "새 번호 " + std::to_string(it->second) + " 가 칸 폭 " +
                                  std::to_string(r.width) + " 을 넘는다"});
            continue;
        }
        if (it->second == r.value) ++unchanged;
        else { edits[r.line].push_back({&r, it->second}); ++movedBy[kw]; }
    }

    // ── 5. 하나라도 거절·충돌·불일치·못 풂이면 쓰지 않는다 ─────────────────────
    bool fail = false;
    auto list = [&](const std::string& head, const std::vector<std::string>& items) {
        if (items.empty()) return;
        fail = true;
        console.error(tag + head + " " + std::to_string(items.size()) + "건");
        for (size_t k = 0; k < items.size() && k < 20; ++k) console.println("  " + items[k]);
        if (items.size() > 20) console.println("  … 외 " + std::to_string(items.size() - 20) + "건");
    };
    list("블록에 v1 이 옮기지 못하는 카드가 있다 — 거절", refused);
    list("블록이 정의한 번호가 new_deck 과 겹친다 — 거절", clashes);
    list("구간 표가 두 덱과 맞지 않는다 — 이 표의 이전·이후 덱이 아니다", tableBad);
    {
        std::vector<std::string> items;
        for (const auto& u : unresolved)
            items.push_back("line " + std::to_string(u.line + 1) + " " + u.kw + ": 절점 " + std::to_string(u.node) +
                            " — " + u.why);
        list("못 푼 절점 참조", items);
    }
    if (fail) {
        console.println("  산출을 쓰지 않았다. 위치로 짝을 찾는 재결속이라 다시 구운 파트의 절점은 옮길 수 없다 —");
        console.println("  그 카드는 남는 파트의 절점·세트로 옮기거나, 그 파트를 다시 굽지 않는 메시 잡으로 다시 받는다");
        return 1;
    }

    // ── 6. 제자리에 바꿔 쓴다 — 칸 폭 그대로 · 번호 칸 말고는 한 바이트도 안 바꾼다 ──────
    std::vector<std::string> out = E;
    for (auto& [li, es] : edits) {
        std::string& s = out[li];
        for (const auto& [ref, nid] : es) {
            if (static_cast<int>(s.size()) < ref->col + ref->width) s.resize(static_cast<size_t>(ref->col + ref->width), ' ');
            char b[32];
            std::snprintf(b, sizeof(b), "%*d", ref->width, nid);
            s.replace(static_cast<size_t>(ref->col), static_cast<size_t>(ref->width), b);
        }
    }
    // 쓰기 전 재검사 — 바꾼 덱의 절점 참조가 전부 새 덱이나 블록 자신에 있는가(같은 정본으로)
    {
        const auto chk = noderefs::find(out, fw, [&](int v) {
            return !ownNodes.count(v) && !newD.mesh.getNodes().count(v);
        });
        if (!chk.refs.empty()) {
            console.error(tag + "바꿔 쓴 블록을 다시 보니 new_deck 에 없는 절점 " + std::to_string(chk.refs.size()) +
                          "곳 — 쓰지 않는다(이 op 의 결함이다)");
            return 1;
        }
    }
    {
        DeckWriter w(in.output, deck_newline::detect(in.entities));
        if (!w.ok()) { console.error(tag + "산출을 열 수 없다: " + in.output); return 1; }
        for (const auto& l : out) w.stream() << l << "\n";
    }

    int moved = 0;
    for (const auto& [k, n] : movedBy) moved += n;
    console.success(tag + "다 묶었다 — 절점 칸 " + std::to_string(moved) + "곳을 새 번호로 · 번호가 그대로인 칸 " +
                    std::to_string(unchanged) + " · 블록 자신의 절점 " + std::to_string(own));
    for (const auto& [k, n] : movedBy) console.println("  " + k + " " + std::to_string(n) + "곳");
    console.println("  → " + in.output + " — new_deck 과 함께 `*INCLUDE` 해 쓴다");
    return 0;
}

}  // namespace rebind
}  // namespace KooRemapper
