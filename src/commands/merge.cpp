#include "merge.h"
#include "cli/ConsoleOutput.h"

#include <string>
#include <vector>
#include <map>
#include <set>
#include <array>
#include <algorithm>
#include <fstream>
#include <sstream>
#include <cmath>
#include <cstdio>
#include <functional>

// Knowledge graph (lat.md):
//   @lat: [[modules/commands]]

using KooRemapper::ConsoleOutput;

// ─────────────────────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────────────────────

static std::string mg_trim(const std::string& s) {
    size_t a = s.find_first_not_of(" \t\r\n");
    if (a == std::string::npos) return "";
    size_t b = s.find_last_not_of(" \t\r\n");
    return s.substr(a, b - a + 1);
}

static std::string mg_stripQuotes(const std::string& s) {
    if (s.size() >= 2 &&
        ((s.front() == '"' && s.back() == '"') ||
         (s.front() == '\'' && s.back() == '\'')))
        return s.substr(1, s.size() - 2);
    return s;
}

static std::string mg_toUpper(const std::string& s) {
    std::string r = s;
    for (auto& c : r) c = (char)toupper((unsigned char)c);
    return r;
}

static double mg_toDouble(const std::string& s, double def = 0.0) {
    try { return std::stod(s); } catch (...) { return def; }
}

static int mg_toInt(const std::string& s, int def = 0) {
    try { return std::stoi(s); } catch (...) { return def; }
}

// Tokenize by whitespace
static std::vector<std::string> mg_tokenWS(const std::string& line) {
    std::vector<std::string> toks;
    std::istringstream iss(line);
    std::string tok;
    while (iss >> tok) toks.push_back(tok);
    return toks;
}

// 10-char fixed-width tokenizer for MAT card data lines
static std::vector<std::string> mg_tok10(const std::string& s) {
    std::vector<std::string> t;
    for (size_t i = 0; i < s.size(); i += 10) {
        size_t len = std::min((size_t)10, s.size() - i);
        std::string f = s.substr(i, len);
        size_t a = f.find_first_not_of(" \t");
        if (a == std::string::npos) { t.push_back(""); continue; }
        size_t b = f.find_last_not_of(" \t");
        t.push_back(f.substr(a, b - a + 1));
    }
    return t;
}

// ─────────────────────────────────────────────────────────────
// Data structures
// ─────────────────────────────────────────────────────────────

struct mg_Vec3 { double x, y, z; };

struct mg_Elem {
    int id, pid;
    int nid[8];
};

struct mg_PartInfo {
    int secid, mid;
    std::string title;
};

struct mg_MatProps {
    std::string type;       // "ELASTIC", "024", "VE076", "RIGID", etc.
    double E = 0, nu = 0, rho = 0;
    double cte = 0;
    bool hasCte = false;
};

struct mg_MergeGroup {
    std::vector<int> pids;
    std::string name;
    int layers = 1;
};

struct mg_Config {
    std::string modelPath, outputPath;
    int dir = 2;            // 0=x, 1=y, 2=z (default)
    int method = 2;         // 0=voigt, 1=reuss, 2=vrh
    std::vector<mg_MergeGroup> groups;
};

// ─────────────────────────────────────────────────────────────
// YAML config parser
// ─────────────────────────────────────────────────────────────

