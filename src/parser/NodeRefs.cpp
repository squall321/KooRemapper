// 절점을 가리키는 카드 칸 — 매뉴얼로 확정한 갈래만 보는 정본 탐지기(오탐을 내느니 세어만 둔다)
#include "parser/NodeRefs.h"

#include "parser/CardCut.h"
#include "parser/CardFields.h"
#include "parser/DeckScan.h"
#include "parser/ElementCardLayout.h"

#include <algorithm>
#include <cstdlib>
#include <sstream>

namespace KooRemapper {
namespace noderefs {
namespace {

using cards::has;
using cards::starts;
using cards::toInt;

using cardcut::Cut;
using cardcut::cut;
using cardcut::isBlank;
using cardcut::isCommentLine;
using cardcut::isKeywordLine;

struct Walker {
    const std::vector<std::string>& L;
    const std::function<bool(int)>& keep;
    Scan& s;
    size_t kwLine = 0;

    void skipped(const std::string& kw) {
        ++s.notChecked;
        if (s.notCheckedKeywords.size() < 8 &&
            std::find(s.notCheckedKeywords.begin(), s.notCheckedKeywords.end(), kw) == s.notCheckedKeywords.end())
            s.notCheckedKeywords.push_back(kw);
    }
    // 줄 `li` 의 칸 `idx` 들을 절점 참조로 모은다.
    void take(size_t li, const std::string& kw, const std::vector<int>& idx, int w) {
        const std::string& line = L[li];
        if (cards::hasParameterRef(line)) { skipped(kw); return; }   // &name — 값이 기호다
        const Cut c = cut(line, w);
        for (int q : idx) {
            if (q < 0 || static_cast<size_t>(q) >= c.f.size()) continue;
            int v = 0;
            if (!toInt(c.f[static_cast<size_t>(q)], v) || v <= 0) continue;
            if (keep && !keep(v)) continue;
            Ref r;
            r.line = li;
            r.kwLine = kwLine;
            r.value = v;
            r.width = w;
            r.col = c.fixed ? q * w : -1;
            s.refs.push_back(r);
        }
    }
};

}  // namespace

// 칸 자리는 `ModelAssembler::cleanupDeadNodeRefs` 머리말의 매뉴얼 확정표(Vol_I 줄 번호)를 그대로 옮겼다.
// 그 장치는 **고치는** 쪽(빼기·옮기기·보고)이고 이것은 **찾는** 쪽이다. 한 줄짜리 카드 표와 정의 카드 표는 이제
// 두 곳이 **같은 표**(`oneFieldCards`·`definitionNodeCards`)를 쓴다(2026-10-16). 세트·세그먼트·이력 목록의 칸 범위는
// 고치는 동작이 갈래마다 달라 그쪽에 남아 있다 — 같은 범위(1-8 · 1-4)를 말해야 한다.
Scan find(const std::vector<std::string>& L, int deckFw, const std::function<bool(int)>& keep) {
    Scan s;
    Walker w{L, keep, s};
    for (size_t i = 0; i < L.size();) {
        if (!isKeywordLine(L[i])) { ++i; continue; }
        const std::string kw = deckscan::kwBare(deckscan::keywordToken(L[i]));
        const int ifw = keywordFieldWidth(L[i], deckFw);   // 8칸 정수 칸이 이 블록에서 갖는 폭(8·10·20)
        const int w10 = ifw >= 20 ? 20 : 10;               // 1-8 칸 표(10칸)의 폭 — long 이면 20
        w.kwLine = i;
        std::vector<size_t> data;
        size_t j = i + 1;
        for (; j < L.size() && !isKeywordLine(L[j]); ++j)
            if (!isCommentLine(L[j])) data.push_back(j);   // 빈 줄도 카드다(제목이 비어 있을 수 있다)
        while (!data.empty() && isBlank(L[data.back()])) data.pop_back();
        i = j;

        // ── `*SET_NODE` 계열 — [제목] · Card 1(SID …) 다음이 멤버 ─────────────────
        //   <BLANK>/_LIST/_LIST_SMOOTH Card 2a 칸 1-8 전부 · _COLUMN Card 2b 칸 1 (234448-234512)
        //   _GENERAL 은 OPTION 이 NODE·DNODE 인 줄의 E1..E7 (234634-234779)
        //   _GENERATE(범위 — 매뉴얼이 빈 번호를 허용한다 234577-234581) · _ADD/_INTERSECT(세트 ID) — 절점이 아니다
        if (starts(kw, "*SET_NODE")) {
            const size_t first = static_cast<size_t>(cards::titleLines(kw)) + 1;
            const auto kind = deckscan::classifySetNode(kw);
            if (kind == deckscan::SetKind::LIST) {
                for (size_t m = first; m < data.size(); ++m) w.take(data[m], kw, {0, 1, 2, 3, 4, 5, 6, 7}, w10);
            } else if (kind == deckscan::SetKind::COLUMN) {
                for (size_t m = first; m < data.size(); ++m) w.take(data[m], kw, {0}, w10);
            } else if (has(kw, "_GENERAL")) {
                for (size_t m = first; m < data.size(); ++m) {
                    const Cut c = cut(L[data[m]], w10);
                    if (c.f.empty()) continue;
                    const std::string opt = cards::upper(c.f[0]);
                    if (opt == "NODE" || opt == "DNODE") w.take(data[m], kw, {1, 2, 3, 4, 5, 6, 7}, w10);
                }
            }
            continue;
        }
        // ── `*SET_SEGMENT` — 멤버 줄 칸 1-4 = N1..N4 (235953-236060) ────────────────
        if (starts(kw, "*SET_SEGMENT")) {
            if (has(kw, "_GENERAL") || has(kw, "_ADD") || has(kw, "_INTERSECT")) continue;
            const size_t first = static_cast<size_t>(cards::titleLines(kw)) + 1;
            for (size_t m = first; m < data.size(); ++m) w.take(data[m], kw, {0, 1, 2, 3}, w10);
            continue;
        }
        // ── 칸 하나가 절점인 한 줄짜리 카드 — 이름이 **정확히** 같을 때만(정본 표 `oneFieldCards`) ─────
        //   `_ID`·`_BIRTH_DEATH` 등은 카드가 한 장 더 붙어 「줄 하나 = 카드 하나」가 아니다 → 세어만 둔다.
        bool done = false;
        for (const auto& o : oneFieldCards()) {
            if (!starts(kw, o.keyword)) continue;
            done = true;
            if (kw != o.keyword) { w.skipped(kw); break; }
            const int wd = o.eightWide ? ifw : w10;
            const bool prescribed = (kw == "*BOUNDARY_PRESCRIBED_MOTION_NODE");
            for (size_t m = 0; m < data.size(); ++m) {
                w.take(data[m], kw, {o.field}, wd);
                if (!prescribed) continue;
                // |DOF| = 9·10·11 이거나 VAD = 4 면 Card 3(OFFSET1 OFFSET2 LRB NODE1 NODE2)이 따라온다 —
                // 그 줄을 다음 Card 1 로 읽지 않는다. 그 카드의 NODE1·NODE2 는 보지 않았다고 센다.
                const Cut c = cut(L[data[m]], w10);
                int dof = 0, vad = 0;
                const bool hasDof = c.f.size() > 1 && toInt(c.f[1], dof);
                if (c.f.size() > 2) toInt(c.f[2], vad);
                if (hasDof && ((std::abs(dof) >= 9 && std::abs(dof) <= 11) || vad == 4)) {
                    ++m;
                    w.skipped(kw);
                }
            }
            break;
        }
        if (done) continue;
        // ── 칸 1-8 이 모두 절점인 목록 — `*DATABASE_HISTORY_NODE` Card 1a (122112-122180) ──
        if (kw == "*DATABASE_HISTORY_NODE") {
            for (size_t m = 0; m < data.size(); ++m) w.take(data[m], kw, {0, 1, 2, 3, 4, 5, 6, 7}, w10);
            continue;
        }
        if (starts(kw, "*DATABASE_HISTORY_NODE")) {
            if (!has(kw, "_SET")) w.skipped(kw);   // _SET 은 세트 ID 다 · _ID/_LOCAL 은 카드 꼴이 다르다
            continue;
        }
        // ── CNRB 의 PNODE(칸 4 · 61032-61057) · 좌표계 절점(칸 2-4 · 128642-128690) ──────────────
        //   옵션이 없는 맨 키워드는 Card 1 만 있어 **줄마다 정의 하나**다 — 모든 줄을 본다(재결속이 뒤 정의의 PNODE 를
        //   놓치면 조용히 틀린다). 옵션(TITLE·SPC·INERTIA)이 붙으면 카드 세트 길이가 달라 **첫 정의만** 본다(놓치는 쪽).
        bool defDone = false;
        for (const auto& dc : definitionNodeCards()) {
            if (!starts(kw, dc.keyword)) continue;
            defDone = true;
            if (kw == dc.keyword) {
                for (size_t m = 0; m < data.size(); ++m) w.take(data[m], kw, dc.fields, w10);
            } else {
                const size_t k = static_cast<size_t>(cards::titleLines(kw));
                if (k < data.size()) w.take(data[k], kw, dc.fields, w10);
            }
            break;
        }
        if (defDone) continue;
        // ── 절점을 무는 줄 알지만 칸 뜻이 변종마다 갈리는 카드 — 세어만 둔다 ──────────
        //   `*CONSTRAINED_JOINT_STIFFNESS_*` 의 첫 칸은 JSID 다 · `_ID`·`_FAILURE` 가 카드를 더 붙인다 ·
        //   보 족은 격자 리더가 담지 않는다.
        if (starts(kw, "*CONSTRAINED_JOINT_") || starts(kw, "*CONSTRAINED_SPOTWELD") ||
            starts(kw, "*ELEMENT_BEAM") || starts(kw, "*ELEMENT_DISCRETE") || starts(kw, "*ELEMENT_SEATBELT")) {
            w.skipped(kw);
            continue;
        }
    }
    return s;
}

const std::vector<OneFieldCard>& oneFieldCards() {
    static const std::vector<OneFieldCard> t = {
        {"*BOUNDARY_SPC_NODE", 0, false},                // NID              Vol_I 46945-47012
        {"*LOAD_NODE_POINT", 0, false},                  // NID              207114-207168
        {"*INITIAL_VELOCITY_NODE", 0, false},            // NID              192116-192161
        {"*CONSTRAINED_EXTRA_NODES_NODE", 1, false},     // PID NID          52799-52849
        {"*ELEMENT_MASS", 1, true},                      // EID NID(8칸 표)  159866-159930
        {"*BOUNDARY_PRESCRIBED_MOTION_NODE", 0, false},  // TYPEID           43306-43420
    };
    return t;
}

const std::vector<DefinitionNodeCard>& definitionNodeCards() {
    static const std::vector<DefinitionNodeCard> t = {
        {"*CONSTRAINED_NODAL_RIGID_BODY", {3}},          // PID CID NSID PNODE … 61032-61057
        {"*DEFINE_COORDINATE_NODES", {1, 2, 3}},         // CID N1 N2 N3 …      128642-128690
    };
    return t;
}

bool mayReference(const std::string& kw) {
    // `find` 가 칸을 읽는 갈래 — 위 가지들과 같은 이름이어야 한다.
    static const char* const kFam[] = {
        "*SET_NODE", "*SET_SEGMENT", "*BOUNDARY_SPC_NODE", "*LOAD_NODE_POINT", "*INITIAL_VELOCITY_NODE",
        "*CONSTRAINED_EXTRA_NODES_NODE", "*ELEMENT_MASS", "*BOUNDARY_PRESCRIBED_MOTION_NODE",
        "*DATABASE_HISTORY_NODE", "*CONSTRAINED_NODAL_RIGID_BODY", "*DEFINE_COORDINATE_NODES",
    };
    for (const char* f : kFam)
        if (starts(kw, f)) return true;
    return false;
}

std::string keywordOf(const std::vector<std::string>& lines, const Ref& r) {
    if (r.kwLine >= lines.size()) return std::string();
    return deckscan::kwBare(deckscan::keywordToken(lines[r.kwLine]));
}

std::vector<int> defined(const std::vector<std::string>& L, int deckFw, bool* anyNodeBlock) {
    std::vector<int> out;
    bool any = false;
    for (size_t i = 0; i < L.size(); ++i) {
        if (!isKeywordLine(L[i])) continue;
        const std::string kw = deckscan::kwBare(deckscan::keywordToken(L[i]));
        if (!starts(kw, "*NODE")) continue;
        const bool plain = (kw == "*NODE");
        if (plain) any = true;
        const int fw = keywordFieldWidth(L[i], deckFw);
        for (size_t j = i + 1; j < L.size() && !isKeywordLine(L[j]); ++j) {
            const std::string& ln = L[j];
            if (isCommentLine(ln) || isBlank(ln)) continue;
            int v = 0;
            if (plain) {
                double xyz[3];
                if (deckscan::readNodeLine(ln, fw, v, xyz) && v > 0) out.push_back(v);
                continue;
            }
            // `*NODE_RIGID_SURFACE` 등 — 칸 뜻을 단정하지 않고 첫 칸을 두 길로 **넘치게** 모은다.
            const auto f = cards::fieldsFixed(ln, fw);
            if (!f.empty() && toInt(f[0], v) && v > 0) out.push_back(v);
            std::istringstream iss(ln);
            std::string t;
            if (iss >> t && toInt(t, v) && v > 0) out.push_back(v);
        }
    }
    deckscan::sortUnique(out);
    if (anyNodeBlock) *anyNodeBlock = any;
    return out;
}

}  // namespace noderefs
}  // namespace KooRemapper
