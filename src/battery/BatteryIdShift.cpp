// battery 덱 글자의 번호를 족마다 옮긴다(BatteryIdShift.h) — battery 쓰개가 내는 키워드마다 번호 칸의 자리를 안다
#include "BatteryIdShift.h"

#include <algorithm>
#include <cctype>
#include <climits>
#include <cstdio>
#include <cstdlib>
#include <sstream>
#include <vector>

// Knowledge graph (lat.md):
//   @lat: [[modules/battery]]

namespace bat {
namespace {

const char* const kFamNames[FAM_COUNT] = {"절점", "요소", "파트", "섹션", "재질", "열 재질", "모래시계", "세트", "접촉", "곡선"};

std::string trimmed(const std::string& s) {
    const size_t a = s.find_first_not_of(" \t\r");
    if (a == std::string::npos) return std::string();
    const size_t b = s.find_last_not_of(" \t\r");
    return s.substr(a, b - a + 1);
}

// 키워드 줄의 첫 토큰(대문자)
std::string keywordOf(const std::string& l) {
    std::string k = l.substr(0, l.find_first_of(" \t\r"));
    for (auto& c : k) c = static_cast<char>(std::toupper(static_cast<unsigned char>(c)));
    return k;
}

bool endsWith(const std::string& s, const char* t) {
    const std::string u(t);
    return s.size() >= u.size() && s.compare(s.size() - u.size(), u.size(), u) == 0;
}

// 칸 폭(열 수)마다 쓸 수 있는 가장 큰 번호 — 8칸(절점 · 요소 줄)은 8자리, 10칸은 int(LS-DYNA 의 번호 상한)
long long capOf(int w) { return w >= 10 ? static_cast<long long>(INT_MAX) : 99999999LL; }

struct Walker {
    std::vector<std::string>& L;
    const IdShift& by;
    ShiftResult& res;
    std::string& err;
    std::string kw;

    bool fail(size_t li, const std::string& why) {
        err = "battery 덱 " + std::to_string(li + 1) + "째 줄(" + kw + ") — " + why;
        return false;
    }
    std::string cell(size_t li, int col, int w) const {
        const std::string& l = L[li];
        if (static_cast<int>(l.size()) <= col) return std::string();
        return l.substr(static_cast<size_t>(col), static_cast<size_t>(w));
    }
    // 정수 칸 — 빈 칸은 0. 정수 꼴이 아니면 false
    bool readInt(size_t li, int col, int w, long long& v, const char* what) {
        const std::string t = trimmed(cell(li, col, w));
        v = 0;
        if (t.empty()) return true;
        const size_t k = (t[0] == '-' || t[0] == '+') ? 1 : 0;
        bool digits = k < t.size();
        for (size_t j = k; j < t.size(); ++j) digits = digits && std::isdigit(static_cast<unsigned char>(t[j]));
        if (!digits) return fail(li, std::string(what) + " 칸 「" + t + "」 을 정수로 읽지 못했다");
        v = std::strtoll(t.c_str(), nullptr, 10);
        return true;
    }
    // 번호 칸 하나를 옮긴다 — 빈 칸 · 0 은 그대로(가리키는 것이 없다), 음수는 뜻이 따로 있어 거절한다.
    // def 면 그 족의 정의 범위에 넣는다(옮기기 전 값)
    bool shift(size_t li, int col, int w, int fam, bool def, const char* what) {
        long long v = 0;
        if (!readInt(li, col, w, v, what)) return false;
        if (v == 0) return true;
        if (v < 0) return fail(li, std::string(what) + " 이 음수(" + std::to_string(v) + ") — 뜻이 따로 있는 칸이라 옮기는 규칙을 모른다");
        if (def) {
            IdRange& r = res.defined[static_cast<size_t>(fam)];
            if (r.hi == 0) r.lo = r.hi = v;
            else { if (v < r.lo) r.lo = v; if (v > r.hi) r.hi = v; }
            res.ids[static_cast<size_t>(fam)].push_back(v);
        }
        const long long d = by[static_cast<size_t>(fam)];
        if (d == 0) return true;
        const long long nv = v + d;
        if (nv < 1 || nv > capOf(w))
            return fail(li, std::string(what) + " " + std::to_string(v) + " 을 " + std::to_string(nv) + " 로 옮기면 " +
                                std::to_string(w) + "칸 번호의 상한(" + std::to_string(capOf(w)) + ")을 넘는다");
        char buf[32];
        std::snprintf(buf, sizeof(buf), "%*lld", w, nv);
        std::string& l = L[li];
        if (static_cast<int>(l.size()) < col + w) l.resize(static_cast<size_t>(col + w), ' ');
        l.replace(static_cast<size_t>(col), static_cast<size_t>(w), buf);
        return true;
    }
    // 뜻을 모르는 번호 칸 — 0(빈 칸)이어야 한다
    bool zero(size_t li, int col, int w, const char* what) {
        long long v = 0;
        if (!readInt(li, col, w, v, what)) return false;
        if (v != 0) return fail(li, std::string(what) + " 이 0 이 아니다(" + std::to_string(v) + ") — 옮기는 규칙을 모르는 칸이다");
        return true;
    }
    // 실수 꼴로 적히는 번호 · 깃발 칸(TGRLC · CMO …) — 수로 읽어 0 이어야 한다
    bool zeroReal(size_t li, int col, int w, const char* what) {
        const std::string t = trimmed(cell(li, col, w));
        if (t.empty()) return true;
        char* end = nullptr;
        const double v = std::strtod(t.c_str(), &end);
        if (end == t.c_str() || *end != '\0') return fail(li, std::string(what) + " 칸 「" + t + "」 을 수로 읽지 못했다");
        if (v != 0.0) return fail(li, std::string(what) + " 이 0 이 아니다(" + t + ") — 옮기는 규칙을 모르는 칸이다");
        return true;
    }
    bool count(size_t li, const std::vector<size_t>& c, size_t lo, size_t hi) {
        if (c.size() < lo || c.size() > hi)
            return fail(li, "데이터 카드 " + std::to_string(c.size()) + "장 — battery 쓰개는 " + std::to_string(lo) +
                                (lo == hi ? "" : "~" + std::to_string(hi)) + "장을 쓴다(꼴을 모른다)");
        return true;
    }

