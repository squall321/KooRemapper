#include "matdb.h"
#include "cli/ConsoleOutput.h"
#include "assembly/AssemblyConfig.h"
#include "assembly/ModelAssembler.h"

#include <string>
#include <fstream>
#include <cctype>
#include <algorithm>
#include <vector>
#include <iterator>

using KooRemapper::ConsoleOutput;
using KooRemapper::MatdbOperation;
using KooRemapper::ModelAssembler;

int runMatdb(const std::string& yamlFile, ConsoleOutput& console) {
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
    auto countIndent = [](const std::string& s) -> int {
        int n=0; while (n<(int)s.size() && s[n]==' ') ++n; return n;
    };
    auto stripQuotes = [](const std::string& s) -> std::string {
        if (s.size() >= 2 && ((s.front()=='"' && s.back()=='"') || (s.front()=='\'' && s.back()=='\'')))
            return s.substr(1, s.size()-2);
        return s;
    };

    std::string modelFile, outputFile;
    MatdbOperation op;
    bool inMaterialsList = false;
    int materialsIndent = 0;
    bool inMaterialItem = false;
    int materialItemIndent = 0;

    std::string ln;
    while (std::getline(f, ln)) {
        if (!ln.empty() && ln.back()=='\r') ln.pop_back();
        int indent = countIndent(ln);
        std::string tr = trim(ln);
        if (tr.empty() || tr[0]=='#') continue;

        if (inMaterialsList && indent <= materialsIndent && tr.substr(0,2) != "- ") {
            inMaterialsList = false;
            inMaterialItem = false;
        }

        size_t cp = tr.find(':');
        if (cp == std::string::npos) continue;
        std::string key = trim(tr.substr(0, cp));
        std::string val = stripQuotes(trim(tr.substr(cp+1)));

        if (!inMaterialsList) {
            if      (key == "model")    modelFile = val;
            else if (key == "output")   outputFile = val;
            else if (key == "database") op.databasePath = val;
            else if (key == "mat_type") op.globalMatType = val;
            else if (key == "thermal")  op.globalThermal = (val == "true" || val == "yes" || val == "1");
            else if (key == "materials") {
                inMaterialsList = true;
                materialsIndent = indent;
            }
        }

        if (inMaterialsList) {
            if (tr.substr(0, 2) == "- " && indent > materialsIndent) {
                op.rules.push_back({});
                inMaterialItem = true;
                materialItemIndent = indent;
                std::string rest = trim(tr.substr(2));
                size_t rcp = rest.find(':');
                if (rcp != std::string::npos) {
                    std::string rk = trim(rest.substr(0, rcp));
                    std::string rv = stripQuotes(trim(rest.substr(rcp+1)));
                    auto& rule = op.rules.back();
                    if      (rk == "match")      rule.match = rv;
                    else if (rk == "match_part") rule.matchPart = rv;
                    else if (rk == "mid")        { try { rule.mid = std::stoi(rv); } catch(...) {} }
                    else if (rk == "mat_type")   rule.matType = rv;
                    else if (rk == "thermal")    rule.thermalOverride = (rv == "true" || rv == "yes" || rv == "1") ? 1 : 0;
                }
            } else if (inMaterialItem && indent > materialItemIndent) {
                auto& rule = op.rules.back();
                if      (key == "match")      rule.match = val;
                else if (key == "match_part") rule.matchPart = val;
                else if (key == "mid")        { try { rule.mid = std::stoi(val); } catch(...) {} }
                else if (key == "mat_type")   rule.matType = val;
                else if (key == "thermal")    rule.thermalOverride = (val == "true" || val == "yes" || val == "1") ? 1 : 0;
            }
        }
    }
    f.close();

    if (modelFile.empty()) { console.error("[matdb] 'model' not specified"); return 1; }
    if (outputFile.empty()) { console.error("[matdb] 'output' not specified"); return 1; }

    if (!configDir.empty() && modelFile.find('/') == std::string::npos && modelFile.find('\\') == std::string::npos)
        modelFile = configDir + "/" + modelFile;

    std::string outputPrefix = outputFile;
    if (outputPrefix.size() > 2 && outputPrefix.substr(outputPrefix.size()-2) == ".k")
        outputPrefix = outputPrefix.substr(0, outputPrefix.size()-2);
    if (!configDir.empty() && outputPrefix.find('/') == std::string::npos && outputPrefix.find('\\') == std::string::npos)
        outputPrefix = configDir + "/" + outputPrefix;

    console.println("[matdb] Model: " + modelFile);
    console.println("[matdb] Output: " + outputPrefix + ".k");
    if (!op.globalMatType.empty())
        console.println("[matdb] Global mat type: " + op.globalMatType);
    else
        console.println("[matdb] Mat type: per-rule (no global default)");
    console.println("[matdb] Thermal: " + std::string(op.globalThermal ? "ON" : "OFF"));
    if (!op.rules.empty())
        console.println("[matdb] Material rules: " + std::to_string(op.rules.size()));

    ModelAssembler assembler;
    if (!assembler.loadRawOnly(modelFile)) {
        console.error(assembler.getErrorMessage());
        return 1;
    }

    if (!assembler.applyMatdb(op, configDir)) {
        console.error(assembler.getErrorMessage());
        return 1;
    }

    for (const auto& msg : assembler.infoMessages)
        console.println(msg);

    if (!assembler.writeOutput(outputPrefix)) {
        console.error(assembler.getErrorMessage());
        return 1;
    }

    console.println("[matdb] Done -> " + outputPrefix + ".k");
    return 0;
}

