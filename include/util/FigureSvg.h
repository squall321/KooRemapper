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

// ★2차(고차) 솔리드의 ELFORM — 16·17(10절점 사면체) · 23·24·29(20·27·64절점 육면체) · 25·26·27·28(오면체·사면체).
inline bool isSecondOrderElform(int ef) { return ef == 16 || ef == 17 || (ef >= 23 && ef <= 29); }

// 리더가 **코너 차례를 아는** 2차 ELFORM — 그 파트는 코너로 그리고 잰다(휜 모서리는 곧게 본다).
//   · 16·17 — 코너는 N1..N4(매뉴얼 Fig 19-31). 리더가 TET4 꼴로 놓는다(2026-10-17 — 그 전에는 앞 8칸을 담아
//     중간절점 넷이 코너 자리로 들어왔고, 단위 사면체 z=0.2 단면 0.12(참값 0.32)·자유면 6면/12삼각(참 4면/4개)이
//     **조용히** 나와 그림 셋이 거절했다).
//   · 23·24·29 — 앞 8칸이 코너다. ELFORM 23 은 실측으로 단면 1.0(참값 1.0)·자유면 6면/12삼각이 맞았다.
inline bool cornersKnownElform(int ef) { return ef == 16 || ef == 17 || ef == 23 || ef == 24 || ef == 29; }

// ★기하를 **믿을 수 없는** 2차 솔리드 파트 — `(pid, elform)` 목록. 세 그림 op 은 거절하고 modelmeta 는 null 로 낸다.
//   · ELFORM 25·26·27·28 — 매뉴얼 본문에 코너 차례가 없다(Remark 2 는 「그림을 보라」뿐 · `*SECTION_SOLID` Remark 16
//     「개발 중」). 짐작한 코너로 그럴듯한 값을 내는 것이 가장 나쁘다.
//   · 절점 칸이 **모자란** 2차 요소가 든 파트 — 매뉴얼 Card 2 는 N1..N10 열 칸 한 장이다. 노드를 8+2 로 쪼갠 덱은 둘째
//     줄을 다음 요소의 Card 1 로 읽어 요소가 사라진다(LS-DYNA 도 그렇게 읽는다 — 실측 TET10 둘 → 하나).
// 요소가 **실제로 있는** 파트만 센다 — 덱에 선언만 있고 안 쓰는 파트로 거절하면 거짓 거절이다.
inline std::vector<std::pair<int, int>> secondOrderSolidPids(const Mesh& mesh) {
    std::map<int, bool> used;
    for (const auto& e : mesh.getElements()) used[e.second.partId] = true;

    std::vector<std::pair<int, int>> out;
    for (const auto& pe : mesh.getPartSolidElform()) {
        const int ef = pe.second;
        if (!isSecondOrderElform(ef) || !used.count(pe.first)) continue;
        const bool incomplete = mesh.getPartIncompleteSolids().count(pe.first) > 0;
        if (!cornersKnownElform(ef) || incomplete) out.push_back(pe);
    }
    return out;
}

// 코너로 그리고 재는 2차 솔리드 파트 — `(pid, elform)`. 거절 목록에 든 파트는 빼고 센다.
inline std::vector<std::pair<int, int>> secondOrderCornerPids(const Mesh& mesh) {
    std::map<int, bool> used;
    for (const auto& e : mesh.getElements()) used[e.second.partId] = true;
    std::vector<std::pair<int, int>> out;
    for (const auto& pe : mesh.getPartSolidElform()) {
        const int ef = pe.second;
        if (!cornersKnownElform(ef) || !used.count(pe.first)) continue;
        if (mesh.getPartIncompleteSolids().count(pe.first)) continue;
        out.push_back(pe);
    }
    return out;
}

// 그 파트를 왜 믿을 수 없나 — 한 마디.
inline std::string secondOrderSolidReason(const Mesh& mesh, int pid, int elform) {
    auto it = mesh.getPartIncompleteSolids().find(pid);
    if (it != mesh.getPartIncompleteSolids().end())
        return "절점 칸이 모자란 2차 요소 " + std::to_string(it->second) + "개";
    (void)elform;
    return "매뉴얼 본문에 코너 차례가 없다";
}

// 거절 문구 — 세 그림 op 이 **같은 말**을 해야 한다(갈리면 어느 쪽을 믿을지 알 수 없다).
inline std::string secondOrderSolidWhy(const std::vector<std::pair<int, int>>& bad, const Mesh& mesh) {
    std::string pids;
    for (size_t i = 0; i < bad.size() && i < 8; ++i) {
        if (i) pids += ", ";
        pids += "PID " + std::to_string(bad[i].first) + "(ELFORM " + std::to_string(bad[i].second) + " — " +
                secondOrderSolidReason(mesh, bad[i].first, bad[i].second) + ")";
    }
    if (bad.size() > 8) pids += ", ... 총 " + std::to_string(bad.size()) + "개";
    return "기하를 믿을 수 없는 **2차 솔리드** 파트가 있다 — " + pids;
}

// 거절한 뒤 무엇을 하라고 할지 — 숫자를 함께 적는다. 그래야 읽는 사람이 **왜** 를 안다.
inline std::vector<std::string> secondOrderSolidAdvice() {
    return {
        "리더는 2차 솔리드의 절점 칸을 **다** 읽고 코너를 제자리에 놓는다 — 10절점 사면체(ELFORM 16·17)와",
        "  20·27·64절점 육면체(23·24·29)는 코너로 그린다(휜 모서리는 곧게 본다).",
        "ELFORM 25·26·27·28(21·40절점 오면체 · 15·20절점 사면체)은 매뉴얼 본문에 코너 차례가 없다",
        "  (「그림을 보라」뿐 · *SECTION_SOLID Remark 16 「개발 중」) — 짐작한 코너로 그리지 않는다.",
        "절점 칸이 모자란 2차 카드는 매뉴얼 꼴이 아니다 — Card 2 는 N1..N10 열 칸 **한 장**이다.",
        "  노드를 8+2 로 쪼갠 덱은 둘째 줄을 다음 요소의 Card 1 로 읽어 **요소가 사라진다**(LS-DYNA 도 그렇게",
        "  읽는다 · 실측 TET10 둘 → 하나). `info` 가 그 파트와 수를 말한다.",
        "→ **1차 요소 덱**이나 표준 꼴(Card 2 열 칸 한 줄)로 다시 내라.",
    };
}

// 코너로 그린다는 알림 — 그림이 휜 모서리를 곧게 보인다는 것을 **말한다**.
inline std::string secondOrderCornerNote(const std::vector<std::pair<int, int>>& ok) {
    std::string pids;
    for (size_t i = 0; i < ok.size() && i < 8; ++i) {
        if (i) pids += ", ";
        pids += "PID " + std::to_string(ok[i].first) + "(ELFORM " + std::to_string(ok[i].second) + ")";
    }
    if (ok.size() > 8) pids += ", ... 총 " + std::to_string(ok.size()) + "개";
    return "2차 솔리드 " + pids + " 는 코너로 그린다 — 중간절점이 휜 모서리는 곧게 보인다";
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
