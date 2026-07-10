// C-clip(스프링 접점) 생성 op 구현 — 박스 파트 치환·Castigliano 캘리브레이션·모멘트일치 눌림·INITIAL_STRESS_SHELL 출력.
#include "cclip.h"
#include "cli/ConsoleOutput.h"
#include "parser/KFileReader.h"
#include "core/Mesh.h"
#include "battery/BatteryWriter.h"
#include "kw_util.h"

#include <algorithm>
#include <cctype>
#include <cmath>
#include <cstdio>
#include <fstream>
#include <iomanip>
#include <limits>
#include <map>
#include <set>
#include <sstream>
#include <string>
#include <vector>

// Knowledge graph (lat.md):
//   @lat: [[modules/commands]]
//   @lat: [[commands/cclip]]

using KooRemapper::ConsoleOutput;
using KooRemapper::KFileReader;
using KooRemapper::Mesh;
using KooRemapper::MaterialData;

namespace {

// ---------------------------------------------------------------------------
// Config structs
// ---------------------------------------------------------------------------

struct CcProfileCfg {
    double flatBottom = 0.0;   // foot flat length (0 = auto 0.6*L)
    double flatTop    = 0.0;   // contact arm length (0 = auto 0.4*L)
    double radius     = 0.0;   // bend radius (0 = auto min(Harc/2, L-Lb))
    double tipRise    = 0.0;   // contact tip height above arc shoulder (0 = auto = working deflection)
};

struct CcMaterial {
    double E = 131000.0, nu = 0.30, rho = 8.36e-9, sigy = 900.0;  // BeCu defaults
    bool set = false;
};

struct CcCalib {
    bool hasPoint = false;
    double pointDefl = 0.0, pointForce = 0.0;
    std::vector<std::pair<double,double>> curve;   // (deflection, force), ascending
    double operatingDefl = 0.0; bool hasOperatingDefl = false;
    double tolerance = 0.05, tMin = 0.03, tMax = 0.30;
    std::string calibrate = "thickness";           // thickness | modulus
    bool set = false;
};

struct CcRule {
    int pid = 0;
    std::string matchPart;
    double freeHeight = 0.0, overtravel = 0.0;
    double width = 0.0, thickness = 0.0;
    CcProfileCfg profile;
    int nArc = 8, nFlat = 2, nWidth = 3, elform = 16;
    bool matchMass = false;
    std::string axis;          // per-clip override of global axis (press-from side, e.g. "-z")
    std::string open;          // per-clip override of C opening ("+"|"-" along the length axis)
    CcMaterial material;       // per-clip override (material.set)
    CcCalib calib;             // per-clip override (calib.set)
};

struct CcConfig {
    std::string modelFile, outputFile;
    std::string mode = "analytic";        // analytic | deck
    std::string attach = "none";          // none | cnrb
    std::string stressOutput = "embed";   // embed | include
    std::string axis = "auto";            // auto|[+|-]x|y|z — press-from side (default +)
    std::string open = "+";               // C opening/bulge direction along the length axis
    double attachTol = 0.1;
    bool report = true;
    CcMaterial material;
    CcCalib calib;
    std::vector<CcRule> clips;
    std::string configDir;
};

// ---------------------------------------------------------------------------
// Small helpers
// ---------------------------------------------------------------------------

std::string cc_trim(const std::string& s) {
    size_t a = 0, b = s.size();
    while (a < b && std::isspace((unsigned char)s[a])) ++a;
    while (b > a && std::isspace((unsigned char)s[b-1])) --b;
    return s.substr(a, b - a);
}

int cc_indent(const std::string& s) {
    int n = 0; while (n < (int)s.size() && s[n] == ' ') ++n; return n;
}

std::string cc_stripQuotes(const std::string& s) {
    if (s.size() >= 2 && ((s.front()=='"' && s.back()=='"') || (s.front()=='\'' && s.back()=='\'')))
        return s.substr(1, s.size()-2);
    return s;
}

// drop an inline "  # comment" tail (only when '#' follows whitespace, so quoted
// or embedded '#' survives via the quote path)
std::string cc_stripInlineComment(const std::string& s) {
    for (size_t i = 1; i < s.size(); ++i)
        if (s[i] == '#' && std::isspace((unsigned char)s[i-1]))
            return cc_trim(s.substr(0, i));
    return s;
}

bool cc_toBool(const std::string& v) { return v=="true" || v=="yes" || v=="1"; }

double cc_toD(const std::string& v, double dflt = 0.0) {
    try { return std::stod(v); } catch (...) { return dflt; }
}
int cc_toI(const std::string& v, int dflt = 0) {
    try { return std::stoi(v); } catch (...) { return dflt; }
}

// glob match (*, ?) — copied from ModelAssembler::wildcardMatch (header-private there)
bool cc_wildcardMatch(const std::string& pattern, const std::string& text) {
    size_t p = 0, t = 0, star = std::string::npos, mark = 0;
    while (t < text.size()) {
        if (p < pattern.size() && (pattern[p] == '?' || pattern[p] == text[t])) { ++p; ++t; }
        else if (p < pattern.size() && pattern[p] == '*') { star = p++; mark = t; }
        else if (star != std::string::npos) { p = star + 1; t = ++mark; }
        else return false;
    }
    while (p < pattern.size() && pattern[p] == '*') ++p;
    return p == pattern.size();
}

// inline map "{k: v, k2: v2}" → pairs
std::vector<std::pair<std::string,std::string>> cc_parseInlineMap(const std::string& v) {
    std::vector<std::pair<std::string,std::string>> out;
    std::string s = cc_trim(v);
    if (s.size() < 2 || s.front() != '{' || s.back() != '}') return out;
    s = s.substr(1, s.size() - 2);
    std::stringstream ss(s);
    std::string item;
    while (std::getline(ss, item, ',')) {
        size_t cp = item.find(':');
        if (cp == std::string::npos) continue;
        out.push_back({cc_trim(item.substr(0,cp)), cc_stripQuotes(cc_trim(item.substr(cp+1)))});
    }
    return out;
}

// inline curve "[[d,f],[d,f],...]" → pairs
std::vector<std::pair<double,double>> cc_parseInlineCurve(const std::string& v) {
    std::vector<std::pair<double,double>> out;
    std::vector<double> nums;
    std::string cur;
    for (char c : v) {
        if ((c >= '0' && c <= '9') || c=='.' || c=='-' || c=='+' || c=='e' || c=='E') cur += c;
        else { if (!cur.empty()) { nums.push_back(cc_toD(cur)); cur.clear(); } }
    }
    if (!cur.empty()) nums.push_back(cc_toD(cur));
    for (size_t i = 0; i + 1 < nums.size(); i += 2) out.push_back({nums[i], nums[i+1]});
    return out;
}

void cc_applyMaterialKey(CcMaterial& m, const std::string& k, const std::string& v) {
    if      (k == "E")    m.E = cc_toD(v, m.E);
    else if (k == "nu")   m.nu = cc_toD(v, m.nu);
    else if (k == "rho")  m.rho = cc_toD(v, m.rho);
    else if (k == "sigy") m.sigy = cc_toD(v, m.sigy);
    m.set = true;
}

void cc_applyCalibKey(CcCalib& c, const std::string& k, const std::string& v) {
    if (k == "point") {
        for (const auto& kv : cc_parseInlineMap(v)) {
            if (kv.first == "deflection") c.pointDefl = cc_toD(kv.second);
            else if (kv.first == "force") c.pointForce = cc_toD(kv.second);
        }
        c.hasPoint = true;
    }
    else if (k == "curve")                 c.curve = cc_parseInlineCurve(v);
    else if (k == "operating_deflection") { c.operatingDefl = cc_toD(v); c.hasOperatingDefl = true; }
    else if (k == "tolerance")             c.tolerance = cc_toD(v, c.tolerance);
    else if (k == "calibrate")             c.calibrate = v;
    else if (k == "t_min")                 c.tMin = cc_toD(v, c.tMin);
    else if (k == "t_max")                 c.tMax = cc_toD(v, c.tMax);
    c.set = true;
}

// ---------------------------------------------------------------------------
// YAML parser (matdb-style minimal parser: rules list + nested sub-blocks)
// ---------------------------------------------------------------------------

bool parseCclipYaml(const std::string& yamlFile, CcConfig& cfg, ConsoleOutput& console) {
    std::ifstream f(yamlFile);
    if (!f.is_open()) { console.error("Cannot open: " + yamlFile); return false; }

    size_t lastSlash = yamlFile.find_last_of("/\\");
    if (lastSlash != std::string::npos) cfg.configDir = yamlFile.substr(0, lastSlash);

    // sub-block states: 0=none 1=material 2=calibration (top level)
    int topBlock = 0; int topBlockIndent = 0;
    bool inClips = false; int clipsIndent = 0;
    bool inClipItem = false; int clipItemIndent = 0;
    // clip sub-block: 0=none 1=profile 2=material 3=calibration
    int clipBlock = 0; int clipBlockIndent = 0;
    // calibration sub-sub-block (block-form point:/curve: as emitted by the platform
    // YAML dumper): 0=none 1=point 2=curve — always resolved before any exit logic.
    CcCalib* curCalib = nullptr; int calibSub = 0; int calibSubIndent = 0;

    std::string ln;
    while (std::getline(f, ln)) {
        if (!ln.empty() && ln.back()=='\r') ln.pop_back();
        int indent = cc_indent(ln);
        std::string tr = cc_trim(ln);
        if (tr.empty() || tr[0]=='#') continue;

        size_t cp0 = tr.find(':');
        std::string key0 = (cp0 == std::string::npos) ? "" : cc_trim(tr.substr(0, cp0));
        std::string val0 = (cp0 == std::string::npos) ? "" : cc_stripQuotes(cc_stripInlineComment(cc_trim(tr.substr(cp0+1))));

        if (curCalib && calibSub != 0) {
            // YAML sequence items may sit at the SAME indent as their key
            if (calibSub == 2 && tr.substr(0,2) == "- " && indent >= calibSubIndent) {
                auto pr = cc_parseInlineCurve(tr.substr(2));   // "- [d, f]"
                if (!pr.empty()) curCalib->curve.push_back(pr[0]);
                continue;
            }
            if (calibSub == 1 && indent > calibSubIndent) {
                if      (key0 == "deflection") { curCalib->pointDefl = cc_toD(val0); continue; }
                else if (key0 == "force")      { curCalib->pointForce = cc_toD(val0); continue; }
            }
            calibSub = 0;
        }

        if (inClips && indent <= clipsIndent && tr.substr(0,2) != "- ") {
            inClips = false; inClipItem = false; clipBlock = 0;
        }
        if (topBlock != 0 && indent <= topBlockIndent) topBlock = 0;
        if (clipBlock != 0 && (indent <= clipBlockIndent || tr.substr(0,2) == "- ")) clipBlock = 0;

        size_t cp = tr.find(':');
        if (cp == std::string::npos && tr.substr(0,2) != "- ") continue;
        std::string key = key0;
        std::string val = val0;

        if (!inClips) {
            if (topBlock == 1) { cc_applyMaterialKey(cfg.material, key, val); continue; }
            if (topBlock == 2) {
                if ((key == "point" || key == "curve") && val.empty()) {
                    curCalib = &cfg.calib; calibSub = (key == "point") ? 1 : 2; calibSubIndent = indent;
                    if (key == "point") cfg.calib.hasPoint = true;
                    cfg.calib.set = true;
                } else cc_applyCalibKey(cfg.calib, key, val);
                continue;
            }

            if      (key == "model")         cfg.modelFile = val;
            else if (key == "output")        cfg.outputFile = val;
            else if (key == "mode")          cfg.mode = val;
            else if (key == "attach")        cfg.attach = val;
            else if (key == "stress_output") cfg.stressOutput = val;
            else if (key == "axis")          cfg.axis = val;
            else if (key == "open")          cfg.open = val;
            else if (key == "attach_tol")    cfg.attachTol = cc_toD(val, cfg.attachTol);
            else if (key == "report")        cfg.report = cc_toBool(val);
            else if (key == "material") {
                if (!val.empty()) for (const auto& kv : cc_parseInlineMap(val))
                    cc_applyMaterialKey(cfg.material, kv.first, kv.second);
                else { topBlock = 1; topBlockIndent = indent; }
            }
            else if (key == "calibration") {
                if (!val.empty() && val[0]=='{') for (const auto& kv : cc_parseInlineMap(val))
                    cc_applyCalibKey(cfg.calib, kv.first, kv.second);
                else { topBlock = 2; topBlockIndent = indent; }
            }
            else if (key == "clips") { inClips = true; clipsIndent = indent; }
            continue;
        }

        // inside clips list
        if (tr.substr(0,2) == "- " && indent > clipsIndent) {
            cfg.clips.push_back(CcRule());
            inClipItem = true; clipItemIndent = indent; clipBlock = 0;
            curCalib = nullptr; calibSub = 0;   // rule vector may reallocate
            std::string rest = cc_trim(tr.substr(2));
            size_t rcp = rest.find(':');
            if (rcp != std::string::npos) {
                key = cc_trim(rest.substr(0, rcp));
                val = cc_stripQuotes(cc_stripInlineComment(cc_trim(rest.substr(rcp+1))));
            } else continue;
        } else if (!(inClipItem && indent > clipItemIndent)) {
            continue;
        }

        CcRule& r = cfg.clips.back();
        if (clipBlock == 1) {   // profile
            if      (key == "flat_bottom") r.profile.flatBottom = cc_toD(val);
            else if (key == "flat_top")    r.profile.flatTop = cc_toD(val);
            else if (key == "radius")      r.profile.radius = cc_toD(val);
            else if (key == "tip_rise")    r.profile.tipRise = cc_toD(val);
            continue;
        }
        if (clipBlock == 2) { cc_applyMaterialKey(r.material, key, val); continue; }
        if (clipBlock == 3) {
            if ((key == "point" || key == "curve") && val.empty()) {
                curCalib = &r.calib; calibSub = (key == "point") ? 1 : 2; calibSubIndent = indent;
                if (key == "point") r.calib.hasPoint = true;
                r.calib.set = true;
            } else cc_applyCalibKey(r.calib, key, val);
            continue;
        }

        if      (key == "pid")         r.pid = cc_toI(val);
        else if (key == "match_part")  r.matchPart = val;
        else if (key == "free_height") r.freeHeight = cc_toD(val);
        else if (key == "overtravel")  r.overtravel = cc_toD(val);
        else if (key == "width")       r.width = cc_toD(val);
        else if (key == "thickness")   r.thickness = cc_toD(val);
        else if (key == "n_arc")       r.nArc = cc_toI(val, r.nArc);
        else if (key == "n_flat")      r.nFlat = cc_toI(val, r.nFlat);
        else if (key == "n_width")     r.nWidth = cc_toI(val, r.nWidth);
        else if (key == "elform")      r.elform = cc_toI(val, r.elform);
        else if (key == "match_mass")  r.matchMass = cc_toBool(val);
        else if (key == "axis")        r.axis = val;
        else if (key == "open")        r.open = val;
        else if (key == "profile") {
            if (!val.empty() && val[0]=='{') for (const auto& kv : cc_parseInlineMap(val)) {
                if      (kv.first == "flat_bottom") r.profile.flatBottom = cc_toD(kv.second);
                else if (kv.first == "flat_top")    r.profile.flatTop = cc_toD(kv.second);
                else if (kv.first == "radius")      r.profile.radius = cc_toD(kv.second);
                else if (kv.first == "tip_rise")    r.profile.tipRise = cc_toD(kv.second);
            }
            else { clipBlock = 1; clipBlockIndent = indent; }
        }
        else if (key == "material") {
            if (!val.empty() && val[0]=='{') for (const auto& kv : cc_parseInlineMap(val))
                cc_applyMaterialKey(r.material, kv.first, kv.second);
            else { clipBlock = 2; clipBlockIndent = indent; }
        }
        else if (key == "calibration") {
            if (!val.empty() && val[0]=='{') for (const auto& kv : cc_parseInlineMap(val))
                cc_applyCalibKey(r.calib, kv.first, kv.second);
            else { clipBlock = 3; clipBlockIndent = indent; }
        }
    }
    return true;
}

// ---------------------------------------------------------------------------
// Box frame (axis-aligned local frame from target part bbox)
// ---------------------------------------------------------------------------

struct CcFrame {
    int iu = 0, iv = 1, iw = 2;         // global axis indices for length/width/compression
    double su = 1, sv = 1, sw = 1;      // axis direction signs (right-handed u,v,w)
    double lo[3] = {0,0,0}, hi[3] = {0,0,0};   // bbox
    double L = 0, W = 0, hInst = 0;     // extents along u, v, w
    bool valid = false;
};

// axisSel: auto | [+|-]x|y|z — the SIDE the mating part presses from (foot on the
// opposite face). openSel: "+"|"-" — C bulge direction along the length axis.
CcFrame deriveBoxFrame(const Mesh& mesh, int pid, const std::string& axisSel,
                       const std::string& openSel, ConsoleOutput& console) {
    CcFrame fr;
    std::set<int> nids;
    for (const auto& [eid, elem] : mesh.getElements()) {
        if (elem.partId != pid) continue;
        for (int i = 0; i < 8; ++i) nids.insert(elem.nodeIds[i]);
    }
    if (nids.empty()) { console.error("[cclip] part " + std::to_string(pid) + " has no solid elements"); return fr; }

    double lo[3] = { 1e300, 1e300, 1e300 }, hi[3] = { -1e300, -1e300, -1e300 };
    for (int nid : nids) {
        const auto* node = mesh.getNode(nid);
        if (!node) continue;
        double p[3] = { node->position.x, node->position.y, node->position.z };
        for (int a = 0; a < 3; ++a) { lo[a] = std::min(lo[a], p[a]); hi[a] = std::max(hi[a], p[a]); }
    }
    double ext[3] = { hi[0]-lo[0], hi[1]-lo[1], hi[2]-lo[2] };

    std::string ax = axisSel;
    double swSign = 1.0;
    if (ax.size() == 2 && (ax[0] == '+' || ax[0] == '-')) {
        if (ax[0] == '-') swSign = -1.0;
        ax = ax.substr(1);
    }
    int iw;
    if      (ax == "x") iw = 0;
    else if (ax == "y") iw = 1;
    else if (ax == "z") iw = 2;
    else if (ax == "auto" || ax.empty()) {
        iw = 0; if (ext[1] < ext[iw]) iw = 1; if (ext[2] < ext[iw]) iw = 2;      // auto: shortest
    } else {
        console.error("[cclip] invalid axis '" + axisSel + "' (expected auto or [+|-]x|y|z)");
        return fr;   // fr.valid stays false
    }

    int a1 = (iw+1)%3, a2 = (iw+2)%3;
    int iu = (ext[a1] >= ext[a2]) ? a1 : a2;    // length = longer of the rest
    int iv = (iu == a1) ? a2 : a1;

    fr.iu = iu; fr.iv = iv; fr.iw = iw;
    fr.sw = swSign;                              // + : pressed from +axis (foot at min face)
    fr.su = (openSel == "-") ? -1.0 : 1.0;       // C bulge toward ±length axis
    // right-handed (u,v,w): e_v = e_w × e_u  → sign via Levi-Civita of (iw,iu,iv)
    auto lc = [](int a, int b, int c) {
        if (a==b || b==c || a==c) return 0;
        return ((b-a+3)%3 == 1) ? 1 : -1;
    };
    fr.sv = fr.sw * fr.su * (double)lc(fr.iw, fr.iu, fr.iv);   // signed e_w x e_u
    for (int a = 0; a < 3; ++a) { fr.lo[a] = lo[a]; fr.hi[a] = hi[a]; }
    fr.L = ext[iu]; fr.W = ext[iv]; fr.hInst = ext[iw];
    fr.valid = (fr.L > 0 && fr.W > 0 && fr.hInst > 0);
    return fr;
}

// local (x=u, y=v, z=w) → global xyz.  Local origin: min-corner in each signed direction.
void cc_toGlobal(const CcFrame& fr, double x, double y, double z, double out[3]) {
    out[fr.iu] = (fr.su > 0 ? fr.lo[fr.iu] : fr.hi[fr.iu]) + fr.su * x;
    out[fr.iv] = (fr.sv > 0 ? fr.lo[fr.iv] : fr.hi[fr.iv]) + fr.sv * y;
    out[fr.iw] = (fr.sw > 0 ? fr.lo[fr.iw] : fr.hi[fr.iw]) + fr.sw * z;
}

// ---------------------------------------------------------------------------
// C profile + Castigliano calibration + moment-matched pressed shape
// ---------------------------------------------------------------------------

struct CcPt { double x=0, z=0, s=0, theta=0; };

struct CcProfile {
    std::vector<CcPt> pts;   // ordered foot(0) → arc → inclined contact arm → tip (free end)
    int iFootEnd = 0;        // index where foot flat ends (flexible region starts)
    int iLoad = 0;           // load-point index (contact tip = free end = profile apex)
    double Lb = 0, Lt = 0, r = 0, H = 0, rise = 0;
};

// Build free-state profile polyline. Segments: foot flat, (arc | arc+leg+arc) up to the
// shoulder at H-rise, then an inclined contact arm rising to the tip apex at H.
// rise >= working deflection keeps the pressed shoulder below the mating plane
// (real clips carry the contact crown above the shoulder by at least the travel).
bool buildCProfile(double L, double H, double rise, const CcProfileCfg& pc,
                   int nArc, int nFlat, CcProfile& out, std::string& err) {
    double Lb = (pc.flatBottom > 0) ? pc.flatBottom : 0.6 * L;
    double Lt = (pc.flatTop    > 0) ? pc.flatTop    : 0.4 * L;
    if (rise >= H)       { err = "tip_rise >= free height"; return false; }
    double Harc = H - rise;                      // arc shoulder height
    double rMax = std::min(Harc / 2.0, L - Lb);
    double r  = (pc.radius > 0) ? pc.radius : rMax;
    if (r > rMax + 1e-9) {
        err = "radius " + std::to_string(r) + " exceeds fit limit " + std::to_string(rMax);
        return false;
    }
    if (Lb + 1e-9 >= L)  { err = "flat_bottom >= part length"; return false; }
    if (Lt > Lb + 1e-9)  { err = "flat_top > flat_bottom (contact arm would overhang the foot)"; return false; }
    if (r <= 0)          { err = "bend radius <= 0"; return false; }

    out.Lb = Lb; out.Lt = Lt; out.r = r; out.H = H; out.rise = rise;
    auto& P = out.pts;
    P.clear();
    const double PI = 3.14159265358979323846;

    auto addPt = [&](double x, double z, double theta) {
        CcPt p; p.x = x; p.z = z; p.theta = theta;
        if (!P.empty()) {
            double dx = x - P.back().x, dz = z - P.back().z;
            p.s = P.back().s + std::sqrt(dx*dx + dz*dz);
        }
        P.push_back(p);
    };

    // foot flat: (0,0) → (Lb,0), tangent +x (theta=0)
    for (int i = 0; i <= nFlat; ++i) addPt(Lb * i / nFlat, 0.0, 0.0);
    out.iFootEnd = (int)P.size() - 1;

    double legLen = Harc - 2.0 * r;
    if (legLen < 1e-9) {
        // semicircle: center (Lb, Harc/2), phi -90° → +90°, theta = phi + 90°
        for (int i = 1; i <= nArc; ++i) {
            double phi = -PI/2 + PI * i / nArc;
            addPt(Lb + r * std::cos(phi), Harc/2 + r * std::sin(phi), phi + PI/2);
        }
    } else {
        int nq = std::max(2, nArc / 2);
        int nl = std::max(1, nFlat);
        // lower quarter: center (Lb, r), phi -90° → 0°
        for (int i = 1; i <= nq; ++i) {
            double phi = -PI/2 + (PI/2) * i / nq;
            addPt(Lb + r * std::cos(phi), r + r * std::sin(phi), phi + PI/2);
        }
        // vertical leg: (Lb+r, r) → (Lb+r, Harc-r), theta = +90°
        for (int i = 1; i <= nl; ++i) addPt(Lb + r, r + legLen * i / nl, PI/2);
        // upper quarter: center (Lb, Harc-r), phi 0° → +90°
        for (int i = 1; i <= nq; ++i) {
            double phi = (PI/2) * i / nq;
            addPt(Lb + r * std::cos(phi), (Harc - r) + r * std::sin(phi), phi + PI/2);
        }
    }

    // inclined contact arm: (Lb, Harc) → tip (Lb-Lt, H); tangent points -x with +z slope
    double thArm = std::atan2(rise, -Lt);   // in (90°, 180°]
    for (int i = 1; i <= nFlat; ++i)
        addPt(Lb - Lt * i / nFlat, Harc + rise * i / nFlat, thArm);
    out.iLoad = (int)P.size() - 1;          // load at the tip apex
    return true;
}

// Unit-load bending moment m(s) = xL - x(s) on the flexible path [iFootEnd .. iLoad], else 0.
double cc_unitMoment(const CcProfile& pr, int i) {
    if (i < pr.iFootEnd || i > pr.iLoad) return 0.0;
    return pr.pts[pr.iLoad].x - pr.pts[i].x;
}

// J = ∫ m(s)^2 ds  (trapezoid over flexible path)
double cc_momentIntegralJ(const CcProfile& pr) {
    double J = 0.0;
    for (int i = pr.iFootEnd; i < pr.iLoad; ++i) {
        double m0 = cc_unitMoment(pr, i), m1 = cc_unitMoment(pr, i+1);
        double ds = pr.pts[i+1].s - pr.pts[i].s;
        J += 0.5 * (m0*m0 + m1*m1) * ds;
    }
    return J;
}

// Pressed shape: theta_def(s) = theta_free(s) + c * Kcum(s), integrate positions from foot.
// Kcum = cumulative unit-load curvature ∫ m/(EI) ds.  Returns profile max height (fit criterion).
std::vector<CcPt> cc_deformProfile(const CcProfile& pr, double c, double EI, double* maxZ) {
    const auto& P = pr.pts;
    int n = (int)P.size();
    std::vector<double> Kcum(n, 0.0);
    for (int i = 1; i < n; ++i) {
        double km0 = cc_unitMoment(pr, i-1) / EI, km1 = cc_unitMoment(pr, i) / EI;
        double ds = P[i].s - P[i-1].s;
        Kcum[i] = Kcum[i-1] + 0.5 * (km0 + km1) * ds;
    }
    // chord-rotation reconstruction: rotate each FREE segment chord by the cumulative
    // curvature change at its midpoint — reproduces the free polyline exactly at c=0
    // (theta-integration would drift at profile kinks).
    std::vector<CcPt> D(n);
    D[0] = P[0];
    D[0].theta = P[0].theta + c * Kcum[0];
    for (int i = 1; i < n; ++i) {
        double dx = P[i].x - P[i-1].x, dz = P[i].z - P[i-1].z;
        double len = std::sqrt(dx*dx + dz*dz);
        double alpha = std::atan2(dz, dx) + c * 0.5 * (Kcum[i-1] + Kcum[i]);
        D[i].x = D[i-1].x + len * std::cos(alpha);
        D[i].z = D[i-1].z + len * std::sin(alpha);
        D[i].s = P[i].s;
        D[i].theta = P[i].theta + c * Kcum[i];
    }
    if (maxZ) {
        double mz = -1e300;
        for (const auto& p : D) mz = std::max(mz, p.z);
        *maxZ = mz;
    }
    return D;
}

// Solve scale c so the pressed profile's max height == hTarget.
// maxZ(c) is piecewise smooth (max over points) — expand along the pressing
// direction, then bisect (robust against the max() kink).
double cc_solvePressScale(const CcProfile& pr, double EI, double Fwork, double hTarget,
                          ConsoleOutput& console) {
    double step = std::max(1e-6, std::fabs(Fwork));
    double zPlus = 0, zMinus = 0;
    cc_deformProfile(pr, +step, EI, &zPlus);
    cc_deformProfile(pr, -step, EI, &zMinus);
    double dir = (zPlus < zMinus) ? +1.0 : -1.0;

    double z0 = 0; cc_deformProfile(pr, 0.0, EI, &z0);
    if (z0 <= hTarget) return 0.0;   // already fits (shouldn't happen: H_free > h_inst)

    double lo = 0.0, hi = dir * step, zhi = 0;
    cc_deformProfile(pr, hi, EI, &zhi);
    int guard = 0;
    while (zhi > hTarget && ++guard <= 24) { hi *= 2.0; cc_deformProfile(pr, hi, EI, &zhi); }
    if (zhi > hTarget) {
        console.warning("[cclip] pressed-shape solve could not reach target height (residual " +
                        std::to_string(zhi - hTarget) + " mm) — check tip_rise vs deflection");
        return hi;
    }
    for (int it = 0; it < 80; ++it) {
        double mid = 0.5 * (lo + hi), zm = 0;
        cc_deformProfile(pr, mid, EI, &zm);
        if (zm > hTarget) lo = mid; else hi = mid;
        if (std::fabs(zm - hTarget) < 1e-10 * std::max(1.0, std::fabs(hTarget))) { hi = mid; break; }
    }
    double zf = 0; cc_deformProfile(pr, hi, EI, &zf);
    if (std::fabs(zf - hTarget) > 1e-4 * std::max(1.0, pr.H))
        console.warning("[cclip] pressed-shape solve residual " + std::to_string(zf - hTarget) + " mm");
    return hi;
}

// ---------------------------------------------------------------------------
// Raw K-file line splicing (matswap patterns, localized as cc_*)
// ---------------------------------------------------------------------------

int cc_scanMaxId(const std::vector<std::string>& lines, const std::string& prefix) {
    int maxId = 0;
    bool active = false, hasTitle = false, titleDone = false;
    for (const auto& ln : lines) {
        std::string tr = kw_trim(ln);
        if (tr.empty()) continue;
        if (tr[0]=='*') {
            std::string up = kw_upper(tr);
            if (up.rfind(prefix,0)==0) {
                active = true;
                hasTitle = (up.find("_TITLE") != std::string::npos);
                titleDone = !hasTitle;
            } else active = false;
            continue;
        }
        if (!active || tr[0]=='$') continue;
        if (!titleDone) { titleDone = true; continue; }
        auto toks = kw_tok10(ln);
        if (!toks.empty()) { try { int id = std::stoi(toks[0]); if (id > maxId) maxId = id; } catch(...){} }
        active = false;
    }
    return maxId;
}

struct CcPartLine { int lineIdx = -1; int secid = 0, mid = 0, hgid = 0; };

CcPartLine cc_findPartLine(const std::vector<std::string>& lines, int targetPid) {
    CcPartLine info;
    bool inPart = false, titleDone = false;
    for (int i = 0; i < (int)lines.size(); ++i) {
        std::string tr = kw_trim(lines[i]);
        if (tr.empty()) continue;
        if (tr[0]=='*') {
            std::string up = kw_upper(tr);
            inPart = (up=="*PART" || up=="*PART_TITLE"); titleDone = false; continue;
        }
        if (!inPart || tr[0]=='$') continue;
        if (!titleDone) { titleDone = true; continue; }
        auto toks = kw_tok10(lines[i]);
        if (toks.size() >= 3) {
            try {
                if (std::stoi(toks[0]) == targetPid) {
                    info.lineIdx = i;
                    info.secid = std::stoi(toks[1]);
                    info.mid = std::stoi(toks[2]);
                    if (toks.size() >= 5 && !toks[4].empty()) info.hgid = std::stoi(toks[4]);
                    return info;
                }
            } catch(...) {}
        }
        titleDone = false;
    }
    return info;
}

bool cc_idShared(const std::vector<std::string>& lines, int fieldIdx, int targetId, int excludePid) {
    bool inPart = false, titleDone = false;
    for (const auto& ln : lines) {
        std::string tr = kw_trim(ln);
        if (tr.empty()) continue;
        if (tr[0]=='*') {
            std::string up = kw_upper(tr);
            inPart = (up=="*PART" || up=="*PART_TITLE"); titleDone = false; continue;
        }
        if (!inPart || tr[0]=='$') continue;
        if (!titleDone) { titleDone = true; continue; }
        auto toks = kw_tok10(ln);
        if ((int)toks.size() > fieldIdx) {
            try {
                int pid = std::stoi(toks[0]);
                if (pid != excludePid && std::stoi(toks[fieldIdx]) == targetId) return true;
            } catch(...) {}
        }
        titleDone = false;
    }
    return false;
}

std::vector<std::string> cc_removeBlockById(const std::vector<std::string>& lines,
                                            const std::string& prefix, int targetId) {
    std::vector<bool> rm(lines.size(), false);
    for (int i = 0; i < (int)lines.size(); ) {
        std::string tr = kw_trim(lines[i]);
        if (tr.empty() || tr[0] != '*') { ++i; continue; }
        std::string up = kw_upper(tr);
        if (up.rfind(prefix,0) != 0) { ++i; continue; }
        bool hasTitle = (up.find("_TITLE") != std::string::npos);
        int titlesLeft = hasTitle ? 1 : 0, id = -1;
        for (int j = i+1; j < (int)lines.size(); ++j) {
            std::string jt = kw_trim(lines[j]);
            if (jt.empty() || jt[0]=='$') continue;
            if (jt[0]=='*') break;
            if (titlesLeft-- > 0) continue;
            auto toks = kw_tok10(lines[j]);
            if (!toks.empty()) { try { id = std::stoi(toks[0]); } catch(...){} }
            break;
        }
        if (id != targetId) { ++i; continue; }
        int end = i + 1;
        while (end < (int)lines.size()) {
            std::string et = kw_trim(lines[end]);
            if (!et.empty() && et[0]=='*') break;
            ++end;
        }
        for (int k = i; k < end; ++k) rm[k] = true;
        i = end;
    }
    std::vector<std::string> out;
    for (int i = 0; i < (int)lines.size(); ++i) if (!rm[i]) out.push_back(lines[i]);
    return out;
}

// Remove *ELEMENT_SOLID data lines whose PID (2nd 8-char field) is in pids.
// Drops the keyword line too if its block becomes empty. Returns removed line count.
int cc_removeSolidElements(std::vector<std::string>& lines, const std::set<int>& pids) {
    std::vector<bool> rm(lines.size(), false);
    int removed = 0;
    for (int i = 0; i < (int)lines.size(); ) {
        std::string tr = kw_trim(lines[i]);
        if (tr.empty() || tr[0] != '*') { ++i; continue; }
        if (kw_upper(tr).rfind("*ELEMENT_SOLID",0) != 0) { ++i; continue; }
        int kwLine = i, end = i + 1, kept = 0;
        while (end < (int)lines.size()) {
            std::string et = kw_trim(lines[end]);
            if (!et.empty() && et[0]=='*') break;
            if (!et.empty() && et[0] != '$') {
                int pid = -1;
                if ((int)lines[end].size() >= 16) pid = cc_toI(cc_trim(lines[end].substr(8,8)), -1);
                if (pid < 0) {   // whitespace-split fallback
                    std::istringstream iss(lines[end]);
                    long a=-1, b=-1; iss >> a >> b; pid = (int)b;
                }
                if (pids.count(pid)) { rm[end] = true; ++removed; }
                else ++kept;
            }
            ++end;
        }
        if (kept == 0 && removed > 0) {
            rm[kwLine] = true;
            for (int k = kwLine+1; k < end; ++k) rm[k] = true;   // drop leftover comments too
        }
        i = end;
    }
    std::vector<std::string> out;
    out.reserve(lines.size());
    for (int i = 0; i < (int)lines.size(); ++i) if (!rm[i]) out.push_back(lines[i]);
    lines = std::move(out);
    return removed;
}

std::string cc_updatePartLine(const std::string& ln, int newSecid, int newMid) {
    std::string r = ln;
    r = kw_setField(r, 10, 10, std::to_string(newSecid));
    r = kw_setField(r, 20, 10, std::to_string(newMid));
    return r;
}

// ---------------------------------------------------------------------------
// Card writers (formats copied from ModelAssembler / BatteryMaterials / BatteryControl)
// ---------------------------------------------------------------------------

struct CcStressRow { double top[6]; double bot[6]; };   // xx yy zz xy yz zx

void cc_writeInitialStressShell(std::ostream& out,
                                const std::vector<std::pair<int,const CcStressRow*>>& rows) {
    out << "*INITIAL_STRESS_SHELL\n";
    out << std::scientific << std::setprecision(3);
    bool first = true;
    for (const auto& [eid, sr] : rows) {
        if (first) out << "$#    eid  nplane  nthick   nhisv  ntensr   large  nthint  nthhsv\n";
        out << std::setw(10) << eid
            << std::setw(8) << 1 << std::setw(8) << 2
            << std::setw(8) << 0 << std::setw(8) << 0
            << std::setw(8) << 0 << std::setw(8) << 0 << std::setw(8) << 0 << "\n";
        if (first) { out << "$#     T     sigxx     sigyy     sigzz     sigxy     sigyz     sigzx       eps\n"; first = false; }
        out << std::setw(10) << -1.0;
        for (int k = 0; k < 6; ++k) out << std::setw(10) << sr->bot[k];
        out << std::setw(10) << 0.0 << "\n";
        out << std::setw(10) << 1.0;
        for (int k = 0; k < 6; ++k) out << std::setw(10) << sr->top[k];
        out << std::setw(10) << 0.0 << "\n";
    }
    out.unsetf(std::ios::scientific);
}

void cc_writeMatElastic(std::ostream& out, int mid, double rho, double E, double nu,
                        const std::string& name) {
    char buf[128];
    out << "*MAT_ELASTIC_TITLE\n" << name << "\n"
        << "$#   mid        ro         e        pr\n";
    snprintf(buf, sizeof(buf), "%10d%10s%10.1f%10.4f\n", mid, bat::sciField(rho).c_str(), E, nu);
    out << buf;
}

void cc_writeMatRigid(std::ostream& out, int mid, double rho, double E, double nu,
                      int cmo, int con1, int con2, const std::string& name) {
    char buf[160];
    out << "*MAT_RIGID_TITLE\n" << name << "\n"
        << "$#   mid        ro         e        pr\n";
    snprintf(buf, sizeof(buf), "%10d%10s%10.1f%10.4f\n", mid, bat::sciField(rho).c_str(), E, nu);
    out << buf;
    snprintf(buf, sizeof(buf), "%10.1f%10d%10d\n", (double)cmo, con1, con2);
    out << buf;
    out << "       0.0       0.0       0.0\n";
}

void cc_writeSpcSet(std::ostream& out, int nsid) {
    out << "*BOUNDARY_SPC_SET\n"
        << "$#    nsid     cid      dofx    dofy    dofz   dofrx   dofry   dofrz\n";
    char buf[128];
    snprintf(buf, sizeof(buf), "%10d%10d%10d%10d%10d%10d%10d%10d\n", nsid, 0, 1, 1, 1, 1, 1, 1);
    out << buf;
}

void cc_writeBpmRigid(std::ostream& out, int pid, int dof, int lcid) {
    out << "*BOUNDARY_PRESCRIBED_MOTION_RIGID\n"
        << "$#     pid     dof     vad    lcid        sf     vid   death   birth\n";
    char buf[160];
    snprintf(buf, sizeof(buf), "%10d%10d%10d%10d%10.1f%10d%10s%10s\n",
             pid, dof, 2, lcid, 1.0, 0, "1.0E28", "0.0");
    out << buf;
}

void cc_writeContactNodesToSurface(std::ostream& out, int ssid, int msid) {
    out << "*CONTACT_AUTOMATIC_NODES_TO_SURFACE\n"
        << "$#    ssid    msid     sstyp   mstyp  sboxid  mboxid     spr     mpr\n";
    char buf[160];
    snprintf(buf, sizeof(buf), "%10d%10d%10d%10d%10d%10d%10d%10d\n", ssid, msid, 4, 3, 0, 0, 0, 0);
    out << buf;
    out << "$#      fs      fd        dc      vc     vdc  penchk      bt      dt\n";
    snprintf(buf, sizeof(buf), "%10.2f%10.2f%10.1f%10.1f%10.1f%10d%10.1f%10s\n",
             0.2, 0.2, 0.0, 0.0, 0.0, 0, 0.0, "1.0E20");
    out << buf;
    out << "       1.0       1.0       1.0       1.0\n";
}

// ---------------------------------------------------------------------------
// Per-clip build result
// ---------------------------------------------------------------------------

struct CcBuilt {
    int pid = 0;
    std::string partTitle;
    int newSecid = 0, newMid = 0;
    double t = 0, E = 0, kTarget = 0, kAchieved = 0, relErr = 0;
    double Fwork = 0, deltaWork = 0, freeHeight = 0, hInst = 0;
    double J = 0, sigMax = 0, sigy = 0;
    double massBox = 0, massClip = 0;
    double stripWidth = 0; char axisChar = 'z'; char pressSign = '+'; char openSign = '+';
    double lsqSlope = 0, curveMaxResid = 0; bool usedCurve = false;
    int orphanNodes = 0, nNodes = 0, nElems = 0;
    std::string nodeCards, shellCards, sectionCard, matCard, attachCards;
    std::vector<std::pair<int,CcStressRow>> stress;   // eid → rows
    std::string deckFile;
};

std::string cc_jsonEsc(const std::string& s) {
    std::string r;
    for (char c : s) { if (c=='"' || c=='\\') { r += '\\'; } r += c; }
    return r;
}

} // namespace

