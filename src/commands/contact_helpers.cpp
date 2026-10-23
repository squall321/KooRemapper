#include <cstring>
#include "contact_helpers.h"
#include "kw_util.h"
#include "cli/ConsoleOutput.h"
#include "core/Mesh.h"
#include "core/Vector3D.h"
#include <string>
#include <vector>
#include <map>
#include <set>
#include <array>
#include <sstream>
#include <algorithm>
#include <cmath>
#include <unordered_map>

// Knowledge graph (lat.md):
//   @lat: [[modules/commands]]
//   @lat: [[commands/contact]]

using namespace KooRemapper;

static bool ct_has(const std::string& s, const char* sub) { return s.find(sub) != std::string::npos; }
static bool ct_starts(const std::string& s, const char* pre) { return s.rfind(pre, 0) == 0; }

// 형마다 Card 3 뒤에 오는 **필수 카드** — 매뉴얼 Vol_I *CONTACT 「Cards must appear in the exact order listed below」:
//   ID → MPP 1 → (MPP 2) → Card 1 · 2 · 3 → Card 4(형마다) → THRM 1(·2…) → ORFR 1-4 → 선택 카드 A, B, …
// Card 4 가 필요한 형(V66620-66640): AUTOMATIC_…_TIEBREAK · …_TIEBREAK_USER · …_COMPOSITE/LUBRICATION ·
// AUTOMATIC_SINGLE_SURFACE_TIED · …_TIED_WELD · CONSTRAINT_ · DRAWBEAD · ERODING_ · _INTERFERENCE · RIGID_ ·
// TIEBREAK_NODES_ · TIEBREAK_SURFACE_ · …_CONTRACTION_JOINT. 우리가 수를 확정할 수 있는 것은 AUTOMATIC_…_TIEBREAK
// (OPTION 에 따라 4.1a · 4.1b · 4.2b 가 붙는다)와 ERODING(1장)뿐이다 — 나머지는 known=false.
ct_CardSpec ct_cardSpec(const std::string& typeIn) {
    ct_CardSpec sp;
    const std::string t = kw_upper(typeIn);
    const bool tiebreak = ct_has(t, "TIEBREAK");
    if (tiebreak && ct_has(t, "TIEBREAK_USER")) {
        sp.known = false; sp.why = "TIEBREAK_USER 의 Card 4.x 수는 사용자 인자 수에 달려 있다";
    } else if (tiebreak && ct_starts(t, "AUTOMATIC_")) {
        sp.card4 = 1; sp.tiebreakAuto = true; sp.damping = ct_has(t, "_DAMPING");
    } else if (tiebreak) {   // TIEBREAK_NODES_… · TIEBREAK_SURFACE_… — AUTOMATIC 과 Card 4 꼴이 다르다
        sp.known = false; sp.why = "TIEBREAK_NODES/SURFACE 의 Card 4 는 AUTOMATIC_…_TIEBREAK 와 꼴이 다르다";
    } else if (ct_starts(t, "ERODING_")) {
        sp.card4 = 1; sp.eroding = true;
    } else if (ct_has(t, "COMPOSITE") || ct_has(t, "LUBRICATION") || ct_has(t, "TIED_WELD") ||
               ct_starts(t, "AUTOMATIC_SINGLE_SURFACE_TIED") || ct_starts(t, "CONSTRAINT_") ||
               ct_has(t, "DRAWBEAD") || ct_has(t, "INTERFERENCE") || ct_starts(t, "RIGID_") ||
               ct_has(t, "CONTRACTION_JOINT")) {
        sp.known = false; sp.why = "이 형의 Card 4 꼴을 KooRemapper 가 모른다";
    }
    if (ct_has(t, "THERMAL_FRICTION")) {
        sp.known = false;
        sp.why = (sp.why.empty() ? "" : sp.why + " · ") + std::string("THERMAL_FRICTION 의 THRM 2.1 은 THRM 2 입력에 달려 있다");
    } else if (ct_has(t, "THERMAL")) {
        sp.thrm = 1;
    }
    if (ct_has(t, "ORTHO_FRICTION")) sp.orfr = 4;
    return sp;
}

std::vector<ContactDef> ct_parseContacts(const std::vector<std::string>& lines) {
    std::vector<ContactDef> result;
    int idx = 0;
    for (int i = 0; i < (int)lines.size(); ++i) {
        std::string tr = kw_trim(lines[i]);
        if (tr.empty() || tr[0] != '*') continue;
        std::string up = kw_upper(tr);
        if (up.rfind("*CONTACT_", 0) != 0) continue;
        // Skip *CONTACT comment lines
        if (up.size() >= 2 && up[1] == '$') continue;

        ContactDef c;
        c.startLine = i;
        c.fullKeyword = tr;
        c.index = idx++;

        // Extract type: remove "*CONTACT_" prefix, then strip _TITLE/_ID suffix
        std::string typeStr = up.substr(9);  // after "*CONTACT_"
        c.hasTitle = false;
        // Check _TITLE suffix
        {
            size_t pos = typeStr.rfind("_TITLE");
            if (pos != std::string::npos && pos == typeStr.size() - 6) {
                c.hasTitle = true;
                typeStr = typeStr.substr(0, pos);
            }
        }
        // `_MPP`(OPTION5) — `_ID` 처럼 끝에도, 가운데(`_MPP_ORTHO_FRICTION`)에도 온다.
        {
            size_t pos = typeStr.rfind("_MPP");
            if (pos != std::string::npos && pos == typeStr.size() - 4) {
                c.hasMpp = true;
                typeStr = typeStr.substr(0, pos);
            } else if ((pos = typeStr.find("_MPP_")) != std::string::npos) {
                c.hasMpp = true;
                typeStr = typeStr.substr(0, pos) + typeStr.substr(pos + 4);
            }
        }
        // `_ID` 옵션. ⚠ 끝에만 오는 것이 아니다 — 매뉴얼 정규 철자에 `_ID_OFFSET`·`_ID_MPP`
        // 처럼 뒤에 다른 옵션이 더 붙는 형태가 있다. 끝만 보면 그 덱에서 ID 줄을 Card 1 로 읽어
        // 슬레이브/마스터와 마찰계수가 통째로 한 카드씩 밀린다.
        bool hasId = false;
        {
            size_t pos = typeStr.rfind("_ID");
            bool atEnd = (pos != std::string::npos && pos == typeStr.size() - 3);
            size_t mid = typeStr.find("_ID_");
            if (atEnd) {
                hasId = true;
                typeStr = typeStr.substr(0, pos);
            } else if (mid != std::string::npos) {
                hasId = true;
                typeStr = typeStr.substr(0, mid) + typeStr.substr(mid + 3);
            }
        }
        c.hasId = hasId;   // 쓰기 쪽이 이것을 봐야 한다 — 지역 변수로 두면 편집이 줄을 잘못 센다
        c.type = typeStr;

        // Collect data lines until next keyword
        int j = i + 1;
        while (j < (int)lines.size()) {
            std::string jt = kw_trim(lines[j]);
            if (!jt.empty() && jt[0] == '*' && jt[0] != '$') {
                // Check it's really a keyword, not $*comment
                if (jt.size() >= 2 && jt[1] != '$') break;
            }
            ++j;
        }
        c.endLine = j;

        // 카드인 줄 — 주석(`$`)만 건너뛰고 **빈 줄은 카드로 센다**(매뉴얼: 「Optional Cards A … may be blank lines」).
        // ⚠ 예전엔 빈 줄도 건너뛰어 빈 Card B 뒤의 Card C 가 Card B 로 읽히고 그렇게 다시 쓰였다.
        std::vector<int> cardIdx;
        for (int k = i + 1; k < j; ++k) {
            const std::string kt = kw_trim(lines[k]);
            if (!kt.empty() && kt[0] == '$') continue;
            cardIdx.push_back(k);
        }
        size_t q = 0;
        auto next = [&]() -> int { return q < cardIdx.size() ? cardIdx[q++] : -1; };

        // ID 카드(`_ID`) · 제목 줄(`_TITLE` — 접촉에는 없는 옵션이지만 덱에서 만나면 한 줄로 읽는다)
        if (hasId || c.hasTitle) {
            c.idLine = next();
            if (c.idLine >= 0) {
                const std::string& dl = lines[c.idLine];
                const std::string dtr = kw_trim(dl);
                c.title = dtr;   // 되쓰기용 — 줄 전체(CID+제목)
                if (hasId) {
                    // 보고용으로 칸을 가른다 — CID 1~10칸 · 제목 11~80칸. 쉼표가 앞에 있으면 자유 형식이다.
                    const size_t comma = dl.find(',');
                    const bool freeForm = comma != std::string::npos && comma < 10;
                    const std::string cidPart = freeForm ? dl.substr(0, comma) : dl.substr(0, std::min<size_t>(10, dl.size()));
                    const std::string ttlPart = freeForm ? dl.substr(comma + 1) : (dl.size() > 10 ? dl.substr(10) : std::string());
                    try { c.idCid = std::stoi(kw_trim(cidPart)); } catch (...) { c.idCid = 0; }
                    c.idTitle = kw_trim(ttlPart);
                }
            }
        }
        // MPP 1 · MPP 2 — MPP 2 는 첫 칸이 `&` 일 때만이다(V67202 「Otherwise, it is interpreted as Card 1」).
        if (c.hasMpp) {
            const int m1 = next();
            if (m1 >= 0) c.mppLines.push_back(m1);
            if (q < cardIdx.size()) {
                const std::string& l = lines[cardIdx[q]];
                if (!l.empty() && l[0] == '&') c.mppLines.push_back(next());
            }
        }
        for (int k = 0; k < 3; ++k) c.cardLine[k] = next();

        auto num = [](const std::vector<std::string>& toks, size_t k, double& dst) {
            if (k < toks.size()) try { dst = std::stod(toks[k]); } catch (...) {}
        };
        auto inum = [](const std::vector<std::string>& toks, size_t k, int& dst) {
            if (k < toks.size()) try { dst = std::stoi(toks[k]); } catch (...) {}
        };
        if (c.cardLine[0] >= 0) {
            // Card 1: SSID MSID SSTYP MSTYP SBOXID MBOXID SPR MPR
            const auto toks = kw_tok10(lines[c.cardLine[0]]);
            inum(toks, 0, c.ssid);   inum(toks, 1, c.msid);   inum(toks, 2, c.sstyp);  inum(toks, 3, c.mstyp);
            inum(toks, 4, c.sboxid); inum(toks, 5, c.mboxid); inum(toks, 6, c.spr);    inum(toks, 7, c.mpr);
        }
        if (c.cardLine[1] >= 0) {
            // Card 2: FS FD DC VC VDC PENCHK BT DT
            const auto toks = kw_tok10(lines[c.cardLine[1]]);
            num(toks, 0, c.fs);  num(toks, 1, c.fd);  num(toks, 2, c.dc);  num(toks, 3, c.vc);
            num(toks, 4, c.vdc); inum(toks, 5, c.penchk); num(toks, 6, c.bt); num(toks, 7, c.dt);
        }
        if (c.cardLine[2] >= 0) {
            // Card 3: SFSA SFSB SAST SBST SFSAT SFSBT FSF VSF
            const auto toks = kw_tok10(lines[c.cardLine[2]]);
            num(toks, 0, c.sfsa);  num(toks, 1, c.sfsb);  num(toks, 2, c.sast); num(toks, 3, c.sbst);
            num(toks, 4, c.sfsat); num(toks, 5, c.sfsbt); num(toks, 6, c.fsf);  num(toks, 7, c.vsf);
        }

        // Card 4 · THRM · ORFR — 형이 요구하는 필수 카드(선택 카드보다 **앞**). 수를 모르면 선택 카드 자리도 모른다.
        const ct_CardSpec spec = ct_cardSpec(c.type);
        c.layoutKnown = spec.known;
        c.layoutWhy = spec.why;
        int nCard4 = spec.card4;
        if (spec.tiebreakAuto && q < cardIdx.size()) {
            // OPTION 에 따라 카드가 붙는다 — DAMPING 이면서 ±9 · ±11 이면 4.1a, 13 · 14 면 4.1b · 4.2b(V68155-68230)
            const auto toks = kw_tok10(lines[cardIdx[q]]);
            int opt = 0;
            inum(toks, 0, opt);
            if (spec.damping && (opt == 9 || opt == -9 || opt == 11 || opt == -11)) nCard4 += 1;
            if (opt == 13 || opt == 14) nCard4 += 2;
        }
        for (int k = 0; k < nCard4; ++k) { const int ln = next(); if (ln < 0) break; c.card4Lines.push_back(ln); }
        if (!c.card4Lines.empty()) {
            const auto toks = kw_tok10(lines[c.card4Lines[0]]);
            if (spec.tiebreakAuto) {
                // Card 4: OPTION NFLS SFLS PARAM ERATEN ERATES CT2CN CN
                c.hasTiebreak = true;
                inum(toks, 0, c.tbOption); num(toks, 1, c.tbNfls); num(toks, 2, c.tbSfls); num(toks, 3, c.tbParam);
                num(toks, 4, c.tbEraten);  num(toks, 5, c.tbErates); num(toks, 6, c.tbCt2cn);
            } else if (spec.eroding) {
                c.hasEroding = true;
            }
        }
        for (int k = 0; k < spec.thrm; ++k) { const int ln = next(); if (ln < 0) break; c.thrmLines.push_back(ln); }
        if (!c.thrmLines.empty()) {
            // THRM 1: K FRAD H0 LMIN LMAX FTOSA BC_FLG ALGO
            const auto toks = kw_tok10(lines[c.thrmLines[0]]);
            c.hasThermal = true;
            num(toks, 0, c.thK);    num(toks, 1, c.thFrad);  num(toks, 2, c.thH0); num(toks, 3, c.thLmin);
            num(toks, 4, c.thLmax); num(toks, 5, c.thFtosa); inum(toks, 6, c.thBcflag); inum(toks, 7, c.thAlgo);
        }
        for (int k = 0; k < spec.orfr; ++k) { const int ln = next(); if (ln < 0) break; c.orfrLines.push_back(ln); }

        // 선택 카드 A, B, … — 자리를 모르면(필수 카드 수 미확정) 읽지 않는다(Card 4 를 Card A 로 읽으면 안 된다).
        if (c.layoutKnown) {
            int cardNum = 0;
            while (q < cardIdx.size()) {
                const int ln = next();
                c.optLines.push_back(ln);
                const std::string& dl = lines[ln];
                const auto toks = kw_tok10(dl);
                c.optionalCards.push_back(dl);
                switch (cardNum) {
                case 0:   // Card A: SOFT SOFSCL LCIDAB MAXPAR SBOPT DEPTH BSORT FRCFRQ
                    c.hasCardA = true;
                    inum(toks, 0, c.soft);  num(toks, 1, c.sofscl); inum(toks, 2, c.lcidab); num(toks, 3, c.maxpar);
                    inum(toks, 4, c.sbopt); inum(toks, 5, c.depth); inum(toks, 6, c.bsort);  inum(toks, 7, c.frcfrq);
                    break;
                case 1:   // Card B: PENMAX THKOPT SHLTHK SNLOG ISYM I2D3D SLDTHK SLDSTF
                    c.hasCardB = true;
                    num(toks, 0, c.penmax); inum(toks, 1, c.thkopt); inum(toks, 2, c.shlthk); inum(toks, 3, c.snlog);
                    inum(toks, 4, c.isym);  inum(toks, 5, c.i2d3d);  num(toks, 6, c.sldthk);  num(toks, 7, c.sldstf);
                    break;
                case 2:   // Card C: IGAP IGNORE DPRFAC DTSTIF EDGEK (공란) FLANGL CID_RCF
                    // ⚠ 6열은 공란이고 FLANGL 이 7열 · CID_RCF 가 8열이다(PDF 1210쪽 표). 예전엔 6 · 7열로 읽고 써서
                    //   FLANGL 을 잃고 그 값을 CID_RCF 로 읽었다.
                    c.hasCardC = true;
                    inum(toks, 0, c.igap);  inum(toks, 1, c.ignore_); num(toks, 2, c.dprfac); num(toks, 3, c.dtstif);
                    num(toks, 4, c.edgek);  num(toks, 6, c.flangl);   inum(toks, 7, c.cid_rcf);
                    break;
                case 3:   // Card D: Q2TRI DTPCHK SFNBR FNLSCL DNLSCL TCSO TIEDID SHLEDG
                    c.hasCardD = true;
                    inum(toks, 0, c.q2tri); num(toks, 1, c.dtpchk); num(toks, 2, c.sfnbr);  num(toks, 3, c.fnlscl);
                    num(toks, 4, c.dnlscl); inum(toks, 5, c.tcso);  inum(toks, 6, c.tiedid); inum(toks, 7, c.shledg);
                    break;
                case 4:   // Card E: SHAREC CPARM8 IPBACK SRNDE FRICSF ICOR FTORQ REGION
                    c.hasCardE = true;
                    inum(toks, 0, c.sharec); inum(toks, 1, c.cparm8); inum(toks, 2, c.ipback); inum(toks, 3, c.srnde);
                    num(toks, 4, c.fricsf);  inum(toks, 5, c.icor);   inum(toks, 6, c.ftorq);  inum(toks, 7, c.region);
                    break;
                case 5:   // Card F: PSTIFF IGNROFF (공란) FSTOL 2DBINR SSFTYP SWTPR TETFAC
                    c.hasCardF = true;
                    inum(toks, 0, c.pstiff); inum(toks, 1, c.ignroff); num(toks, 3, c.fstol); inum(toks, 4, c.d2binr);
                    inum(toks, 5, c.ssftyp); inum(toks, 6, c.swtpr);   num(toks, 7, c.tetfac);
                    break;
                case 6:   // Card G: (공란) SHLOFF
                    c.hasCardG = true;
                    num(toks, 1, c.shloff);
                    break;
                default:  // Card G 너머 — 원문만 든다
                    break;
                }
                cardNum++;
            }
        }
        result.push_back(c);
        i = j - 1;  // advance outer loop
    }
    return result;
}

