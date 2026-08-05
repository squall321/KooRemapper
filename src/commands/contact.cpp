#include "contact.h"
#include "contact_helpers.h"
#include "kw_util.h"
#include "cli/ConsoleOutput.h"
#include "core/Mesh.h"
#include "parser/KFileReader.h"
#include <fstream>
#include <sstream>
#include <string>
#include <vector>
#include <map>
#include <set>
#include <algorithm>

// Knowledge graph (lat.md):
//   @lat: [[modules/commands]]
//   @lat: [[commands/contact]]

using namespace KooRemapper;

int runContact(const std::string& yamlFile, ConsoleOutput& console) {
    // 1. Parse YAML
    std::string configDir;
    {
        size_t sep = yamlFile.find_last_of("/\\");
        configDir = (sep != std::string::npos) ? yamlFile.substr(0, sep+1) : "";
    }
    auto resolvePath = [&](const std::string& p) -> std::string {
        if (!configDir.empty() && !p.empty() &&
            p[0]!='/' && p[0]!='\\' && !(p.size()>=2 && p[1]==':') &&
            p.find('/')  == std::string::npos &&
            p.find('\\') == std::string::npos)
            return configDir + "/" + p;
        return p;
    };

    std::ifstream yin(yamlFile);
    if (!yin.is_open()) { console.error("Cannot open YAML: " + yamlFile); return 1; }

    std::string modelFile, outputFile;

    struct ContactAction {
        std::string action;  // analyze/create/convert/modify/remove
        // create fields
        std::string type;
        struct Side {
            int pid = 0;
            std::vector<int> pids;
            bool asSegment = false;
            bool facing = false;   // filter segments to only those facing the other side
        };
        Side slave, master;
        double friction = -1.0;  // -1 = not set (sentinel)
        std::string title;
        // convert/modify/remove fields
        int contactIndex = -1;
        std::string slaveTo, masterTo;  // "segment"
        bool convertFacing = false;     // facing filter for convert action
        // Card 1 extended
        int sboxid = -1, mboxid = -1, spr = -1, mpr = -1;
        // Card 2 extended (-1 = not set sentinel for doubles, -1 for ints)
        double fd = -1, dc = -1, vc = -1, vdc = -1; int penchk = -1; double bt = -1, dt = -1;
        // Card 3
        double sfsa=-1, sfsb=-1, sast=-1, sbst=-1, sfsat=-1, sfsbt=-1, fsf=-1, vsf=-1;
        // Card A
        int soft = -1; double sofscl = -1; int lcidab = -1; double maxpar = -1;
        int sbopt = -1, depth = -1, bsort = -1, frcfrq = -1;
        // Card B
        double penmax = -1; int thkopt = -1, shlthk = -1, snlog = -1;
        int isym = -1, i2d3d = -1; double sldthk = -1, sldstf = -1;
        // Card C
        int igap = -1, ignore_ = -1; double dprfac = -1, dtstif = -1;
        double edgek = -1, flangl = -1; int cid_rcf = -1;
        // Card D
        int q2tri = -1; double dtpchk = -1, sfnbr = -1, fnlscl = -1, dnlscl = -1;
        int tcso = -1, tiedid = -1, shledg = -1;
        // Card E
        int sharec = -1, cparm8 = -1, ipback = -1, srnde = -1;
        double fricsf = -1; int icor = -1, ftorq = -1, region = -1;
        // Card F
        int pstiff = -1, ignroff = -1; double fstol = -1;
        int d2binr = -1, ssftyp = -1, swtpr = -1; double tetfac = -1;
        // Card G
        double shloff = -1;
        // THERMAL 카드 (create; -1=미설정 sentinel)
        double th_k=-1, th_frad=-1, th_h0=-1, th_lmin=-1, th_lmax=-1, th_chlm=-1;
        int th_bcflag=-1, th_algo=-1;
        // TIEBREAK 카드 (create)
        int tb_option=-1; double tb_nfls=-1, tb_sfls=-1, tb_param=-1, tb_eraten=-1, tb_erates=-1, tb_ct2cn=-1;
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

        auto flushAction = [&]() {
            if (hasAction) {
                actions.push_back(curAction);
                curAction = ContactAction{};
                hasAction = false;
                currentSide.clear();
            }
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

            size_t colon = t.find(':');
            if (colon == std::string::npos) continue;
            std::string key = kw_trim(t.substr(0, colon));
            std::string val = kw_trim(t.substr(colon+1));
            // strip inline comment
            { size_t h = val.find('#'); if (h != std::string::npos) val = kw_trim(val.substr(0, h)); }

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
                    curAction.action = kw_trim(t.substr(ac+1));
                    // strip inline comment from action
                    size_t h = curAction.action.find('#');
                    if (h != std::string::npos) curAction.action = kw_trim(curAction.action.substr(0, h));
                }
                hasAction = true;
                currentSide.clear();
                continue;
            }

            if (!hasAction) continue;

            // Sub-keys of current action
            if (key == "type") { curAction.type = val; continue; }
            if (key == "title") { curAction.title = val; continue; }
            if (key == "contact_index") { try { curAction.contactIndex = std::stoi(val); } catch(...){} continue; }
            if (key == "slave_to") { curAction.slaveTo = val; continue; }
            if (key == "master_to") { curAction.masterTo = val; continue; }
            if (key == "facing" && curAction.action == "convert") {
                curAction.convertFacing = (val=="true"||val=="yes"||val=="1"); continue;
            }
            // Card 1
            if (key == "friction") { try { curAction.friction = std::stod(val); } catch(...){} continue; }
            if (key == "sboxid")  { try { curAction.sboxid = std::stoi(val); } catch(...){} continue; }
            if (key == "mboxid")  { try { curAction.mboxid = std::stoi(val); } catch(...){} continue; }
            if (key == "spr")     { try { curAction.spr = std::stoi(val); } catch(...){} continue; }
            if (key == "mpr")     { try { curAction.mpr = std::stoi(val); } catch(...){} continue; }
            // Card 2
            if (key == "fd")      { try { curAction.fd = std::stod(val); } catch(...){} continue; }
            if (key == "dc")      { try { curAction.dc = std::stod(val); } catch(...){} continue; }
            if (key == "vc")      { try { curAction.vc = std::stod(val); } catch(...){} continue; }
            if (key == "vdc")     { try { curAction.vdc = std::stod(val); } catch(...){} continue; }
            if (key == "penchk")  { try { curAction.penchk = std::stoi(val); } catch(...){} continue; }
            if (key == "bt")      { try { curAction.bt = std::stod(val); } catch(...){} continue; }
            if (key == "dt")      { try { curAction.dt = std::stod(val); } catch(...){} continue; }
            // Card 3
            if (key == "sfsa")    { try { curAction.sfsa = std::stod(val); } catch(...){} continue; }
            if (key == "sfsb")    { try { curAction.sfsb = std::stod(val); } catch(...){} continue; }
            if (key == "sast")    { try { curAction.sast = std::stod(val); } catch(...){} continue; }
            if (key == "sbst")    { try { curAction.sbst = std::stod(val); } catch(...){} continue; }
            if (key == "sfsat")   { try { curAction.sfsat = std::stod(val); } catch(...){} continue; }
            if (key == "sfsbt")   { try { curAction.sfsbt = std::stod(val); } catch(...){} continue; }
            if (key == "fsf")     { try { curAction.fsf = std::stod(val); } catch(...){} continue; }
            if (key == "vsf")     { try { curAction.vsf = std::stod(val); } catch(...){} continue; }
            // Card A
            if (key == "soft")    { try { curAction.soft = std::stoi(val); } catch(...){} continue; }
            if (key == "sofscl")  { try { curAction.sofscl = std::stod(val); } catch(...){} continue; }
            if (key == "lcidab")  { try { curAction.lcidab = std::stoi(val); } catch(...){} continue; }
            if (key == "maxpar")  { try { curAction.maxpar = std::stod(val); } catch(...){} continue; }
            if (key == "sbopt")   { try { curAction.sbopt = std::stoi(val); } catch(...){} continue; }
            if (key == "depth")   { try { curAction.depth = std::stoi(val); } catch(...){} continue; }
            if (key == "bsort")   { try { curAction.bsort = std::stoi(val); } catch(...){} continue; }
            if (key == "frcfrq")  { try { curAction.frcfrq = std::stoi(val); } catch(...){} continue; }
            // Card B
            if (key == "penmax")  { try { curAction.penmax = std::stod(val); } catch(...){} continue; }
            if (key == "thkopt")  { try { curAction.thkopt = std::stoi(val); } catch(...){} continue; }
            if (key == "shlthk")  { try { curAction.shlthk = std::stoi(val); } catch(...){} continue; }
            if (key == "snlog")   { try { curAction.snlog = std::stoi(val); } catch(...){} continue; }
            if (key == "isym")    { try { curAction.isym = std::stoi(val); } catch(...){} continue; }
            if (key == "i2d3d")   { try { curAction.i2d3d = std::stoi(val); } catch(...){} continue; }
            if (key == "sldthk")  { try { curAction.sldthk = std::stod(val); } catch(...){} continue; }
            if (key == "sldstf")  { try { curAction.sldstf = std::stod(val); } catch(...){} continue; }
            // Card C
            if (key == "igap")    { try { curAction.igap = std::stoi(val); } catch(...){} continue; }
            if (key == "ignore")  { try { curAction.ignore_ = std::stoi(val); } catch(...){} continue; }
            if (key == "dprfac")  { try { curAction.dprfac = std::stod(val); } catch(...){} continue; }
            if (key == "dtstif")  { try { curAction.dtstif = std::stod(val); } catch(...){} continue; }
            if (key == "edgek")   { try { curAction.edgek = std::stod(val); } catch(...){} continue; }
            if (key == "flangl")  { try { curAction.flangl = std::stod(val); } catch(...){} continue; }
            if (key == "cid_rcf") { try { curAction.cid_rcf = std::stoi(val); } catch(...){} continue; }
            // Card D
            if (key == "q2tri")   { try { curAction.q2tri = std::stoi(val); } catch(...){} continue; }
            if (key == "dtpchk")  { try { curAction.dtpchk = std::stod(val); } catch(...){} continue; }
            if (key == "sfnbr")   { try { curAction.sfnbr = std::stod(val); } catch(...){} continue; }
            if (key == "fnlscl")  { try { curAction.fnlscl = std::stod(val); } catch(...){} continue; }
            if (key == "dnlscl")  { try { curAction.dnlscl = std::stod(val); } catch(...){} continue; }
            if (key == "tcso")    { try { curAction.tcso = std::stoi(val); } catch(...){} continue; }
            if (key == "tiedid")  { try { curAction.tiedid = std::stoi(val); } catch(...){} continue; }
            if (key == "shledg")  { try { curAction.shledg = std::stoi(val); } catch(...){} continue; }
            // Card E
            if (key == "sharec")  { try { curAction.sharec = std::stoi(val); } catch(...){} continue; }
            if (key == "cparm8")  { try { curAction.cparm8 = std::stoi(val); } catch(...){} continue; }
            if (key == "ipback")  { try { curAction.ipback = std::stoi(val); } catch(...){} continue; }
            if (key == "srnde")   { try { curAction.srnde = std::stoi(val); } catch(...){} continue; }
            if (key == "fricsf")  { try { curAction.fricsf = std::stod(val); } catch(...){} continue; }
            if (key == "icor")    { try { curAction.icor = std::stoi(val); } catch(...){} continue; }
            if (key == "ftorq")   { try { curAction.ftorq = std::stoi(val); } catch(...){} continue; }
            if (key == "region")  { try { curAction.region = std::stoi(val); } catch(...){} continue; }
            // Card F
            if (key == "pstiff")  { try { curAction.pstiff = std::stoi(val); } catch(...){} continue; }
            if (key == "ignroff") { try { curAction.ignroff = std::stoi(val); } catch(...){} continue; }
            if (key == "fstol")   { try { curAction.fstol = std::stod(val); } catch(...){} continue; }
            if (key == "d2binr" || key == "2dbinr") { try { curAction.d2binr = std::stoi(val); } catch(...){} continue; }
            if (key == "ssftyp")  { try { curAction.ssftyp = std::stoi(val); } catch(...){} continue; }
            if (key == "swtpr")   { try { curAction.swtpr = std::stoi(val); } catch(...){} continue; }
            if (key == "tetfac")  { try { curAction.tetfac = std::stod(val); } catch(...){} continue; }
            // Card G
            if (key == "shloff")  { try { curAction.shloff = std::stod(val); } catch(...){} continue; }
            // THERMAL 카드 필드 (create, type: tied_thermal)
            if (key == "k")       { try { curAction.th_k = std::stod(val); } catch(...){} continue; }
            if (key == "frad")    { try { curAction.th_frad = std::stod(val); } catch(...){} continue; }
            if (key == "h0")      { try { curAction.th_h0 = std::stod(val); } catch(...){} continue; }
            if (key == "lmin")    { try { curAction.th_lmin = std::stod(val); } catch(...){} continue; }
            if (key == "lmax")    { try { curAction.th_lmax = std::stod(val); } catch(...){} continue; }
            if (key == "chlm")    { try { curAction.th_chlm = std::stod(val); } catch(...){} continue; }
            if (key == "bc_flag") { try { curAction.th_bcflag = std::stoi(val); } catch(...){} continue; }
            if (key == "algo")    { try { curAction.th_algo = std::stoi(val); } catch(...){} continue; }
            // TIEBREAK 카드 필드 (create, type: tiebreak)
            if (key == "option")  { try { curAction.tb_option = std::stoi(val); } catch(...){} continue; }
            if (key == "nfls")    { try { curAction.tb_nfls = std::stod(val); } catch(...){} continue; }
            if (key == "sfls")    { try { curAction.tb_sfls = std::stod(val); } catch(...){} continue; }
            if (key == "param")   { try { curAction.tb_param = std::stod(val); } catch(...){} continue; }
            if (key == "eraten")  { try { curAction.tb_eraten = std::stod(val); } catch(...){} continue; }
            if (key == "erates")  { try { curAction.tb_erates = std::stod(val); } catch(...){} continue; }
            if (key == "ct2cn")   { try { curAction.tb_ct2cn = std::stod(val); } catch(...){} continue; }

            // detect fields
            if (key == "scope") { curAction.scope = val; continue; }
            if (key == "contact_type") { curAction.contactType = val; continue; }
            if (key == "tolerance") { try { curAction.detectTolerance = std::stod(val); } catch(...){} continue; }
            if (key == "normal_angle") { try { curAction.detectNormalAngle = std::stod(val); } catch(...){} continue; }
            if (key == "auto_create") { curAction.detectAutoCreate = (val=="true"||val=="yes"||val=="1"); continue; }
            if (key == "title_prefix") { curAction.titlePrefix = val; continue; }
            if (key == "skip_existing") { curAction.skipExisting = val; continue; }
            if (key == "subtract_existing") { curAction.subtractExisting = (val=="true"||val=="yes"||val=="1"); continue; }
            if (key == "include" || key == "exclude") {
                // Parse list: [kw1, kw2, ...] or bare value
                std::vector<std::string>& tgt = (key == "include") ?
                    curAction.includeKeys : curAction.excludeKeys;
                std::string v = val;
                if (!v.empty() && v.front() == '[') v.erase(v.begin());
                if (!v.empty() && v.back() == ']') v.pop_back();
                std::istringstream kss(v);
                std::string kw;
                while (std::getline(kss, kw, ',')) {
                    size_t s = kw.find_first_not_of(" \t");
                    size_t e = kw.find_last_not_of(" \t");
                    if (s != std::string::npos && e != std::string::npos)
                        tgt.push_back(kw.substr(s, e - s + 1));
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
                        if (k2 == "pid") { try { side.pid = std::stoi(v2); } catch(...){} }
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
                if (key == "pid") { try { side.pid = std::stoi(val); } catch(...){} continue; }
                if (key == "pids") { side.pids = parsePidList(val); continue; }
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
    }

    // 2. Read model as rawLines
    std::vector<std::string> lines;
    {
        std::ifstream mf(modelPath);
        if (!mf.is_open()) { console.error("Cannot open model: " + modelPath); return 1; }
        std::string ln;
        while (std::getline(mf, ln)) lines.push_back(ln);
    }

    // 3. Optionally load Mesh (for surface extraction)
    bool needMesh = false;
    for (const auto& act : actions) {
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
            console.error("Cannot parse mesh: " + modelPath + " (" + e.what() + ")");
            return 1;
        }
    }

    // 4. Parse existing contacts and sets
    auto contacts = ct_parseContacts(lines);
    auto sets     = ct_parseSets(lines);
    int nextSetId = ct_findMaxSetId(sets) + 1;

    console.println("[contact] Model: " + modelFile + " (" + std::to_string(lines.size()) + " lines)");
    console.println("[contact] Found " + std::to_string(contacts.size()) + " contacts, " +
                    std::to_string(sets.size()) + " sets");

    // 5. Process actions
    std::vector<std::string> insertBlocks;   // blocks to insert before *END
    std::vector<std::pair<int,int>> removeRanges;  // (start,end) to remove (sorted descending later)
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
            // Normalize type to uppercase with underscores
            for (auto& c : ctype) { if (c == '-') c = '_'; c = static_cast<char>(toupper(static_cast<unsigned char>(c))); }
            // 짧은 별칭 → 전체 키워드 (thermal/tiebreak). 전체 키워드로 쓴 경우는 그대로 통과.
            if (ctype == "TIED_THERMAL" || ctype == "THERMAL")
                ctype = "TIED_SURFACE_TO_SURFACE_THERMAL";
            else if (ctype == "TIEBREAK")
                ctype = "AUTOMATIC_SURFACE_TO_SURFACE_TIEBREAK";

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

                        ssid = nextSetId++;
                        insertBlocks.push_back(ct_generateSetSegment(ssid, sFaces,
                            "Slave_PID" + std::to_string(act.slave.pid) + "_facing"));
                        sstyp = 0;
                        msid = nextSetId++;
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
                    ssid = nextSetId++;
                    insertBlocks.push_back(ct_generateSetSegment(ssid, faces,
                        "Slave_PID" + std::to_string(act.slave.pid)));
                    sstyp = 0;
                    console.println("[contact] Created SET_SEGMENT " + std::to_string(ssid) +
                                  " (" + std::to_string(faces.size()) + " faces) for slave PID " +
                                  std::to_string(act.slave.pid));
                }
            } else if (!act.slave.pids.empty()) {
                // Multiple PIDs → SET_PART
                ssid = nextSetId++;
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
                    msid = nextSetId++;
                    insertBlocks.push_back(ct_generateSetSegment(msid, faces,
                        "Master_PID" + std::to_string(act.master.pid)));
                    mstyp = 0;
                    console.println("[contact] Created SET_SEGMENT " + std::to_string(msid) +
                                  " (" + std::to_string(faces.size()) + " faces) for master PID " +
                                  std::to_string(act.master.pid));
                }
            } else if (!act.master.pids.empty()) {
                msid = nextSetId++;
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
                    ssid = nextSetId++;
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
            // Card 1 optional
            if (act.sboxid >= 0) newDef.sboxid = act.sboxid;
            if (act.mboxid >= 0) newDef.mboxid = act.mboxid;
            if (act.spr >= 0) newDef.spr = act.spr;
            if (act.mpr >= 0) newDef.mpr = act.mpr;
            // Card 2
            newDef.fs = (act.friction >= 0) ? act.friction : 0.0;
            if (act.fd >= 0) newDef.fd = act.fd;
            if (act.dc >= 0) newDef.dc = act.dc;
            if (act.vc >= 0) newDef.vc = act.vc;
            if (act.vdc >= 0) newDef.vdc = act.vdc;
            if (act.penchk >= 0) newDef.penchk = act.penchk;
            if (act.bt >= 0) newDef.bt = act.bt;
            if (act.dt >= 0) newDef.dt = act.dt;
            // Card 3
            if (act.sfsa >= 0) newDef.sfsa = act.sfsa;
            if (act.sfsb >= 0) newDef.sfsb = act.sfsb;
            if (act.sast >= 0) newDef.sast = act.sast;
            if (act.sbst >= 0) newDef.sbst = act.sbst;
            if (act.sfsat >= 0) newDef.sfsat = act.sfsat;
            if (act.sfsbt >= 0) newDef.sfsbt = act.sfsbt;
            if (act.fsf >= 0) newDef.fsf = act.fsf;
            if (act.vsf >= 0) newDef.vsf = act.vsf;
            // Card A — any field set → hasCardA
            if (act.soft>=0||act.sofscl>=0||act.lcidab>=0||act.maxpar>=0||
                act.sbopt>=0||act.depth>=0||act.bsort>=0||act.frcfrq>=0) {
                newDef.hasCardA = true;
                if (act.soft >= 0) newDef.soft = act.soft;
                if (act.sofscl >= 0) newDef.sofscl = act.sofscl;
                if (act.lcidab >= 0) newDef.lcidab = act.lcidab;
                if (act.maxpar >= 0) newDef.maxpar = act.maxpar;
                if (act.sbopt >= 0) newDef.sbopt = act.sbopt;
                if (act.depth >= 0) newDef.depth = act.depth;
                if (act.bsort >= 0) newDef.bsort = act.bsort;
                if (act.frcfrq >= 0) newDef.frcfrq = act.frcfrq;
            }
            // Card B
            if (act.penmax>=0||act.thkopt>=0||act.shlthk>=0||act.snlog>=0||
                act.isym>=0||act.i2d3d>=0||act.sldthk>=0||act.sldstf>=0) {
                newDef.hasCardB = true; newDef.hasCardA = true;
                if (act.penmax >= 0) newDef.penmax = act.penmax;
                if (act.thkopt >= 0) newDef.thkopt = act.thkopt;
                if (act.shlthk >= 0) newDef.shlthk = act.shlthk;
                if (act.snlog >= 0) newDef.snlog = act.snlog;
                if (act.isym >= 0) newDef.isym = act.isym;
                if (act.i2d3d >= 0) newDef.i2d3d = act.i2d3d;
                if (act.sldthk >= 0) newDef.sldthk = act.sldthk;
                if (act.sldstf >= 0) newDef.sldstf = act.sldstf;
            }
            // Card C
            if (act.igap>=0||act.ignore_>=0||act.dprfac>=0||act.dtstif>=0||
                act.edgek>=0||act.flangl>=0||act.cid_rcf>=0) {
                newDef.hasCardC = true; newDef.hasCardB = true; newDef.hasCardA = true;
                if (act.igap >= 0) newDef.igap = act.igap;
                if (act.ignore_ >= 0) newDef.ignore_ = act.ignore_;
                if (act.dprfac >= 0) newDef.dprfac = act.dprfac;
                if (act.dtstif >= 0) newDef.dtstif = act.dtstif;
                if (act.edgek >= 0) newDef.edgek = act.edgek;
                if (act.flangl >= 0) newDef.flangl = act.flangl;
                if (act.cid_rcf >= 0) newDef.cid_rcf = act.cid_rcf;
            }
            // Card D
            if (act.q2tri>=0||act.dtpchk>=0||act.sfnbr>=0||act.fnlscl>=0||
                act.dnlscl>=0||act.tcso>=0||act.tiedid>=0||act.shledg>=0) {
                newDef.hasCardD = true; newDef.hasCardC = true;
                newDef.hasCardB = true; newDef.hasCardA = true;
                if (act.q2tri >= 0) newDef.q2tri = act.q2tri;
                if (act.dtpchk >= 0) newDef.dtpchk = act.dtpchk;
                if (act.sfnbr >= 0) newDef.sfnbr = act.sfnbr;
                if (act.fnlscl >= 0) newDef.fnlscl = act.fnlscl;
                if (act.dnlscl >= 0) newDef.dnlscl = act.dnlscl;
                if (act.tcso >= 0) newDef.tcso = act.tcso;
                if (act.tiedid >= 0) newDef.tiedid = act.tiedid;
                if (act.shledg >= 0) newDef.shledg = act.shledg;
            }
            // Card E
            if (act.sharec>=0||act.cparm8>=0||act.ipback>=0||act.srnde>=0||
                act.fricsf>=0||act.icor>=0||act.ftorq>=0||act.region>=0) {
                newDef.hasCardE = true; newDef.hasCardD = true;
                newDef.hasCardC = true; newDef.hasCardB = true; newDef.hasCardA = true;
                if (act.sharec >= 0) newDef.sharec = act.sharec;
                if (act.cparm8 >= 0) newDef.cparm8 = act.cparm8;
                if (act.ipback >= 0) newDef.ipback = act.ipback;
                if (act.srnde >= 0) newDef.srnde = act.srnde;
                if (act.fricsf >= 0) newDef.fricsf = act.fricsf;
                if (act.icor >= 0) newDef.icor = act.icor;
                if (act.ftorq >= 0) newDef.ftorq = act.ftorq;
                if (act.region >= 0) newDef.region = act.region;
            }
            // Card F
            if (act.pstiff>=0||act.ignroff>=0||act.fstol>=0||
                act.d2binr>=0||act.ssftyp>=0||act.swtpr>=0||act.tetfac>=0) {
                newDef.hasCardF = true; newDef.hasCardE = true; newDef.hasCardD = true;
                newDef.hasCardC = true; newDef.hasCardB = true; newDef.hasCardA = true;
                if (act.pstiff >= 0) newDef.pstiff = act.pstiff;
                if (act.ignroff >= 0) newDef.ignroff = act.ignroff;
                if (act.fstol >= 0) newDef.fstol = act.fstol;
                if (act.d2binr >= 0) newDef.d2binr = act.d2binr;
                if (act.ssftyp >= 0) newDef.ssftyp = act.ssftyp;
                if (act.swtpr >= 0) newDef.swtpr = act.swtpr;
                if (act.tetfac >= 0) newDef.tetfac = act.tetfac;
            }
            // Card G
            if (act.shloff >= 0) {
                newDef.hasCardG = true; newDef.hasCardF = true; newDef.hasCardE = true;
                newDef.hasCardD = true; newDef.hasCardC = true;
                newDef.hasCardB = true; newDef.hasCardA = true;
                newDef.shloff = act.shloff;
            }
            // THERMAL 카드 (_THERMAL 계열) — 필드는 미설정 시 기본값(chlm=1) 유지.
            if (ctype.find("THERMAL") != std::string::npos) {
                newDef.hasThermal = true;
                if (act.th_k >= 0)      newDef.thK = act.th_k;
                if (act.th_frad >= 0)   newDef.thFrad = act.th_frad;
                if (act.th_h0 >= 0)     newDef.thH0 = act.th_h0;
                if (act.th_lmin >= 0)   newDef.thLmin = act.th_lmin;
                if (act.th_lmax >= 0)   newDef.thLmax = act.th_lmax;
                if (act.th_chlm >= 0)   newDef.thChlm = act.th_chlm;
                if (act.th_bcflag >= 0) newDef.thBcflag = act.th_bcflag;
                if (act.th_algo >= 0)   newDef.thAlgo = act.th_algo;
            }
            // TIEBREAK 카드 (_TIEBREAK 계열) — OPTION 기본 1(quadratic NFLS/SFLS).
            if (ctype.find("TIEBREAK") != std::string::npos) {
                newDef.hasTiebreak = true;
                if (act.tb_option >= 0) newDef.tbOption = act.tb_option;
                if (act.tb_nfls >= 0)   newDef.tbNfls = act.tb_nfls;
                if (act.tb_sfls >= 0)   newDef.tbSfls = act.tb_sfls;
                if (act.tb_param >= 0)  newDef.tbParam = act.tb_param;
                if (act.tb_eraten >= 0) newDef.tbEraten = act.tb_eraten;
                if (act.tb_erates >= 0) newDef.tbErates = act.tb_erates;
                if (act.tb_ct2cn >= 0)  newDef.tbCt2cn = act.tb_ct2cn;
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
            auto collectFaces = [&](int sid, int styp) -> std::vector<std::array<int,4>> {
                if (styp == 3) return ct_extractSurface(mesh, sid);
                if (styp == 2) {
                    for (const auto& s : sets)
                        if (s.type == "PART" && s.id == sid) {
                            std::vector<std::array<int,4>> result;
                            for (int pid : s.ids) {
                                auto f = ct_extractSurface(mesh, pid);
                                result.insert(result.end(), f.begin(), f.end());
                            }
                            return result;
                        }
                }
                if (styp == 0) {
                    for (const auto& s : sets)
                        if (s.type == "SEGMENT" && s.id == sid)
                            return s.segments;
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

                        int newSsid = nextSetId++;
                        insertBlocks.push_back(ct_generateSetSegment(newSsid, sFaces,
                            "Slave_facing"));
                        int newMsid = nextSetId++;
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
                    int newSid = nextSetId++;
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
                // Part set → expand to segment
                // Find the set and get PIDs
                for (const auto& s : sets) {
                    if (s.type == "PART" && s.id == ct.ssid) {
                        std::vector<std::array<int,4>> allFaces;
                        for (int pid : s.ids) {
                            auto faces = ct_extractSurface(mesh, pid);
                            allFaces.insert(allFaces.end(), faces.begin(), faces.end());
                        }
                        if (!allFaces.empty()) {
                            int newSid = nextSetId++;
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
                        break;
                    }
                }
            }

            // Convert master to segment
            if (act.masterTo == "segment" && ct.mstyp == 3) {
                auto faces = ct_extractSurface(mesh, ct.msid);
                if (faces.empty()) {
                    console.warning("[contact] No surface for master PID " + std::to_string(ct.msid));
                } else {
                    int newSid = nextSetId++;
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
                for (const auto& s : sets) {
                    if (s.type == "PART" && s.id == ct.msid) {
                        std::vector<std::array<int,4>> allFaces;
                        for (int pid : s.ids) {
                            auto faces = ct_extractSurface(mesh, pid);
                            allFaces.insert(allFaces.end(), faces.begin(), faces.end());
                        }
                        if (!allFaces.empty()) {
                            int newSid = nextSetId++;
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
                        break;
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
            std::string modFields;

            // Card 1 modifications
            if (act.sboxid >= 0 || act.mboxid >= 0 || act.spr >= 0 || act.mpr >= 0) {
                // Full Card 1 rewrite via ct_modifyContactCard1 doesn't cover these,
                // so use impl_setField for extended fields
                // For now, reuse ct_modifyContactCard1 for ssid/msid/sstyp/mstyp: skip (no change)
            }

            // Card 2 modifications (FS + extended)
            if (act.friction >= 0) { ct_modifyContactFs(lines, ct, act.friction); ct.fs = act.friction; }
            // For other Card 2 fields, we need to modify in-place too
            {
                bool card2Modified = false;
                bool titleSkipped2 = !ct.hasTitle;
                int cn2 = 0;
                for (int i = ct.startLine + 1; i < ct.endLine; ++i) {
                    std::string dtr = kw_trim(lines[i]);
                    if (dtr.empty() || dtr[0] == '$') continue;
                    if (!titleSkipped2) { titleSkipped2 = true; continue; }
                    if (cn2 == 1) {
                        // Card 2 line
                        char buf[20];
                        if (act.fd >= 0)     { snprintf(buf,sizeof(buf),"%10.2f",act.fd);     lines[i]=kw_setField(lines[i],10,10,buf); ct.fd=act.fd; card2Modified=true; }
                        if (act.dc >= 0)     { snprintf(buf,sizeof(buf),"%10.2f",act.dc);     lines[i]=kw_setField(lines[i],20,10,buf); ct.dc=act.dc; card2Modified=true; }
                        if (act.vc >= 0)     { snprintf(buf,sizeof(buf),"%10.2f",act.vc);     lines[i]=kw_setField(lines[i],30,10,buf); ct.vc=act.vc; card2Modified=true; }
                        if (act.vdc >= 0)    { snprintf(buf,sizeof(buf),"%10.2f",act.vdc);    lines[i]=kw_setField(lines[i],40,10,buf); ct.vdc=act.vdc; card2Modified=true; }
                        if (act.penchk >= 0) { lines[i]=kw_setField(lines[i],50,10,std::to_string(act.penchk)); ct.penchk=act.penchk; card2Modified=true; }
                        if (act.bt >= 0)     { snprintf(buf,sizeof(buf),"%10.2f",act.bt);     lines[i]=kw_setField(lines[i],60,10,buf); ct.bt=act.bt; card2Modified=true; }
                        if (act.dt >= 0)     { snprintf(buf,sizeof(buf),"%10.3E",act.dt);     lines[i]=kw_setField(lines[i],70,10,buf); ct.dt=act.dt; card2Modified=true; }
                        break;
                    }
                    cn2++;
                }
                if (card2Modified) {
                    modFields += " Card2";
                } else {
                    bool card2Requested = (act.fd>=0||act.dc>=0||act.vc>=0||act.vdc>=0||
                                           act.penchk>=0||act.bt>=0||act.dt>=0);
                    if (card2Requested)
                        console.warning("[contact] [" + std::to_string(act.contactIndex) +
                            "] Card2 not found in file — add it explicitly or the contact has only Card1");
                }
            }

            // Card 3 modifications
            {
                bool card3Modified = false;
                bool titleSkipped3 = !ct.hasTitle;
                int cn3 = 0;
                for (int i = ct.startLine + 1; i < ct.endLine; ++i) {
                    std::string dtr = kw_trim(lines[i]);
                    if (dtr.empty() || dtr[0] == '$') continue;
                    if (!titleSkipped3) { titleSkipped3 = true; continue; }
                    if (cn3 == 2) {
                        // Card 3 line
                        char buf[20];
                        if (act.sfsa >= 0)  { snprintf(buf,sizeof(buf),"%10.2f",act.sfsa);  lines[i]=kw_setField(lines[i],0,10,buf); ct.sfsa=act.sfsa; card3Modified=true; }
                        if (act.sfsb >= 0)  { snprintf(buf,sizeof(buf),"%10.2f",act.sfsb);  lines[i]=kw_setField(lines[i],10,10,buf); ct.sfsb=act.sfsb; card3Modified=true; }
                        if (act.sast >= 0)  { snprintf(buf,sizeof(buf),"%10.2f",act.sast);  lines[i]=kw_setField(lines[i],20,10,buf); ct.sast=act.sast; card3Modified=true; }
                        if (act.sbst >= 0)  { snprintf(buf,sizeof(buf),"%10.2f",act.sbst);  lines[i]=kw_setField(lines[i],30,10,buf); ct.sbst=act.sbst; card3Modified=true; }
                        if (act.sfsat >= 0) { snprintf(buf,sizeof(buf),"%10.2f",act.sfsat); lines[i]=kw_setField(lines[i],40,10,buf); ct.sfsat=act.sfsat; card3Modified=true; }
                        if (act.sfsbt >= 0) { snprintf(buf,sizeof(buf),"%10.2f",act.sfsbt); lines[i]=kw_setField(lines[i],50,10,buf); ct.sfsbt=act.sfsbt; card3Modified=true; }
                        if (act.fsf >= 0)   { snprintf(buf,sizeof(buf),"%10.2f",act.fsf);   lines[i]=kw_setField(lines[i],60,10,buf); ct.fsf=act.fsf; card3Modified=true; }
                        if (act.vsf >= 0)   { snprintf(buf,sizeof(buf),"%10.2f",act.vsf);   lines[i]=kw_setField(lines[i],70,10,buf); ct.vsf=act.vsf; card3Modified=true; }
                        break;
                    }
                    cn3++;
                }
                if (card3Modified) {
                    modFields += " Card3";
                } else {
                    bool card3Requested = (act.sfsa>=0||act.sfsb>=0||act.sast>=0||act.sbst>=0||
                                           act.sfsat>=0||act.sfsbt>=0||act.fsf>=0||act.vsf>=0);
                    if (card3Requested)
                        console.warning("[contact] [" + std::to_string(act.contactIndex) +
                            "] Card3 not found in file — contact may only have Card1/Card2");
                }
            }

            // Optional Cards A~G: merge YAML values into existing ContactDef, then replace
            bool anyOptional = (act.soft>=0||act.sofscl>=0||act.lcidab>=0||act.maxpar>=0||
                act.sbopt>=0||act.depth>=0||act.bsort>=0||act.frcfrq>=0||
                act.penmax>=0||act.thkopt>=0||act.shlthk>=0||act.snlog>=0||
                act.isym>=0||act.i2d3d>=0||act.sldthk>=0||act.sldstf>=0||
                act.igap>=0||act.ignore_>=0||act.dprfac>=0||act.dtstif>=0||
                act.edgek>=0||act.flangl>=0||act.cid_rcf>=0||
                act.q2tri>=0||act.dtpchk>=0||act.sfnbr>=0||act.fnlscl>=0||
                act.dnlscl>=0||act.tcso>=0||act.tiedid>=0||act.shledg>=0||
                act.sharec>=0||act.cparm8>=0||act.ipback>=0||act.srnde>=0||
                act.fricsf>=0||act.icor>=0||act.ftorq>=0||act.region>=0||
                act.pstiff>=0||act.ignroff>=0||act.fstol>=0||
                act.d2binr>=0||act.ssftyp>=0||act.swtpr>=0||act.tetfac>=0||
                act.shloff>=0);

            if (anyOptional) {
                // Start from existing parsed values
                ContactDef merged = ct;
                // Card A
                if (act.soft>=0||act.sofscl>=0||act.lcidab>=0||act.maxpar>=0||
                    act.sbopt>=0||act.depth>=0||act.bsort>=0||act.frcfrq>=0) {
                    merged.hasCardA = true;
                    if (act.soft >= 0) merged.soft = act.soft;
                    if (act.sofscl >= 0) merged.sofscl = act.sofscl;
                    if (act.lcidab >= 0) merged.lcidab = act.lcidab;
                    if (act.maxpar >= 0) merged.maxpar = act.maxpar;
                    if (act.sbopt >= 0) merged.sbopt = act.sbopt;
                    if (act.depth >= 0) merged.depth = act.depth;
                    if (act.bsort >= 0) merged.bsort = act.bsort;
                    if (act.frcfrq >= 0) merged.frcfrq = act.frcfrq;
                }
                // Card B
                if (act.penmax>=0||act.thkopt>=0||act.shlthk>=0||act.snlog>=0||
                    act.isym>=0||act.i2d3d>=0||act.sldthk>=0||act.sldstf>=0) {
                    merged.hasCardB = true; merged.hasCardA = true;
                    if (act.penmax >= 0) merged.penmax = act.penmax;
                    if (act.thkopt >= 0) merged.thkopt = act.thkopt;
                    if (act.shlthk >= 0) merged.shlthk = act.shlthk;
                    if (act.snlog >= 0) merged.snlog = act.snlog;
                    if (act.isym >= 0) merged.isym = act.isym;
                    if (act.i2d3d >= 0) merged.i2d3d = act.i2d3d;
                    if (act.sldthk >= 0) merged.sldthk = act.sldthk;
                    if (act.sldstf >= 0) merged.sldstf = act.sldstf;
                }
                // Card C
                if (act.igap>=0||act.ignore_>=0||act.dprfac>=0||act.dtstif>=0||
                    act.edgek>=0||act.flangl>=0||act.cid_rcf>=0) {
                    merged.hasCardC = true; merged.hasCardB = true; merged.hasCardA = true;
                    if (act.igap >= 0) merged.igap = act.igap;
                    if (act.ignore_ >= 0) merged.ignore_ = act.ignore_;
                    if (act.dprfac >= 0) merged.dprfac = act.dprfac;
                    if (act.dtstif >= 0) merged.dtstif = act.dtstif;
                    if (act.edgek >= 0) merged.edgek = act.edgek;
                    if (act.flangl >= 0) merged.flangl = act.flangl;
                    if (act.cid_rcf >= 0) merged.cid_rcf = act.cid_rcf;
                }
                // Card D~G: same pattern
                if (act.q2tri>=0||act.shledg>=0||act.tcso>=0||act.tiedid>=0||
                    act.dtpchk>=0||act.sfnbr>=0||act.fnlscl>=0||act.dnlscl>=0) {
                    merged.hasCardD = true; merged.hasCardC = true;
                    merged.hasCardB = true; merged.hasCardA = true;
                    if (act.q2tri >= 0) merged.q2tri = act.q2tri;
                    if (act.dtpchk >= 0) merged.dtpchk = act.dtpchk;
                    if (act.sfnbr >= 0) merged.sfnbr = act.sfnbr;
                    if (act.fnlscl >= 0) merged.fnlscl = act.fnlscl;
                    if (act.dnlscl >= 0) merged.dnlscl = act.dnlscl;
                    if (act.tcso >= 0) merged.tcso = act.tcso;
                    if (act.tiedid >= 0) merged.tiedid = act.tiedid;
                    if (act.shledg >= 0) merged.shledg = act.shledg;
                }
                if (act.sharec>=0||act.cparm8>=0||act.ipback>=0||act.srnde>=0||
                    act.fricsf>=0||act.icor>=0||act.ftorq>=0||act.region>=0) {
                    merged.hasCardE = true; merged.hasCardD = true;
                    merged.hasCardC = true; merged.hasCardB = true; merged.hasCardA = true;
                    if (act.sharec >= 0) merged.sharec = act.sharec;
                    if (act.cparm8 >= 0) merged.cparm8 = act.cparm8;
                    if (act.ipback >= 0) merged.ipback = act.ipback;
                    if (act.srnde >= 0) merged.srnde = act.srnde;
                    if (act.fricsf >= 0) merged.fricsf = act.fricsf;
                    if (act.icor >= 0) merged.icor = act.icor;
                    if (act.ftorq >= 0) merged.ftorq = act.ftorq;
                    if (act.region >= 0) merged.region = act.region;
                }
                if (act.pstiff>=0||act.ignroff>=0||act.fstol>=0||
                    act.d2binr>=0||act.ssftyp>=0||act.swtpr>=0||act.tetfac>=0) {
                    merged.hasCardF = true; merged.hasCardE = true; merged.hasCardD = true;
                    merged.hasCardC = true; merged.hasCardB = true; merged.hasCardA = true;
                    if (act.pstiff >= 0) merged.pstiff = act.pstiff;
                    if (act.ignroff >= 0) merged.ignroff = act.ignroff;
                    if (act.fstol >= 0) merged.fstol = act.fstol;
                    if (act.d2binr >= 0) merged.d2binr = act.d2binr;
                    if (act.ssftyp >= 0) merged.ssftyp = act.ssftyp;
                    if (act.swtpr >= 0) merged.swtpr = act.swtpr;
                    if (act.tetfac >= 0) merged.tetfac = act.tetfac;
                }
                if (act.shloff >= 0) {
                    merged.hasCardG = true; merged.hasCardF = true; merged.hasCardE = true;
                    merged.hasCardD = true; merged.hasCardC = true;
                    merged.hasCardB = true; merged.hasCardA = true;
                    merged.shloff = act.shloff;
                }

                ct_modifyOptionalCards(lines, ct, merged);
                modFields += " OptCards";
                // Re-parse since line numbers shifted
                contacts = ct_parseContacts(lines);
                sets = ct_parseSets(lines);
            }

            if (act.friction >= 0) modFields += " FS=" + std::to_string(act.friction);
            console.println("[contact] [" + std::to_string(act.contactIndex) +
                          "] Modified:" + modFields);
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
            removeRanges.push_back({ct.startLine, ct.endLine});
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
                        if (ct_pairHasExisting(pr.pidA, pr.pidB, contacts, sets, act.skipExisting)) {
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
                            pr.pidA, pr.pidB, contacts, sets, mesh, tol, nAngle);
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
                    int slaveSid = nextSetId++;
                    int masterSid = nextSetId++;
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
                        def.ssid = slaveSid;
                        def.msid = preset.needMasterSide ? masterSid : 0;
                        def.sstyp = 0; // SET_SEGMENT
                        def.mstyp = preset.needMasterSide ? 0 : 0;
                        // Card 1 optional
                        if (act.sboxid >= 0) def.sboxid = act.sboxid;
                        if (act.mboxid >= 0) def.mboxid = act.mboxid;
                        if (act.spr >= 0) def.spr = act.spr;
                        if (act.mpr >= 0) def.mpr = act.mpr;
                        // Card 2
                        def.fs = (act.friction >= 0) ? act.friction : 0.0;
                        if (act.fd >= 0) def.fd = act.fd;
                        if (act.dc >= 0) def.dc = act.dc;
                        if (act.vc >= 0) def.vc = act.vc;
                        if (act.vdc >= 0) def.vdc = act.vdc;
                        if (act.penchk >= 0) def.penchk = act.penchk;
                        if (act.bt >= 0) def.bt = act.bt;
                        if (act.dt >= 0) def.dt = act.dt;
                        // Card 3
                        if (act.sfsa >= 0) def.sfsa = act.sfsa;
                        if (act.sfsb >= 0) def.sfsb = act.sfsb;
                        if (act.sast >= 0) def.sast = act.sast;
                        if (act.sbst >= 0) def.sbst = act.sbst;
                        if (act.sfsat >= 0) def.sfsat = act.sfsat;
                        if (act.sfsbt >= 0) def.sfsbt = act.sfsbt;
                        if (act.fsf >= 0) def.fsf = act.fsf;
                        if (act.vsf >= 0) def.vsf = act.vsf;
                        // Card A
                        if (act.soft>=0||act.sofscl>=0||act.lcidab>=0||act.maxpar>=0||
                            act.sbopt>=0||act.depth>=0||act.bsort>=0||act.frcfrq>=0) {
                            def.hasCardA = true;
                            if (act.soft >= 0) def.soft = act.soft;
                            if (act.sofscl >= 0) def.sofscl = act.sofscl;
                            if (act.lcidab >= 0) def.lcidab = act.lcidab;
                            if (act.maxpar >= 0) def.maxpar = act.maxpar;
                            if (act.sbopt >= 0) def.sbopt = act.sbopt;
                            if (act.depth >= 0) def.depth = act.depth;
                            if (act.bsort >= 0) def.bsort = act.bsort;
                            if (act.frcfrq >= 0) def.frcfrq = act.frcfrq;
                        }
                        // Card B
                        if (act.penmax>=0||act.thkopt>=0||act.shlthk>=0||act.snlog>=0||
                            act.isym>=0||act.i2d3d>=0||act.sldthk>=0||act.sldstf>=0) {
                            def.hasCardB = true; def.hasCardA = true;
                            if (act.penmax >= 0) def.penmax = act.penmax;
                            if (act.thkopt >= 0) def.thkopt = act.thkopt;
                            if (act.shlthk >= 0) def.shlthk = act.shlthk;
                            if (act.snlog >= 0) def.snlog = act.snlog;
                            if (act.isym >= 0) def.isym = act.isym;
                            if (act.i2d3d >= 0) def.i2d3d = act.i2d3d;
                            if (act.sldthk >= 0) def.sldthk = act.sldthk;
                            if (act.sldstf >= 0) def.sldstf = act.sldstf;
                        }
                        // Card C
                        if (act.igap>=0||act.ignore_>=0||act.dprfac>=0||act.dtstif>=0||
                            act.edgek>=0||act.flangl>=0||act.cid_rcf>=0) {
                            def.hasCardC = true; def.hasCardB = true; def.hasCardA = true;
                            if (act.igap >= 0) def.igap = act.igap;
                            if (act.ignore_ >= 0) def.ignore_ = act.ignore_;
                            if (act.dprfac >= 0) def.dprfac = act.dprfac;
                            if (act.dtstif >= 0) def.dtstif = act.dtstif;
                            if (act.edgek >= 0) def.edgek = act.edgek;
                            if (act.flangl >= 0) def.flangl = act.flangl;
                            if (act.cid_rcf >= 0) def.cid_rcf = act.cid_rcf;
                        }
                        // Card D
                        if (act.q2tri>=0||act.dtpchk>=0||act.sfnbr>=0||act.fnlscl>=0||
                            act.dnlscl>=0||act.tcso>=0||act.tiedid>=0||act.shledg>=0) {
                            def.hasCardD = true; def.hasCardC = true;
                            def.hasCardB = true; def.hasCardA = true;
                            if (act.q2tri >= 0) def.q2tri = act.q2tri;
                            if (act.dtpchk >= 0) def.dtpchk = act.dtpchk;
                            if (act.sfnbr >= 0) def.sfnbr = act.sfnbr;
                            if (act.fnlscl >= 0) def.fnlscl = act.fnlscl;
                            if (act.dnlscl >= 0) def.dnlscl = act.dnlscl;
                            if (act.tcso >= 0) def.tcso = act.tcso;
                            if (act.tiedid >= 0) def.tiedid = act.tiedid;
                            if (act.shledg >= 0) def.shledg = act.shledg;
                        }
                        // Card E
                        if (act.sharec>=0||act.cparm8>=0||act.ipback>=0||act.srnde>=0||
                            act.fricsf>=0||act.icor>=0||act.ftorq>=0||act.region>=0) {
                            def.hasCardE = true; def.hasCardD = true;
                            def.hasCardC = true; def.hasCardB = true; def.hasCardA = true;
                            if (act.sharec >= 0) def.sharec = act.sharec;
                            if (act.cparm8 >= 0) def.cparm8 = act.cparm8;
                            if (act.ipback >= 0) def.ipback = act.ipback;
                            if (act.srnde >= 0) def.srnde = act.srnde;
                            if (act.fricsf >= 0) def.fricsf = act.fricsf;
                            if (act.icor >= 0) def.icor = act.icor;
                            if (act.ftorq >= 0) def.ftorq = act.ftorq;
                            if (act.region >= 0) def.region = act.region;
                        }
                        // Card F
                        if (act.pstiff>=0||act.ignroff>=0||act.fstol>=0||
                            act.d2binr>=0||act.ssftyp>=0||act.swtpr>=0||act.tetfac>=0) {
                            def.hasCardF = true; def.hasCardE = true; def.hasCardD = true;
                            def.hasCardC = true; def.hasCardB = true; def.hasCardA = true;
                            if (act.pstiff >= 0) def.pstiff = act.pstiff;
                            if (act.ignroff >= 0) def.ignroff = act.ignroff;
                            if (act.fstol >= 0) def.fstol = act.fstol;
                            if (act.d2binr >= 0) def.d2binr = act.d2binr;
                            if (act.ssftyp >= 0) def.ssftyp = act.ssftyp;
                            if (act.swtpr >= 0) def.swtpr = act.swtpr;
                            if (act.tetfac >= 0) def.tetfac = act.tetfac;
                        }
                        // Card G
                        if (act.shloff >= 0) {
                            def.hasCardG = true; def.hasCardF = true; def.hasCardE = true;
                            def.hasCardD = true; def.hasCardC = true;
                            def.hasCardB = true; def.hasCardA = true;
                            def.shloff = act.shloff;
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

                int slaveSid = nextSetId++;
                int masterSid = nextSetId++;
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
                    def.ssid = slaveSid;
                    def.msid = masterSid;
                    def.sstyp = 0; def.mstyp = 0;
                    // Card 1 optional
                    if (act.sboxid >= 0) def.sboxid = act.sboxid;
                    if (act.mboxid >= 0) def.mboxid = act.mboxid;
                    if (act.spr >= 0) def.spr = act.spr;
                    if (act.mpr >= 0) def.mpr = act.mpr;
                    // Card 2
                    def.fs = (act.friction >= 0) ? act.friction : 0.0;
                    if (act.fd >= 0) def.fd = act.fd;
                    if (act.dc >= 0) def.dc = act.dc;
                    if (act.vc >= 0) def.vc = act.vc;
                    if (act.vdc >= 0) def.vdc = act.vdc;
                    if (act.penchk >= 0) def.penchk = act.penchk;
                    if (act.bt >= 0) def.bt = act.bt;
                    if (act.dt >= 0) def.dt = act.dt;
                    // Card 3
                    if (act.sfsa >= 0) def.sfsa = act.sfsa;
                    if (act.sfsb >= 0) def.sfsb = act.sfsb;
                    if (act.sast >= 0) def.sast = act.sast;
                    if (act.sbst >= 0) def.sbst = act.sbst;
                    if (act.sfsat >= 0) def.sfsat = act.sfsat;
                    if (act.sfsbt >= 0) def.sfsbt = act.sfsbt;
                    if (act.fsf >= 0) def.fsf = act.fsf;
                    if (act.vsf >= 0) def.vsf = act.vsf;
                    // Card A
                    if (act.soft>=0||act.sofscl>=0||act.lcidab>=0||act.maxpar>=0||
                        act.sbopt>=0||act.depth>=0||act.bsort>=0||act.frcfrq>=0) {
                        def.hasCardA = true;
                        if (act.soft >= 0) def.soft = act.soft;
                        if (act.sofscl >= 0) def.sofscl = act.sofscl;
                        if (act.lcidab >= 0) def.lcidab = act.lcidab;
                        if (act.maxpar >= 0) def.maxpar = act.maxpar;
                        if (act.sbopt >= 0) def.sbopt = act.sbopt;
                        if (act.depth >= 0) def.depth = act.depth;
                        if (act.bsort >= 0) def.bsort = act.bsort;
                        if (act.frcfrq >= 0) def.frcfrq = act.frcfrq;
                    }
                    // Card B
                    if (act.penmax>=0||act.thkopt>=0||act.shlthk>=0||act.snlog>=0||
                        act.isym>=0||act.i2d3d>=0||act.sldthk>=0||act.sldstf>=0) {
                        def.hasCardB = true; def.hasCardA = true;
                        if (act.penmax >= 0) def.penmax = act.penmax;
                        if (act.thkopt >= 0) def.thkopt = act.thkopt;
                        if (act.shlthk >= 0) def.shlthk = act.shlthk;
                        if (act.snlog >= 0) def.snlog = act.snlog;
                        if (act.isym >= 0) def.isym = act.isym;
                        if (act.i2d3d >= 0) def.i2d3d = act.i2d3d;
                        if (act.sldthk >= 0) def.sldthk = act.sldthk;
                        if (act.sldstf >= 0) def.sldstf = act.sldstf;
                    }
                    // Card C
                    if (act.igap>=0||act.ignore_>=0||act.dprfac>=0||act.dtstif>=0||
                        act.edgek>=0||act.flangl>=0||act.cid_rcf>=0) {
                        def.hasCardC = true; def.hasCardB = true; def.hasCardA = true;
                        if (act.igap >= 0) def.igap = act.igap;
                        if (act.ignore_ >= 0) def.ignore_ = act.ignore_;
                        if (act.dprfac >= 0) def.dprfac = act.dprfac;
                        if (act.dtstif >= 0) def.dtstif = act.dtstif;
                        if (act.edgek >= 0) def.edgek = act.edgek;
                        if (act.flangl >= 0) def.flangl = act.flangl;
                        if (act.cid_rcf >= 0) def.cid_rcf = act.cid_rcf;
                    }
                    // Card D
                    if (act.q2tri>=0||act.dtpchk>=0||act.sfnbr>=0||act.fnlscl>=0||
                        act.dnlscl>=0||act.tcso>=0||act.tiedid>=0||act.shledg>=0) {
                        def.hasCardD = true; def.hasCardC = true;
                        def.hasCardB = true; def.hasCardA = true;
                        if (act.q2tri >= 0) def.q2tri = act.q2tri;
                        if (act.dtpchk >= 0) def.dtpchk = act.dtpchk;
                        if (act.sfnbr >= 0) def.sfnbr = act.sfnbr;
                        if (act.fnlscl >= 0) def.fnlscl = act.fnlscl;
                        if (act.dnlscl >= 0) def.dnlscl = act.dnlscl;
                        if (act.tcso >= 0) def.tcso = act.tcso;
                        if (act.tiedid >= 0) def.tiedid = act.tiedid;
                        if (act.shledg >= 0) def.shledg = act.shledg;
                    }
                    // Card E
                    if (act.sharec>=0||act.cparm8>=0||act.ipback>=0||act.srnde>=0||
                        act.fricsf>=0||act.icor>=0||act.ftorq>=0||act.region>=0) {
                        def.hasCardE = true; def.hasCardD = true;
                        def.hasCardC = true; def.hasCardB = true; def.hasCardA = true;
                        if (act.sharec >= 0) def.sharec = act.sharec;
                        if (act.cparm8 >= 0) def.cparm8 = act.cparm8;
                        if (act.ipback >= 0) def.ipback = act.ipback;
                        if (act.srnde >= 0) def.srnde = act.srnde;
                        if (act.fricsf >= 0) def.fricsf = act.fricsf;
                        if (act.icor >= 0) def.icor = act.icor;
                        if (act.ftorq >= 0) def.ftorq = act.ftorq;
                        if (act.region >= 0) def.region = act.region;
                    }
                    // Card F
                    if (act.pstiff>=0||act.ignroff>=0||act.fstol>=0||
                        act.d2binr>=0||act.ssftyp>=0||act.swtpr>=0||act.tetfac>=0) {
                        def.hasCardF = true; def.hasCardE = true; def.hasCardD = true;
                        def.hasCardC = true; def.hasCardB = true; def.hasCardA = true;
                        if (act.pstiff >= 0) def.pstiff = act.pstiff;
                        if (act.ignroff >= 0) def.ignroff = act.ignroff;
                        if (act.fstol >= 0) def.fstol = act.fstol;
                        if (act.d2binr >= 0) def.d2binr = act.d2binr;
                        if (act.ssftyp >= 0) def.ssftyp = act.ssftyp;
                        if (act.swtpr >= 0) def.swtpr = act.swtpr;
                        if (act.tetfac >= 0) def.tetfac = act.tetfac;
                    }
                    // Card G
                    if (act.shloff >= 0) {
                        def.hasCardG = true; def.hasCardF = true; def.hasCardE = true;
                        def.hasCardD = true; def.hasCardC = true;
                        def.hasCardB = true; def.hasCardA = true;
                        def.shloff = act.shloff;
                    }
                    insertBlocks.push_back(ct_generateContact(def));
                    console.println("[contact] Created *CONTACT_" + preset.keyword);
                }
            }
            continue;
        }

        console.warning("[contact] Unknown action: " + act.action);
    }

    // 6. Apply removals (descending order to preserve indices)
    if (!removeRanges.empty()) {
        std::sort(removeRanges.begin(), removeRanges.end(),
                  [](const auto& a, const auto& b){ return a.first > b.first; });
        for (const auto& [start, end] : removeRanges) {
            ct_removeBlock(lines, start, end);
        }
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

    std::ofstream outf(outPath);
    if (!outf.is_open()) { console.error("Cannot write output: " + outPath); return 1; }
    for (const auto& ln : lines) outf << ln << "\n";
    console.println("[contact] Done -> " + outputFile);
    return 0;
}
