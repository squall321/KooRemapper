#include "parser/DeckWriter.h"
#include "parser/IdAllocator.h"
#include "parser/IncludeClosure.h"
#include "contact.h"
#include "contact_helpers.h"
#include "kw_util.h"
#include "cli/ConsoleOutput.h"
#include "util/YamlComment.h"
#include "util/ContactKeywords.h"
#include "core/Mesh.h"
#include "parser/KFileReader.h"
#include <fstream>
#include <sstream>
#include <string>
#include <vector>
#include <map>
#include <set>
#include <algorithm>
#include <cerrno>
#include <climits>
#include <cmath>
#include <cstdlib>
#include <optional>

// Knowledge graph (lat.md):
//   @lat: [[modules/commands]]
//   @lat: [[commands/contact]]

using namespace KooRemapper;

int runContact(const std::string& yamlFile, ConsoleOutput& console) {
    {   // 탭으로 들여쓴 YAML 은 블록이 통째로 무너져 조용히 아무 일도 안 했다 — 파싱 전에 거른다
        std::string tabLine;
        if (KooRemapper::yamlScanTabIndent(yamlFile, tabLine)) {
            console.error(KooRemapper::yamlTabIndentMessage("contact", tabLine));
            return 1;
        }
    }
    // 1. Parse YAML
    std::string configDir;
    {
        size_t sep = yamlFile.find_last_of("/\\");
        configDir = (sep != std::string::npos) ? yamlFile.substr(0, sep) : "";
    }
    auto resolvePath = [&](const std::string& p) -> std::string {
        return KooRemapper::yamlResolvePath(configDir, p);   // YAML 폴더 기준(절대 경로는 그대로)
    };

    std::ifstream yin(yamlFile);
    if (!yin.is_open()) { console.error("Cannot open YAML: " + yamlFile); return 1; }
    KooRemapper::yamlSkipBOM(yin);   // 윈도우 편집기가 붙인 BOM 이 첫 키를 망가뜨렸다

    std::string modelFile, outputFile;

    // 카드 칸 값은 **있으면** 쓴다(std::optional). ⚠ 예전엔 -1 을 「안 줌」 으로 써서(`>= 0` 문) 매뉴얼이 뜻을 둔 음수 —
    //   FS −1/−2 · BT/DT 음수(동적 이완) · DT −9999 · SFSA<0(Mortar 곡선) · SAST/SBST<0(TIED) · 상자 음수(접촉 부피) ·
    //   DEPTH/BSORT 곡선 · IGAP<0 · DPRFAC/DTSTIF 곡선 · NFLS<0(곡선) … — 을 조용히 버렸다.
    using OD = std::optional<double>;
    using OI = std::optional<int>;
    struct ContactAction {
        std::string action;  // analyze/create/convert/modify/remove/detect
        // create fields
        std::string type;
        struct Side {
            int pid = 0;
            std::vector<int> pids;
            bool asSegment = false;
            bool facing = false;   // filter segments to only those facing the other side
        };
        Side slave, master;
        OD friction;
        std::string title;
        // convert/modify/remove fields
        int contactIndex = -1;
        std::string slaveTo, masterTo;  // "segment"
        bool convertFacing = false;     // facing filter for convert action
        // Card 1 extended
        OI sboxid, mboxid, spr, mpr;
        // Card 2
        OD fd, dc, vc, vdc; OI penchk; OD bt, dt;
        // Card 3
        OD sfsa, sfsb, sast, sbst, sfsat, sfsbt, fsf, vsf;
        // Card A
        OI soft; OD sofscl; OI lcidab; OD maxpar; OI sbopt, depth, bsort, frcfrq;
        // Card B
        OD penmax; OI thkopt, shlthk, snlog, isym, i2d3d; OD sldthk, sldstf;
        // Card C
        OI igap, ignore_; OD dprfac, dtstif, edgek, flangl; OI cid_rcf;
        // Card D
        OI q2tri; OD dtpchk, sfnbr, fnlscl, dnlscl; OI tcso, tiedid, shledg;
        // Card E
        OI sharec, cparm8, ipback, srnde; OD fricsf; OI icor, ftorq, region;
        // Card F
        OI pstiff, ignroff; OD fstol; OI d2binr, ssftyp, swtpr; OD tetfac;
        // Card G
        OD shloff;
        // THRM 1 (_THERMAL): K FRAD H0 LMIN LMAX FTOSA BC_FLG ALGO — 키 `ftosa`(옛 이름 `chlm` 도 받는다)
        OD th_k, th_frad, th_h0, th_lmin, th_lmax, th_ftosa; OI th_bcflag, th_algo;
        // Card 4 (AUTOMATIC_…_TIEBREAK): OPTION NFLS SFLS PARAM ERATEN ERATES CT2CN
        OI tb_option; OD tb_nfls, tb_sfls, tb_param, tb_eraten, tb_erates, tb_ct2cn;
        // detect fields
        std::string scope;                        // "all" or empty
        std::vector<std::string> includeKeys;     // part name include keywords
        std::vector<std::string> excludeKeys;     // part name exclude keywords
        std::string contactType = "auto";         // contact type preset
        double detectTolerance = 0.1;
        double detectNormalAngle = 45.0;
        bool detectAutoCreate = false;
        std::string titlePrefix;                  // e.g. "Tied" → "Tied_PartA_PartB"
        std::string skipExisting;                 // "tied"/"all"/empty → pair-level skip
        bool subtractExisting = false;            // segment-level subtraction
    };
    std::vector<ContactAction> actions;

    // Simple YAML parser
    {
        std::string line;
        bool inContacts = false;
        int contactsIndent = 0;
        ContactAction curAction;
        bool hasAction = false;
        std::string currentSide;  // "slave" or "master"
        // 'include:'/'exclude:' 뒤에 오는 블록 리스트(- 항목)를 담을 자리 (없으면 nullptr)
        std::vector<std::string>* pendingKeyList = nullptr;
        // slave:/master: 밑 'pids:' 뒤에 오는 블록 리스트(- 1 항목)를 담을 자리 (없으면 nullptr).
        // 예전엔 '- 1' 줄에 콜론이 없어 그냥 버려져, 인라인 'pids: [1]' 은 SET_PART 를 만드는데
        // 같은 뜻의 블록 목록은 조용히 아무 세트도 안 만들었다.
        std::vector<int>* pendingPidList = nullptr;

        auto flushAction = [&]() {
            if (hasAction) {
                actions.push_back(curAction);
                curAction = ContactAction{};
                hasAction = false;
                currentSide.clear();
                pendingPidList = nullptr;   // 새 항목 — 앞 항목의 pids 목록은 닫힌다
            }
        };

        auto stripQuotes = [](const std::string& s) -> std::string {
            if (s.size() >= 2 && ((s.front()=='"' && s.back()=='"') || (s.front()=='\'' && s.back()=='\'')))
                return s.substr(1, s.size()-2);
            return s;
        };

        // 숫자 칸 — 글자 전체가 수여야 한다. ⚠ 예전엔 `catch(...){}` 로 못 읽은 값을 조용히 버렸다
        //   (`friction: 0,3` · `soft: two` 가 rc 0 으로 「안 준 것」 이 됐다).
        auto parseNum = [](const std::string& v, double& out) -> bool {
            if (v.empty()) return false;
            char* end = nullptr;
            out = std::strtod(v.c_str(), &end);
            return end && *end == '\0' && std::isfinite(out);
        };
        auto parseInt = [](const std::string& v, int& out) -> bool {
            if (v.empty()) return false;
            char* end = nullptr;
            errno = 0;
            const long l = std::strtol(v.c_str(), &end, 10);
            if (!end || *end != '\0' || errno == ERANGE || l < INT_MIN || l > INT_MAX) return false;
            out = (int)l;
            return true;
        };
        auto badNumber = [&](const std::string& k, const std::string& v, bool integer) {
            console.error("[contact] '" + k + ": " + v + "' — " + (integer ? "정수" : "수") + "로 읽을 수 없다");
        };
        // 카드 칸 키 → 자리. 실수(d) 또는 정수(i) 하나.
        struct NumKey { const char* key; OD ContactAction::* d; OI ContactAction::* i; };
        static const NumKey kNumKeys[] = {
            {"friction", &ContactAction::friction, nullptr},
            // Card 1
            {"sboxid", nullptr, &ContactAction::sboxid}, {"mboxid", nullptr, &ContactAction::mboxid},
            {"spr", nullptr, &ContactAction::spr},       {"mpr", nullptr, &ContactAction::mpr},
            // Card 2
            {"fd", &ContactAction::fd, nullptr}, {"dc", &ContactAction::dc, nullptr}, {"vc", &ContactAction::vc, nullptr},
            {"vdc", &ContactAction::vdc, nullptr}, {"penchk", nullptr, &ContactAction::penchk},
            {"bt", &ContactAction::bt, nullptr}, {"dt", &ContactAction::dt, nullptr},
            // Card 3
            {"sfsa", &ContactAction::sfsa, nullptr}, {"sfsb", &ContactAction::sfsb, nullptr},
            {"sast", &ContactAction::sast, nullptr}, {"sbst", &ContactAction::sbst, nullptr},
            {"sfsat", &ContactAction::sfsat, nullptr}, {"sfsbt", &ContactAction::sfsbt, nullptr},
            {"fsf", &ContactAction::fsf, nullptr}, {"vsf", &ContactAction::vsf, nullptr},
            // Card A
            {"soft", nullptr, &ContactAction::soft}, {"sofscl", &ContactAction::sofscl, nullptr},
            {"lcidab", nullptr, &ContactAction::lcidab}, {"maxpar", &ContactAction::maxpar, nullptr},
            {"sbopt", nullptr, &ContactAction::sbopt}, {"depth", nullptr, &ContactAction::depth},
            {"bsort", nullptr, &ContactAction::bsort}, {"frcfrq", nullptr, &ContactAction::frcfrq},
            // Card B
            {"penmax", &ContactAction::penmax, nullptr}, {"thkopt", nullptr, &ContactAction::thkopt},
            {"shlthk", nullptr, &ContactAction::shlthk}, {"snlog", nullptr, &ContactAction::snlog},
            {"isym", nullptr, &ContactAction::isym}, {"i2d3d", nullptr, &ContactAction::i2d3d},
            {"sldthk", &ContactAction::sldthk, nullptr}, {"sldstf", &ContactAction::sldstf, nullptr},
            // Card C
            {"igap", nullptr, &ContactAction::igap}, {"ignore", nullptr, &ContactAction::ignore_},
            {"dprfac", &ContactAction::dprfac, nullptr}, {"dtstif", &ContactAction::dtstif, nullptr},
            {"edgek", &ContactAction::edgek, nullptr}, {"flangl", &ContactAction::flangl, nullptr},
            {"cid_rcf", nullptr, &ContactAction::cid_rcf},
            // Card D
            {"q2tri", nullptr, &ContactAction::q2tri}, {"dtpchk", &ContactAction::dtpchk, nullptr},
            {"sfnbr", &ContactAction::sfnbr, nullptr}, {"fnlscl", &ContactAction::fnlscl, nullptr},
            {"dnlscl", &ContactAction::dnlscl, nullptr}, {"tcso", nullptr, &ContactAction::tcso},
            {"tiedid", nullptr, &ContactAction::tiedid}, {"shledg", nullptr, &ContactAction::shledg},
            // Card E
            {"sharec", nullptr, &ContactAction::sharec}, {"cparm8", nullptr, &ContactAction::cparm8},
            {"ipback", nullptr, &ContactAction::ipback}, {"srnde", nullptr, &ContactAction::srnde},
            {"fricsf", &ContactAction::fricsf, nullptr}, {"icor", nullptr, &ContactAction::icor},
            {"ftorq", nullptr, &ContactAction::ftorq}, {"region", nullptr, &ContactAction::region},
            // Card F
            {"pstiff", nullptr, &ContactAction::pstiff}, {"ignroff", nullptr, &ContactAction::ignroff},
            {"fstol", &ContactAction::fstol, nullptr}, {"d2binr", nullptr, &ContactAction::d2binr},
            {"2dbinr", nullptr, &ContactAction::d2binr}, {"ssftyp", nullptr, &ContactAction::ssftyp},
            {"swtpr", nullptr, &ContactAction::swtpr}, {"tetfac", &ContactAction::tetfac, nullptr},
            // Card G
            {"shloff", &ContactAction::shloff, nullptr},
            // THRM 1
            {"k", &ContactAction::th_k, nullptr}, {"frad", &ContactAction::th_frad, nullptr},
            {"h0", &ContactAction::th_h0, nullptr}, {"lmin", &ContactAction::th_lmin, nullptr},
            {"lmax", &ContactAction::th_lmax, nullptr}, {"ftosa", &ContactAction::th_ftosa, nullptr},
            {"chlm", &ContactAction::th_ftosa, nullptr},   // 옛 이름 — 3D 접촉에서 이 칸은 FTOSA 다
            {"bc_flag", nullptr, &ContactAction::th_bcflag}, {"bc_flg", nullptr, &ContactAction::th_bcflag},
            {"algo", nullptr, &ContactAction::th_algo},
            // Card 4 (TIEBREAK)
            {"option", nullptr, &ContactAction::tb_option}, {"nfls", &ContactAction::tb_nfls, nullptr},
            {"sfls", &ContactAction::tb_sfls, nullptr}, {"param", &ContactAction::tb_param, nullptr},
            {"eraten", &ContactAction::tb_eraten, nullptr}, {"erates", &ContactAction::tb_erates, nullptr},
            {"ct2cn", &ContactAction::tb_ct2cn, nullptr},
        };

        auto parsePidList = [](const std::string& s) -> std::vector<int> {
            std::vector<int> result;
            std::string buf;
            for (char c : s) {
                if (c == '[' || c == ']' || c == ' ') continue;
                if (c == ',') {
                    if (!buf.empty()) { try { result.push_back(std::stoi(buf)); } catch(...){} buf.clear(); }
                } else {
                    buf += c;
                }
            }
            if (!buf.empty()) { try { result.push_back(std::stoi(buf)); } catch(...){} }
            return result;
        };

        while (std::getline(yin, line)) {
            std::string raw = line;
            int indent = 0;
            for (char c : raw) { if (c == ' ') ++indent; else break; }
            std::string t = kw_trim(raw);
            if (t.empty() || t[0] == '#') continue;

            // include:/exclude: 의 블록 리스트 항목 — 예전엔 콜론이 없어 그냥 버려졌다
            if (pendingKeyList && t[0] == '-') {
                std::string item = kw_trim(yamlStripComment(t.substr(1)));
                if (item.find(':') == std::string::npos) {
                    item = stripQuotes(item);
                    if (!item.empty()) pendingKeyList->push_back(item);
                    continue;
                }
            }
            pendingKeyList = nullptr;

            // slave:/master: 밑 'pids:' 의 블록 리스트 항목 — 인라인 'pids: [1]' 과 같게 읽는다
            if (pendingPidList && t[0] == '-') {
                std::string item = kw_trim(yamlStripComment(t.substr(1)));
                if (item.find(':') == std::string::npos) {
                    item = stripQuotes(item);
                    if (!item.empty()) { try { pendingPidList->push_back(std::stoi(item)); } catch(...){} }
                    continue;
                }
            }
            pendingPidList = nullptr;

            size_t colon = t.find(':');
            if (colon == std::string::npos) continue;
            std::string key = kw_trim(t.substr(0, colon));
            // 예전엔 find('#') 로 따옴표 안·붙어 쓴 # 까지 잘랐고 따옴표도 떼지 않았다 (title: "Self # x" → '"Self')
            std::string val = stripQuotes(kw_trim(yamlStripComment(t.substr(colon+1))));

            // Top-level keys
            if (key == "model" && indent < 4) { modelFile = val; inContacts = false; continue; }
            if (key == "output" && indent < 4) { outputFile = val; inContacts = false; continue; }

            if (key == "contacts" && indent < 4) {
                inContacts = true;
                contactsIndent = indent;
                continue;
            }

            if (!inContacts) continue;

            // Detect new list item: "- action: ..."
            if (t.find("- action") == 0) {
                flushAction();
                size_t ac = t.find(':');
                if (ac != std::string::npos) {
                    curAction.action = stripQuotes(kw_trim(yamlStripComment(t.substr(ac+1))));
                }
                hasAction = true;
                currentSide.clear();
                continue;
            }

            if (!hasAction) continue;

            // Sub-keys of current action
            if (key == "type") { curAction.type = val; continue; }
            if (key == "title") { curAction.title = val; continue; }
            if (key == "contact_index") {
                if (!parseInt(val, curAction.contactIndex)) { badNumber(key, val, true); return 1; }
                continue;
            }
            if (key == "slave_to") { curAction.slaveTo = val; continue; }
            if (key == "master_to") { curAction.masterTo = val; continue; }
            if (key == "facing" && curAction.action == "convert") {
                curAction.convertFacing = (val=="true"||val=="yes"||val=="1"); continue;
            }
            // 카드 칸 숫자 — 표(`kNumKeys`)로 한 번에. 못 읽으면 rc 1(조용히 버리지 않는다).
            {
                const NumKey* nk = nullptr;
                for (const auto& k : kNumKeys) if (key == k.key) { nk = &k; break; }
                if (nk) {
                    if (nk->d) {
                        double v = 0;
                        if (!parseNum(val, v)) { badNumber(key, val, false); return 1; }
                        curAction.*(nk->d) = v;
                    } else {
                        int v = 0;
                        if (!parseInt(val, v)) { badNumber(key, val, true); return 1; }
                        curAction.*(nk->i) = v;
                    }
                    continue;
                }
            }

            // detect fields
            if (key == "scope") { curAction.scope = val; continue; }
            if (key == "contact_type") {
                // 예전엔 모르는 값을 그대로 키워드로 붙여 *CONTACT_BOGUS_TITLE 같은 덱을 만들었다
                static const char* kContactTypes[] = {
                    "auto", "automatic", "tied", "tied_thermal", "thermal", "tiebreak",
                    "mortar", "tied_mortar", "single", "eroding", "forming"
                };
                std::string lv = val;
                std::transform(lv.begin(), lv.end(), lv.begin(),
                               [](unsigned char c){ return (char)std::tolower(c); });
                bool known = lv.empty();
                for (const char* ct : kContactTypes) if (lv == ct) { known = true; break; }
                if (!known) {
                    console.error("[contact] unsupported contact_type '" + val +
                                  "' (allowed: auto, tied, tied_thermal, tiebreak, mortar, "
                                  "tied_mortar, single, eroding, forming)");
                    return 1;
                }
                curAction.contactType = val;
                continue;
            }
            if (key == "tolerance") {
                if (!parseNum(val, curAction.detectTolerance)) { badNumber(key, val, false); return 1; }
                continue;
            }
            if (key == "normal_angle") {
                if (!parseNum(val, curAction.detectNormalAngle)) { badNumber(key, val, false); return 1; }
                continue;
            }
            if (key == "auto_create") { curAction.detectAutoCreate = (val=="true"||val=="yes"||val=="1"); continue; }
            if (key == "title_prefix") { curAction.titlePrefix = val; continue; }
            if (key == "skip_existing") { curAction.skipExisting = val; continue; }
            if (key == "subtract_existing") { curAction.subtractExisting = (val=="true"||val=="yes"||val=="1"); continue; }
            if (key == "include" || key == "exclude") {
                // Parse list: [kw1, kw2, ...] or bare value
                std::vector<std::string>& tgt = (key == "include") ?
                    curAction.includeKeys : curAction.excludeKeys;
                std::string v = val;
                if (v.empty()) { pendingKeyList = &tgt; continue; }   // 블록 리스트 형식
                if (!v.empty() && v.front() == '[') v.erase(v.begin());
                if (!v.empty() && v.back() == ']') v.pop_back();
                std::istringstream kss(v);
                std::string kw;
                while (std::getline(kss, kw, ',')) {
                    size_t s = kw.find_first_not_of(" \t");
                    size_t e = kw.find_last_not_of(" \t");
                    if (s != std::string::npos && e != std::string::npos)
                        tgt.push_back(stripQuotes(kw.substr(s, e - s + 1)));  // 예전엔 ["CUBE"] 의 따옴표가 남아 아무 파트도 안 맞았다
                }
                continue;
            }

            // slave:/master: can be inline { pid: N } or multiline
            if (key == "slave" || key == "master") {
                currentSide = key;
                ContactAction::Side& side = (key == "slave") ? curAction.slave : curAction.master;
                // Check for inline: { pid: 1, as_segment: true }
                if (val.find('{') != std::string::npos) {
                    // Parse inline map
                    std::string inner = val;
                    size_t br = inner.find('{');
                    if (br != std::string::npos) inner = inner.substr(br+1);
                    br = inner.find('}');
                    if (br != std::string::npos) inner = inner.substr(0, br);
                    // Split by comma (but not inside brackets)
                    std::vector<std::string> pairs;
                    {
                        std::string cur;
                        int bracketDepth = 0;
                        for (char ch : inner) {
                            if (ch == '[') { bracketDepth++; cur += ch; }
                            else if (ch == ']') { bracketDepth--; cur += ch; }
                            else if (ch == ',' && bracketDepth == 0) {
                                pairs.push_back(cur); cur.clear();
                            } else { cur += ch; }
                        }
                        if (!cur.empty()) pairs.push_back(cur);
                    }
                    for (const auto& pr : pairs) {
                        size_t c2 = pr.find(':');
                        if (c2 == std::string::npos) continue;
                        std::string k2 = kw_trim(pr.substr(0, c2));
                        std::string v2 = kw_trim(pr.substr(c2+1));
                        if (k2 == "pid") { if (!parseInt(v2, side.pid)) { badNumber(k2, v2, true); return 1; } }
                        else if (k2 == "pids") { side.pids = parsePidList(v2); }
                        else if (k2 == "as_segment") { side.asSegment = (v2=="true"||v2=="yes"||v2=="1"); }
                        else if (k2 == "facing") { side.facing = (v2=="true"||v2=="yes"||v2=="1"); }
                    }
                    currentSide.clear();
                }
                continue;
            }

            // Multiline slave/master sub-keys
            if (!currentSide.empty()) {
                ContactAction::Side& side = (currentSide == "slave") ? curAction.slave : curAction.master;
                if (key == "pid") { if (!parseInt(val, side.pid)) { badNumber(key, val, true); return 1; } continue; }
                if (key == "pids") {
                    // 값이 비면 다음 '- 1' 줄들이 목록이다 — 예전엔 빈 목록으로 두고 그 줄들을 버렸다
                    if (val.empty()) { side.pids.clear(); pendingPidList = &side.pids; }
                    else side.pids = parsePidList(val);
                    continue;
                }
                if (key == "as_segment") { side.asSegment = (val=="true"||val=="yes"||val=="1"); continue; }
                if (key == "facing") { side.facing = (val=="true"||val=="yes"||val=="1"); continue; }
            }
        }
        flushAction();
    }

    if (modelFile.empty()) { console.error("YAML missing 'model' key"); return 1; }
    if (actions.empty()) { console.error("YAML has no contact actions"); return 1; }

    std::string modelPath = resolvePath(modelFile);
    std::string outPath;
    if (!outputFile.empty()) {
        outPath = resolvePath(outputFile);
        if (const std::string note = KooRemapper::yamlOutputExtNote(outPath); !note.empty())
            console.warning("[contact] " + note);
    }

    // 2. Read model as rawLines
    std::vector<std::string> lines;
    {
        std::ifstream mf(modelPath);
        if (!mf.is_open()) { console.error("Cannot open model: " + modelPath); return 1; }
        std::string ln;
        while (std::getline(mf, ln)) lines.push_back(ln);
    }

    // 인클루드 닫힘을 읽는다 — 새 세트·접촉 번호를 **그 안의 최대값 위로** 내려고.
    // ⚠ 예전에는 이 덱 하나만 세고 경고만 했다. 그래서 인클루드에 `*SET_SEGMENT 11` 이 있는 덱에
    //   새 `*SET_SEGMENT 11` 을 냈다(재현 — 같은 종류의 SID 가 둘이면 LS-DYNA 가 키워드 단계에서
    //   멈춘다). 못 읽은 인클루드가 있으면 **그 자리만** 말한다 — 그 안의 번호는 못 봤다.
    const auto inclClosure = KooRemapper::include_closure::read(modelPath, lines);
    if (!inclClosure.files.empty())
        console.info("[contact] 인클루드 " + std::to_string(inclClosure.files.size()) +
                     "개를 읽어 세트·접촉 번호를 그 위로 냅니다");

    // 3. Optionally load Mesh (for surface extraction)
    bool needMesh = false;
    bool onlyAnalyze = true;
    for (const auto& act : actions) {
        if (act.action != "analyze") onlyAnalyze = false;
        // `analyze` 도 메시가 필요하다 — `*SET_*_GENERATE` 의 범위는 **한계값**이라 덱에 정의된
        // ID 로 좁혀야 멤버 수를 말할 수 있다. 못 읽으면 보고를 멈추지 않고 못 좁혔다고 말한다.
        if (act.action == "analyze") needMesh = true;
        if (act.action == "create" && (act.slave.asSegment || act.master.asSegment)) needMesh = true;
        if (act.action == "convert") needMesh = true;
        if (act.action == "detect") needMesh = true;
    }

    KooRemapper::Mesh mesh;
    if (needMesh) {
        KooRemapper::KFileReader reader;
        try {
            mesh = reader.readFile(modelPath);
        } catch (const std::exception& e) {
            if (!onlyAnalyze) {
                console.error("Cannot parse mesh: " + modelPath + " (" + e.what() + ")");
                return 1;
            }
            // 읽기 전용 보고다 — 멈추지 않는다. 대신 무엇을 못 하게 됐는지 말한다.
            console.warning("메시를 읽지 못해 세트 범위를 좁히지 못합니다: " + std::string(e.what()));
        }
    }

    // 4. Parse existing contacts and sets
    auto contacts = ct_parseContacts(lines);
    auto sets     = ct_parseSets(lines);
    ct_resolveSetRanges(sets, mesh);   // `_GENERATE` 범위를 덱에 정의된 ID 로 좁힌다
    // 새 번호는 한 길(`IdAllocator`)로 낸다. 최대값은 **지금까지와 같은 스캐너**로 센다 — 주 덱은
    // 그대로이고(인클루드가 없으면 번호가 한 글자도 안 바뀐다) 인클루드 파일마다 같은 스캐너를 더
    // 돌려 올린다. SET 은 모든 종류를 한 통으로 센다(이 op 의 규약 — 겹칠 수 없게 보수적으로).
    // 새 접촉의 CID 는 덱의 기존 `_ID` CID **위로** 낸다. 같은 CID 가 둘이면 LS-DYNA 가
    // 키워드 단계에서 멈춘다 — 이 리포의 ID 규율대로 발행 전에 최대값을 본다.
    KooRemapper::ids::UsedIds usedIds;
    usedIds.raise(KooRemapper::ids::Ns::Set, ct_findMaxSetId(sets));
    usedIds.raise(KooRemapper::ids::Ns::Contact, ct_findMaxContactId(lines));
    for (const auto& f : inclClosure.files) {
        usedIds.raise(KooRemapper::ids::Ns::Set, ct_findMaxSetId(ct_parseSets(f.lines)));
        usedIds.raise(KooRemapper::ids::Ns::Contact, ct_findMaxContactId(f.lines));
    }
    usedIds.noteClosure(inclClosure);
    for (const auto& b : usedIds.blind)
        console.warning("[contact] 못 본 인클루드가 있어 그 안의 세트·접촉 번호와 겹쳐 낼 수 있습니다 — " + b);
    KooRemapper::ids::IdAllocator ids(usedIds);

    console.println("[contact] Model: " + modelFile + " (" + std::to_string(lines.size()) + " lines)");
    console.println("[contact] Found " + std::to_string(contacts.size()) + " contacts, " +
                    std::to_string(sets.size()) + " sets");

    // ── 카드 조립 — create · detect · modify 가 **같은 규칙**을 쓴다 ─────────────────────────────────
    // ⚠ 예전엔 create · detect(두 갈래)가 같은 칸 옮기기를 세 벌 베껴 두었고, detect 사본에는 THRM · Card 4 가 빠져
    //   tied_thermal · tiebreak 를 골라도 필수 카드 없는 키워드를 냈다(D12).
    auto applyCard123 = [](const ContactAction& a, ContactDef& d) {
        if (a.sboxid) d.sboxid = *a.sboxid;
        if (a.mboxid) d.mboxid = *a.mboxid;
        if (a.spr) d.spr = *a.spr;
        if (a.mpr) d.mpr = *a.mpr;
        d.fs = a.friction.value_or(d.fs);
        if (a.fd) d.fd = *a.fd;
        if (a.dc) d.dc = *a.dc;
        if (a.vc) d.vc = *a.vc;
        if (a.vdc) d.vdc = *a.vdc;
        if (a.penchk) d.penchk = *a.penchk;
        if (a.bt) d.bt = *a.bt;
        if (a.dt) d.dt = *a.dt;
        if (a.sfsa) d.sfsa = *a.sfsa;
        if (a.sfsb) d.sfsb = *a.sfsb;
        if (a.sast) d.sast = *a.sast;
        if (a.sbst) d.sbst = *a.sbst;
        if (a.sfsat) d.sfsat = *a.sfsat;
        if (a.sfsbt) d.sfsbt = *a.sfsbt;
        if (a.fsf) d.fsf = *a.fsf;
        if (a.vsf) d.vsf = *a.vsf;
    };
    // 선택 카드 A~G — 칸을 하나라도 주면 그 카드(와 앞 카드 전부 — LS-DYNA 는 차례대로 읽는다)를 쓴다.
    auto anyOptional = [](const ContactAction& a) -> bool {
        return a.soft||a.sofscl||a.lcidab||a.maxpar||a.sbopt||a.depth||a.bsort||a.frcfrq||
               a.penmax||a.thkopt||a.shlthk||a.snlog||a.isym||a.i2d3d||a.sldthk||a.sldstf||
               a.igap||a.ignore_||a.dprfac||a.dtstif||a.edgek||a.flangl||a.cid_rcf||
               a.q2tri||a.dtpchk||a.sfnbr||a.fnlscl||a.dnlscl||a.tcso||a.tiedid||a.shledg||
               a.sharec||a.cparm8||a.ipback||a.srnde||a.fricsf||a.icor||a.ftorq||a.region||
               a.pstiff||a.ignroff||a.fstol||a.d2binr||a.ssftyp||a.swtpr||a.tetfac||a.shloff;
    };
    auto applyOptional = [](const ContactAction& a, ContactDef& d) {
        int top = 0;   // 1=A … 7=G
        auto set = [&](auto& dst, const auto& src, int card) { if (src) { dst = *src; top = std::max(top, card); } };
        set(d.soft, a.soft, 1);   set(d.sofscl, a.sofscl, 1); set(d.lcidab, a.lcidab, 1); set(d.maxpar, a.maxpar, 1);
        set(d.sbopt, a.sbopt, 1); set(d.depth, a.depth, 1);   set(d.bsort, a.bsort, 1);   set(d.frcfrq, a.frcfrq, 1);
        set(d.penmax, a.penmax, 2); set(d.thkopt, a.thkopt, 2); set(d.shlthk, a.shlthk, 2); set(d.snlog, a.snlog, 2);
        set(d.isym, a.isym, 2);     set(d.i2d3d, a.i2d3d, 2);   set(d.sldthk, a.sldthk, 2); set(d.sldstf, a.sldstf, 2);
        set(d.igap, a.igap, 3);     set(d.ignore_, a.ignore_, 3); set(d.dprfac, a.dprfac, 3); set(d.dtstif, a.dtstif, 3);
        set(d.edgek, a.edgek, 3);   set(d.flangl, a.flangl, 3); set(d.cid_rcf, a.cid_rcf, 3);
        set(d.q2tri, a.q2tri, 4);   set(d.dtpchk, a.dtpchk, 4); set(d.sfnbr, a.sfnbr, 4);   set(d.fnlscl, a.fnlscl, 4);
        set(d.dnlscl, a.dnlscl, 4); set(d.tcso, a.tcso, 4);     set(d.tiedid, a.tiedid, 4); set(d.shledg, a.shledg, 4);
        set(d.sharec, a.sharec, 5); set(d.cparm8, a.cparm8, 5); set(d.ipback, a.ipback, 5); set(d.srnde, a.srnde, 5);
        set(d.fricsf, a.fricsf, 5); set(d.icor, a.icor, 5);     set(d.ftorq, a.ftorq, 5);   set(d.region, a.region, 5);
        set(d.pstiff, a.pstiff, 6); set(d.ignroff, a.ignroff, 6); set(d.fstol, a.fstol, 6); set(d.d2binr, a.d2binr, 6);
        set(d.ssftyp, a.ssftyp, 6); set(d.swtpr, a.swtpr, 6);   set(d.tetfac, a.tetfac, 6);
        set(d.shloff, a.shloff, 7);
        if (top >= 1) d.hasCardA = true;
        if (top >= 2) d.hasCardB = true;
        if (top >= 3) d.hasCardC = true;
        if (top >= 4) d.hasCardD = true;
        if (top >= 5) d.hasCardE = true;
        if (top >= 6) d.hasCardF = true;
        if (top >= 7) d.hasCardG = true;
    };
    // 형이 요구하는 필수 카드(Card 4 · THRM). 우리가 꼴을 아는 것만 쓰고, 모르는 것은 **거절**한다 — 예전엔 대문자로 그대로
    // 써서 경고만 하고 rc 0 으로 불완전한 키워드를 냈다(ERODING 의 Card 4 · TIEBREAK_USER · THERMAL_FRICTION …).
    auto applyMandatory = [](const ContactAction& a, const std::string& keyword, ContactDef& d, std::string& err) -> bool {
        const ct_CardSpec sp = ct_cardSpec(keyword);
        const std::string kw = "*CONTACT_" + kw_upper(keyword);
        if (!sp.known) { err = kw + " — " + sp.why + ". 이 키워드의 필수 카드를 KooRemapper 는 쓰지 못한다"; return false; }
        if (sp.orfr > 0) { err = kw + " — ORFR 1-4(직교 마찰) 카드를 KooRemapper 는 쓰지 못한다"; return false; }
        if (sp.tiebreakAuto) {
            // 매뉴얼 Card 4 의 OPTION · NFLS · SFLS 는 required(기본값 없음, V68117-68150).
            if (!a.tb_option) {
                err = kw + " — option 을 주어야 한다(매뉴얼 Card 4 의 OPTION · NFLS · SFLS 는 required). "
                      "1 = 닿은 절점이 영구히 붙는다(파손 없음) · 2 = 처음 닿은 절점이 파손 때까지 붙는다 · "
                      "4 = 같고 마찰 미끄럼 허용 · 9/11 = 응집 혼합 모드 …";
                return false;
            }
            const int opt = *a.tb_option;
            if (opt == 13 || opt == 14) { err = kw + " — OPTION 13/14 는 Card 4.1b · 4.2b 가 더 필요하다(지원하지 않는다)"; return false; }
            // 매뉴얼 Remark 2 — SOFT=2 는 tiebreak 에 구현돼 있지 않고, SINGLE_SURFACE · GENERAL TIEBREAK 는 OPTION 1~5 만.
            if (a.soft && *a.soft == 2) { err = kw + " — SOFT=2(세그먼트 대 세그먼트)는 tiebreak 에 구현돼 있지 않다(매뉴얼 Remark 2)"; return false; }
            {
                const std::string ku = kw_upper(keyword);
                const bool singleOrGeneral = ku.find("SINGLE_SURFACE_TIEBREAK") != std::string::npos ||
                                             ku.find("GENERAL_TIEBREAK") != std::string::npos;
                if (singleOrGeneral && (opt < 1 || opt > 5)) {
                    err = kw + " — SINGLE_SURFACE · GENERAL TIEBREAK 은 OPTION 1~5 만 지원된다(매뉴얼 Remark 2)"; return false;
                }
            }
            if (sp.damping && (opt == 9 || opt == -9 || opt == 11 || opt == -11)) {
                err = kw + " — DAMPING 과 OPTION ±9/±11 은 Card 4.1a 가 더 필요하다(지원하지 않는다)"; return false;
            }
            // 파손 OPTION 에 응력을 안 주면 0 이라 곧바로 떨어진다 — 받아야 쓴다.
            if (opt != 1 && (!a.tb_nfls || !a.tb_sfls)) {
                err = kw + " — OPTION " + std::to_string(opt) + " 은 파손 응력을 쓴다: nfls · sfls 를 주어야 한다(안 주면 0 이라 곧바로 떨어진다)";
                return false;
            }
            d.hasTiebreak = true;
            d.tbOption = opt;
            if (a.tb_nfls) d.tbNfls = *a.tb_nfls;
            if (a.tb_sfls) d.tbSfls = *a.tb_sfls;
            if (a.tb_param) d.tbParam = *a.tb_param;
            if (a.tb_eraten) d.tbEraten = *a.tb_eraten;
            if (a.tb_erates) d.tbErates = *a.tb_erates;
            if (a.tb_ct2cn) d.tbCt2cn = *a.tb_ct2cn;
        }
        if (sp.eroding) d.hasEroding = true;
        if (sp.thrm > 0) {
            d.hasThermal = true;
            if (a.th_k) d.thK = *a.th_k;
            if (a.th_frad) d.thFrad = *a.th_frad;
            if (a.th_h0) d.thH0 = *a.th_h0;
            if (a.th_lmin) d.thLmin = *a.th_lmin;
            if (a.th_lmax) d.thLmax = *a.th_lmax;
            if (a.th_ftosa) d.thFtosa = *a.th_ftosa;
            if (a.th_bcflag) d.thBcflag = *a.th_bcflag;
            if (a.th_algo) d.thAlgo = *a.th_algo;
        }
        return true;
    };

    // 5. Process actions
    std::vector<std::string> insertBlocks;   // blocks to insert before *END
    std::vector<int> removeIdx;   // 지울 접촉 번호(맨 끝에 다시 읽어 그 범위를 지운다)
    bool modified = false;
    bool analyzeOnly = true;

    for (size_t ai = 0; ai < actions.size(); ++ai) {
        const auto& act = actions[ai];

        // ── analyze ──
        if (act.action == "analyze") {
            ct_analyze(contacts, sets, mesh, console);
            continue;
        }

        analyzeOnly = false;

        // ── create ──
        if (act.action == "create") {
            std::string ctype = act.type;
            for (auto& c : ctype) if (c == '-') c = '_';
            // 짧은 이름 → 전체 키워드. assemble 의 contact create 가 쓰는 바로 그 표(ct_getPreset)를
            // 같이 쓴다 — 예전엔 여기서만 별칭 tied_thermal/thermal/tiebreak 만 풀고 나머지는 대문자로
            // 바꿔 그대로 붙여, 같은 'type: auto' 가 assemble 에선 AUTOMATIC_SURFACE_TO_SURFACE,
            // 단독 contact 에선 없는 키워드 AUTO 가 됐다. 전체 키워드로 쓴 값은 그대로 통과한다.
            ctype = ct_getPreset(ctype).keyword;

            // 표에 없는 값은 ct_getPreset 이 대문자로 바꿔 그대로 돌려준다 — examples/contact/README.md 가
            // 약속한 통과 규칙이므로 막지 않고, 아는 키워드 목록에 없을 때만 경고를 찍는다(assemble 과 같은 목록).
            // 한동안 목록 밖을 rc=1 로 막았는데, LS-DYNA 접촉 키워드는 목록보다 훨씬 많아
            // forming_one_way_surface_to_surface·automatic_nodes_to_surface 처럼 멀쩡한 값이 함께 막혔다.
            if (!KooRemapper::ctKnownContactKeyword(ctype))
                console.warning(KooRemapper::ctUnknownContactKeywordWarning(act.type, ctype));

            int ssid = 0, msid = 0, sstyp = 0, mstyp = 0;

            // Facing filter: when both slave and master have as_segment+facing,
            // use detect algorithm to extract only mutually facing segments
            bool useFacingFilter = (act.slave.asSegment && act.slave.facing &&
                                    act.master.asSegment && act.master.facing &&
                                    act.slave.pid > 0 && act.master.pid > 0);

            if (useFacingFilter) {
                double tol = act.detectTolerance;
                double angle = act.detectNormalAngle;
                auto slaveFacesAll = ct_extractSurface(mesh, act.slave.pid);
                auto masterFacesAll = ct_extractSurface(mesh, act.master.pid);
                if (slaveFacesAll.empty() || masterFacesAll.empty()) {
                    console.warning("[contact] No surface found for facing filter (slave:" +
                        std::to_string(act.slave.pid) + " master:" + std::to_string(act.master.pid) + ")");
                } else {
                    auto pairs = ct_detectContacting(slaveFacesAll, masterFacesAll, mesh,
                        act.slave.pid, act.master.pid, tol, angle);
                    if (pairs.empty()) {
                        console.warning("[contact] No facing segments found between PID " +
                            std::to_string(act.slave.pid) + " and PID " + std::to_string(act.master.pid));
                    } else {
                        // Collect unique facing faces for each side
                        std::set<int> sIdxSet, mIdxSet;
                        for (const auto& p : pairs) { sIdxSet.insert(p.faceA); mIdxSet.insert(p.faceB); }
                        std::vector<std::array<int,4>> sFaces, mFaces;
                        for (int idx : sIdxSet) sFaces.push_back(slaveFacesAll[idx]);
                        for (int idx : mIdxSet) mFaces.push_back(masterFacesAll[idx]);

                        ssid = ids.issue(KooRemapper::ids::Ns::Set);
                        insertBlocks.push_back(ct_generateSetSegment(ssid, sFaces,
                            "Slave_PID" + std::to_string(act.slave.pid) + "_facing"));
                        sstyp = 0;
                        msid = ids.issue(KooRemapper::ids::Ns::Set);
                        insertBlocks.push_back(ct_generateSetSegment(msid, mFaces,
                            "Master_PID" + std::to_string(act.master.pid) + "_facing"));
                        mstyp = 0;
                        console.println("[contact] Facing filter: " +
                            std::to_string(slaveFacesAll.size()) + " -> " + std::to_string(sFaces.size()) +
                            " slave, " + std::to_string(masterFacesAll.size()) + " -> " +
                            std::to_string(mFaces.size()) + " master segments");
                    }
                }
            } else {
            // Determine slave side
            if (act.slave.asSegment && act.slave.pid > 0) {
                // Extract surface → SET_SEGMENT
                auto faces = ct_extractSurface(mesh, act.slave.pid);
                if (faces.empty()) {
                    console.warning("[contact] No surface found for slave PID " +
                                std::to_string(act.slave.pid));
                } else {
                    ssid = ids.issue(KooRemapper::ids::Ns::Set);
                    insertBlocks.push_back(ct_generateSetSegment(ssid, faces,
                        "Slave_PID" + std::to_string(act.slave.pid)));
                    sstyp = 0;
                    console.println("[contact] Created SET_SEGMENT " + std::to_string(ssid) +
                                  " (" + std::to_string(faces.size()) + " faces) for slave PID " +
                                  std::to_string(act.slave.pid));
                }
            } else if (!act.slave.pids.empty()) {
                // Multiple PIDs → SET_PART
                ssid = ids.issue(KooRemapper::ids::Ns::Set);
                insertBlocks.push_back(ct_generateSetPart(ssid, act.slave.pids, "Slave_parts"));
                sstyp = 2;
                console.println("[contact] Created SET_PART " + std::to_string(ssid) +
                              " (" + std::to_string(act.slave.pids.size()) + " parts) for slave");
            } else if (act.slave.pid > 0) {
                // Single PID → direct SSTYP=3
                ssid = act.slave.pid;
                sstyp = 3;
            }

            // Determine master side (similar logic)
            if (act.master.asSegment && act.master.pid > 0) {
                auto faces = ct_extractSurface(mesh, act.master.pid);
                if (faces.empty()) {
                    console.warning("[contact] No surface found for master PID " +
                                std::to_string(act.master.pid));
                } else {
                    msid = ids.issue(KooRemapper::ids::Ns::Set);
                    insertBlocks.push_back(ct_generateSetSegment(msid, faces,
                        "Master_PID" + std::to_string(act.master.pid)));
                    mstyp = 0;
                    console.println("[contact] Created SET_SEGMENT " + std::to_string(msid) +
                                  " (" + std::to_string(faces.size()) + " faces) for master PID " +
                                  std::to_string(act.master.pid));
                }
            } else if (!act.master.pids.empty()) {
                msid = ids.issue(KooRemapper::ids::Ns::Set);
                insertBlocks.push_back(ct_generateSetPart(msid, act.master.pids, "Master_parts"));
                mstyp = 2;
                console.println("[contact] Created SET_PART " + std::to_string(msid) +
                              " (" + std::to_string(act.master.pids.size()) + " parts) for master");
            } else if (act.master.pid > 0) {
                msid = act.master.pid;
                mstyp = 3;
            }
            } // end else (not useFacingFilter)

            // For single surface types, master is unused
            bool isSingle = (ctype.find("SINGLE_SURFACE") != std::string::npos);
            if (isSingle) {
                // Slave only — if pids given, use SET_PART
                if (!act.slave.pids.empty() && sstyp != 2) {
                    ssid = ids.issue(KooRemapper::ids::Ns::Set);
                    insertBlocks.push_back(ct_generateSetPart(ssid, act.slave.pids, "SingleSurf_parts"));
                    sstyp = 2;
                }
                msid = 0; mstyp = 0;
            }

            // Build ContactDef from action
            ContactDef newDef;
            newDef.type = ctype;
            newDef.ssid = ssid; newDef.msid = msid;
            newDef.sstyp = sstyp; newDef.mstyp = mstyp;
            newDef.title = act.title.empty() ? ("Contact_" + std::to_string(ai)) : act.title;
            // 제목이 있으면 `_ID` 카드로 나가므로 CID 가 필요하다(`ct_generateContact` 참조).
            newDef.cid = ids.issue(KooRemapper::ids::Ns::Contact);
            applyCard123(act, newDef);
            applyOptional(act, newDef);
            {
                std::string err;
                if (!applyMandatory(act, ctype, newDef, err)) { console.error("[contact] create: " + err); return 1; }
            }

            insertBlocks.push_back(ct_generateContact(newDef));
            console.println("[contact] Created *CONTACT_" + ctype +
                          (act.title.empty() ? "" : " (" + act.title + ")"));
            modified = true;
            continue;
        }

        // ── convert ──
        if (act.action == "convert") {
            if (act.contactIndex < 0 || act.contactIndex >= (int)contacts.size()) {
                console.error("[contact] Invalid contact_index: " + std::to_string(act.contactIndex));
                return 1;
            }
            auto& ct = contacts[act.contactIndex];

            // Helper: collect face list from a contact side.
            // Handles sstyp=3 (direct PID), sstyp=2 (SET_PART), sstyp=0 (SET_SEGMENT).
            // 세트는 정본 해석기로 푼다(`_ADD`·`_INTERSECT`·`_COLLECT`). 못 풀면 **말하고** 빈 목록 —
            // 예전엔 `*SET_PART_ADD` 면이 말없이 0개였고 `*SET_SEGMENT_ADD` 는 세트 ID 를 절점으로 읽었다.
            auto collectFaces = [&](int sid, int styp) -> std::vector<std::array<int,4>> {
                if (styp == 3) return ct_extractSurface(mesh, sid);
                if (styp == 2 || styp == 0) {
                    const SetMembers m = ct_setMembers(sets, sid, styp == 2 ? "PART" : "SEGMENT");
                    if (!m.found) return {};
                    if (!m.resolved) {
                        console.warning("[contact] " + m.why + " — 이 면을 모으지 않는다");
                        return {};
                    }
                    if (styp == 0) return m.segments;
                    std::vector<std::array<int,4>> result;
                    for (int pid : m.ids) {
                        auto f = ct_extractSurface(mesh, pid);
                        result.insert(result.end(), f.begin(), f.end());
                    }
                    return result;
                }
                return {};
            };

            // Facing filter: detect only mutually facing segments
            bool convertBothSegment = (act.slaveTo == "segment" && act.masterTo == "segment");
            if (act.convertFacing && convertBothSegment) {
                double tol = act.detectTolerance;
                double angle = act.detectNormalAngle;
                auto slaveFacesAll = collectFaces(ct.ssid, ct.sstyp);
                auto masterFacesAll = collectFaces(ct.msid, ct.mstyp);
                if (slaveFacesAll.empty() || masterFacesAll.empty()) {
                    console.warning("[contact] No faces for facing filter (contact [" +
                        std::to_string(act.contactIndex) + "] sstyp=" +
                        std::to_string(ct.sstyp) + " mstyp=" + std::to_string(ct.mstyp) + ")");
                } else {
                    // Representative PIDs (0 for SET_SEGMENT; only used for tagging)
                    int sPid = (ct.sstyp == 3) ? ct.ssid : 0;
                    int mPid = (ct.mstyp == 3) ? ct.msid : 1;
                    auto pairs = ct_detectContacting(slaveFacesAll, masterFacesAll, mesh,
                        sPid, mPid, tol, angle);
                    if (pairs.empty()) {
                        console.warning("[contact] No facing segments found for contact [" +
                            std::to_string(act.contactIndex) + "]");
                    } else {
                        std::set<int> sIdxSet, mIdxSet;
                        for (const auto& p : pairs) { sIdxSet.insert(p.faceA); mIdxSet.insert(p.faceB); }
                        std::vector<std::array<int,4>> sFaces, mFaces;
                        for (int idx : sIdxSet) sFaces.push_back(slaveFacesAll[idx]);
                        for (int idx : mIdxSet) mFaces.push_back(masterFacesAll[idx]);

                        int newSsid = ids.issue(KooRemapper::ids::Ns::Set);
                        insertBlocks.push_back(ct_generateSetSegment(newSsid, sFaces,
                            "Slave_facing"));
                        int newMsid = ids.issue(KooRemapper::ids::Ns::Set);
                        insertBlocks.push_back(ct_generateSetSegment(newMsid, mFaces,
                            "Master_facing"));
                        ct_modifyContactCard1(lines, ct, newSsid, newMsid, 0, 0);
                        console.println("[contact] [" + std::to_string(act.contactIndex) +
                            "] Facing filter: slave " + std::to_string(slaveFacesAll.size()) +
                            " -> " + std::to_string(sFaces.size()) +
                            ", master " + std::to_string(masterFacesAll.size()) +
                            " -> " + std::to_string(mFaces.size()) + " segments");
                        ct.ssid = newSsid; ct.sstyp = 0;
                        ct.msid = newMsid; ct.mstyp = 0;
                        modified = true;
                    }
                }
                continue;
            }

            // Convert slave to segment
            if (act.slaveTo == "segment" && ct.sstyp == 3) {
                auto faces = ct_extractSurface(mesh, ct.ssid);
                if (faces.empty()) {
                    console.warning("[contact] No surface for slave PID " + std::to_string(ct.ssid));
                } else {
                    int newSid = ids.issue(KooRemapper::ids::Ns::Set);
                    insertBlocks.push_back(ct_generateSetSegment(newSid, faces,
                        "Slave_PID" + std::to_string(ct.ssid)));
                    ct_modifyContactCard1(lines, ct, newSid, ct.msid, 0, ct.mstyp);
                    console.println("[contact] [" + std::to_string(act.contactIndex) +
                                  "] Slave PID " + std::to_string(ct.ssid) +
                                  " -> SET_SEGMENT " + std::to_string(newSid) +
                                  " (" + std::to_string(faces.size()) + " faces)");
                    ct.ssid = newSid;
                    ct.sstyp = 0;
                    modified = true;
                }
            } else if (act.slaveTo == "segment" && ct.sstyp == 2) {
                // Part set → expand to segment — 정본 해석기로 멤버를 푼다(못 풀면 바꾸지 않고 말한다)
                const SetMembers sm = ct_setMembers(sets, ct.ssid, "PART");
                if (sm.found && !sm.resolved)
                    console.warning("[contact] [" + std::to_string(act.contactIndex) + "] " + sm.why +
                                    " — 슬레이브를 세그먼트로 바꾸지 않는다");
                if (sm.resolved) {
                    std::vector<std::array<int,4>> allFaces;
                    for (int pid : sm.ids) {
                        auto faces = ct_extractSurface(mesh, pid);
                        allFaces.insert(allFaces.end(), faces.begin(), faces.end());
                    }
                    if (!allFaces.empty()) {
                        int newSid = ids.issue(KooRemapper::ids::Ns::Set);
                        insertBlocks.push_back(ct_generateSetSegment(newSid, allFaces,
                            "Slave_expanded"));
                        ct_modifyContactCard1(lines, ct, newSid, ct.msid, 0, ct.mstyp);
                        console.println("[contact] [" + std::to_string(act.contactIndex) +
                                      "] Slave SET_PART " + std::to_string(ct.ssid) +
                                      " -> SET_SEGMENT " + std::to_string(newSid) +
                                      " (" + std::to_string(allFaces.size()) + " faces)");
                        ct.ssid = newSid;
                        ct.sstyp = 0;
                        modified = true;
                    }
                }
            }

            // Convert master to segment
            if (act.masterTo == "segment" && ct.mstyp == 3) {
                auto faces = ct_extractSurface(mesh, ct.msid);
                if (faces.empty()) {
                    console.warning("[contact] No surface for master PID " + std::to_string(ct.msid));
                } else {
                    int newSid = ids.issue(KooRemapper::ids::Ns::Set);
                    insertBlocks.push_back(ct_generateSetSegment(newSid, faces,
                        "Master_PID" + std::to_string(ct.msid)));
                    ct_modifyContactCard1(lines, ct, ct.ssid, newSid, ct.sstyp, 0);
                    console.println("[contact] [" + std::to_string(act.contactIndex) +
                                  "] Master PID " + std::to_string(ct.msid) +
                                  " -> SET_SEGMENT " + std::to_string(newSid) +
                                  " (" + std::to_string(faces.size()) + " faces)");
                    ct.msid = newSid;
                    ct.mstyp = 0;
                    modified = true;
                }
            } else if (act.masterTo == "segment" && ct.mstyp == 2) {
                // Part set → expand to segment — 슬레이브와 같은 규칙
                const SetMembers mm = ct_setMembers(sets, ct.msid, "PART");
                if (mm.found && !mm.resolved)
                    console.warning("[contact] [" + std::to_string(act.contactIndex) + "] " + mm.why +
                                    " — 마스터를 세그먼트로 바꾸지 않는다");
                if (mm.resolved) {
                    std::vector<std::array<int,4>> allFaces;
                    for (int pid : mm.ids) {
                        auto faces = ct_extractSurface(mesh, pid);
                        allFaces.insert(allFaces.end(), faces.begin(), faces.end());
                    }
                    if (!allFaces.empty()) {
                        int newSid = ids.issue(KooRemapper::ids::Ns::Set);
                        insertBlocks.push_back(ct_generateSetSegment(newSid, allFaces,
                            "Master_expanded"));
                        ct_modifyContactCard1(lines, ct, ct.ssid, newSid, ct.sstyp, 0);
                        console.println("[contact] [" + std::to_string(act.contactIndex) +
                                      "] Master SET_PART " + std::to_string(ct.msid) +
                                      " -> SET_SEGMENT " + std::to_string(newSid) +
                                      " (" + std::to_string(allFaces.size()) + " faces)");
                        ct.msid = newSid;
                        ct.mstyp = 0;
                        modified = true;
                    }
                }
            }
            continue;
        }

        // ── modify ──
        if (act.action == "modify") {
            if (act.contactIndex < 0 || act.contactIndex >= (int)contacts.size()) {
                console.error("[contact] Invalid contact_index: " + std::to_string(act.contactIndex));
                return 1;
            }
            auto& ct = contacts[act.contactIndex];
            const std::string where = "[contact] [" + std::to_string(act.contactIndex) + "] ";
            std::string modFields;

            // 카드 1 · 2 · 3 칸 — 파서가 찾은 줄에 그 자리 그대로(직접 세지 않는다 · 빈 줄 · MPP 카드를 안다).
            // ⚠ 예전엔 Card 1 확장 칸(sboxid · mboxid · spr · mpr)을 받아 놓고 아무것도 안 하면서 「Modified:」 를 찍었고,
            //   Card 2 · 3 은 `%10.2f` 로 반올림해 썼다(마찰 0.125 → 0.13).
            auto setCard = [&](int card, int field, const std::string& text, const char* name) -> bool {
                if (ct_setCardField(lines, ct, card, field, text)) return true;
                console.error(where + "Card " + std::to_string(card + 1) + " 이 덱에 없어 " + name + " 를 고칠 수 없다");
                return false;
            };
            struct RealField { const OD* v; int card; int field; const char* fmt; const char* name; };
            struct IntField { const OI* v; int card; int field; const char* name; };
            const RealField reals[] = {
                {&act.friction, 1, 0, "%10.2f", "FS"}, {&act.fd, 1, 1, "%10.2f", "FD"}, {&act.dc, 1, 2, "%10.2f", "DC"},
                {&act.vc, 1, 3, "%10.2f", "VC"}, {&act.vdc, 1, 4, "%10.2f", "VDC"}, {&act.bt, 1, 6, "%10.2f", "BT"},
                {&act.dt, 1, 7, "%10.3E", "DT"},
                {&act.sfsa, 2, 0, "%10.2f", "SFSA"}, {&act.sfsb, 2, 1, "%10.2f", "SFSB"}, {&act.sast, 2, 2, "%10.2f", "SAST"},
                {&act.sbst, 2, 3, "%10.2f", "SBST"}, {&act.sfsat, 2, 4, "%10.2f", "SFSAT"}, {&act.sfsbt, 2, 5, "%10.2f", "SFSBT"},
                {&act.fsf, 2, 6, "%10.2f", "FSF"}, {&act.vsf, 2, 7, "%10.2f", "VSF"},
            };
            const IntField ints[] = {
                {&act.sboxid, 0, 4, "SBOXID"}, {&act.mboxid, 0, 5, "MBOXID"}, {&act.spr, 0, 6, "SPR"}, {&act.mpr, 0, 7, "MPR"},
                {&act.penchk, 1, 5, "PENCHK"},
            };
            for (const auto& f : ints) {
                if (!*f.v) continue;
                if (!setCard(f.card, f.field, std::to_string(**f.v), f.name)) return 1;
                modFields += std::string(" ") + f.name + "=" + std::to_string(**f.v);
            }
            for (const auto& f : reals) {
                if (!*f.v) continue;
                const std::string txt = ct_real(**f.v, f.fmt);
                if (!setCard(f.card, f.field, txt, f.name)) return 1;
                modFields += std::string(" ") + f.name + "=" + kw_trim(txt);
            }

            // 필수 카드(THRM 1 · TIEBREAK Card 4)의 칸 — 그 카드가 있는 접촉에서만. ⚠ 예전엔 이 키들을 modify 에서
            // 받고 조용히 무시했다.
            {
                const bool thermalKeys = act.th_k || act.th_frad || act.th_h0 || act.th_lmin || act.th_lmax ||
                                         act.th_ftosa || act.th_bcflag || act.th_algo;
                const bool tiebreakKeys = act.tb_option || act.tb_nfls || act.tb_sfls || act.tb_param ||
                                          act.tb_eraten || act.tb_erates || act.tb_ct2cn;
                auto editLine = [&](int ln, int field, const std::string& text) { lines[ln] = kw_setField(lines[ln], field * 10, 10, text); };
                if (thermalKeys) {
                    if (ct.thrmLines.empty()) { console.error(where + "THRM 1 카드가 없는 접촉이다 — 열 칸(k · frad · …)을 고칠 수 없다"); return 1; }
                    const int ln = ct.thrmLines[0];
                    const std::pair<const OD*, int> rf[] = {{&act.th_k, 0}, {&act.th_frad, 1}, {&act.th_h0, 2}, {&act.th_lmin, 3},
                                                            {&act.th_lmax, 4}, {&act.th_ftosa, 5}};
                    for (const auto& [v, fld] : rf) if (*v) editLine(ln, fld, ct_real(**v, "%10.3g"));
                    if (act.th_bcflag) editLine(ln, 6, std::to_string(*act.th_bcflag));
                    if (act.th_algo) editLine(ln, 7, std::to_string(*act.th_algo));
                    modFields += " THRM1";
                }
                if (tiebreakKeys) {
                    if (!ct.hasTiebreak || ct.card4Lines.empty()) {
                        console.error(where + "AUTOMATIC_…_TIEBREAK Card 4 가 없는 접촉이다 — option · nfls · … 를 고칠 수 없다"); return 1;
                    }
                    const int ln = ct.card4Lines[0];
                    if (act.tb_option) editLine(ln, 0, std::to_string(*act.tb_option));
                    const std::pair<const OD*, int> rf[] = {{&act.tb_nfls, 1}, {&act.tb_sfls, 2}, {&act.tb_param, 3},
                                                            {&act.tb_eraten, 4}, {&act.tb_erates, 5}, {&act.tb_ct2cn, 6}};
                    for (const auto& [v, fld] : rf) if (*v) editLine(ln, fld, ct_real(**v, "%10.3g"));
                    modFields += " Card4";
                }
            }

            // 선택 카드 A~G — 읽은 값에 YAML 값을 얹어 선택 카드 줄만 다시 쓴다(Card 4 · THRM · ORFR 는 그대로).
            if (anyOptional(act)) {
                ContactDef merged = ct;
                applyOptional(act, merged);
                std::string why;
                if (!ct_modifyOptionalCards(lines, ct, merged, &why)) {
                    console.error(where + "선택 카드를 고치지 않았다 — " + why);
                    return 1;
                }
                modFields += " OptCards";
            }

            if (modFields.empty()) {
                console.warning(where + "modify 에 고칠 칸이 없다 — 아무것도 바꾸지 않았다");
                continue;
            }
            // 줄이 바뀌었다 — 뒤 액션이 낡은 자리 · 값을 보지 않게 다시 읽는다
            contacts = ct_parseContacts(lines);
            sets = ct_parseSets(lines);
            ct_resolveSetRanges(sets, mesh);
            console.println(where + "Modified:" + modFields);
            modified = true;
            continue;
        }

        // ── remove ──
        if (act.action == "remove") {
            if (act.contactIndex < 0 || act.contactIndex >= (int)contacts.size()) {
                console.error("[contact] Invalid contact_index: " + std::to_string(act.contactIndex));
                return 1;
            }
            auto& ct = contacts[act.contactIndex];
            console.println("[contact] Removing [" + std::to_string(act.contactIndex) +
                          "] " + ct.fullKeyword);
            // ⚠ 줄 범위가 아니라 **접촉 번호**를 기억한다 — 뒤의 modify 가 선택 카드를 넣어 줄이 밀리면 예전엔 적어 둔 범위가
            //   낡아 **다른 줄을 지웠다**(D21). 지우기는 맨 끝에 다시 읽어 그 번호의 범위로 한다(번호는 그동안 안 바뀐다 —
            //   새 접촉은 맨 끝 `*END` 앞에 붙는다).
            if (std::find(removeIdx.begin(), removeIdx.end(), act.contactIndex) == removeIdx.end())
                removeIdx.push_back(act.contactIndex);
            modified = true;
            continue;
        }

        // ── detect ──
        if (act.action == "detect") {
            analyzeOnly = false;
            double tol = act.detectTolerance;
            double nAngle = act.detectNormalAngle;
            auto preset = ct_getPreset(act.contactType);
            std::string prefix = act.titlePrefix.empty() ? "Auto" : act.titlePrefix;
            // 접촉을 만들 거면 필수 카드(THRM · Card 4)를 쓸 수 있는지 먼저 본다 — 쓸 수 없으면 세트도 만들지 않고 멈춘다.
            if (act.detectAutoCreate) {
                ContactDef probe;
                std::string err;
                if (!applyMandatory(act, preset.keyword, probe, err)) { console.error("[contact] detect: " + err); return 1; }
            }

            bool autoMode = (act.scope == "all" || !act.includeKeys.empty());

            if (autoMode) {
                // --- Automatic mode: scope/include/exclude ---
                auto sel = ct_selectParts(mesh, act.scope, act.includeKeys, act.excludeKeys);
                if (sel.targetPids.empty()) {
                    console.warning("[contact] detect: no target parts matched");
                    continue;
                }

                int excludeCount = (int)mesh.getParts().size() -
                    (int)std::set<int>(sel.counterPids.begin(), sel.counterPids.end()).size();
                console.println("[contact] Part selection: " +
                    std::to_string(sel.targetPids.size()) + " target, " +
                    std::to_string(sel.counterPids.size()) + " counter" +
                    (excludeCount > 0 ? " (" + std::to_string(excludeCount) + " excluded)" : ""));

                // Extract surfaces for all relevant PIDs
                std::set<int> allPids(sel.targetPids.begin(), sel.targetPids.end());
                allPids.insert(sel.counterPids.begin(), sel.counterPids.end());
                auto surfMap = ct_extractAllSurfaces(mesh,
                    std::vector<int>(allPids.begin(), allPids.end()));

                int totalFaces = 0;
                for (const auto& [pid, f] : surfMap) totalFaces += (int)f.size();
                // 세그먼트 → 그 면을 가진 파트 — SET_SEGMENT 로 정의된 기존 접촉(detect 가 만든 것 전부)을 파트 쌍으로 비교한다(D13).
                const ct_SegOwners segOwners = ct_segmentOwners(surfMap);
                console.println("[contact] Extracted surfaces: " +
                    std::to_string(totalFaces) + " total faces");

                // Run all-pairs detection
                auto pairResults = ct_detectAllPairs(surfMap, sel.targetPids,
                    sel.counterPids, mesh, tol, nAngle);

                if (pairResults.empty()) {
                    console.println("[contact] No contacting pairs found");
                    continue;
                }

                console.println("[contact] Detected " +
                    std::to_string(pairResults.size()) + " contacting pair(s):");

                int createdContacts = 0;
                int skippedPairs = 0;
                int subtractedPairs = 0;
                for (const auto& pr : pairResults) {
                    // Get part names
                    std::string nameA, nameB;
                    auto itA = mesh.getParts().find(pr.pidA);
                    auto itB = mesh.getParts().find(pr.pidB);
                    if (itA != mesh.getParts().end()) nameA = itA->second.name;
                    if (itB != mesh.getParts().end()) nameB = itB->second.name;
                    if (nameA.empty()) nameA = "PID" + std::to_string(pr.pidA);
                    if (nameB.empty()) nameB = "PID" + std::to_string(pr.pidB);

                    // skip_existing: skip this pair if existing contact covers it
                    if (!act.skipExisting.empty()) {
                        if (ct_pairHasExisting(pr.pidA, pr.pidB, contacts, sets, act.skipExisting, &segOwners)) {
                            console.println("  PID " + std::to_string(pr.pidA) +
                                " (" + nameA + ") <-> PID " + std::to_string(pr.pidB) +
                                " (" + nameB + "): skipped (existing " + act.skipExisting + ")");
                            skippedPairs++;
                            continue;
                        }
                    }

                    // Determine final face lists (possibly with subtraction)
                    auto facesA = pr.contactFacesA;
                    auto facesB = pr.contactFacesB;

                    // subtract_existing: remove tied segments from detected faces
                    if (act.subtractExisting) {
                        auto [tiedA, tiedB] = ct_getExistingTiedSegments(
                            pr.pidA, pr.pidB, contacts, sets, mesh, tol, nAngle, &segOwners);
                        if (!tiedA.empty() || !tiedB.empty()) {
                            auto newA = ct_subtractFaces(facesA, tiedA);
                            auto newB = ct_subtractFaces(facesB, tiedB);
                            if (newA.empty() && newB.empty()) {
                                console.println("  PID " + std::to_string(pr.pidA) +
                                    " (" + nameA + ") <-> PID " + std::to_string(pr.pidB) +
                                    " (" + nameB + "): all segments tied, skipped");
                                skippedPairs++;
                                continue;
                            }
                            console.println("  PID " + std::to_string(pr.pidA) +
                                " (" + nameA + ") <-> PID " + std::to_string(pr.pidB) +
                                " (" + nameB + "): subtracted " +
                                std::to_string(facesA.size() - newA.size()) + "/" +
                                std::to_string(facesB.size() - newB.size()) + " tied segments");
                            facesA = std::move(newA);
                            facesB = std::move(newB);
                            subtractedPairs++;
                        }
                    }

                    char gapBuf[128];
                    snprintf(gapBuf, sizeof(gapBuf), "gap %.3f~%.3f",
                             pr.gapMin, pr.gapMax);
                    console.println("  PID " + std::to_string(pr.pidA) +
                        " (" + nameA + ") <-> PID " + std::to_string(pr.pidB) +
                        " (" + nameB + "): " +
                        std::to_string((int)facesA.size()) + "/" +
                        std::to_string((int)facesB.size()) +
                        " segments, " + gapBuf);

                    // Create SET_SEGMENTs
                    int slaveSid = ids.issue(KooRemapper::ids::Ns::Set);
                    int masterSid = ids.issue(KooRemapper::ids::Ns::Set);
                    insertBlocks.push_back(ct_generateSetSegment(slaveSid,
                        facesA,
                        prefix + "_S_" + nameA));
                    insertBlocks.push_back(ct_generateSetSegment(masterSid,
                        facesB,
                        prefix + "_M_" + nameB));
                    modified = true;

                    if (act.detectAutoCreate) {
                        ContactDef def{};
                        def.type = preset.keyword;
                        def.fullKeyword = "*CONTACT_" + preset.keyword;
                        def.hasTitle = true;
                        def.title = prefix + "_" + nameA + "_" + nameB;
                        def.cid = ids.issue(KooRemapper::ids::Ns::Contact);   // `_ID` 카드로 나간다
                        def.ssid = slaveSid;
                        def.msid = preset.needMasterSide ? masterSid : 0;
                        def.sstyp = 0; // SET_SEGMENT
                        def.mstyp = preset.needMasterSide ? 0 : 0;
                        applyCard123(act, def);
                        applyOptional(act, def);
                        {
                            std::string err;
                            if (!applyMandatory(act, preset.keyword, def, err)) { console.error("[contact] detect: " + err); return 1; }
                        }
                        insertBlocks.push_back(ct_generateContact(def));
                        createdContacts++;
                    }
                }

                if (act.detectAutoCreate || skippedPairs > 0 || subtractedPairs > 0) {
                    std::string summary = "[contact] Created " +
                        std::to_string(createdContacts) + " contacts";
                    if (skippedPairs > 0)
                        summary += ", " + std::to_string(skippedPairs) + " skipped";
                    if (subtractedPairs > 0)
                        summary += ", " + std::to_string(subtractedPairs) + " subtracted";
                    console.println(summary);
                }
            } else {
                // --- Explicit PID mode (backward compatible) ---
                std::vector<std::array<int,4>> slaveFaces, masterFaces;
                int slavePid = act.slave.pid;
                int masterPid = act.master.pid;

                if (!act.slave.pids.empty()) {
                    std::vector<std::vector<std::array<int,4>>> perPid;
                    for (int p : act.slave.pids) perPid.push_back(ct_extractSurface(mesh, p));
                    slaveFaces = ct_mergeFaces(perPid);
                    slavePid = act.slave.pids[0]; // representative
                } else if (slavePid > 0) {
                    slaveFaces = ct_extractSurface(mesh, slavePid);
                }

                if (!act.master.pids.empty()) {
                    std::vector<std::vector<std::array<int,4>>> perPid;
                    for (int p : act.master.pids) perPid.push_back(ct_extractSurface(mesh, p));
                    masterFaces = ct_mergeFaces(perPid);
                    masterPid = act.master.pids[0];
                } else if (masterPid > 0) {
                    masterFaces = ct_extractSurface(mesh, masterPid);
                }

                if (slaveFaces.empty() || masterFaces.empty()) {
                    console.warning("[contact] detect: empty surface(s)");
                    continue;
                }

                console.println("[contact] Detecting: " +
                    std::to_string(slaveFaces.size()) + " slave faces x " +
                    std::to_string(masterFaces.size()) + " master faces" +
                    "  tol=" + std::to_string(tol) +
                    "  angle=" + std::to_string(nAngle));

                auto pairs = ct_detectContacting(slaveFaces, masterFaces, mesh,
                                                  slavePid, masterPid, tol, nAngle);

                if (pairs.empty()) {
                    console.println("[contact] No contacting segments found");
                    continue;
                }

                // Collect unique faces
                std::set<int> usedS, usedM;
                double gMin = 1e30, gMax = 0, gSum = 0;
                for (const auto& cp : pairs) {
                    usedS.insert(cp.faceA);
                    usedM.insert(cp.faceB);
                    if (cp.gap < gMin) gMin = cp.gap;
                    if (cp.gap > gMax) gMax = cp.gap;
                    gSum += cp.gap;
                }
                double gAvg = pairs.empty() ? 0 : gSum / pairs.size();

                std::vector<std::array<int,4>> sFaces, mFaces;
                for (int i : usedS) sFaces.push_back(slaveFaces[i]);
                for (int j : usedM) mFaces.push_back(masterFaces[j]);

                char gapBuf[128];
                snprintf(gapBuf, sizeof(gapBuf),
                         "gap min=%.4f max=%.4f avg=%.4f", gMin, gMax, gAvg);
                console.println("[contact] Found " +
                    std::to_string(pairs.size()) + " pairs, " +
                    std::to_string(sFaces.size()) + " slave / " +
                    std::to_string(mFaces.size()) + " master segments, " + gapBuf);

                int slaveSid = ids.issue(KooRemapper::ids::Ns::Set);
                int masterSid = ids.issue(KooRemapper::ids::Ns::Set);
                insertBlocks.push_back(ct_generateSetSegment(slaveSid, sFaces,
                    prefix + "_Slave"));
                insertBlocks.push_back(ct_generateSetSegment(masterSid, mFaces,
                    prefix + "_Master"));
                modified = true;

                if (act.detectAutoCreate) {
                    ContactDef def{};
                    def.type = preset.keyword;
                    def.fullKeyword = "*CONTACT_" + preset.keyword;
                    def.hasTitle = true;
                    def.title = prefix + "_PID" + std::to_string(slavePid) +
                                "_PID" + std::to_string(masterPid);
                    def.cid = ids.issue(KooRemapper::ids::Ns::Contact);   // `_ID` 카드로 나간다
                    def.ssid = slaveSid;
                    def.msid = masterSid;
                    def.sstyp = 0; def.mstyp = 0;
                    applyCard123(act, def);
                    applyOptional(act, def);
                    {
                        std::string err;
                        if (!applyMandatory(act, preset.keyword, def, err)) { console.error("[contact] detect: " + err); return 1; }
                    }
                    insertBlocks.push_back(ct_generateContact(def));
                    console.println("[contact] Created *CONTACT_" + preset.keyword);
                }
            }
            continue;
        }

        console.warning("[contact] Unknown action: " + act.action);
    }

    // 6. Apply removals — 지금 줄로 다시 읽어 번호의 범위를 구하고 뒤에서부터 지운다
    if (!removeIdx.empty()) {
        const auto now = ct_parseContacts(lines);
        std::vector<std::pair<int,int>> ranges;
        for (int ix : removeIdx)
            if (ix >= 0 && ix < (int)now.size()) ranges.push_back({now[ix].startLine, now[ix].endLine});
        std::sort(ranges.begin(), ranges.end(), [](const auto& a, const auto& b){ return a.first > b.first; });
        for (const auto& [start, end] : ranges) ct_removeBlock(lines, start, end);
    }

    // 7. Insert new blocks before *END
    if (!insertBlocks.empty()) {
        int endPos = -1;
        for (int i = (int)lines.size()-1; i >= 0; --i) {
            std::string up = kw_trim(lines[i]);
            for (auto& c : up) c = static_cast<char>(toupper(static_cast<unsigned char>(c)));
            if (up == "*END") { endPos = i; break; }
        }
        if (endPos < 0) endPos = (int)lines.size();

        std::vector<std::string> combined;
        for (const auto& blk : insertBlocks) {
            // Split block into lines
            std::istringstream bs(blk);
            std::string bl;
            while (std::getline(bs, bl)) combined.push_back(bl);
        }
        lines.insert(lines.begin() + endPos, combined.begin(), combined.end());
    }

    // 8. Write output if modified
    if (analyzeOnly && !modified) {
        console.println("[contact] Analysis only — no output written.");
        return 0;
    }

    if (outPath.empty()) {
        console.error("YAML missing 'output' key (required for non-analyze actions)");
        return 1;
    }

    // 원본 덱의 개행을 따른다 — 안 그러면 CRLF 덱이 조용히 LF 로 바뀌거나,
    // 원본 줄만 CRLF 로 남고 새로 넣은 줄이 LF 가 되어 **한 파일 안에서 개행이 갈린다**.
    KooRemapper::DeckWriter outf_w(outPath, KooRemapper::deck_newline::detect(modelPath));
    std::ostream& outf = outf_w.stream();
    if (!outf_w.ok()) { console.error("Cannot write output: " + outPath); return 1; }
    for (const auto& ln : lines) outf << ln << "\n";
    console.println("[contact] Done -> " + outputFile);
    return 0;
}
