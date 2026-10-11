#pragma once
// LS-DYNA 덱을 **스트리밍으로 훑는** 공용 보조 — 키워드 토큰·카드 칸·`*NODE` 줄·`*SET_NODE` 변종
//
// 왜 한 곳인가 (2026-10-11). 이 지식은 `cleanup-nodes` 안에만 있었고, `extract-parts` 가
// **같은 것을 전부** 필요로 했다(같은 덱을 같은 폭으로 읽어 같은 줄을 가려내야 한다).
// 이 리포는 같은 지식의 사본이 갈려 생긴 결함을 이미 여러 번 치렀다 — 요소 위상 표 여섯 벌
// (매뉴얼 §46) · 카드 칸 읽기(`parser/CardFields.h`) · 요소 카드 줄 수 사다리
// (`elementCardSpan`). 그래서 베끼지 않고 옮겼다.
//
// `CardFields.h` 와 무엇이 다른가 — 그쪽은 **한 줄을 칸으로 자르는 규칙**이고, 여기는
// **덱을 블록으로 걸어가는 규칙**이다(어느 줄이 데이터인가, `*NODE` 줄의 좌표는 어디인가,
// 어느 `*SET_NODE` 변종을 멤버로 읽을 수 있나).
//
// ★여기 담긴 것은 편의 함수가 아니라 **실측으로 값을 치른 규율**이다. 주석을 지우지 말라.
//
// @lat: [[modules/parser]]

#include "parser/CardFields.h"
#include "parser/ElementCardLayout.h"

#include <algorithm>
#include <sstream>
#include <string>
#include <vector>

