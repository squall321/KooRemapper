#include "standalone_ops.h"
#include "util/YamlComment.h"
#include "assembly/ModelAssembler.h"
#include "assembly/AssemblyConfig.h"
#include "assembly/AssemblyConfigReader.h"
#include "cli/ConsoleOutput.h"
#include <fstream>
#include <sstream>
#include <string>
#include <vector>
#include <algorithm>

// Knowledge graph (lat.md):
//   @lat: [[modules/commands]]

using namespace KooRemapper;

// ══════════════════════════════════════════════════════════════════════════════
// Standalone commands for operations that were previously assemble-only
// ══════════════════════════════════════════════════════════════════════════════

// Helper: common YAML parsing setup
struct StandaloneYamlBase {
    std::string modelFile, outputFile, configDir;
    double matE = 0.0, matNu = 0.0;

    static std::string trim(const std::string& s) {
        size_t a=0, b=s.size();
        while (a<b && std::isspace((unsigned char)s[a])) ++a;
        while (b>a && std::isspace((unsigned char)s[b-1])) --b;
        return s.substr(a,b-a);
    }
    static int countIndent(const std::string& s) {
        int n=0; while (n<(int)s.size() && s[n]==' ') ++n; return n;
    }
    static std::string stripQuotes(const std::string& s) {
        if (s.size() >= 2 && ((s.front()=='"' && s.back()=='"') || (s.front()=='\'' && s.back()=='\'')))
            return s.substr(1, s.size()-2);
        return s;
    }
    // 'key: value' 줄의 키 — operations 항목 첫 줄('- type: hex20')은 대시를 떼고 읽는다.
    // 예전엔 키가 '- type'·'- source_pid' 가 되어 항목의 첫 키를 조용히 버렸다(convert 가 hex20 대신 tet10 기본값).
    static std::string keyOf(const std::string& tr, size_t cp) {
        std::string k = trim(tr.substr(0, cp));
        // 대시 판정은 아래 목록 분기들과 같게 '- '(공백)만 — 예전엔 '-\t' 도 떼어 탭 항목이 앞 항목을 덮어썼다
        if (k.size() >= 2 && k[0] == '-' && k[1] == ' ') k = trim(k.substr(2));
        return k;
    }
    // 키가 목록 항목 첫 줄('- layers:')이면 키 열은 대시 다음 — 블록을 여는 키의 들여쓰기 기준이 된다.
    // 예전엔 대시 줄 들여쓰기를 기준 삼아 같은 항목의 형제 키들을 블록 안으로 삼켰다.
    static int keyIndent(const std::string& tr, int indent) {
        if (tr.substr(0,2) != "- ") return indent;
        size_t i = 1;
        while (i < tr.size() && tr[i] == ' ') ++i;
        return indent + (int)i;
    }

    bool resolveFiles(const std::string& yamlFile) {
        size_t lastSlash = yamlFile.find_last_of("/\\");
        if (lastSlash != std::string::npos) configDir = yamlFile.substr(0, lastSlash);
        return true;
    }

    // 절대 경로가 아니면 YAML 이 있는 폴더 기준으로 푼다(assemble 과 같은 규칙).
    // 예전엔 '/' 가 없는 이름만 붙여, '../arc30/arc30_flat.k' 같은 상대 경로는 실행 폴더에서 찾아 열지 못했다.
    std::string resolvePath(const std::string& p) const {
        if (configDir.empty() || p.empty()) return p;
        if (p.size() >= 2 && p[1] == ':') return p;            // Windows 절대 경로(X:\...)
        if (p[0] == '/' || p[0] == '\\') return p;             // POSIX 절대 경로 / UNC
        return configDir + "/" + p;
    }

    std::string getOutputPrefix() const {
        std::string op = outputFile.empty() ? modelFile : outputFile;
        op = resolvePath(op);
        if (op.size() >= 2 && op.substr(op.size()-2) == ".k")
            op = op.substr(0, op.size()-2);
        return op;
    }

    void parseCommonKey(const std::string& key, const std::string& val) {
        if      (key == "model" || key == "base_model")  modelFile = val;
        else if (key == "output") outputFile = val;
        else if (key == "E")  { try { matE = std::stod(val); } catch(...) {} }
        else if (key == "nu") { try { matNu = std::stod(val); } catch(...) {} }
    }
};

// ── Standalone wrap ─────────────────────────────────────────────────────────
int runWrap(const std::string& yamlFile, ConsoleOutput& console) {
    StandaloneYamlBase y;
    y.resolveFiles(yamlFile);

    WrapOperation op;

    std::ifstream f(yamlFile);
    if (!f.is_open()) { console.error("Cannot open: " + yamlFile); return 1; }
    std::string ln;
    while (std::getline(f, ln)) {
        std::string tr = y.trim(ln);
        if (tr.empty() || tr[0] == '#') continue;
        size_t cp = tr.find(':');
        if (cp == std::string::npos) continue;
        std::string key = y.keyOf(tr, cp);
        std::string val = y.stripQuotes(y.trim(KooRemapper::yamlStripComment(tr.substr(cp+1))));

        y.parseCommonKey(key, val);

        if (key == "target_pid") {
            if (!val.empty() && val.front() == '[') {
                std::string inner = val.substr(1, val.size() - 2);
                std::istringstream iss(inner);
                std::string tok;
                while (std::getline(iss, tok, ',')) {
                    try { op.targetPids.push_back(std::stoi(y.trim(tok))); } catch (...) {}
                }
            } else {
                try { op.targetPids.push_back(std::stoi(val)); } catch (...) {}
            }
        } else if (key == "axis") {
            op.axis = val;
        } else if (key == "tension") {
            try { op.tension = std::stod(val); } catch (...) {}
        } else if (key == "center") {
            if (!val.empty() && val.front() == '[') {
                std::string inner = val.substr(1, val.size() - 2);
                size_t comma = inner.find(',');
                if (comma != std::string::npos) {
                    try {
                        op.centerA = std::stod(y.trim(inner.substr(0, comma)));
                        op.centerB = std::stod(y.trim(inner.substr(comma + 1)));
                        op.autoCenter = false;
                    } catch (...) {}
                }
            }
        }
    }
    f.close();

    if (op.targetPids.empty()) { console.error("No target_pid specified"); return 1; }
    if (op.tension == 0.0) { console.error("tension must be non-zero"); return 1; }

    ModelAssembler assembler;
    if (!assembler.loadBaseModel(y.resolvePath(y.modelFile))) {
        console.error(assembler.getErrorMessage()); return 1;
    }
    if (!assembler.applyWrap(op, y.matE, y.matNu)) {
        console.error(assembler.getErrorMessage()); return 1;
    }
    for (auto& msg : assembler.infoMessages) console.info(msg);
    if (!assembler.writeOutput(y.getOutputPrefix())) {
        console.error(assembler.getErrorMessage()); return 1;
    }
    console.success("Wrap output: " + y.getOutputPrefix() + ".k");
    return 0;
}

