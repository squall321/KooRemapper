// StepForge 조각을 기존 덱에 넣는다 — 계약(BOUNDARY-DYNAFORGE §3-3) 그대로 검증하고 덱 번호 위로 옮겨 `*END` 앞에 둔다
#include "assembly/ModelAssembler.h"

#include "core/Mesh.h"
#include "parser/DeckScan.h"
#include "parser/ElementCardLayout.h"
#include "parser/FragmentMap.h"
#include "parser/KFileReader.h"

#include <algorithm>
#include <cstdio>
#include <filesystem>
#include <fstream>
#include <limits>
#include <sstream>

// 왜 이 op 이 있나 (2026-10-16). 경계 합의(§1·§3-3)가 「조각을 쓰는 것은 StepForge, 그 조각을 기존 덱에
// **넣는** 것은 우리」로 정했다(이미 있는 덱의 바이트를 바꾸는 일이라서). 과도기 번호 길(Q5)대로 저쪽이
// 정한 시작 번호로 쓴 조각을 **우리가 옮긴다** — 대상 덱(인클루드 닫힘까지)의 최대값 위로.
//
// 지키는 것.
//   · 받기 전에 **계약 그대로** 본다 — 대응표 칸 집합(모르는 칸 거절) · unit 이 덱 단위와 같다 · frame 이
//     world · 조각 대조(`fragment::check` — 번호 구간 · 파트 집합 · 파트마다 요소·절점 구간 · coord_sha)
//   · 조각에 계약 밖 키워드가 있으면 **거절**한다 — 옮기는 규칙을 모르는 카드를 옮기면 번호가 그럴듯하게 틀린다
//   · PID·SECID·MID 는 **한 이동량**으로 옮긴다 — 저쪽 라이터가 셋을 같은 번호로 쓰고 `ranges.pid` 가 셋의 대역이다
//     (덱에 넣은 뒤에도 그 규약이 선다)
//   · 좌표 글자는 **바이트 그대로**(번호 칸만 바꾼다) — 넣은 블록을 다시 읽어 파트마다 coord_sha 로 스스로 대조한다
//   · 번호 칸은 **덱의 폭**으로 쓴다(i10 덱이면 10칸). long 덱은 받지 않는다(좌표 칸도 넓어진다 — 장부의 원칙)
//   · 세트가 든 조각(`ranges.sid` 가 null 이 아님)은 아직 받지 않는다 — 저쪽 조각은 늘 null 이다(§3-3)

