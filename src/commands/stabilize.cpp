#include "stabilize.h"
#include "kw_util.h"
#include "cli/ConsoleOutput.h"

#include <string>
#include <fstream>
#include <vector>
#include <climits>
#include <cstdio>
#include <iostream>

using KooRemapper::ConsoleOutput;

static bool stab_hasShellElements(const std::vector<std::string>& lines) {
    for (const auto& ln : lines) {
        std::string tr = kw_trim(ln);
        if (!tr.empty() && tr[0] == '*')
            if (kw_upper(tr).rfind("*ELEMENT_SHELL", 0) == 0) return true;
    }
    return false;
}

// Like kw_patchControlField but can target card N (0=first data card)
static int stab_patchControlFieldN(std::vector<std::string>& lines,
                                    const std::string& keyword, int cardIdx,
                                    int fieldPos, int fieldWidth,
                                    const std::string& newVal) {
    bool inBlock = false, hasTitle = false, titleDone = false;
    int dataCardSeen = 0;
    for (auto& ln : lines) {
        std::string tr = kw_trim(ln);
        if (tr.empty()) continue;
        if (tr[0] == '*') {
            std::string up = kw_upper(tr);
            inBlock    = (up.rfind(keyword, 0) == 0);
            hasTitle   = (up.find("_TITLE") != std::string::npos);
            titleDone  = false;
            dataCardSeen = 0;
            continue;
        }
        if (!inBlock || tr[0] == '$') continue;
        if (hasTitle && !titleDone) { titleDone = true; continue; }
        if (dataCardSeen < cardIdx) { ++dataCardSeen; continue; }
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

// If *CONTROL_CONTACT exists with only Card 1, insert a blank Card 2 after it.
static void stab_ensureControlContactCard2(std::vector<std::string>& lines) {
    bool inBlock = false, hasTitle = false, titleDone = false;
    int dataCardSeen = 0, card1Idx = -1;
    for (int i = 0; i < (int)lines.size(); ++i) {
        std::string tr = kw_trim(lines[i]);
        if (tr.empty()) continue;
        if (tr[0] == '*') {
            std::string up = kw_upper(tr);
            bool isCC = (up.rfind("*CONTROL_CONTACT", 0) == 0);
            if (inBlock && card1Idx >= 0 && dataCardSeen == 1) {
                lines.insert(lines.begin() + card1Idx + 1, "");
                return;
            }
            inBlock      = isCC;
            hasTitle     = isCC && (up.find("_TITLE") != std::string::npos);
            titleDone    = false;
            dataCardSeen = 0;
            card1Idx     = -1;
            continue;
        }
        if (!inBlock || tr[0] == '$') continue;
        if (hasTitle && !titleDone) { titleDone = true; continue; }
        if (dataCardSeen == 0) card1Idx = i;
        else if (dataCardSeen == 1) return;
        ++dataCardSeen;
    }
    if (inBlock && card1Idx >= 0 && dataCardSeen == 1)
        lines.insert(lines.begin() + card1Idx + 1, "");
}

static void stab_resolveLevel(StabilizeConfig& cfg) {
    int lv = cfg.level;
    if (lv <= 0) return;

    if (lv >= 1) {
        if (cfg.hgen   < 0) cfg.hgen   = 2;
        if (cfg.rwen   < 0) cfg.rwen   = 2;
        if (cfg.slnten < 0) cfg.slnten = 2;
        if (cfg.rylen  < 0) cfg.rylen  = 2;
    }
    if (lv >= 2) {
        if (cfg.osu        < 0) cfg.osu        = 1;
        if (cfg.inn        < 0) cfg.inn        = 4;
        if (cfg.esortSolid < 0) cfg.esortSolid = 1;
        if (cfg.esortShell < 0) cfg.esortShell = 1;
    }
    if (lv >= 3) {
        if (cfg.tssfac < 0) cfg.tssfac = 0.80;
    }
    if (lv >= 4) {
        if (cfg.ihq < 0) cfg.ihq = 4;
        if (cfg.qh  < 0) cfg.qh  = 0.10;
    }
    if (lv >= 5) {
        if (cfg.bwc   < 0)        cfg.bwc   = 1;
        if (cfg.miter < 0)        cfg.miter = 2;
        if (cfg.irnxx == INT_MIN) cfg.irnxx = -2;
        if (cfg.wrpang < 0)       cfg.wrpang = 10.0;
    }
    if (lv >= 6) {
        if (cfg.orien  < 0) cfg.orien  = 2;
        if (cfg.shlthk < 0) cfg.shlthk = 1;
        if (cfg.xpene  < 0) cfg.xpene  = 2.0;
        if (cfg.islchk < 0) cfg.islchk = 2;
        if (cfg.soft   < 0) cfg.soft   = 1;
        if (cfg.sbopt  < 0) cfg.sbopt  = 2;
        if (cfg.depth  < 0) cfg.depth  = 3;
    }
    if (lv >= 7) {
        if (cfg.tssfac < 0 || cfg.tssfac > 0.67) cfg.tssfac = 0.67;
        if (cfg.bulkQ1 < 0) cfg.bulkQ1 = 1.5;
        if (cfg.bulkQ2 < 0) cfg.bulkQ2 = 0.06;
    }
    if (lv >= 8) {
        cfg.shlthk = 2;
        cfg.soft   = 2;
        cfg.sbopt  = 3;
        cfg.depth  = 5;
        if (cfg.nsbcs  < 0) cfg.nsbcs  = 5;
        if (cfg.enmass < 0) cfg.enmass = 1;
        if (cfg.ignore_ < 0) cfg.ignore_ = 1;
        if (cfg.maxpar  < 0) cfg.maxpar  = 1.15;
    }
    if (lv >= 9) {
        cfg.ihq = 6;
        cfg.qh  = 1.0;
    }
    if (lv >= 10) {
        if (cfg.tssfac > 0.60) cfg.tssfac = 0.60;
        if (cfg.nsbcs  > 2)    cfg.nsbcs  = 2;
    }
    if (lv >= 11) {
        if (cfg.erode < 0) cfg.erode = 11;
        cfg.enmass = 2;
        if (cfg.nsbcs  > 1)    cfg.nsbcs  = 1;
        if (cfg.tssfac > 0.55) cfg.tssfac = 0.55;
    }
    if (lv >= 12) {
        if (cfg.tssfac > 0.50) cfg.tssfac = 0.50;
        cfg.bulkQ1 = 2.0;
        cfg.bulkQ2 = 0.10;
    }
}

std::vector<std::string> stab_applyExplicit(
        std::vector<std::string>& lines,
        const StabilizeConfig& cfg) {
    std::vector<std::string> msgs;
    auto tag = [](const std::string& s) { return "[stabilize] " + s; };

    bool hasShell = stab_hasShellElements(lines);
    if (!hasShell) msgs.push_back(tag("Note: No *ELEMENT_SHELL — shell-specific options will be skipped"));

    // ── 1. CONTROL_ENERGY ────────────────────────────────────────────
    if (cfg.hgen >= 0 || cfg.rwen >= 0 || cfg.slnten >= 0 || cfg.rylen >= 0) {
        int h = cfg.hgen   >= 0 ? cfg.hgen   : 2;
        int r = cfg.rwen   >= 0 ? cfg.rwen   : 2;
        int s = cfg.slnten >= 0 ? cfg.slnten : 2;
        int y = cfg.rylen  >= 0 ? cfg.rylen  : 2;
        bool anyMod = false;
        if (!kw_hasKeyword(lines, "*CONTROL_ENERGY")) {
            char buf[90]; snprintf(buf, sizeof(buf), "%10d%10d%10d%10d", h, r, s, y);
            kw_insertBeforeEnd(lines,
                "*CONTROL_ENERGY\n"
                "$     HGEN      RWEN    SLNTEN     RYLEN\n" + std::string(buf));
            msgs.push_back(tag("*CONTROL_ENERGY: HGEN=" + std::to_string(h) +
                               ",RWEN=" + std::to_string(r) + ",SLNTEN=" + std::to_string(s) +
                               ",RYLEN=" + std::to_string(y) + " (inserted)"));
        } else {
            if (cfg.hgen   >= 0 && kw_patchControlField(lines, "*CONTROL_ENERGY",  0, 10, std::to_string(cfg.hgen))   == 2) anyMod = true;
            if (cfg.rwen   >= 0 && kw_patchControlField(lines, "*CONTROL_ENERGY", 10, 10, std::to_string(cfg.rwen))   == 2) anyMod = true;
            if (cfg.slnten >= 0 && kw_patchControlField(lines, "*CONTROL_ENERGY", 20, 10, std::to_string(cfg.slnten)) == 2) anyMod = true;
            if (cfg.rylen  >= 0 && kw_patchControlField(lines, "*CONTROL_ENERGY", 30, 10, std::to_string(cfg.rylen))  == 2) anyMod = true;
            msgs.push_back(tag(std::string("*CONTROL_ENERGY: ") + (anyMod ? "modified" : "OK")));
        }
    }

    // ── 2. CONTROL_ACCURACY ──────────────────────────────────────────
    if (cfg.osu >= 0 || cfg.inn >= 0) {
        bool anyMod = false;
        if (!kw_hasKeyword(lines, "*CONTROL_ACCURACY")) {
            int o = cfg.osu >= 0 ? cfg.osu : 0;
            int n = cfg.inn >= 0 ? cfg.inn : 4;
            char buf[90]; snprintf(buf, sizeof(buf), "%10d%10d", o, n);
            kw_insertBeforeEnd(lines,
                "*CONTROL_ACCURACY\n"
                "$      OSU       INN    PIDOSU\n" + std::string(buf));
            msgs.push_back(tag("*CONTROL_ACCURACY: OSU=" + std::to_string(o) +
                               ",INN=" + std::to_string(n) + " (inserted)"));
        } else {
            if (cfg.osu >= 0 && kw_patchControlField(lines, "*CONTROL_ACCURACY",  0, 10, std::to_string(cfg.osu)) == 2) anyMod = true;
            if (cfg.inn >= 0 && kw_patchControlField(lines, "*CONTROL_ACCURACY", 10, 10, std::to_string(cfg.inn)) == 2) anyMod = true;
            msgs.push_back(tag(std::string("*CONTROL_ACCURACY: ") + (anyMod ? "modified" : "OK")));
        }
    }

    // ── 3. CONTROL_SOLID (ESORT) ──────────────────────────────────────
    if (cfg.esortSolid >= 0) {
        int r = kw_patchControlField(lines, "*CONTROL_SOLID", 0, 10, std::to_string(cfg.esortSolid));
        if (r == 0) {
            char buf[90]; snprintf(buf, sizeof(buf), "%10d", cfg.esortSolid);
            kw_insertBeforeEnd(lines,
                "*CONTROL_SOLID\n"
                "$    ESORT    FMATRX    NIPTETS     SWLOCL     PSFAIL       T10      ICOH     TET13\n" + std::string(buf));
            msgs.push_back(tag("*CONTROL_SOLID: ESORT=" + std::to_string(cfg.esortSolid) + " (inserted)"));
        } else {
            msgs.push_back(tag(std::string("*CONTROL_SOLID: ESORT=") + std::to_string(cfg.esortSolid) +
                               (r == 2 ? " (modified)" : " (OK)")));
        }
    }

    // ── 4. CONTROL_SHELL (WRPANG ESORT IRNXX BWC MITER) ──────────────
    bool needShellCard = (cfg.esortShell >= 0 || cfg.bwc >= 0 || cfg.miter >= 0 ||
                          cfg.irnxx != INT_MIN || cfg.wrpang >= 0);
    if (needShellCard && !hasShell) {
        msgs.push_back(tag("*CONTROL_SHELL: skipped (no shell elements in model)"));
    } else if (needShellCard) {
        bool anyMod = false;
        if (!kw_hasKeyword(lines, "*CONTROL_SHELL")) {
            double wrp = cfg.wrpang     >= 0       ? cfg.wrpang     : 20.0;
            int    es  = cfg.esortShell >= 0       ? cfg.esortShell : 0;
            int    iro = cfg.irnxx      != INT_MIN ? cfg.irnxx      : -1;
            int    bw  = cfg.bwc        >= 0       ? cfg.bwc        : 2;
            int    mi  = cfg.miter      >= 0       ? cfg.miter      : 1;
            char buf[90];
            snprintf(buf, sizeof(buf), "%10.4f%10d%10d%10s%10s%10d%10d",
                     wrp, es, iro, "", "", bw, mi);
            kw_insertBeforeEnd(lines,
                "*CONTROL_SHELL\n"
                "$   WRPANG     ESORT     IRNXX    ISTUPD    THEORY       BWC     MITER      PROJ\n" +
                std::string(buf));
            msgs.push_back(tag("*CONTROL_SHELL: inserted"));
        } else {
            if (cfg.wrpang >= 0) {
                char buf[16]; snprintf(buf, sizeof(buf), "%10.4f", cfg.wrpang);
                if (kw_patchControlField(lines, "*CONTROL_SHELL",  0, 10, std::string(buf)) == 2) anyMod = true;
            }
            if (cfg.esortShell >= 0 && kw_patchControlField(lines, "*CONTROL_SHELL", 10, 10, std::to_string(cfg.esortShell)) == 2) anyMod = true;
            if (cfg.irnxx != INT_MIN && kw_patchControlField(lines, "*CONTROL_SHELL", 20, 10, std::to_string(cfg.irnxx)) == 2) anyMod = true;
            if (cfg.bwc   >= 0 && kw_patchControlField(lines, "*CONTROL_SHELL", 50, 10, std::to_string(cfg.bwc))   == 2) anyMod = true;
            if (cfg.miter >= 0 && kw_patchControlField(lines, "*CONTROL_SHELL", 60, 10, std::to_string(cfg.miter)) == 2) anyMod = true;
            msgs.push_back(tag(std::string("*CONTROL_SHELL: ") + (anyMod ? "modified" : "OK")));
        }
    }

    // ── 5. CONTROL_TIMESTEP (TSSFAC, ERODE) ──────────────────────────
    if (cfg.tssfac >= 0 || cfg.erode >= 0) {
        bool anyMod = false;
        if (!kw_hasKeyword(lines, "*CONTROL_TIMESTEP")) {
            double ts = cfg.tssfac >= 0 ? cfg.tssfac : 0.9;
            int    er = cfg.erode  >= 0 ? cfg.erode  : 0;
            char buf[90];
            snprintf(buf, sizeof(buf), "       0.0%10.6f         0       0.0       0.0         0%10d         0",
                     ts, er);
            kw_insertBeforeEnd(lines,
                "*CONTROL_TIMESTEP\n"
                "$   DTINIT    TSSFAC      ISDO    TSLIMT     DT2MS      LCTM     ERODE     MS1ST\n" +
                std::string(buf));
            msgs.push_back(tag("*CONTROL_TIMESTEP: inserted"));
        } else {
            if (cfg.tssfac >= 0) {
                char buf[16]; snprintf(buf, sizeof(buf), "%10.6f", cfg.tssfac);
                int r = kw_patchControlField(lines, "*CONTROL_TIMESTEP", 10, 10, std::string(buf));
                if (r == 2) anyMod = true;
                msgs.push_back(tag("*CONTROL_TIMESTEP: TSSFAC=" + std::to_string(cfg.tssfac) +
                                   (r == 2 ? " (modified)" : " (OK)")));
            }
            if (cfg.erode >= 0) {
                int r = kw_patchControlField(lines, "*CONTROL_TIMESTEP", 60, 10, std::to_string(cfg.erode));
                if (r == 2) anyMod = true;
                msgs.push_back(tag("*CONTROL_TIMESTEP: ERODE=" + std::to_string(cfg.erode) +
                                   (r == 2 ? " (modified)" : " (OK)")));
            }
        }
    }

    // ── 6. CONTROL_HOURGLASS ─────────────────────────────────────────
    if (cfg.ihq >= 0 || cfg.qh >= 0) {
        bool anyMod = false;
        if (!kw_hasKeyword(lines, "*CONTROL_HOURGLASS")) {
            int    h = cfg.ihq >= 0 ? cfg.ihq : 1;
            double q = cfg.qh  >= 0 ? cfg.qh  : 0.1;
            char buf[90]; snprintf(buf, sizeof(buf), "%10d%10.4f", h, q);
            kw_insertBeforeEnd(lines,
                "*CONTROL_HOURGLASS\n"
                "$      IHQ        QH\n" + std::string(buf));
            msgs.push_back(tag("*CONTROL_HOURGLASS: IHQ=" + std::to_string(h) +
                               ",QH=" + std::to_string(q) + " (inserted)"));
        } else {
            if (cfg.ihq >= 0 && kw_patchControlField(lines, "*CONTROL_HOURGLASS", 0, 10, std::to_string(cfg.ihq)) == 2) anyMod = true;
            if (cfg.qh  >= 0) {
                char buf[16]; snprintf(buf, sizeof(buf), "%10.4f", cfg.qh);
                if (kw_patchControlField(lines, "*CONTROL_HOURGLASS", 10, 10, std::string(buf)) == 2) anyMod = true;
            }
            msgs.push_back(tag(std::string("*CONTROL_HOURGLASS: ") + (anyMod ? "modified" : "OK")));
        }
    }

    // ── 7. CONTROL_CONTACT (Card 1 + Card 2) ─────────────────────────
    bool needCC1 = (cfg.orien >= 0 || cfg.shlthk >= 0 || cfg.islchk >= 0 || cfg.enmass >= 0);
    bool needCC2 = (cfg.nsbcs >= 0 || cfg.xpene  >= 0);
    if (needCC1 || needCC2) {
        bool anyMod = false;
        if (!kw_hasKeyword(lines, "*CONTROL_CONTACT")) {
            std::string c1(80, ' ');
            if (cfg.islchk >= 0) c1 = kw_setField(c1, 20, 10, std::to_string(cfg.islchk));
            if (cfg.shlthk >= 0) c1 = kw_setField(c1, 30, 10, std::to_string(cfg.shlthk));
            if (cfg.orien  >= 0) c1 = kw_setField(c1, 60, 10, std::to_string(cfg.orien));
            if (cfg.enmass >= 0) c1 = kw_setField(c1, 70, 10, std::to_string(cfg.enmass));
            std::string c2(80, ' ');
            if (cfg.nsbcs >= 0) c2 = kw_setField(c2, 20, 10, std::to_string(cfg.nsbcs));
            if (cfg.xpene >= 0) {
                char buf[16]; snprintf(buf, sizeof(buf), "%10.4f", cfg.xpene);
                c2 = kw_setField(c2, 40, 10, std::string(buf));
            }
            kw_insertBeforeEnd(lines,
                "*CONTROL_CONTACT\n"
                "$    SLSFAC    RWPNAL    ISLCHK    SHLTHK    PENOPT    THKCHG     ORIEN    ENMASS\n" + c1 + "\n"
                "$    USRSTR    USRFRC     NSBCS    INTERM     XPENE     SSTHK      ECDT   TIEDPRJ\n" + c2);
            msgs.push_back(tag("*CONTROL_CONTACT: inserted"));
        } else {
            if (cfg.islchk >= 0 && kw_patchControlField(lines, "*CONTROL_CONTACT", 20, 10, std::to_string(cfg.islchk)) == 2) anyMod = true;
            if (cfg.shlthk >= 0 && kw_patchControlField(lines, "*CONTROL_CONTACT", 30, 10, std::to_string(cfg.shlthk)) == 2) anyMod = true;
            if (cfg.orien  >= 0 && kw_patchControlField(lines, "*CONTROL_CONTACT", 60, 10, std::to_string(cfg.orien))  == 2) anyMod = true;
            if (cfg.enmass >= 0 && kw_patchControlField(lines, "*CONTROL_CONTACT", 70, 10, std::to_string(cfg.enmass)) == 2) anyMod = true;
            if (needCC2) {
                stab_ensureControlContactCard2(lines);
                if (cfg.nsbcs >= 0 && stab_patchControlFieldN(lines, "*CONTROL_CONTACT", 1, 20, 10, std::to_string(cfg.nsbcs)) == 2) anyMod = true;
                if (cfg.xpene >= 0) {
                    char buf[16]; snprintf(buf, sizeof(buf), "%10.4f", cfg.xpene);
                    if (stab_patchControlFieldN(lines, "*CONTROL_CONTACT", 1, 40, 10, std::string(buf)) == 2) anyMod = true;
                }
            }
            msgs.push_back(tag(std::string("*CONTROL_CONTACT: ") + (anyMod ? "modified" : "OK")));
        }
    }

    // ── 8. CONTROL_BULK_VISCOSITY (forced override) ────────────────────
    if (cfg.bulkQ1 >= 0 || cfg.bulkQ2 >= 0) {
        bool anyMod = false;
        if (!kw_hasKeyword(lines, "*CONTROL_BULK_VISCOSITY")) {
            double q1 = cfg.bulkQ1 >= 0 ? cfg.bulkQ1 : 1.5;
            double q2 = cfg.bulkQ2 >= 0 ? cfg.bulkQ2 : 0.06;
            char buf[90]; snprintf(buf, sizeof(buf), "%10.4f%10.4f", q1, q2);
            kw_insertBeforeEnd(lines,
                "*CONTROL_BULK_VISCOSITY\n"
                "$       Q1        Q2\n" + std::string(buf));
            msgs.push_back(tag("*CONTROL_BULK_VISCOSITY: Q1=" + std::to_string(q1) +
                               ",Q2=" + std::to_string(q2) + " (inserted)"));
        } else {
            if (cfg.bulkQ1 >= 0) {
                char buf[16]; snprintf(buf, sizeof(buf), "%10.4f", cfg.bulkQ1);
                if (kw_patchControlField(lines, "*CONTROL_BULK_VISCOSITY",  0, 10, std::string(buf)) == 2) anyMod = true;
            }
            if (cfg.bulkQ2 >= 0) {
                char buf[16]; snprintf(buf, sizeof(buf), "%10.4f", cfg.bulkQ2);
                if (kw_patchControlField(lines, "*CONTROL_BULK_VISCOSITY", 10, 10, std::string(buf)) == 2) anyMod = true;
            }
            msgs.push_back(tag(std::string("*CONTROL_BULK_VISCOSITY: ") + (anyMod ? "modified (forced)" : "OK")));
        }
    }

    // ── 9. Per-contact optional cards (Card A: SOFT/SBOPT/DEPTH/MAXPAR; Card C: IGNORE) ──
    bool needPerContact = (cfg.soft >= 0 || cfg.sbopt >= 0 || cfg.depth >= 0 ||
                           cfg.maxpar >= 0 || cfg.ignore_ >= 0);
    if (needPerContact) {
        stab_applyPerContact(lines, cfg, msgs);
    }

    return msgs;
}

int runStabilize(const std::string& yamlFile, ConsoleOutput& console) {
    std::ifstream f(yamlFile);
    if (!f.is_open()) { console.error("Cannot open: " + yamlFile); return 1; }

    std::string configDir;
    size_t lastSlash = yamlFile.find_last_of("/\\");
    if (lastSlash != std::string::npos) configDir = yamlFile.substr(0, lastSlash);

    std::string modelFile, outputFile;
    StabilizeConfig cfg;
    cfg.mode = "explicit";

    std::string ln;
    while (std::getline(f, ln)) {
        if (!ln.empty() && ln.back()=='\r') ln.pop_back();
        std::string tr = kw_trim(ln);
        if (tr.empty() || tr[0]=='#') continue;
        size_t cp = tr.find(':');
        if (cp == std::string::npos) continue;
        std::string key = kw_trim(tr.substr(0, cp));
        std::string val = kw_trim(tr.substr(cp+1));
        if (val.empty()) continue;

        auto parseInt  = [&](int& v)    { try { v = std::stoi(val); } catch(...) {} };
        auto parseDbl  = [&](double& v) { try { v = std::stod(val); } catch(...) {} };
        auto parseBool = [&](bool& v)   { v = (val=="true"||val=="yes"||val=="1"); };

        if      (key == "model")           modelFile = val;
        else if (key == "output")          outputFile = val;
        else if (key == "stabilize")       cfg.mode = val;
        else if (key == "level")           parseInt(cfg.level);
        else if (key == "confirm_erosion") parseBool(cfg.confirmErosion);
        else if (key == "tssfac")          parseDbl(cfg.tssfac);
        else if (key == "erode")           parseInt(cfg.erode);
        else if (key == "ihq")             parseInt(cfg.ihq);
        else if (key == "qh")              parseDbl(cfg.qh);
        else if (key == "osu")             parseInt(cfg.osu);
        else if (key == "inn")             parseInt(cfg.inn);
        else if (key == "esort_solid")     parseInt(cfg.esortSolid);
        else if (key == "esort_shell")     parseInt(cfg.esortShell);
        else if (key == "bwc")             parseInt(cfg.bwc);
        else if (key == "miter")           parseInt(cfg.miter);
        else if (key == "irnxx")           parseInt(cfg.irnxx);
        else if (key == "wrpang")          parseDbl(cfg.wrpang);
        else if (key == "orien")           parseInt(cfg.orien);
        else if (key == "shlthk")         parseInt(cfg.shlthk);
        else if (key == "enmass")          parseInt(cfg.enmass);
        else if (key == "islchk")          parseInt(cfg.islchk);
        else if (key == "xpene")           parseDbl(cfg.xpene);
        else if (key == "nsbcs")           parseInt(cfg.nsbcs);
        else if (key == "soft")            parseInt(cfg.soft);
        else if (key == "sbopt")           parseInt(cfg.sbopt);
        else if (key == "depth")           parseInt(cfg.depth);
        else if (key == "maxpar")          parseDbl(cfg.maxpar);
        else if (key == "ignore")          parseInt(cfg.ignore_);
        else if (key == "bulk_q1")         parseDbl(cfg.bulkQ1);
        else if (key == "bulk_q2")         parseDbl(cfg.bulkQ2);
        else if (key == "hgen")            parseInt(cfg.hgen);
        else if (key == "rwen")            parseInt(cfg.rwen);
        else if (key == "slnten")          parseInt(cfg.slnten);
        else if (key == "rylen")           parseInt(cfg.rylen);
    }

    if (modelFile.empty())  { console.error("stabilize YAML: 'model' not specified");  return 1; }
    if (outputFile.empty()) { console.error("stabilize YAML: 'output' not specified"); return 1; }

    auto resolvePath = [&](const std::string& p) -> std::string {
        if (!configDir.empty() && !p.empty() &&
            p[0] != '/' && p[0] != '\\' &&
            !(p.size() >= 2 && p[1] == ':'))
            return configDir + "/" + p;
        return p;
    };
    std::string modelPath  = resolvePath(modelFile);
    std::string outputPath = resolvePath(outputFile);

    stab_resolveLevel(cfg);

    if (cfg.erode >= 0 && !cfg.confirmErosion) {
        console.println("[stabilize] WARNING: ERODE=" + std::to_string(cfg.erode) +
                        " will allow element deletion during the simulation.");
        console.println("[stabilize] Add 'confirm_erosion: true' to YAML to skip this prompt.");
        std::cout << "Apply ERODE? [y/N]: " << std::flush;
        std::string answer;
        std::getline(std::cin, answer);
        for (auto& c : answer) c = (char)std::tolower((unsigned char)c);
        if (answer != "y" && answer != "yes") {
            cfg.erode = -1;
            console.println("[stabilize] ERODE skipped.");
        }
    }

    console.println("[stabilize] Mode  : " + cfg.mode);
    console.println("[stabilize] Model : " + modelPath);
    console.println("[stabilize] Output: " + outputPath);
    if (cfg.level > 0)
        console.println("[stabilize] Level : " + std::to_string(cfg.level));

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

    if (cfg.mode != "explicit") {
        console.error("Unknown stabilize mode: " + cfg.mode + " (only 'explicit' supported)");
        return 1;
    }
    auto msgs = stab_applyExplicit(lines, cfg);
    for (const auto& m : msgs) console.println(m);

    {
        std::ofstream fout(outputPath);
        if (!fout.is_open()) { console.error("Cannot write: " + outputPath); return 1; }
        for (const auto& l : lines) fout << l << "\n";
    }

    console.println("[stabilize] Done -> " + outputPath);
    return 0;
}
