// 덱이 *INCLUDE 로 나뉘어 있나 — ID 발행자가 "못 본 것이 있다" 고 말할 수 있게 하는 공용 스캐너
#pragma once

#include <cctype>
#include <fstream>
#include <string>
#include <vector>

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

}  // namespace include_scan
}  // namespace KooRemapper