// ── Standalone update ───────────────────────────────────────────────────────
int runUpdate(const std::string& yamlFile, ConsoleOutput& console) {
    StandaloneYamlBase y;
    y.resolveFiles(yamlFile);

    UpdateOperation op;

    std::ifstream f(yamlFile);
    if (!f.is_open()) { console.error("Cannot open: " + yamlFile); return 1; }
    std::string ln;
    while (std::getline(f, ln)) {
        std::string tr = y.trim(ln);
        if (tr.empty() || tr[0] == '#') continue;
        size_t cp = tr.find(':');
        if (cp == std::string::npos) continue;
        std::string key = y.keyOf(tr, cp);
        std::string val = y.stripQuotes(y.trim(KooRemapper::yamlStripComment(tr.substr(cp+1))));

        y.parseCommonKey(key, val);

        if (key == "dynain") {
            op.dynainFile = val;
        }
    }
    f.close();

    if (y.modelFile.empty()) { console.error("[update] model not specified"); return 1; }
    if (op.dynainFile.empty()) { console.error("[update] dynain not specified"); return 1; }

    // Resolve paths
    std::string modelPath = y.resolvePath(y.modelFile);
    op.dynainFile = y.resolvePath(op.dynainFile);
    std::string outputPrefix = y.getOutputPrefix();

    console.println("[update] Model: " + modelPath);
    console.println("[update] Dynain: " + op.dynainFile);

    ModelAssembler assembler;
    if (!assembler.loadBaseModel(modelPath)) {
        console.error(assembler.getErrorMessage()); return 1;
    }
    if (!assembler.applyUpdate(op)) {
        console.error(assembler.getErrorMessage()); return 1;
    }
    for (auto& msg : assembler.infoMessages) console.info(msg);
    if (!assembler.writeOutput(outputPrefix)) {
        console.error(assembler.getErrorMessage()); return 1;
    }
    console.success("Update output: " + outputPrefix + ".k");
    return 0;
}

// 단독 명령도 assemble 과 같은 규칙으로 값을 검사한다 — 예전엔 검증 없이 적용해 bend(source 누락)는 SIGSEGV,
// indent(points·r1/r2 누락)는 abort 했고, offset connection_mode: shared·iga element_size: 0 같은 값은 조용히 통과했다.
template <typename Op>
static bool validateLikeAssemble(AssemblyOperation::Type type, Op AssemblyOperation::*member, const Op& op,
                                 const char* tag, ConsoleOutput& console) {
    AssemblyOperation aop;
    aop.type = type;
    aop.*member = op;
    try {
        AssemblyConfigReader::validateOperation(aop, 0);
    } catch (const std::exception& e) {
        console.error(std::string("[") + tag + "] " + e.what());
        return false;
    }
    return true;
}

// ── Standalone restack ──────────────────────────────────────────────────────
int runRestack(const std::string& yamlFile, ConsoleOutput& console) {
    StandaloneYamlBase y;
    y.resolveFiles(yamlFile);

    std::ifstream f(yamlFile);
    if (!f.is_open()) { console.error("Cannot open: " + yamlFile); return 1; }

    RestackOperation op;
    bool inLayers = false;
    int layersIndent = 0;
    bool readingMatCard = false;
    // 블록은 키보다 깊게 들여쓴 줄까지(YAML). 예전엔 ':' 나 '-' 로 시작하는 카드 줄(제목 'Steel: SUS304')에서
    // 끊겨 층 PART mid 가 0 이 됐고, 들여쓰기를 키+2칸으로 가정해 더 깊은 카드는 10열 칸이 밀렸다.
    int matCardKeyIndent = 0;
    int matCardBaseIndent = -1;  // 첫 내용 줄의 들여쓰기

    std::string ln;
    while (std::getline(f, ln)) {
        if (!ln.empty() && ln.back() == '\r') ln.pop_back();
        int indent = y.countIndent(ln);
        std::string tr = y.trim(ln);
        if (tr.empty() || tr[0]=='#') continue;

        if (readingMatCard) {
            if (indent > matCardKeyIndent) {
                if (matCardBaseIndent < 0) matCardBaseIndent = indent;
                if (!op.layers.empty())
                    op.layers.back().materialCard += ln.substr(std::min(indent, matCardBaseIndent)) + "\n";
                continue;
            }
            readingMatCard = false;
        }

        if (inLayers && indent <= layersIndent && tr.substr(0,2) != "- ") {
            inLayers = false;
        }

        size_t cp = tr.find(':');
        if (cp == std::string::npos) continue;
        std::string key = y.keyOf(tr, cp);
        std::string val = y.stripQuotes(y.trim(KooRemapper::yamlStripComment(tr.substr(cp+1))));

        if (!inLayers) {
            y.parseCommonKey(key, val);
            if      (key == "target_pid") { try { op.targetPid = std::stoi(val); } catch(...) {} }
            else if (key == "direction") op.direction = val;
            else if (key == "element_type") op.elementType = val;
            else if (key == "layers") { inLayers = true; layersIndent = y.keyIndent(tr, indent); }
            continue;
        }

        // Layer list
        if (tr.substr(0,2) == "- ") {
            op.layers.push_back({});
            std::string rest = y.trim(tr.substr(2));
            size_t rcp = rest.find(':');
            if (rcp != std::string::npos) {
                std::string rk = y.trim(rest.substr(0, rcp));
                // 예전엔 대시 줄 값의 주석을 안 떼 'material_card: |  # 메모' 층을 카드 없음으로, '"0.2"  # 메모' 를 잘못된 두께로 봤다
                std::string rv = y.stripQuotes(y.trim(KooRemapper::yamlStripComment(rest.substr(rcp+1))));
                if (rk == "thickness") { try { op.layers.back().thickness = std::stod(rv); } catch(...) {} }
                else if (rk == "material_card" && rv == "|") { readingMatCard = true; matCardKeyIndent = y.keyIndent(tr, indent); matCardBaseIndent = -1; }
            }
            continue;
        }
        if (!op.layers.empty()) {
            if (key == "thickness") { try { op.layers.back().thickness = std::stod(val); } catch(...) {} }
            else if (key == "material_card" && val == "|") { readingMatCard = true; matCardKeyIndent = indent; matCardBaseIndent = -1; }
        }
    }
    f.close();

    if (y.modelFile.empty()) { console.error("[restack] model not specified"); return 1; }
    std::string modelPath = y.resolvePath(y.modelFile);
    std::string outputPrefix = y.getOutputPrefix();

    console.println("[restack] Model: " + modelPath);
    if (!validateLikeAssemble(AssemblyOperation::RESTACK, &AssemblyOperation::restack, op, "restack", console)) return 1;
    ModelAssembler assembler;
    if (!assembler.loadBaseModel(modelPath)) { console.error(assembler.getErrorMessage()); return 1; }
    if (!assembler.applyRestack(op, y.matE, y.matNu)) { console.error(assembler.getErrorMessage()); return 1; }
    for (const auto& msg : assembler.infoMessages) console.println(msg);
    if (!assembler.writeOutput(outputPrefix)) { console.error(assembler.getErrorMessage()); return 1; }
    console.println("[restack] Done -> " + outputPrefix + ".k");
    return 0;
}

