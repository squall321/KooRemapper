#include "optimize.h"
#include "contact_helpers.h"
#include "kw_util.h"
#include "cli/ConsoleOutput.h"
#include <fstream>
#include <sstream>
#include <string>
#include <vector>
#include <set>
#include <cstdio>
#include <cmath>

using namespace KooRemapper;

// ── opt_* helpers ─────────────────────────────────────────────────────────────

static bool opt_contactInvolvesPid(const ContactDef& ct,
                                    const std::set<int>& targetPids,
                                    const std::vector<SetDef>& sets) {
    auto checkSide = [&](int sid, int styp) -> bool {
        if (styp == 3) {
            return targetPids.count(sid) > 0;
        } else if (styp == 2) {
            for (const auto& s : sets) {
                if (s.type == "PART" && s.id == sid) {
                    for (int pid : s.ids) {
                        if (targetPids.count(pid)) return true;
                    }
                }
            }
        }
        return false;
    };
    return checkSide(ct.ssid, ct.sstyp) || checkSide(ct.msid, ct.mstyp);
}

static int opt_patchControlField(std::vector<std::string>& lines,
                                  const std::string& keyword,
                                  int fieldPos, int fieldWidth,
                                  const std::string& newVal) {
    bool inBlock = false, hasTitle = false, titleDone = false;
    for (auto& ln : lines) {
        std::string tr = kw_trim(ln);
        if (tr.empty()) continue;
        if (tr[0] == '*') {
            std::string up = kw_upper(tr);
            inBlock = (up.rfind(keyword, 0) == 0);
            hasTitle = (up.find("_TITLE") != std::string::npos);
            titleDone = false;
            continue;
        }
        if (!inBlock || tr[0] == '$') continue;
        if (hasTitle && !titleDone) { titleDone = true; continue; }
        std::string curVal;
        if ((int)ln.size() > fieldPos) {
            int end = std::min((int)ln.size(), fieldPos + fieldWidth);
            curVal = kw_trim(ln.substr(fieldPos, end - fieldPos));
        }
        if (curVal == kw_trim(newVal)) return 1;
        ln = kw_setField(ln, fieldPos, fieldWidth, newVal);
        return 2;
    }
    return 0;
}

static bool opt_hasKeyword(const std::vector<std::string>& lines, const std::string& keyword) {
    for (const auto& ln : lines) {
        std::string tr = kw_trim(ln);
        if (!tr.empty() && tr[0] == '*') {
            if (kw_upper(tr).rfind(keyword, 0) == 0) return true;
        }
    }
    return false;
}

static std::string opt_readControlField(const std::vector<std::string>& lines,
                                         const std::string& keyword,
                                         int fieldPos, int fieldWidth) {
    bool inBlock = false, hasTitle = false, titleDone = false;
    for (const auto& ln : lines) {
        std::string tr = kw_trim(ln);
        if (tr.empty()) continue;
        if (tr[0] == '*') {
            std::string up = kw_upper(tr);
            inBlock = (up.rfind(keyword, 0) == 0);
            hasTitle = (up.find("_TITLE") != std::string::npos);
            titleDone = false;
            continue;
        }
        if (!inBlock || tr[0] == '$') continue;
        if (hasTitle && !titleDone) { titleDone = true; continue; }
        if ((int)ln.size() > fieldPos) {
            int end = std::min((int)ln.size(), fieldPos + fieldWidth);
            return kw_trim(ln.substr(fieldPos, end - fieldPos));
        }
        return "";
    }
    return "";
}

static bool opt_isImplicit(const std::vector<std::string>& lines) {
    for (const auto& ln : lines) {
        std::string tr = kw_trim(ln);
        if (!tr.empty() && tr[0] == '*') {
            if (kw_upper(tr).rfind("*CONTROL_IMPLICIT", 0) == 0) return true;
        }
    }
    return false;
}

