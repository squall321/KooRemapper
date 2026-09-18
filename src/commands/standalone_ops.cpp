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
#include <cmath>
#include <cstdio>
#include <cstdlib>

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
        return KooRemapper::yamlResolvePath(configDir, p);
    }

    // operations 항목 수 — 단독 명령은 한 항목만 다루므로, 여러 개면 조용히 합치지 말고 거부해야 한다.
    // 반환 -1 = 항목 대시 들여쓰기가 일관되지 않아 항목 수를 셀 수 없음 — 예전엔 그런 대시를
    // 세지 않아 항목 하나로 보고 뒤 항목만 조용히 적용했다(quad8 을 버리고 tria6 만 실행).
    static int countOperations(const std::string& yamlFile) {
        std::ifstream f(yamlFile);
        if (!f.is_open()) return 0;
        KooRemapper::yamlSkipBOM(f);   // 윈도우 편집기가 붙인 BOM 이 첫 키를 망가뜨렸다
        int opsIndent = -1;   // 'operations:' 키의 들여쓰기
        int itemIndent = -1;  // 항목 대시의 들여쓰기 — 하위 목록(layers·points·targets)은 더 깊어 세지 않는다
        // 현재 열려 있는 블록 키(값이 빈 'layers:'·'targets:' 등)의 들여쓰기 스택. 하나만 기억하면
        // 목록 항목 안의 중첩 매핑('gauss:')이 닫혀도 값이 되돌아오지 않아, 그 다음 형제 항목 대시를
        // '들여쓰기가 어긋났다'며 정상 YAML 을 거부했다.
        std::vector<int> blockIndents;
        int literalIndent = -1; // '|' 블록(material_card 등) 키의 들여쓰기 — 그 안의 카드 줄은 YAML 구조가 아니다
        int count = 0;
        std::string ln;
        while (std::getline(f, ln)) {
            if (!ln.empty() && ln.back() == '\r') ln.pop_back();
            int indent = countIndent(ln);
            std::string tr = trim(ln);
            if (literalIndent >= 0) {
                if (tr.empty() || indent > literalIndent) continue;
                literalIndent = -1;
            }
            if (tr.empty() || tr[0] == '#') continue;
            if (opsIndent < 0) {
                size_t cp = tr.find(':');
                if (cp != std::string::npos && trim(tr.substr(0, cp)) == "operations") opsIndent = indent;
                continue;
            }
            if (tr.substr(0,2) == "- " || tr == "-") {
                if (indent < opsIndent) break;   // 바깥 목록으로 나감
                if (itemIndent < 0) itemIndent = indent;
                // 대시 줄은 자기보다 깊은 블록 키를 닫는다(항목 대시 열에 맞춰 열린 키는 살아 있다)
                while (!blockIndents.empty() && blockIndents.back() > indent) blockIndents.pop_back();
                if (indent == itemIndent) {
                    ++count;
                    blockIndents.clear();
                    // '- layers:' 처럼 대시 줄이 바로 블록 키면 그 줄이 하위 목록을 연다
                    size_t dcp = tr.find(':');
                    if (dcp != std::string::npos) {
                        std::string dv = trim(KooRemapper::yamlStripComment(tr.substr(dcp+1)));
                        if (dv.empty()) blockIndents.push_back(keyIndent(tr, indent));
                        // '|-' '|+' '>2' 같은 지시자도 블록이다 — 예전엔 '|'·'>' 만 알아봐
                        // 블록 안의 '- ' 카드 줄을 항목으로 세어 '여러 op' 로 거부했다
                        else if (KooRemapper::yamlParseBlockHeader(dv).isBlock) literalIndent = keyIndent(tr, indent);
                    }
                    continue;
                }
                // 항목보다 깊은 대시는 블록 키가 열어 준 하위 목록일 때만 정상이다
                if (!blockIndents.empty() && indent >= blockIndents.back()) {
                    std::string item = trim(KooRemapper::yamlStripComment(tr));
                    if (!item.empty() && item[0] == '-' &&
                        KooRemapper::yamlParseBlockHeader(trim(item.substr(1))).isBlock) literalIndent = indent;
                    continue;
                }
                return -1;
            }
            if (indent <= opsIndent) break;      // operations 의 형제 키 — 블록 끝
            size_t cp = tr.find(':');
            if (cp != std::string::npos) {
                // 같은 열 이하의 키가 나오면 앞서 열린 블록은 닫힌 것이다
                while (!blockIndents.empty() && blockIndents.back() >= indent) blockIndents.pop_back();
                std::string v = trim(KooRemapper::yamlStripComment(tr.substr(cp+1)));
                if (v.empty()) blockIndents.push_back(keyIndent(tr, indent));   // 하위 목록/매핑을 여는 키
                else if (KooRemapper::yamlParseBlockHeader(v).isBlock) literalIndent = keyIndent(tr, indent);
            }
        }
        return count;
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

// operations 가 여러 개인 YAML 은 단독 명령에서 키가 서로 덮여 마지막 항목만 적용됐다
// (quad8 다음 tria6 이면 tria6 만). 조용히 하나만 하지 말고 assemble 로 안내한다.
static bool rejectMultiOperation(const std::string& yamlFile, const char* tag, const ConsoleOutput& console) {
    int n = StandaloneYamlBase::countOperations(yamlFile);
    if (n < 0) {
        console.error(std::string("[") + tag + "] " + yamlFile + " 의 operations 항목 대시 들여쓰기가 일관되지 않습니다 — "
                      "들여쓰기를 확인하세요 / inconsistent '-' indentation in the operations list; check the indentation.");
        console.error(std::string("[") + tag + "] 모든 항목의 '-' 를 같은 열에 맞추세요 / align every item's '-' at the same column.");
        return true;
    }
    if (n <= 1) return false;
    console.error(std::string("[") + tag + "] " + yamlFile + " 에 operations 항목이 " + std::to_string(n) +
                  "개 있습니다 — 단독 명령은 한 항목만 적용합니다 / has " + std::to_string(n) +
                  " operations; a standalone command applies only one.");
    console.error(std::string("[") + tag + "] 'KooRemapper assemble " + yamlFile + "' 로 실행하세요 / run it instead.");
    return true;
}

// output 이 비면 예전엔 입력 모델 경로를 그대로 출력 이름으로 써 사용자 원본을 그 자리에서 덮어썼다
// (assemble 은 같은 설정을 'output not specified' 로 거부). 접미사 자동 생성 같은 기본 이름 규칙은
// 코드 어디에도 없어 '덮어쓰기'가 유일한 동작이었으므로 D3 대로 거절한다.
static bool rejectEmptyOutput(const StandaloneYamlBase& y, const char* tag, const ConsoleOutput& console) {
    if (!y.outputFile.empty()) return false;
    console.error(std::string("[") + tag + "] output 이 비어 있습니다 — 입력 모델을 덮어쓰게 되므로 output 을 지정하세요 / "
                  "output not specified; it would overwrite the input model.");
    return true;
}

// 비유한 값 막기(D7) — 수식·입력이 nan/inf 를 만들면 좌표·두께가 'nan' 토큰으로 그대로 써지고 rc=0 이었다.
// 숫자만 들어가는 블록(*NODE·*ELEMENT·*INITIAL)만 본다 — 제목 줄이 있는 키워드는 'Nan...' 같은 이름을
// 값으로 오해할 수 있어 제외한다.
static bool deckHasNonFinite(const std::string& path, std::string& where) {
    std::ifstream f(path);
    if (!f.is_open()) return false;
    bool numericBlock = false;
    int lineNo = 0;
    std::string ln;
    while (std::getline(f, ln)) {
        ++lineNo;
        if (!ln.empty() && ln.back() == '\r') ln.pop_back();
        if (!ln.empty() && ln[0] == '*') {
            numericBlock = (ln.compare(0, 5, "*NODE") == 0 ||
                            ln.compare(0, 8, "*ELEMENT") == 0 ||
                            ln.compare(0, 8, "*INITIAL") == 0);
            continue;
        }
        if (!numericBlock || ln.empty() || ln[0] == '$') continue;
        // 숫자 줄에는 nan/inf 의 글자가 없다 — 빠른 걸러내기(큰 덱에서 줄마다 strtod 하지 않도록)
        if (ln.find_first_of("nNiI") == std::string::npos) continue;
        std::istringstream iss(ln);
        std::string tok;
        while (iss >> tok) {
            const char* begin = tok.c_str();
            char* end = nullptr;
            double v = std::strtod(begin, &end);
            if (end == begin + tok.size() && !std::isfinite(v)) {
                where = path + ":" + std::to_string(lineNo) + " '" + tok + "'";
                return true;
            }
        }
    }
    return false;
}

// 이번 writeOutput 이 실제로 쓴 파일 목록. ModelAssembler 는 경로를 내주지 않아 같은 규칙으로 되짚는다 —
//   <prefix>.k        항상
//   <prefix>.dynain   초기응력이 쌓였을 때만(단독 명령은 dynain_embed 를 쓰지 않는다)
//   <prefix>_iga_pN.k 덱에 들어간 *INCLUDE 이름으로 찾는다
// 남의 파일은 건드리지 않아야 하므로 '있으면 우리 것' 이 아니라 '이번에 쓴 것' 만 고른다.
static std::vector<std::string> writtenOutputs(const ModelAssembler& assembler, const std::string& outputPrefix) {
    std::vector<std::string> out;
    std::string deck = outputPrefix + ".k";
    out.push_back(deck);
    if (!assembler.getAccumulatedResults().empty()) out.push_back(outputPrefix + ".dynain");
    if (assembler.getIGACount() <= 0) return out;

    size_t slash = outputPrefix.find_last_of("/\\");
    std::string dir = (slash == std::string::npos) ? "" : outputPrefix.substr(0, slash + 1);
    std::string stem = ((slash == std::string::npos) ? outputPrefix : outputPrefix.substr(slash + 1)) + "_iga_p";
    std::ifstream f(deck);
    if (!f.is_open()) return out;
    std::string ln;
    bool afterInclude = false;
    while (std::getline(f, ln)) {
        if (!ln.empty() && ln.back() == '\r') ln.pop_back();
        std::string tr = StandaloneYamlBase::trim(ln);
        if (!tr.empty() && tr[0] == '*') { afterInclude = (tr.compare(0, 8, "*INCLUDE") == 0); continue; }
        if (!afterInclude || tr.empty() || tr[0] == '$') continue;
        afterInclude = false;
        if (tr.size() > stem.size() + 2 && tr.compare(0, stem.size(), stem) == 0 &&
            tr.compare(tr.size() - 2, 2, ".k") == 0) {
            out.push_back(dir + tr);
        }
    }
    return out;
}

// 쓰기 + 비유한 값 확인. ModelAssembler 는 쓰기 전에 노드 좌표를 꺼낼 공개 접근자가 없어 쓴 직후에 보고,
// 발견하면 그 파일을 지워 0 나누기 경로와 같은 결과(에러 메시지 + 결과 파일 없음 + rc=1)로 맞춘다.
// writeOutput 은 <prefix>.k 뿐 아니라 <prefix>.dynain·<prefix>_iga_pN.k 도 함께 쓴다 — .k 만 보고 .k 만 지우면
// nan 초기응력이 든 dynain 이 디스크에 남고(formstrain·indent 는 그쪽이 주 산출물이다) 사용자는 남은 파일을
// 멀쩡한 것으로 오해한다. 그래서 이번에 쓴 파일을 모두 보고, 하나라도 나쁘면 모두 지우고 목록을 찍는다.
static bool writeOutputChecked(ModelAssembler& assembler, const std::string& outputPrefix,
                               const char* tag, ConsoleOutput& console) {
    if (!assembler.writeOutput(outputPrefix)) { console.error(assembler.getErrorMessage()); return false; }

    std::vector<std::string> written = writtenOutputs(assembler, outputPrefix);
    std::string where;
    bool bad = false;
    for (const auto& w : written) { if (deckHasNonFinite(w, where)) { bad = true; break; } }
    if (!bad) return true;

    std::string removed;
    for (const auto& w : written) {
        if (std::remove(w.c_str()) == 0) {
            if (!removed.empty()) removed += ", ";
            removed += w;
        }
    }
    console.error(std::string("[") + tag + "] 결과에 유한하지 않은 값(nan/inf)이 있습니다: " + where +
                  " — 지운 출력 파일: " + removed +
                  " / non-finite value in the result; removed: " + removed);
    return false;
}

// ── Standalone wrap ─────────────────────────────────────────────────────────
int runWrap(const std::string& yamlFile, ConsoleOutput& console) {
    {   // 탭으로 들여쓴 YAML 은 블록이 통째로 무너져 조용히 아무 일도 안 했다 — 파싱 전에 거른다
        std::string tabLine;
        if (KooRemapper::yamlScanTabIndent(yamlFile, tabLine)) {
            console.error(KooRemapper::yamlTabIndentMessage("wrap", tabLine));
            return 1;
        }
    }
    StandaloneYamlBase y;
    y.resolveFiles(yamlFile);
    if (rejectMultiOperation(yamlFile, "wrap", console)) return 1;

    WrapOperation op;

    std::ifstream f(yamlFile);
    if (!f.is_open()) { console.error("Cannot open: " + yamlFile); return 1; }
    KooRemapper::yamlSkipBOM(f);   // 윈도우 편집기가 붙인 BOM 이 첫 키를 망가뜨렸다
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

    if (rejectEmptyOutput(y, "wrap", console)) return 1;
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
    if (!writeOutputChecked(assembler, y.getOutputPrefix(), "wrap", console)) return 1;
    console.success("Wrap output: " + y.getOutputPrefix() + ".k");
    return 0;
}

// ── Standalone update ───────────────────────────────────────────────────────
int runUpdate(const std::string& yamlFile, ConsoleOutput& console) {
    {   // 탭으로 들여쓴 YAML 은 블록이 통째로 무너져 조용히 아무 일도 안 했다 — 파싱 전에 거른다
        std::string tabLine;
        if (KooRemapper::yamlScanTabIndent(yamlFile, tabLine)) {
            console.error(KooRemapper::yamlTabIndentMessage("update", tabLine));
            return 1;
        }
    }
    StandaloneYamlBase y;
    y.resolveFiles(yamlFile);
    if (rejectMultiOperation(yamlFile, "update", console)) return 1;

    UpdateOperation op;

    std::ifstream f(yamlFile);
    if (!f.is_open()) { console.error("Cannot open: " + yamlFile); return 1; }
    KooRemapper::yamlSkipBOM(f);   // 윈도우 편집기가 붙인 BOM 이 첫 키를 망가뜨렸다
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

    if (rejectEmptyOutput(y, "update", console)) return 1;

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
    if (!writeOutputChecked(assembler, outputPrefix, "update", console)) return 1;
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
    {   // 탭으로 들여쓴 YAML 은 블록이 통째로 무너져 조용히 아무 일도 안 했다 — 파싱 전에 거른다
        std::string tabLine;
        if (KooRemapper::yamlScanTabIndent(yamlFile, tabLine)) {
            console.error(KooRemapper::yamlTabIndentMessage("restack", tabLine));
            return 1;
        }
    }
    StandaloneYamlBase y;
    y.resolveFiles(yamlFile);
    if (rejectMultiOperation(yamlFile, "restack", console)) return 1;

    std::ifstream f(yamlFile);
    if (!f.is_open()) { console.error("Cannot open: " + yamlFile); return 1; }
    KooRemapper::yamlSkipBOM(f);   // 윈도우 편집기가 붙인 BOM 이 첫 키를 망가뜨렸다

    RestackOperation op;
    bool inLayers = false;
    int layersIndent = 0;
    bool readingMatCard = false;
    // 블록은 키보다 깊게 들여쓴 줄까지(YAML). 예전엔 ':' 나 '-' 로 시작하는 카드 줄(제목 'Steel: SUS304')에서
    // 끊겨 층 PART mid 가 0 이 됐고, 들여쓰기를 키+2칸으로 가정해 더 깊은 카드는 10열 칸이 밀렸다.
    int matCardKeyIndent = 0;
    int matCardBaseIndent = -1;  // 첫 내용 줄의 들여쓰기
    std::string cardError;       // 카드 값 오류 — 발견 즉시 rc=1 로 끊는다

    // 따옴표 스칼라는 PyYAML 이 긴 값을 '\\' + 줄바꿈으로 접어 내보내므로 줄을 미리 모두 읽어 둔다
    std::vector<std::string> lines;
    {
        std::string raw;
        while (std::getline(f, raw)) {
            if (!raw.empty() && raw.back() == '\r') raw.pop_back();
            lines.push_back(raw);
        }
    }
    f.close();

    // 블록이 끝나는 자리에서 끝 빈 줄을 버린다(YAML clip) — 예전엔 파일 끝에서 한 번만 훑었다
    auto closeMatCard = [&]() {
        // 끝 빈 줄은 어느 chomping 지시자든 버린다 — assemble 과 같은 규칙(위 주석 참고)
        if (readingMatCard && !op.layers.empty())
            KooRemapper::yamlChompBlock(op.layers.back().materialCard, ' ');
        readingMatCard = false;
    };

    for (size_t li = 0; li < lines.size(); ++li) {
        if (!cardError.empty()) { console.error("[restack] " + cardError); return 1; }
        const std::string& ln = lines[li];
        int indent = y.countIndent(ln);
        std::string tr = y.trim(ln);

        // 블록 내용 판정은 assemble(AssemblyConfigReader)과 같은 규칙이다 — 예전엔 여기만
        // '키 열보다 깊으면 내용' 으로 봐 '|4' 같은 명시 들여쓰기 지시자를 사실상 무시했고,
        // 같은 YAML 이 단독은 rc=0 덱, assemble 은 rc=1 로 갈렸다. 빈 줄·'#' 줄 건너뛰기도
        // 블록 읽기 뒤로 옮긴다('#' 로 시작하는 카드 줄은 주석이 아니라 내용이다).
        if (readingMatCard) {
            KooRemapper::YamlBlockLineKind kind =
                KooRemapper::yamlClassifyBlockLine(tr, indent, matCardKeyIndent, matCardBaseIndent);
            if (kind == KooRemapper::YamlBlockLineKind::BLANK) {
                // *MAT_..._TITLE 의 제목 줄 자리면 남긴다(버리면 데이터 줄이 한 줄 밀려 읽힌다).
                // 그 밖의 빈 줄은 버린다 — 남기면 LS-DYNA 가 칸이 모두 0 인 데이터 줄로 읽는다.
                if (!op.layers.empty() &&
                    KooRemapper::yamlCardBlankIsTitleSlot(op.layers.back().materialCard))
                    op.layers.back().materialCard += "\n";
                continue;
            }
            if (kind == KooRemapper::YamlBlockLineKind::TOO_SHALLOW) {
                cardError = KooRemapper::yamlShallowBlockMessage("material_card", indent, matCardBaseIndent);
                continue;
            }
            if (kind == KooRemapper::YamlBlockLineKind::CONTENT) {
                if (matCardBaseIndent < 0) matCardBaseIndent = indent;
                if (!op.layers.empty())
                    op.layers.back().materialCard += ln.substr(matCardBaseIndent) + "\n";
                continue;
            }
            closeMatCard();
        }
        if (tr.empty() || tr[0]=='#') continue;

        if (inLayers && indent <= layersIndent && tr.substr(0,2) != "- " && tr != "-") {
            inLayers = false;
        }

        // '-' 만 있는 줄로 여는 층 항목도 정상 YAML 이다 — 키는 다음 줄부터 온다(예전엔
        // '- ' 만 항목으로 보아 그런 층 목록을 하나도 못 읽고 'no layers defined' 로 거부했다)
        if (inLayers && KooRemapper::yamlTrimEdges(KooRemapper::yamlStripComment(tr)) == "-") {
            op.layers.push_back({});
            continue;
        }

        size_t cp = tr.find(':');
        if (cp == std::string::npos) continue;
        std::string key = y.keyOf(tr, cp);
        std::string val = y.stripQuotes(y.trim(KooRemapper::yamlStripComment(tr.substr(cp+1))));
        std::string rawVal = y.trim(tr.substr(cp+1));   // 카드 키는 따옴표를 스스로 푼다

        if (!inLayers) {
            y.parseCommonKey(key, val);
            // op 수준 키도 assemble 과 같은 집합 — 예전엔 interface_contact·element_size·czm_* 를 몰라
            // 같은 YAML 이 명령에 따라 다른 덱이 됐다(매뉴얼은 같은 알고리즘이라고 약속한다)
            if      (key == "target_pid") { try { op.targetPid = std::stoi(val); } catch(...) {} }
            else if (key == "direction") op.direction = val;
            else if (key == "element_type") op.elementType = val;
            else if (key == "element_size") { try { op.elementSize = std::stod(val); } catch(...) {} }
            else if (key == "interface_contact") op.interfaceContact = val;
            else if (key == "czm_normal") { try { op.czmNormal = std::stod(val); } catch(...) {} }
            else if (key == "czm_shear") { try { op.czmShear = std::stod(val); } catch(...) {} }
            else if (key == "drop_height") { try { op.dropHeight = std::stod(val); } catch(...) {} }
            // pid_refs 는 rc=1 강제의 유일한 탈출구다 — 읽는 자리가 없어 'warn' 이 통하지 않았다
            else if (key == "pid_refs") op.pidRefs = val;
            else if (key == "layers") { inLayers = true; layersIndent = y.keyIndent(tr, indent); }
            continue;
        }

        // 층 키 — assemble 과 같은 집합을 읽는다. 예전엔 thickness·material_card 만 읽어
        // title 은 'Restack Layer N' 으로, num_elements·element_type 은 무시돼 층 분할이 달라졌다.
        auto applyLayerKey = [&](const std::string& k, const std::string& v,
                                 const std::string& rawV, int blockKeyIndent) {
            RestackLayer& L = op.layers.back();
            if      (k == "thickness")    { try { L.thickness = std::stod(v); } catch(...) {} }
            else if (k == "num_elements" || k == "nz") { try { L.numElements = std::stoi(v); } catch(...) {} }
            else if (k == "element_type") L.elementType = v;
            else if (k == "title" || k == "name") L.title = v;
            else if (k == "czm_normal")   { try { L.czmNormal = std::stod(v); } catch(...) {} }
            else if (k == "czm_shear")    { try { L.czmShear = std::stod(v); } catch(...) {} }
            else if (k == "material_card") {
                // assemble(AssemblyConfigReader)과 같은 규칙 — 블록 지시자 전 종류와 따옴표 스칼라를
                // 똑같이 다룬다. 예전엔 v == "|" 정확 비교라 '|-' 나 따옴표 카드가 그대로 카드가 됐다.
                std::string vv = y.trim(KooRemapper::yamlStripComment(rawV));
                KooRemapper::YamlBlockHeader h = KooRemapper::yamlParseBlockHeader(vv);
                if (h.isBlock) {
                    if (h.folded) { cardError = KooRemapper::yamlFoldedCardMessage("material_card"); return; }
                    readingMatCard = true; matCardKeyIndent = blockKeyIndent;
                    matCardBaseIndent = (h.indent > 0) ? blockKeyIndent + h.indent : -1;
                } else if (vv.empty()) {
                    cardError = "material_card: 값이 비어 있습니다 — '|' 블록이나 따옴표 문자열로 "
                                "카드를 주세요 / empty value";
                } else if (rawV[0] == '"' || rawV[0] == '\'') {
                    std::string joined; size_t endLine = li;
                    if (!KooRemapper::yamlJoinQuotedScalar(lines, li, rawV, joined, endLine)) {
                        cardError = "material_card: 따옴표가 닫히지 않았습니다 / unterminated quoted scalar";
                        return;
                    }
                    li = endLine;
                    L.materialCard = KooRemapper::yamlDecodeQuotedScalar(joined);
                    KooRemapper::yamlChompBlock(L.materialCard, ' ');
                } else {
                    L.materialCard = vv;
                    KooRemapper::yamlChompBlock(L.materialCard, ' ');
                }
            }
        };

        // Layer list
        if (tr.substr(0,2) == "- ") {
            op.layers.push_back({});
            std::string rest = y.trim(tr.substr(2));
            size_t rcp = rest.find(':');
            if (rcp != std::string::npos) {
                std::string rk = y.trim(rest.substr(0, rcp));
                // 예전엔 대시 줄 값의 주석을 안 떼 'material_card: |  # 메모' 층을 카드 없음으로, '"0.2"  # 메모' 를 잘못된 두께로 봤다
                std::string rv = y.stripQuotes(y.trim(KooRemapper::yamlStripComment(rest.substr(rcp+1))));
                applyLayerKey(rk, rv, y.trim(rest.substr(rcp+1)), y.keyIndent(tr, indent));
            }
            continue;
        }
        if (!op.layers.empty()) {
            applyLayerKey(key, val, rawVal, indent);
        }
    }
    // 파일 끝에서 끝난 블록도 chomping 을 적용한다(YAML '|' 는 clip — 끝 빈 줄을 버린다).
    // 남겨 두면 층 카드 뒤 빈 줄이 덱에 그대로 찍혀 같은 YAML 인데 assemble 결과와 달라진다.
    closeMatCard();
    if (!cardError.empty()) { console.error("[restack] " + cardError); return 1; }

    if (y.modelFile.empty()) { console.error("[restack] model not specified"); return 1; }
    std::string modelPath = y.resolvePath(y.modelFile);
    if (rejectEmptyOutput(y, "restack", console)) return 1;
    std::string outputPrefix = y.getOutputPrefix();

    console.println("[restack] Model: " + modelPath);
    if (!validateLikeAssemble(AssemblyOperation::RESTACK, &AssemblyOperation::restack, op, "restack", console)) return 1;
    ModelAssembler assembler;
    if (!assembler.loadBaseModel(modelPath)) { console.error(assembler.getErrorMessage()); return 1; }
    if (!assembler.applyRestack(op, y.matE, y.matNu)) { console.error(assembler.getErrorMessage()); return 1; }
    for (const auto& msg : assembler.infoMessages) console.println(msg);
    if (!writeOutputChecked(assembler, outputPrefix, "restack", console)) return 1;
    console.println("[restack] Done -> " + outputPrefix + ".k");
    return 0;
}

// ── Standalone bend ─────────────────────────────────────────────────────────
int runBend(const std::string& yamlFile, ConsoleOutput& console) {
    {   // 탭으로 들여쓴 YAML 은 블록이 통째로 무너져 조용히 아무 일도 안 했다 — 파싱 전에 거른다
        std::string tabLine;
        if (KooRemapper::yamlScanTabIndent(yamlFile, tabLine)) {
            console.error(KooRemapper::yamlTabIndentMessage("bend", tabLine));
            return 1;
        }
    }
    StandaloneYamlBase y;
    y.resolveFiles(yamlFile);
    if (rejectMultiOperation(yamlFile, "bend", console)) return 1;

    std::ifstream f(yamlFile);
    if (!f.is_open()) { console.error("Cannot open: " + yamlFile); return 1; }
    KooRemapper::yamlSkipBOM(f);   // 윈도우 편집기가 붙인 BOM 이 첫 키를 망가뜨렸다

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
    if (rejectEmptyOutput(y, "bend", console)) return 1;
    std::string outputPrefix = y.getOutputPrefix();

    console.println("[bend] Model: " + modelPath);
    if (!validateLikeAssemble(AssemblyOperation::BEND, &AssemblyOperation::bend, op, "bend", console)) return 1;
    ModelAssembler assembler;
    if (!assembler.loadBaseModel(modelPath)) { console.error(assembler.getErrorMessage()); return 1; }
    if (!assembler.applyBend(op, y.matE, y.matNu, y.configDir)) { console.error(assembler.getErrorMessage()); return 1; }
    for (const auto& msg : assembler.infoMessages) console.println(msg);
    if (!writeOutputChecked(assembler, outputPrefix, "bend", console)) return 1;
    console.println("[bend] Done -> " + outputPrefix + ".k");
    return 0;
}

// ── Standalone indent ───────────────────────────────────────────────────────
int runIndent(const std::string& yamlFile, ConsoleOutput& console) {
    {   // 탭으로 들여쓴 YAML 은 블록이 통째로 무너져 조용히 아무 일도 안 했다 — 파싱 전에 거른다
        std::string tabLine;
        if (KooRemapper::yamlScanTabIndent(yamlFile, tabLine)) {
            console.error(KooRemapper::yamlTabIndentMessage("indent", tabLine));
            return 1;
        }
    }
    StandaloneYamlBase y;
    y.resolveFiles(yamlFile);
    if (rejectMultiOperation(yamlFile, "indent", console)) return 1;

    std::ifstream f(yamlFile);
    if (!f.is_open()) { console.error("Cannot open: " + yamlFile); return 1; }
    KooRemapper::yamlSkipBOM(f);   // 윈도우 편집기가 붙인 BOM 이 첫 키를 망가뜨렸다

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
    if (rejectEmptyOutput(y, "indent", console)) return 1;
    std::string outputPrefix = y.getOutputPrefix();

    console.println("[indent] Model: " + modelPath);
    if (!validateLikeAssemble(AssemblyOperation::INDENT, &AssemblyOperation::indent, op, "indent", console)) return 1;
    ModelAssembler assembler;
    if (!assembler.loadBaseModel(modelPath)) { console.error(assembler.getErrorMessage()); return 1; }
    if (!assembler.applyIndent(op, y.matE, y.matNu)) { console.error(assembler.getErrorMessage()); return 1; }
    for (const auto& msg : assembler.infoMessages) console.println(msg);
    if (!writeOutputChecked(assembler, outputPrefix, "indent", console)) return 1;
    console.println("[indent] Done -> " + outputPrefix + ".k");
    return 0;
}

// ── Standalone formstrain ───────────────────────────────────────────────────
int runFormstrain(const std::string& yamlFile, ConsoleOutput& console) {
    {   // 탭으로 들여쓴 YAML 은 블록이 통째로 무너져 조용히 아무 일도 안 했다 — 파싱 전에 거른다
        std::string tabLine;
        if (KooRemapper::yamlScanTabIndent(yamlFile, tabLine)) {
            console.error(KooRemapper::yamlTabIndentMessage("formstrain", tabLine));
            return 1;
        }
    }
    StandaloneYamlBase y;
    y.resolveFiles(yamlFile);
    if (rejectMultiOperation(yamlFile, "formstrain", console)) return 1;

    std::ifstream f(yamlFile);
    if (!f.is_open()) { console.error("Cannot open: " + yamlFile); return 1; }
    KooRemapper::yamlSkipBOM(f);   // 윈도우 편집기가 붙인 BOM 이 첫 키를 망가뜨렸다

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
    if (rejectEmptyOutput(y, "formstrain", console)) return 1;
    std::string outputPrefix = y.getOutputPrefix();

    console.println("[formstrain] Model: " + modelPath);
    ModelAssembler assembler;
    if (!assembler.loadBaseModel(modelPath)) { console.error(assembler.getErrorMessage()); return 1; }
    if (!assembler.applyFormStrain(op)) { console.error(assembler.getErrorMessage()); return 1; }
    for (const auto& msg : assembler.infoMessages) console.println(msg);
    if (!writeOutputChecked(assembler, outputPrefix, "formstrain", console)) return 1;
    console.println("[formstrain] Done -> " + outputPrefix + ".k");
    return 0;
}

// ── Standalone convert (tet10/hex20/quad8/tria6) ────────────────────────────
int runConvert(const std::string& yamlFile, ConsoleOutput& console) {
    {   // 탭으로 들여쓴 YAML 은 블록이 통째로 무너져 조용히 아무 일도 안 했다 — 파싱 전에 거른다
        std::string tabLine;
        if (KooRemapper::yamlScanTabIndent(yamlFile, tabLine)) {
            console.error(KooRemapper::yamlTabIndentMessage("convert", tabLine));
            return 1;
        }
    }
    StandaloneYamlBase y;
    y.resolveFiles(yamlFile);
    if (rejectMultiOperation(yamlFile, "convert", console)) return 1;

    std::ifstream f(yamlFile);
    if (!f.is_open()) { console.error("Cannot open: " + yamlFile); return 1; }
    KooRemapper::yamlSkipBOM(f);   // 윈도우 편집기가 붙인 BOM 이 첫 키를 망가뜨렸다

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
    if (rejectEmptyOutput(y, "convert", console)) return 1;
    std::string outputPrefix = y.getOutputPrefix();

    console.println("[convert] Model: " + modelPath);
    console.println("[convert] Type: " + op.convertType);
    ModelAssembler assembler;
    if (!assembler.loadBaseModel(modelPath)) { console.error(assembler.getErrorMessage()); return 1; }
    if (!assembler.applyTet10Convert(op)) { console.error(assembler.getErrorMessage()); return 1; }
    for (const auto& msg : assembler.infoMessages) console.println(msg);
    if (!writeOutputChecked(assembler, outputPrefix, "convert", console)) return 1;
    console.println("[convert] Done -> " + outputPrefix + ".k");
    return 0;
}

// ── Standalone refine ───────────────────────────────────────────────────────
int runRefine(const std::string& yamlFile, ConsoleOutput& console) {
    {   // 탭으로 들여쓴 YAML 은 블록이 통째로 무너져 조용히 아무 일도 안 했다 — 파싱 전에 거른다
        std::string tabLine;
        if (KooRemapper::yamlScanTabIndent(yamlFile, tabLine)) {
            console.error(KooRemapper::yamlTabIndentMessage("refine", tabLine));
            return 1;
        }
    }
    StandaloneYamlBase y;
    y.resolveFiles(yamlFile);
    if (rejectMultiOperation(yamlFile, "refine", console)) return 1;

    std::ifstream f(yamlFile);
    if (!f.is_open()) { console.error("Cannot open: " + yamlFile); return 1; }
    KooRemapper::yamlSkipBOM(f);   // 윈도우 편집기가 붙인 BOM 이 첫 키를 망가뜨렸다

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
    if (rejectEmptyOutput(y, "refine", console)) return 1;
    std::string outputPrefix = y.getOutputPrefix();

    console.println("[refine] Model: " + modelPath);
    ModelAssembler assembler;
    if (!assembler.loadBaseModel(modelPath)) { console.error(assembler.getErrorMessage()); return 1; }
    if (!assembler.applyRefine(op)) { console.error(assembler.getErrorMessage()); return 1; }
    for (const auto& msg : assembler.infoMessages) console.println(msg);
    if (!writeOutputChecked(assembler, outputPrefix, "refine", console)) return 1;
    console.println("[refine] Done -> " + outputPrefix + ".k");
    return 0;
}

// ── Standalone elform ───────────────────────────────────────────────────────
int runElform(const std::string& yamlFile, ConsoleOutput& console) {
    {   // 탭으로 들여쓴 YAML 은 블록이 통째로 무너져 조용히 아무 일도 안 했다 — 파싱 전에 거른다
        std::string tabLine;
        if (KooRemapper::yamlScanTabIndent(yamlFile, tabLine)) {
            console.error(KooRemapper::yamlTabIndentMessage("elform", tabLine));
            return 1;
        }
    }
    StandaloneYamlBase y;
    y.resolveFiles(yamlFile);
    if (rejectMultiOperation(yamlFile, "elform", console)) return 1;

    std::ifstream f(yamlFile);
    if (!f.is_open()) { console.error("Cannot open: " + yamlFile); return 1; }
    KooRemapper::yamlSkipBOM(f);   // 윈도우 편집기가 붙인 BOM 이 첫 키를 망가뜨렸다

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
    if (rejectEmptyOutput(y, "elform", console)) return 1;
    std::string outputPrefix = y.getOutputPrefix();

    console.println("[elform] Model: " + modelPath);
    ModelAssembler assembler;
    if (!assembler.loadBaseModel(modelPath)) { console.error(assembler.getErrorMessage()); return 1; }
    if (!assembler.applyElform(op)) { console.error(assembler.getErrorMessage()); return 1; }
    for (const auto& msg : assembler.infoMessages) console.println(msg);
    if (!writeOutputChecked(assembler, outputPrefix, "elform", console)) return 1;
    console.println("[elform] Done -> " + outputPrefix + ".k");
    return 0;
}

// ── Standalone disconnect ───────────────────────────────────────────────────
int runDisconnect(const std::string& yamlFile, ConsoleOutput& console) {
    {   // 탭으로 들여쓴 YAML 은 블록이 통째로 무너져 조용히 아무 일도 안 했다 — 파싱 전에 거른다
        std::string tabLine;
        if (KooRemapper::yamlScanTabIndent(yamlFile, tabLine)) {
            console.error(KooRemapper::yamlTabIndentMessage("disconnect", tabLine));
            return 1;
        }
    }
    StandaloneYamlBase y;
    y.resolveFiles(yamlFile);
    if (rejectMultiOperation(yamlFile, "disconnect", console)) return 1;

    std::ifstream f(yamlFile);
    if (!f.is_open()) { console.error("Cannot open: " + yamlFile); return 1; }
    KooRemapper::yamlSkipBOM(f);   // 윈도우 편집기가 붙인 BOM 이 첫 키를 망가뜨렸다

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
    if (rejectEmptyOutput(y, "disconnect", console)) return 1;
    std::string outputPrefix = y.getOutputPrefix();

    console.println("[disconnect] Model: " + modelPath);
    ModelAssembler assembler;
    if (!assembler.loadBaseModel(modelPath)) { console.error(assembler.getErrorMessage()); return 1; }
    if (!assembler.applyDisconnect(op)) { console.error(assembler.getErrorMessage()); return 1; }
    for (const auto& msg : assembler.infoMessages) console.println(msg);
    if (!writeOutputChecked(assembler, outputPrefix, "disconnect", console)) return 1;
    console.println("[disconnect] Done -> " + outputPrefix + ".k");
    return 0;
}

// ── Standalone iga ──────────────────────────────────────────────────────────
int runIga(const std::string& yamlFile, ConsoleOutput& console) {
    {   // 탭으로 들여쓴 YAML 은 블록이 통째로 무너져 조용히 아무 일도 안 했다 — 파싱 전에 거른다
        std::string tabLine;
        if (KooRemapper::yamlScanTabIndent(yamlFile, tabLine)) {
            console.error(KooRemapper::yamlTabIndentMessage("iga", tabLine));
            return 1;
        }
    }
    StandaloneYamlBase y;
    y.resolveFiles(yamlFile);
    if (rejectMultiOperation(yamlFile, "iga", console)) return 1;

    std::ifstream f(yamlFile);
    if (!f.is_open()) { console.error("Cannot open: " + yamlFile); return 1; }
    KooRemapper::yamlSkipBOM(f);   // 윈도우 편집기가 붙인 BOM 이 첫 키를 망가뜨렸다

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
    if (rejectEmptyOutput(y, "iga", console)) return 1;
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
    if (!writeOutputChecked(assembler, outputPrefix, "iga", console)) return 1;
    console.println("[iga] Done -> " + outputPrefix + ".k");
    return 0;
}

// ── Standalone warpage ──────────────────────────────────────────────────────
int runWarpage(const std::string& yamlFile, ConsoleOutput& console) {
    {   // 탭으로 들여쓴 YAML 은 블록이 통째로 무너져 조용히 아무 일도 안 했다 — 파싱 전에 거른다
        std::string tabLine;
        if (KooRemapper::yamlScanTabIndent(yamlFile, tabLine)) {
            console.error(KooRemapper::yamlTabIndentMessage("warpage", tabLine));
            return 1;
        }
    }
    StandaloneYamlBase y;
    y.resolveFiles(yamlFile);
    if (rejectMultiOperation(yamlFile, "warpage", console)) return 1;

    std::ifstream f(yamlFile);
    if (!f.is_open()) { console.error("Cannot open: " + yamlFile); return 1; }
    KooRemapper::yamlSkipBOM(f);   // 윈도우 편집기가 붙인 BOM 이 첫 키를 망가뜨렸다

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
    if (rejectEmptyOutput(y, "warpage", console)) return 1;
    std::string outputPrefix = y.getOutputPrefix();

    console.println("[warpage] Model: " + modelPath);
    ModelAssembler assembler;
    if (!assembler.loadBaseModel(modelPath)) { console.error(assembler.getErrorMessage()); return 1; }
    if (!assembler.applyWarpage(op, y.matE, y.matNu, y.configDir)) { console.error(assembler.getErrorMessage()); return 1; }
    for (const auto& msg : assembler.infoMessages) console.println(msg);
    if (!writeOutputChecked(assembler, outputPrefix, "warpage", console)) return 1;
    console.println("[warpage] Done -> " + outputPrefix + ".k");
    return 0;
}

// ── Standalone offset ───────────────────────────────────────────────────────
int runOffset(const std::string& yamlFile, ConsoleOutput& console) {
    {   // 탭으로 들여쓴 YAML 은 블록이 통째로 무너져 조용히 아무 일도 안 했다 — 파싱 전에 거른다
        std::string tabLine;
        if (KooRemapper::yamlScanTabIndent(yamlFile, tabLine)) {
            console.error(KooRemapper::yamlTabIndentMessage("offset", tabLine));
            return 1;
        }
    }
    StandaloneYamlBase y;
    y.resolveFiles(yamlFile);
    if (rejectMultiOperation(yamlFile, "offset", console)) return 1;

    std::ifstream f(yamlFile);
    if (!f.is_open()) { console.error("Cannot open: " + yamlFile); return 1; }
    KooRemapper::yamlSkipBOM(f);   // 윈도우 편집기가 붙인 BOM 이 첫 키를 망가뜨렸다

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
    bool sawMatCardsKey = false;   // material_cards 를 줬는데 카드가 0개면 조용히 넘기지 않는다
    std::string cardError;         // 카드 값 오류 — 발견 즉시 rc=1 로 끊는다

    // 따옴표 스칼라는 PyYAML 이 긴 값을 '\\' + 줄바꿈으로 접어 내보내므로 줄을 미리 모두 읽어 둔다
    std::vector<std::string> lines;
    {
        std::string raw;
        while (std::getline(f, raw)) {
            if (!raw.empty() && raw.back() == '\r') raw.pop_back();
            lines.push_back(raw);
        }
    }
    f.close();

    size_t li = 0;   // 따옴표 스칼라가 여러 줄에 걸치면 아래 람다가 이 값을 건너뛴다

    std::string matCardKeyName = "material_card";   // 얕은 내용 줄 메시지에 쓸 카드 키 이름
    // 블록이 끝날 때 chomping 을 적용한다 — assemble 과 같게 끝 빈 줄을 버린다(clip/strip)
    auto closeOffsetCard = [&]() {
        // 끝 빈 줄은 어느 chomping 지시자든 버린다 — assemble 과 같은 규칙
        if (readingMatCard)            KooRemapper::yamlChompBlock(op.materialCard, ' ');
        else if (readingCzmMatCard)    KooRemapper::yamlChompBlock(op.czmMaterialCard, ' ');
        else if (readingMatCardsItem && !op.materialCards.empty())
            KooRemapper::yamlChompBlock(op.materialCards.back(), ' ');
        readingMatCard = false;
        readingCzmMatCard = false;
        readingMatCardsItem = false;
    };
    // 카드 키 한 줄 — 블록 머리표 전 종류와 따옴표 스칼라를 assemble 과 같은 규칙으로 읽는다
    auto startOffsetCard = [&](const char* keyName, const std::string& rawV, int blockKeyIndent,
                               std::string& dst, bool& readingFlag) {
        std::string vv = y.trim(KooRemapper::yamlStripComment(rawV));
        KooRemapper::YamlBlockHeader h = KooRemapper::yamlParseBlockHeader(vv);
        if (h.isBlock) {
            if (h.folded) { cardError = KooRemapper::yamlFoldedCardMessage(keyName); return; }
            readingFlag = true; matCardKeyIndent = blockKeyIndent;
            matCardBaseIndent = (h.indent > 0) ? blockKeyIndent + h.indent : -1;
            matCardKeyName = keyName;
            return;
        }
        if (vv.empty()) {
            cardError = std::string(keyName) + ": 값이 비어 있습니다 — '|' 블록이나 따옴표 문자열로 "
                        "카드를 주세요 / empty value";
            return;
        }
        if (rawV[0] == '"' || rawV[0] == '\'') {
            std::string joined; size_t endLine = li;
            if (!KooRemapper::yamlJoinQuotedScalar(lines, li, rawV, joined, endLine)) {
                cardError = std::string(keyName) + ": 따옴표가 닫히지 않았습니다 / unterminated quoted scalar";
                return;
            }
            li = endLine;
            dst = KooRemapper::yamlDecodeQuotedScalar(joined);
        } else {
            dst = vv;
        }
        KooRemapper::yamlChompBlock(dst, ' ');
    };

    for (li = 0; li < lines.size(); ++li) {
        if (!cardError.empty()) { console.error("[offset] " + cardError); return 1; }
        const std::string& ln = lines[li];
        int indent = y.countIndent(ln);
        std::string tr = y.trim(ln);
        // 블록 내용 판정은 assemble(AssemblyConfigReader)·단독 restack 과 같은 규칙이다.
        // '#' 로 시작하는 줄도 블록 안에서는 주석이 아니라 카드 내용이고, 빈 줄은 양쪽 다 버린다.
        if (readingMatCard || readingCzmMatCard || readingMatCardsItem) {
            KooRemapper::YamlBlockLineKind kind =
                KooRemapper::yamlClassifyBlockLine(tr, indent, matCardKeyIndent, matCardBaseIndent);
            if (kind == KooRemapper::YamlBlockLineKind::BLANK) continue;
            if (kind == KooRemapper::YamlBlockLineKind::TOO_SHALLOW) {
                cardError = KooRemapper::yamlShallowBlockMessage(matCardKeyName, indent, matCardBaseIndent);
                continue;
            }
            if (kind == KooRemapper::YamlBlockLineKind::CONTENT) {
                if (matCardBaseIndent < 0) matCardBaseIndent = indent;
                std::string content = ln.substr(matCardBaseIndent) + "\n";
                if (readingMatCard)            op.materialCard += content;
                else if (readingCzmMatCard)    op.czmMaterialCard += content;
                else if (!op.materialCards.empty()) op.materialCards.back() += content;
                continue;
            }
            // 블록 끝 — material_cards 항목은 아래 목록 처리가 다음 '- |' 를 보고 닫는다
            if (!readingMatCardsItem) closeOffsetCard();
        }

        if (tr.empty() || tr[0]=='#') continue;

        if (inMatCardsList) {
            // 예전엔 '- |   # 메모' 항목을 못 알아봐 목록이 끊기고 층 재질이 빠졌다.
            // 대시를 키와 같은 열에 쓰는 블록 목록도 YAML 에서 합법인데 '>' 로 걸러 통째로 버렸다(D4).
            // '- |-' '- |2' 처럼 지시자가 붙은 항목도 같은 블록이다.
            std::string item = y.trim(KooRemapper::yamlStripComment(tr));
            KooRemapper::YamlBlockHeader ih;
            if (!item.empty() && item[0] == '-')
                ih = KooRemapper::yamlParseBlockHeader(y.trim(item.substr(1)));
            if (indent >= matCardsKeyIndent && ih.isBlock) {
                if (ih.folded) { console.error("[offset] " + KooRemapper::yamlFoldedCardMessage("material_cards")); return 1; }
                closeOffsetCard();
                op.materialCards.emplace_back();
                readingMatCardsItem = true;
                matCardKeyIndent = indent;
                matCardBaseIndent = (ih.indent > 0) ? indent + ih.indent : -1;
                matCardKeyName = "material_cards";
                continue;
            }
            closeOffsetCard();
            inMatCardsList = false;
        }

        size_t cp = tr.find(':');
        if (cp == std::string::npos) continue;
        std::string key = y.keyOf(tr, cp);
        std::string val = y.stripQuotes(y.trim(KooRemapper::yamlStripComment(tr.substr(cp+1))));
        std::string rawVal = y.trim(tr.substr(cp+1));   // 카드 키는 따옴표를 스스로 푼다

        y.parseCommonKey(key, val);
        if      (key == "source_pid") { try { op.sourcePid = std::stoi(val); } catch(...) {} }
        else if (key == "material_cards" && val.empty()) { inMatCardsList = true; sawMatCardsKey = true; matCardsKeyIndent = y.keyIndent(tr, indent); }
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
        // 예전엔 val == "|" 정확 비교라 '|-' 나 따옴표 카드가 else 로 빠져 아예 버려졌다 —
        // 카드 없이 돌면 층 PART 가 덱에 없는 MID 를 가리킨다
        else if (key == "material_card") { startOffsetCard("material_card", rawVal, y.keyIndent(tr, indent), op.materialCard, readingMatCard); }
        else if (key == "czm_material_card") { startOffsetCard("czm_material_card", rawVal, y.keyIndent(tr, indent), op.czmMaterialCard, readingCzmMatCard); }
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
    // 파일 끝에서 끝난 블록도 chomping 을 적용한다(clip — 끝 빈 줄을 버린다)
    closeOffsetCard();
    if (!cardError.empty()) { console.error("[offset] " + cardError); return 1; }

    if (y.modelFile.empty()) { console.error("[offset] model not specified"); return 1; }
    // 카드 없이 돌면 층 PART 가 덱에 없는 MID 를 가리켜 LS-DYNA 가 죽는다 — 파싱이 실패하면 오류로 알린다
    if (sawMatCardsKey && op.materialCards.empty()) {
        console.error("[offset] material_cards 에 '- |' 블록 항목이 하나도 없습니다 / "
                      "material_cards has no '- |' block items.");
        return 1;
    }
    std::string modelPath = y.resolvePath(y.modelFile);
    if (rejectEmptyOutput(y, "offset", console)) return 1;
    std::string outputPrefix = y.getOutputPrefix();

    console.println("[offset] Model: " + modelPath);
    if (!validateLikeAssemble(AssemblyOperation::OFFSET, &AssemblyOperation::offset, op, "offset", console)) return 1;
    ModelAssembler assembler;
    if (!assembler.loadBaseModel(modelPath)) { console.error(assembler.getErrorMessage()); return 1; }
    if (!assembler.applyOffset(op, y.matE, y.matNu)) { console.error(assembler.getErrorMessage()); return 1; }
    for (const auto& msg : assembler.infoMessages) console.println(msg);
    if (!writeOutputChecked(assembler, outputPrefix, "offset", console)) return 1;
    console.println("[offset] Done -> " + outputPrefix + ".k");
    return 0;
}