// ── Standalone bend ─────────────────────────────────────────────────────────
int runBend(const std::string& yamlFile, ConsoleOutput& console) {
    StandaloneYamlBase y;
    y.resolveFiles(yamlFile);

    std::ifstream f(yamlFile);
    if (!f.is_open()) { console.error("Cannot open: " + yamlFile); return 1; }

    BendOperation op;
    std::string ln;
    while (std::getline(f, ln)) {
        if (!ln.empty() && ln.back() == '\r') ln.pop_back();
        std::string tr = y.trim(ln);
        if (tr.empty() || tr[0]=='#') continue;
        size_t cp = tr.find(':');
        if (cp == std::string::npos) continue;
        std::string key = y.keyOf(tr, cp);
        std::string val = y.stripQuotes(y.trim(KooRemapper::yamlStripComment(tr.substr(cp+1))));

        y.parseCommonKey(key, val);
        if      (key == "target_pid") { try { op.targetPid = std::stoi(val); } catch(...) {} }
        else if (key == "plane") op.plane = val;
        else if (key == "mode") op.mode = val;
        else if (key == "source") op.source = val;
        else if (key == "dat_file") op.datFile = val;
        else if (key == "dat_top") op.datTop = val;
        else if (key == "dat_bottom") op.datBottom = val;
        else if (key == "expression") op.expression = val;
    }
    f.close();

    if (y.modelFile.empty()) { console.error("[bend] model not specified"); return 1; }
    std::string modelPath = y.resolvePath(y.modelFile);
    std::string outputPrefix = y.getOutputPrefix();

    console.println("[bend] Model: " + modelPath);
    if (!validateLikeAssemble(AssemblyOperation::BEND, &AssemblyOperation::bend, op, "bend", console)) return 1;
    ModelAssembler assembler;
    if (!assembler.loadBaseModel(modelPath)) { console.error(assembler.getErrorMessage()); return 1; }
    if (!assembler.applyBend(op, y.matE, y.matNu, y.configDir)) { console.error(assembler.getErrorMessage()); return 1; }
    for (const auto& msg : assembler.infoMessages) console.println(msg);
    if (!assembler.writeOutput(outputPrefix)) { console.error(assembler.getErrorMessage()); return 1; }
    console.println("[bend] Done -> " + outputPrefix + ".k");
    return 0;
}