std::vector<std::string> opt_applyRubber(std::vector<std::string>& lines,
                                          const OptimizeConfig& cfg) {
    std::vector<std::string> msgs;
    std::set<int> targetPids(cfg.pids.begin(), cfg.pids.end());

    bool isImplicit;
    if (cfg.analysisType == "implicit") {
        isImplicit = true;
        msgs.push_back("[optimize] Analysis type: implicit (specified)");
    } else if (cfg.analysisType == "explicit") {
        isImplicit = false;
        msgs.push_back("[optimize] Analysis type: explicit (specified)");
    } else {
        isImplicit = opt_isImplicit(lines);
        msgs.push_back(std::string("[optimize] Analysis type: ") +
                       (isImplicit ? "implicit" : "explicit") + " (auto-detected)");
    }

    // 1. CONTROL_ACCURACY: INN=4
    {
        int r = opt_patchControlField(lines, "*CONTROL_ACCURACY", 10, 10, "4");
        if (r == 0) {
            kw_insertBeforeEnd(lines,
                "*CONTROL_ACCURACY\n"
                "$      OSU       INN    PIDOSU\n"
                "         0         4");
            msgs.push_back("[optimize] *CONTROL_ACCURACY: INN=4 (inserted)");
        } else if (r == 2) {
            msgs.push_back("[optimize] *CONTROL_ACCURACY: INN=4 (modified)");
        } else {
            msgs.push_back("[optimize] *CONTROL_ACCURACY: INN=4 (OK)");
        }
    }

    // 2. CONTROL_ENERGY: HGEN=2, RWEN=2, SLNTEN=2, RYLEN=2
    {
        if (!opt_hasKeyword(lines, "*CONTROL_ENERGY")) {
            kw_insertBeforeEnd(lines,
                "*CONTROL_ENERGY\n"
                "$     HGEN      RWEN    SLNTEN     RYLEN\n"
                "         2         2         2         2");
            msgs.push_back("[optimize] *CONTROL_ENERGY: HGEN=2,RWEN=2,SLNTEN=2,RYLEN=2 (inserted)");
        } else {
            bool anyMod = false;
            if (opt_patchControlField(lines, "*CONTROL_ENERGY",  0, 10, "2")==2) anyMod=true;
            if (opt_patchControlField(lines, "*CONTROL_ENERGY", 10, 10, "2")==2) anyMod=true;
            if (opt_patchControlField(lines, "*CONTROL_ENERGY", 20, 10, "2")==2) anyMod=true;
            if (opt_patchControlField(lines, "*CONTROL_ENERGY", 30, 10, "2")==2) anyMod=true;
            msgs.push_back(std::string("[optimize] *CONTROL_ENERGY: HGEN=2,RWEN=2,SLNTEN=2,RYLEN=2 (") +
                           (anyMod ? "modified)" : "OK)"));
        }
    }

    // 3. CONTROL_TIMESTEP: TSSFAC — explicit only
    if (!isImplicit) {
        char buf[16];
        snprintf(buf, sizeof(buf), "%10.6f", cfg.tssfac);
        std::string tssfacStr(buf);

        if (!opt_hasKeyword(lines, "*CONTROL_TIMESTEP")) {
            kw_insertBeforeEnd(lines,
                "*CONTROL_TIMESTEP\n"
                "$   DTINIT    TSSFAC      ISDO    TSLIMT     DT2MS      LCTM     ERODE     MS1ST\n"
                "       0.0" + tssfacStr + "         0       0.0       0.0         0         0         0");
            msgs.push_back("[optimize] *CONTROL_TIMESTEP: TSSFAC=" + kw_trim(tssfacStr) + " (inserted)");
        } else {
            std::string oldVal = opt_readControlField(lines, "*CONTROL_TIMESTEP", 10, 10);
            int r = opt_patchControlField(lines, "*CONTROL_TIMESTEP", 10, 10, kw_trim(tssfacStr));
            if (r == 2)
                msgs.push_back("[optimize] *CONTROL_TIMESTEP: TSSFAC=" + kw_trim(tssfacStr) + " (was " + oldVal + ")");
            else
                msgs.push_back("[optimize] *CONTROL_TIMESTEP: TSSFAC=" + kw_trim(tssfacStr) + " (OK)");
        }

        std::string dt2ms = opt_readControlField(lines, "*CONTROL_TIMESTEP", 40, 10);
        if (!dt2ms.empty()) {
            double dt2msVal = 0;
            try { dt2msVal = std::stod(dt2ms); } catch(...) {}
            if (dt2msVal != 0.0)
                msgs.push_back("[optimize] WARNING: DT2MS=" + dt2ms + " (dynamic impact requires DT2MS=0)");
        }
    } else {
        msgs.push_back("[optimize] *CONTROL_TIMESTEP: TSSFAC skipped (implicit — use CONTROL_IMPLICIT_AUTO dt0/dtmax)");
    }

    // 4. CONTROL_BULK_VISCOSITY: warning only, explicit only
    if (!isImplicit) {
        if (opt_hasKeyword(lines, "*CONTROL_BULK_VISCOSITY")) {
            std::string q1s = opt_readControlField(lines, "*CONTROL_BULK_VISCOSITY", 0, 10);
            std::string q2s = opt_readControlField(lines, "*CONTROL_BULK_VISCOSITY", 10, 10);
            double q1v = 1.5, q2v = 0.06;
            try { q1v = std::stod(q1s); } catch(...) {}
            try { q2v = std::stod(q2s); } catch(...) {}
            if (std::abs(q1v - 1.5) < 0.01 && std::abs(q2v - 0.06) < 0.001) {
                msgs.push_back("[optimize] *CONTROL_BULK_VISCOSITY: Q1=1.5, Q2=0.06 (OK)");
            } else {
                char wbuf[128];
                snprintf(wbuf, sizeof(wbuf),
                    "[optimize] WARNING: *CONTROL_BULK_VISCOSITY Q1=%.2f Q2=%.3f (recommended: Q1=1.5, Q2=0.06)", q1v, q2v);
                msgs.push_back(std::string(wbuf));
            }
        } else {
            msgs.push_back("[optimize] *CONTROL_BULK_VISCOSITY: not present (LS-DYNA defaults apply)");
        }
    } else {
        msgs.push_back("[optimize] *CONTROL_BULK_VISCOSITY: skipped (implicit — not applicable)");
    }

    // 5. CONTACT: SOFT=0, SBOPT=2.0 for target PIDs
    if (!targetPids.empty()) {
        auto contacts = ct_parseContacts(lines);
        auto sets = ct_parseSets(lines);
        int modCount = 0;

        for (const auto& ct : contacts) {
            if (!opt_contactInvolvesPid(ct, targetPids, sets)) continue;

            bool titleSkipped = !ct.hasTitle;
            int cardNum = 0;
            for (int i = ct.startLine + 1; i < ct.endLine; ++i) {
                std::string dtr = kw_trim(lines[i]);
                if (dtr.empty() || dtr[0] == '$') continue;
                if (!titleSkipped) { titleSkipped = true; continue; }
                if (cardNum == 3) {
                    bool modified = false;
                    char buf[16];

                    auto softToks = kw_tok10(lines[i]);
                    int curSoft = 0;
                    if (!softToks.empty()) try { curSoft = std::stoi(softToks[0]); } catch(...) {}
                    if (curSoft != 0) {
                        lines[i] = kw_setField(lines[i], 0, 10, "0");
                        modified = true;
                        snprintf(buf, sizeof(buf), "SOFT=%d->0", curSoft);
                        msgs.push_back("[optimize] CONTACT #" + std::to_string(ct.index) + ": " + buf);
                    }

                    int curSbopt = 2;
                    if (softToks.size() >= 5) try { curSbopt = std::stoi(softToks[4]); } catch(...) {}
                    if (curSbopt == 1) {
                        lines[i] = kw_setField(lines[i], 40, 10, "2");
                        modified = true;
                        msgs.push_back("[optimize] CONTACT #" + std::to_string(ct.index) + ": SBOPT=1->2");
                    }

                    if (modified) modCount++;
                    break;
                }
                cardNum++;
            }

            if (!ct.hasCardA && ct.soft != 0) {
                msgs.push_back("[optimize] CONTACT #" + std::to_string(ct.index) +
                               ": no Card A found, cannot set SOFT/SBOPT");
            }
        }

        for (const auto& ct : contacts) {
            if (ct.sstyp == 0 && ct.mstyp == 0) continue;
            bool hasPid = false;
            if (ct.sstyp == 3 && targetPids.count(ct.ssid)) hasPid = true;
            if (ct.mstyp == 3 && targetPids.count(ct.msid)) hasPid = true;
            if (!hasPid) continue;
            if (ct.sstyp == 0 || ct.mstyp == 0)
                msgs.push_back("[optimize] WARNING: CONTACT #" + std::to_string(ct.index) +
                               " has SSTYP=0 side - SOFT/SBOPT not verified");
        }

        if (modCount > 0)
            msgs.push_back("[optimize] " + std::to_string(modCount) + " contact(s) modified");
    }

    return msgs;
}

