// 세트 멤버 해석 정본 — 규칙과 근거는 set_members.h
#include "set_members.h"

#include <algorithm>
#include <set>

namespace {

bool hasDialect(const SetDef& s, const char* d) {
    return s.dialect.find(d) != std::string::npos;
}

std::vector<const SetDef*> defsOf(const std::vector<SetDef>& sets, int sid, const std::string& type) {
    std::vector<const SetDef*> out;
    for (const auto& s : sets)
        if (s.id == sid && s.type == type) out.push_back(&s);
    return out;
}

std::string tag(const std::string& type, int sid) {
    return "SET_" + type + " " + std::to_string(sid);
}

// 방언 중 멤버를 **풀지 않는** 것 — 옵션 코드(`_GENERAL`)·자료 칸(`_COLUMN`)·(세트 ID, 종류) 쌍(`_ADVANCED`).
const char* unsupportedDialect(const SetDef& s) {
    if (hasDialect(s, "ADVANCED")) return "ADVANCED";
    if (hasDialect(s, "GENERAL")) return "GENERAL";
    if (hasDialect(s, "COLUMN")) return "COLUMN";
    return nullptr;
}

struct Acc {
    std::set<int> ids;
    std::vector<std::array<int,4>> segs;        // 덱 순서를 지킨다
    std::set<std::array<int,4>> segSeen;
    void addSeg(const std::array<int,4>& g) {
        if (segSeen.insert(g).second) segs.push_back(g);
    }
};

// 같은 종류 · 같은 ID 정의가 여럿이면 **모두 COLLECT 일 때만** 합친다(Vol_I `*SET` COLLECT —
// 하나라도 아니면 LS-DYNA 가 오류로 끝낸다). 합칠 수 없으면 false.
bool collectable(const std::vector<const SetDef*>& defs, const std::string& type, int sid,
                 std::string& why) {
    if (defs.size() <= 1) return true;
    for (const SetDef* d : defs) {
        if (!hasDialect(*d, "COLLECT")) {
            why = tag(type, sid) + " 정의가 " + std::to_string(defs.size()) +
                  "개인데 COLLECT 가 아닌 것이 있다 — LS-DYNA 는 오류로 끝낸다";
            return false;
        }
    }
    return true;
}

// `_ADD` 의 멤버 세트 ID — PART 의 음수는 「앞 칸부터 그 절대값까지」의 범위다(Vol_I `*SET_PART_ADD`
// PSID[N] LT.0). 범위는 **덱에 정의된** 세트만 고른다. 명시한 세트가 덱에 없으면 빼고 `note` 에 적는다
// ("Ignore any nonexistant part set IDs in *SET_PART_ADD").
bool addMemberIds(const std::vector<SetDef>& sets, const SetDef& s, std::vector<int>& out,
                  std::string& why, std::string& note) {
    std::vector<int> listed;
    int prev = 0;
    for (int m : s.memberSets) {
        if (m > 0) { listed.push_back(m); prev = m; continue; }
        if (s.type != "PART") {
            why = tag(s.type, s.id) + "_ADD 의 음수 멤버 " + std::to_string(m) +
                  " — 범위 표기는 *SET_PART_ADD 에만 정의돼 있다";
            return false;
        }
        if (prev <= 0 || -m < prev) {
            why = tag(s.type, s.id) + "_ADD 의 음수 멤버 " + std::to_string(m) +
                  " 가 앞 칸과 범위를 이루지 못한다";
            return false;
        }
        std::set<int> inRange;
        for (const auto& t : sets)
            if (t.type == s.type && t.id > prev && t.id <= -m) inRange.insert(t.id);
        out.insert(out.end(), inRange.begin(), inRange.end());
        prev = 0;   // 범위 하나가 시작 칸을 썼다 — 다음 음수는 새 시작 칸이 있어야 한다
    }
    std::vector<int> missing;
    for (int id : listed) {
        if (defsOf(sets, id, s.type).empty()) missing.push_back(id);
        else out.push_back(id);
    }
    if (!missing.empty()) {
        std::string ids;
        for (size_t k = 0; k < missing.size(); ++k) ids += (k ? ", " : "") + std::to_string(missing[k]);
        if (!note.empty()) note += " · ";
        note += tag(s.type, s.id) + "_ADD 의 멤버 세트 " + ids + " 가 덱에 없어 뺐다";
    }
    return true;
}

bool collect(const std::vector<SetDef>& sets, int sid, const std::string& type,
             std::vector<int>& path, Acc& acc, std::string& why, std::string& note) {
    auto defs = defsOf(sets, sid, type);
    if (defs.empty()) { why = tag(type, sid) + " 이 덱에 없다"; return false; }
    if (std::find(path.begin(), path.end(), sid) != path.end()) {
        why = tag(type, sid) + " 가 돌아서 자기 자신을 포함한다(순환)";
        return false;
    }
    if (!collectable(defs, type, sid, why)) return false;

    path.push_back(sid);
    bool ok = true;
    for (const SetDef* d : defs) {
        if (const char* bad = unsupportedDialect(*d)) {
            why = tag(type, sid) + " 는 _" + bad + " 방언이라 멤버를 풀지 않는다";
            ok = false;
        } else if (hasDialect(*d, "ADD")) {
            std::vector<int> mids;
            ok = addMemberIds(sets, *d, mids, why, note);
            for (size_t k = 0; ok && k < mids.size(); ++k)
                ok = collect(sets, mids[k], type, path, acc, why, note);
        } else if (hasDialect(*d, "INTERSECT")) {
            // 교집합 — 멤버 세트 **모두에** 드는 것만. 세그먼트는 네 절점이 같은 차례로 같을 때 같다고 본다.
            if (d->memberSets.empty()) {
                why = tag(type, sid) + "_INTERSECT 에 멤버 세트가 없다";
                ok = false;
            }
            Acc inter;
            bool first = true;
            for (size_t k = 0; ok && k < d->memberSets.size(); ++k) {
                const int m = d->memberSets[k];
                if (m <= 0) {
                    why = tag(type, sid) + "_INTERSECT 의 멤버 " + std::to_string(m) + " 는 세트 ID 가 아니다";
                    ok = false;
                    break;
                }
                Acc one;
                if (!collect(sets, m, type, path, one, why, note)) { ok = false; break; }
                if (first) { inter = one; first = false; continue; }
                Acc next;
                for (int v : inter.ids) if (one.ids.count(v)) next.ids.insert(v);
                for (const auto& g : inter.segs) if (one.segSeen.count(g)) next.addSeg(g);
                inter = next;
            }
            if (ok) {
                acc.ids.insert(inter.ids.begin(), inter.ids.end());
                for (const auto& g : inter.segs) acc.addSeg(g);
            }
        } else if (!d->ranges.empty() && !d->rangesResolved) {
            why = tag(type, sid) + " 의 _GENERATE 범위를 덱에 정의된 ID 로 좁히지 않았다";
            ok = false;
        } else if (!d->membersKnown) {
            why = tag(type, sid) + (d->dialect.empty() ? "" : "_" + d->dialect) +
                  " — 멤버의 뜻을 확정하지 못했다";
            ok = false;
        } else {
            acc.ids.insert(d->ids.begin(), d->ids.end());
            for (const auto& g : d->segments) acc.addSeg(g);
        }
        if (!ok) break;
    }
    path.pop_back();
    return ok;
}

int hasRec(const std::vector<SetDef>& sets, int sid, const std::string& type, int id,
           std::vector<int>& path) {
    auto defs = defsOf(sets, sid, type);
    if (defs.empty()) return -1;
    if (std::find(path.begin(), path.end(), sid) != path.end()) return -1;
    std::string why;
    if (!collectable(defs, type, sid, why)) return -1;

    path.push_back(sid);
    bool unknown = false, yes = false;
    for (const SetDef* d : defs) {
        int r = 0;
        if (unsupportedDialect(*d)) {
            r = -1;
        } else if (hasDialect(*d, "ADD")) {
            std::vector<int> mids;
            std::string note;
            if (!addMemberIds(sets, *d, mids, why, note)) {
                r = -1;
            } else {
                for (int m : mids) {
                    const int x = hasRec(sets, m, type, id, path);
                    if (x == 1) { r = 1; break; }
                    if (x == -1) r = -1;
                }
            }
        } else if (hasDialect(*d, "INTERSECT")) {
            r = d->memberSets.empty() ? -1 : 1;
            for (int m : d->memberSets) {
                const int x = (m > 0) ? hasRec(sets, m, type, id, path) : -1;
                if (x == 0) { r = 0; break; }
                if (x == -1) r = -1;
            }
        } else if (!d->membersKnown && d->ranges.empty()) {
            r = -1;
        } else {
            // 평범한 목록과 `_GENERATE` 범위 — 범위는 좁히지 않아도 포함 여부는 답할 수 있다.
            r = ct_setContains(*d, id) ? 1 : 0;
        }
        if (r == 1) { yes = true; break; }
        if (r == -1) unknown = true;
    }
    path.pop_back();
    if (yes) return 1;
    return unknown ? -1 : 0;
}

}  // namespace

SetMembers ct_setMembers(const std::vector<SetDef>& sets, int sid, const std::string& type) {
    SetMembers r;
    r.found = !defsOf(sets, sid, type).empty();
    std::vector<int> path;
    Acc acc;
    r.resolved = collect(sets, sid, type, path, acc, r.why, r.note);
    if (r.resolved) {
        r.why.clear();
        r.ids.assign(acc.ids.begin(), acc.ids.end());
        r.segments = acc.segs;
    }
    return r;
}

int ct_setHas(const std::vector<SetDef>& sets, int sid, const std::string& type, int id) {
    std::vector<int> path;
    return hasRec(sets, sid, type, id, path);
}

// 그 ID 가 이 세트에 드는가 — **정의 목록이 없어도** 답할 수 있는 물음이다.
// `optimize` 처럼 메시를 안 읽는 op 이 쓴다(그 op 은 "이 접촉이 대상 파트를 건드리나" 만 묻는다).
bool ct_setContains(const SetDef& s, int id) {
    for (int v : s.ids) if (v == id) return true;
    for (const auto& r : s.ranges)
        if (id >= r[0] && id <= r[1] && (r[2] <= 1 || (id - r[0]) % r[2] == 0)) return true;
    return false;
}
