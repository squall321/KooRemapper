// 파트·요소를 가리키는 카드 칸 — 칸 뜻이 확실한 갈래만 보는 정본(오탐을 내느니 세어만 둔다)
#include "parser/IdRefs.h"

#include "parser/CardCut.h"
#include "parser/CardFields.h"
#include "parser/DeckScan.h"
#include "commands/contact_helpers.h"   // 접촉 Card 1 자리 — 카드 자리 정본(ct_parseContacts)

#include <algorithm>
#include <map>

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
// (2026-10-17 — 파트 감쇠 `*DAMPING_PART_MASS`·`_STIFFNESS` 와 초기응력 `*INITIAL_STRESS_SOLID`·`_SHELL` 은 아래에서 읽는다)
const char* const kCounted[] = {
    "*PART_MOVE", "*BOUNDARY_PRESCRIBED_MOTION_RIGID",
    "*INITIAL_VELOCITY_GENERATION", "*MAT_ADD_THERMAL_EXPANSION", "*DEFORMABLE_TO_RIGID",
    "*INITIAL_STRAIN_SOLID", "*INITIAL_STRAIN_SHELL",
};

int ceilDiv(int a, int b) { return a <= 0 ? 0 : (a + b - 1) / b; }

}  // namespace

Scan find(const std::vector<std::string>& L, int deckFw, const std::function<bool(Axis, int)>& keep) {
    Scan s;
    Walker w{L, keep, s};
    // 접촉 Card 1 줄 — 키워드 줄 → Card 1 줄. 정본이 ID 카드 · MPP 1 · `&` MPP 2 · 빈 줄을 센다(사본을 두지 않는다 — 10-24).
    std::map<size_t, size_t> contactCard1;
    for (const auto& c : ct_parseContacts(L))
        if (c.cardLine[0] >= 0) contactCard1[static_cast<size_t>(c.startLine)] = static_cast<size_t>(c.cardLine[0]);
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
        //   앞에 오는 카드(제목 줄 · ID 카드 · MPP 1 · `&` MPP 2)는 정본이 센다(위 `contactCard1`).
        //   서명(STYP 두 칸이 0..6 정수)이 안 맞으면 단정하지 않는다.
        if (starts(kw, "*CONTACT_")) {
            const auto at = contactCard1.find(b.kwLine);
            if (at == contactCard1.end()) { w.skipped(kw); continue; }
            const size_t li = at->second;
            const auto c = cardcut::cut(L[li], w10);
            int sstyp = -1, mstyp = -1;
            const bool sig = c.f.size() >= 4 && toInt(c.f[2], sstyp) && toInt(c.f[3], mstyp) &&
                             sstyp >= 0 && sstyp <= 6 && mstyp >= 0 && mstyp <= 6;
            if (!sig) { w.skipped(kw); continue; }
            std::vector<int> idx;
            if (sstyp == 3) idx.push_back(0);
            if (mstyp == 3) idx.push_back(1);
            if (!idx.empty()) w.take(li, kw, Axis::Part, idx, w10);
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
        // ── 파트 감쇠 — Card 1 칸 1 = PID(맨 키워드) · `_SET` 은 PSID(블록의 세트 번호라 그대로 둔다) ─────────────
        //   (Vol_I 114601-114860) `*DAMPING_PART_MASS` 는 FLAG(칸 4) = 1 이면 Card 2(STX..SRZ)가 따라온다 — 그 줄을 다음
        //   Card 1 로 읽지 않는다. 그 밖의 꼬리(모르는 변형)는 단정하지 않는다.
        if (starts(kw, "*DAMPING_PART_MASS") || starts(kw, "*DAMPING_PART_STIFFNESS")) {
            const bool mass = starts(kw, "*DAMPING_PART_MASS");
            const std::string base = mass ? "*DAMPING_PART_MASS" : "*DAMPING_PART_STIFFNESS";
            const bool set = (kw == base + "_SET");
            if (kw != base && !set) { w.skipped(kw); continue; }
            for (size_t m = 0; m < b.data.size(); ++m) {
                if (!set) w.take(b.data[m], kw, Axis::Part, {0}, w10);
                if (!mass) continue;
                const auto c = cardcut::cut(L[b.data[m]], w10);
                int flag = 0;
                if (c.f.size() > 3 && toInt(c.f[3], flag) && flag == 1) ++m;   // Card 2 를 건넌다
            }
            continue;
        }
        // ── 초기응력 — 카드 세트마다 Card 1 칸 1 = EID(맨 키워드) · `_SET` 은 SID(블록의 세트 번호) ───────────────
        //   세트 길이는 Card 1 의 칸이 정한다(Vol_I 189463-189900 SHELL · 190150-190470 SOLID) —
        //     SOLID  LARGE 0: 1 + NINT (NHISV 는 0 이어야 한다)
        //            LARGE 1: 1 + NINT×(2 + ⌈(NHISV−3)/5⌉) + NTHINT×⌈NTHHSV/5⌉
        //     SHELL  LARGE 0: 1 + NPLANE×NTHICK×(1 + ⌈NHISV/8⌉ + ⌈NTENSR/6⌉)
        //            LARGE 1: 1 + NPLANE×NTHICK×(2 + ⌈NHISV/5⌉ + 2⌈NTENSR/6⌉) + NTHINT×⌈NTHHSV/5⌉
        //   칸이 그 꼴이 아니거나(정수 아님 · 음수 · LARGE 가 0·1 이 아님) 세트를 다 걸었는데 줄이 남거나 모자라면
        //   그 블록은 **단정하지 않는다**(EID 를 엉뚱한 줄에서 읽느니 세어 둔다). `_NURBS_PATCH` 등 다른 꼬리도 같다.
        if (starts(kw, "*INITIAL_STRESS_SOLID") || starts(kw, "*INITIAL_STRESS_SHELL")) {
            const bool solid = starts(kw, "*INITIAL_STRESS_SOLID");
            const std::string base = solid ? "*INITIAL_STRESS_SOLID" : "*INITIAL_STRESS_SHELL";
            const bool set = (kw == base + "_SET");
            if (kw != base && !set) { w.skipped(kw); continue; }
            std::vector<size_t> card1;
            bool ok = true;
            size_t m = 0;
            while (ok && m < b.data.size()) {
                const auto c = cardcut::cut(L[b.data[m]], w10);
                int f[8] = {0, 0, 0, 0, 0, 0, 0, 0};
                for (size_t q = 0; q < 8 && ok; ++q)
                    if (q < c.f.size() && !c.f[q].empty() && (!toInt(c.f[q], f[q]) || f[q] < 0)) ok = false;
                if (!ok || f[0] <= 0) { ok = false; break; }
                long long n = 0;
                if (solid) {
                    const int nint = f[1], nhisv = f[2], large = f[3], nthint = f[6], nthhsv = f[7];
                    if (nint <= 0 || (large != 0 && large != 1) || (large == 0 && (nhisv != 0 || nthint != 0))) { ok = false; break; }
                    n = large == 0 ? nint
                                   : static_cast<long long>(nint) * (2 + ceilDiv(nhisv - 3, 5)) +
                                     static_cast<long long>(nthint) * ceilDiv(nthhsv, 5);
                } else {
                    const int np = f[1], nt = f[2], nhisv = f[3], ntensr = f[4], large = f[5], nthint = f[6], nthhsv = f[7];
                    if (np <= 0 || nt <= 0 || (large != 0 && large != 1) || (large == 0 && nthint != 0)) { ok = false; break; }
                    const long long ip = static_cast<long long>(np) * nt;
                    n = large == 0 ? ip * (1 + ceilDiv(nhisv, 8) + ceilDiv(ntensr, 6))
                                   : ip * (2 + ceilDiv(nhisv, 5) + 2 * ceilDiv(ntensr, 6)) +
                                     static_cast<long long>(nthint) * ceilDiv(nthhsv, 5);
                }
                card1.push_back(m);
                m += 1 + static_cast<size_t>(n);
            }
            if (!ok || m != b.data.size()) { w.skipped(kw); continue; }
            if (!set) for (size_t k : card1) w.take(b.data[k], kw, Axis::Elem, {0}, w10);
            continue;
        }
        for (const char* p : kCounted)
            if (starts(kw, p)) {
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
        "*DAMPING_PART_MASS", "*DAMPING_PART_STIFFNESS", "*INITIAL_STRESS_SOLID", "*INITIAL_STRESS_SHELL",
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