static mg_Config mg_parseConfig(const std::string& yamlFile, ConsoleOutput& console) {
    mg_Config cfg;
    std::ifstream yf(yamlFile);
    if (!yf.is_open()) {
        console.error("Cannot open config: " + yamlFile);
        return cfg;
    }

    std::string configDir;
    {
        size_t sep = yamlFile.find_last_of("/\\");
        if (sep != std::string::npos) configDir = yamlFile.substr(0, sep + 1);
    }

    bool inMergeList = false;
    bool inPidsList = false;
    int mergeListIndent = 0;
    mg_MergeGroup curGroup;

    std::string line;
    while (std::getline(yf, line)) {
        std::string trimmed = mg_trim(line);
        if (trimmed.empty() || trimmed[0] == '#') continue;

        int indent = 0;
        while (indent < (int)line.size() && line[indent] == ' ') ++indent;

        // PID list items
        if (inPidsList && trimmed[0] == '-' && indent > mergeListIndent + 2) {
            std::string val = mg_trim(trimmed.substr(1));
            int pid = mg_toInt(val);
            if (pid > 0) curGroup.pids.push_back(pid);
            continue;
        } else if (inPidsList && !(trimmed[0] == '-' && indent > mergeListIndent + 2)) {
            inPidsList = false;
        }

        // Merge list items
        if (inMergeList) {
            if (indent <= mergeListIndent && trimmed[0] != '-') {
                // End of merge list — save last group
                if (!curGroup.pids.empty()) cfg.groups.push_back(curGroup);
                inMergeList = false;
            } else if (trimmed.size() > 1 && trimmed[0] == '-' && indent >= mergeListIndent) {
                // New merge item or continuation
                // Check if "- pids:" or "- name:" or sub-key
                std::string content = mg_trim(trimmed.substr(1));

                // Start of new group item?
                size_t colon = content.find(':');
                if (colon != std::string::npos) {
                    std::string k = mg_trim(content.substr(0, colon));
                    std::string v = mg_trim(content.substr(colon + 1));
                    v = mg_stripQuotes(v);

                    if (k == "pids") {
                        // Save previous group
                        if (!curGroup.pids.empty()) cfg.groups.push_back(curGroup);
                        curGroup = mg_MergeGroup{};

                        // Inline array: [1, 2, 3]
                        if (!v.empty() && v[0] == '[') {
                            std::string inner = v.substr(1);
                            size_t rb = inner.rfind(']');
                            if (rb != std::string::npos) inner = inner.substr(0, rb);
                            std::istringstream ss(inner);
                            std::string tok;
                            while (std::getline(ss, tok, ',')) {
                                int pid = mg_toInt(mg_trim(tok));
                                if (pid > 0) curGroup.pids.push_back(pid);
                            }
                        } else {
                            inPidsList = true;
                        }
                    } else if (k == "name") {
                        curGroup.name = v;
                    } else if (k == "layers") {
                        curGroup.layers = std::max(1, mg_toInt(v));
                    }
                }
                continue;
            } else if (indent > mergeListIndent) {
                // Sub-key of current merge item
                size_t colon = trimmed.find(':');
                if (colon != std::string::npos) {
                    std::string k = mg_trim(trimmed.substr(0, colon));
                    std::string v = mg_trim(trimmed.substr(colon + 1));
                    v = mg_stripQuotes(v);
                    if (k == "pids") {
                        if (!v.empty() && v[0] == '[') {
                            std::string inner = v.substr(1);
                            size_t rb = inner.rfind(']');
                            if (rb != std::string::npos) inner = inner.substr(0, rb);
                            std::istringstream ss(inner);
                            std::string tok;
                            while (std::getline(ss, tok, ',')) {
                                int pid = mg_toInt(mg_trim(tok));
                                if (pid > 0) curGroup.pids.push_back(pid);
                            }
                        } else {
                            inPidsList = true;
                        }
                    } else if (k == "name") {
                        curGroup.name = v;
                    } else if (k == "layers") {
                        curGroup.layers = std::max(1, mg_toInt(v));
                    }
                }
                continue;
            }
        }

        // Top-level keys
        size_t colon = trimmed.find(':');
        if (colon == std::string::npos) continue;
        std::string key = mg_trim(trimmed.substr(0, colon));
        std::string val = mg_trim(trimmed.substr(colon + 1));
        val = mg_stripQuotes(val);

        if (key == "model" || key == "input") {
            cfg.modelPath = val;
        } else if (key == "output") {
            cfg.outputPath = val;
        } else if (key == "direction") {
            std::string d = mg_toUpper(val);
            if (d == "X") cfg.dir = 0;
            else if (d == "Y") cfg.dir = 1;
            else cfg.dir = 2;
        } else if (key == "method") {
            std::string m = mg_toUpper(val);
            if (m == "VOIGT") cfg.method = 0;
            else if (m == "REUSS") cfg.method = 1;
            else cfg.method = 2; // vrh
        } else if (key == "merge") {
            inMergeList = true;
            mergeListIndent = indent;
            curGroup = mg_MergeGroup{};
        }
    }

    // Save last group
    if (inMergeList && !curGroup.pids.empty())
        cfg.groups.push_back(curGroup);

    // Resolve paths
    auto resolve = [&](std::string& p) {
        if (p.empty()) return;
        if (p.size() >= 2 && (p[1] == ':' || p[0] == '/' || p[0] == '\\')) return;
        p = configDir + p;
    };
    resolve(cfg.modelPath);
    resolve(cfg.outputPath);

    if (cfg.outputPath.empty()) {
        size_t dot = cfg.modelPath.rfind('.');
        if (dot != std::string::npos)
            cfg.outputPath = cfg.modelPath.substr(0, dot) + "_merged" + cfg.modelPath.substr(dot);
        else
            cfg.outputPath = cfg.modelPath + "_merged";
    }

    return cfg;
}

// ─────────────────────────────────────────────────────────────
// K-file parser: extract nodes, elements, parts, materials, CTE
// ─────────────────────────────────────────────────────────────

struct mg_KModel {
    std::vector<std::string> rawLines;
    std::map<int, mg_Vec3> nodes;
    std::map<int, mg_Elem> elems;      // solid elements only
    std::map<int, mg_PartInfo> parts;   // pid → {secid, mid, title}
    std::map<int, mg_MatProps> mats;    // mid → material props
    int maxElemId = 0, maxPartId = 0, maxMatId = 0, maxSecId = 0;
};