namespace KooRemapper {
namespace {

// 계약(§3-3)이 적은 조각 키워드 — 이것 밖은 거절한다.
bool contractKeyword(const std::string& kw) {
    if (kw.rfind("*MAT_", 0) == 0)
        return kw.rfind("*MAT_ADD_", 0) != 0 && kw.rfind("*MAT_THERMAL_", 0) != 0;
    return kw == "*KEYWORD" || kw == "*END" || kw == "*NODE" || kw == "*ELEMENT_SOLID" || kw == "*ELEMENT_SHELL" ||
           kw == "*PART" || kw == "*SECTION_SOLID" || kw == "*SECTION_SOLID_TITLE" || kw == "*SECTION_SHELL" ||
           kw == "*SECTION_SHELL_TITLE";
}

std::string padInt(long long v, int w) {
    char buf[32];
    std::snprintf(buf, sizeof(buf), "%*lld", w, v);
    return buf;
}

bool parseLL(const std::string& s, long long& v) {
    const std::string t = deckscan::trim(s);
    if (t.empty()) { v = 0; return true; }
    try {
        size_t used = 0;
        v = std::stoll(t, &used);
        return used == t.size();
    } catch (...) {
        return false;
    }
}

struct Shift {
    long long node = 0, elem = 0, pid = 0;   // pid 는 SECID·MID 에도 같다
};

// 조각 줄을 옮긴다 — 번호 칸만 바꾸고 나머지 글자는 그대로 둔다.
bool remapFragment(const std::vector<std::string>& in, const Shift& sh, int fw, std::string& out,
                   std::vector<std::string>& notes, std::string& err) {
    enum class Blk { None, Node, Elem, Part, Section, Mat };
    Blk blk = Blk::None;
    std::string kw;
    int setPos = 0;      // 키워드 블록 안에서 몇째 데이터 줄인가(제목 포함)
    bool nodeLineNext = false;   // 두 줄 꼴 솔리드 카드(EID PID / 절점)의 둘째 줄을 기다린다
    int setLen = 0;      // 한 정의(세트)의 데이터 줄 수 — 0 이면 첫 카드만 옮긴다
    bool hasTitle = false;
    std::ostringstream o;
    for (size_t i = 0; i < in.size(); ++i) {
        const std::string& l = in[i];
        const std::string where = "조각 " + std::to_string(i + 1) + "째 줄";
        const size_t g = l.find_first_not_of(" \t");
        if (g != std::string::npos && l[g] == '*') {
            kw = deckscan::kwBare(deckscan::keywordToken(l));
            if (!contractKeyword(kw)) {
                err = where + " — 계약(§3-3) 밖 키워드 " + kw + " — 옮기는 규칙을 모르는 카드는 받지 않는다";
                return false;
            }
            if (keywordFieldWidth(l, 8) != 8) {
                err = where + " — 칸 폭 접미사(" + deckscan::keywordToken(l) + ") — 조각은 표준 폭이어야 한다";
                return false;
            }
            if (kw == "*KEYWORD" || kw == "*END") { blk = Blk::None; continue; }   // 덱의 것을 쓴다
            hasTitle = kw.find("_TITLE") != std::string::npos;
            setPos = 0;
            nodeLineNext = false;
            if (kw == "*NODE") { blk = Blk::Node; setLen = 1; }
            else if (kw.rfind("*ELEMENT_", 0) == 0) { blk = Blk::Elem; setLen = 1; }
            else if (kw == "*PART") { blk = Blk::Part; setLen = 2; hasTitle = true; }   // *PART 는 늘 제목이 있다
            else if (kw.rfind("*SECTION_SOLID", 0) == 0) { blk = Blk::Section; setLen = (hasTitle ? 1 : 0) + 1; }
            else if (kw.rfind("*SECTION_SHELL", 0) == 0) { blk = Blk::Section; setLen = (hasTitle ? 1 : 0) + 2; }
            else { blk = Blk::Mat; setLen = 0; }
            o << kw << "\n";
            continue;
        }
        if (blk == Blk::None || (g != std::string::npos && l[g] == '$')) { o << l << "\n"; continue; }
        // 빈 줄은 주석이 아니라 **기본값 카드**다(LS-DYNA). 절점·요소 블록에서는 뜻이 없으니 거절하고,
        // 파트·섹션·재질 블록에서는 카드로 센다(제목이 비었을 수 있다)
        if (g == std::string::npos && (blk == Blk::Node || blk == Blk::Elem)) {
            err = where + " — 절점·요소 블록의 빈 줄";
            return false;
        }
        if (l.find(',') != std::string::npos) { err = where + " — 자유 형식(콤마) 줄 — 조각은 고정폭이어야 한다"; return false; }
        const int pos = setLen > 0 ? setPos % setLen : setPos;
        ++setPos;
        switch (blk) {
            case Blk::Node: {
                long long id = 0;
                if (l.size() < 8 || !parseLL(l.substr(0, 8), id) || id <= 0) { err = where + " — 절점 번호를 읽지 못했다"; return false; }
                o << padInt(id + sh.node, fw) << l.substr(8) << "\n";
                break;
            }
            case Blk::Elem: {
                auto f = deckscan::fieldsFixed(l, 8);
                while (!f.empty() && deckscan::trim(f.back()).empty()) f.pop_back();   // 끝의 빈 칸은 칸이 아니다
                // 솔리드는 두 줄 꼴(첫 줄 EID PID · 둘째 줄 절점)도 합법이다 — 같은 규칙으로 옮기고 꼴은 그대로 둔다
                const bool nodesOnly = nodeLineNext;
                nodeLineNext = false;
                if (!nodesOnly && f.size() == 2 && kw == "*ELEMENT_SOLID") nodeLineNext = true;
                else if (!nodesOnly && f.size() < 3) { err = where + " — 요소 카드의 칸이 모자라다"; return false; }
                std::string line;
                for (size_t k = 0; k < f.size(); ++k) {
                    long long v = 0;
                    if (!parseLL(f[k], v)) { err = where + " — 요소 카드 " + std::to_string(k + 1) + "째 칸이 정수가 아니다"; return false; }
                    if (nodesOnly) { if (v != 0) v += sh.node; }
                    else if (k == 0) v += sh.elem;
                    else if (k == 1) v += sh.pid;
                    else if (v != 0) v += sh.node;
                    line += padInt(v, fw);
                }
                o << line << "\n";
                break;
            }
            case Blk::Part: {
                if (pos == 0) { o << l << "\n"; break; }                     // 제목
                const auto f = deckscan::fieldsFixed(l, 10);
                long long pid = 0, secid = 0, mid = 0;
                if (f.size() < 3 || !parseLL(f[0], pid) || !parseLL(f[1], secid) || !parseLL(f[2], mid)) {
                    err = where + " — *PART 카드의 PID·SECID·MID 를 읽지 못했다"; return false;
                }
                for (size_t k : {3, 4, 7}) {                                   // EOSID · HGID · TMID
                    long long v = 0;
                    if (k < f.size() && (!parseLL(f[k], v) || v != 0)) {
                        err = where + " — *PART 의 EOSID·HGID·TMID 가 0 이 아니다 — 그 번호를 옮기는 규칙이 계약에 없다";
                        return false;
                    }
                }
                o << padInt(pid + sh.pid, 10) << padInt(secid + sh.pid, 10) << padInt(mid + sh.pid, 10)
                  << (l.size() > 30 ? l.substr(30) : std::string()) << "\n";
                break;
            }
            case Blk::Section:
            case Blk::Mat: {
                const int card1 = hasTitle ? 1 : 0;
                if (pos != card1) { o << l << "\n"; break; }                  // 제목·나머지 카드는 그대로
                long long id = 0;
                if (!parseLL(l.substr(0, std::min<size_t>(10, l.size())), id) || id <= 0) {
                    err = where + " — " + kw + " 의 번호(첫 칸)를 읽지 못했다"; return false;
                }
                o << padInt(id + sh.pid, 10) << (l.size() > 10 ? l.substr(10) : std::string()) << "\n";
                // 저쪽 자리표시 물성(RO = E = 1.0 — 일부러 눈에 띄게 둔 값)은 그대로 넣되 말한다
                if (blk == Blk::Mat && kw.rfind("*MAT_ELASTIC", 0) == 0) {
                    const auto f = deckscan::fieldsFixed(l, 10);
                    if (f.size() >= 3) {
                        try {
                            if (std::stod(f[1]) == 1.0 && std::stod(f[2]) == 1.0)
                                notes.push_back("MID " + std::to_string(id + sh.pid) +
                                                " — 저쪽 자리표시 물성(RO = E = 1.0)이다. 해석 전에 실물 물성으로 바꿀 것");
                        } catch (...) {}
                    }
                }
                break;
            }
            case Blk::None: break;
        }
    }
    if (nodeLineNext) { err = "조각 끝 — 두 줄 꼴 솔리드 카드의 절점 줄이 없다"; return false; }
    out = o.str();
    return true;
}

}  // namespace

bool ModelAssembler::applyCadSolidMerge(const CadSolidMergeOperation& op) {
    const std::string tag = "[cad_solid_merge_to_deck] ";
    // ① 대응표 — 칸 집합 그대로
    std::string mapText;
    {
        std::ifstream f(op.fragmentMap, std::ios::binary);
        if (!f.is_open()) { errorMessage_ = tag + "대응표를 열지 못했다: " + op.fragmentMap; return false; }
        std::ostringstream ss;
        ss << f.rdbuf();
        mapText = ss.str();
    }
    fragment::Map m;
    std::string err;
    if (!fragment::parseMap(mapText, m, err)) { errorMessage_ = tag + err; return false; }
    // ② unit·frame — 맞추는 것은 삽입 쪽이다(Q6). 환산·변환은 하지 않는다 — 다르면 거절
    if (m.unit != op.deckUnit) {
        errorMessage_ = tag + "조각 단위 '" + m.unit + "' 가 덱 단위 '" + op.deckUnit +
                        "' 와 다르다 — 환산하지 않는다(덱 단위가 다르면 deck_unit 으로 알려 거절받는 것이 맞다)";
        return false;
    }
    if (m.frame != "world") {
        errorMessage_ = tag + "조각 frame '" + m.frame + "' — world 만 받는다(좌표 변환을 하지 않는다)";
        return false;
    }
    if (m.sid.used) {
        errorMessage_ = tag + "ranges.sid 가 null 이 아니다 — 세트가 든 조각은 아직 받지 않는다(저쪽 조각은 늘 null)";
        return false;
    }
    // ③ 조각 대조 — 번호 구간 · 파트 집합 · 파트마다 요소·절점 구간 · coord_sha
    std::vector<std::string> frag;
    {
        std::ifstream f(op.fragment);
        if (!f.is_open()) { errorMessage_ = tag + "조각을 열지 못했다: " + op.fragment; return false; }
        for (std::string l; std::getline(f, l);) {
            if (!l.empty() && l.back() == '\r') l.pop_back();
            frag.push_back(l);
        }
    }
    if (deckFieldWidth(frag) != 8) { errorMessage_ = tag + "조각의 *KEYWORD 폭이 표준(8)이 아니다 — 계약은 표준 폭이다"; return false; }
    const auto problems = fragment::check(m, op.fragment);
    if (!problems.empty()) {
        errorMessage_ = tag + "조각이 대응표와 맞지 않는다(" + std::to_string(problems.size()) + "건) — 넣지 않았다";
        for (const auto& p : problems) errorMessage_ += "\n  " + p;
        return false;
    }
    // ④ 번호 이동 — 대상 덱(인클루드 닫힘까지 센 커서) 위로
    const int fw = deckFieldWidth(rawLines_);
    if (fw == 20) { errorMessage_ = tag + "long 폭 덱은 받지 않는다 — 좌표 칸도 넓어져 조각 글자를 그대로 둘 수 없다"; return false; }
    Shift sh;
    if (m.node.used) sh.node = (long long)maxNodeId_ + 1 - m.node.lo;
    if (m.elem.used) sh.elem = (long long)maxElementId_ + 1 - m.elem.lo;
    if (m.pid.used)
        sh.pid = (long long)std::max({maxPartId_, maxSectionId_, maxMaterialId_}) + 1 - m.pid.lo;
    const long long idCap = fw == 8 ? 99999999LL : (long long)std::numeric_limits<int>::max();
    const long long cardCap = (long long)std::numeric_limits<int>::max();
    if ((m.node.used && m.node.hi + sh.node > idCap) || (m.elem.used && m.elem.hi + sh.elem > idCap) ||
        (m.pid.used && m.pid.hi + sh.pid > cardCap)) {
        errorMessage_ = tag + "옮긴 번호가 덱의 칸 폭(" + std::to_string(fw) + ")을 넘는다 — 넣지 않았다";
        return false;
    }
    std::string block;
    std::vector<std::string> notes;
    if (!remapFragment(frag, sh, fw, block, notes, err)) { errorMessage_ = tag + err; return false; }

    // ⑤ 옮긴 대응표(덱 번호) — 넣은 블록을 다시 읽어 파트마다 스스로 대조한다(coord_sha 가 검증 관문이다 — Q12)
    fragment::Map rebased = m;
    auto shiftRange = [](fragment::Range& r, long long d) { if (r.used) { r.lo += d; r.hi += d; } };
    shiftRange(rebased.node, sh.node);
    shiftRange(rebased.elem, sh.elem);
    shiftRange(rebased.pid, sh.pid);
    for (auto& p : rebased.parts) {
        p.pid += sh.pid;
        p.nodeStart += sh.node;
        p.elemStart += sh.elem;
    }
    {
        namespace fs = std::filesystem;
        std::error_code ec;
        const fs::path tmp = fs::temp_directory_path(ec) /
                             ("koorm_merge_" + std::to_string(std::hash<std::string>{}(op.fragment + block.substr(0, 256))) + ".k");
        {
            std::ofstream t(tmp, std::ios::binary);
            t << (fw == 10 ? "*KEYWORD I10=Y\n" : "*KEYWORD\n") << block << "*END\n";
        }
        std::vector<std::string> again;
        try {
            KFileReader reader;
            again = fragment::checkParts(rebased, reader.readFile(tmp.string()));
        } catch (const std::exception& e) {
            again.push_back(std::string("넣을 블록을 다시 읽지 못했다: ") + e.what());
        }
        fs::remove(tmp, ec);
        if (!again.empty()) {
            errorMessage_ = tag + "옮긴 블록이 조각과 다르다(" + std::to_string(again.size()) + "건) — 넣지 않았다";
            for (const auto& a : again) errorMessage_ += "\n  " + a;
            return false;
        }
    }

    // ⑥ 넣는다 — `*END` 앞(다른 op 이 덧붙이는 블록과 같은 자리). 쓰기 뒤 검증이 이 블록의 파트도 대조한다
    auto span = [](const fragment::Range& a, const fragment::Range& b) {
        if (!a.used) return std::string("없음");
        return std::to_string(a.lo) + "~" + std::to_string(a.hi) + " → " + std::to_string(b.lo) + "~" + std::to_string(b.hi);
    };
    const std::string moves = "절점 " + span(m.node, rebased.node) + " · 요소 " + span(m.elem, rebased.elem) +
                              " · PID·SECID·MID " + span(m.pid, rebased.pid);
    std::ostringstream head;
    head << "$\n$ === cad_solid_merge_to_deck — StepForge 조각 " << std::filesystem::path(op.fragment).filename().string()
         << " 을 넣었다 ===\n"
         << "$ 번호(조각 → 이 덱) — " << moves << "\n";
    addedKeywordBlocks_.push_back(head.str() + block);
    if (rebased.node.used) maxNodeId_ = std::max<long long>(maxNodeId_, rebased.node.hi);
    if (rebased.elem.used) maxElementId_ = std::max<long long>(maxElementId_, rebased.elem.hi);
    if (rebased.pid.used) {
        maxPartId_ = std::max<long long>(maxPartId_, rebased.pid.hi);
        maxSectionId_ = std::max<long long>(maxSectionId_, rebased.pid.hi);
        maxMaterialId_ = std::max<long long>(maxMaterialId_, rebased.pid.hi);
    }

    infoMessages.push_back(tag + "조각 " + op.fragment + " — 파트 " + std::to_string(m.parts.size()) +
                           " · unit " + m.unit + " · frame " + m.frame + " · 대조 통과(coord_sha " +
                           std::to_string(m.parts.size()) + "/" + std::to_string(m.parts.size()) + ")");
    infoMessages.push_back("  번호(조각 → 이 덱) — " + moves);
    for (size_t k = 0; k < m.parts.size(); ++k) {
        const auto& a = m.parts[k];
        const auto& b = rebased.parts[k];
        infoMessages.push_back("  PID " + std::to_string(a.pid) + " → " + std::to_string(b.pid) + "  " + a.name +
                               "  절점 " + std::to_string(b.nodeStart) + "~" + std::to_string(b.nodeStart + b.nodeCount - 1) +
                               " · 요소 " + std::to_string(b.elemStart) + "~" + std::to_string(b.elemStart + b.elemCount - 1) +
                               "  (" + a.path + ")");
    }
    for (const auto& n : notes) infoMessages.push_back("  [WARN] " + n);
    mergedMaps_.push_back(rebased);
    return true;
}

}  // namespace KooRemapper
