// 덱이 가리키는 세트 ID 가 실제로 정의돼 있나 — 델타 검사가 못 보는 '애초에 없는' 참조를 잡는다
#include "validation/ReferenceIntegrity.h"

#include "parser/CardFields.h"

#include "parser/IncludeScan.h"

#include <algorithm>
#include <cctype>
#include <map>
#include <cstring>
#include <sstream>
#include <set>
#include <string>
#include <vector>

namespace KooRemapper {
// 카드 칸 읽기는 **공용 보조**(`parser/CardFields.h`)를 쓴다 — 여기 사본이 있었고
// `cleanup-nodes` 가 같은 지식을 베껴야 했다. 사본을 늘리지 않는다.
using namespace KooRemapper::cards;   // NOLINT(google-build-using-namespace)

namespace {

// `*CONTACT_*` 의 **카드 자체 손상**을 본다(참조 무결성과는 다른 축이다).
//   ① Card 1 의 SSID/MSID 칸에 실수가 들어 있다 — 정수 칸이다.
//   ② 필수 카드가 모자란다 — 표준 접촉은 Card 1·2·3 이 **필수**다.
// ②는 **표면 대 표면 서명이 확인될 때만** 센다. `*CONTACT_INTERIOR`·`*CONTACT_1D` 처럼
// 카드 구성이 다른 변종을 3장으로 단정하면 오탐이 나고, 오탐이 나면 이 보고를 아무도 안 믿는다.
void contactDamage(const std::vector<std::string>& lines, size_t i, const std::string& kw,
                   ReferenceReport& rep) {
    const bool hasId = (kw.size() >= 3 && kw.compare(kw.size() - 3, 3, "_ID") == 0) || has(kw, "_ID_");
    // ⚠ **`*CONTACT_*` 에는 `_TITLE` 옵션이 없다.** 제목을 붙이는 옵션은 `_ID` 뿐이고, 그 카드는
    // CID 1~10칸 + HEADING 11~80칸이다. `_TITLE` 로 적힌 접촉은 LS-DYNA 가 제목줄을 **데이터
    // 카드로 읽고** 키워드 단계에서 멈춘다 — 실측(2026-10-02, R16.1.1 MPP):
    //   Error 10060 Unable to read line / 10246 improperly formatted data /
    //   10450 in keyword command → Error termination (0 cycles)
    // 그런데 **우리가 그 형식을 만들어 왔다**(`ct_generateContact`) — 그래서 커밋된 예제 덱
    // 17장이 그 상태였다. 고친 뒤 되돌아오지 못하게 여기서 소리 내어 말한다.
    if (has(kw, "_TITLE"))
        rep.damaged.push_back({(int)i + 1, kw,
            "`*CONTACT_*` 에는 _TITLE 옵션이 없습니다 — _ID 로 쓰고 CID(1~10칸)+제목(11~80칸) 카드를 두세요"});
    int skip = (has(kw, "_TITLE") ? 1 : 0) + (hasId ? 1 : 0);
    // ⚠ **빈 줄도 카드다.** Card 2·3 은 필수지만 칸을 전부 기본값으로 두는 접촉이 있어
    // (`*CONTACT_FORCE_TRANSDUCER_PENALTY`) 빈 줄로 적힌다. 건너뛰면 그 덱이 "필수 카드가
    // 1장뿐" 으로 뜬다. 리포의 카드 색인도 같은 규율이다("빈 줄도 카드다").
    std::vector<size_t> data;
    for (size_t j = i + 1; j < lines.size(); ++j) {
        const std::string d = trim(lines[j]);
        if (isComment(d)) continue;
        if (isKeyword(d)) break;
        if (skip > 0) { --skip; continue; }
        data.push_back(j);
    }
    if (data.empty()) { ++rep.notChecked; return; }
    if (hasParameterRef(lines[data[0]])) { ++rep.notChecked; return; }   // &name — 값이 기호다

    // 표면 대 표면 **서명**부터 확인한다 — Card 1 의 3·4번째 칸이 SSTYP/MSTYP 로 읽히는가.
    // 이것을 먼저 보는 이유가 둘이다.
    //   · `*CONTACT_1D`·`*CONTACT_INTERIOR` 처럼 카드 구성이 다른 변종에 3장 규칙을 들이대면
    //     그 덱이 통째로 오탐이 된다.
    //   · `_ID`·`_MPP` 를 선언했는데 그 머리 카드가 **없는** 덱에서는 우리가 한 칸 밀려 Card 2
    //     (실수가 든 줄)를 Card 1 로 보게 된다. 그때 실수 검사를 먼저 하면 그 덱 전부가
    //     "SSID 칸에 실수" 로 뜬다. 서명이 안 맞으면 아무 말도 하지 않는 것이 맞다.
    const auto f1 = fields10(lines[data[0]]);
    int sstyp = 0, mstyp = 0;
    const bool sig = f1.size() >= 4 && toInt(f1[2], sstyp) && toInt(f1[3], mstyp)
                     && sstyp >= 0 && sstyp <= 6 && mstyp >= 0 && mstyp <= 6;
    if (!sig) { ++rep.notChecked; return; }

    static const char* const kName[2] = {"SSID", "MSID"};
    for (size_t c = 0; c < 2 && c < f1.size(); ++c)
        if (looksReal(f1[c]))
            rep.damaged.push_back({(int)data[0] + 1, kw,
                std::string(kName[c]) + " 칸에 실수 " + f1[c] + " 가 들어 있습니다(정수 칸입니다)"});

    if (data.size() < 3)
        rep.damaged.push_back({(int)i + 1, kw,
            "필수 카드가 " + std::to_string(data.size()) + "장뿐입니다 — 표준 접촉은 Card 1·2·3 이 필수입니다"});
}

}  // namespace

ReferenceReport checkSetReferences(const std::vector<std::string>& lines) {
    ReferenceReport rep;

    // ── 1단계: 정의된 세트 ID 를 모은다 ─────────────────────────────────────
    // `*SET_<종류>[_옵션][_TITLE]` 의 **첫 데이터 카드 첫 칸**이 SID 다. `_GENERATE`/`_ADD`/
    // `_COLUMN`/`_GENERAL` 은 멤버 해석만 바꾸고 SID 자리는 같다 — 그래서 정의 수집은 안전하다.
    std::set<int> definedSets;
    // 종류 → (SID → 처음 본 줄). 같은 종류 안에서 SID 가 겹치는지 보려고 둔다.
    std::map<std::string, std::map<int, int>> seenSetIds;
    for (size_t i = 0; i < lines.size(); ++i) {
        std::string t = trim(lines[i]);
        if (!isKeyword(t)) continue;
        std::string kw = upper(t);
        // `*SECTION_*`·`*MAT_*` 도 **같은 종류 안에서 ID 가 유일해야 한다.** 겹치면 LS-DYNA 가
        // 키워드 단계에서 멈춘다. 실측(2026-09-28): `restack` 이 파트가 참조하지 않는 `*SECTION`
        // 을 못 보고 그 번호를 재발행해 SECID 를 겹치게 만들었다(rc=0 이었다).
        //
        // ⚠ 첫 칸이 **구조 MID 가 아닌** `*MAT_` 변종을 빼야 한다. 실측으로 오탐 4장을 냈다 —
        //    `*MAT_THERMAL_*` 의 첫 칸은 **TMID**(열 재질 ID)로 다른 네임스페이스다
        //    (`materials/test_matdb_result.k` 등). `*MAT_ADD_*` 는 첫 칸이 **PID** 이고
        //    `*MAT_NONLOCAL` 도 자기 ID 체계다.
        // ⚠ 한 키워드 아래 정의가 **여러 장** 오므로 첫 카드만 보면 안 된다(매뉴얼 "Card Sets").
        //    그래서 데이터 줄 전체를 훑되, **첫 칸이 정수인 줄만** 후보로 본다.
        const bool matOtherNs = starts(kw, "*MAT_ADD_") || starts(kw, "*MAT_THERMAL_") ||
                                starts(kw, "*MAT_NONLOCAL");
        if (starts(kw, "*SECTION_") || (starts(kw, "*MAT_") && !matOtherNs)) {
            const bool isSec = starts(kw, "*SECTION_");
            std::string ns = isSec ? "SECTION" : "MAT";
            int skip = titleLines(kw);
            // ⚠ 한 키워드 아래 카드 세트가 여러 장이고 **세트 길이 표가 우리에겐 없다.** 그래서
            // 여기서는 **첫 정의만** 본다 — 넘치게 세면 두 번째 카드(두께·물성 줄)의 첫 칸을 ID 로
            // 오해해 오탐이 난다. 놓치는 쪽을 택한다.
            for (size_t j = i + 1; j < lines.size(); ++j) {
                std::string d = trim(lines[j]);
                if (d.empty() || isComment(d)) continue;
                if (isKeyword(d)) break;
                if (skip > 0) { --skip; continue; }
                if (hasParameterRef(lines[j])) break;
                int id = 0;
                if (firstFieldId(lines[j], id) && id > 0 && !has(kw, "_COLLECT")) {
                    auto& slot = seenSetIds[ns][id];
                    if (slot > 0)
                        rep.damaged.push_back({(int)j + 1, "*" + ns,
                            "ID " + std::to_string(id) + " 가 line " + std::to_string(slot) +
                            " 과 겹칩니다 — 같은 종류의 ID 는 유일해야 합니다"});
                    else
                        slot = (int)j + 1;
                }
                break;
            }
            continue;
        }
        if (!starts(kw, "*SET_")) continue;
        int skip = titleLines(kw);
        for (size_t j = i + 1; j < lines.size(); ++j) {
            std::string d = trim(lines[j]);
            if (d.empty() || isComment(d)) continue;
            if (isKeyword(d)) break;
            if (skip > 0) { --skip; continue; }
            auto f = fields10(lines[j]);
            int sid = 0;
            if (!f.empty() && toInt(f[0], sid) && sid > 0) {
                definedSets.insert(sid);
                // **같은 타입 안에서** SID 가 겹치나 — 겹치면 LS-DYNA 가 error termination 한다
                // (`_COLLECT` 면 합법이라 그때는 세지 않는다).
                //
                // ⚠ **타입을 지우고 한 통으로 보면 안 된다.** SID 네임스페이스는 종류별로 갈리므로
                // `*SET_PART 6` 과 `*SET_NODE 6` 의 공존은 **합법**이고, 실사용 덱 1,303장 중
                // **312장(24%)** 이 그렇다(2026-09-27 실측). 한 통으로 보면 넷 중 하나가 오탐이다.
                if (!has(kw, "_COLLECT")) {
                    // `*SET_<종류>[_LIST][_방언][_TITLE]` 에서 **종류**만 남긴다.
                    std::string ns = kw.substr(5);
                    for (const char* suf : {"_TITLE", "_COLLECT", "_GENERATE_INCREMENT",
                                            "_GENERATE", "_GENERAL", "_INTERSECT", "_ADD",
                                            "_COLUMN", "_LIST"}) {
                        const size_t sl = std::strlen(suf);
                        size_t at = ns.find(suf);
                        while (at != std::string::npos) {
                            ns = ns.substr(0, at) + ns.substr(at + sl);
                            at = ns.find(suf);
                        }
                    }
                    auto& slot = seenSetIds[ns][sid];
                    if (slot > 0)
                        rep.damaged.push_back({(int)j + 1, "*SET_" + ns,
                            "SID " + std::to_string(sid) + " 가 line " + std::to_string(slot) +
                            " 과 겹칩니다 — 같은 종류의 세트 ID 는 유일해야 합니다"});
                    else
                        slot = (int)j + 1;
                }
            }
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

        if (contact) contactDamage(lines, i, kw, rep);

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
