#include "load_boundary.h"
#include "assembly/ModelAssembler.h"
#include "assembly/AssemblyConfig.h"
#include "cli/ConsoleOutput.h"
#include <fstream>
#include <sstream>
#include <string>
#include <vector>

using namespace KooRemapper;

int runLoad(const std::string& yamlFile, ConsoleOutput& console) {

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
    LoadOperation loadOp;
    bool inLoadsList = false;
    int loadsListIndent = 0;
    bool inLoadItem = false;
    int loadItemIndent = 0;
    bool inCurveList = false;
    int curveListIndent = 0;

    std::string ln;
    while (std::getline(f, ln)) {
        if (!ln.empty() && ln.back()=='\r') ln.pop_back();
        int indent = countIndent(ln);
        std::string tr = trim(ln);
        if (tr.empty() || tr[0]=='#') continue;

        // Exit loads list
        if (inLoadsList && indent <= loadsListIndent && tr.substr(0,2) != "- ") {
            inLoadsList = false;
            inLoadItem = false;
            inCurveList = false;
        }

        // Exit curve list
        if (inCurveList && indent <= curveListIndent && tr.substr(0,2) != "- ") {
            inCurveList = false;
        }

        // Curve points: - [0.0, 1.0]
        if (inCurveList && tr.substr(0,2) == "- ") {
            std::string rest = trim(tr.substr(2));
            if (rest.front() == '[' && rest.back() == ']') {
                rest = rest.substr(1, rest.size()-2);
                size_t comma = rest.find(',');
                if (comma != std::string::npos) {
                    LoadCurvePoint pt;
                    try {
                        pt.time = std::stod(trim(rest.substr(0, comma)));
                        pt.value = std::stod(trim(rest.substr(comma+1)));
                        loadOp.loads.back().curve.push_back(pt);
                    } catch(...) {}
                }
            }
            continue;
        }

        size_t cp = tr.find(':');
        if (cp == std::string::npos) continue;
        std::string key = trim(tr.substr(0, cp));
        std::string val = stripQuotes(trim(tr.substr(cp+1)));

        if (!inLoadsList) {
            if      (key == "model")  modelFile = val;
            else if (key == "output") outputFile = val;
            else if (key == "loads") {
                inLoadsList = true;
                loadsListIndent = indent;
            }
            continue;
        }

        // Load list item start
        if (inLoadsList && tr.substr(0,2) == "- " && indent > loadsListIndent) {
            loadOp.loads.push_back({});
            inLoadItem = true;
            inCurveList = false;
            loadItemIndent = indent;
            std::string rest = trim(tr.substr(2));
            size_t rcp = rest.find(':');
            if (rcp != std::string::npos) {
                std::string rk = trim(rest.substr(0, rcp));
                std::string rv = stripQuotes(trim(rest.substr(rcp+1)));
                auto& lcase = loadOp.loads.back();
                if      (rk == "part") {
                    try { lcase.pid = std::stoi(rv); } catch(...) { lcase.partName = rv; }
                }
                else if (rk == "mode")       lcase.mode = rv;
                else if (rk == "value")      { try { lcase.value = std::stod(rv); } catch(...) {} }
                else if (rk == "select")     lcase.select = rv;
                else if (rk == "angle")      { try { lcase.angle = std::stod(rv); } catch(...) {} }
                else if (rk == "set_id")     { try { lcase.setId = std::stoi(rv); } catch(...) {} }
                else if (rk == "contact_id") { try { lcase.contactId = std::stoi(rv); } catch(...) {} }
            }
            continue;
        }

        // Sub-keys of current load item
        if (inLoadItem && indent > loadItemIndent) {
            auto& lcase = loadOp.loads.back();

            if (key == "curve") {
                inCurveList = true;
                curveListIndent = indent;
                continue;
            }

            if (key == "direction") {
                if (val.front() == '[' && val.back() == ']') {
                    std::string inner = val.substr(1, val.size()-2);
                    std::istringstream iss(inner);
                    std::string tok;
                    int di = 0;
                    while (std::getline(iss, tok, ',') && di < 3) {
                        try { lcase.direction[di] = std::stod(trim(tok)); } catch(...) {}
                        di++;
                    }
                }
                continue;
            }

            if      (key == "part") {
                try { lcase.pid = std::stoi(val); } catch(...) { lcase.partName = val; }
            }
            else if (key == "mode")       lcase.mode = val;
            else if (key == "value")      { try { lcase.value = std::stod(val); } catch(...) {} }
            else if (key == "select")     lcase.select = val;
            else if (key == "angle")      { try { lcase.angle = std::stod(val); } catch(...) {} }
            else if (key == "set_id")     { try { lcase.setId = std::stoi(val); } catch(...) {} }
            else if (key == "contact_id") { try { lcase.contactId = std::stoi(val); } catch(...) {} }
        }
    }
    f.close();

    if (modelFile.empty()) { console.error("[load] 'model' not specified"); return 1; }
    if (outputFile.empty()) { console.error("[load] 'output' not specified"); return 1; }
    if (loadOp.loads.empty()) { console.error("[load] 'loads' list is empty"); return 1; }

    if (!configDir.empty() && modelFile.find('/') == std::string::npos && modelFile.find('\\') == std::string::npos)
        modelFile = configDir + "/" + modelFile;

    std::string outputPrefix = outputFile;
    if (outputPrefix.size() > 2 && outputPrefix.substr(outputPrefix.size()-2) == ".k")
        outputPrefix = outputPrefix.substr(0, outputPrefix.size()-2);
    if (!configDir.empty() && outputPrefix.find('/') == std::string::npos && outputPrefix.find('\\') == std::string::npos)
        outputPrefix = configDir + "/" + outputPrefix;

    console.println("[load] Model: " + modelFile);
    console.println("[load] Output: " + outputPrefix + ".k");
    console.println("[load] Load cases: " + std::to_string(loadOp.loads.size()));

    ModelAssembler assembler;
    if (!assembler.loadBaseModel(modelFile)) {
        console.error(assembler.getErrorMessage());
        return 1;
    }

    if (!assembler.applyLoad(loadOp)) {
        console.error(assembler.getErrorMessage());
        return 1;
    }

    for (const auto& msg : assembler.infoMessages)
        console.println(msg);

    if (!assembler.writeOutput(outputPrefix)) {
        console.error(assembler.getErrorMessage());
        return 1;
    }

    console.println("[load] Done -> " + outputPrefix + ".k");
    return 0;
}