static void mg_parseKFile(const std::string& path, mg_KModel& mdl, ConsoleOutput& console) {
    std::ifstream inf(path);
    if (!inf.is_open()) {
        console.error("Cannot open model: " + path);
        return;
    }

    std::string line;
    std::string curKeyword;
    bool inNode = false, inElemSolid = false, inPart = false;
    bool partTitleRead = false;
    int partPid = 0;
    std::string partTitle;

    // Material parsing state
    bool inMat = false;
    std::string matType;
    int matMid = 0;
    int matCardNum = 0;
    bool matTitleLine = false; // _TITLE suffix means next line is title

    // VE076 Prony series
    double veBulk = 0;
    double veRho = 0;
    std::vector<double> veGi, veBetai;

    // CTE
    bool inThermalExp = false;
    int thermalExpMid = 0;
    int thermalExpCard = 0;

    // Section tracking
    bool inSection = false;
    int sectionId = 0;

    auto finishVE = [&]() {
        if (matMid > 0 && matType == "VE076") {
            // Fully relaxed: G∞ = sum of Gi where betai == 0
            double G_inf = 0;
            for (size_t i = 0; i < veGi.size(); i++) {
                if (veBetai[i] == 0.0) G_inf += veGi[i];
            }
            double K = veBulk;
            double E = 0, nu = 0;
            if (K > 0 && G_inf > 0) {
                E = 9.0 * K * G_inf / (3.0 * K + G_inf);
                nu = (3.0 * K - 2.0 * G_inf) / (2.0 * (3.0 * K + G_inf));
            }
            mdl.mats[matMid] = {"VE076", E, nu, veRho, 0, false};
            console.info("  [mat-parse] VE076 MID=" + std::to_string(matMid) +
                " BULK=" + std::to_string(K) + " G_inf=" + std::to_string(G_inf) +
                " E=" + std::to_string(E) + " nu=" + std::to_string(nu));
        }
        veGi.clear();
        veBetai.clear();
        veBulk = 0;
        veRho = 0;
    };

    while (std::getline(inf, line)) {
        mdl.rawLines.push_back(line);
        std::string trimmed = mg_trim(line);
        if (trimmed.empty()) continue;

        // Comment line
        if (trimmed[0] == '$') continue;

        // Keyword line
        if (trimmed[0] == '*') {
            // Finish previous VE material
            if (inMat && matType == "VE076") finishVE();

            std::string up = mg_toUpper(trimmed);
            inNode = inElemSolid = inPart = inMat = inThermalExp = inSection = false;

            if (up.find("*NODE") == 0 && up.find("*NODE_") == std::string::npos) {
                inNode = true;
            } else if (up.find("*ELEMENT_SOLID") == 0) {
                inElemSolid = true;
            } else if (up.find("*PART") == 0 && up.find("*PART_CONTACT") == std::string::npos) {
                inPart = true;
                partTitleRead = false;
                partPid = 0;
                partTitle.clear();
            } else if (up.find("*SECTION_SOLID") == 0) {
                inSection = true;
                sectionId = 0;
            } else if (up.find("*MAT_ELASTIC") == 0 &&
                       up.find("*MAT_ELASTIC_PLASTIC") == std::string::npos &&
                       up.find("*MAT_ELASTIC_VISCOPLASTIC") == std::string::npos) {
                // Matches *MAT_ELASTIC and *MAT_ELASTIC_TITLE but not *MAT_ELASTIC_PLASTIC_*
                inMat = true;
                matType = "ELASTIC";
                matCardNum = 0;
                matMid = 0;
                matTitleLine = (up.find("TITLE") != std::string::npos);
            } else if (up.find("*MAT_PIECEWISE_LINEAR") == 0 || up.find("*MAT_024") == 0) {
                inMat = true;
                matType = "024";
                matCardNum = 0;
                matMid = 0;
                matTitleLine = (up.find("TITLE") != std::string::npos);
            } else if (up.find("*MAT_GENERAL_VISCOELASTIC") == 0 || up.find("*MAT_076") == 0) {
                inMat = true;
                matType = "VE076";
                matCardNum = 0;
                matMid = 0;
                matTitleLine = (up.find("TITLE") != std::string::npos);
            } else if (up.find("*MAT_RIGID") == 0 || up.find("*MAT_020") == 0) {
                inMat = true;
                matType = "RIGID";
                matCardNum = 0;
                matMid = 0;
                matTitleLine = (up.find("TITLE") != std::string::npos);
            } else if (up.find("*MAT_ADD_THERMAL_EXPANSION") == 0) {
                inThermalExp = true;
                thermalExpMid = 0;
                thermalExpCard = 0;
                matTitleLine = (up.find("TITLE") != std::string::npos);
            } else if (up.find("*MAT_") == 0) {
                // Unrecognized MAT keyword — log it
                console.info("  [mat-parse] SKIP unrecognized: " + trimmed);
            }
            continue;
        }

        // *NODE data
        if (inNode) {
            auto toks = mg_tokenWS(trimmed);
            if (toks.size() >= 4) {
                int nid = mg_toInt(toks[0]);
                if (nid > 0) {
                    mdl.nodes[nid] = {mg_toDouble(toks[1]), mg_toDouble(toks[2]), mg_toDouble(toks[3])};
                }
            }
            continue;
        }

        // *ELEMENT_SOLID data
        if (inElemSolid) {
            auto toks = mg_tokenWS(trimmed);
            if (toks.size() >= 10) {
                mg_Elem e;
                e.id = mg_toInt(toks[0]);
                e.pid = mg_toInt(toks[1]);
                for (int i = 0; i < 8; i++) e.nid[i] = mg_toInt(toks[2 + i]);
                if (e.id > 0) {
                    mdl.elems[e.id] = e;
                    if (e.id > mdl.maxElemId) mdl.maxElemId = e.id;
                }
            }
            continue;
        }

        // *PART data
        if (inPart) {
            if (!partTitleRead) {
                partTitle = trimmed;
                partTitleRead = true;
                continue;
            }
            auto toks = mg_tokenWS(trimmed);
            if (toks.size() >= 3) {
                int pid = mg_toInt(toks[0]);
                int secid = mg_toInt(toks[1]);
                int mid = mg_toInt(toks[2]);
                if (pid > 0) {
                    mdl.parts[pid] = {secid, mid, partTitle};
                    if (pid > mdl.maxPartId) mdl.maxPartId = pid;
                }
            }
            inPart = false;
            continue;
        }

        // *SECTION_SOLID
        if (inSection) {
            auto toks = mg_tokenWS(trimmed);
            if (toks.size() >= 1) {
                int sid = mg_toInt(toks[0]);
                if (sid > mdl.maxSecId) mdl.maxSecId = sid;
            }
            inSection = false;
            continue;
        }

        // Material data
        if (inMat) {
            if (matTitleLine) {
                matTitleLine = false;
                continue; // skip title line
            }
            matCardNum++;
            // Use fixed-width 10-char tokenizer (handles LS-DYNA fixed format)
            auto toks = mg_tok10(line);
            if (toks.size() < 4 || (toks.size() >= 1 && toks[0].empty())) toks = mg_tokenWS(trimmed);

            if (matType == "ELASTIC" && matCardNum == 1) {
                // Card 1: MID, RO, E, PR, DA, DB
                if (toks.size() >= 4) {
                    matMid = mg_toInt(toks[0]);
                    double rho = mg_toDouble(toks[1]);
                    double E = mg_toDouble(toks[2]);
                    double pr = mg_toDouble(toks[3]);
                    console.info("  [mat-parse] ELASTIC MID=" + std::to_string(matMid) +
                        " RO=" + toks[1] + " E=" + toks[2] + " PR=" + toks[3] +
                        " (toks=" + std::to_string(toks.size()) + ")");
                    if (matMid > 0) {
                        mdl.mats[matMid] = {"ELASTIC", E, pr, rho, 0, false};
                        if (matMid > mdl.maxMatId) mdl.maxMatId = matMid;
                    }
                } else {
                    console.info("  [mat-parse] ELASTIC card1 too few tokens: " + std::to_string(toks.size()) + " raw=[" + trimmed + "]");
                }
                inMat = false;
            } else if (matType == "024" && matCardNum == 1) {
                // Card 1: MID, RO, E, PR, SIGY, ETAN, FAIL, TDEL
                if (toks.size() >= 4) {
                    matMid = mg_toInt(toks[0]);
                    double rho = mg_toDouble(toks[1]);
                    double E = mg_toDouble(toks[2]);
                    double pr = mg_toDouble(toks[3]);
                    console.info("  [mat-parse] MAT_024 MID=" + std::to_string(matMid) +
                        " RO=" + toks[1] + " E=" + toks[2] + " PR=" + toks[3]);
                    if (matMid > 0) {
                        mdl.mats[matMid] = {"024", E, pr, rho, 0, false};
                        if (matMid > mdl.maxMatId) mdl.maxMatId = matMid;
                    }
                } else {
                    console.info("  [mat-parse] MAT_024 card1 too few tokens: " + std::to_string(toks.size()) + " raw=[" + trimmed + "]");
                }
                inMat = false;
            } else if (matType == "RIGID" && matCardNum == 1) {
                if (toks.size() >= 4) {
                    matMid = mg_toInt(toks[0]);
                    double rho = mg_toDouble(toks[1]);
                    double E = mg_toDouble(toks[2]);
                    double pr = mg_toDouble(toks[3]);
                    console.info("  [mat-parse] RIGID MID=" + std::to_string(matMid) +
                        " RO=" + toks[1] + " E=" + toks[2] + " PR=" + toks[3]);
                    if (matMid > 0) {
                        mdl.mats[matMid] = {"RIGID", E, pr, rho, 0, false};
                        if (matMid > mdl.maxMatId) mdl.maxMatId = matMid;
                    }
                } else {
                    console.info("  [mat-parse] RIGID card1 too few tokens: " + std::to_string(toks.size()) + " raw=[" + trimmed + "]");
                }
                inMat = false;
            } else if (matType == "VE076") {
                if (matCardNum == 1) {
                    // Card 1: MID, RO, BULK, ...
                    if (toks.size() >= 3) {
                        matMid = mg_toInt(toks[0]);
                        veRho = mg_toDouble(toks[1]);
                        veBulk = mg_toDouble(toks[2]);
                        if (matMid > mdl.maxMatId) mdl.maxMatId = matMid;
                    }
                } else if (matCardNum == 2) {
                    // Card 2: LCID, NT, ... (skip)
                } else {
                    // Card 3+: GI, BETAI, KI, BETAKI
                    if (toks.size() >= 2) {
                        double gi = mg_toDouble(toks[0]);
                        double bi = mg_toDouble(toks[1]);
                        veGi.push_back(gi);
                        veBetai.push_back(bi);
                    }
                }
            }
            continue;
        }

        // CTE data
        if (inThermalExp) {
            if (matTitleLine) {
                matTitleLine = false;
                continue;
            }
            thermalExpCard++;
            auto toks = mg_tok10(line);
            if (toks.size() < 2 || (toks.size() >= 1 && toks[0].empty())) toks = mg_tokenWS(trimmed);
            if (thermalExpCard == 1 && toks.size() >= 2) {
                // Card 1: PID (actually MID reference), LCID, MULT
                thermalExpMid = mg_toInt(toks[0]);
            } else if (thermalExpCard == 2 && toks.size() >= 1) {
                // Card 2: ALPHA (isotropic CTE)
                double alpha = mg_toDouble(toks[0]);
                if (thermalExpMid > 0 && mdl.mats.count(thermalExpMid)) {
                    mdl.mats[thermalExpMid].cte = alpha;
                    mdl.mats[thermalExpMid].hasCte = true;
                }
                inThermalExp = false;
            }
            continue;
        }
    }

    // Finish last VE material if file ended mid-parse
    if (inMat && matType == "VE076") finishVE();

    inf.close();
}