// Parse all *SET_* blocks from rawLines
std::vector<SetDef> ct_parseSets(const std::vector<std::string>& lines) {
    std::vector<SetDef> result;
    for (int i = 0; i < (int)lines.size(); ++i) {
        std::string tr = kw_trim(lines[i]);
        if (tr.empty() || tr[0] != '*') continue;
        std::string up = kw_upper(tr);
        if (up.rfind("*SET_", 0) != 0) continue;

        SetDef s;
        s.startLine = i;

        // `*SET_<종류>[_LIST][_방언…][_TITLE]` — 방언을 **버리지 않고 기록한다**.
        //
        // ⚠ 예전에는 `_LIST` 를 찾아 **그 앞만** 남겼다. 그러면 매뉴얼 정규 철자
        //    `*SET_PART_LIST_GENERATE` 에서 방언이 통째로 사라져 `type` 이 "PART" 가 되고,
        //    범위쌍 `1 5` 가 **파트 1 과 5** 로 읽혔다. 그 값을 소비자가 그대로 쓴다
        //    (`resolvePids`·`mm_resolveSide`·`opt_contactInvolvesPid`) — 조용한 오답이다.
        //    실측: `*SET_PART_LIST_GENERATE 7 / 1 5` → `SET_PART 7: 2 entries [1, 5]`, rc=0.
        std::string rest = up.substr(5);  // after "*SET_"
        s.hasTitle = (rest.find("_TITLE") != std::string::npos);
        if (s.hasTitle) rest = rest.substr(0, rest.find("_TITLE"));
        {
            size_t pos = rest.find("_LIST");
            if (pos != std::string::npos) rest = rest.substr(0, pos) + rest.substr(pos + 5);
        }
        // 꼬리에서 아는 방언을 벗긴다. **꼬리에만** 맞추므로 목록 순서는 상관없다
        // (`_GENERATE` 가 `PART_GENERATE_INCREMENT` 의 꼬리에는 안 맞는다 — 돌연변이로 확인).
        // 여러 번 도는 이유는 `_COLLECT` 가 다른 방언과 겹쳐 붙기 때문이다
        // (매뉴얼이 `*SET_PART_LIST_GENERATE_COLLECT` 오류 함정을 언급한다).
        static const char* const kDialects[] = {
            "_GENERATE_INCREMENT", "_GENERATE", "_GENERAL", "_ADD", "_INTERSECT",
            "_COLUMN", "_COLLECT",
            // `*SET_NODE_ADD_ADVANCED` — 떼지 않으면 종류가 "NODE_ADD_ADVANCED" 로 남아 어느 소비자도
            // 노드 세트로 알아보지 못한다. 떼어 두면 종류는 NODE · 멤버는 미확정(정본 해석기가 말한다).
            "_ADVANCED",
        };
        for (bool peeled = true; peeled;) {
            peeled = false;
            for (const char* d : kDialects) {
                const size_t dl = std::strlen(d);
                if (rest.size() > dl && rest.compare(rest.size() - dl, dl, d) == 0) {
                    const std::string name(d + 1);
                    s.dialect = s.dialect.empty() ? name : (name + "_" + s.dialect);
                    rest = rest.substr(0, rest.size() - dl);
                    peeled = true;
                    break;
                }
            }
        }
        s.type = rest;  // "SEGMENT", "NODE", "PART", "SHELL", "SOLID"
        // 멤버가 개체 ID 가 **아닌** 방언 — `_ADD`·`_INTERSECT` 는 세트 ID, `_GENERAL` 은 옵션
        // 코드, `_COLUMN` 은 첫 칸만 ID 고 뒤는 자료다. 뜻을 확정하지 못한다고 말하고 비워 둔다.
        {
            const std::string& dl = s.dialect;
            if (dl.find("ADD") != std::string::npos || dl.find("INTERSECT") != std::string::npos ||
                dl.find("GENERAL") != std::string::npos || dl.find("COLUMN") != std::string::npos)
                s.membersKnown = false;
        }

        // Collect data lines
        int j = i + 1;
        while (j < (int)lines.size()) {
            std::string jt = kw_trim(lines[j]);
            if (!jt.empty() && jt[0] == '*' && !(jt.size() >= 2 && jt[1] == '$')) break;
            ++j;
        }
        s.endLine = j;

        // Parse data
        bool titleRead = !s.hasTitle;
        bool headerRead = false;

        for (int k = i + 1; k < j; ++k) {
            std::string dtr = kw_trim(lines[k]);
            if (dtr.empty() || dtr[0] == '$') continue;

            if (!titleRead) {
                s.title = dtr;
                titleRead = true;
                continue;
            }

            auto toks = kw_tok10(lines[k]);

            if (!headerRead) {
                // Header line: SID [DA1 DA2 DA3 DA4] [SOLVER]
                if (!toks.empty()) try { s.id = std::stoi(toks[0]); } catch(...){}
                if (s.type == "SEGMENT") {
                    if (toks.size() >= 2) try { s.da1 = std::stod(toks[1]); } catch(...){}
                    if (toks.size() >= 3) try { s.da2 = std::stod(toks[2]); } catch(...){}
                    if (toks.size() >= 4) try { s.da3 = std::stod(toks[3]); } catch(...){}
                    if (toks.size() >= 5) try { s.da4 = std::stod(toks[4]); } catch(...){}
                }
                headerRead = true;
                continue;
            }

            // Data lines
            if (!s.membersKnown) {
                // 뜻을 확정하지 못한 방언 — 개체 ID 칸(`ids`·`segments`)에는 넣지 않는다(채우면 소비자가
                // 개체로 쓴다). `_ADD`·`_INTERSECT` 의 멤버는 **세트 ID** 라 `memberSets` 에 따로 들고,
                // 푸는 일은 정본 해석기(`set_members.h`)가 한다. `_GENERAL`·`_COLUMN`·`_ADVANCED` 는 읽지 않는다.
                // ⚠ SEGMENT 보다 **먼저** 걸러야 한다 — 예전엔 SEGMENT 분기가 앞이라 `*SET_SEGMENT_ADD` 의
                //   세트 ID 가 세그먼트의 절점 번호로 읽혔다(재현: 접촉 파트쌍 (1,3) 이 (2,3) 으로 나왔다).
                const std::string& dl = s.dialect;
                if ((dl.find("ADD") != std::string::npos || dl.find("INTERSECT") != std::string::npos) &&
                    dl.find("ADVANCED") == std::string::npos) {
                    for (const auto& t : toks) {
                        if (t.empty()) continue;
                        try {
                            int v = std::stoi(t);
                            if (v != 0) s.memberSets.push_back(v);
                        } catch(...){}
                    }
                }
            } else if (s.type == "SEGMENT") {
                // N1 N2 N3 N4 [A1 A2 A3 A4]
                std::array<int,4> seg = {0,0,0,0};
                for (int f = 0; f < 4 && f < (int)toks.size(); ++f) {
                    try { seg[f] = std::stoi(toks[f]); } catch(...){}
                }
                if (seg[0] != 0) s.segments.push_back(seg);
            } else if (s.dialect == "GENERATE") {
                // Card 2b: B1BEG B1END B2BEG B2END … — 한 줄에 **범위쌍 4개**(Vol_I `*SET`).
                // 펼치지 않고 범위로 들고 있는 이유는 `SetDef::ranges` 주석에 있다.
                for (size_t f = 0; f < toks.size(); f += 2) {
                    int b = 0, e = 0;
                    try { b = std::stoi(toks[f]); } catch(...){ continue; }
                    // END 칸이 비었거나 아예 없으면 홑개다(줄이 홀수 칸으로 끝나기도 한다).
                    if (f + 1 < toks.size()) { try { e = std::stoi(toks[f + 1]); } catch(...){ e = 0; } }
                    if (b <= 0) continue;
                    s.ranges.push_back({b, (e < b ? b : e), 1});
                }
            } else if (s.dialect == "GENERATE_INCREMENT") {
                // Card 2c: BBEG BEND INCR — 한 줄에 범위 하나다.
                int b = 0, e = 0, inc = 1;
                try { b = std::stoi(toks[0]); } catch(...){ continue; }
                if (toks.size() >= 2) try { e = std::stoi(toks[1]); } catch(...){ e = 0; }
                if (toks.size() >= 3) try { inc = std::stoi(toks[2]); } catch(...){ inc = 1; }
                if (inc <= 0) inc = 1;
                if (b <= 0) continue;
                s.ranges.push_back({b, (e < b ? b : e), inc});
            } else {
                // Up to 8 IDs per line
                for (const auto& t : toks) {
                    if (t.empty()) continue;
                    try {
                        int v = std::stoi(t);
                        if (v != 0) s.ids.push_back(v);
                    } catch(...){}
                }
            }
        }
        result.push_back(s);
        i = j - 1;
    }
    return result;
}