int runOptimize(const std::string& yamlFile, ConsoleOutput& console) {
    // Parse YAML
    std::ifstream f(yamlFile);
    if (!f.is_open()) { console.error("Cannot open: " + yamlFile); return 1; }

    std::string configDir;
    size_t lastSlash = yamlFile.find_last_of("/\\");
    if (lastSlash != std::string::npos) configDir = yamlFile.substr(0, lastSlash);

    auto trim = [](const std::string& s) -> std::string {
        size_t a=0, b=s.size();
        while (a<b && std::isspace((unsigned char)s[a])) ++a;
        while (b>a && std::isspace((unsigned char)s[b-1])) --b;
        return s.substr(a,b-a);
    };

    std::string modelFile, outputFile;
    OptimizeConfig cfg;
    cfg.mode = "rubber";  // default

    std::string ln;
    while (std::getline(f, ln)) {
        if (!ln.empty() && ln.back()=='\r') ln.pop_back();
        std::string tr = trim(ln);
        if (tr.empty() || tr[0]=='#') continue;
        size_t cp = tr.find(':');
        if (cp == std::string::npos) continue;
        std::string key = trim(tr.substr(0, cp));
        std::string val = trim(tr.substr(cp+1));

        if      (key == "model")    modelFile = val;
        else if (key == "output")   outputFile = val;
        else if (key == "optimize")      cfg.mode = val;
        else if (key == "tssfac")        { try { cfg.tssfac = std::stod(val); } catch(...) {} }
        else if (key == "analysis_type") cfg.analysisType = val;
        else if (key == "pid")           cfg.pids = { std::stoi(val) };
        else if (key == "pids") {
            std::string lv = val;
            if (!lv.empty() && lv.front()=='[') lv = lv.substr(1);
            if (!lv.empty() && lv.back()==']') lv.pop_back();
            std::istringstream ss(lv); std::string tok;
            while (std::getline(ss, tok, ',')) {
                std::string t = trim(tok);
                if (!t.empty()) try { cfg.pids.push_back(std::stoi(t)); } catch(...) {}
            }
        }
    }

    if (modelFile.empty())  { console.error("optimize YAML: 'model' not specified");  return 1; }
    if (outputFile.empty()) { console.error("optimize YAML: 'output' not specified"); return 1; }

    // Resolve paths relative to configDir
    auto resolvePath = [&](const std::string& p) -> std::string {
        if (!configDir.empty() && !p.empty() &&
            p[0] != '/' && p[0] != '\\' &&
            !(p.size() >= 2 && p[1] == ':')) {
            return configDir + "/" + p;
        }
        return p;
    };
    std::string modelPath = resolvePath(modelFile);
    std::string outputPath = resolvePath(outputFile);

    console.println("[optimize] Mode   : " + cfg.mode);
    console.println("[optimize] Model  : " + modelPath);
    console.println("[optimize] Output : " + outputPath);
    if (!cfg.pids.empty()) {
        std::string pidStr;
        for (int pid : cfg.pids) {
            if (!pidStr.empty()) pidStr += ", ";
            pidStr += std::to_string(pid);
        }
        console.println("[optimize] PIDs   : " + pidStr);
    }

    // Read model
    std::vector<std::string> lines;
    {
        std::ifstream mf(modelPath);
        if (!mf.is_open()) { console.error("Cannot open model: " + modelPath); return 1; }
        std::string l;
        while (std::getline(mf, l)) {
            if (!l.empty() && l.back()=='\r') l.pop_back();
            lines.push_back(l);
        }
    }

    // Apply optimization
    std::vector<std::string> msgs;
    if (cfg.mode == "rubber") {
        msgs = opt_applyRubber(lines, cfg);
    } else {
        console.error("Unknown optimize mode: " + cfg.mode);
        return 1;
    }

    for (const auto& m : msgs) console.println(m);

    // Write output
    {
        std::ofstream fout(outputPath);
        if (!fout.is_open()) { console.error("Cannot write: " + outputPath); return 1; }
        for (const auto& l : lines) fout << l << "\n";
    }

    console.println("[optimize] Done -> " + outputPath);
    return 0;
}