namespace KooRemapper {
namespace deckscan {

using KooRemapper::cards::fieldsFixed;
using KooRemapper::cards::has;
using KooRemapper::cards::looksReal;
using KooRemapper::cards::toInt;
using KooRemapper::cards::trim;
using KooRemapper::cards::upper;

// ── 키워드 줄 ────────────────────────────────────────────────────────────────

inline std::string keywordToken(const std::string& line) {
    size_t a = line.find_first_not_of(" \t");
    if (a == std::string::npos) return "";
    size_t b = line.find_first_of(" \t\r\n", a);
    return upper(line.substr(a, b == std::string::npos ? std::string::npos : b - a));
}

// 키워드 토큰에서 칸폭 접미사(`%` `+` `-`)를 뗀다 — `*ELEMENT_SOLID%` 도 솔리드다.
inline std::string kwBare(const std::string& tok) {
    std::string t = tok;
    while (!t.empty() && (t.back() == '%' || t.back() == '+' || t.back() == '-')) t.pop_back();
    return t;
}

inline bool isDataLine(const std::string& l) {
    size_t g = l.find_first_not_of(" \t\r\n");
    if (g == std::string::npos) return false;
    return l[g] != '$' && l[g] != '*';
}

// ── 카드 칸 ──────────────────────────────────────────────────────────────────

// 카드 줄을 칸으로 나눈다 — 콤마가 있으면 자유형식, 아니면 **고정폭**.
//
// ⚠ 공백 토큰으로 되돌리는 것은 고정폭 칸 하나에 두 수가 들어 있을 때(= 덱이 실제로 어긋나
// 있을 때)뿐이다. 되돌림을 먼저 하면 요청서 §6 의 사고가 그대로 재현된다 — 절점 ID 8자리가
// 8칸을 꽉 채워 공백이 사라지고, `split()` 이 두 토큰으로 읽어 그 줄을 2줄 포맷으로 오판하며
// **연결성이 통째로 뒤섞인다**. 폭을 아는 자리에서는 폭만 믿는다.
inline std::vector<std::string> cardFields(const std::string& line, int fw) {
    std::string body = line;
    while (!body.empty() && (body.back() == '\r' || body.back() == '\n')) body.pop_back();
    if (body.find(',') != std::string::npos) {
        std::vector<std::string> out;
        std::string tok;
        for (char c : body) {
            if (c == ',') { out.push_back(trim(tok)); tok.clear(); }
            else tok += c;
        }
        out.push_back(trim(tok));
        return out;
    }
    std::vector<std::string> out = fieldsFixed(body, fw);
    bool misaligned = false;
    for (const auto& f : out)
        if (f.find(' ') != std::string::npos || f.find('\t') != std::string::npos) misaligned = true;
    if (!misaligned) return out;
    // 칸이 어긋난 덱 — 여기서만 공백 토큰으로 읽는다
    out.clear();
    std::istringstream iss(body);
    std::string t;
    while (iss >> t) out.push_back(t);
    return out;
}

inline int fieldInt(const std::vector<std::string>& f, size_t i) {
    int v = 0;
    if (i >= f.size()) return 0;
    if (!toInt(f[i], v)) return 0;
    return v;
}

// 우리가 모델링하지 않은 키워드에서 정수를 **최대한 많이** 긁는다 — 8칸·10칸·공백 토큰의
// 합집합이고 실수 표기는 버린다. 과포함은 '남기는' 쪽이라 안전한 방향이다.
//
// ⚠ `*SET_NODE_*` 블록을 여기 보내면 안 된다 — 운영 덱의 '전체 절점' 세트가 모든 절점 ID 를
// 글자 그대로 담고 있어서, 그것을 참조로 세면 고아가 **전부** 가려진다(실측으로 재현했다:
// 13.4M 절점 덱에서 고아 118,568개가 '전부 참조됨' 으로 나온 원인이 이것이다).
inline void harvestInts(const std::string& line, std::vector<int>& out) {
    auto take = [&out](const std::vector<std::string>& f, size_t from) {
        for (size_t q = from; q < f.size(); ++q) {
            if (f[q].empty() || looksReal(f[q])) continue;
            int v = 0;
            if (toInt(f[q], v) && v > 0) out.push_back(v);
        }
    };
    take(fieldsFixed(line, 8), 0);
    take(fieldsFixed(line, 10), 0);
    std::vector<std::string> ws;
    {
        std::string cur;
        for (char c : line) {
            if (c == ',' || c == ' ' || c == '\t' || c == '\r') {
                if (!cur.empty()) { ws.push_back(cur); cur.clear(); }
            } else cur += c;
        }
        if (!cur.empty()) ws.push_back(cur);
    }
    take(ws, 0);
}

// ── 정렬 집합 ────────────────────────────────────────────────────────────────

inline void sortUnique(std::vector<int>& v) {
    std::sort(v.begin(), v.end());
    v.erase(std::unique(v.begin(), v.end()), v.end());
}

inline bool inSorted(const std::vector<int>& v, int x) {
    return std::binary_search(v.begin(), v.end(), x);
}

// ── 경로 ─────────────────────────────────────────────────────────────────────

inline std::string dirOf(const std::string& path) {
    size_t s = path.find_last_of("/\\");
    return s == std::string::npos ? std::string(".") : path.substr(0, s);
}

inline std::string joinPath(const std::string& dir, const std::string& rel) {
    if (rel.empty()) return rel;
    if (rel[0] == '/' || (rel.size() > 1 && rel[1] == ':')) return rel;   // 절대 경로
    if (dir.empty() || dir == ".") return rel;
    return dir + "/" + rel;
}

// ── `*NODE` 줄 ───────────────────────────────────────────────────────────────

// 표준 포맷은 (I8,3F16,2I8), i10 은 (I10,3F16,2I10), long 은 (I20,3F20,2I20) — 정수 칸 폭이
// 바뀌면 실수 칸 폭도 같이 바뀐다(`ElementCardLayout::realFieldWidth`).
//
// ⚠ 고정폭을 **먼저** 본다. 공백 토큰을 먼저 보면 `12345678-1.0000000E+01` 처럼 ID 8자리가
// x 좌표와 붙은 줄에서 한 토큰으로 읽혀 ID 가 통째로 틀린다.
inline bool readNodeLine(const std::string& line, int fw, int& nid, double xyz[3]) {
    std::string body = line;
    while (!body.empty() && (body.back() == '\r' || body.back() == '\n')) body.pop_back();
    const int rw = KooRemapper::realFieldWidth(fw);
    nid = 0;
    xyz[0] = xyz[1] = xyz[2] = 0.0;

    if (body.find(',') == std::string::npos && (int)body.size() >= fw) {
        std::string idf = trim(body.substr(0, (size_t)fw));
        if (toInt(idf, nid) && nid > 0) {
            for (int k = 0; k < 3; ++k) {
                size_t off = (size_t)fw + (size_t)k * (size_t)rw;
                if (off >= body.size()) break;
                std::string c = trim(body.substr(off, (size_t)rw));
                if (c.empty()) continue;
                try { xyz[k] = std::stod(c); } catch (...) { }
            }
            return true;
        }
    }
    // 자유형식(콤마·공백)
    std::vector<std::string> t;
    {
        std::string cur;
        for (char c : body) {
            if (c == ',' || c == ' ' || c == '\t') { if (!cur.empty()) { t.push_back(cur); cur.clear(); } }
            else cur += c;
        }
        if (!cur.empty()) t.push_back(cur);
    }
    if (t.empty() || !toInt(t[0], nid) || nid <= 0) return false;
    for (size_t k = 0; k < 3 && k + 1 < t.size(); ++k) {
        try { xyz[k] = std::stod(t[k + 1]); } catch (...) { }
    }
    return true;
}

// ── `*SET_NODE_*` 변종 ───────────────────────────────────────────────────────

// 멤버를 ID 로 **읽을 수 있는** 변종만 정리(prune) 대상이다.
//   LIST   : `*SET_NODE` · `*SET_NODE_LIST` — 멤버 ID 8개/줄
//   COLUMN : `*SET_NODE_COLUMN` — 한 줄에 NID 하나 + 실수 4개
//   OPAQUE : `_GENERATE`(범위) · `_GENERAL`(옵션 코드) · `_ADD`/`_INTERSECT`(세트 ID)
//            → **정리하지 않고**, 이름하는 절점을 전부 남긴다(범위는 펼친다).
enum class SetKind { LIST, COLUMN, OPAQUE };

inline SetKind classifySetNode(const std::string& kw) {
    if (has(kw, "_GENERATE") || has(kw, "_GENERAL") || has(kw, "_INTERSECT") ||
        has(kw, "_ADD") || has(kw, "_INTERVAL"))
        return SetKind::OPAQUE;
    if (has(kw, "_COLUMN")) return SetKind::COLUMN;
    return SetKind::LIST;
}


}  // namespace deckscan
}  // namespace KooRemapper