// `_GENERATE` 범위를 **덱에 정의된 ID** 로 좁혀 `ids` 를 채운다. 파싱한 직후 한 번 부른다.
//
// ⚠ 이것을 부르지 않으면 `_GENERATE` 세트의 `ids` 는 **빈 채로 남는다.** 그것이 의도다 —
// 범위를 그대로 펼쳐 넘기면 소비자가 없는 파트를 진짜처럼 쓴다(`mm_resolveSide` 는 존재
// 여부를 걸러 주지 않는다). 못 좁히면 닫히는 쪽으로 실패한다.
//
// 지금 좁힐 수 있는 종류는 **PART 와 NODE** 다. 요소 종류(SHELL/SOLID/TSHELL/BEAM)는 ID
// 네임스페이스가 종류별로 갈려 `Mesh` 의 한 통짜 요소 map 으로는 정확히 좁힐 수 없다 —
// 그때는 확정하지 못했다고 말한다(넘겨짚어 펼치는 것보다 낫다).
void ct_resolveSetRanges(std::vector<SetDef>& sets, const KooRemapper::Mesh& mesh) {
    std::vector<int> parts, nodes;
    for (const auto& [pid, p] : mesh.getParts()) { (void)p; parts.push_back(pid); }
    for (const auto& [nid, n] : mesh.getNodes()) { (void)n; nodes.push_back(nid); }

    for (auto& s : sets) {
        if (s.ranges.empty()) continue;
        const std::vector<int>* def = (s.type == "PART") ? &parts
                                    : (s.type == "NODE") ? &nodes : nullptr;
        if (!def) { s.membersKnown = false; continue; }
        for (int id : *def)
            if (ct_setContains(s, id)) s.ids.push_back(id);
        s.rangesResolved = true;
    }
}

// Find max Set ID across all SET_* keywords
int ct_findMaxSetId(const std::vector<SetDef>& sets) {
    int maxId = 0;
    for (const auto& s : sets) if (s.id > maxId) maxId = s.id;
    return maxId;
}

// 덱에 이미 있는 `*CONTACT_*_ID` 카드의 CID 최대값. 새 접촉의 CID 를 그 위로 발행한다 —
// 같은 CID 가 둘이면 LS-DYNA 가 키워드 단계에서 멈춘다(이 리포의 ID 규율: 발행 전에 최대값을 본다).
int ct_findMaxContactId(const std::vector<std::string>& lines) {
    int maxId = 0;
    for (size_t i = 0; i < lines.size(); ++i) {
        const std::string tr = kw_trim(lines[i]);
        if (tr.size() < 9 || tr[0] != '*') continue;
        std::string up = kw_upper(tr);
        if (up.compare(0, 9, "*CONTACT_") != 0) continue;
        const bool hasId = (up.size() >= 3 && up.compare(up.size() - 3, 3, "_ID") == 0)
                           || up.find("_ID_") != std::string::npos;
        if (!hasId) continue;
        // 첫 비주석 데이터 줄의 1~10칸이 CID 다.
        for (size_t j = i + 1; j < lines.size(); ++j) {
            const std::string d = kw_trim(lines[j]);
            if (d.empty() || d[0] == '$') continue;
            if (d[0] == '*') break;
            auto toks = kw_tok10(lines[j]);
            if (!toks.empty()) {
                try { int v = std::stoi(kw_trim(toks[0])); if (v > maxId) maxId = v; }
                catch (...) { /* CID 칸이 숫자가 아니면 건너뛴다 */ }
            }
            break;
        }
    }
    return maxId;
}

// Extract outer surface from solid/shell elements of given PID
// Reuses extractSourceSurface() algorithm
std::vector<std::array<int,4>> ct_extractSurface(
        const KooRemapper::Mesh& mesh, int pid) {
    using namespace KooRemapper;

    // Check for shell elements first
    // (KFileReader stores shells differently — check element types)
    std::vector<std::array<int,4>> faces;

    // Build face count map: sorted key → (count, original winding)
    std::map<std::array<int,4>, std::pair<int, std::array<int,4>>> faceMap;

    bool foundSolid = false;
    for (const auto& [eid, elem] : mesh.getElements()) {
        if (elem.partId != pid) continue;
        foundSolid = true;

        for (int fi : elem.getValidFaceIndices()) {
            auto fn = elem.getFaceNodeIds(fi);
            std::array<int,4> winding = {fn[0], fn[1], fn[2], fn[3]};

            std::array<int,4> key = winding;
            std::sort(key.begin(), key.end());

            auto it = faceMap.find(key);
            if (it == faceMap.end()) {
                faceMap[key] = {1, winding};
            } else {
                it->second.first++;
            }
        }
    }

    if (!foundSolid) {
        // Try shell elements (QUAD4) — TODO: if shells are parsed into elements map
        // For now just return empty; shell handling can be added later
        return faces;
    }

    for (const auto& [key, val] : faceMap) {
        if (val.first == 1) {
            faces.push_back(val.second);
        }
    }
    return faces;
}

// ============================================================
// Module B: Core Detection — Spatial Hash Grid Algorithm
// ============================================================

// ---- B-1. Data structures ----

struct ct_FaceInfo {
    std::array<int, 4> nodeIds;
    Vector3D verts[4];       // cached vertex positions
    Vector3D centroid;
    Vector3D normal;         // unit normal (direction NOT guaranteed outward)
    double area;
    double radius;           // max distance from centroid to any vertex
    int nVerts;              // 3 (tri) or 4 (quad)
    int pid;                 // owning part ID
    int sourceIndex;         // index in original faces vector
};

struct ct_CellKey {
    int ix, iy, iz;
    bool operator==(const ct_CellKey& o) const {
        return ix == o.ix && iy == o.iy && iz == o.iz;
    }
};

struct ct_CellKeyHash {
    size_t operator()(const ct_CellKey& k) const {
        size_t h = size_t(k.ix) * 73856093ULL;
        h ^= size_t(k.iy) * 19349663ULL;
        h ^= size_t(k.iz) * 83492791ULL;
        return h;
    }
};


static ct_CellKey ct_cellKey(const Vector3D& pos, double cellSize) {
    return { (int)std::floor(pos.x / cellSize),
             (int)std::floor(pos.y / cellSize),
             (int)std::floor(pos.z / cellSize) };
}

static std::vector<ct_FaceInfo> ct_buildFaceInfo(
        const std::vector<std::array<int,4>>& faces,
        const KooRemapper::Mesh& mesh,
        int pid) {
    using namespace KooRemapper;
    std::vector<ct_FaceInfo> info;
    info.reserve(faces.size());
    for (int idx = 0; idx < (int)faces.size(); ++idx) {
        ct_FaceInfo fi;
        fi.nodeIds = faces[idx];
        fi.pid = pid;
        fi.sourceIndex = idx;

        // Detect triangle (TET4 degenerate quad)
        bool isTri = (faces[idx][3] == faces[idx][2] ||
                      faces[idx][3] == 0);
        fi.nVerts = isTri ? 3 : 4;

        // Cache vertex positions
        bool valid = true;
        for (int k = 0; k < fi.nVerts; ++k) {
            const auto* nd = mesh.getNode(faces[idx][k]);
            if (!nd) { valid = false; break; }
            fi.verts[k] = nd->position;
        }
        if (!valid) continue;
        if (isTri) fi.verts[3] = fi.verts[2]; // fill 4th slot

        // Centroid
        fi.centroid = Vector3D(0, 0, 0);
        for (int k = 0; k < fi.nVerts; ++k) fi.centroid = fi.centroid + fi.verts[k];
        fi.centroid = fi.centroid * (1.0 / fi.nVerts);

        // Normal
        Vector3D n;
        if (isTri) {
            Vector3D v1 = fi.verts[1] - fi.verts[0];
            Vector3D v2 = fi.verts[2] - fi.verts[0];
            n = v1.cross(v2);
        } else {
            Vector3D d1 = fi.verts[2] - fi.verts[0];
            Vector3D d2 = fi.verts[3] - fi.verts[1];
            n = d1.cross(d2);
        }
        fi.area = n.magnitude() * 0.5;
        if (fi.area < 1e-20) continue; // skip degenerate face
        fi.normal = n.normalized();

        // Radius: max distance from centroid to any vertex
        fi.radius = 0;
        for (int k = 0; k < fi.nVerts; ++k) {
            double r = fi.verts[k].distanceTo(fi.centroid);
            if (r > fi.radius) fi.radius = r;
        }

        info.push_back(fi);
    }
    return info;
}

