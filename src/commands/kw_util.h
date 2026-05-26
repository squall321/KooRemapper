#pragma once
// ============================================================
// kw_util.h — Common LS-DYNA keyword file manipulation utilities
// Used by multiple command implementations.
// All functions are inline to keep this header-only.
// ============================================================

#include <string>
#include <vector>
#include <algorithm>
#include <cctype>
#include <sstream>
#include <cstdio>

// Knowledge graph (lat.md):
//   @lat: [[modules/commands]]

// ---------------------------------------------------------------------------
// String helpers
// ---------------------------------------------------------------------------

inline std::string kw_trim(const std::string& s) {
    size_t a = s.find_first_not_of(" \t\r\n");
    if (a == std::string::npos) return "";
    size_t b = s.find_last_not_of(" \t\r\n");
    return s.substr(a, b - a + 1);
}

inline std::string kw_upper(const std::string& s) {
    std::string r = s;
    std::transform(r.begin(), r.end(), r.begin(),
                   [](unsigned char c){ return (char)std::toupper(c); });
    return r;
}

// Split a line into 10-character fixed-width tokens (trimmed)
inline std::vector<std::string> kw_tok10(const std::string& s) {
    std::vector<std::string> toks;
    for (int i = 0; i < (int)s.size(); i += 10)
        toks.push_back(kw_trim(s.substr(i, std::min(10, (int)s.size()-i))));
    return toks;
}

// ---------------------------------------------------------------------------
// Fixed-width field manipulation
// ---------------------------------------------------------------------------

// Set a fixed-width field at [pos, pos+width) in a line (right-aligned)
inline std::string kw_setField(const std::string& line, int pos, int width,
                                const std::string& val) {
    std::string r = line;
    while ((int)r.size() < pos + width) r += ' ';
    std::string v = val;
    if ((int)v.size() > width) v = v.substr(v.size() - width);
    r.replace(pos, width, std::string(width - (int)v.size(), ' ') + v);
    return r;
}

// ---------------------------------------------------------------------------
// Keyword block operations
// ---------------------------------------------------------------------------

// Remove all blocks whose keyword line starts with keyword (case-insensitive)
inline std::vector<std::string> kw_removeKeyword(
        const std::vector<std::string>& lines, const std::string& keyword) {
    std::vector<bool> rm(lines.size(), false);
    std::string kwUp = kw_upper(keyword);
    for (int i = 0; i < (int)lines.size(); ) {
        std::string up = kw_upper(kw_trim(lines[i]));
        if (up.rfind(kwUp, 0) != 0) { ++i; continue; }
        int end = i + 1;
        while (end < (int)lines.size()) {
            std::string et = kw_trim(lines[end]);
            if (!et.empty() && et[0] == '*') break;
            ++end;
        }
        for (int k = i; k < end; ++k) rm[k] = true;
        i = end;
    }
    std::vector<std::string> out;
    for (size_t i = 0; i < lines.size(); ++i) if (!rm[i]) out.push_back(lines[i]);
    return out;
}

// Remove *DEFINE_CURVE blocks where SIDR field (toks[1]) == 1 (DR load curves)
// Modifies lines in place; returns number of curves removed
inline int kw_removeDrCurves(std::vector<std::string>& lines) {
    int removed = 0;
    std::vector<bool> rm(lines.size(), false);
    for (int i = 0; i < (int)lines.size(); ) {
        std::string up = kw_upper(kw_trim(lines[i]));
        if (up.rfind("*DEFINE_CURVE", 0) != 0) { ++i; continue; }
        bool hasTitle = (up.find("_TITLE") != std::string::npos);
        int titlesLeft = hasTitle ? 1 : 0; int sidr = -1;
        for (int j = i+1; j < (int)lines.size(); ++j) {
            std::string jt = kw_trim(lines[j]);
            if (jt.empty() || jt[0]=='$') continue;
            if (jt[0]=='*') break;
            if (titlesLeft-- > 0) continue;
            auto toks = kw_tok10(lines[j]);
            if (toks.size() >= 2) { try { sidr = std::stoi(toks[1]); } catch(...){} }
            break;
        }
        if (sidr != 1) { ++i; continue; }
        int end = i+1;
        while (end < (int)lines.size()) {
            std::string et = kw_trim(lines[end]);
            if (!et.empty() && et[0]=='*') break;
            ++end;
        }
        for (int k = i; k < end; ++k) rm[k] = true;
        ++removed; i = end;
    }
    std::vector<std::string> out;
    for (size_t i = 0; i < lines.size(); ++i) if (!rm[i]) out.push_back(lines[i]);
    lines = std::move(out);
    return removed;
}

// Insert content lines before *END (or append if *END not found)
inline void kw_insertBeforeEnd(std::vector<std::string>& lines,
                                const std::string& content) {
    std::vector<std::string> newLines;
    std::istringstream iss(content);
    std::string ln;
    while (std::getline(iss, ln)) newLines.push_back(ln);
    for (int i = 0; i < (int)lines.size(); ++i) {
        if (kw_upper(kw_trim(lines[i])) == "*END") {
            lines.insert(lines.begin()+i, newLines.begin(), newLines.end());
            return;
        }
    }
    for (const auto& l : newLines) lines.push_back(l);
}