// ── Standalone indent ───────────────────────────────────────────────────────
int runIndent(const std::string& yamlFile, ConsoleOutput& console) {
    StandaloneYamlBase y;
    y.resolveFiles(yamlFile);

    std::ifstream f(yamlFile);
    if (!f.is_open()) { console.error("Cannot open: " + yamlFile); return 1; }

    IndentOperation op;
    bool inPoints = false;
    int pointsIndent = 0;
    bool inShape = false;

    std::string ln;
    while (std::getline(f, ln)) {
        if (!ln.empty() && ln.back() == '\r') ln.pop_back();
        int indent = y.countIndent(ln);
        std::string tr = y.trim(ln);
        if (tr.empty() || tr[0]=='#') continue;

        if (inPoints && indent <= pointsIndent && tr.substr(0,2) != "- ") {
            inPoints = false;
        }

        if (inPoints && tr.substr(0,2) == "- ") {
            // Parse [x1, x2] — 예전엔 '- [6, 3]   # 메모' 가 ']' 로 끝나지 않아 점을 조용히 버렸다
            std::string rest = y.trim(KooRemapper::yamlStripComment(tr.substr(2)));
            if (!rest.empty() && rest.front() == '[' && rest.back() == ']') {
                std::string inner = rest.substr(1, rest.size()-2);
                std::istringstream iss(inner);
                std::string tok;
                double x1=0, x2=0;
                if (std::getline(iss, tok, ',')) { try { x1 = std::stod(y.trim(tok)); } catch(...) {} }
                if (std::getline(iss, tok, ',')) { try { x2 = std::stod(y.trim(tok)); } catch(...) {} }
                op.points.push_back({x1, x2});
            }
            continue;
        }

        size_t cp = tr.find(':');
        if (cp == std::string::npos) continue;
        std::string key = y.keyOf(tr, cp);
        std::string val = y.stripQuotes(y.trim(KooRemapper::yamlStripComment(tr.substr(cp+1))));

        y.parseCommonKey(key, val);
        if      (key == "target_pid") { try { op.targetPid = std::stoi(val); } catch(...) {} }
        else if (key == "plane") op.plane = val;
        else if (key == "direction") op.direction = val;
        else if (key == "depth") { try { op.depth = std::stod(val); } catch(...) {} }
        else if (key == "r1") { try { op.r1 = std::stod(val); } catch(...) {} }
        else if (key == "r2") { try { op.r2 = std::stod(val); } catch(...) {} }
        else if (key == "bottom_ratio") { try { op.bottomRatio = std::stod(val); } catch(...) {} }
        else if (key == "stress") op.stress = (val == "true" || val == "yes" || val == "1");
        else if (key == "shell_thickness") { try { op.shellThickness = std::stod(val); } catch(...) {} }
        else if (key == "type" && inShape) op.shapeType = val;
        else if (key == "shape") inShape = true;
        else if (key == "points") { inPoints = true; pointsIndent = y.keyIndent(tr, indent); }
    }
    f.close();

    if (y.modelFile.empty()) { console.error("[indent] model not specified"); return 1; }
    std::string modelPath = y.resolvePath(y.modelFile);
    std::string outputPrefix = y.getOutputPrefix();

    console.println("[indent] Model: " + modelPath);
    if (!validateLikeAssemble(AssemblyOperation::INDENT, &AssemblyOperation::indent, op, "indent", console)) return 1;
    ModelAssembler assembler;
    if (!assembler.loadBaseModel(modelPath)) { console.error(assembler.getErrorMessage()); return 1; }
    if (!assembler.applyIndent(op, y.matE, y.matNu)) { console.error(assembler.getErrorMessage()); return 1; }
    for (const auto& msg : assembler.infoMessages) console.println(msg);
    if (!assembler.writeOutput(outputPrefix)) { console.error(assembler.getErrorMessage()); return 1; }
    console.println("[indent] Done -> " + outputPrefix + ".k");
    return 0;
}

// ── Standalone formstrain ───────────────────────────────────────────────────
int runFormstrain(const std::string& yamlFile, ConsoleOutput& console) {
    StandaloneYamlBase y;
    y.resolveFiles(yamlFile);

    std::ifstream f(yamlFile);
    if (!f.is_open()) { console.error("Cannot open: " + yamlFile); return 1; }

    FormStrainOperation op;
    std::string ln;
    while (std::getline(f, ln)) {
        if (!ln.empty() && ln.back() == '\r') ln.pop_back();
        std::string tr = y.trim(ln);
        if (tr.empty() || tr[0]=='#') continue;
        size_t cp = tr.find(':');
        if (cp == std::string::npos) continue;
        std::string key = y.keyOf(tr, cp);
        std::string val = y.stripQuotes(y.trim(KooRemapper::yamlStripComment(tr.substr(cp+1))));

        y.parseCommonKey(key, val);
        if      (key == "target_pid") { try { op.targetPid = std::stoi(val); } catch(...) {} }
        else if (key == "shell_thickness") { try { op.shellThickness = std::stod(val); } catch(...) {} }
        else if (key == "min_curvature") { try { op.minCurvature = std::stod(val); } catch(...) {} }
    }
    f.close();

    if (y.modelFile.empty()) { console.error("[formstrain] model not specified"); return 1; }
    std::string modelPath = y.resolvePath(y.modelFile);
    std::string outputPrefix = y.getOutputPrefix();

    console.println("[formstrain] Model: " + modelPath);
    ModelAssembler assembler;
    if (!assembler.loadBaseModel(modelPath)) { console.error(assembler.getErrorMessage()); return 1; }
    if (!assembler.applyFormStrain(op)) { console.error(assembler.getErrorMessage()); return 1; }
    for (const auto& msg : assembler.infoMessages) console.println(msg);
    if (!assembler.writeOutput(outputPrefix)) { console.error(assembler.getErrorMessage()); return 1; }
    console.println("[formstrain] Done -> " + outputPrefix + ".k");
    return 0;
}

// ── Standalone convert (tet10/hex20/quad8/tria6) ────────────────────────────
int runConvert(const std::string& yamlFile, ConsoleOutput& console) {
    StandaloneYamlBase y;
    y.resolveFiles(yamlFile);

    std::ifstream f(yamlFile);
    if (!f.is_open()) { console.error("Cannot open: " + yamlFile); return 1; }

    Tet10ConvertOperation op;
    std::string ln;
    while (std::getline(f, ln)) {
        if (!ln.empty() && ln.back() == '\r') ln.pop_back();
        std::string tr = y.trim(ln);
        if (tr.empty() || tr[0]=='#') continue;
        size_t cp = tr.find(':');
        if (cp == std::string::npos) continue;
        std::string key = y.keyOf(tr, cp);
        std::string val = y.stripQuotes(y.trim(KooRemapper::yamlStripComment(tr.substr(cp+1))));

        y.parseCommonKey(key, val);
        if      (key == "target_pid") { try { op.targetPid = std::stoi(val); } catch(...) {} }
        else if (key == "elform") { try { op.elform = std::stoi(val); } catch(...) {} }
        else if (key == "convert_type" || key == "type") op.convertType = val;
    }
    f.close();

    if (y.modelFile.empty()) { console.error("[convert] model not specified"); return 1; }
    std::string modelPath = y.resolvePath(y.modelFile);
    std::string outputPrefix = y.getOutputPrefix();

    console.println("[convert] Model: " + modelPath);
    console.println("[convert] Type: " + op.convertType);
    ModelAssembler assembler;
    if (!assembler.loadBaseModel(modelPath)) { console.error(assembler.getErrorMessage()); return 1; }
    if (!assembler.applyTet10Convert(op)) { console.error(assembler.getErrorMessage()); return 1; }
    for (const auto& msg : assembler.infoMessages) console.println(msg);
    if (!assembler.writeOutput(outputPrefix)) { console.error(assembler.getErrorMessage()); return 1; }
    console.println("[convert] Done -> " + outputPrefix + ".k");
    return 0;
}