static double ct_averageFaceSize(const std::vector<ct_FaceInfo>& faces) {
    if (faces.empty()) return 1.0;
    double sum = 0;
    for (const auto& f : faces) sum += std::sqrt(f.area);
    return sum / faces.size();
}

// Insert face into all grid cells its AABB overlaps
static void ct_insertFaceToGrid(
        std::unordered_map<ct_CellKey, std::vector<int>, ct_CellKeyHash>& grid,
        const ct_FaceInfo& fi, int idx, double cellSize) {
    // Compute AABB of face vertices
    double minX = fi.verts[0].x, maxX = fi.verts[0].x;
    double minY = fi.verts[0].y, maxY = fi.verts[0].y;
    double minZ = fi.verts[0].z, maxZ = fi.verts[0].z;
    for (int k = 1; k < fi.nVerts; ++k) {
        if (fi.verts[k].x < minX) minX = fi.verts[k].x;
        if (fi.verts[k].x > maxX) maxX = fi.verts[k].x;
        if (fi.verts[k].y < minY) minY = fi.verts[k].y;
        if (fi.verts[k].y > maxY) maxY = fi.verts[k].y;
        if (fi.verts[k].z < minZ) minZ = fi.verts[k].z;
        if (fi.verts[k].z > maxZ) maxZ = fi.verts[k].z;
    }
    int ixMin = (int)std::floor(minX / cellSize);
    int ixMax = (int)std::floor(maxX / cellSize);
    int iyMin = (int)std::floor(minY / cellSize);
    int iyMax = (int)std::floor(maxY / cellSize);
    int izMin = (int)std::floor(minZ / cellSize);
    int izMax = (int)std::floor(maxZ / cellSize);
    for (int ix = ixMin; ix <= ixMax; ++ix)
        for (int iy = iyMin; iy <= iyMax; ++iy)
            for (int iz = izMin; iz <= izMax; ++iz)
                grid[{ix, iy, iz}].push_back(idx);
}

// ---- B-4. Narrow phase check (4-stage) ----

static bool ct_narrowPhaseCheck(
        const ct_FaceInfo& fA, const ct_FaceInfo& fB,
        double gapTol, double cosThresh, double& gapOut) {

    // Stage 1: centroid distance pre-filter
    double centDist = fA.centroid.distanceTo(fB.centroid);
    if (centDist > fA.radius + fB.radius + gapTol) return false;

    // Stage 2: normal parallelism (direction-agnostic via |dot|)
    double absDot = std::abs(fA.normal.dot(fB.normal));
    if (absDot < cosThresh) return false;

    // Stage 3: vertex-to-plane projection (bilateral)
    // Check A's vertices against B's plane, and vice versa
    double minGap = std::numeric_limits<double>::max();

    // A → B plane
    for (int k = 0; k < fA.nVerts; ++k) {
        Vector3D diff = fA.verts[k] - fB.centroid;
        double gap_k = std::abs(diff.dot(fB.normal));
        // Check projected point is within face B's extent
        Vector3D projPt = fA.verts[k] - fB.normal * diff.dot(fB.normal);
        double projDist = projPt.distanceTo(fB.centroid);
        if (projDist < fB.radius + gapTol) {
            if (gap_k < minGap) minGap = gap_k;
        }
    }
    // B → A plane
    for (int k = 0; k < fB.nVerts; ++k) {
        Vector3D diff = fB.verts[k] - fA.centroid;
        double gap_k = std::abs(diff.dot(fA.normal));
        Vector3D projPt = fB.verts[k] - fA.normal * diff.dot(fA.normal);
        double projDist = projPt.distanceTo(fA.centroid);
        if (projDist < fA.radius + gapTol) {
            if (gap_k < minGap) minGap = gap_k;
        }
    }

    if (minGap > gapTol) return false;
    gapOut = minGap;
    return true;
}

// ---- B-5. Single pair detection ----

std::vector<ct_ContactPair> ct_detectContacting(
        const std::vector<std::array<int,4>>& facesA,
        const std::vector<std::array<int,4>>& facesB,
        const KooRemapper::Mesh& mesh,
        int pidA, int pidB,
        double gapTolerance,
        double normalAngleDeg) {

    auto infoA = ct_buildFaceInfo(facesA, mesh, pidA);
    auto infoB = ct_buildFaceInfo(facesB, mesh, pidB);
    if (infoA.empty() || infoB.empty()) return {};

    double avgSize = (ct_averageFaceSize(infoA) + ct_averageFaceSize(infoB)) * 0.5;
    double cellSize = std::max(avgSize, gapTolerance * 2.0);
    cellSize = std::max(cellSize, 1e-10);
    double cosThresh = std::cos(normalAngleDeg * 3.14159265358979323846 / 180.0);

    // Build grid from B (master)
    std::unordered_map<ct_CellKey, std::vector<int>, ct_CellKeyHash> grid;
    for (int j = 0; j < (int)infoB.size(); ++j)
        ct_insertFaceToGrid(grid, infoB[j], j, cellSize);

    // Query with A (slave) — collect candidates with dedup
    std::set<std::pair<int,int>> candidates;
    for (int i = 0; i < (int)infoA.size(); ++i) {
        // AABB cell range for slave face
        double minX = infoA[i].verts[0].x, maxX = minX;
        double minY = infoA[i].verts[0].y, maxY = minY;
        double minZ = infoA[i].verts[0].z, maxZ = minZ;
        for (int k = 1; k < infoA[i].nVerts; ++k) {
            if (infoA[i].verts[k].x < minX) minX = infoA[i].verts[k].x;
            if (infoA[i].verts[k].x > maxX) maxX = infoA[i].verts[k].x;
            if (infoA[i].verts[k].y < minY) minY = infoA[i].verts[k].y;
            if (infoA[i].verts[k].y > maxY) maxY = infoA[i].verts[k].y;
            if (infoA[i].verts[k].z < minZ) minZ = infoA[i].verts[k].z;
            if (infoA[i].verts[k].z > maxZ) maxZ = infoA[i].verts[k].z;
        }
        // Expand by 1 cell margin for tolerance
        int ixMin = (int)std::floor(minX / cellSize) - 1;
        int ixMax = (int)std::floor(maxX / cellSize) + 1;
        int iyMin = (int)std::floor(minY / cellSize) - 1;
        int iyMax = (int)std::floor(maxY / cellSize) + 1;
        int izMin = (int)std::floor(minZ / cellSize) - 1;
        int izMax = (int)std::floor(maxZ / cellSize) + 1;
        for (int ix = ixMin; ix <= ixMax; ++ix)
            for (int iy = iyMin; iy <= iyMax; ++iy)
                for (int iz = izMin; iz <= izMax; ++iz) {
                    auto it = grid.find({ix, iy, iz});
                    if (it == grid.end()) continue;
                    for (int j : it->second)
                        candidates.insert({i, j});
                }
    }

    // Narrow phase
    // faceA/faceB stored as sourceIndex (original index in facesA/facesB),
    // NOT the infoA/infoB index — callers use these to index back into facesA/facesB.
    std::vector<ct_ContactPair> results;
    for (const auto& [i, j] : candidates) {
        double gap;
        if (ct_narrowPhaseCheck(infoA[i], infoB[j], gapTolerance, cosThresh, gap)) {
            results.push_back({pidA, pidB, infoA[i].sourceIndex, infoB[j].sourceIndex, gap});
        }
    }
    return results;
}

// ---- B-6. All-pairs detection (Global Grid) ----

std::vector<ct_PairResult> ct_detectAllPairs(
        const std::map<int, std::vector<std::array<int,4>>>& surfacesByPid,
        const std::vector<int>& targetPids,
        const std::vector<int>& counterPids,
        const KooRemapper::Mesh& mesh,
        double gapTolerance,
        double normalAngleDeg) {

    // Build face info for all PIDs, tagged with PID
    std::vector<ct_FaceInfo> allFaces;
    // Track per-PID ranges: pid → (startIdx, count)
    std::map<int, std::pair<int,int>> pidRange;

    std::set<int> counterSet(counterPids.begin(), counterPids.end());
    std::set<int> targetSet(targetPids.begin(), targetPids.end());
    // Collect all unique PIDs needed
    std::set<int> allPids;
    allPids.insert(targetPids.begin(), targetPids.end());
    allPids.insert(counterPids.begin(), counterPids.end());

    for (int pid : allPids) {
        auto it = surfacesByPid.find(pid);
        if (it == surfacesByPid.end()) continue;
        int startIdx = (int)allFaces.size();
        auto fi = ct_buildFaceInfo(it->second, mesh, pid);
        allFaces.insert(allFaces.end(), fi.begin(), fi.end());
        pidRange[pid] = {startIdx, (int)fi.size()};
    }
    if (allFaces.empty()) return {};

    double avgSize = ct_averageFaceSize(allFaces);
    double cellSize = std::max(avgSize, gapTolerance * 2.0);
    cellSize = std::max(cellSize, 1e-10);
    double cosThresh = std::cos(normalAngleDeg * 3.14159265358979323846 / 180.0);

    // Insert counter faces into grid
    std::unordered_map<ct_CellKey, std::vector<int>, ct_CellKeyHash> grid;
    for (int pid : counterPids) {
        auto it = pidRange.find(pid);
        if (it == pidRange.end()) continue;
        int start = it->second.first;
        int count = it->second.second;
        for (int i = start; i < start + count; ++i)
            ct_insertFaceToGrid(grid, allFaces[i], i, cellSize);
    }

    // Query with target faces — collect candidates with dedup
    std::set<std::pair<int,int>> candidates;
    for (int pid : targetPids) {
        auto it = pidRange.find(pid);
        if (it == pidRange.end()) continue;
        int start = it->second.first;
        int count = it->second.second;
        for (int i = start; i < start + count; ++i) {
            const auto& fi = allFaces[i];
            double minX = fi.verts[0].x, maxX = minX;
            double minY = fi.verts[0].y, maxY = minY;
            double minZ = fi.verts[0].z, maxZ = minZ;
            for (int k = 1; k < fi.nVerts; ++k) {
                if (fi.verts[k].x < minX) minX = fi.verts[k].x;
                if (fi.verts[k].x > maxX) maxX = fi.verts[k].x;
                if (fi.verts[k].y < minY) minY = fi.verts[k].y;
                if (fi.verts[k].y > maxY) maxY = fi.verts[k].y;
                if (fi.verts[k].z < minZ) minZ = fi.verts[k].z;
                if (fi.verts[k].z > maxZ) maxZ = fi.verts[k].z;
            }
            int ixMin = (int)std::floor(minX / cellSize) - 1;
            int ixMax = (int)std::floor(maxX / cellSize) + 1;
            int iyMin = (int)std::floor(minY / cellSize) - 1;
            int iyMax = (int)std::floor(maxY / cellSize) + 1;
            int izMin = (int)std::floor(minZ / cellSize) - 1;
            int izMax = (int)std::floor(maxZ / cellSize) + 1;
            for (int ix = ixMin; ix <= ixMax; ++ix)
                for (int iy = iyMin; iy <= iyMax; ++iy)
                    for (int iz = izMin; iz <= izMax; ++iz) {
                        auto git = grid.find({ix, iy, iz});
                        if (git == grid.end()) continue;
                        for (int j : git->second) {
                            if (allFaces[j].pid == fi.pid) continue; // skip same PID
                            // Canonical ordering: smaller PID first
                            int a = std::min(i, j), b = std::max(i, j);
                            candidates.insert({a, b});
                        }
                    }
        }
    }

    // Narrow phase + group by PID pair
    std::map<std::pair<int,int>, std::vector<ct_ContactPair>> grouped;
    for (const auto& [a, b] : candidates) {
        double gap;
        if (ct_narrowPhaseCheck(allFaces[a], allFaces[b],
                                gapTolerance, cosThresh, gap)) {
            int pA = std::min(allFaces[a].pid, allFaces[b].pid);
            int pB = std::max(allFaces[a].pid, allFaces[b].pid);
            grouped[{pA, pB}].push_back({pA, pB, a, b, gap});
        }
    }

    // Build results
    std::vector<ct_PairResult> results;
    for (auto& [pidPair, pairs] : grouped) {
        ct_PairResult pr;
        pr.pidA = pidPair.first;
        pr.pidB = pidPair.second;
        pr.pairCount = (int)pairs.size();
        pr.gapMin = std::numeric_limits<double>::max();
        pr.gapMax = 0;
        double gapSum = 0;
        std::set<int> usedA, usedB;
        for (const auto& cp : pairs) {
            if (cp.gap < pr.gapMin) pr.gapMin = cp.gap;
            if (cp.gap > pr.gapMax) pr.gapMax = cp.gap;
            gapSum += cp.gap;
            // Determine which face belongs to which PID
            int idxA = (allFaces[cp.faceA].pid == pr.pidA) ? cp.faceA : cp.faceB;
            int idxB = (allFaces[cp.faceB].pid == pr.pidB) ? cp.faceB : cp.faceA;
            usedA.insert(idxA);
            usedB.insert(idxB);
        }
        pr.gapAvg = pairs.empty() ? 0 : gapSum / pairs.size();
        for (int idx : usedA) pr.contactFacesA.push_back(allFaces[idx].nodeIds);
        for (int idx : usedB) pr.contactFacesB.push_back(allFaces[idx].nodeIds);
        results.push_back(pr);
    }
    return results;
}