// ---------------------------------------------------------------------------
// CONTROL card readers / modifiers
// ---------------------------------------------------------------------------

// Read endtim from *CONTROL_TERMINATION first data line.
// Returns -1.0 if keyword not found, 0.0 if found but field empty, else the value.
inline double kw_readEndtime(const std::vector<std::string>& lines) {
    bool inTerm=false, hasTitle=false, titleDone=false, found=false;
    for (const auto& ln : lines) {
        std::string tr = kw_trim(ln);
        if (tr.empty()) continue;
        if (tr[0]=='*') {
            std::string up = kw_upper(tr);
            inTerm = (up.rfind("*CONTROL_TERMINATION", 0) == 0);
            if (inTerm) found = true;
            hasTitle = (up.find("_TITLE") != std::string::npos);
            titleDone = false; continue;
        }
        if (!inTerm || tr[0]=='$') continue;
        if (hasTitle && !titleDone) { titleDone = true; continue; }
        auto toks = kw_tok10(ln);
        if (!toks.empty()) { try { return std::stod(toks[0]); } catch(...) { return 0.0; } }
        inTerm = false;
    }
    return found ? 0.0 : -1.0;
}

// Update *CONTROL_TERMINATION endtim field (pos 0, width 10)
inline bool kw_modifyTermination(std::vector<std::string>& lines, double endtime) {
    bool inTerm=false, hasTitle=false, titleDone=false;
    for (auto& ln : lines) {
        std::string tr = kw_trim(ln);
        if (tr.empty()) continue;
        if (tr[0]=='*') {
            std::string up = kw_upper(tr);
            inTerm = (up.rfind("*CONTROL_TERMINATION", 0) == 0);
            hasTitle = (up.find("_TITLE") != std::string::npos);
            titleDone = false; continue;
        }
        if (!inTerm || tr[0]=='$') continue;
        if (hasTitle && !titleDone) { titleDone = true; continue; }
        char buf[32]; snprintf(buf, sizeof(buf), "%g", endtime);
        ln = kw_setField(ln, 0, 10, kw_trim(buf));
        return true;
    }
    return false;
}

// Modify *CONTROL_TIMESTEP: set TSSFAC (pos 10, width 10) and DT2MS (pos 40, width 10)
inline bool kw_modifyTimestep(std::vector<std::string>& lines,
                               const std::string& tssfac = "0.900000",
                               const std::string& dt2ms  = "0.0") {
    bool inTs=false, hasTitle=false, titleDone=false;
    for (auto& ln : lines) {
        std::string tr = kw_trim(ln);
        if (tr.empty()) continue;
        if (tr[0]=='*') {
            std::string up = kw_upper(tr);
            inTs = (up.rfind("*CONTROL_TIMESTEP", 0) == 0);
            hasTitle = (up.find("_TITLE") != std::string::npos);
            titleDone = false; continue;
        }
        if (!inTs || tr[0]=='$') continue;
        if (hasTitle && !titleDone) { titleDone = true; continue; }
        ln = kw_setField(ln, 10, 10, tssfac);
        ln = kw_setField(ln, 40, 10, dt2ms);
        return true;
    }
    return false;
}

// Check *SECTION_SHELL for ELFORM=16 (not supported in implicit)
// Appends warning strings; if fix==true, replaces ELFORM=16 with 2
inline void kw_checkShellElform(std::vector<std::string>& lines, bool fix,
                                 std::vector<std::string>& warnings) {
    bool inShell=false, hasTitle=false, titleDone=false;
    for (auto& ln : lines) {
        std::string tr = kw_trim(ln);
        if (tr.empty()) continue;
        if (tr[0]=='*') {
            std::string up = kw_upper(tr);
            inShell = (up.rfind("*SECTION_SHELL", 0) == 0);
            hasTitle = (up.find("_TITLE") != std::string::npos);
            titleDone = false; continue;
        }
        if (!inShell || tr[0]=='$') continue;
        if (hasTitle && !titleDone) { titleDone = true; continue; }
        auto toks = kw_tok10(ln);
        if (toks.size() >= 2) {
            int elform = -1;
            try { elform = std::stoi(toks[1]); } catch(...) {}
            if (elform == 16) {
                warnings.push_back("[WARNING]  *SECTION_SHELL SECID=" + toks[0] +
                    ": ELFORM=16 not supported in implicit"
                    " (set fix_shell_elform: true to auto-fix)");
                if (fix) ln = kw_setField(ln, 10, 10, "2");
            }
        }
        inShell = false; // one data line per section keyword
    }
}

// ---------------------------------------------------------------------------
// CONTROL card field patchers (used by stabilize, optimize, etc.)
// ---------------------------------------------------------------------------

// Returns 0=not found, 1=already has value, 2=modified
inline int kw_patchControlField(std::vector<std::string>& lines,
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

inline bool kw_hasKeyword(const std::vector<std::string>& lines, const std::string& keyword) {
    for (const auto& ln : lines) {
        std::string tr = kw_trim(ln);
        if (!tr.empty() && tr[0] == '*') {
            if (kw_upper(tr).rfind(keyword, 0) == 0) return true;
        }
    }
    return false;
}