// ── Standalone refine ───────────────────────────────────────────────────────
int runRefine(const std::string& yamlFile, ConsoleOutput& console) {
    StandaloneYamlBase y;
    y.resolveFiles(yamlFile);

    std::ifstream f(yamlFile);
    if (!f.is_open()) { console.error("Cannot open: " + yamlFile); return 1; }

    RefineOperation op;
    std::string ln;
    while (std::getline(f, ln)) {
        if (!ln.empty() && ln.back() == '\r') ln.pop_back();
        std::string tr = y.trim(ln);
        if (tr.empty() || tr[0]=='#') continue;
        size_t cp = tr.find(':');
        if (cp == std::string::npos) continue;
        std::string key = y.keyOf(tr, cp);
        std::string val = y.stripQuotes(y.trim(KooRemapper::yamlStripComment(tr.substr(cp+1))));

        y.parseCommonKey(key, val);
        if      (key == "target_pid") { try { op.targetPid = std::stoi(val); } catch(...) {} }
        else if (key == "ratio") { try { op.ratio = std::stoi(val); } catch(...) {} }
    }
    f.close();

    if (y.modelFile.empty()) { console.error("[refine] model not specified"); return 1; }
    std::string modelPath = y.resolvePath(y.modelFile);
    std::string outputPrefix = y.getOutputPrefix();

    console.println("[refine] Model: " + modelPath);
    ModelAssembler assembler;
    if (!assembler.loadBaseModel(modelPath)) { console.error(assembler.getErrorMessage()); return 1; }
    if (!assembler.applyRefine(op)) { console.error(assembler.getErrorMessage()); return 1; }
    for (const auto& msg : assembler.infoMessages) console.println(msg);
    if (!assembler.writeOutput(outputPrefix)) { console.error(assembler.getErrorMessage()); return 1; }
    console.println("[refine] Done -> " + outputPrefix + ".k");
    return 0;
}

// ── Standalone elform ───────────────────────────────────────────────────────
int runElform(const std::string& yamlFile, ConsoleOutput& console) {
    StandaloneYamlBase y;
    y.resolveFiles(yamlFile);

    std::ifstream f(yamlFile);
    if (!f.is_open()) { console.error("Cannot open: " + yamlFile); return 1; }

    ElformOperation op;
    std::string ln;
    while (std::getline(f, ln)) {
        if (!ln.empty() && ln.back() == '\r') ln.pop_back();
        std::string tr = y.trim(ln);
        if (tr.empty() || tr[0]=='#') continue;
        size_t cp = tr.find(':');
        if (cp == std::string::npos) continue;
        std::string key = y.keyOf(tr, cp);
        std::string val = y.stripQuotes(y.trim(KooRemapper::yamlStripComment(tr.substr(cp+1))));

        y.parseCommonKey(key, val);
        if      (key == "target_pid") { try { op.targetPid = std::stoi(val); } catch(...) {} }
        else if (key == "target_elform") op.targetElform = val;
    }
    f.close();

    if (y.modelFile.empty()) { console.error("[elform] model not specified"); return 1; }
    std::string modelPath = y.resolvePath(y.modelFile);
    std::string outputPrefix = y.getOutputPrefix();

    console.println("[elform] Model: " + modelPath);
    ModelAssembler assembler;
    if (!assembler.loadBaseModel(modelPath)) { console.error(assembler.getErrorMessage()); return 1; }
    if (!assembler.applyElform(op)) { console.error(assembler.getErrorMessage()); return 1; }
    for (const auto& msg : assembler.infoMessages) console.println(msg);
    if (!assembler.writeOutput(outputPrefix)) { console.error(assembler.getErrorMessage()); return 1; }
    console.println("[elform] Done -> " + outputPrefix + ".k");
    return 0;
}

// ── Standalone disconnect ───────────────────────────────────────────────────
int runDisconnect(const std::string& yamlFile, ConsoleOutput& console) {
    StandaloneYamlBase y;
    y.resolveFiles(yamlFile);

    std::ifstream f(yamlFile);
    if (!f.is_open()) { console.error("Cannot open: " + yamlFile); return 1; }

    DisconnectOperation op;
    std::string ln;
    while (std::getline(f, ln)) {
        if (!ln.empty() && ln.back() == '\r') ln.pop_back();
        std::string tr = y.trim(ln);
        if (tr.empty() || tr[0]=='#') continue;
        size_t cp = tr.find(':');
        if (cp == std::string::npos) continue;
        std::string key = y.keyOf(tr, cp);
        std::string val = y.stripQuotes(y.trim(KooRemapper::yamlStripComment(tr.substr(cp+1))));

        y.parseCommonKey(key, val);
        if      (key == "target_pid") { try { op.targetPid = std::stoi(val); } catch(...) {} }
        else if (key == "mode") op.mode = val;
        else if (key == "cohesive_part_id") { try { op.cohesivePartId = std::stoi(val); } catch(...) {} }
        else if (key == "failure_strain") { try { op.failureStrain = std::stod(val); } catch(...) {} }
    }
    f.close();

    if (y.modelFile.empty()) { console.error("[disconnect] model not specified"); return 1; }
    std::string modelPath = y.resolvePath(y.modelFile);
    std::string outputPrefix = y.getOutputPrefix();

    console.println("[disconnect] Model: " + modelPath);
    ModelAssembler assembler;
    if (!assembler.loadBaseModel(modelPath)) { console.error(assembler.getErrorMessage()); return 1; }
    if (!assembler.applyDisconnect(op)) { console.error(assembler.getErrorMessage()); return 1; }
    for (const auto& msg : assembler.infoMessages) console.println(msg);
    if (!assembler.writeOutput(outputPrefix)) { console.error(assembler.getErrorMessage()); return 1; }
    console.println("[disconnect] Done -> " + outputPrefix + ".k");
    return 0;
}

