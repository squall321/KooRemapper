// 재질 번호(MID) 공용 훑기 — 구조 재질 블록을 카드 묶음으로 갈라 MID 를 세고, 그 정의를 지우거나 베낀다(MaterialIds.h)
#include "parser/MaterialIds.h"

#include "parser/CardFields.h"
#include "parser/CarryoverPlan.h"
#include "parser/DeckScan.h"
#include "parser/ElementCardLayout.h"

#include <algorithm>
#include <cstdio>

namespace KooRemapper {
namespace matids {

namespace {

bool blankLine(const std::string& l) { return l.find_first_not_of(" \t\r") == std::string::npos; }

// 키워드 줄인가(첫 비공백 글자가 `*`) — 섹션 묶음 훑기 · 옛 첫 카드 훑기와 같은 판정
bool keywordLine(const std::string& l) {
    const size_t g = l.find_first_not_of(" \t");
    return g != std::string::npos && l[g] == '*';
}

bool commentLine(const std::string& l) {
    const size_t h = l.find_first_not_of(" \t\r");
    return h != std::string::npos && l[h] == '$';
}

// 묶음 한 벌의 데이터 줄 수(`_TITLE` 제목 줄은 뺀다) — 모르면 -1. Vol II R16 의 카드 요약 그대로(MaterialIds.h 머리말)
int setRows(const std::string& base, const std::string& card1, int w) {
    if (card1.find(',') != std::string::npos) return -1;   // 자유 형식 — 칸 자리를 모른다
    const bool fluid = base == "*MAT_ELASTIC_FLUID" || base == "*MAT_001_FLUID";
    if (fluid || base == "*MAT_ELASTIC" || base == "*MAT_001") {
        // Card 1.1(EFUNC CNVT ITERLM)은 E < 0 일 때 온다 · Card 2(VC CP)는 `_FLUID` 일 때 온다
        const auto f = deckscan::cardFields(card1, w);
        const std::string e = f.size() > 2 ? deckscan::trim(f[2]) : std::string();
        double ev = 0;
        if (!e.empty() && !carryover::realField(e, ev)) return -1;   // E 가 수가 아니다(매개변수 `&E` 따위) — 지어내지 않는다
        return 1 + (!e.empty() && ev < 0 ? 1 : 0) + (fluid ? 1 : 0);
    }
    static const std::map<std::string, int> fixed = {
        {"*MAT_PLASTIC_KINEMATIC", 2}, {"*MAT_003", 2},
        {"*MAT_VISCOELASTIC", 1}, {"*MAT_006", 1},
        {"*MAT_NULL", 1}, {"*MAT_009", 1},
        {"*MAT_RIGID", 3}, {"*MAT_020", 3},
        {"*MAT_PIECEWISE_LINEAR_PLASTICITY", 4}, {"*MAT_024", 4},
    };
    const auto it = fixed.find(base);
    return it == fixed.end() ? -1 : it->second;
}

// Card 1 의 MID — 옛 첫 카드 훑기와 같은 칸 읽기(고정폭 · 어긋난 줄이면 공백 토큰 · 정수만)
int midOf(const std::string& card1, int w) { return deckscan::fieldInt(deckscan::cardFields(card1, w), 0); }

// MID 칸을 newMid 로 — 고정폭 칸이 정수면 그 칸을 오른쪽 맞춤으로, 쉼표 줄이면 첫 값을, 칸이 어긋난 줄이면 첫 토큰을 바꾼다
std::string withMid(const std::string& line, int w, int newMid) {
    const std::string val = std::to_string(newMid);
    const size_t comma = line.find(',');
    if (comma != std::string::npos) return val + line.substr(comma);
    int probe = 0;
    if (cards::toInt(deckscan::trim(line.substr(0, std::min(line.size(), static_cast<size_t>(w)))), probe) &&
        val.size() <= static_cast<size_t>(w)) {
        std::string head(static_cast<size_t>(w) - val.size(), ' ');
        head += val;
        return line.size() > static_cast<size_t>(w) ? head + line.substr(static_cast<size_t>(w)) : head;
    }
    const size_t a = line.find_first_not_of(" \t");
    if (a == std::string::npos) return line;
    const size_t b = line.find_first_of(" \t", a);
    return line.substr(0, a) + val + (b == std::string::npos ? std::string() : line.substr(b));
}

}  // namespace

bool isStructuralKeyword(const std::string& kw) {
    return kw.rfind("*MAT_", 0) == 0 && kw.rfind("*MAT_ADD_", 0) != 0 && !cards::isThermalMaterialKeyword(kw);
}

Scan scan(const std::vector<std::string>& lines) {
    Scan out;
    const int deckFw = deckFieldWidth(lines);
    for (size_t i = 0; i < lines.size();) {
        if (!keywordLine(lines[i])) { ++i; continue; }
        const std::string kw = deckscan::kwBare(deckscan::keywordToken(lines[i]));
        size_t j = i + 1;
        std::vector<size_t> rows;   // 블록의 데이터 줄(빈 줄 포함 · 주석 뺌)
        for (; j < lines.size() && !keywordLine(lines[j]); ++j)
            if (!commentLine(lines[j])) rows.push_back(j);
        if (!isStructuralKeyword(kw)) { i = j; continue; }
        while (!rows.empty() && blankLine(lines[rows.back()])) rows.pop_back();   // 끝의 빈 줄은 여백
        Block blk;
        blk.keyword = i;
        blk.end = j;
        blk.width = keywordFieldWidth(lines[i], deckFw) == 20 ? 20 : 10;
        const int w = blk.width;
        const bool title = kw.size() > 6 && kw.compare(kw.size() - 6, 6, "_TITLE") == 0;
        const std::string base = title ? kw.substr(0, kw.size() - 6) : kw;
        const size_t t = title ? 1 : 0;
        size_t rest = std::string::npos;   // 못 가른 자리(행 차례)
        for (size_t a = 0; a < rows.size();) {
            if (a + t >= rows.size()) break;                                  // 묶음이 제목 줄에서 끝났다 — Card 1 이 없다
            const int mid = midOf(lines[rows[a + t]], w);
            const int n = setRows(base, lines[rows[a + t]], w);
            if (mid <= 0) { rest = a; break; }                                // 묶음의 MID 칸이 정수가 아니다(빈 칸 · 이름표)
            Set s;
            s.mid = mid;
            s.first = rows[a];
            s.card1 = rows[a + t];
            if (n < 0) {
                // 행 수를 모르는 꼴 — 그 묶음의 MID 는 읽고, 그 자리부터 행마다 넉넉히 센다(뒤에 묶음이 더 쌓였는지 모른다)
                s.last = rows.back();
                s.exact = false;
                blk.sets.push_back(s);
                rest = a;
                break;
            }
            if (a + t + static_cast<size_t>(n) > rows.size()) {
                // 마지막 묶음이 모자란다(빠진 카드) — 블록 끝까지가 그 묶음이다(뒤에 남는 줄이 없다 · StepForge 도 읽은 만큼 싣는다)
                s.last = rows.back();
                s.exact = true;
                blk.sets.push_back(s);
                break;
            }
            s.last = rows[a + t + static_cast<size_t>(n) - 1];
            s.exact = true;
            blk.sets.push_back(s);
            a += t + static_cast<size_t>(n);
        }
        if (rest != std::string::npos) {
            blk.remainder = true;
            for (size_t r = rest; r < rows.size(); ++r) {
                int v = 0;
                if (deckscan::digitsField(lines[rows[r]], w, v)) out.loose.insert(v);
            }
        }
        const size_t bi = out.blocks.size();
        for (size_t k = 0; k < blk.sets.size(); ++k) out.defs[blk.sets[k].mid].emplace_back(bi, k);
        out.blocks.push_back(std::move(blk));
        i = j;
    }
    return out;
}

std::set<int> defined(const std::vector<std::string>& lines) {
    std::set<int> out;
    for (const auto& [mid, at] : scan(lines).defs) {
        (void)at;
        out.insert(mid);
    }
    return out;
}

std::set<int> inUse(const std::vector<std::string>& lines) {
    const Scan s = scan(lines);
    std::set<int> out = s.loose;
    for (const auto& [mid, at] : s.defs) {
        (void)at;
        out.insert(mid);
    }
    return out;
}

int maxId(const std::vector<std::string>& lines) {
    const auto ids = inUse(lines);
    return ids.empty() ? 0 : *ids.rbegin();
}

std::map<int, std::vector<size_t>> definitionLines(const std::vector<std::string>& lines) {
    const Scan s = scan(lines);
    std::map<int, std::vector<size_t>> out;
    for (const auto& [mid, at] : s.defs)
        for (const auto& [b, k] : at) out[mid].push_back(s.blocks[b].sets[k].card1);
    return out;
}

Removed removeDefinition(std::vector<std::string>& lines, int mid) {
    Removed r;
    const Scan s = scan(lines);
    const auto it = s.defs.find(mid);
    if (it != s.defs.end()) {
        std::vector<bool> cut(lines.size(), false);
        std::map<size_t, size_t> hits;   // 블록 → 지울 묶음 수
        for (const auto& [b, k] : it->second) ++hits[b];
        for (const auto& [b, n] : hits) {
            const Block& blk = s.blocks[b];
            // 블록의 묶음이 다 지워지면(못 가른 자리 없이) 키워드 줄째 — 빈 재질 키워드를 남기지 않는다. 길이를 모르는 첫 묶음도 블록째다
            // (예전 그대로 — 그 뒤에 쌓인 재질이 있는지 모른다)
            bool whole = !blk.remainder && n == blk.sets.size();
            for (const auto& [b2, k] : it->second)
                if (b2 == b && k == 0 && !blk.sets[k].exact) whole = true;
            for (const auto& [b2, k] : it->second) {
                if (b2 != b) continue;
                // 길이를 모르는 쌓인 묶음(앞 묶음은 갈랐다)은 그 자리부터 블록 끝까지 — 그 묶음의 끝을 모른다
                const size_t to = blk.sets[k].exact ? blk.sets[k].last + 1 : blk.end;
                for (size_t l = whole ? blk.keyword : blk.sets[k].first; l < (whole ? blk.end : to); ++l) cut[l] = true;
            }
            r.sets += static_cast<int>(n);
        }
        std::vector<std::string> keep;
        keep.reserve(lines.size());
        for (size_t l = 0; l < lines.size(); ++l)
            if (!cut[l]) keep.push_back(std::move(lines[l]));
        lines.swap(keep);
    }
    r.stillUsed = inUse(lines).count(mid) > 0;
    return r;
}

bool isMidKeyedAddOn(const std::string& kw) {
    if (kw.rfind("*MAT_ADD_", 0) != 0) return false;
    std::string base = kw;
    if (base.size() > 6 && base.compare(base.size() - 6, 6, "_TITLE") == 0) base.resize(base.size() - 6);
    static const std::set<std::string> mid = {
        "*MAT_ADD_EROSION", "*MAT_ADD_DAMAGE_GISSMO", "*MAT_ADD_DAMAGE_DIEM", "*MAT_ADD_FATIGUE", "*MAT_ADD_GENERALIZED_DAMAGE",
        "*MAT_ADD_INELASTICITY", "*MAT_ADD_PERMEABILITY", "*MAT_ADD_PORE_AIR", "*MAT_ADD_PROPERTY_DEPENDENCE", "*MAT_ADD_PZELECTRIC",
        "*MAT_ADD_AIRBAG_POROSITY_LEAKAGE", "*MAT_ADD_BASIC_INCREMENTAL_FAILURE"};
    return mid.count(base) > 0;
}

int removeMidAddOns(std::vector<std::string>& lines, int mid) {
    const int deckFw = deckFieldWidth(lines);
    std::vector<bool> cut(lines.size(), false);
    int n = 0;
    for (size_t i = 0; i < lines.size();) {
        if (!keywordLine(lines[i])) { ++i; continue; }
        const std::string kw = deckscan::kwBare(deckscan::keywordToken(lines[i]));
        size_t j = i + 1;
        while (j < lines.size() && !keywordLine(lines[j])) ++j;
        if (isMidKeyedAddOn(kw)) {
            const int w = keywordFieldWidth(lines[i], deckFw) == 20 ? 20 : 10;
            bool title = kw.size() > 6 && kw.compare(kw.size() - 6, 6, "_TITLE") == 0;
            for (size_t r = i + 1; r < j; ++r) {
                if (commentLine(lines[r])) continue;
                if (title) { title = false; continue; }
                if (midOf(lines[r], w) == mid) {
                    for (size_t l = i; l < j; ++l) cut[l] = true;
                    ++n;
                }
                break;
            }
        }
        i = j;
    }
    if (n > 0) {
        std::vector<std::string> keep;
        keep.reserve(lines.size());
        for (size_t l = 0; l < lines.size(); ++l)
            if (!cut[l]) keep.push_back(std::move(lines[l]));
        lines.swap(keep);
    }
    return n;
}

std::string copyDefinition(const std::vector<std::string>& lines, int mid, int newMid) {
    const Scan s = scan(lines);
    const auto it = s.defs.find(mid);
    if (it == s.defs.end()) return "";
    const auto [b, k] = it->second.front();
    const Block& blk = s.blocks[b];
    const Set& set = blk.sets[k];
    // 묶음 앞의 주석(머리말 `$#  mid  ro …`)도 싣는다 — 첫 묶음이면 키워드 다음 줄부터, 쌓인 묶음이면 앞 묶음 다음 줄부터
    const size_t from = k == 0 ? blk.keyword + 1 : blk.sets[k - 1].last + 1;
    const size_t to = set.exact ? set.last + 1 : blk.end;
    std::string out = lines[blk.keyword] + "\n";
    for (size_t l = from; l < to; ++l) {
        if (k == 0 && l < set.first && !commentLine(lines[l])) continue;   // 키워드와 첫 묶음 사이는 주석뿐이다(빈 줄은 여백)
        out += (l == set.card1 ? withMid(lines[l], blk.width, newMid) : lines[l]) + "\n";
    }
    return out;
}

}  // namespace matids
}  // namespace KooRemapper