// Standalone boundary command
int runBoundary(const std::string& yamlFile, ConsoleOutput& console) {

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
    BoundaryOperation boundaryOp;
    bool inBoundariesList = false;
    int boundariesListIndent = 0;
    bool inBoundaryItem = false;

    std::string ln;
    while (std::getline(f, ln)) {
        if (!ln.empty() && ln.back()=='\r') ln.pop_back();
        int indent = countIndent(ln);
        std::string tr = trim(ln);
        if (tr.empty() || tr[0]=='#') continue;

        // Exit boundaries list
        if (inBoundariesList && indent <= boundariesListIndent && tr.substr(0,2) != "- ") {
            inBoundariesList = false;
            inBoundaryItem = false;
        }

        size_t cp = tr.find(':');
        if (cp == std::string::npos) continue;
        std::string key = trim(tr.substr(0, cp));
        std::string val = stripQuotes(trim(tr.substr(cp+1)));

        if (!inBoundariesList) {
            if      (key == "model")  modelFile = val;
            else if (key == "output") outputFile = val;
            else if (key == "boundaries") {
                inBoundariesList = true;
                boundariesListIndent = indent;
            }
            continue;
        }

        // Boundary list item start
        if (inBoundariesList && tr.substr(0,2) == "- " && indent > boundariesListIndent) {
            boundaryOp.boundaries.push_back({});
            inBoundaryItem = true;
            std::string rest = trim(tr.substr(2));
            size_t rcp = rest.find(':');
            if (rcp != std::string::npos) {
                std::string rk = trim(rest.substr(0, rcp));
                std::string rv = stripQuotes(trim(rest.substr(rcp+1)));
                auto& bc = boundaryOp.boundaries.back();
                if (rk == "part") {
                    try { bc.pid = std::stoi(rv); } catch(...) { bc.partName = rv; }
                } else if (rk == "dof") bc.dof = rv;
                else if (rk == "select") bc.select = rv;
            }
            continue;
        }

        // Sub-keys of boundary item
        if (inBoundaryItem && !boundaryOp.boundaries.empty()) {
            auto& bc = boundaryOp.boundaries.back();
            if (key == "part") {
                try { bc.pid = std::stoi(val); } catch(...) { bc.partName = val; }
            } else if (key == "dof") bc.dof = val;
            else if (key == "select") bc.select = val;
            else if (key == "angle") { try { bc.angle = std::stod(val); } catch(...) {} }
            else if (key == "set_id") { try { bc.setId = std::stoi(val); } catch(...) {} }
            else if (key == "dofx") { try { bc.dofx = std::stoi(val); } catch(...) {} }
            else if (key == "dofy") { try { bc.dofy = std::stoi(val); } catch(...) {} }
            else if (key == "dofz") { try { bc.dofz = std::stoi(val); } catch(...) {} }
            else if (key == "dofrx") { try { bc.dofrx = std::stoi(val); } catch(...) {} }
            else if (key == "dofry") { try { bc.dofry = std::stoi(val); } catch(...) {} }
            else if (key == "dofrz") { try { bc.dofrz = std::stoi(val); } catch(...) {} }
            else if (key == "direction" && !val.empty() && val.front() == '[' && val.back() == ']') {
                std::string inner = val.substr(1, val.size()-2);
                std::istringstream iss(inner);
                std::string tok;
                int di = 0;
                while (std::getline(iss, tok, ',') && di < 3) {
                    try { bc.direction[di] = std::stod(trim(tok)); } catch(...) {}
                    di++;
                }
            }
            continue;
        }
    }
    f.close();

    if (modelFile.empty()) { console.error("model not specified"); return 1; }
    if (outputFile.empty()) outputFile = modelFile;

    // Resolve paths
    if (!configDir.empty()) {
        auto hasDir = [](const std::string& p) {
            return p.find('/') != std::string::npos || p.find('\\') != std::string::npos;
        };
        if (!hasDir(modelFile))  modelFile  = configDir + "/" + modelFile;
        if (!hasDir(outputFile)) outputFile = configDir + "/" + outputFile;
    }

    std::string outputPrefix = outputFile;
    if (outputPrefix.size() >= 2 && outputPrefix.substr(outputPrefix.size()-2) == ".k")
        outputPrefix = outputPrefix.substr(0, outputPrefix.size()-2);

    console.println("[boundary] Model: " + modelFile);
    console.println("[boundary] Output: " + outputPrefix + ".k");
    console.println("[boundary] Boundary cases: " + std::to_string(boundaryOp.boundaries.size()));

    ModelAssembler assembler;
    if (!assembler.loadBaseModel(modelFile)) {
        console.error(assembler.getErrorMessage());
        return 1;
    }

    if (!assembler.applyBoundary(boundaryOp)) {
        console.error(assembler.getErrorMessage());
        return 1;
    }

    for (const auto& msg : assembler.infoMessages)
        console.println(msg);

    if (!assembler.writeOutput(outputPrefix)) {
        console.error(assembler.getErrorMessage());
        return 1;
    }

    console.println("[boundary] Done -> " + outputPrefix + ".k");
    return 0;
}

