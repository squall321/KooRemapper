// 덱이 *INCLUDE 로 나뉘어 있나 — ID 발행자가 "못 본 것이 있다" 고 말할 수 있게 하는 공용 스캐너
#pragma once

#include <cctype>
#include <fstream>
#include <string>
#include <vector>

#include "cli/ConsoleOutput.h"

namespace KooRemapper {
namespace include_scan {

// 왜 이 단위가 있나 (2026-09-25, 덱 계약 2차 P0-6):
//
//   이 리포의 ID 발행자는 "이 덱의 최대 ID + 1" 로 새 번호를 낸다. 그런데 리더는 `*INCLUDE`
//   안을 **읽지 않는다**(`KFileReader` 에 INCLUDE 처리가 0건이다). 실사용 낙하시험 덱은 거의
//   언제나 나뉘어 있으므로, 인클루드에 이미 있는 번호를 **다시 발급할 수 있다.**
//   이번 단계의 목표는 번호 정책을 바꾸는 것이 아니라 **못 봤다는 사실을 말하게 하는 것**이다.
//
//   같은 판정이 리포에 이미 셋 있었고 서로 달랐다.
//     · `ModelAssembler.cpp` 의 `rsCountIncludes` — `*INCLUDE_PATH` 를 제외한다(옳다)
//     · `ReferenceIntegrity.cpp` 의 인클루드 루프 — 제외하지 않아 **탐색 경로를 파일로 센다**
//       (`*INCLUDE_PATH` 만 있는 덱에서 "안 읽은 인클루드가 있다" 는 오탐이 실측으로 확인됐다)
//     · `cclip.cpp` 의 스캔 코퍼스 수집 — 역시 제외하지 않는다
//   그래서 판정을 한 자리로 모은다. 헤더 전용인 이유는 줄 훑기 30줄이 전부라 번역 단위를
//   새로 만들 이유가 없고, CMakeLists 를 건드리지 않아도 되기 때문이다.

struct Unread {
    size_t count = 0;                  // 읽지 않은 `*INCLUDE` 카드 수
    size_t firstLine = 0;              // 첫 카드의 0-기반 줄 번호(count>0 일 때만 뜻이 있다)
    std::vector<std::string> names;    // 그 카드가 가리키는 파일 이름(최대 maxNames 개)
    bool truncatedNames = false;       // 이름을 잘랐나
};

// `*INCLUDE` 카드를 센다. **`*INCLUDE_PATH` 는 세지 않는다** — 그것은 탐색 경로일 뿐 카드를
// 끌어오지 않으므로, 세면 "안 읽은 덱이 있다" 는 거짓 경고가 된다.
// 이름은 카드 다음의 첫 비주석·비공백 줄에서 얻는다(LS-DYNA 관례).
inline Unread scan(const std::vector<std::string>& lines, size_t maxNames = 8) {
    Unread out;
    for (size_t i = 0; i < lines.size(); ++i) {
        const std::string& raw = lines[i];
        const size_t g = raw.find_first_not_of(" \t");
        if (g == std::string::npos || raw[g] != '*') continue;
        std::string up = raw.substr(g);
        while (!up.empty() && (up.back() == '\r' || up.back() == ' ' || up.back() == '\t'))
            up.pop_back();
        for (auto& c : up) c = static_cast<char>(std::toupper(static_cast<unsigned char>(c)));
        if (up.rfind("*INCLUDE", 0) != 0) continue;
        if (up.rfind("*INCLUDE_PATH", 0) == 0) continue;   // ⚠ 탐색 경로다 — 세지 않는다
        if (out.count == 0) out.firstLine = i;
        ++out.count;
        // 이름 한 줄
        for (size_t j = i + 1; j < lines.size(); ++j) {
            const std::string& d = lines[j];
            const size_t h = d.find_first_not_of(" \t\r");
            if (h == std::string::npos) continue;          // 빈 줄
            if (d[h] == '$') continue;                     // 주석
            if (d[h] == '*') break;                        // 이름 없이 다음 키워드가 왔다
            std::string nm = d.substr(h);
            while (!nm.empty() && (nm.back() == '\r' || nm.back() == ' ' || nm.back() == '\t'))
                nm.pop_back();
            if (out.names.size() < maxNames) out.names.push_back(nm);
            else out.truncatedNames = true;
            break;
        }
    }
    return out;
}

// 경고 문구. 첫 줄은 `[WARN]` 으로, 둘째 줄은 들여쓴 본문으로 내보내라는 뜻으로 둘을 돌려준다.
//
// `scope` 는 **이 op 이 무엇을 이 덱 안에서만 세었나**다. op 마다 다르다 —
// `cclip` 은 인클루드 한 단계를 실제로 읽으므로 세트·파트는 보지만 노드·요소는 못 보고,
// `cnrb2spring` 은 최대+1 발행자가 아니라 고정 번호대의 **충돌 검사**라 문제의 모양이 다르다.
// 문구를 한 종류로 뭉개면 그 차이가 사라져 읽는 쪽이 잘못된 결론을 낸다.
inline std::vector<std::string> warnLines(const Unread& u, const std::string& scope) {
    if (u.count == 0) return {};
    std::string names;
    for (size_t k = 0; k < u.names.size(); ++k) names += (k ? ", " : "") + u.names[k];
    if (u.truncatedNames) names += ", …";
    std::vector<std::string> out;
    out.push_back("*INCLUDE " + std::to_string(u.count) + "개를 읽지 않았습니다 — " + scope);
    out.push_back("  보지 않은 파일: " + (names.empty() ? std::string("(이름 없음)") : names));
    return out;
}

// 덱을 **줄 벡터로 들고 있지 않은** op 용. `meshfix`·`tetremesh` 는 KFileReader 로 Mesh 만
// 만들고 원문을 보관하지 않는다 — 그때 스캔하려고 전문을 또 읽어 벡터에 담으면 700MB 덱에서
// 메모리가 곱으로 든다. 여기서는 한 줄씩 흘려 읽는다(상수 메모리).
inline Unread scanFile(const std::string& path, size_t maxNames = 8) {
    Unread out;
    std::ifstream fh(path);
    if (!fh.is_open()) return out;
    std::string raw;
    size_t idx = 0;
    bool wantName = false;
    while (std::getline(fh, raw)) {
        const size_t g = raw.find_first_not_of(" \t");
        if (g != std::string::npos && raw[g] == '*') {
            std::string up = raw.substr(g);
            while (!up.empty() && (up.back() == '\r' || up.back() == ' ' || up.back() == '\t'))
                up.pop_back();
            for (auto& c : up) c = static_cast<char>(std::toupper(static_cast<unsigned char>(c)));
            const bool isInc = up.rfind("*INCLUDE", 0) == 0 && up.rfind("*INCLUDE_PATH", 0) != 0;
            if (isInc) {
                if (out.count == 0) out.firstLine = idx;
                ++out.count;
                wantName = true;              // 다음 데이터 줄이 파일 이름이다
            } else {
                wantName = false;             // 이름 없이 다음 키워드가 왔다
            }
        } else if (wantName) {
            const size_t h = raw.find_first_not_of(" \t\r");
            if (h != std::string::npos && raw[h] != '$') {
                std::string nm = raw.substr(h);
                while (!nm.empty() && (nm.back() == '\r' || nm.back() == ' ' || nm.back() == '\t'))
                    nm.pop_back();
                if (out.names.size() < maxNames) out.names.push_back(nm);
                else out.truncatedNames = true;
                wantName = false;
            }
        }
        ++idx;
    }
    return out;
}

// 경고를 콘솔에 낸다 — 자리가 아홉이라 여섯 줄을 베끼면 문구가 갈린다.
//
// ⚠ **콘솔 전용이다.** 덱(`rawLines_`·`addedKeywordBlocks_` 등)에 문자열을 넣으면 출력 바이트가
//   변해 이 단계의 목표('번호 불변')가 '바이트 변경' 으로 바뀐다.
// ⚠ **rc 를 건드리지 않는다.** 하류(플랫폼 워커·pyKooCAE REMAP 스텝)가 rc≠0 이면 체인을 멈춘다.
//   `ConsoleOutput` 의 모든 출력은 stdout 이고 rc 와 무관하다(전수 확인).
inline void warnUnread(const ConsoleOutput& console,
                       const std::vector<std::string>& lines,
                       const std::string& scope) {
    const auto u = scan(lines);
    if (u.count == 0) return;
    const auto msg = warnLines(u, scope);
    console.warning(msg[0]);
    for (size_t k = 1; k < msg.size(); ++k) console.println(msg[k]);
}

// 파일 경로로 스캔하는 판(`scanFile`) — 문구·규율은 `warnUnread` 와 같다.
inline void warnUnreadFile(const ConsoleOutput& console, const std::string& path,
                           const std::string& scope) {
    const auto u = scanFile(path);
    if (u.count == 0) return;
    const auto msg = warnLines(u, scope);
    console.warning(msg[0]);
    for (size_t k = 1; k < msg.size(); ++k) console.println(msg[k]);
}

}  // namespace include_scan
}  // namespace KooRemapper