// ── Standalone iga ──────────────────────────────────────────────────────────
int runIga(const std::string& yamlFile, ConsoleOutput& console) {
    StandaloneYamlBase y;
    y.resolveFiles(yamlFile);

    std::ifstream f(yamlFile);
    if (!f.is_open()) { console.error("Cannot open: " + yamlFile); return 1; }

    IGAOperation igaOp;
    bool inTargets = false;
    int targetsIndent = 0;
    bool inTargetItem = false;

    std::string ln;
    while (std::getline(f, ln)) {
        if (!ln.empty() && ln.back() == '\r') ln.pop_back();
        int indent = y.countIndent(ln);
        std::string tr = y.trim(ln);
        if (tr.empty() || tr[0]=='#') continue;

        if (inTargets && indent <= targetsIndent && tr.substr(0,2) != "- ") {
            inTargets = false;
            inTargetItem = false;
        }

        size_t cp = tr.find(':');
        if (cp == std::string::npos) continue;
        std::string key = y.keyOf(tr, cp);
        std::string val = y.stripQuotes(y.trim(KooRemapper::yamlStripComment(tr.substr(cp+1))));

        if (!inTargets) {
            y.parseCommonKey(key, val);
            if (key == "targets") { inTargets = true; targetsIndent = y.keyIndent(tr, indent); }
            continue;
        }

        // 대상 한 항목의 키 — 대시 줄(- key: v)과 하위 줄에 같은 규칙. 예전엔 대시 줄은 target_pid·target_pids·element_size 만,
        // 둘 다 target_name·exclude_name 을 몰라 이름 지정 대상이 'part 0' 으로 실패했다(assemble 경로는 지원).
        auto applyTargetKey = [&](KooRemapper::IGATargetConfig& t, const std::string& k, const std::string& v) {
            if      (k == "target_pid") { try { t.targetPid = std::stoi(v); } catch(...) {} }
            else if (k == "target_pids") {
                // Parse inline list: [1, 2, 3] or "1 2 3"
                std::string s = v;
                if (!s.empty() && s.front() == '[') s = s.substr(1);
                if (!s.empty() && s.back()  == ']') s.pop_back();
                std::replace(s.begin(), s.end(), ',', ' ');
                std::istringstream ss(s);
                int pid; while (ss >> pid) t.targetPids.push_back(pid);
            }
            else if (k == "target_name") t.targetName = v;
            else if (k == "exclude_name") t.excludeName = v;
            else if (k == "element_size") { try { t.elementSize = std::stod(v); } catch(...) {} }
            else if (k == "element_size_r") { try { t.elementSizeR = std::stod(v); } catch(...) {} }
            else if (k == "element_size_s") { try { t.elementSizeS = std::stod(v); } catch(...) {} }
            else if (k == "element_size_t") { try { t.elementSizeT = std::stod(v); } catch(...) {} }
            else if (k == "offset") { try { t.offset = std::stod(v); } catch(...) {} }
            else if (k == "bbox_scale") { try { t.bboxScale = std::stod(v); } catch(...) {} }
            else if (k == "bbox_scale_r") { try { t.bboxScaleR = std::stod(v); } catch(...) {} }
            else if (k == "bbox_scale_s") { try { t.bboxScaleS = std::stod(v); } catch(...) {} }
            else if (k == "bbox_scale_t") { try { t.bboxScaleT = std::stod(v); } catch(...) {} }
            else if (k == "ir") { try { t.ir = std::stoi(v); } catch(...) {} }
            else if (k == "styp") { try { t.styp = std::stoi(v); } catch(...) {} }
            else if (k == "tollg") { try { t.tollg = std::stod(v); } catch(...) {} }
            else if (k == "pr") { try { t.pr = std::stoi(v); } catch(...) {} }
            else if (k == "ps") { try { t.ps = std::stoi(v); } catch(...) {} }
            else if (k == "pt") { try { t.pt = std::stoi(v); } catch(...) {} }
            else if (k == "nisr") { try { t.nisr = std::stoi(v); } catch(...) {} }
            else if (k == "niss") { try { t.niss = std::stoi(v); } catch(...) {} }
            else if (k == "nist") { try { t.nist = std::stoi(v); } catch(...) {} }
        };

        if (tr.substr(0,2) == "- " && indent > targetsIndent) {
            igaOp.targets.push_back({});
            inTargetItem = true;
            std::string rest = y.trim(tr.substr(2));
            size_t rcp = rest.find(':');
            if (rcp != std::string::npos) {
                std::string rk = y.trim(rest.substr(0, rcp));
                std::string rv = y.stripQuotes(y.trim(KooRemapper::yamlStripComment(rest.substr(rcp+1))));
                applyTargetKey(igaOp.targets.back(), rk, rv);
            }
            continue;
        }

        if (inTargetItem && !igaOp.targets.empty()) {
            applyTargetKey(igaOp.targets.back(), key, val);
        }
    }
    f.close();

    if (y.modelFile.empty()) { console.error("[iga] model not specified"); return 1; }
    std::string modelPath = y.resolvePath(y.modelFile);
    std::string outputPrefix = y.getOutputPrefix();

    // Expand target_pids into individual single-pid targets
    {
        std::vector<KooRemapper::IGATargetConfig> expanded;
        for (auto& t : igaOp.targets) {
            if (!t.targetPids.empty()) {
                for (int pid : t.targetPids) {
                    auto copy = t;
                    copy.targetPid = pid;
                    copy.targetPids.clear();
                    expanded.push_back(copy);
                }
            } else {
                expanded.push_back(t);
            }
        }
        igaOp.targets = std::move(expanded);
    }

    console.println("[iga] Model: " + modelPath);
    console.println("[iga] Targets: " + std::to_string(igaOp.targets.size()));
    if (!validateLikeAssemble(AssemblyOperation::IGA, &AssemblyOperation::iga, igaOp, "iga", console)) return 1;
    ModelAssembler assembler;
    if (!assembler.loadBaseModel(modelPath)) { console.error(assembler.getErrorMessage()); return 1; }
    if (!assembler.applyIGA(igaOp, outputPrefix)) { console.error(assembler.getErrorMessage()); return 1; }
    for (const auto& msg : assembler.infoMessages) console.println(msg);
    if (!assembler.writeOutput(outputPrefix)) { console.error(assembler.getErrorMessage()); return 1; }
    console.println("[iga] Done -> " + outputPrefix + ".k");
    return 0;
}