// ─────────────────────────────────────────────────────────────
// Column detection via shared-face connectivity
// ─────────────────────────────────────────────────────────────

// Face key: sorted 4 node IDs
using FaceKey = std::array<int, 4>;

static FaceKey mg_makeFaceKey(int a, int b, int c, int d) {
    FaceKey f = {a, b, c, d};
    std::sort(f.begin(), f.end());
    return f;
}

// Get "low" and "high" face of a hex element along stacking direction
// Returns {lowFaceNodes[4], highFaceNodes[4]}
static void mg_getStackFaces(const mg_Elem& e, const std::map<int, mg_Vec3>& nodes,
                              int dir, int lowFace[4], int highFace[4]) {
    // HEX8 has 3 opposite face pairs; pick the one most aligned with stacking direction
    // Each pair: face0[i] and face1[i] are connected by an edge
    static const int facePairs[3][2][4] = {
        {{0,1,2,3}, {4,5,6,7}},   // pair A: nid[0..3] vs nid[4..7]
        {{0,1,5,4}, {3,2,6,7}},   // pair B: edges 0-3,1-2,5-6,4-7
        {{0,3,7,4}, {1,2,6,5}}    // pair C: edges 0-1,3-2,7-6,4-5
    };
    auto getCoord = [&](int nid) -> double {
        auto it = nodes.find(nid);
        if (it == nodes.end()) return 0.0;
        if (dir == 0) return it->second.x;
        if (dir == 1) return it->second.y;
        return it->second.z;
    };

    int bestPair = 0;
    double maxDiff = 0;
    for (int p = 0; p < 3; p++) {
        double avgA = 0, avgB = 0;
        for (int k = 0; k < 4; k++) {
            avgA += getCoord(e.nid[facePairs[p][0][k]]);
            avgB += getCoord(e.nid[facePairs[p][1][k]]);
        }
        double diff = std::abs(avgB - avgA);
        if (diff > maxDiff) { maxDiff = diff; bestPair = p; }
    }
    double avgA = 0, avgB = 0;
    for (int k = 0; k < 4; k++) {
        avgA += getCoord(e.nid[facePairs[bestPair][0][k]]);
        avgB += getCoord(e.nid[facePairs[bestPair][1][k]]);
    }
    if (avgA <= avgB) {
        for (int i = 0; i < 4; i++) { lowFace[i] = e.nid[facePairs[bestPair][0][i]]; highFace[i] = e.nid[facePairs[bestPair][1][i]]; }
    } else {
        for (int i = 0; i < 4; i++) { lowFace[i] = e.nid[facePairs[bestPair][1][i]]; highFace[i] = e.nid[facePairs[bestPair][0][i]]; }
    }
}

