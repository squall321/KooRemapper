#include "matdb.h"
#include "cli/ConsoleOutput.h"
#include "assembly/AssemblyConfig.h"
#include "assembly/ModelAssembler.h"

#include <string>
#include <fstream>
#include <cctype>

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
                    if      (rk == "match")    rule.match = rv;
                    else if (rk == "mid")      { try { rule.mid = std::stoi(rv); } catch(...) {} }
                    else if (rk == "mat_type") rule.matType = rv;
                    else if (rk == "thermal")  rule.thermalOverride = (rv == "true" || rv == "yes" || rv == "1") ? 1 : 0;
                }
            } else if (inMaterialItem && indent > materialItemIndent) {
                auto& rule = op.rules.back();
                if      (key == "match")    rule.match = val;
                else if (key == "mid")      { try { rule.mid = std::stoi(val); } catch(...) {} }
                else if (key == "mat_type") rule.matType = val;
                else if (key == "thermal")  rule.thermalOverride = (val == "true" || val == "yes" || val == "1") ? 1 : 0;
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
    console.println("[matdb] Mat type: " + op.globalMatType);
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