// ---- B-7. Merge faces from multiple PIDs (remove internal shared faces) ----

std::vector<std::array<int,4>> ct_mergeFaces(
        const std::vector<std::vector<std::array<int,4>>>& perPidFaces) {
    // Dedup: sorted key → (count, original winding)
    std::map<std::array<int,4>, std::pair<int, std::array<int,4>>> faceMap;
    for (const auto& faces : perPidFaces) {
        for (const auto& f : faces) {
            std::array<int,4> key = f;
            std::sort(key.begin(), key.end());
            auto it = faceMap.find(key);
            if (it == faceMap.end()) {
                faceMap[key] = {1, f};
            } else {
                it->second.first++;
            }
        }
    }
    std::vector<std::array<int,4>> result;
    for (const auto& [key, val] : faceMap) {
        if (val.first == 1) result.push_back(val.second);
    }
    return result;
}

// ============================================================
// Module A: Part Selection (include/exclude/all filtering)
// ============================================================

static bool ct_matchPartName(const std::string& partName,
                              const std::vector<std::string>& keywords) {
    if (keywords.empty()) return false;
    std::string upper = partName;
    std::transform(upper.begin(), upper.end(), upper.begin(),
                   [](unsigned char c) { return (char)std::toupper(c); });
    for (const auto& kw : keywords) {
        std::string kwUp = kw;
        std::transform(kwUp.begin(), kwUp.end(), kwUp.begin(),
                       [](unsigned char c) { return (char)std::toupper(c); });
        if (upper.find(kwUp) != std::string::npos) return true;
    }
    return false;
}


ct_PartSelection ct_selectParts(
        const KooRemapper::Mesh& mesh,
        const std::string& scope,
        const std::vector<std::string>& includeKeys,
        const std::vector<std::string>& excludeKeys) {
    using namespace KooRemapper;
    ct_PartSelection sel;

    // Collect all PIDs, filtering by exclude
    std::vector<std::pair<int, std::string>> allParts;
    for (const auto& [pid, part] : mesh.getParts()) {
        if (!excludeKeys.empty() && ct_matchPartName(part.name, excludeKeys))
            continue;
        allParts.push_back({pid, part.name});
    }

    if (scope == "all") {
        // All non-excluded parts are both target and counter
        for (const auto& [pid, name] : allParts) {
            sel.targetPids.push_back(pid);
            sel.counterPids.push_back(pid);
        }
    } else if (!includeKeys.empty()) {
        // Include-matched parts are targets, rest are counters
        for (const auto& [pid, name] : allParts) {
            if (ct_matchPartName(name, includeKeys)) {
                sel.targetPids.push_back(pid);
            }
            // All non-excluded parts are potential counters
            sel.counterPids.push_back(pid);
        }
    }
    // If neither scope nor include → empty (caller uses explicit PID mode)
    return sel;
}

std::map<int, std::vector<std::array<int,4>>> ct_extractAllSurfaces(
        const KooRemapper::Mesh& mesh,
        const std::vector<int>& pids) {
    std::map<int, std::vector<std::array<int,4>>> result;
    for (int pid : pids) {
        auto faces = ct_extractSurface(mesh, pid);
        if (!faces.empty()) result[pid] = std::move(faces);
    }
    return result;
}

// ============================================================
// Module C: Contact Type Presets
// ============================================================


ct_ContactPreset ct_getPreset(const std::string& contactType) {
    std::string t = contactType;
    std::transform(t.begin(), t.end(), t.begin(),
                   [](unsigned char c) { return (char)std::tolower(c); });

    if (t == "auto" || t == "automatic" || t.empty())
        return {"AUTOMATIC_SURFACE_TO_SURFACE", true};
    if (t == "tied")
        return {"TIED_SURFACE_TO_SURFACE", true};
    if (t == "tied_thermal" || t == "thermal")
        return {"TIED_SURFACE_TO_SURFACE_THERMAL", true};
    if (t == "tiebreak")
        return {"AUTOMATIC_SURFACE_TO_SURFACE_TIEBREAK", true};
    if (t == "mortar")
        return {"AUTOMATIC_SURFACE_TO_SURFACE_MORTAR", true};
    // ⚠ 예전엔 `TIED_SURFACE_TO_SURFACE_MORTAR` 를 냈다 — 매뉴얼에 없는 키워드다(Vol_I 0회). Mortar 묶음 접촉은
    //   `AUTOMATIC_SURFACE_TO_SURFACE_MORTAR_TIED`(V67003)다.
    if (t == "tied_mortar")
        return {"AUTOMATIC_SURFACE_TO_SURFACE_MORTAR_TIED", true};
    if (t == "single")
        return {"AUTOMATIC_SINGLE_SURFACE", false};
    if (t == "eroding")
        return {"ERODING_SURFACE_TO_SURFACE", true};
    if (t == "forming")
        return {"FORMING_SURFACE_TO_SURFACE", true};

    // Custom: use as-is (uppercase)
    std::string upper = contactType;
    std::transform(upper.begin(), upper.end(), upper.begin(),
                   [](unsigned char c) { return (char)std::toupper(c); });
    return {upper, true};
}

// ---- Skip/Subtract helpers ----

static std::array<int,4> ct_segKey(std::array<int,4> f) { std::sort(f.begin(), f.end()); return f; }

ct_SegOwners ct_segmentOwners(const std::map<int, std::vector<std::array<int,4>>>& surfacesByPid) {
    ct_SegOwners owners;
    for (const auto& [pid, faces] : surfacesByPid)
        for (const auto& f : faces) {
            auto& v = owners[ct_segKey(f)];
            if (std::find(v.begin(), v.end(), pid) == v.end()) v.push_back(pid);
        }
    return owners;
}

// 접촉 한쪽(SID · SSTYP)이 덮는 파트들 — 세트는 정본 해석기로(`_ADD`·`_COLLECT` 를 따라간다). 못 풀면 빈 목록 —
// 「이미 묶였다」 를 짐작으로 단정하지 않는다. SET_SEGMENT(SSTYP 0)는 세그먼트를 가진 파트로 푼다(`owners` 가 있을 때).
static std::set<int> ct_sidePids(int sid, int styp, const std::vector<SetDef>& sets, const ct_SegOwners* owners) {
    std::set<int> out;
    if (styp == 3) { out.insert(sid); return out; }
    if (styp == 2) {
        const auto m = ct_setMembers(sets, sid, "PART");
        if (m.resolved) out.insert(m.ids.begin(), m.ids.end());
        return out;
    }
    if (styp == 0 && owners) {
        const auto m = ct_setMembers(sets, sid, "SEGMENT");
        if (!m.resolved) return out;
        for (const auto& g : m.segments) {
            auto it = owners->find(ct_segKey(g));
            if (it != owners->end()) out.insert(it->second.begin(), it->second.end());
        }
    }
    return out;
}

// Check if a PID pair has an existing contact
// mode: "tied" → only TIED contacts, "all" → any contact
bool ct_pairHasExisting(int pidA, int pidB,
        const std::vector<ContactDef>& contacts,
        const std::vector<SetDef>& sets,
        const std::string& mode,
        const ct_SegOwners* owners) {
    for (const auto& ct : contacts) {
        bool typeMatch = false;
        if (mode == "all") {
            typeMatch = true;
        } else if (mode == "tied") {
            typeMatch = (kw_upper(ct.type).find("TIED") != std::string::npos);
        } else {
            continue;
        }
        if (!typeMatch) continue;
        const auto sSet = ct_sidePids(ct.ssid, ct.sstyp, sets, owners);
        const auto mSet = ct_sidePids(ct.msid, ct.mstyp, sets, owners);
        // Check both orderings: (A in slave, B in master) or (A in master, B in slave)
        if ((sSet.count(pidA) && mSet.count(pidB)) || (sSet.count(pidB) && mSet.count(pidA)))
            return true;
    }
    return false;
}