    // 접촉 SSID · MSID 의 족 — STYP 0 세그먼트 세트 · 1 셸 요소 세트 · 2 파트 세트 · 4 절점 세트 · 6 제외 파트 세트 = 세트,
    // 3 = 파트, 5 = 전부(번호를 보지 않는다). 그 밖이면 거절
    bool contactSide(size_t li, int idCol, int typCol, const char* what) {
        long long typ = 0;
        if (!readInt(li, typCol, 10, typ, "STYP")) return false;
        if (typ == 5) return true;
        if (typ == 3) return shift(li, idCol, 10, FAM_PART, false, what);
        if (typ == 0 || typ == 1 || typ == 2 || typ == 4 || typ == 6) return shift(li, idCol, 10, FAM_SET, false, what);
        return fail(li, std::string(what) + " 의 STYP " + std::to_string(typ) + " — 옮기는 규칙을 모른다");
    }

    bool block(size_t kwLine, const std::vector<size_t>& c) {
        const std::string& k = kw;
        const bool title = endsWith(k, "_TITLE");
        const size_t t0 = title ? 1 : 0;   // 제목 줄 다음이 첫 카드
        auto starts = [&](const char* p) { return k.rfind(p, 0) == 0; };

        if (k == "*KEYWORD" || k == "*END") return count(kwLine, c, 0, 0);
        if (k == "*NODE") {
            for (size_t li : c) if (!shift(li, 0, 8, FAM_NODE, true, "NID")) return false;
            return true;
        }
        if (k == "*ELEMENT_SHELL" || k == "*ELEMENT_SOLID" || k == "*ELEMENT_TSHELL") {
            const bool shell = (k == "*ELEMENT_SHELL");
            for (size_t li : c) {
                const size_t n = L[li].size();
                if (shell ? (n < 48 || n > 80) : n < 80)
                    return fail(li, shell ? "셸 요소 줄이 EID PID N1~N4(8칸)가 아니다" : "한 줄 꼴(EID PID N1~N8, 8칸 열)이 아니다");
                if (!shift(li, 0, 8, FAM_ELEM, true, "EID") || !shift(li, 8, 8, FAM_PART, false, "PID")) return false;
                const int nodes = shell ? static_cast<int>((n - 16 + 7) / 8) : 8;
                for (int q = 0; q < nodes && q < 8; ++q)
                    if (!shift(li, 16 + 8 * q, 8, FAM_NODE, false, "절점")) return false;
            }
            return true;
        }
        if (k == "*PART") {
            if (c.size() % 2 != 0) return fail(kwLine, "제목과 카드가 짝이 맞지 않는다");
            for (size_t q = 1; q < c.size(); q += 2) {
                const size_t li = c[q];
                if (!shift(li, 0, 10, FAM_PART, true, "PID") || !shift(li, 10, 10, FAM_SECTION, false, "SECID") ||
                    !shift(li, 20, 10, FAM_MAT, false, "MID") || !zero(li, 30, 10, "EOSID") ||
                    !shift(li, 40, 10, FAM_HOURGLASS, false, "HGID") || !shift(li, 70, 10, FAM_TMAT, false, "TMID"))
                    return false;
            }
            return true;
        }
        if (k == "*SECTION_SHELL") {
            if (c.size() % 2 != 0) return fail(kwLine, "Card 1 · 2 가 짝이 맞지 않는다");
            for (size_t q = 0; q < c.size(); q += 2) {
                long long irid = 0;
                if (!shift(c[q], 0, 10, FAM_SECTION, true, "SECID") || !readInt(c[q], 50, 10, irid, "QR/IRID")) return false;
                if (irid < 0) return fail(c[q], "QR/IRID 가 음수 — 적분 규칙 번호는 옮기는 규칙을 모른다");
                if (!zero(c[q + 1], 70, 10, "EDGSET")) return false;
            }
            return true;
        }
        if (k == "*SECTION_SOLID" || k == "*SECTION_TSHELL") {
            for (size_t li : c) {
                long long elform = 0;
                if (!shift(li, 0, 10, FAM_SECTION, true, "SECID") || !readInt(li, 10, 10, elform, "ELFORM")) return false;
                if (k == "*SECTION_SOLID" && elform >= 101) return fail(li, "사용자 요소(ELFORM ≥ 101)는 카드가 더 있다 — 꼴을 모른다");
                if (k == "*SECTION_TSHELL") {
                    long long qr = 0;
                    if (!zero(li, 60, 10, "ICOMP") || !readInt(li, 50, 10, qr, "QR")) return false;
                    if (qr < 0) return fail(li, "QR 이 음수 — 적분 규칙 번호는 옮기는 규칙을 모른다");
                }
            }
            return true;
        }
        if (k == "*HOURGLASS") {
            for (size_t li : c) if (!shift(li, 0, 10, FAM_HOURGLASS, true, "HGID")) return false;
            return true;
        }
        if (k == "*MAT_THERMAL_ISOTROPIC_TITLE" || k == "*MAT_THERMAL_ISOTROPIC") {
            if (!count(kwLine, c, t0 + 2, t0 + 2)) return false;
            return shift(c[t0], 0, 10, FAM_TMAT, true, "TMID") && zeroReal(c[t0], 20, 10, "TGRLC");
        }
        if (k == "*MAT_ADD_THERMAL_EXPANSION") {
            for (size_t li : c)
                if (!shift(li, 0, 10, FAM_PART, false, "PID") || !shift(li, 10, 10, FAM_CURVE, false, "LCID") ||
                    !shift(li, 30, 10, FAM_CURVE, false, "LCIDY") || !shift(li, 50, 10, FAM_CURVE, false, "LCIDZ"))
                    return false;
            return true;
        }
        if (starts("*MAT_")) {
            std::string base = title ? k.substr(0, k.size() - 6) : k;
            static const char* const kMats[] = {"*MAT_ELASTIC", "*MAT_JOHNSON_COOK", "*MAT_VISCOELASTIC", "*MAT_NULL",
                                                "*MAT_PIECEWISE_LINEAR_PLASTICITY", "*MAT_RIGID"};
            bool known = false;
            for (const char* m : kMats) known = known || base == m;
            if (!known) return fail(kwLine, "battery 쓰개가 내지 않는 재질 키워드다 — 옮기는 규칙을 모른다");
            if (c.size() < t0 + 1) return fail(kwLine, "재질 Card 1 이 없다");
            if (!shift(c[t0], 0, 10, FAM_MAT, true, "MID")) return false;
            if (base == "*MAT_PIECEWISE_LINEAR_PLASTICITY" && c.size() > t0 + 1)
                return shift(c[t0 + 1], 20, 10, FAM_CURVE, false, "LCSS") && shift(c[t0 + 1], 30, 10, FAM_CURVE, false, "LCSR");
            if (base == "*MAT_RIGID") {
                if (c.size() > t0 + 1 && !zeroReal(c[t0 + 1], 0, 10, "CMO")) return false;
                if (c.size() > t0 + 2 && !zeroReal(c[t0 + 2], 0, 10, "LCO/A1")) return false;
            }
            return true;
        }
        if (k == "*SET_NODE_LIST_TITLE" || k == "*SET_NODE_LIST" || k == "*SET_PART_LIST_TITLE" || k == "*SET_PART_LIST") {
            if (c.size() < t0 + 1) return fail(kwLine, "세트 Card 1 이 없다");
            if (!shift(c[t0], 0, 10, FAM_SET, true, "SID")) return false;
            const int fam = starts("*SET_NODE") ? FAM_NODE : FAM_PART;
            for (size_t q = t0 + 1; q < c.size(); ++q)
                for (int f = 0; f < 8; ++f)
                    if (!shift(c[q], 10 * f, 10, fam, false, fam == FAM_NODE ? "절점" : "파트")) return false;
            return true;
        }
        if (k == "*SET_SEGMENT_TITLE" || k == "*SET_SEGMENT") {
            if (c.size() < t0 + 1) return fail(kwLine, "세트 Card 1 이 없다");
            if (!shift(c[t0], 0, 10, FAM_SET, true, "SID")) return false;
            for (size_t q = t0 + 1; q < c.size(); ++q)
                for (int f = 0; f < 4; ++f)
                    if (!shift(c[q], 10 * f, 10, FAM_NODE, false, "절점")) return false;
            return true;
        }
        if (k == "*DEFINE_CURVE_TITLE" || k == "*DEFINE_CURVE") {
            if (c.size() < t0 + 1) return fail(kwLine, "곡선 Card 1 이 없다");
            return shift(c[t0], 0, 10, FAM_CURVE, true, "LCID");
        }
        if (k == "*CONTACT_AUTOMATIC_SINGLE_SURFACE_ID" || k == "*CONTACT_AUTOMATIC_SURFACE_TO_SURFACE_ID" ||
            k == "*CONTACT_TIED_SURFACE_TO_SURFACE_ID") {
            if (!count(kwLine, c, 4, 7)) return false;   // ID · Card 1 · 2 · 3 (+ 선택 Card A · B · C)
            if (!shift(c[0], 0, 10, FAM_CONTACT, true, "CID") || !contactSide(c[1], 0, 20, "SSID") ||
                !contactSide(c[1], 10, 30, "MSID") || !zero(c[1], 40, 10, "SBOXID") || !zero(c[1], 50, 10, "MBOXID"))
                return false;
            if (c.size() > 4) {   // Card A — SOFT SOFSCL LCIDAB MAXPAR SBOPT DEPTH BSORT FRCFRQ
                long long depth = 0, bsort = 0;
                if (!shift(c[4], 20, 10, FAM_CURVE, false, "LCIDAB") || !readInt(c[4], 50, 10, depth, "DEPTH") ||
                    !readInt(c[4], 60, 10, bsort, "BSORT"))
                    return false;
                if (depth < 0 || bsort < 0) return fail(c[4], "DEPTH · BSORT 가 음수(곡선 번호) — 옮기는 규칙을 모른다");
            }
            // Card B(PENMAX THKOPT SHLTHK SNLOG ISYM I2D3D SLDTHK SLDSTF)에는 번호 칸이 없다. ★예전엔 그 21~30열을 LCBCKT(MPP Card 1
            //   의 칸)로 보고 곡선처럼 옮겼다 — 매뉴얼의 Card B 에서 그 칸은 SHLTHK 다(2026-11-08 · 6차 검토 P2)
            if (c.size() > 6) {   // Card C — IGAP IGNORE DPRFAC DTSTIF EDGEK (빈 칸) FLANGL CID_RCF
                const std::string t = trimmed(cell(c[6], 20, 10));
                if (!t.empty()) {
                    char* end = nullptr;
                    const double v = std::strtod(t.c_str(), &end);
                    if (end == t.c_str() || *end != '\0') return fail(c[6], "DPRFAC 칸 「" + t + "」 을 수로 읽지 못했다");
                    if (v >= 1.0 || v <= -1.0)
                        return fail(c[6], "DPRFAC " + t + " 은 세트 · 곡선 번호다(|값| ≥ 1) — 옮기는 규칙을 모른다");
                }
                if (!zero(c[6], 70, 10, "CID_RCF(좌표계)")) return false;
            }
            return true;
        }
        if (k == "*BOUNDARY_SPC_NODE") {
            for (size_t li : c) if (!shift(li, 0, 10, FAM_NODE, false, "NID") || !zero(li, 10, 10, "CID(좌표계)")) return false;
            return true;
        }
        if (k == "*BOUNDARY_SPC_SET") {
            for (size_t li : c) if (!shift(li, 0, 10, FAM_SET, false, "NSID") || !zero(li, 10, 10, "CID(좌표계)")) return false;
            return true;
        }
        if (k == "*BOUNDARY_PRESCRIBED_MOTION_SET") {
            for (size_t li : c) {
                long long dof = 0, vad = 0;
                if (!readInt(li, 10, 10, dof, "DOF") || !readInt(li, 20, 10, vad, "VAD")) return false;
                if (vad == 4 || (dof >= 9 && dof <= 11) || (dof <= -9 && dof >= -11))
                    return fail(li, "VAD 4 · DOF 9~11 은 Card 2 가 붙는다 — 꼴을 모른다");
                if (!shift(li, 0, 10, FAM_SET, false, "NSID") || !shift(li, 30, 10, FAM_CURVE, false, "LCID") ||
                    !zero(li, 50, 10, "VID"))
                    return false;
            }
            return true;
        }
        if (k == "*LOAD_SEGMENT_SET") {
            for (size_t li : c)
                if (!shift(li, 0, 10, FAM_SET, false, "SSID") || !shift(li, 10, 10, FAM_CURVE, false, "LCID") ||
                    !zero(li, 50, 10, "6째 칸") || !zero(li, 60, 10, "7째 칸") || !zero(li, 70, 10, "8째 칸"))
                    return false;
            return true;
        }
        if (k == "*LOAD_THERMAL_VARIABLE") {
            if (c.size() % 2 != 0) return fail(kwLine, "Card 1 · 2 가 짝이 맞지 않는다");
            for (size_t q = 0; q < c.size(); q += 2)
                if (!shift(c[q], 0, 10, FAM_SET, false, "NSID") || !shift(c[q], 10, 10, FAM_SET, false, "NSIDEX") ||
                    !zero(c[q], 20, 10, "BOXID") || !shift(c[q + 1], 20, 10, FAM_CURVE, false, "LCID") ||
                    !shift(c[q + 1], 50, 10, FAM_CURVE, false, "LCIDE") || !shift(c[q + 1], 60, 10, FAM_CURVE, false, "LCIDR") ||
                    !shift(c[q + 1], 70, 10, FAM_CURVE, false, "LCIDEDR"))
                    return false;
            return true;
        }
        if (k == "*AIRBAG_LINEAR_FLUID") {
            if (!count(kwLine, c, 2, 2)) return false;
            if (!shift(c[0], 0, 10, FAM_SET, false, "SID") || !zero(c[0], 20, 10, "RBID")) return false;
            static const char* const kLc[] = {"LCINT", "LCOUTT", "LCOUTP", "LCFIT", "LCBULK", "LCID"};
            for (int f = 0; f < 6; ++f)
                if (!shift(c[1], 20 + 10 * f, 10, FAM_CURVE, false, kLc[f])) return false;
            return true;
        }
        if (k == "*INITIAL_STRESS_SHELL") {
            for (size_t q = 0; q < c.size();) {
                long long nplane = 0, nthick = 0;
                if (!shift(c[q], 0, 10, FAM_ELEM, false, "EID") || !readInt(c[q], 10, 10, nplane, "NPLANE") ||
                    !readInt(c[q], 20, 10, nthick, "NTHICK") || !zero(c[q], 30, 10, "NHISV") || !zero(c[q], 40, 10, "NTENSR") ||
                    !zero(c[q], 50, 10, "LARGE"))
                    return false;
                if (nplane < 1 || nthick < 1) return fail(c[q], "NPLANE · NTHICK 가 1 보다 작다 — 카드 수를 모른다");
                q += 1 + static_cast<size_t>(nplane * nthick);
                if (q > c.size()) return fail(c.back(), "응력 카드가 NPLANE × NTHICK 장보다 적다");
            }
            return true;
        }
        if (k == "*INITIAL_STRAIN_SOLID") {
            for (size_t q = 0; q < c.size();) {
                long long nint = 0;
                if (!shift(c[q], 0, 10, FAM_ELEM, false, "EID") || !readInt(c[q], 10, 10, nint, "NINT") ||
                    !zero(c[q], 20, 10, "LARGE"))
                    return false;
                q += 1 + static_cast<size_t>(nint < 1 ? 1 : nint);
                if (q > c.size()) return fail(c.back(), "변형률 카드가 NINT 장보다 적다");
            }
            return true;
        }
        if (k == "*INCLUDE_DYNAIN") {
            res.includesDynain = true;
            return true;
        }
        // 해석 제어 · 출력 카드 — 번호 칸만 본다(곡선 · 세트를 가리키는 칸)
        if (k == "*CONTROL_TIMESTEP") {
            return count(kwLine, c, 1, 1) && shift(c[0], 50, 10, FAM_CURVE, false, "LCTM");
        }
        if (k == "*CONTROL_SOLID") {
            return count(kwLine, c, 1, 1) && shift(c[0], 40, 10, FAM_SET, false, "PSFAIL");
        }
        if (k == "*CONTROL_SHELL") return count(kwLine, c, 1, 2);   // Card 3(PSSTUPD …)이 붙으면 꼴을 모른다
        if (k == "*CONTROL_THERMAL_TIMESTEP") {
            return count(kwLine, c, 1, 1) && shift(c[0], 70, 10, FAM_CURVE, false, "LCTS");
        }
        if (k == "*CONTROL_THERMAL_SOLVER") {
            return count(kwLine, c, 1, 2) && (c.size() < 2 || zero(c[1], 50, 10, "Card 2 의 6째 칸"));
        }
        if (k == "*CONTROL_DYNAMIC_RELAXATION") return count(kwLine, c, 1, 1);
        if (k == "*DATABASE_BINARY_D3PLOT") {
            return count(kwLine, c, 1, 1) && shift(c[0], 10, 10, FAM_CURVE, false, "LCDT") &&
                   shift(c[0], 40, 10, FAM_SET, false, "PSETID");
        }
        if (k == "*DATABASE_GLSTAT" || k == "*DATABASE_MATSUM" || k == "*DATABASE_RCFORC") {
            return count(kwLine, c, 1, 1) && shift(c[0], 20, 10, FAM_CURVE, false, "LCUR");
        }
        if (k == "*DATABASE_EXTENT_BINARY" || k == "*CONTROL_TERMINATION" || k == "*CONTROL_ENERGY" ||
            k == "*CONTROL_HOURGLASS" || k == "*CONTROL_BULK_VISCOSITY" || k == "*CONTROL_CONTACT" || k == "*CONTROL_SOLUTION")
            return true;   // 번호 칸이 없다
        return fail(kwLine, "battery 쓰개가 내지 않는 키워드다 — 옮기는 규칙을 모르는 카드는 옮기지 않는다");
    }

