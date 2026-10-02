// 적층을 EI 중립축 기준으로 옮긴 뒤 기준 셸에 감는 op — shellmap 의 "축=0 이 중립면" 전제를 실제로 맞춘다.
#include "stackwrap.h"

#include "assembly/ModelAssembler.h"
#include "cli/ConsoleOutput.h"
#include "commands/core_ops.h"
#include "commands/neutralaxis.h"
#include "core/Mesh.h"
#include "parser/KFileReader.h"
#include "util/YamlComment.h"

#include <cmath>
#include <cstdio>
#include <fstream>
#include <string>

using KooRemapper::ConsoleOutput;
using KooRemapper::Mesh;
using KooRemapper::KFileReader;
using KooRemapper::yamlStripComment;

namespace {

struct Config {
    std::string bentShell;
    std::string flatStack;
    std::string output;       // 접두어 — <output>.k 와 <output>_neutral.k 를 쓴다
    double thickness = 0.0;   // 0 = shellmap 자동 탐지
    int axis = 2;             // 적층 방향(중립축을 재는 축)
    bool shift = true;        // false = 옮기지 않고 그대로 감는다(대조용)
};

std::string trim(const std::string& s) {
    size_t a = s.find_first_not_of(" \t");
    if (a == std::string::npos) return "";
    size_t b = s.find_last_not_of(" \t\r");
    return s.substr(a, b - a + 1);
}

std::string num(const char* f, double v) {
    char b[64];
    std::snprintf(b, sizeof(b), f, v);
    return std::string(b);
}

bool parseYaml(const std::string& path, Config& c, ConsoleOutput& console) {
    std::ifstream f(path);
    if (!f.is_open()) { console.error("Cannot open: " + path); return false; }
    KooRemapper::yamlSkipBOM(f);
    std::string ln;
    while (std::getline(f, ln)) {
        if (!ln.empty() && ln.back() == '\r') ln.pop_back();
        std::string t = trim(ln);
        if (t.empty() || t[0] == '#') continue;
        size_t cp = t.find(':');
        if (cp == std::string::npos) continue;
        const std::string key = trim(t.substr(0, cp));
        const std::string val = trim(yamlStripComment(t.substr(cp + 1)));
        if (val.empty()) continue;
        try {
            if      (key == "bent_shell") c.bentShell = val;
            else if (key == "flat_stack") c.flatStack = val;
            else if (key == "output")     c.output = val;
            else if (key == "thickness")  c.thickness = std::stod(val);
            else if (key == "shift")      c.shift = (val == "true" || val == "yes" || val == "1");
            else if (key == "axis") {
                if      (val == "x") c.axis = 0;
                else if (val == "y") c.axis = 1;
                else if (val == "z") c.axis = 2;
                else { console.error("axis: 는 x, y, z 중 하나여야 한다 (받은 값: " + val + ")"); return false; }
            }
            else console.warning("모르는 키는 무시한다: " + key);
        } catch (const std::exception&) {
            console.error("숫자를 읽을 수 없다: " + key + ": " + val);
            return false;
        }
    }
    return true;
}

}  // namespace

int runStackWrap(const std::string& yamlFile, ConsoleOutput& console) {
    Config c;
    if (!parseYaml(yamlFile, c, console)) return 1;
    if (c.bentShell.empty()) { console.error("bent_shell: 이 필요하다"); return 1; }
    if (c.flatStack.empty()) { console.error("flat_stack: 이 필요하다"); return 1; }
    if (c.output.empty())    { console.error("output: 이 필요하다"); return 1; }

    const char* axisName = c.axis == 0 ? "x" : (c.axis == 1 ? "y" : "z");

    console.header("Stack wrap (neutral-axis aligned)");
    console.keyValue("Bent shell", c.bentShell);
    console.keyValue("Flat stack", c.flatStack);
    console.keyValue("Stack axis", axisName);

    // ① 적층의 EI 중립축을 잰다
    KFileReader reader;
    Mesh mesh;
    try {
        mesh = reader.readFile(c.flatStack);
    } catch (const std::exception& e) {
        console.error("Failed to load flat stack: " + std::string(e.what()));
        return 1;
    }
    const NaResult na = computeNeutralAxis(mesh, c.axis);
    for (const auto& s : na.skipped) console.warning("중립축 제외: " + s);
    if (!na.ok) {
        console.error("중립축을 잴 수 없다 — 두께와 E 를 모두 읽은 파트가 0개다.");
        console.info("  적층의 모든 파트에 *MAT 와 (셸이면) *SECTION_SHELL 두께가 있어야 한다.");
        return 1;
    }
    console.keyValue("Layers", std::to_string(na.layers.size()));
    console.keyValue("Neutral axis", num("%.12g", na.neutral));
    console.keyValue("Geometric mid-plane", num("%.12g", na.geometric));
    console.keyValue("Stack extent", num("%.12g", na.stackLo) + " .. " + num("%.12g", na.stackHi));

    // ② 중립면이 축=0 에 오도록 옮긴다 — shellmap 이 그 전제로 법선 오프셋을 쓴다(§1-6)
    std::string mapInput = c.flatStack;
    if (!c.shift) {
        console.warning("shift: false — 옮기지 않고 그대로 감는다. shellmap 은 " +
                        std::string(axisName) + "=0 을 중립면으로 보므로 중립축이 " +
                        num("%.12g", na.neutral) + " 만큼 어긋난 채 매핑된다.");
    } else if (std::fabs(na.neutral) == 0.0) {
        console.info("중립축이 이미 " + std::string(axisName) + "=0 이다 — 옮길 것이 없다.");
    } else {
        const double d[3] = {c.axis == 0 ? -na.neutral : 0.0,
                             c.axis == 1 ? -na.neutral : 0.0,
                             c.axis == 2 ? -na.neutral : 0.0};
        KooRemapper::ModelAssembler asm_;
        if (!asm_.loadBaseModel(c.flatStack)) {
            console.error(asm_.getErrorMessage());
            return 1;
        }
        if (!asm_.applyTranslate(d[0], d[1], d[2])) {
            console.error(asm_.getErrorMessage());
            return 1;
        }
        const std::string shiftedPrefix = c.output + "_neutral";
        if (!asm_.writeOutput(shiftedPrefix)) {
            console.error(asm_.getErrorMessage());
            return 1;
        }
        for (const auto& m : asm_.infoMessages) console.info(m);
        mapInput = shiftedPrefix + ".k";
        console.keyValue("Shift applied", num("%.12g", -na.neutral) + " along " + axisName);
        console.success("Wrote shifted stack: " + mapInput);
    }

    // ③ 기준 셸에 감는다 — 매핑은 shellmap 과 **같은 경로**다(두 구현을 두지 않는다)
    const std::string outDeck = c.output + ".k";
    const int rc = runShellMapping(c.bentShell, mapInput, outDeck, c.thickness, console);
    if (rc != 0) {
        console.error("매핑이 실패했다 — 산출물을 믿지 말라.");
        return rc;
    }
    console.success("Stack wrap output: " + outDeck);
    return 0;
}