// ── Standalone RBE command ──────────────────────────────────────────────────
int runRbe(const std::string& yamlFile, ConsoleOutput& console) {

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
    RbeOperation rbeOp;
    bool inRbeList = false;
    int rbeListIndent = 0;
    bool inRbeItem = false;

    std::string ln;
    while (std::getline(f, ln)) {
        if (!ln.empty() && ln.back()=='\r') ln.pop_back();
        int indent = countIndent(ln);
        std::string tr = trim(ln);
        if (tr.empty() || tr[0]=='#') continue;

        // Exit rbe list
        if (inRbeList && indent <= rbeListIndent && tr.substr(0,2) != "- ") {
            inRbeList = false;
            inRbeItem = false;
        }

        size_t cp = tr.find(':');
        if (cp == std::string::npos) continue;
        std::string key = trim(tr.substr(0, cp));
        std::string val = stripQuotes(trim(tr.substr(cp+1)));

        if (!inRbeList) {
            if      (key == "model")  modelFile = val;
            else if (key == "output") outputFile = val;
            else if (key == "rbe") {
                inRbeList = true;
                rbeListIndent = indent;
            }
            continue;
        }

        // RBE list item start
        if (inRbeList && tr.substr(0,2) == "- " && indent > rbeListIndent) {
            rbeOp.constraints.push_back({});
            inRbeItem = true;
            std::string rest = trim(tr.substr(2));
            size_t rcp = rest.find(':');
            if (rcp != std::string::npos) {
                std::string rk = trim(rest.substr(0, rcp));
                std::string rv = stripQuotes(trim(rest.substr(rcp+1)));
                auto& rc = rbeOp.constraints.back();
                if (rk == "part") {
                    try { rc.pid = std::stoi(rv); } catch(...) { rc.partName = rv; }
                } else if (rk == "select") rc.select = rv;
                else if (rk == "type") rc.type = rv;
                else if (rk == "mode") rc.mode = rv;
            }
            continue;
        }

        // Sub-keys of rbe item
        if (inRbeItem && !rbeOp.constraints.empty()) {
            auto& rc = rbeOp.constraints.back();
            if (key == "part") {
                try { rc.pid = std::stoi(val); } catch(...) { rc.partName = val; }
            } else if (key == "select") rc.select = val;
            else if (key == "type") rc.type = val;
            else if (key == "mode") rc.mode = val;
            else if (key == "angle") { try { rc.angle = std::stod(val); } catch(...) {} }
            else if (key == "direction" && !val.empty() && val.front() == '[' && val.back() == ']') {
                std::string inner = val.substr(1, val.size()-2);
                std::istringstream iss(inner);
                std::string tok;
                int di = 0;
                while (std::getline(iss, tok, ',') && di < 3) {
                    try { rc.direction[di] = std::stod(trim(tok)); } catch(...) {}
                    di++;
                }
            }
            continue;
        }
    }
    f.close();

    if (modelFile.empty()) { console.error("model not specified"); return 1; }
    if (outputFile.empty()) outputFile = modelFile;

    // Resolve paths
    if (!configDir.empty()) {
        auto hasDir = [](const std::string& p) {
            return p.find('/') != std::string::npos || p.find('\\') != std::string::npos;
        };
        if (!hasDir(modelFile))  modelFile  = configDir + "/" + modelFile;
        if (!hasDir(outputFile)) outputFile = configDir + "/" + outputFile;
    }

    std::string outputPrefix = outputFile;
    if (outputPrefix.size() >= 2 && outputPrefix.substr(outputPrefix.size()-2) == ".k")
        outputPrefix = outputPrefix.substr(0, outputPrefix.size()-2);

    console.println("[rbe] Model: " + modelFile);
    console.println("[rbe] Output: " + outputPrefix + ".k");
    console.println("[rbe] Constraints: " + std::to_string(rbeOp.constraints.size()));

    ModelAssembler assembler;
    if (!assembler.loadBaseModel(modelFile)) {
        console.error(assembler.getErrorMessage());
        return 1;
    }

    if (!assembler.applyRbe(rbeOp)) {
        console.error(assembler.getErrorMessage());
        return 1;
    }

    for (const auto& msg : assembler.infoMessages)
        console.println(msg);

    if (!assembler.writeOutput(outputPrefix)) {
        console.error(assembler.getErrorMessage());
        return 1;
    }

    console.println("[rbe] Done -> " + outputPrefix + ".k");
    return 0;
}