// Get existing tied segments for a PID pair from existing contacts
// Returns {faces of pidA's side, faces of pidB's side} — empty if not found
std::pair<std::vector<std::array<int,4>>, std::vector<std::array<int,4>>>
ct_getExistingTiedSegments(int pidA, int pidB,
        const std::vector<ContactDef>& contacts,
        const std::vector<SetDef>& sets,
        const Mesh& mesh, double tol, double nAngle,
        const ct_SegOwners* owners) {
    std::pair<std::vector<std::array<int,4>>, std::vector<std::array<int,4>>> result;

    for (const auto& ct : contacts) {
        // Only TIED contacts
        if (kw_upper(ct.type).find("TIED") == std::string::npos) continue;

        const auto sSet = ct_sidePids(ct.ssid, ct.sstyp, sets, owners);
        const auto mSet = ct_sidePids(ct.msid, ct.mstyp, sets, owners);
        bool matchForward = (sSet.count(pidA) && mSet.count(pidB));
        bool matchReverse = (sSet.count(pidB) && mSet.count(pidA));
        if (!matchForward && !matchReverse) continue;

        // Found matching tied contact. Get segments.
        if (ct.sstyp == 0 && ct.mstyp == 0) {
            // Already segment-based: 정본 해석기로(`*SET_SEGMENT_ADD` 도 펼친다).
            // ⚠ 슬레이브가 pidB 쪽이면(거꾸로 맞음) 두 쪽을 바꿔 돌려준다 — 예전엔 늘 슬레이브를 pidA 쪽으로 넣었다.
            auto sl = ct_setMembers(sets, ct.ssid, "SEGMENT").segments;
            auto ms = ct_setMembers(sets, ct.msid, "SEGMENT").segments;
            if (!matchForward) std::swap(sl, ms);
            result.first.insert(result.first.end(), sl.begin(), sl.end());
            result.second.insert(result.second.end(), ms.begin(), ms.end());
        } else {
            // Part-based: use detect to find tied segments
            auto facesA = ct_extractSurface(mesh, pidA);
            auto facesB = ct_extractSurface(mesh, pidB);
            if (!facesA.empty() && !facesB.empty()) {
                auto pairs = ct_detectContacting(facesA, facesB, mesh, pidA, pidB, tol, nAngle);
                std::set<int> aIdx, bIdx;
                for (const auto& p : pairs) { aIdx.insert(p.faceA); bIdx.insert(p.faceB); }
                for (int i : aIdx) result.first.push_back(facesA[i]);
                for (int i : bIdx) result.second.push_back(facesB[i]);
            }
        }
    }
    return result;
}

// Subtract tiedFaces from allFaces. Returns faces in allFaces that are NOT in tiedFaces.
// Comparison by sorted node IDs.
std::vector<std::array<int,4>> ct_subtractFaces(
        const std::vector<std::array<int,4>>& allFaces,
        const std::vector<std::array<int,4>>& tiedFaces) {
    // Build set of tied face keys (sorted node IDs)
    std::set<std::array<int,4>> tiedSet;
    for (const auto& f : tiedFaces) {
        auto key = f;
        std::sort(key.begin(), key.end());
        tiedSet.insert(key);
    }
    std::vector<std::array<int,4>> result;
    for (const auto& f : allFaces) {
        auto key = f;
        std::sort(key.begin(), key.end());
        if (!tiedSet.count(key)) result.push_back(f);
    }
    return result;
}

// ---- Generation helpers ----

std::string ct_generateSetSegment(int setId,
        const std::vector<std::array<int,4>>& faces,
        const std::string& title = "") {
    std::ostringstream ss;
    if (title.empty()) {
        ss << "*SET_SEGMENT\n";
    } else {
        ss << "*SET_SEGMENT_TITLE\n" << title << "\n";
    }
    ss << "$#     sid       da1       da2       da3       da4\n";
    char buf[90]; snprintf(buf, sizeof(buf), "%10d  0.000000  0.000000  0.000000  0.000000", setId);
    ss << buf << "\n";
    ss << "$#      n1        n2        n3        n4\n";
    for (const auto& f : faces) {
        snprintf(buf, sizeof(buf), "%10d%10d%10d%10d", f[0], f[1], f[2], f[3]);
        ss << buf << "\n";
    }
    return ss.str();
}

std::string ct_generateSetPart(int setId,
        const std::vector<int>& pids,
        const std::string& title = "") {
    std::ostringstream ss;
    if (title.empty()) {
        ss << "*SET_PART_LIST\n";
    } else {
        ss << "*SET_PART_LIST_TITLE\n" << title << "\n";
    }
    ss << "$#     sid\n";
    char buf[90]; snprintf(buf, sizeof(buf), "%10d", setId);
    ss << buf << "\n";
    ss << "$#    pid1      pid2      pid3      pid4      pid5      pid6      pid7      pid8\n";
    for (size_t i = 0; i < pids.size(); ++i) {
        snprintf(buf, sizeof(buf), "%10d", pids[i]);
        ss << buf;
        if ((i + 1) % 8 == 0 || i + 1 == pids.size()) ss << "\n";
    }
    return ss.str();
}

std::string ct_generateSetNode(int setId,
        const std::vector<int>& nids,
        const std::string& title = "") {
    std::ostringstream ss;
    if (title.empty()) {
        ss << "*SET_NODE_LIST\n";
    } else {
        ss << "*SET_NODE_LIST_TITLE\n" << title << "\n";
    }
    ss << "$#     sid\n";
    char buf[90]; snprintf(buf, sizeof(buf), "%10d", setId);
    ss << buf << "\n";
    ss << "$#    nid1      nid2      nid3      nid4      nid5      nid6      nid7      nid8\n";
    for (size_t i = 0; i < nids.size(); ++i) {
        snprintf(buf, sizeof(buf), "%10d", nids[i]);
        ss << buf;
        if ((i + 1) % 8 == 0 || i + 1 == nids.size()) ss << "\n";
    }
    return ss.str();
}

// 실수 칸 하나 — 예전 형식으로 쓴 글자가 같은 값을 돌려주면 그 글자(골든 바이트 그대로), 아니면 값을 지키는 표기.
// ⚠ 예전엔 형식 그대로 써서 마찰 0.125 → 0.13 · 출생 시각 0.0005 → 0.00 · 파손 응력 123.456 → 123 으로 조용히 바꿨다.
std::string ct_real(double v, const char* legacyFmt) { return kw_realKeep(v, legacyFmt, 10); }

static std::string ct_int(int v) { char b[32]; snprintf(b, sizeof(b), "%10d", v); return b; }

// Format helpers for Optional Cards A~G
static std::string ct_formatCardA(const ContactDef& d) {
    return "$#    soft    sofscl    lcidab    maxpar     sbopt     depth     bsort    frcfrq\n" +
           ct_int(d.soft) + ct_real(d.sofscl, "%10.2f") + ct_int(d.lcidab) + ct_real(d.maxpar, "%10.4f") +
           ct_int(d.sbopt) + ct_int(d.depth) + ct_int(d.bsort) + ct_int(d.frcfrq);
}
static std::string ct_formatCardB(const ContactDef& d) {
    return "$#  penmax    thkopt    shlthk     snlog      isym     i2d3d    sldthk    sldstf\n" +
           ct_real(d.penmax, "%10.4f") + ct_int(d.thkopt) + ct_int(d.shlthk) + ct_int(d.snlog) +
           ct_int(d.isym) + ct_int(d.i2d3d) + ct_real(d.sldthk, "%10.4f") + ct_real(d.sldstf, "%10.4f");
}
static std::string ct_formatCardC(const ContactDef& d) {
    // ⚠ 6열은 공란 · FLANGL 7열 · CID_RCF 8열(PDF 1210쪽). 예전엔 6 · 7열에 써서 LS-DYNA 가 FLANGL 을 버리고
    //   CID_RCF 를 FLANGL 로 읽었다.
    return "$#    igap    ignore    dprfac    dtstif     edgek              flangl   cid_rcf\n" +
           ct_int(d.igap) + ct_int(d.ignore_) + ct_real(d.dprfac, "%10.4f") + ct_real(d.dtstif, "%10.4f") +
           ct_real(d.edgek, "%10.4f") + std::string(10, ' ') + ct_real(d.flangl, "%10.4f") + ct_int(d.cid_rcf);
}
static std::string ct_formatCardD(const ContactDef& d) {
    return "$#   q2tri    dtpchk     sfnbr    fnlscl    dnlscl      tcso    tiedid    shledg\n" +
           ct_int(d.q2tri) + ct_real(d.dtpchk, "%10.4f") + ct_real(d.sfnbr, "%10.4f") + ct_real(d.fnlscl, "%10.4f") +
           ct_real(d.dnlscl, "%10.4f") + ct_int(d.tcso) + ct_int(d.tiedid) + ct_int(d.shledg);
}
static std::string ct_formatCardE(const ContactDef& d) {
    return "$#  sharec    cparm8    ipback     srnde    fricsf      icor     ftorq    region\n" +
           ct_int(d.sharec) + ct_int(d.cparm8) + ct_int(d.ipback) + ct_int(d.srnde) +
           ct_real(d.fricsf, "%10.4f") + ct_int(d.icor) + ct_int(d.ftorq) + ct_int(d.region);
}
static std::string ct_formatCardF(const ContactDef& d) {
    return "$#  pstiff   ignroff              fstol    2dbinr    ssftyp     swtpr    tetfac\n" +
           ct_int(d.pstiff) + ct_int(d.ignroff) + std::string(10, ' ') + ct_real(d.fstol, "%10.4f") +
           ct_int(d.d2binr) + ct_int(d.ssftyp) + ct_int(d.swtpr) + ct_real(d.tetfac, "%10.4f");
}
static std::string ct_formatCardG(const ContactDef& d) {
    return "$#            shloff\n" + std::string(10, ' ') + ct_real(d.shloff, "%10.4f") + std::string(60, ' ');
}

// Append optional cards A~G to stream (ensures card ordering: A before B, etc.)
static void ct_appendOptionalCards(std::ostringstream& ss, const ContactDef& d) {
    // Determine highest card needed
    int maxCard = 0;
    if (d.hasCardG) maxCard = 7;
    else if (d.hasCardF) maxCard = 6;
    else if (d.hasCardE) maxCard = 5;
    else if (d.hasCardD) maxCard = 4;
    else if (d.hasCardC) maxCard = 3;
    else if (d.hasCardB) maxCard = 2;
    else if (d.hasCardA) maxCard = 1;

    // Emit all cards up to maxCard (LS-DYNA sequential dependency)
    if (maxCard >= 1) ss << ct_formatCardA(d) << "\n";
    if (maxCard >= 2) ss << ct_formatCardB(d) << "\n";
    if (maxCard >= 3) ss << ct_formatCardC(d) << "\n";
    if (maxCard >= 4) ss << ct_formatCardD(d) << "\n";
    if (maxCard >= 5) ss << ct_formatCardE(d) << "\n";
    if (maxCard >= 6) ss << ct_formatCardF(d) << "\n";
    if (maxCard >= 7) ss << ct_formatCardG(d) << "\n";
}