    bool run() {
        size_t i = 0;
        while (i < L.size()) {
            if (L[i].empty() || L[i][0] != '*') { ++i; continue; }
            kw = keywordOf(L[i]);
            std::vector<size_t> cards;
            size_t j = i + 1;
            for (; j < L.size() && !(!L[j].empty() && L[j][0] == '*'); ++j)
                if (L[j].empty() || L[j][0] != '$') cards.push_back(j);
            if (!block(i, cards)) return false;
            i = j;
        }
        return true;
    }
};

// 줄로 나눠 걷는다 — out 이 없으면(범위만 잴 때) 옮긴 글자를 짓지 않는다
bool walkBatteryIds(const std::string& deck, const IdShift& by, std::string* out, ShiftResult& res, std::string& err) {
    res = ShiftResult{};
    std::vector<std::string> lines;
    {
        std::istringstream in(deck);
        std::string l;
        while (std::getline(in, l)) lines.push_back(l);
    }
    Walker w{lines, by, res, err, std::string()};
    if (!w.run()) return false;
    if (!out) return true;
    std::string o;
    o.reserve(deck.size() + deck.size() / 16);
    for (const auto& l : lines) { o += l; o += '\n'; }
    if (!deck.empty() && deck.back() != '\n' && !o.empty()) o.pop_back();   // 끝 개행 유무를 그대로
    out->swap(o);
    return true;
}

}  // namespace

const char* idFamName(int fam) { return (fam >= 0 && fam < FAM_COUNT) ? kFamNames[fam] : "?"; }

bool shiftBatteryIds(const std::string& deck, const IdShift& by, std::string& out, ShiftResult& res, std::string& err) {
    return walkBatteryIds(deck, by, &out, res, err);
}

bool scanBatteryIds(const std::string& deck, ShiftResult& res, std::string& err) {
    return walkBatteryIds(deck, IdShift{}, nullptr, res, err);
}

IdSpans spansOf(std::vector<long long> ids, IdSpans extra) {
    std::sort(ids.begin(), ids.end());
    ids.erase(std::unique(ids.begin(), ids.end()), ids.end());
    for (size_t a = 0; a < ids.size();) {
        size_t b = a;
        while (b + 1 < ids.size() && ids[b + 1] == ids[b] + 1) ++b;
        extra.emplace_back(ids[a], ids[b]);
        a = b + 1;
    }
    std::sort(extra.begin(), extra.end());
    IdSpans out;
    for (const auto& s : extra) {
        if (s.second < s.first) continue;
        if (!out.empty() && s.first <= out.back().second + 1) out.back().second = std::max(out.back().second, s.second);
        else out.push_back(s);
    }
    return out;
}

long long famCap(int fam) {
    return (fam == FAM_NODE || fam == FAM_ELEM || fam == FAM_PART) ? 99999999LL : static_cast<long long>(INT_MAX);
}

namespace {
// battery 번호를 s 만큼 옮기면 taken 에 드는 첫 번호(옮기기 전 값) — 없으면 0. 둘 다 정렬돼 있어 한 번 훑는다
long long firstHit(const std::vector<long long>& b, const IdSpans& t, long long s) {
    size_t i = 0, j = 0;
    while (i < b.size() && j < t.size()) {
        const long long v = b[i] + s;
        if (v < t[j].first) ++i;
        else if (v > t[j].second) ++j;
        else return b[i];
    }
    return 0;
}
std::string spanText(long long lo, long long hi) {
    return lo == hi ? std::to_string(lo) : std::to_string(lo) + "~" + std::to_string(hi);
}
}  // namespace

bool placeBatteryIds(int fam, const std::vector<long long>& battery, const IdSpans& taken, long long given,
                     const std::string& key, long long& shift, std::string& why) {
    shift = 0;
    if (battery.empty()) return true;
    const long long lo = battery.front(), hi = battery.back(), cap = famCap(fam);
    const std::string name = idFamName(fam);
    if (given > 0) {
        if (hi + given > cap) {
            why = key + " " + std::to_string(given) + " — battery " + name + " " + spanText(lo, hi) + " 이 " +
                  spanText(lo + given, hi + given) + " 가 되어 칸 상한(" + std::to_string(cap) + ")을 넘는다";
            return false;
        }
        const long long h = firstHit(battery, taken, given);
        if (h != 0) {
            why = key + " " + std::to_string(given) + " — battery " + name + " " + std::to_string(h) + " 이 " +
                  std::to_string(h + given) + " 가 되어 기존 모델의 " + name + " " + std::to_string(h + given) +
                  " 과 겹친다 — 겹치지 않는 값을 주거나 0(저절로)으로 두라";
            return false;
        }
        shift = given;
        return true;
    }
    if (firstHit(battery, taken, 0) == 0) return true;   // 겹치지 않는다 — 옮기지 않는다
    const long long top = taken.back().second;
    if (hi + top <= cap) {   // 기존 최대값 위로(예전 규칙)
        shift = top;
        return true;
    }
    // 빈자리 — battery 범위가 통째로 들어가는 가장 낮은 자리(위로만 · 구간 사이와 마지막 구간 뒤)
    const long long width = hi - lo;
    for (size_t k = 0; k < taken.size(); ++k) {
        const long long start = std::max(taken[k].second + 1, lo + 1);
        const long long room = (k + 1 < taken.size()) ? taken[k + 1].first - 1 : cap;
        if (start + width <= std::min(room, cap)) {
            shift = start - lo;
            return true;
        }
    }
    why = "battery " + name + " " + spanText(lo, hi) + " 이 기존 모델의 " + name + " 번호와 겹치는데 놓을 자리가 없다 — 기존 최대값(" +
          std::to_string(top) + ") 위로 옮기면 칸 상한(" + std::to_string(cap) + ")을 넘고, 기존 번호 사이에도 " +
          std::to_string(width + 1) + "칸 너비의 빈자리가 없다";
    return false;
}

}  // namespace bat
