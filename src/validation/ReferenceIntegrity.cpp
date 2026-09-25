// 덱이 가리키는 세트 ID 가 실제로 정의돼 있나 — 델타 검사가 못 보는 '애초에 없는' 참조를 잡는다
#include "validation/ReferenceIntegrity.h"

#include "parser/IncludeScan.h"

#include <algorithm>
#include <cctype>
#include <set>
#include <string>
#include <vector>

namespace KooRemapper {
namespace {

std::string upper(std::string s) {
    for (auto& c : s) c = (char)std::toupper((unsigned char)c);
    return s;
}

std::string trim(const std::string& s) {
    size_t b = s.find_first_not_of(" \t\r\n");
    if (b == std::string::npos) return "";
    size_t e = s.find_last_not_of(" \t\r\n");
    return s.substr(b, e - b + 1);
}

bool isComment(const std::string& t) { return !t.empty() && t[0] == '$'; }
bool isKeyword(const std::string& t) { return !t.empty() && t[0] == '*'; }

// 카드 줄을 10칸 고정폭으로 자른다. 칸이 공백으로 갈려 있으면 자유형식으로도 읽는다.
// ⚠ 둘 다 보는 이유 — 운영 덱은 칸을 꽉 채우기도 하고(공백 없음) 느슨하게 쓰기도 한다.
std::vector<std::string> fields10(const std::string& line) {
    std::vector<std::string> out;
    for (size_t i = 0; i < line.size(); i += 10) out.push_back(trim(line.substr(i, 10)));
    // 자유형식이 더 그럴듯하면(고정폭 첫 칸이 통째로 숫자가 아닌데 공백 분해는 숫자면) 그쪽을 쓴다.
    std::vector<std::string> ws;
    size_t i = 0;
    while (i < line.size()) {
        while (i < line.size() && std::isspace((unsigned char)line[i])) ++i;
        size_t b = i;
        while (i < line.size() && !std::isspace((unsigned char)line[i])) ++i;
        if (i > b) ws.push_back(line.substr(b, i - b));
    }
    if (!ws.empty() && (out.empty() || out[0].empty())) return ws;
    return out;
}

bool toInt(const std::string& s, int& v) {
    if (s.empty()) return false;
    size_t i = 0;
    if (s[0] == '+' || s[0] == '-') i = 1;
    if (i >= s.size()) return false;
    for (size_t k = i; k < s.size(); ++k)
        if (!std::isdigit((unsigned char)s[k])) return false;
    try { v = std::stoi(s); } catch (...) { return false; }
    return true;
}

bool starts(const std::string& kw, const char* p) { return kw.rfind(p, 0) == 0; }
bool has(const std::string& kw, const char* p) { return kw.find(p) != std::string::npos; }

// `&name` — *PARAMETER 참조가 있는 줄은 값이 기호라 숫자로 읽으면 안 된다.
bool hasParameterRef(const std::string& line) { return line.find('&') != std::string::npos; }

// `*SET_*` 정의의 제목줄 수. `_TITLE` 이면 SID 줄 앞에 제목이 한 줄 더 있다.
int titleLines(const std::string& kw) { return has(kw, "_TITLE") ? 1 : 0; }

}  // namespace

ReferenceReport checkSetReferences(const std::vector<std::string>& lines) {
    ReferenceReport rep;

    // ── 1단계: 정의된 세트 ID 를 모은다 ─────────────────────────────────────
    // `*SET_<종류>[_옵션][_TITLE]` 의 **첫 데이터 카드 첫 칸**이 SID 다. `_GENERATE`/`_ADD`/
    // `_COLUMN`/`_GENERAL` 은 멤버 해석만 바꾸고 SID 자리는 같다 — 그래서 정의 수집은 안전하다.
    std::set<int> definedSets;
    for (size_t i = 0; i < lines.size(); ++i) {
        std::string t = trim(lines[i]);
        if (!isKeyword(t)) continue;
        std::string kw = upper(t);
        if (!starts(kw, "*SET_")) continue;
        int skip = titleLines(kw);
        for (size_t j = i + 1; j < lines.size(); ++j) {
            std::string d = trim(lines[j]);
            if (d.empty() || isComment(d)) continue;
            if (isKeyword(d)) break;
            if (skip > 0) { --skip; continue; }
            auto f = fields10(lines[j]);
            int sid = 0;
            if (!f.empty() && toInt(f[0], sid) && sid > 0) definedSets.insert(sid);
            break;                       // 첫 데이터 카드만 본다
        }
    }

    // `*INCLUDE` — 세트가 그 안에 정의됐을 수 있다. 읽지 않으므로 0건을 단정하면 안 된다.
    //
    // ⚠ 예전 구현은 `rfind("*INCLUDE", 0) == 0` 만 봐서 **`*INCLUDE_PATH` 를 파일로 셌다.**
    // 그것은 탐색 경로일 뿐 카드를 끌어오지 않으므로, `*INCLUDE_PATH` 만 있는 덱에서
    // "안 읽은 인클루드가 있다" 는 거짓 경고가 났다(실측 확인). 공용 스캐너가 그것을 제외한다.
    {
        const auto u = include_scan::scan(lines);
        if (u.count > 0) {
            rep.hasUnreadIncludes = true;
            rep.includeNames = u.names;
        }
    }

    // ── 2단계: 세트를 가리키는 참조를 본다 ──────────────────────────────────
    auto note = [&](size_t li, const std::string& kw, int id) {
        if (id <= 0) return;                       // 0 은 "없음/전체" 의 관례다
        if (definedSets.count(id)) return;
        rep.dangling.push_back({(int)li + 1, kw, "세트", id});
    };

    for (size_t i = 0; i < lines.size(); ++i) {
        std::string t = trim(lines[i]);
        if (!isKeyword(t)) continue;
        const std::string kw = upper(t);

        // 칸 뜻이 확실한 것만 본다. 나머지는 세어만 두고 건드리지 않는다.
        const bool histSet  = starts(kw, "*DATABASE_HISTORY_") && has(kw, "_SET");
        const bool spcSet   = starts(kw, "*BOUNDARY_SPC_SET");
        const bool dampSet  = starts(kw, "*DAMPING_PART_SET");
        const bool loadSet  = starts(kw, "*LOAD_NODE_SET") || starts(kw, "*LOAD_SEGMENT_SET");
        const bool cnrb     = starts(kw, "*CONSTRAINED_NODAL_RIGID_BODY");
        const bool contact  = starts(kw, "*CONTACT_");

        if (!(histSet || spcSet || dampSet || loadSet || cnrb || contact)) continue;

        // 제목줄 건너뛰기. `_TITLE` 은 1줄, `_ID` 도 cid+제목 줄이 1줄 더 있다.
        int skip = (has(kw, "_TITLE") ? 1 : 0) + ((kw.size() >= 3 && kw.compare(kw.size() - 3, 3, "_ID") == 0) ||
                                                  has(kw, "_ID_") ? 1 : 0);
        for (size_t j = i + 1; j < lines.size(); ++j) {
            const std::string raw = lines[j];
            std::string d = trim(raw);
            if (d.empty() || isComment(d)) continue;
            if (isKeyword(d)) break;
            if (skip > 0) { --skip; continue; }
            if (hasParameterRef(raw)) { ++rep.notChecked; break; }   // &name — 기호다

            auto f = fields10(raw);
            int v = 0;
            if (histSet || spcSet || dampSet || loadSet) {
                if (!f.empty() && toInt(f[0], v)) note(j, kw, v); else ++rep.notChecked;
            } else if (cnrb) {
                // PID CID NSID PNODE … — NSID 는 3번째 칸이다
                if (f.size() >= 3 && toInt(f[2], v)) note(j, kw, v); else ++rep.notChecked;
            } else if (contact) {
                // SSID MSID SSTYP MSTYP … — **타입 칸이 세트라고 말할 때만** 본다.
                // ⚠ 타입이 비어 있으면 기본값이 카드마다 달라 단정할 수 없다 — 그때는 검사하지 않는다.
                //    (2=파트세트, 4=노드세트, 0=세그먼트세트가 세트를 가리킨다. 3=파트 ID 는 세트가 아니다)
                int ssid = 0, msid = 0, sstyp = -1, mstyp = -1;
                bool okS = f.size() >= 1 && toInt(f[0], ssid);
                bool okM = f.size() >= 2 && toInt(f[1], msid);
                bool okST = f.size() >= 3 && toInt(f[2], sstyp);
                bool okMT = f.size() >= 4 && toInt(f[3], mstyp);
                auto typeIsSet = [](int ty) { return ty == 0 || ty == 2 || ty == 4; };
                if (okS && okST && typeIsSet(sstyp)) note(j, kw, ssid); else ++rep.notChecked;
                if (okM && okMT && typeIsSet(mstyp)) note(j, kw, msid); else ++rep.notChecked;
            }
            break;                                  // 첫 데이터 카드만 본다
        }
    }

    return rep;
}

}  // namespace KooRemapper