std::string ct_generateContact(const ContactDef& d) {
    std::ostringstream ss;
    // ⚠ **`*CONTACT_*` 에는 `_TITLE` 옵션이 없다.** 제목을 붙이는 옵션은 `_ID` 이고, 그 카드는
    // CID 1~10칸 + HEADING 11~80칸이다. 예전 판은 제목이 있으면 `_TITLE` 을 붙였고, 그러면
    // LS-DYNA 가 제목줄을 **데이터 카드로 읽고** 키워드 단계에서 즉사한다 — 실측(2026-10-02,
    // R16.1.1 MPP): `Error 10060 Unable to read line` / `10246 improperly formatted data` /
    // `10450 in keyword command` → `Error termination (0 cycles)`. 그 덱의 다른 부분(166만 요소
    // dynain 포함)은 전부 정상 로드됐고 **접촉 카드만** 죽었다.
    std::string kw = "*CONTACT_" + kw_upper(d.type);
    if (d.hasId) {
        // 덱에서 읽은 `_ID` 카드 — `title` 에 줄 전체(CID+제목)가 들어 있으므로 그대로 돌려준다.
        ss << kw << "_ID\n";
        if (!d.title.empty()) ss << d.title << "\n";
    } else if (!d.title.empty()) {
        ss << kw << "_ID\n";
        char head[128];
        snprintf(head, sizeof(head), "%10d%s", d.cid, d.title.c_str());
        ss << head << "\n";
    } else {
        ss << kw << "\n";
    }

    // Card 1: SSID MSID SSTYP MSTYP SBOXID MBOXID SPR MPR
    ss << "$#    ssid      msid     sstyp     mstyp    sboxid    mboxid       spr       mpr\n";
    ss << ct_int(d.ssid) << ct_int(d.msid) << ct_int(d.sstyp) << ct_int(d.mstyp)
       << ct_int(d.sboxid) << ct_int(d.mboxid) << ct_int(d.spr) << ct_int(d.mpr) << "\n";

    // Card 2: FS FD DC VC VDC PENCHK BT DT
    ss << "$#      fs        fd        dc        vc       vdc    penchk        bt        dt\n";
    ss << ct_real(d.fs, "%10.2f") << ct_real(d.fd, "%10.2f") << ct_real(d.dc, "%10.2f") << ct_real(d.vc, "%10.2f")
       << ct_real(d.vdc, "%10.2f") << ct_int(d.penchk) << ct_real(d.bt, "%10.2f") << ct_real(d.dt, "%10.3E") << "\n";

    // Card 3: SFSA SFSB SAST SBST SFSAT SFSBT FSF VSF
    ss << "$#    sfsa      sfsb      sast      sbst     sfsat     sfsbt       fsf       vsf\n";
    ss << ct_real(d.sfsa, "%10.2f") << ct_real(d.sfsb, "%10.2f") << ct_real(d.sast, "%10.2f") << ct_real(d.sbst, "%10.2f")
       << ct_real(d.sfsat, "%10.2f") << ct_real(d.sfsbt, "%10.2f") << ct_real(d.fsf, "%10.2f") << ct_real(d.vsf, "%10.2f") << "\n";

    // Card 4 — 형이 요구하는 필수 카드. ⚠ 선택 카드보다 **앞**이다(매뉴얼 카드 순서). 예전엔 THRM · TIEBREAK 카드를
    // 선택 카드 뒤에 써서, 선택 카드가 있으면 LS-DYNA 가 Card A 를 Card 4 로 읽었다.
    if (d.hasTiebreak) {
        // AUTOMATIC_…_TIEBREAK: OPTION NFLS SFLS PARAM ERATEN ERATES CT2CN
        ss << "$#  option      nfls      sfls     param    eraten    erates     ct2cn\n";
        ss << ct_int(d.tbOption) << ct_real(d.tbNfls, "%10.3g") << ct_real(d.tbSfls, "%10.3g")
           << ct_real(d.tbParam, "%10.3g") << ct_real(d.tbEraten, "%10.3g") << ct_real(d.tbErates, "%10.3g")
           << ct_real(d.tbCt2cn, "%10.3g") << "\n";
    }
    if (d.hasEroding) {
        // ERODING_*: ISYM EROSOP IADJ — 매뉴얼 기본(0 · 1 · 0)
        ss << "$#    isym    erosop      iadj\n";
        ss << ct_int(0) << ct_int(1) << ct_int(0) << "\n";
    }
    // THRM 1 (_THERMAL): K FRAD H0 LMIN LMAX FTOSA BC_FLG ALGO — Card 4 뒤 · 선택 카드 앞
    if (d.hasThermal) {
        ss << "$#       k      frad        h0      lmin      lmax     ftosa    bc_flg      algo\n";
        ss << ct_real(d.thK, "%10.3g") << ct_real(d.thFrad, "%10.3g") << ct_real(d.thH0, "%10.3g")
           << ct_real(d.thLmin, "%10.3g") << ct_real(d.thLmax, "%10.3g") << ct_real(d.thFtosa, "%10.3g")
           << ct_int(d.thBcflag) << ct_int(d.thAlgo) << "\n";
    }

    // Optional Cards A~G
    ct_appendOptionalCards(ss, d);

    return ss.str();
}

// 카드 k(0=Card 1 · 1=Card 2 · 2=Card 3)의 칸 하나를 그 자리에서 고친다 — 줄은 파서가 찾은 자리다(직접 세지 않는다).
bool ct_setCardField(std::vector<std::string>& lines, const ContactDef& c, int card, int field,
        const std::string& text) {
    if (card < 0 || card > 2) return false;
    const int ln = c.cardLine[card];
    if (ln < 0 || ln >= (int)lines.size()) return false;
    lines[ln] = kw_setField(lines[ln], field * 10, 10, text);
    return true;
}

// Modify an existing contact's Card 1 fields in-place
bool ct_modifyContactCard1(std::vector<std::string>& lines,
        const ContactDef& c,
        int newSsid, int newMsid, int newSstyp, int newMstyp) {
    if (c.cardLine[0] < 0) return false;
    if (newSsid  >= 0) ct_setCardField(lines, c, 0, 0, std::to_string(newSsid));
    if (newMsid  >= 0) ct_setCardField(lines, c, 0, 1, std::to_string(newMsid));
    if (newSstyp >= 0) ct_setCardField(lines, c, 0, 2, std::to_string(newSstyp));
    if (newMstyp >= 0) ct_setCardField(lines, c, 0, 3, std::to_string(newMstyp));
    return true;
}

// Modify Card 2 FS field
void ct_modifyContactFs(std::vector<std::string>& lines,
        const ContactDef& c, double newFs) {
    ct_setCardField(lines, c, 1, 0, ct_real(newFs, "%10.2f"));
}

// 선택 카드(A…)만 바꾼다 — 마지막 필수 카드(Card 3 · Card 4 · THRM · ORFR) **뒤**부터 블록 끝까지를 새 선택 카드로.
// ⚠ 예전엔 「Card 3 뒤 전부」 를 지워 TIEBREAK Card 4 · THRM 1 이 사라지고 그 자리에 Card A 가 들어갔다.
bool ct_modifyOptionalCards(std::vector<std::string>& lines,
        ContactDef& ct, const ContactDef& newVals, std::string* why) {
    if (!ct.layoutKnown) {
        if (why) *why = "선택 카드 자리를 확정할 수 없다 — " + ct.layoutWhy;
        return false;
    }
    if (ct.cardLine[2] < 0) {
        if (why) *why = "Card 3 이 없다 — 선택 카드는 Card 3(과 필수 카드) 뒤에 온다";
        return false;
    }
    int lastMand = ct.cardLine[2];
    for (const auto* v : {&ct.card4Lines, &ct.thrmLines, &ct.orfrLines})
        if (!v->empty()) lastMand = std::max(lastMand, v->back());

    const int optStart = lastMand + 1;
    const int optEnd = ct.endLine;
    if (optEnd > optStart) lines.erase(lines.begin() + optStart, lines.begin() + optEnd);

    std::ostringstream ss;
    ct_appendOptionalCards(ss, newVals);
    std::vector<std::string> newLines;
    {
        std::istringstream is(ss.str());
        std::string ln;
        while (std::getline(is, ln)) newLines.push_back(ln);
    }
    if (!newLines.empty()) lines.insert(lines.begin() + optStart, newLines.begin(), newLines.end());
    ct.endLine += (int)newLines.size() - (optEnd - optStart);
    return true;
}

// Remove a block [startLine, endLine) from lines
void ct_removeBlock(std::vector<std::string>& lines, int startLine, int endLine) {
    if (startLine >= 0 && endLine > startLine && endLine <= (int)lines.size()) {
        lines.erase(lines.begin() + startLine, lines.begin() + endLine);
    }
}

// SSTYP description
std::string ct_stypName(int styp) {
    switch(styp) {
        case 0: return "Segment Set";
        case 1: return "Shell Set";
        case 2: return "Part Set";
        case 3: return "Part ID";
        case 4: return "Node Set";
        case 5: return "All Parts";
        case 6: return "Exempt Parts";
        default: return "Unknown(" + std::to_string(styp) + ")";
    }
}

// Analyze and print contact report
// 접촉 면이 가리키는 세트의 멤버를 한 줄로 — 정본 해석기로 푼다. 못 풀면 **못 풀었다고** 적는다
// (예전엔 `_ADD` 세트에서 아무것도 안 찍어 「멤버 없음」 처럼 보였다). 세트가 덱에 없으면 비운다(예전과 같다).
static std::string ct_memberSuffix(const std::vector<SetDef>& sets, int sid, const std::string& type) {
    auto m = ct_setMembers(sets, sid, type);
    if (!m.found) return "";
    if (!m.resolved) return " -> 풀지 못함(" + m.why + ")";
    std::string out;
    if (type == "SEGMENT") {
        out = " -> " + std::to_string(m.segments.size()) + " segments";
    } else if (!m.ids.empty()) {
        out = " -> [";
        for (size_t k = 0; k < m.ids.size(); ++k) {
            if (k) out += ", ";
            out += std::to_string(m.ids[k]);
        }
        out += "]";
    }
    if (!m.note.empty()) out += " (" + m.note + ")";
    return out;
}