// Build columns of elements via shared faces
// Returns: list of columns, each column = sorted bottom→top list of element IDs
static std::vector<std::vector<int>> mg_buildColumns(
    const std::vector<int>& elemIds,
    const std::map<int, mg_Elem>& allElems,
    const std::map<int, mg_Vec3>& nodes,
    int dir)
{
    // Map: highFaceKey → elemId (element that has this as its high face)
    // Map: lowFaceKey  → elemId (element that has this as its low face)
    std::map<FaceKey, int> highFaceOf;  // faceKey → elem whose HIGH face is this
    std::map<FaceKey, int> lowFaceOf;   // faceKey → elem whose LOW face is this

    for (int eid : elemIds) {
        auto it = allElems.find(eid);
        if (it == allElems.end()) continue;
        const auto& e = it->second;

        int lo[4], hi[4];
        mg_getStackFaces(e, nodes, dir, lo, hi);

        FaceKey loKey = mg_makeFaceKey(lo[0], lo[1], lo[2], lo[3]);
        FaceKey hiKey = mg_makeFaceKey(hi[0], hi[1], hi[2], hi[3]);

        highFaceOf[hiKey] = eid;
        lowFaceOf[loKey] = eid;
    }

    // Find bottom elements: elements whose low face is NOT the high face of any other element
    std::set<int> elemSet(elemIds.begin(), elemIds.end());
    std::set<int> visited;
    std::vector<std::vector<int>> columns;

    for (int eid : elemIds) {
        if (visited.count(eid)) continue;

        auto it = allElems.find(eid);
        if (it == allElems.end()) continue;
        const auto& e = it->second;

        int lo[4], hi[4];
        mg_getStackFaces(e, nodes, dir, lo, hi);
        FaceKey loKey = mg_makeFaceKey(lo[0], lo[1], lo[2], lo[3]);

        // Is this element's low face the high face of another element in the set?
        auto hIt = highFaceOf.find(loKey);
        if (hIt != highFaceOf.end() && elemSet.count(hIt->second)) {
            continue; // Not a bottom element
        }

        // This is a bottom element — trace upward
        std::vector<int> column;
        int curEid = eid;
        while (curEid > 0 && !visited.count(curEid)) {
            visited.insert(curEid);
            column.push_back(curEid);

            // Find element above: whose low face == this element's high face
            auto cIt = allElems.find(curEid);
            if (cIt == allElems.end()) break;

            int clo[4], chi[4];
            mg_getStackFaces(cIt->second, nodes, dir, clo, chi);
            FaceKey chiKey = mg_makeFaceKey(chi[0], chi[1], chi[2], chi[3]);

            auto lIt = lowFaceOf.find(chiKey);
            if (lIt != lowFaceOf.end() && elemSet.count(lIt->second) && !visited.count(lIt->second)) {
                curEid = lIt->second;
            } else {
                curEid = 0;
            }
        }

        if (!column.empty()) columns.push_back(column);
    }

    return columns;
}

