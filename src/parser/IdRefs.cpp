// 파트·요소를 가리키는 카드 칸 — 칸 뜻이 확실한 갈래만 보는 정본(오탐을 내느니 세어만 둔다)
#include "parser/IdRefs.h"

#include "parser/CardCut.h"
#include "parser/CardFields.h"
#include "parser/DeckScan.h"

#include <algorithm>

namespace KooRemapper {
namespace idrefs {
namespace {

using cards::has;
using cards::starts;
using cards::toInt;

struct Walker {
    const std::vector<std::string>& L;
    const std::function<bool(Axis, int)>& keep;
    Scan& s;
    size_t kwLine = 0;

    void skipped(const std::string& kw) {
        ++s.notChecked;
        if (s.notCheckedKeywords.size() < 8 &&
            std::find(s.notCheckedKeywords.begin(), s.notCheckedKeywords.end(), kw) == s.notCheckedKeywords.end())
            s.notCheckedKeywords.push_back(kw);
    }
    void take(size_t li, const std::string& kw, Axis ax, const std::vector<int>& idx, int w) {
        const std::string& line = L[li];
        if (cards::hasParameterRef(line)) { skipped(kw); return; }
        const auto c = cardcut::cut(line, w);
        for (int q : idx) {
            if (q < 0 || static_cast<size_t>(q) >= c.f.size()) continue;
            int v = 0;
            if (!toInt(c.f[static_cast<size_t>(q)], v) || v <= 0) continue;
            if (keep && !keep(ax, v)) continue;
            Ref r;
            r.line = li;
            r.kwLine = kwLine;
            r.axis = ax;
            r.value = v;
            r.width = w;
            r.col = c.fixed ? q * w : -1;
            s.refs.push_back(r);
        }
    }
    // `*SET_<종류>` 목록 — [제목] · Card 1(SID …) 다음이 멤버. `_COLUMN` 은 칸 1 만, 그 밖은 칸 1-8.
    void setList(const cardcut::Block& b, Axis ax, int w10) {
        if (has(b.kw, "_GENERATE") || has(b.kw, "_GENERAL")) { skipped(b.kw); return; }   // 범위 · 옵션 글자
        if (has(b.kw, "_ADD") || has(b.kw, "_INTERSECT")) return;                          // 멤버가 세트 ID 다
        const size_t first = static_cast<size_t>(cards::titleLines(b.kw)) + 1;
        const bool column = has(b.kw, "_COLUMN");
        for (size_t m = first; m < b.data.size(); ++m)
            take(b.data[m], b.kw, ax, column ? std::vector<int>{0} : std::vector<int>{0, 1, 2, 3, 4, 5, 6, 7}, w10);
    }
};

const char* const kElemSets[] = {"*SET_SOLID", "*SET_SHELL", "*SET_BEAM", "*SET_TSHELL"};
const char* const kElemHist[] = {"*DATABASE_HISTORY_SOLID", "*DATABASE_HISTORY_SHELL",
                                 "*DATABASE_HISTORY_BEAM", "*DATABASE_HISTORY_TSHELL"};
// PID·EID 를 가리키지만 칸 뜻을 여기서 단정하지 않는 갈래(`ModelAssembler::scanDeadReferences` 의 스칼라 PID 표 ·
// EID 축과 같은 이름들) — 세어만 둔다.
const char* const kCounted[] = {
    "*DAMPING_PART_MASS", "*DAMPING_PART_STIFFNESS", "*PART_MOVE", "*BOUNDARY_PRESCRIBED_MOTION_RIGID",
    "*INITIAL_VELOCITY_GENERATION", "*MAT_ADD_THERMAL_EXPANSION", "*DEFORMABLE_TO_RIGID",
    "*INITIAL_STRESS_SOLID", "*INITIAL_STRESS_SHELL", "*INITIAL_STRAIN_SOLID", "*INITIAL_STRAIN_SHELL",
};

}  // namespace

Scan find(const std::vector<std::string>& L, int deckFw, const std::function<bool(Axis, int)>& keep) {
    Scan s;
    Walker w{L, keep, s};
    for (const auto& b : cardcut::blocks(L)) {
        const std::string& kw = b.kw;
        const int ifw = keywordFieldWidth(L[b.kwLine], deckFw);
        const int w10 = ifw >= 20 ? 20 : 10;
        w.kwLine = b.kwLine;

        if (starts(kw, "*SET_PART")) { w.setList(b, Axis::Part, w10); continue; }
        bool done = false;
        for (const char* p : kElemSets)
            if (starts(kw, p)) { w.setList(b, Axis::Elem, w10); done = true; break; }
        if (done) continue;
        for (const char* p : kElemHist) {
            if (!starts(kw, p)) continue;
            done = true;
            if (kw == p) {
                for (size_t m = 0; m < b.data.size(); ++m) w.take(b.data[m], kw, Axis::Elem, {0, 1, 2, 3, 4, 5, 6, 7}, w10);
            } else if (!has(kw, "_SET")) {
                w.skipped(kw);   // _ID·_LOCAL — 카드 꼴이 다르다 · _SET 은 세트 ID 다
            }
            break;
        }
        if (done) continue;

        // ── 접촉 Card 1 — SSID MSID SSTYP MSTYP(STYP = 3 이면 그 ID 칸이 PID 다) ─────────────────
        //   앞에 오는 카드 — 제목(_TITLE 은 접촉에 없지만 덱이 쓰면 한 줄) · ID 카드(_ID) · MPP 카드(_MPP —
        //   첫 줄이 `&` 로 시작하면 한 장 더). 서명(STYP 두 칸이 0..6 정수)이 안 맞으면 단정하지 않는다.
        if (starts(kw, "*CONTACT_")) {
            size_t k = (has(kw, "_TITLE") ? 1u : 0u) +
                       ((kw.size() >= 3 && kw.compare(kw.size() - 3, 3, "_ID") == 0) || has(kw, "_ID_") ? 1u : 0u);
            if (has(kw, "_MPP")) {
                if (k < b.data.size()) {
                    ++k;
                    if (k < b.data.size()) {
                        const std::string& nx = L[b.data[k]];
                        const size_t g = nx.find_first_not_of(" \t");
                        if (g != std::string::npos && nx[g] == '&') ++k;
                    }
                }
            }
            if (k >= b.data.size()) { w.skipped(kw); continue; }
            const auto c = cardcut::cut(L[b.data[k]], w10);
            int sstyp = -1, mstyp = -1;
            const bool sig = c.f.size() >= 4 && toInt(c.f[2], sstyp) && toInt(c.f[3], mstyp) &&
                             sstyp >= 0 && sstyp <= 6 && mstyp >= 0 && mstyp <= 6;
            if (!sig) { w.skipped(kw); continue; }
            std::vector<int> idx;
            if (sstyp == 3) idx.push_back(0);
            if (mstyp == 3) idx.push_back(1);
            if (!idx.empty()) w.take(b.data[k], kw, Axis::Part, idx, w10);
            continue;
        }
        // ── `*CONSTRAINED_RIGID_BODIES` — 줄마다 PIDL PIDC ──────────────────────────────────
        if (kw == "*CONSTRAINED_RIGID_BODIES") {
            for (size_t m = 0; m < b.data.size(); ++m) w.take(b.data[m], kw, Axis::Part, {0, 1}, w10);
            continue;
        }
        // ── `*ELEMENT_MASS` 의 PID(칸 4 · 8칸 표) — 0 이 아니면 단정하지 않는다 ─────────────────
        if (starts(kw, "*ELEMENT_MASS")) {
            for (size_t m = 0; m < b.data.size(); ++m) {
                const auto c = cardcut::cut(L[b.data[m]], ifw);
                int pid = 0;
                if (c.f.size() > 3 && toInt(c.f[3], pid) && pid > 0) w.skipped(kw);
            }
            continue;
        }
        for (const char* p : kCounted)
            if (starts(kw, p)) {
                if (!(has(kw, "_SET") && (starts(kw, "*DAMPING_PART_MASS") || starts(kw, "*DAMPING_PART_STIFFNESS"))))
                    w.skipped(kw);
                break;
            }
    }
    return s;
}

bool mayReference(const std::string& kw) {
    static const char* const kFam[] = {
        "*SET_PART", "*SET_SOLID", "*SET_SHELL", "*SET_BEAM", "*SET_TSHELL",
        "*DATABASE_HISTORY_SOLID", "*DATABASE_HISTORY_SHELL", "*DATABASE_HISTORY_BEAM", "*DATABASE_HISTORY_TSHELL",
        "*CONTACT_", "*CONSTRAINED_RIGID_BODIES", "*ELEMENT_MASS",
    };
    for (const char* f : kFam)
        if (starts(kw, f)) return true;
    for (const char* f : kCounted)
        if (starts(kw, f)) return true;
    return false;
}

std::string keywordOf(const std::vector<std::string>& lines, const Ref& r) {
    if (r.kwLine >= lines.size()) return std::string();
    return deckscan::kwBare(deckscan::keywordToken(lines[r.kwLine]));
}

}  // namespace idrefs
}  // namespace KooRemapper
