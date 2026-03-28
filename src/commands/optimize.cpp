#include "optimize.h"
#include "cli/ConsoleOutput.h"
#include <fstream>
#include <sstream>
#include <string>
#include <vector>

using namespace KooRemapper;

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
