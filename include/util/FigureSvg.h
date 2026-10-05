#pragma once
// 그림(SVG)을 쓰는 자리들이 함께 쓰는 유틸 — 이스케이프·인코딩 판정·범주 색.
//
// 왜 한 자리인가. 그림을 내는 op 이 둘 이상이 되면(단면·자유면) 이스케이프와 색 배정이 **갈린다**
// (StepForge D-236 이 같은 값을 치렀다). 특히 둘은 그냥 편의 함수가 아니라 **실측으로 값을 치른
// 규율**이다.
//   · 파트 제목은 `*PART` 다음 줄의 **자유 텍스트**다 — STEP 라벨과 같은 노출이다.
//   · XML 1.0 은 제어문자를 담지 못해 **이름에 하나만 있어도 SVG 가 통째로 안 읽힌다.**
//   · 한국어 윈도 덱은 **CP949** 가 기본이고, 그 바이트를 UTF-8 선언 SVG 에 쓰면 XML 파싱이
//     실패해 **그림이 죽는다**(실측: "알루미늄 집전체" → `not well-formed`).
//   · 색을 호출마다 새로 배정하면 두 그림을 견줄 수 없다 — **pid 로 고정**한다.
#include <map>
#include <string>
#include <utility>
#include <vector>

#include "core/Mesh.h"