// ─────────────────────────────────────────────────────────────
// Material homogenization
// ─────────────────────────────────────────────────────────────

static mg_MatProps mg_homogenize(
    const std::vector<std::pair<mg_MatProps, double>>& matsWithFrac,
    int method, ConsoleOutput& console)
{
    // matsWithFrac: list of {material, volume_fraction}
    mg_MatProps result;
    result.type = "ELASTIC";

    double E_voigt = 0, inv_E_reuss = 0;
    double nu_voigt = 0;
    double rho_mix = 0;
    double cte_mix = 0;
    bool anyCte = false;
    double totalFrac = 0;

    for (auto& [m, vf] : matsWithFrac) {
        if (m.E <= 0) continue;
        totalFrac += vf;
        E_voigt += vf * m.E;
        inv_E_reuss += vf / m.E;
        nu_voigt += vf * m.nu;
        rho_mix += vf * m.rho;
        if (m.hasCte) {
            cte_mix += vf * m.cte;
            anyCte = true;
        }
    }

    if (totalFrac <= 0) return result;

    double E_reuss = (inv_E_reuss > 0) ? (1.0 / inv_E_reuss) : 0;

    if (method == 0) {
        result.E = E_voigt;
    } else if (method == 1) {
        result.E = E_reuss;
    } else {
        result.E = 0.5 * (E_voigt + E_reuss); // VRH
    }

    result.nu = nu_voigt;
    result.rho = rho_mix;
    result.cte = cte_mix;
    result.hasCte = anyCte;

    return result;
}

// ─────────────────────────────────────────────────────────────
// Main: runMerge
// ─────────────────────────────────────────────────────────────