// ---------------------------------------------------------------------------
// runCclip
// ---------------------------------------------------------------------------

int runCclip(const std::string& yamlFile, ConsoleOutput& console) {
    CcConfig cfg;
    if (!parseCclipYaml(yamlFile, cfg, console)) return 1;

    if (cfg.modelFile.empty())  { console.error("[cclip] 'model' not specified"); return 1; }
    if (cfg.outputFile.empty()) { console.error("[cclip] 'output' not specified"); return 1; }
    if (cfg.clips.empty())      { console.error("[cclip] 'clips' rules not specified"); return 1; }
    if (cfg.mode != "analytic" && cfg.mode != "deck") { console.error("[cclip] mode must be analytic|deck"); return 1; }
    if (cfg.stressOutput != "embed" && cfg.stressOutput != "include") { console.error("[cclip] stress_output must be embed|include"); return 1; }

    auto resolvePath = [&](const std::string& p) {
        if (!cfg.configDir.empty() && p.find('/')==std::string::npos && p.find('\\')==std::string::npos)
            return cfg.configDir + "/" + p;
        return p;
    };
    std::string modelPath = resolvePath(cfg.modelFile);
    std::string outPrefix = cfg.outputFile;
    if (outPrefix.size() > 2 && outPrefix.substr(outPrefix.size()-2) == ".k")
        outPrefix = outPrefix.substr(0, outPrefix.size()-2);
    std::string outPath = resolvePath(outPrefix + ".k");
    std::string outPrefixPath = resolvePath(outPrefix);

    console.info("[cclip] Model: " + cfg.modelFile);
    console.info("[cclip] Mode: " + cfg.mode + ", stress_output: " + cfg.stressOutput + ", attach: " + cfg.attach);

    // Parse mesh (nodes/elements/parts/materials)
    KFileReader reader;
    Mesh mesh;
    try { mesh = reader.readFile(modelPath); }
    catch (const std::exception& e) { console.error("[cclip] read failed: " + std::string(e.what())); return 1; }
    console.info("[cclip] Parsed: " + std::to_string(mesh.getNodes().size()) + " nodes, " +
                 std::to_string(mesh.getElements().size()) + " elements, " +
                 std::to_string(mesh.getPartCount()) + " parts");

    // Raw lines (for splice — preserves unparsed keywords)
    std::vector<std::string> lines;
    {
        std::ifstream mf(modelPath);
        if (!mf.is_open()) { console.error("[cclip] cannot open model: " + modelPath); return 1; }
        std::string ln;
        while (std::getline(mf, ln)) { if (!ln.empty() && ln.back()=='\r') ln.pop_back(); lines.push_back(ln); }
    }

    // Resolve rule targets → ordered pid list
    std::vector<std::pair<int,const CcRule*>> targets;
    std::set<int> seen;
    for (const auto& r : cfg.clips) {
        if (r.pid > 0) {
            if (mesh.getParts().count(r.pid) == 0)
                { console.error("[cclip] pid " + std::to_string(r.pid) + " not found"); return 1; }
            if (seen.insert(r.pid).second) targets.push_back({r.pid, &r});
        } else if (!r.matchPart.empty()) {
            bool any = false;
            for (const auto& [pid, part] : mesh.getParts()) {
                if (cc_wildcardMatch(r.matchPart, part.name)) {
                    if (seen.insert(pid).second) { targets.push_back({pid, &r}); any = true; }
                }
            }
            if (!any) console.warning("[cclip] match_part '" + r.matchPart + "' matched no parts");
        } else {
            console.error("[cclip] clip rule needs pid or match_part"); return 1;
        }
    }
    if (targets.empty()) { console.error("[cclip] no target parts resolved"); return 1; }
    console.info("[cclip] Targets: " + std::to_string(targets.size()) + " part(s)");

    // ID bases (mesh IDs + raw-scan for MID/SECID/SET that KFileReader may not track)
    int nextNid  = mesh.getMaxNodeId() + 1;
    int nextEid  = mesh.getMaxElementId() + 1;
    int nextSec  = std::max(cc_scanMaxId(lines, "*SECTION"), 0) + 1;
    int nextMid  = std::max(cc_scanMaxId(lines, "*MAT"), 0) + 1;
    int nextSet  = std::max(cc_scanMaxId(lines, "*SET"), 0) + 1;
    int nextPidX = 0;   // extra part-like ids (CNRB)
    for (const auto& [pid, p] : mesh.getParts()) nextPidX = std::max(nextPidX, pid);
    ++nextPidX;

    std::vector<CcBuilt> builds;

    for (const auto& [pid, rulePtr] : targets) {
        const CcRule& r = *rulePtr;
        CcBuilt b;
        b.pid = pid;
        b.partTitle = mesh.getParts().at(pid).name;

        // ---- frame
        std::string axisSel = !r.axis.empty() ? r.axis : cfg.axis;
        std::string openSel = !r.open.empty() ? r.open : cfg.open;
        CcFrame fr = deriveBoxFrame(mesh, pid, axisSel, openSel, console);
        if (!fr.valid) return 1;
        b.hInst = fr.hInst;
        b.axisChar = "xyz"[fr.iw];
        b.pressSign = (fr.sw > 0) ? '+' : '-';
        b.openSign = (fr.su > 0) ? '+' : '-';

        // ---- free height / working deflection
        double Hfree = r.freeHeight;
        const CcCalib& cal = r.calib.set ? r.calib : cfg.calib;
        if (!cal.set) { console.error("[cclip] pid " + std::to_string(pid) + ": calibration missing"); return 1; }
        double deltaOp;
        if (cal.hasPoint) deltaOp = cal.pointDefl;
        else if (!cal.curve.empty()) {
            if (!cal.hasOperatingDefl) { console.error("[cclip] curve calibration requires operating_deflection"); return 1; }
            deltaOp = cal.operatingDefl;
        } else { console.error("[cclip] calibration needs point or curve"); return 1; }
        if (Hfree <= 0) Hfree = fr.hInst + ((r.overtravel > 0) ? r.overtravel : deltaOp);
        if (Hfree <= fr.hInst + 1e-9) {
            console.error("[cclip] pid " + std::to_string(pid) + ": free_height (" + std::to_string(Hfree) +
                          ") must exceed installed height (" + std::to_string(fr.hInst) + ")");
            return 1;
        }
        double deltaWork = Hfree - fr.hInst;
        if (std::fabs(deltaWork - deltaOp) > 1e-9)
            console.warning("[cclip] pid " + std::to_string(pid) + ": working deflection from geometry (" +
                            std::to_string(deltaWork) + ") != calibration deflection (" +
                            std::to_string(deltaOp) + ") — using geometry value for pressing, calibration value for stiffness");
        b.freeHeight = Hfree; b.deltaWork = deltaWork;

        // ---- material (rule > global > K-file part material)
        CcMaterial mat = r.material.set ? r.material : cfg.material;
        if (!r.material.set && !cfg.material.set) {
            const MaterialData* md = mesh.getMaterial(mesh.getParts().at(pid).materialId);
            if (md && md->isValid()) { mat.E = md->E; mat.nu = md->nu; if (md->density>0) mat.rho = md->density; if (md->sigy>0) mat.sigy = md->sigy; }
            else console.warning("[cclip] pid " + std::to_string(pid) + ": no usable K-file material — using BeCu defaults");
        }
        b.sigy = mat.sigy;

        // ---- target stiffness + working force
        double kTarget, Fwork;
        if (cal.hasPoint) {
            if (cal.pointDefl <= 0 || cal.pointForce <= 0) { console.error("[cclip] point needs positive deflection/force"); return 1; }
            kTarget = cal.pointForce / cal.pointDefl;
            Fwork = cal.pointForce;
        } else {
            // secant at operating point (guarantees working force); LSQ slope reported as diagnostic
            auto cv = cal.curve;
            std::sort(cv.begin(), cv.end());
            double Fop = 0;
            if (deltaOp <= cv.front().first) Fop = cv.front().second * (deltaOp / cv.front().first);
            else if (deltaOp >= cv.back().first) Fop = cv.back().second;
            else for (size_t i = 0; i + 1 < cv.size(); ++i)
                if (deltaOp >= cv[i].first && deltaOp <= cv[i+1].first) {
                    double a = (deltaOp - cv[i].first) / (cv[i+1].first - cv[i].first);
                    Fop = cv[i].second + a * (cv[i+1].second - cv[i].second);
                    break;
                }
            kTarget = Fop / deltaOp;
            Fwork = Fop;
            double sdF = 0, sdd = 0;
            for (auto& p : cv) { sdF += p.first * p.second; sdd += p.first * p.first; }
            b.lsqSlope = (sdd > 0) ? sdF / sdd : 0;
            for (auto& p : cv) {
                double resid = std::fabs(p.second - kTarget * p.first) / std::max(1e-12, p.second);
                b.curveMaxResid = std::max(b.curveMaxResid, resid);
            }
            b.usedCurve = true;
        }
        b.kTarget = kTarget; b.Fwork = Fwork;

        // ---- profile + calibration
        double W = (r.width > 0) ? r.width : fr.W;
        // tip rise > working deflection keeps the pressed shoulder clear of the mating plane
        double rise = (r.profile.tipRise > 0) ? r.profile.tipRise
                                              : std::min(0.45 * Hfree, 1.2 * deltaWork);
        if (rise < 1.05 * deltaWork)
            console.warning("[cclip] pid " + std::to_string(pid) + ": tip_rise (" + std::to_string(rise) +
                            ") < 1.05x working deflection (" + std::to_string(deltaWork) +
                            ") — pressed shoulder may sit near the mating plane");
        CcProfile prof;
        std::string perr;
        if (!buildCProfile(fr.L, Hfree, rise, r.profile, r.nArc, r.nFlat, prof, perr)) {
            console.error("[cclip] pid " + std::to_string(pid) + ": profile: " + perr); return 1;
        }
        double J = cc_momentIntegralJ(prof);
        if (J <= 0) { console.error("[cclip] pid " + std::to_string(pid) + ": zero moment integral"); return 1; }
        b.J = J;
        b.stripWidth = W;

        double t, E = mat.E;
        if (cal.calibrate == "modulus") {
            if (r.thickness <= 0) { console.error("[cclip] calibrate=modulus requires explicit thickness"); return 1; }
            t = r.thickness;
            E = 12.0 * J * kTarget / (W * t * t * t);
            b.kAchieved = kTarget; b.relErr = 0.0;
        } else {
            t = std::cbrt(12.0 * J * kTarget / (E * W));
            double tc = std::min(std::max(t, cal.tMin), cal.tMax);
            if (tc != t) console.warning("[cclip] pid " + std::to_string(pid) + ": thickness clamped " +
                                          std::to_string(t) + " → " + std::to_string(tc));
            t = tc;
            b.kAchieved = E * W * t * t * t / (12.0 * J);
            b.relErr = std::fabs(b.kAchieved - kTarget) / kTarget;
            if (b.relErr > cal.tolerance) {
                console.error("[cclip] pid " + std::to_string(pid) + ": stiffness error " +
                              std::to_string(b.relErr * 100) + "% exceeds tolerance " +
                              std::to_string(cal.tolerance * 100) + "% (clamped thickness?)");
                return 1;
            }
        }
        b.t = t; b.E = E;

        // ---- pressed shape (analytic) — moment-matched morph
        double I = W * t * t * t / 12.0;
        double EI = E * I;
        bool pressed = (cfg.mode == "analytic");
        std::vector<CcPt> shape;
        double cScale = 0;
        if (pressed) {
            // shape scale c absorbs large-rotation geometry; the STRESS field is scaled
            // by the calibrated working force so its moment field equilibrates F_work
            // (the measured contact force) at the tip — squeeze_interference principle.
            cScale = cc_solvePressScale(prof, EI, Fwork, fr.hInst, console);
            shape = cc_deformProfile(prof, cScale, EI, nullptr);
            if (std::fabs(cScale) > 1e-12) {
                double geomDev = std::fabs(std::fabs(cScale) - Fwork) / Fwork;
                if (geomDev > 0.30)
                    console.warning("[cclip] pid " + std::to_string(pid) +
                                    ": large-deflection shape factor deviates " +
                                    std::to_string(geomDev * 100) + "% from linear estimate");
            }
        } else {
            shape = prof.pts;
        }

        // ---- strip mesh (nodes + quads), IDs allocated from running counters
        int nP = (int)shape.size();
        int nW = std::max(1, r.nWidth);
        int baseNid = nextNid, baseEid = nextEid;
        std::ostringstream nodeSS, shellSS;
        bat::writeComment(nodeSS, "cclip pid " + std::to_string(pid) + " nodes");
        nodeSS << "*NODE\n";
        double y0 = (fr.W - W) / 2.0;
        for (int i = 0; i < nP; ++i)
            for (int j = 0; j <= nW; ++j) {
                double g[3];
                cc_toGlobal(fr, shape[i].x, y0 + W * j / nW, shape[i].z, g);
                bat::writeNode(nodeSS, baseNid + i * (nW + 1) + j, g[0], g[1], g[2]);
            }
        bat::writeComment(shellSS, "cclip pid " + std::to_string(pid) + " shells");
        shellSS << "*ELEMENT_SHELL\n";
        for (int i = 0; i < nP - 1; ++i)
            for (int j = 0; j < nW; ++j) {
                int n00 = baseNid + i * (nW+1) + j;
                int n10 = baseNid + (i+1) * (nW+1) + j;
                int n11 = baseNid + (i+1) * (nW+1) + j + 1;
                int n01 = baseNid + i * (nW+1) + j + 1;
                bat::writeShell(shellSS, baseEid + i * nW + j, pid, n00, n10, n11, n01);
            }
        b.nNodes = nP * (nW + 1);
        b.nElems = (nP - 1) * nW;
        nextNid += b.nNodes;
        nextEid += b.nElems;
        b.nodeCards = nodeSS.str();
        b.shellCards = shellSS.str();

        // ---- section + material cards (new SECID/MID, PID kept)
        b.newSecid = nextSec++;
        b.newMid = nextMid++;
        double rhoClip = mat.rho;
        // mass bookkeeping (box bbox volume ≈ exact for a rectangular block)
        const MaterialData* mdBox = mesh.getMaterial(mesh.getParts().at(pid).materialId);
        double rhoBox = (mdBox && mdBox->density > 0) ? mdBox->density : mat.rho;
        b.massBox = rhoBox * fr.L * fr.W * fr.hInst;
        double stripArea = prof.pts.back().s * W;
        b.massClip = rhoClip * stripArea * t;
        if (r.matchMass && b.massClip > 0) {
            rhoClip *= b.massBox / b.massClip;
            b.massClip = b.massBox;
        }
        std::ostringstream secSS, matSS;
        bat::writeSectionShell(secSS, b.newSecid, r.elform, t);
        cc_writeMatElastic(matSS, b.newMid, rhoClip, E, mat.nu, "CCLIP_" + std::to_string(pid));
        b.sectionCard = secSS.str();
        b.matCard = matSS.str();

        // ---- initial stress rows (pressed bending state, tangent-aligned uniaxial)
        if (pressed) {
            std::vector<double> Kcum(nP, 0.0);
            for (int i = 1; i < nP; ++i) {
                double km0 = cc_unitMoment(prof, i-1) / EI, km1 = cc_unitMoment(prof, i) / EI;
                Kcum[i] = Kcum[i-1] + 0.5 * (km0 + km1) * (prof.pts[i].s - prof.pts[i-1].s);
            }
            double stressSign = (cScale >= 0) ? 1.0 : -1.0;
            for (int i = 0; i < nP - 1; ++i) {
                double dKm = stressSign * Fwork * 0.5 * (cc_unitMoment(prof, i) + cc_unitMoment(prof, i+1)) / EI;
                double sigB = E * dKm * t / 2.0;   // fiber stress magnitude at surfaces
                b.sigMax = std::max(b.sigMax, std::fabs(sigB));
                double thm = 0.5 * (shape[i].theta + shape[i+1].theta);
                // tangent in global coords: cos(th)*su*e_iu + sin(th)*sw*e_iw
                double tau[3] = {0,0,0};
                tau[fr.iu] = std::cos(thm) * fr.su;
                tau[fr.iw] = std::sin(thm) * fr.sw;
                // sigma(zeta)=-E*dK*zeta → top(T=+1, +normal side) = -sigB, bottom = +sigB
                CcStressRow row;
                double comp[6] = { tau[0]*tau[0], tau[1]*tau[1], tau[2]*tau[2],
                                   tau[0]*tau[1], tau[1]*tau[2], tau[2]*tau[0] };
                for (int k = 0; k < 6; ++k) { row.top[k] = -sigB * comp[k]; row.bot[k] = +sigB * comp[k]; }
                for (int j = 0; j < nW; ++j)
                    b.stress.push_back({ baseEid + i * nW + j, row });
            }
            if (mat.sigy > 0 && b.sigMax > 0.8 * mat.sigy)
                console.warning("[cclip] pid " + std::to_string(pid) + ": sig_max " + std::to_string(b.sigMax) +
                                " MPa exceeds 0.8*sigy (" + std::to_string(0.8*mat.sigy) +
                                ") — plasticity expected, v1 is elastic-only");
        }

        // ---- attach (cnrb): foot nodes + nearby non-target-part nodes within attach_tol
        if (cfg.attach == "cnrb") {
            std::vector<int> setNids;
            for (int i = 0; i <= prof.iFootEnd; ++i)
                for (int j = 0; j <= nW; ++j) setNids.push_back(baseNid + i * (nW+1) + j);
            // foot bbox in global coords
            double g0[3], g1[3];
            cc_toGlobal(fr, 0.0, y0, 0.0, g0);
            cc_toGlobal(fr, prof.Lb, y0 + W, 0.0, g1);
            double flo[3], fhi[3];
            for (int a = 0; a < 3; ++a) { flo[a] = std::min(g0[a], g1[a]) - cfg.attachTol; fhi[a] = std::max(g0[a], g1[a]) + cfg.attachTol; }
            std::set<int> targetNids;
            for (const auto& [eid, elem] : mesh.getElements())
                if (elem.partId == pid) for (int i2 = 0; i2 < 8; ++i2) targetNids.insert(elem.nodeIds[i2]);
            int boardHits = 0;
            for (const auto& [nid, node] : mesh.getNodes()) {
                if (targetNids.count(nid)) continue;
                double p[3] = { node.position.x, node.position.y, node.position.z };
                if (p[0] >= flo[0] && p[0] <= fhi[0] && p[1] >= flo[1] && p[1] <= fhi[1] &&
                    p[2] >= flo[2] && p[2] <= fhi[2]) { setNids.push_back(nid); ++boardHits; }
            }
            if (boardHits == 0)
                console.warning("[cclip] pid " + std::to_string(pid) +
                                ": attach=cnrb found no board nodes within attach_tol — CNRB spans foot only");
            std::ostringstream atSS;
            int sid = nextSet++;
            bat::writeSetNodeList(atSS, sid, "CCLIP_FOOT_" + std::to_string(pid), setNids);
            int cnrbPid = nextPidX++;
            atSS << "*CONSTRAINED_NODAL_RIGID_BODY\n"
                 << "$#     pid     cid    nsid   pnode    iprt  drflag  rrflag\n";
            char buf[128];
            snprintf(buf, sizeof(buf), "%10d%10d%10d\n", cnrbPid, 0, sid);
            atSS << buf;
            b.attachCards = atSS.str();
        }

        // ---- deck mode: standalone compression deck per clip
        if (cfg.mode == "deck") {
            std::string deckPath = outPrefixPath + "_cclip_deck_" + std::to_string(pid) + ".k";
            std::ofstream dk(deckPath);
            if (!dk.is_open()) { console.error("[cclip] cannot write deck: " + deckPath); return 1; }
            dk << "*KEYWORD\n*TITLE\ncclip compression deck pid " << pid << "\n";
            // free-state strip (local pid 1) + rigid plate (pid 2)
            dk << "*NODE\n";
            int dn = 1;
            std::map<int,int> localNid;   // strip grid (i,j) → local id
            for (int i = 0; i < nP; ++i)
                for (int j = 0; j <= nW; ++j) {
                    double g[3];
                    cc_toGlobal(fr, prof.pts[i].x, y0 + W * j / nW, prof.pts[i].z, g);
                    bat::writeNode(dk, dn, g[0], g[1], g[2]);
                    localNid[i * (nW+1) + j] = dn++;
                }
            // plate: 4 nodes just above the top flat, spanning contact flat × width
            double gap = 0.01 * t + t / 2.0;
            double zPlate = Hfree + gap;
            double xA = prof.Lb - prof.Lt, xB = prof.Lb;
            int pn[4];
            for (int k = 0; k < 4; ++k) {
                double px = (k==0||k==3) ? xA - 0.2 : xB + 0.2;
                double py = (k<2) ? y0 - 0.2 : y0 + W + 0.2;
                double g[3];
                cc_toGlobal(fr, px, py, zPlate, g);
                bat::writeNode(dk, dn, g[0], g[1], g[2]);
                pn[k] = dn++;
            }
            dk << "*ELEMENT_SHELL\n";
            int de = 1;
            for (int i = 0; i < nP - 1; ++i)
                for (int j = 0; j < nW; ++j)
                    bat::writeShell(dk, de++, 1,
                                    localNid[i*(nW+1)+j], localNid[(i+1)*(nW+1)+j],
                                    localNid[(i+1)*(nW+1)+j+1], localNid[i*(nW+1)+j+1]);
            bat::writeShell(dk, de++, 2, pn[0], pn[1], pn[2], pn[3]);
            bat::writePart(dk, "CCLIP", 1, 1, 1);
            bat::writeSectionShell(dk, 1, r.elform, t);
            cc_writeMatElastic(dk, 1, rhoClip, E, mat.nu, "CCLIP");
            bat::writePart(dk, "PRESS_PLATE", 2, 2, 2);
            bat::writeSectionShell(dk, 2, 2, 0.5);
            // plate free only along compression axis: CON1 code by axis (x→5, y→6, z→4), all rotations fixed
            int con1 = (fr.iw == 0) ? 5 : (fr.iw == 1) ? 6 : 4;
            cc_writeMatRigid(dk, 2, 7.85e-9, 210000.0, 0.3, 1, con1, 7, "PRESS_PLATE");
            // foot SPC
            std::vector<int> footN;
            for (int i = 0; i <= prof.iFootEnd; ++i)
                for (int j = 0; j <= nW; ++j) footN.push_back(localNid[i*(nW+1)+j]);
            bat::writeSetNodeList(dk, 1, "CCLIP_FOOT", footN);
            cc_writeSpcSet(dk, 1);
            // tip node set (upper contact arm) for contact
            std::vector<int> tipN;
            for (int i = prof.iFootEnd; i < nP; ++i)
                if (prof.pts[i].z >= Hfree - 0.5 * rise)
                    for (int j = 0; j <= nW; ++j) tipN.push_back(localNid[i*(nW+1)+j]);
            bat::writeSetNodeList(dk, 2, "CCLIP_TIP", tipN);
            cc_writeContactNodesToSurface(dk, 2, 2);
            // prescribed compression: plate moves toward the clip (local −w) so the tip
            // lands at h_inst; global displacement sign follows the frame's sw
            bat::writeDefineCurve(dk, 1, "cclip_compress", {{0.0, 0.0}, {1.0, -fr.sw * (deltaWork + gap)}});
            cc_writeBpmRigid(dk, 2, fr.iw + 1, 1);
            // implicit quasi-static (card text mirrors implicit op level defaults)
            dk << "*CONTROL_IMPLICIT_GENERAL\n$#  imflag       dt0\n         1       0.1\n";
            dk << "*CONTROL_IMPLICIT_SOLUTION\n$#  nsolvr    ilimit    maxref     dctol     ectol\n"
                  "        12        11        15     0.001      0.01\n";
            dk << "*CONTROL_IMPLICIT_AUTO\n$#   iauto    iteopt    itewin     dtmin     dtmax\n"
                  "         1        11         5       0.0       0.0\n";
            dk << "*CONTROL_TERMINATION\n$#  endtim\n       1.0\n";
            dk << "*DATABASE_RCFORC\n      0.01         0\n";
            dk << "*DATABASE_NODOUT\n      0.01         0\n";
            bat::writeSetPartList(dk, 3, "CCLIP_PART", {1});
            dk << "*INTERFACE_SPRINGBACK_LSDYNA\n$#    psid\n         3\n";
            dk << "*END\n";
            dk.close();
            b.deckFile = deckPath;
            console.info("[cclip] pid " + std::to_string(pid) + ": compression deck → " + deckPath);
        }

        // orphan nodes: target-part nodes not used by any other part's elements
        {
            std::set<int> targetNids, otherNids;
            for (const auto& [eid, elem] : mesh.getElements()) {
                auto& dst = (elem.partId == pid) ? targetNids : otherNids;
                for (int i2 = 0; i2 < 8; ++i2) dst.insert(elem.nodeIds[i2]);
            }
            for (int nid : targetNids) if (!otherNids.count(nid)) ++b.orphanNodes;
        }

        // console report
        {
            std::ostringstream os;
            os << std::fixed << std::setprecision(4);
            os << "[cclip] pid " << pid << " (" << b.partTitle << "): L=" << fr.L << " W=" << W
               << " h_inst=" << fr.hInst << " H_free=" << Hfree << " δ=" << deltaWork
               << " press_from=" << b.pressSign << b.axisChar << " open=" << b.openSign;
            console.info(os.str());
            std::ostringstream os2;
            os2 << std::scientific << std::setprecision(4);
            os2 << "[cclip]   k_target=" << kTarget << " N/mm → t=" << b.t << " mm"
                << " (k_achieved=" << b.kAchieved << ", err=" << std::fixed << std::setprecision(2)
                << b.relErr * 100 << "%), F_work=" << std::setprecision(3) << b.Fwork << " N";
            console.info(os2.str());
            if (b.usedCurve) {
                std::ostringstream os3;
                os3 << "[cclip]   curve: secant@δ_op used; LSQ slope=" << std::scientific << std::setprecision(4)
                    << b.lsqSlope << ", max residual=" << std::fixed << std::setprecision(1)
                    << b.curveMaxResid * 100 << "% — v1 matches LINEAR (secant) stiffness only";
                console.info(os3.str());
            }
            if (pressed) {
                std::ostringstream os4;
                os4 << "[cclip]   sig_max=" << std::fixed << std::setprecision(1) << b.sigMax
                    << " MPa" << (b.sigy > 0 ? (" (sigy=" + std::to_string((int)b.sigy) + ")") : "");
                console.info(os4.str());
            }
        }

        builds.push_back(std::move(b));
    }

    // ------------------------------------------------------------------
    // Splice model: remove target solids, retarget parts, insert new cards
    // ------------------------------------------------------------------
    std::set<int> pidSet;
    for (const auto& b : builds) pidSet.insert(b.pid);
    int removedLines = cc_removeSolidElements(lines, pidSet);
    console.info("[cclip] Removed " + std::to_string(removedLines) + " solid element line(s)");

    for (const auto& b : builds) {
        CcPartLine pl = cc_findPartLine(lines, b.pid);
        if (pl.lineIdx < 0) { console.error("[cclip] *PART line for pid " + std::to_string(b.pid) + " not found"); return 1; }
        lines[pl.lineIdx] = cc_updatePartLine(lines[pl.lineIdx], b.newSecid, b.newMid);
        if (pl.secid > 0 && !cc_idShared(lines, 1, pl.secid, b.pid))
            lines = cc_removeBlockById(lines, "*SECTION", pl.secid);
        if (pl.mid > 0 && !cc_idShared(lines, 2, pl.mid, b.pid))
            lines = cc_removeBlockById(lines, "*MAT", pl.mid);
    }

    std::ostringstream ins;
    for (const auto& b : builds) {
        ins << b.nodeCards << b.shellCards << b.sectionCard << b.matCard << b.attachCards;
    }
    bool anyStress = false;
    for (const auto& b : builds) if (!b.stress.empty()) anyStress = true;
    std::string dynainName = outPrefix + ".dynain";
    if (anyStress) {
        std::vector<std::pair<int,const CcStressRow*>> rows;
        for (const auto& b : builds)
            for (const auto& [eid, sr] : b.stress) rows.push_back({eid, &sr});
        if (cfg.stressOutput == "embed") {
            cc_writeInitialStressShell(ins, rows);
        } else {
            std::string dynainPath = outPrefixPath + ".dynain";
            std::ofstream df(dynainPath);
            if (!df.is_open()) { console.error("[cclip] cannot write: " + dynainPath); return 1; }
            df << "*KEYWORD\n";
            cc_writeInitialStressShell(df, rows);
            df << "*END\n";
            df.close();
            ins << "*INCLUDE\n" << dynainName << "\n";
            console.info("[cclip] Initial stress → " + dynainPath);
        }
    }
    kw_insertBeforeEnd(lines, ins.str());

    std::ofstream of(outPath);
    if (!of.is_open()) { console.error("[cclip] cannot write: " + outPath); return 1; }
    for (const auto& l : lines) of << l << "\n";
    of.close();
    console.success("[cclip] Done → " + outPath);

    // ------------------------------------------------------------------
    // JSON report
    // ------------------------------------------------------------------
    if (cfg.report) {
        std::string repPath = outPrefixPath + "_cclip_report.json";
        std::ofstream rf(repPath);
        if (rf.is_open()) {
            rf << std::scientific << std::setprecision(6);
            rf << "{\n  \"mode\": \"" << cfg.mode << "\",\n  \"stress_output\": \"" << cfg.stressOutput << "\",\n  \"clips\": [\n";
            for (size_t i = 0; i < builds.size(); ++i) {
                const auto& b = builds[i];
                rf << "    {\n"
                   << "      \"pid\": " << b.pid << ",\n"
                   << "      \"part_title\": \"" << cc_jsonEsc(b.partTitle) << "\",\n"
                   << "      \"installed_height\": " << b.hInst << ",\n"
                   << "      \"free_height\": " << b.freeHeight << ",\n"
                   << "      \"operating_deflection\": " << b.deltaWork << ",\n"
                   << "      \"operating_force\": " << b.Fwork << ",\n"
                   << "      \"target_stiffness\": " << b.kTarget << ",\n"
                   << "      \"achieved_stiffness\": " << b.kAchieved << ",\n"
                   << "      \"rel_error\": " << b.relErr << ",\n"
                   << "      \"thickness\": " << b.t << ",\n"
                   << "      \"E\": " << b.E << ",\n"
                   << "      \"moment_integral_J\": " << b.J << ",\n"
                   << "      \"axis\": \"" << b.axisChar << "\",\n"
                   << "      \"press_from\": \"" << b.pressSign << b.axisChar << "\",\n"
                   << "      \"open\": \"" << b.openSign << "\",\n"
                   << "      \"strip_width\": " << b.stripWidth << ",\n"
                   << "      \"sig_max\": " << b.sigMax << ",\n"
                   << "      \"sigy\": " << b.sigy << ",\n"
                   << "      \"mass_box\": " << b.massBox << ",\n"
                   << "      \"mass_clip\": " << b.massClip << ",\n"
                   << "      \"orphan_nodes\": " << b.orphanNodes << ",\n"
                   << "      \"nodes\": " << b.nNodes << ",\n"
                   << "      \"elements\": " << b.nElems << ",\n"
                   << "      \"used_curve\": " << (b.usedCurve ? "true" : "false") << ",\n"
                   << "      \"lsq_slope\": " << b.lsqSlope << ",\n"
                   << "      \"curve_max_residual\": " << b.curveMaxResid << ",\n"
                   << "      \"new_secid\": " << b.newSecid << ",\n"
                   << "      \"new_mid\": " << b.newMid
                   << (b.deckFile.empty() ? "" : (std::string(",\n      \"deck_file\": \"") + cc_jsonEsc(b.deckFile) + "\""))
                   << "\n    }" << (i + 1 < builds.size() ? "," : "") << "\n";
            }
            rf << "  ],\n  \"limitations\": \"v1: linear(secant) stiffness match; elastic bending prestress only; shell contact gap ~t/2 not compensated\"\n}\n";
            rf.close();
            console.info("[cclip] Report → " + repPath);
        }
    }
    return 0;
}