// ── Standalone warpage ──────────────────────────────────────────────────────
int runWarpage(const std::string& yamlFile, ConsoleOutput& console) {
    StandaloneYamlBase y;
    y.resolveFiles(yamlFile);

    std::ifstream f(yamlFile);
    if (!f.is_open()) { console.error("Cannot open: " + yamlFile); return 1; }

    WarpageOperation op;
    bool inDataBbox = false;
    int dataBboxIndent = 0;

    std::string ln;
    while (std::getline(f, ln)) {
        if (!ln.empty() && ln.back() == '\r') ln.pop_back();
        int indent = y.countIndent(ln);
        std::string tr = y.trim(ln);
        if (tr.empty() || tr[0]=='#') continue;

        if (inDataBbox && indent <= dataBboxIndent) inDataBbox = false;

        size_t cp = tr.find(':');
        if (cp == std::string::npos) continue;
        std::string key = y.keyOf(tr, cp);
        std::string val = y.stripQuotes(y.trim(KooRemapper::yamlStripComment(tr.substr(cp+1))));

        if (inDataBbox) {
            if      (key == "x_min") { try { op.dataBboxXmin = std::stod(val); op.hasDataBbox = true; } catch(...) {} }
            else if (key == "x_max") { try { op.dataBboxXmax = std::stod(val); op.hasDataBbox = true; } catch(...) {} }
            else if (key == "y_min") { try { op.dataBboxYmin = std::stod(val); op.hasDataBbox = true; } catch(...) {} }
            else if (key == "y_max") { try { op.dataBboxYmax = std::stod(val); op.hasDataBbox = true; } catch(...) {} }
            continue;
        }

        y.parseCommonKey(key, val);
        if      (key == "target_pid") { try { op.targetPid = std::stoi(val); } catch(...) {} }
        else if (key == "dat_file") op.datFile = val;
        else if (key == "plane") op.plane = val;
        else if (key == "deflection_axis") op.deflectionAxis = val;
        else if (key == "unit") op.unit = val;
        else if (key == "mask_value") { try { op.maskValue = std::stod(val); } catch(...) {} }
        else if (key == "noise_threshold") { try { op.noiseThreshold = std::stod(val); } catch(...) {} }
        else if (key == "morph_factor") { try { op.morphFactor = std::stod(val); } catch(...) {} }
        else if (key == "mode") op.mode = val;
        else if (key == "finite_strain") op.useFiniteStrain = (val == "true" || val == "yes" || val == "1");
        else if (key == "outside_behavior") op.outsideBehavior = val;
        else if (key == "debug") op.debug = (val == "true" || val == "yes" || val == "1");
        else if (key == "debug_prefix") op.debugPrefix = val;
        else if (key == "data_bbox") { inDataBbox = true; dataBboxIndent = y.keyIndent(tr, indent); }
    }
    f.close();

    if (y.modelFile.empty()) { console.error("[warpage] model not specified"); return 1; }
    std::string modelPath = y.resolvePath(y.modelFile);
    std::string outputPrefix = y.getOutputPrefix();

    console.println("[warpage] Model: " + modelPath);
    ModelAssembler assembler;
    if (!assembler.loadBaseModel(modelPath)) { console.error(assembler.getErrorMessage()); return 1; }
    if (!assembler.applyWarpage(op, y.matE, y.matNu, y.configDir)) { console.error(assembler.getErrorMessage()); return 1; }
    for (const auto& msg : assembler.infoMessages) console.println(msg);
    if (!assembler.writeOutput(outputPrefix)) { console.error(assembler.getErrorMessage()); return 1; }
    console.println("[warpage] Done -> " + outputPrefix + ".k");
    return 0;
}