int runMatdbList(const std::string& dbPath, ConsoleOutput& console) {
    std::ifstream f(dbPath);
    if (!f.is_open()) {
        console.error("[matdb list] Cannot open: " + dbPath);
        return 1;
    }
    std::string content((std::istreambuf_iterator<char>(f)),
                         std::istreambuf_iterator<char>());
    f.close();

    console.println("[matdb list] Database: " + dbPath);
    console.println("");

    // Simple JSON scan: find "materials" → each MID entry
    // Look for patterns: "MID": { ... "tag": "...", "category": "...",
    //   "mat_type": "...", "cards_structural": { "TYPE1": ..., "TYPE2": ... } }
    size_t pos = content.find("\"materials\"");
    if (pos == std::string::npos) {
        console.error("[matdb list] No 'materials' section found");
        return 1;
    }

    // Scan for "N": { entries
    struct MatEntry {
        int mid;
        std::string tag, category, matType;
        std::vector<std::string> variants;
    };
    std::vector<MatEntry> entries;

    auto findStr = [&](size_t from, const std::string& key) -> std::string {
        std::string pat = "\"" + key + "\"";
        size_t p = content.find(pat, from);
        if (p == std::string::npos || p > from + 5000) return "";
        p = content.find(':', p);
        if (p == std::string::npos) return "";
        p = content.find('"', p + 1);
        if (p == std::string::npos) return "";
        size_t e = content.find('"', p + 1);
        if (e == std::string::npos) return "";
        return content.substr(p + 1, e - p - 1);
    };

    // Find each "N": { where N is a number (MID)
    size_t search = pos;
    while (true) {
        size_t q1 = content.find('"', search);
        if (q1 == std::string::npos) break;
        size_t q2 = content.find('"', q1 + 1);
        if (q2 == std::string::npos) break;
        std::string midStr = content.substr(q1 + 1, q2 - q1 - 1);
        search = q2 + 1;

        // Check if it's a number
        bool isNum = !midStr.empty();
        for (char c : midStr) if (!std::isdigit(c)) { isNum = false; break; }
        if (!isNum) continue;

        // Check next non-space is ':'
        size_t col = content.find_first_not_of(" \t\n\r", search);
        if (col == std::string::npos || content[col] != ':') continue;
        size_t brace = content.find('{', col);
        if (brace == std::string::npos) continue;

        MatEntry e;
        e.mid = std::stoi(midStr);
        e.tag = findStr(brace, "tag");
        e.category = findStr(brace, "category");
        e.matType = findStr(brace, "mat_type");

        // Find cards_structural keys
        size_t cs = content.find("\"cards_structural\"", brace);
        if (cs != std::string::npos && cs < brace + 5000) {
            size_t cb = content.find('{', cs);
            size_t ce = content.find('}', cb);
            if (cb != std::string::npos && ce != std::string::npos) {
                std::string block = content.substr(cb, ce - cb);
                size_t vs = 0;
                while (true) {
                    size_t vq1 = block.find('"', vs);
                    if (vq1 == std::string::npos) break;
                    size_t vq2 = block.find('"', vq1 + 1);
                    if (vq2 == std::string::npos) break;
                    std::string vname = block.substr(vq1 + 1, vq2 - vq1 - 1);
                    vs = vq2 + 1;
                    // Check it's a key (followed by :)
                    size_t vc = block.find_first_not_of(" \t", vs);
                    if (vc < block.size() && block[vc] == ':') {
                        e.variants.push_back(vname);
                        // Skip the value (find next key)
                        vs = block.find('"', vc);
                        if (vs == std::string::npos) break;
                    }
                }
            }
        }

        if (e.mid > 0) entries.push_back(e);
        search = brace + 1;
    }

    // Sort and print
    std::sort(entries.begin(), entries.end(),
              [](const MatEntry& a, const MatEntry& b) { return a.mid < b.mid; });

    char buf[256];
    console.println("  MID  Tag                          Category    Primary              Variants");
    console.println("  ---  ---------------------------  ----------  -------------------  --------");
    for (auto& e : entries) {
        std::string vars;
        for (auto& v : e.variants) {
            if (!vars.empty()) vars += ", ";
            vars += v;
        }
        snprintf(buf, sizeof(buf), "  %3d  %-28s %-11s %-20s %s",
                 e.mid, e.tag.c_str(), e.category.c_str(), e.matType.c_str(), vars.c_str());
        console.println(buf);
    }
    console.println("");
    snprintf(buf, sizeof(buf), "  Total: %d materials", (int)entries.size());
    console.println(buf);
    return 0;
}