void ct_analyze(const std::vector<ContactDef>& contacts,
                       const std::vector<SetDef>& sets,
                       const KooRemapper::Mesh& mesh,
                       ConsoleOutput& console) {
    // Contacts
    console.println("\n--- Contacts (" + std::to_string(contacts.size()) + ") ---");
    if (contacts.empty()) {
        console.println("  No contacts found.");
    }
    for (const auto& c : contacts) {
        console.println("  [" + std::to_string(c.index) + "] " + c.fullKeyword);
        if (!c.title.empty()) console.println("      Title: " + c.title);

        // Slave info
        std::string slaveInfo = "      Slave:  ";
        if (c.sstyp == 3) slaveInfo += "PID " + std::to_string(c.ssid);
        else if (c.sstyp == 0) slaveInfo += "SET_SEGMENT " + std::to_string(c.ssid);
        else if (c.sstyp == 2) slaveInfo += "SET_PART " + std::to_string(c.ssid);
        else if (c.sstyp == 4) slaveInfo += "SET_NODE " + std::to_string(c.ssid);
        else if (c.sstyp == 5) slaveInfo += "All Parts";
        else slaveInfo += "ID=" + std::to_string(c.ssid);
        slaveInfo += " (SSTYP=" + std::to_string(c.sstyp) + ", " + ct_stypName(c.sstyp) + ")";

        // Resolve set members — 종류를 맞춰 찾는다(예전엔 ID 만 보고 첫 세트에서 멈춰, 같은 ID 의 다른 종류
        // 세트가 앞에 있으면 아무것도 안 찍었다).
        if (c.sstyp == 2 || c.sstyp == 0)
            slaveInfo += ct_memberSuffix(sets, c.ssid, c.sstyp == 2 ? "PART" : "SEGMENT");
        console.println(slaveInfo);

        // Master info
        std::string masterInfo = "      Master: ";
        if (c.mstyp == 3) masterInfo += "PID " + std::to_string(c.msid);
        else if (c.mstyp == 0) masterInfo += "SET_SEGMENT " + std::to_string(c.msid);
        else if (c.mstyp == 2) masterInfo += "SET_PART " + std::to_string(c.msid);
        else if (c.mstyp == 4) masterInfo += "SET_NODE " + std::to_string(c.msid);
        else if (c.msid == 0 && c.mstyp == 0) masterInfo += "(none)";
        else masterInfo += "ID=" + std::to_string(c.msid);
        if (c.msid != 0 || c.mstyp != 0)
            masterInfo += " (MSTYP=" + std::to_string(c.mstyp) + ", " + ct_stypName(c.mstyp) + ")";

        if ((c.mstyp == 2 || c.mstyp == 0) && (c.msid != 0 || c.mstyp != 0))
            masterInfo += ct_memberSuffix(sets, c.msid, c.mstyp == 2 ? "PART" : "SEGMENT");
        console.println(masterInfo);

        // Friction & Card 2 options
        char fbuf[120];
        // ⚠ 보고도 값을 반올림하지 않는다(예전 `%.2f` 는 마찰 0.125 를 0.13 으로 보였다).
        snprintf(fbuf, sizeof(fbuf), "      FS=%.6g  FD=%.6g", c.fs, c.fd);
        std::string optLine(fbuf);
        if (c.dc != 0) { snprintf(fbuf, sizeof(fbuf), "  DC=%.6g", c.dc); optLine += fbuf; }
        if (c.vc != 0) { snprintf(fbuf, sizeof(fbuf), "  VC=%.6g", c.vc); optLine += fbuf; }
        if (c.penchk != 0) optLine += "  PENCHK=" + std::to_string(c.penchk);
        console.println(optLine);

        // 필수 카드(Card 4 · THRM) — 선택 카드보다 앞이다
        if (c.hasTiebreak) {
            snprintf(fbuf, sizeof(fbuf), "      Card 4 (TIEBREAK): OPTION=%d  NFLS=%.6g  SFLS=%.6g", c.tbOption, c.tbNfls, c.tbSfls);
            console.println(fbuf);
        }
        if (c.hasEroding) console.println("      Card 4 (ERODING) 있음");
        if (c.hasThermal) {
            snprintf(fbuf, sizeof(fbuf), "      THRM 1: K=%.6g  FRAD=%.6g  H0=%.6g  FTOSA=%.6g", c.thK, c.thFrad, c.thH0, c.thFtosa);
            console.println(fbuf);
        }
        if (c.hasMpp) console.println("      MPP 카드 " + std::to_string(c.mppLines.size()) + "장(Card 1 앞)");
        if (!c.layoutKnown)
            console.println("      ⚠ 선택 카드 자리를 확정하지 못했다 — " + c.layoutWhy + " (선택 카드는 읽지도 고치지도 않는다)");

        // Card A — 0 은 「형의 기본」 이라 0 이 아닌 칸만 적는다
        if (c.hasCardA) {
            std::string ca = "      Card A: SOFT=" + std::to_string(c.soft);
            if (c.sofscl != 0) { snprintf(fbuf, sizeof(fbuf), "  SOFSCL=%.6g", c.sofscl); ca += fbuf; }
            if (c.depth != 0) ca += "  DEPTH=" + std::to_string(c.depth);
            if (c.sbopt != 0) ca += "  SBOPT=" + std::to_string(c.sbopt);
            if (c.bsort != 0) ca += "  BSORT=" + std::to_string(c.bsort);
            if (c.frcfrq != 0) ca += "  FRCFRQ=" + std::to_string(c.frcfrq);
            if (c.lcidab != 0) ca += "  LCIDAB=" + std::to_string(c.lcidab);
            if (c.maxpar != 0) { snprintf(fbuf, sizeof(fbuf), "  MAXPAR=%.6g", c.maxpar); ca += fbuf; }
            console.println(ca);
        }
        // Card B
        if (c.hasCardB) {
            std::string cb = "      Card B:";
            if (c.penmax != 0) { snprintf(fbuf, sizeof(fbuf), " PENMAX=%.4f", c.penmax); cb += fbuf; }
            if (c.thkopt != 0) cb += " THKOPT=" + std::to_string(c.thkopt);
            if (c.shlthk != 0) cb += " SHLTHK=" + std::to_string(c.shlthk);
            if (c.snlog != 0) cb += " SNLOG=" + std::to_string(c.snlog);
            if (c.isym != 0) cb += " ISYM=" + std::to_string(c.isym);
            if (c.i2d3d != 0) cb += " I2D3D=" + std::to_string(c.i2d3d);
            if (c.sldthk != 0) { snprintf(fbuf, sizeof(fbuf), " SLDTHK=%.4f", c.sldthk); cb += fbuf; }
            if (c.sldstf != 0) { snprintf(fbuf, sizeof(fbuf), " SLDSTF=%.4f", c.sldstf); cb += fbuf; }
            console.println(cb);
        }
        // Card C
        if (c.hasCardC) {
            std::string cc = "      Card C:";
            if (c.igap != 1) cc += " IGAP=" + std::to_string(c.igap);
            if (c.ignore_ != 0) cc += " IGNORE=" + std::to_string(c.ignore_);
            if (c.dprfac != 0) { snprintf(fbuf, sizeof(fbuf), " DPRFAC=%.4f", c.dprfac); cc += fbuf; }
            if (c.dtstif != 0) { snprintf(fbuf, sizeof(fbuf), " DTSTIF=%.4f", c.dtstif); cc += fbuf; }
            if (c.edgek != 0) { snprintf(fbuf, sizeof(fbuf), " EDGEK=%.4f", c.edgek); cc += fbuf; }
            if (c.flangl != 0) { snprintf(fbuf, sizeof(fbuf), " FLANGL=%.4f", c.flangl); cc += fbuf; }
            if (c.cid_rcf != 0) cc += " CID_RCF=" + std::to_string(c.cid_rcf);
            console.println(cc);
        }
        // Card D
        if (c.hasCardD) {
            std::string cd = "      Card D:";
            if (c.q2tri != 0) cd += " Q2TRI=" + std::to_string(c.q2tri);
            if (c.shledg != 0) cd += " SHLEDG=" + std::to_string(c.shledg);
            if (c.tcso != 0) cd += " TCSO=" + std::to_string(c.tcso);
            if (c.tiedid != 0) cd += " TIEDID=" + std::to_string(c.tiedid);
            console.println(cd);
        }
        // Card E
        if (c.hasCardE) {
            std::string ce = "      Card E:";
            if (c.sharec != 0) ce += " SHAREC=" + std::to_string(c.sharec);
            if (c.cparm8 != 0) ce += " CPARM8=" + std::to_string(c.cparm8);
            if (c.ipback != 0) ce += " IPBACK=" + std::to_string(c.ipback);
            if (c.fricsf != 1.0) { snprintf(fbuf, sizeof(fbuf), " FRICSF=%.4f", c.fricsf); ce += fbuf; }
            if (c.icor != 0) ce += " ICOR=" + std::to_string(c.icor);
            if (c.region != 0) ce += " REGION=" + std::to_string(c.region);
            console.println(ce);
        }
        // Card F
        if (c.hasCardF) {
            std::string cf = "      Card F:";
            if (c.pstiff != 0) cf += " PSTIFF=" + std::to_string(c.pstiff);
            if (c.ignroff != 0) cf += " IGNROFF=" + std::to_string(c.ignroff);
            if (c.fstol != 2.0) { snprintf(fbuf, sizeof(fbuf), " FSTOL=%.4f", c.fstol); cf += fbuf; }
            console.println(cf);
        }
        // Card G
        if (c.hasCardG) {
            snprintf(fbuf, sizeof(fbuf), "      Card G: SHLOFF=%.4f", c.shloff);
            console.println(std::string(fbuf));
        }
        console.println("");
    }

    // Sets
    console.println("--- Sets (" + std::to_string(sets.size()) + ") ---");
    if (sets.empty()) {
        console.println("  No sets found.");
    }
    for (const auto& s : sets) {
        std::string info = "  SET_" + s.type + (s.dialect.empty() ? "" : "_" + s.dialect) +
                           " " + std::to_string(s.id) + ": ";
        if (!s.membersKnown && !s.memberSets.empty()) {
            // `_ADD`·`_INTERSECT` — 멤버는 **세트 ID** 다. 정본 해석기로 푼 결과를 함께 적는다.
            info += s.dialect + " 멤버 세트 [";
            for (size_t k = 0; k < s.memberSets.size(); ++k) {
                if (k) info += ", ";
                info += std::to_string(s.memberSets[k]);
            }
            info += "]";
            auto m = ct_setMembers(sets, s.id, s.type);
            if (!m.resolved) {
                info += " -> 풀지 못함(" + m.why + ")";
            } else if (s.type == "SEGMENT") {
                info += " -> " + std::to_string(m.segments.size()) + " segments";
            } else {
                info += " -> " + std::to_string(m.ids.size()) + " entries";
                if (!m.ids.empty() && m.ids.size() <= 10) {
                    info += " [";
                    for (size_t k = 0; k < m.ids.size(); ++k) {
                        if (k) info += ", ";
                        info += std::to_string(m.ids[k]);
                    }
                    info += "]";
                }
            }
            if (!m.note.empty()) info += " (" + m.note + ")";
        } else if (!s.membersKnown) {
            // 조용히 0건이라고 말하면 거짓이다 — 왜 못 읽었는지 말한다.
            info += "멤버 뜻 미확정(" + s.dialect + ")";
        } else if (!s.ranges.empty()) {
            // 범위는 **한계값**이다 — 실제 멤버는 그 사이에 덱이 정의한 ID 뿐이다.
            info += (s.rangesResolved ? std::to_string(s.ids.size()) + " entries"
                                      : std::string("멤버 수 미정(메시를 안 읽었습니다)"));
            info += " (범위 ";
            for (size_t k = 0; k < s.ranges.size(); ++k) {
                if (k) info += ", ";
                info += std::to_string(s.ranges[k][0]) + "-" + std::to_string(s.ranges[k][1]);
                if (s.ranges[k][2] > 1) info += "/" + std::to_string(s.ranges[k][2]);
            }
            info += " — 한계값이라 정의된 ID 만 셉니다)";
            if (!s.ids.empty() && s.ids.size() <= 10) {
                info += " [";
                for (size_t k = 0; k < s.ids.size(); ++k) {
                    if (k) info += ", ";
                    info += std::to_string(s.ids[k]);
                }
                info += "]";
            }
        } else if (s.type == "SEGMENT") {
            info += std::to_string(s.segments.size()) + " segments";
        } else {
            info += std::to_string(s.ids.size()) + " entries";
            if (s.ids.size() <= 10) {
                info += " [";
                for (size_t k = 0; k < s.ids.size(); ++k) {
                    if (k) info += ", ";
                    info += std::to_string(s.ids[k]);
                }
                info += "]";
            }
        }
        if (!s.title.empty()) info += " \"" + s.title + "\"";
        console.println(info);
    }

    // Coverage analysis
    console.println("\n--- Coverage ---");
    std::map<int, std::vector<std::string>> pidContacts;
    for (const auto& [pid, part] : mesh.getParts()) {
        pidContacts[pid];  // ensure entry exists
    }
    for (const auto& c : contacts) {
        auto addCoverage = [&](int id, int styp, const std::string& role) {
            if (styp == 3) {
                // Direct PID
                pidContacts[id].push_back(role + "[" + std::to_string(c.index) + "]");
            } else if (styp == 2) {
                // Part set — 정본 해석기로 푼다(`_ADD`·`_COLLECT` 를 따라간다 · 못 풀면 덧붙이지 않는다)
                const SetMembers members = ct_setMembers(sets, id, "PART");
                for (int pid : members.ids) {
                    pidContacts[pid].push_back(role + "[" + std::to_string(c.index) + "]");
                }
            } else if (styp == 5) {
                // All parts
                for (auto& [pid, v] : pidContacts) {
                    v.push_back(role + "[" + std::to_string(c.index) + "]");
                }
            }
        };
        addCoverage(c.ssid, c.sstyp, "slave");
        addCoverage(c.msid, c.mstyp, "master");
    };

    for (const auto& [pid, roles] : pidContacts) {
        std::string line = "  PID " + std::to_string(pid) + ": ";
        if (roles.empty()) {
            line += "no contact (!)";
        } else {
            for (size_t k = 0; k < roles.size(); ++k) {
                if (k) line += ", ";
                line += roles[k];
            }
        }
        console.println(line);
    }
    console.println("");
}