// ── Standalone offset ───────────────────────────────────────────────────────
int runOffset(const std::string& yamlFile, ConsoleOutput& console) {
    StandaloneYamlBase y;
    y.resolveFiles(yamlFile);

    std::ifstream f(yamlFile);
    if (!f.is_open()) { console.error("Cannot open: " + yamlFile); return 1; }

    OffsetOperation op;
    bool readingMatCard = false;
    bool readingCzmMatCard = false;
    // 블록은 키보다 깊게 들여쓴 줄까지, 기준 들여쓰기는 첫 내용 줄(YAML) — 키+2칸 가정은 더 깊은 카드의 10열 칸을 밀었다
    int matCardKeyIndent = 0;
    int matCardBaseIndent = -1;
    // material_cards: 층마다 다른 재질 목록 — assemble 은 읽는데 여기선 빠져, 층 PART 가 없는 MID 를 가리켰다
    bool inMatCardsList = false;
    bool readingMatCardsItem = false;
    int matCardsKeyIndent = 0;

    std::string ln;
    while (std::getline(f, ln)) {
        if (!ln.empty() && ln.back() == '\r') ln.pop_back();
        int indent = y.countIndent(ln);
        std::string tr = y.trim(ln);
        if (tr.empty() || tr[0]=='#') {
            // Multi-line material card may include comment-like lines
            if (readingMatCard && matCardBaseIndent >= 0 && indent >= matCardBaseIndent) {
                op.materialCard += ln.substr(std::min(indent, matCardBaseIndent)) + "\n";
            } else if (readingCzmMatCard && matCardBaseIndent >= 0 && indent >= matCardBaseIndent) {
                op.czmMaterialCard += ln.substr(std::min(indent, matCardBaseIndent)) + "\n";
            } else if (readingMatCardsItem && matCardBaseIndent >= 0 && indent >= matCardBaseIndent) {
                op.materialCards.back() += ln.substr(std::min(indent, matCardBaseIndent)) + "\n";
            }
            continue;
        }

        if (readingMatCard) {
            if (indent > matCardKeyIndent) {
                if (matCardBaseIndent < 0) matCardBaseIndent = indent;
                op.materialCard += ln.substr(std::min(indent, matCardBaseIndent)) + "\n";
                continue;
            }
            readingMatCard = false;
        }
        if (readingCzmMatCard) {
            if (indent > matCardKeyIndent) {
                if (matCardBaseIndent < 0) matCardBaseIndent = indent;
                op.czmMaterialCard += ln.substr(std::min(indent, matCardBaseIndent)) + "\n";
                continue;
            }
            readingCzmMatCard = false;
        }
        if (inMatCardsList) {
            if (readingMatCardsItem && indent > matCardKeyIndent) {
                if (matCardBaseIndent < 0) matCardBaseIndent = indent;
                op.materialCards.back() += ln.substr(std::min(indent, matCardBaseIndent)) + "\n";
                continue;
            }
            // 예전엔 '- |   # 메모' 항목을 못 알아봐 목록이 끊기고 층 재질이 빠졌다
            std::string item = KooRemapper::yamlStripComment(tr);
            if (indent > matCardsKeyIndent && (item == "- |" || item == "-|")) {
                op.materialCards.emplace_back();
                readingMatCardsItem = true;
                matCardKeyIndent = indent;
                matCardBaseIndent = -1;
                continue;
            }
            inMatCardsList = false;
            readingMatCardsItem = false;
        }

        size_t cp = tr.find(':');
        if (cp == std::string::npos) continue;
        std::string key = y.keyOf(tr, cp);
        std::string val = y.stripQuotes(y.trim(KooRemapper::yamlStripComment(tr.substr(cp+1))));

        y.parseCommonKey(key, val);
        if      (key == "source_pid") { try { op.sourcePid = std::stoi(val); } catch(...) {} }
        else if (key == "material_cards" && val.empty()) { inMatCardsList = true; matCardsKeyIndent = y.keyIndent(tr, indent); }
        else if (key == "offset_direction") op.offsetDirection = val;
        else if (key == "thickness") { try { op.thickness = std::stod(val); } catch(...) {} }
        else if (key == "thickness_formula") op.thicknessFormula = val;
        else if (key == "num_layers") { try { op.numLayers = std::stoi(val); } catch(...) {} }
        else if (key == "use_local_normals") op.useLocalNormals = (val == "true" || val == "yes" || val == "1");
        else if (key == "element_type") op.elementType = val;
        else if (key == "connection_mode") op.connectionMode = val;
        else if (key == "czm_part_id") { try { op.czmPartId = std::stoi(val); } catch(...) {} }
        else if (key == "czm_mid") { try { op.czmMid = std::stoi(val); } catch(...) {} }
        else if (key == "prestress_mode") op.prestressMode = val;
        else if (key == "inner_offset") { try { op.innerOffset = std::stod(val); } catch(...) {} }
        else if (key == "outer_offset") { try { op.outerOffset = std::stod(val); } catch(...) {} }
        else if (key == "new_pid") { try { op.newPid = std::stoi(val); } catch(...) {} }
        else if (key == "new_secid") { try { op.newSecid = std::stoi(val); } catch(...) {} }
        else if (key == "new_mid") { try { op.newMid = std::stoi(val); } catch(...) {} }
        else if (key == "part_title") op.partTitle = val;
        else if (key == "shell_thickness") { try { op.shellThickness = std::stod(val); } catch(...) {} }
        else if (key == "shell_offset") { try { op.shellOffset = std::stod(val); } catch(...) {} }
        else if (key == "material_card" && val == "|") { readingMatCard = true; matCardKeyIndent = y.keyIndent(tr, indent); matCardBaseIndent = -1; }
        else if (key == "czm_material_card" && val == "|") { readingCzmMatCard = true; matCardKeyIndent = y.keyIndent(tr, indent); matCardBaseIndent = -1; }
        // Region selection
        else if (key == "bbox_xmin") { try { op.region.xMin = std::stod(val); op.region.useBoundingBox = true; } catch(...) {} }
        else if (key == "bbox_xmax") { try { op.region.xMax = std::stod(val); op.region.useBoundingBox = true; } catch(...) {} }
        else if (key == "bbox_ymin") { try { op.region.yMin = std::stod(val); op.region.useBoundingBox = true; } catch(...) {} }
        else if (key == "bbox_ymax") { try { op.region.yMax = std::stod(val); op.region.useBoundingBox = true; } catch(...) {} }
        else if (key == "bbox_zmin") { try { op.region.zMin = std::stod(val); op.region.useBoundingBox = true; } catch(...) {} }
        else if (key == "bbox_zmax") { try { op.region.zMax = std::stod(val); op.region.useBoundingBox = true; } catch(...) {} }
        else if (key == "node_id_min") { try { op.region.nodeIdMin = std::stoi(val); } catch(...) {} }
        else if (key == "node_id_max") { try { op.region.nodeIdMax = std::stoi(val); } catch(...) {} }
        else if (key == "element_id_min") { try { op.region.elementIdMin = std::stoi(val); } catch(...) {} }
        else if (key == "element_id_max") { try { op.region.elementIdMax = std::stoi(val); } catch(...) {} }
    }
    f.close();

    if (y.modelFile.empty()) { console.error("[offset] model not specified"); return 1; }
    std::string modelPath = y.resolvePath(y.modelFile);
    std::string outputPrefix = y.getOutputPrefix();

    console.println("[offset] Model: " + modelPath);
    if (!validateLikeAssemble(AssemblyOperation::OFFSET, &AssemblyOperation::offset, op, "offset", console)) return 1;
    ModelAssembler assembler;
    if (!assembler.loadBaseModel(modelPath)) { console.error(assembler.getErrorMessage()); return 1; }
    if (!assembler.applyOffset(op, y.matE, y.matNu)) { console.error(assembler.getErrorMessage()); return 1; }
    for (const auto& msg : assembler.infoMessages) console.println(msg);
    if (!assembler.writeOutput(outputPrefix)) { console.error(assembler.getErrorMessage()); return 1; }
    console.println("[offset] Done -> " + outputPrefix + ".k");
    return 0;
}