int runMerge(const std::string& yamlFile, ConsoleOutput& console) {
    mg_Config cfg = mg_parseConfig(yamlFile, console);
    if (cfg.modelPath.empty() || cfg.groups.empty()) {
        console.error("Invalid config: model and merge groups required");
        return 1;
    }

    const char* dirName[] = {"X", "Y", "Z"};
    const char* methName[] = {"Voigt", "Reuss", "VRH"};

    console.info("Model: " + cfg.modelPath);
    console.info("Direction: " + std::string(dirName[cfg.dir]));
    console.info("Method: " + std::string(methName[cfg.method]));
    console.info("Merge groups: " + std::to_string(cfg.groups.size()));

    // --- Phase 1: Parse K-file ---
    mg_KModel mdl;
    mg_parseKFile(cfg.modelPath, mdl, console);

    console.info("Nodes: " + std::to_string(mdl.nodes.size()) +
                 ", Elements: " + std::to_string(mdl.elems.size()) +
                 ", Parts: " + std::to_string(mdl.parts.size()) +
                 ", Materials: " + std::to_string(mdl.mats.size()));

    // --- Phase 2: Process each merge group ---
    int newPid = mdl.maxPartId + 1;
    int newMid = mdl.maxMatId + 1;
    int newSecId = mdl.maxSecId + 1;
    int newEid = mdl.maxElemId + 1;

    // Collect all elements to remove and new elements to add
    std::set<int> removeElemIds;
    std::set<int> mergePidSet; // All PIDs being merged (for filtering ELEMENT_SOLID)

    struct NewElem { int id, pid; int nid[8]; };
    std::vector<NewElem> newElems;

    struct GroupResult {
        std::string name;
        int pid, mid, secid;
        mg_MatProps matProps;
        int nColumns;
        int nOrigElems;
    };
    std::vector<GroupResult> results;

    for (size_t gi = 0; gi < cfg.groups.size(); gi++) {
        const auto& grp = cfg.groups[gi];
        std::string gname = grp.name.empty() ?
            ("Merged_Group_" + std::to_string(gi + 1)) : grp.name;

        console.info("\n--- Group: " + gname + " ---");

        // Collect elements for this group
        std::set<int> grpPids(grp.pids.begin(), grp.pids.end());
        std::vector<int> grpElemIds;
        for (auto& [eid, e] : mdl.elems) {
            if (grpPids.count(e.pid)) grpElemIds.push_back(eid);
        }

        if (grpElemIds.empty()) {
            console.error("  No elements found for PIDs");
            continue;
        }
        console.info("  Elements: " + std::to_string(grpElemIds.size()));

        for (int pid : grp.pids) mergePidSet.insert(pid);

        // Build columns
        auto columns = mg_buildColumns(grpElemIds, mdl.elems, mdl.nodes, cfg.dir);
        console.info("  Columns detected: " + std::to_string(columns.size()));

        if (columns.empty()) {
            console.error("  No columns detected — skipping");
            continue;
        }

        // Compute volume fractions per material
        std::map<int, int> midCount; // mid → number of elements
        int totalInGroup = 0;
        for (auto& col : columns) {
            for (int eid : col) {
                auto it = mdl.elems.find(eid);
                if (it == mdl.elems.end()) continue;
                int pid = it->second.pid;
                auto pit = mdl.parts.find(pid);
                if (pit == mdl.parts.end()) continue;
                midCount[pit->second.mid]++;
                totalInGroup++;
            }
        }

        std::vector<std::pair<mg_MatProps, double>> matsWithFrac;
        for (auto& [mid, cnt] : midCount) {
            double vf = (double)cnt / totalInGroup;
            auto mit = mdl.mats.find(mid);
            if (mit == mdl.mats.end()) {
                console.error("  MID " + std::to_string(mid) + " not found in material DB");
                continue;
            }
            matsWithFrac.push_back({mit->second, vf});
            console.info("  MID " + std::to_string(mid) + " (" + mit->second.type +
                         "): E=" + std::to_string(mit->second.E) +
                         " nu=" + std::to_string(mit->second.nu) +
                         " rho=" + std::to_string(mit->second.rho) +
                         " vf=" + std::to_string(vf));
        }

        // Homogenize
        mg_MatProps hom = mg_homogenize(matsWithFrac, cfg.method, console);
        console.info("  Homogenized: E=" + std::to_string(hom.E) +
                     " nu=" + std::to_string(hom.nu) +
                     " rho=" + std::to_string(hom.rho));
        if (hom.hasCte)
            console.info("  CTE=" + std::to_string(hom.cte));

        // Create merged elements
        int grpPidNew = newPid++;
        int grpMidNew = newMid++;
        int grpSecNew = newSecId++;

        int nLayers = std::max(1, grp.layers);
        for (auto& col : columns) {
            // Mark all elements in column for removal
            for (int eid : col) removeElemIds.insert(eid);

            if (col.empty()) continue;

            int colSize = (int)col.size();
            int actualLayers = std::min(nLayers, colSize);

            for (int L = 0; L < actualLayers; L++) {
                int start = (int)((long long)L * colSize / actualLayers);
                int end   = (int)((long long)(L+1) * colSize / actualLayers);
                if (start >= end) continue;

                auto botIt = mdl.elems.find(col[start]);
                auto topIt = mdl.elems.find(col[end - 1]);
                if (botIt == mdl.elems.end() || topIt == mdl.elems.end()) continue;

                int botLo[4], botHi[4], topLo[4], topHi[4];
                mg_getStackFaces(botIt->second, mdl.nodes, cfg.dir, botLo, botHi);
                mg_getStackFaces(topIt->second, mdl.nodes, cfg.dir, topLo, topHi);

                // Build robust HEX8 from bottom and top face nodes
                // Sort bottom face CCW (viewed from stacking-), match top 1:1
                int dim1 = (cfg.dir + 1) % 3;
                int dim2 = (cfg.dir + 2) % 3;
                auto gc = [&](int nid, int d) -> double {
                    auto it = mdl.nodes.find(nid);
                    if (it == mdl.nodes.end()) return 0.0;
                    if (d == 0) return it->second.x;
                    if (d == 1) return it->second.y;
                    return it->second.z;
                };

                // Sort bottom face nodes CCW by angle from centroid
                double cx = 0, cy = 0;
                for (int i = 0; i < 4; i++) {
                    cx += gc(botLo[i], dim1);
                    cy += gc(botLo[i], dim2);
                }
                cx /= 4; cy /= 4;
                // Compute angle and sort
                struct AngleIdx { double angle; int idx; };
                AngleIdx ai[4];
                for (int i = 0; i < 4; i++) {
                    ai[i].angle = std::atan2(gc(botLo[i], dim2) - cy, gc(botLo[i], dim1) - cx);
                    ai[i].idx = i;
                }
                std::sort(ai, ai + 4, [](const AngleIdx& a, const AngleIdx& b) { return a.angle < b.angle; });
                int sortedBot[4];
                for (int i = 0; i < 4; i++) sortedBot[i] = botLo[ai[i].idx];

                // Verify CCW: cross product should align with stacking direction (+)
                double v1x = gc(sortedBot[1], dim1) - gc(sortedBot[0], dim1);
                double v1y = gc(sortedBot[1], dim2) - gc(sortedBot[0], dim2);
                double v3x = gc(sortedBot[3], dim1) - gc(sortedBot[0], dim1);
                double v3y = gc(sortedBot[3], dim2) - gc(sortedBot[0], dim2);
                double cross = v1x * v3y - v1y * v3x;
                if (cross < 0) {
                    // Reverse to make CCW: swap [1] and [3]
                    std::swap(sortedBot[1], sortedBot[3]);
                }

                // Spatially match top face nodes to sorted bottom
                int matched[4];
                bool used[4] = {false,false,false,false};
                for (int i = 0; i < 4; i++) {
                    double b1 = gc(sortedBot[i], dim1), b2 = gc(sortedBot[i], dim2);
                    double bestDist = 1e30;
                    int bestJ = 0;
                    for (int j = 0; j < 4; j++) {
                        if (used[j]) continue;
                        double d1 = gc(topHi[j], dim1) - b1;
                        double d2 = gc(topHi[j], dim2) - b2;
                        double dist = d1*d1 + d2*d2;
                        if (dist < bestDist) { bestDist = dist; bestJ = j; }
                    }
                    matched[i] = topHi[bestJ];
                    used[bestJ] = true;
                }

                NewElem ne;
                ne.id = newEid++;
                ne.pid = grpPidNew;
                for (int i = 0; i < 4; i++) ne.nid[i] = sortedBot[i];
                for (int i = 0; i < 4; i++) ne.nid[i + 4] = matched[i];
                newElems.push_back(ne);
            }
        }

        results.push_back({gname, grpPidNew, grpMidNew, grpSecNew,
                           hom, (int)columns.size(), (int)grpElemIds.size()});
    }

    // --- Phase 3: Write output ---
    console.info("\nWriting output: " + cfg.outputPath);

    std::ofstream outf(cfg.outputPath);
    if (!outf.is_open()) {
        console.error("Cannot open output: " + cfg.outputPath);
        return 1;
    }

    // Build set of nodes still in use (remaining + new elements) for orphan removal
    std::set<int> usedNodeIds;
    for (auto& [eid, el] : mdl.elems) {
        if (removeElemIds.count(eid)) continue;
        for (int j = 0; j < 8; j++) usedNodeIds.insert(el.nid[j]);
    }
    for (auto& ne : newElems) {
        for (int j = 0; j < 8; j++) usedNodeIds.insert(ne.nid[j]);
    }

    // Copy raw lines, filtering removed elements and orphan nodes
    bool inElemBlock = false;
    bool inNodeBlock = false;
    bool atEnd = false;

    for (auto& rawLine : mdl.rawLines) {
        std::string up = mg_toUpper(mg_trim(rawLine));

        if (!rawLine.empty() && rawLine[0] == '*') {
            inElemBlock = (up.find("*ELEMENT_SOLID") == 0);
            inNodeBlock = (up.find("*NODE") == 0 && up.find("*NODE_") == std::string::npos);
            if (up == "*END") {
                atEnd = true;
                break;
            }
        }

        if (inElemBlock && !rawLine.empty() && rawLine[0] != '*' && rawLine[0] != '$') {
            auto toks = mg_tokenWS(rawLine);
            if (toks.size() >= 2) {
                int eid = mg_toInt(toks[0]);
                if (removeElemIds.count(eid)) continue;
            }
        }

        if (inNodeBlock && !rawLine.empty() && rawLine[0] != '*' && rawLine[0] != '$') {
            auto toks = mg_tokenWS(rawLine);
            if (toks.size() >= 1) {
                int nid = mg_toInt(toks[0]);
                if (nid > 0 && !usedNodeIds.count(nid)) continue; // orphan node
            }
        }

        outf << rawLine << "\n";
    }

    // Append new material, section, part, and elements for each group
    for (auto& gr : results) {
        outf << "$\n";
        outf << "$ === Merged: " << gr.name << " ===\n";
        outf << "$\n";

        // MAT_ELASTIC
        outf << "*MAT_ELASTIC_TITLE\n";
        outf << gr.name << "\n";
        char buf[256];
        // LS-DYNA 10-char fixed fields: MID, RO, E, PR
        snprintf(buf, sizeof(buf), "%10d%10.3E%10.1f%10.4f       0.0       0.0       0.0",
                 gr.mid, gr.matProps.rho, gr.matProps.E, gr.matProps.nu);
        outf << "$#     mid        ro         e        pr        da        db  not used\n";
        outf << buf << "\n";

        // CTE if present
        if (gr.matProps.hasCte) {
            outf << "*MAT_ADD_THERMAL_EXPANSION_TITLE\n";
            outf << gr.name << "_CTE\n";
            snprintf(buf, sizeof(buf), "%10d%10d%10.3E",
                     gr.mid, 0, 1.0);
            outf << "$#     pid      lcid      mult\n";
            outf << buf << "\n";
            snprintf(buf, sizeof(buf), "%10.3E", gr.matProps.cte);
            outf << "$#                                   alpha\n";
            outf << buf << "\n";
        }

        // SECTION_SOLID
        outf << "*SECTION_SOLID\n";
        snprintf(buf, sizeof(buf), "%10d%10d", gr.secid, 1);
        outf << "$#   secid    elform\n";
        outf << buf << "\n";

        // PART
        outf << "*PART\n";
        outf << gr.name << "\n";
        snprintf(buf, sizeof(buf), "%10d%10d%10d", gr.pid, gr.secid, gr.mid);
        outf << buf << "\n";
    }

    // New elements
    if (!newElems.empty()) {
        outf << "$\n";
        outf << "$ === Merged Elements ===\n";
        outf << "$\n";
        outf << "*ELEMENT_SOLID\n";
        for (auto& ne : newElems) {
            char buf2[256];
            snprintf(buf2, sizeof(buf2), "%8d%8d%8d%8d%8d%8d%8d%8d%8d%8d",
                     ne.id, ne.pid,
                     ne.nid[0], ne.nid[1], ne.nid[2], ne.nid[3],
                     ne.nid[4], ne.nid[5], ne.nid[6], ne.nid[7]);
            outf << buf2 << "\n";
        }
    }

    outf << "*END\n";
    outf.close();

    // Summary
    console.info("\nSummary:");
    for (auto& gr : results) {
        console.info("  " + gr.name + ": " + std::to_string(gr.nOrigElems) +
                     " elems → " + std::to_string(gr.nColumns) +
                     " merged (PID=" + std::to_string(gr.pid) +
                     ", MID=" + std::to_string(gr.mid) + ")");
        char sb[128];
        snprintf(sb, sizeof(sb), "    E=%.1f  nu=%.4f  rho=%.4E",
                 gr.matProps.E, gr.matProps.nu, gr.matProps.rho);
        console.info(sb);
        if (gr.matProps.hasCte) {
            snprintf(sb, sizeof(sb), "    CTE=%.4E", gr.matProps.cte);
            console.info(sb);
        }
    }

    return 0;
}