namespace KooRemapper {
namespace figure {

// 문자열이 **유효한 UTF-8** 인가. 파트 제목은 덱 바이트 그대로이고 한국어 윈도 LS-DYNA 덱은
// CP949 가 기본이다 — 그 바이트를 UTF-8 선언 SVG 에 그대로 쓰면 **XML 파싱이 통째로 실패해
// 그림이 죽는다**(실측: 제목 "알루미늄 집전체" 를 CP949 로 넣으니 `not well-formed` 로 안 읽혔다).
// 그래서 먼저 판정한다. 리포에 CP949 표를 싣지 않으므로 변환은 하지 않고, **읽을 수 있는 그림을
// 내고 사실을 말한다** — 원본 바이트는 매니페스트에 16진으로 남겨 복원할 수 있게 한다.
inline bool isUtf8(const std::string& s) {
    size_t i = 0;
    while (i < s.size()) {
        const unsigned char c = static_cast<unsigned char>(s[i]);
        size_t n = 0;
        if (c < 0x80) n = 0;
        else if ((c & 0xE0) == 0xC0) n = 1;
        else if ((c & 0xF0) == 0xE0) n = 2;
        else if ((c & 0xF8) == 0xF0) n = 3;
        else return false;
        if (i + n >= s.size() + (n ? 0 : 1)) { if (n) return false; }
        for (size_t k = 1; k <= n; ++k) {
            if (i + k >= s.size()) return false;
            if ((static_cast<unsigned char>(s[i + k]) & 0xC0) != 0x80) return false;
        }
        i += n + 1;
    }
    return true;
}

inline std::string hexOf(const std::string& s) {
    static const char* H = "0123456789abcdef";
    std::string out;
    out.reserve(s.size() * 2);
    for (char ch : s) {
        const unsigned char u = static_cast<unsigned char>(ch);
        out += H[u >> 4];
        out += H[u & 0xF];
    }
    return out;
}

// 비 ASCII 바이트를 `?` 로 바꾼다 — 읽을 수 있는 그림을 내기 위해서다(그리고 그 사실을 적는다).
inline std::string asciiOnly(const std::string& s) {
    std::string out;
    out.reserve(s.size());
    for (char ch : s) {
        const unsigned char u = static_cast<unsigned char>(ch);
        out += (u < 0x80) ? ch : '?';
    }
    return out;
}

// XML 이스케이프. 파트 제목은 `*PART` 다음 줄의 **자유 텍스트**라 무엇이든 들어 있다 —
// STEP 라벨과 같은 노출이다. 그리고 XML 1.0 은 제어문자를 담지 못해 **이름에 \x01 하나면 SVG 가
// 통째로 안 읽힌다**(StepForge 실측). 그래서 지우지 않고 보이는 기호로 바꾸고, 바꿨다는 사실을
// 매니페스트에 싣는다.
inline std::string xesc(const std::string& s, bool* stripped = nullptr) {
    std::string out;
    out.reserve(s.size() + 16);
    for (char ch : s) {
        const unsigned char u = static_cast<unsigned char>(ch);
        switch (ch) {
            case '&': out += "&amp;";  continue;
            case '<': out += "&lt;";   continue;
            case '>': out += "&gt;";   continue;
            case '"': out += "&quot;"; continue;
            case '\'': out += "&apos;"; continue;
            default: break;
        }
        if (u < 0x20 || u == 0x7F) {
            out += '?';                       // 보이는 자리표시 — 지우면 사라진 줄 모른다
            if (stripped) *stripped = true;
            continue;
        }
        out += ch;
    }
    return out;
}

// ★그릴 수 없는 **2차 솔리드** 파트를 골라낸다 — `(pid, elform)` 목록.
//
// 왜 거절해야 하나(실측 2026-10-05). 리더는 `*ELEMENT_SOLID` 카드 2 에서 **앞 8칸만** 저장하고
// TET4/PENTA6 만 판정한다. 그래서 10절점 사면체(ELFORM 16·17)는 **중간절점 넷이 코너 자리로**
// 들어온 육면체가 된다. 증상이 조용하다 —
//   · 단위 사면체 z=0.2 단면 면적이 **0.12** 로 나온다(참값 0.32). 오류 없이 통과한다.
//   · 자유면이 **6면/삼각형 12개** 로 나온다(TET4 참값 4면/4개).
//   · 게다가 ELFORM 16·17 은 `solidNodesFromElform` 이 모르므로 **중간절점 카드를 먹지 않아**
//     그 줄이 다음 요소의 카드 1 로 읽힌다 — TET10 둘이 **하나로** 읽혔다.
//
// 어느 ELFORM 이 위험한가. 기준은 "**앞 8칸이 육면체 코너 여덟인가**" 다.
//   · 23·24·29 (20·27·64절점 **육면체**) — 코너가 앞 8칸이다. ELFORM 23 은 실측으로
//     단면 면적 1.0(참값 1.0)·자유면 6면/12삼각이 맞게 나왔다. 그래서 거절하지 않는다.
//   · 16·17 (10절점 사면체) · 25·28 (21·40절점 오면체) · 26·27 (15·20절점 사면체) —
//     앞 8칸에 중간절점이 섞인다. **거절한다.**
//   · 그 밖의 값은 1차 요소이므로 손대지 않는다.
//
// 요소가 **실제로 있는** 파트만 센다 — 덱에 선언만 있고 안 쓰는 파트로 거절하면 거짓 거절이다.
inline std::vector<std::pair<int, int>> secondOrderSolidPids(const Mesh& mesh) {
    std::map<int, bool> used;
    for (const auto& e : mesh.getElements()) used[e.second.partId] = true;

    std::vector<std::pair<int, int>> out;
    for (const auto& pe : mesh.getPartSolidElform()) {
        const int ef = pe.second;
        const bool unsafe = (ef == 16 || ef == 17 || ef == 25 || ef == 26 || ef == 27 || ef == 28);
        if (unsafe && used.count(pe.first)) out.push_back(pe);
    }
    return out;
}

// 거절 문구 — 세 그림 op 이 **같은 말**을 해야 한다(갈리면 어느 쪽을 믿을지 알 수 없다).
inline std::string secondOrderSolidWhy(const std::vector<std::pair<int, int>>& bad) {
    std::string pids;
    for (size_t i = 0; i < bad.size() && i < 8; ++i) {
        if (i) pids += ", ";
        pids += "PID " + std::to_string(bad[i].first) + "(ELFORM " + std::to_string(bad[i].second) + ")";
    }
    if (bad.size() > 8) pids += ", ... 총 " + std::to_string(bad.size()) + "개";
    return "**2차 솔리드**를 쓰는 파트가 있다 — " + pids;
}

// 거절한 뒤 무엇을 하라고 할지 — 숫자를 함께 적는다. 그래야 읽는 사람이 **왜** 를 안다.
inline std::vector<std::string> secondOrderSolidAdvice() {
    return {
        "리더는 `*ELEMENT_SOLID` 노드 칸의 **앞 8개만** 저장한다. 10절점 사면체는 중간절점 넷이",
        "  코너 자리(n5..n8)로 들어와 **육면체로 읽힌다.**",
        "실측 — 같은 기하를 `convert type: tet10` 으로 바꾼 덱의 단면 총면적이 **0.19** 다",
        "  (1차 원본 0.665 · 오차 71%). 다각형 수는 둘 다 2개로 같아서 **알아볼 수가 없다.**",
        "10절점 카드를 두 줄로 적은 덱은 중간절점 줄을 다음 요소의 카드 1 로 읽어 **요소가",
        "  사라진다**(실측 TET10 둘 → 하나). `info` 는 '정의되지 않은 카드' 로 그 신호를 준다.",
        "→ **1차 요소 덱으로 그려라.** 20절점 **육면체**(ELFORM 23)는 코너가 앞 8칸이라 그릴 수",
        "  있다 — 실측으로 단면 면적 1.0(참값 1.0)·자유면 6면/12삼각이 맞게 나왔다.",
    };
}

// 색맹 안전 범주 색(Okabe-Ito). **pid 로 고정**한다 — 호출마다 바뀌면 두 그림을 견줄 수 없다.
inline const char* colorFor(int pid) {
    static const char* P[] = {"#0072B2","#E69F00","#009E73","#CC79A7",
                              "#56B4E9","#D55E00","#F0E442","#999999"};
    const int n = 8;
    int k = pid % n;
    if (k < 0) k += n;
    return P[k];
}

}  // namespace figure
}  // namespace KooRemapper
