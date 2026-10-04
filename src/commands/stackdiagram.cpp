// 적층 층 구조를 모식도로 그리는 op — 평면을 고를 필요가 없고 중립축을 함께 긋는다.
//
// `section` 과 무엇이 다른가. `section` 은 **실제 기하**를 평면으로 잘라 정확하다. 이 op 은
// 파트별 축 방향 범위(사실상 AABB)만 쓰는 **모식도**다. 그래서 둘의 쓸 자리가 갈린다.
//   · 평면을 고를 필요가 없다 — 축만 주면 된다(단면은 축을 잘못 고르면 61파트 중 1개만 만난다)
//   · 중립축·기하 중심면·굽힘강성을 **한 그림에** 긋는다(§1-6 의 이야기가 그림 하나로 보인다)
//   · ⚠ **AABB 라서 감긴/접힌 적층에서는 층이 갈리지 않는다.** 실측 — 감긴 덱 `wrapped.k` 의
//     세 파트가 z 범위가 전부 `0 ~ 1.0` 으로 **세 쌍 모두 겹친다.** 그 경우 그림을 내지 않고
//     `section` 을 쓰라고 말한다. 포개진 AABB 를 층처럼 그리면 그것이 가장 나쁜 거짓이다.
#include "stackdiagram.h"

#include "cli/ConsoleOutput.h"
#include "commands/neutralaxis.h"
#include "core/Mesh.h"
#include "core/Platform.h"
#include "parser/KFileReader.h"
#include "util/FigureSvg.h"
#include "util/YamlComment.h"

#include <algorithm>
#include <cmath>
#include <cstdio>
#include <fstream>
#include <map>
#include <string>
#include <vector>

using namespace KooRemapper;
using KooRemapper::figure::asciiOnly;
using KooRemapper::figure::colorFor;
using KooRemapper::figure::hexOf;
using KooRemapper::figure::isUtf8;
using KooRemapper::figure::xesc;

namespace {

struct Config {
    std::string model, output;
    int axis = 2;
    int width = 900, height = 700;
    int maxParts = 60;
    double minBarPx = 3.0;   // 얇은 층도 보이게 하는 바닥값 — 바닥 처리한 층은 **적는다**
    bool force = false;      // AABB 가 포개져도 그린다(사용자가 알고 쓸 때만)
    // 다른 층을 이만큼 이상 **안에 품는** 파트는 층이 아니라 감싸는 것이다(케이스·탭·파우치).
    // ⚠ 분수 문턱("전체의 90% 이상")을 쓰면 안 된다 — 실측으로 배터리 덱의 케이스가 88.4% 라
    //   간신히 빗나갔고, 그 88.4% 의 분모는 셸 띠가 양 끝으로 삐져나와 늘어난 값이었다.
    //   "품는가" 가 실제 기준이고 임의 상수가 없다.
    int enclosureMinInside = 2;
};

std::string trim(const std::string& s) {
    size_t a = s.find_first_not_of(" \t");
    if (a == std::string::npos) return "";
    size_t b = s.find_last_not_of(" \t\r");
    return s.substr(a, b - a + 1);
}

// 그릴 층들이 차지한 축 범위 — `na.sumT`/`na.stackLo` 는 **E 를 읽은 층만** 본다.
double loOf(const std::vector<NaLayer>& v) {
    double lo = 1e300;
    for (const NaLayer& L : v) lo = std::min(lo, L.c - 0.5 * L.t);
    return (lo < 1e300) ? lo : 0.0;
}
double hiOf(const std::vector<NaLayer>& v) {
    double hi = -1e300;
    for (const NaLayer& L : v) hi = std::max(hi, L.c + 0.5 * L.t);
    return (hi > -1e300) ? hi : 0.0;
}
double spanOf(const std::vector<NaLayer>& v) {
    const double d = hiOf(v) - loOf(v);
    return (d > 0.0) ? d : 1.0;
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
        const std::string t = trim(ln);
        if (t.empty() || t[0] == '#') continue;
        const size_t cp = t.find(':');
        if (cp == std::string::npos) continue;
        const std::string key = trim(t.substr(0, cp));
        const std::string val = trim(yamlStripComment(t.substr(cp + 1)));
        if (val.empty()) continue;
        try {
            if      (key == "model")      c.model = val;
            else if (key == "output")     c.output = val;
            else if (key == "width")      c.width = std::stoi(val);
            else if (key == "height")     c.height = std::stoi(val);
            else if (key == "max_parts")  c.maxParts = std::stoi(val);
            else if (key == "min_bar_px") c.minBarPx = std::stod(val);
            else if (key == "force")      c.force = (val == "true" || val == "yes" || val == "1");
            else if (key == "enclosure_min_inside") c.enclosureMinInside = std::stoi(val);
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

int runStackDiagram(const std::string& yamlFile, ConsoleOutput& console) {
    Config c;
    if (!parseYaml(yamlFile, c, console)) return 1;
    if (c.model.empty())  { console.error("model: 이 필요하다"); return 1; }
    if (c.output.empty()) { console.error("output: 이 필요하다"); return 1; }
    if (c.width < 430 || c.height < 240) {
        console.error("width 는 430 이상, height 는 240 이상이어야 한다 — 범례와 여백이 들어가야 한다.");
        return 1;
    }
    if (c.maxParts < 1)    { console.error("max_parts 는 1 이상이어야 한다"); return 1; }
    if (c.minBarPx < 0.0)  { console.error("min_bar_px 는 음수가 될 수 없다"); return 1; }
    if (c.enclosureMinInside < 1) {
        console.error("enclosure_min_inside 는 1 이상이어야 한다"); return 1;
    }

    KFileReader reader;
    Mesh mesh;
    try {
        mesh = reader.readFile(c.model);
    } catch (const std::exception& e) {
        console.error("Failed to load mesh: " + std::string(e.what()));
        return 1;
    }
    if (mesh.elements.empty()) {
        console.error("요소가 없다 — 이 덱에는 기하가 없다. 빈 그림을 내지 않는다.");
        return 1;
    }

    const char* AX = "xyz";
    console.header("Stack diagram: " + Platform::getFilename(c.model));
    console.keyValue("Axis", std::string(1, AX[c.axis]));

    // 층 목록·중립축은 `neutralaxis` 와 **같은 계산**을 쓴다 — 둘이 갈리면 안 된다.
    const NaResult na = computeNeutralAxis(mesh, c.axis);
    // ★제외 사유를 다 찍지 않는다 — 실측 배터리 덱은 `*MAT` 가 포함 파일에 있어 60줄이 쏟아진다.
    //   몇 개인지와 처음 몇 줄만 말하고, 나머지는 `neutralaxis` 가 보여 준다.
    {
        size_t shownSkip = 0;
        for (const auto& sk : na.skipped) {
            if (shownSkip++ < 3) console.warning("제외: " + sk);
        }
        if (na.skipped.size() > 3)
            console.warning("제외 " + std::to_string(na.skipped.size()) +
                            "개 — 나머지는 `neutralaxis` 로 보라.");
    }

    // 그릴 층 = E 를 읽은 층 + **두께만 읽은 층**. 모식도는 E 가 필요 없다 — 중립축만 필요하다.
    std::vector<NaLayer> bars = na.layers;
    bars.insert(bars.end(), na.geomOnly.begin(), na.geomOnly.end());
    std::sort(bars.begin(), bars.end(),
              [](const NaLayer& a, const NaLayer& b) { return a.c < b.c; });
    if (bars.empty()) {
        console.error("그릴 층이 없다 — 축 방향 두께를 읽은 파트가 0개다.");
        console.info("  셸이면 *SECTION_SHELL 두께가, 솔리드면 그 축 방향 범위가 있어야 한다.");
        return 1;
    }
    // ★**층이 아닌 파트**를 갈라낸다. 실측 — 배터리 적층 덱의 PID 13 은 z 0.153~2.478 로
    //   적층 **전체**를 감싸고(케이스·탭), 나머지 55개 얇은 층과 전부 겹친다. 그것을 층으로
    //   쌓으면 "55쌍 포개짐" 이 되어 그릴 수 없는 덱처럼 보인다 — 실은 층이 아닌 것 하나가
    //   섞인 것이다. 감싸는 파트는 **테두리로** 그리고 겹침 판정에서 뺀다.
    std::vector<NaLayer> encl;
    {
        const double eps = 1e-9 * std::max(1.0, spanOf(bars));
        std::vector<NaLayer> keep;
        for (size_t i = 0; i < bars.size(); ++i) {
            const double lo1 = bars[i].c - 0.5 * bars[i].t, hi1 = bars[i].c + 0.5 * bars[i].t;
            int inside = 0;
            for (size_t j = 0; j < bars.size(); ++j) {
                if (i == j) continue;
                const double lo2 = bars[j].c - 0.5 * bars[j].t, hi2 = bars[j].c + 0.5 * bars[j].t;
                // **엄격히** 품는 것만 센다 — 범위가 같은 것(감긴 적층)은 품는 것이 아니다.
                if (lo1 <= lo2 + eps && hi1 >= hi2 - eps && (hi1 - lo1) > (hi2 - lo2) + eps) ++inside;
            }
            if (inside >= c.enclosureMinInside) encl.push_back(bars[i]);
            else keep.push_back(bars[i]);
        }
        if (!keep.empty()) bars.swap(keep);   // 전부 감싸는 파트면 그대로 층으로 본다
        else encl.clear();
    }
    if (!encl.empty()) {
        std::string ids;
        for (const NaLayer& L : encl) ids += (ids.empty() ? "" : ", ") + std::to_string(L.pid);
        console.keyValue("Enclosing parts", std::to_string(encl.size()) + "  (PID " + ids + ")");
        console.info("다른 층을 " + std::to_string(c.enclosureMinInside) +
                     "개 이상 **안에 품는** 파트는 층이 아니라 감싸는 것으로 본다(케이스·탭·파우치). "
                     "테두리로 그리고 겹침 판정에서 뺀다.");
    }

    const bool haveNeutral = na.ok;
    if (!haveNeutral)
        console.warning("E 를 읽은 층이 없어 **중립축을 긋지 않는다** — 층 구조만 그린다. "
                        "실제 과제는 `*MAT` 가 포함 파일에 있는 경우가 많다(병합 덱을 쓰라).");
    if (!na.geomOnly.empty())
        console.warning("E 를 못 읽은 층 " + std::to_string(na.geomOnly.size()) +
                        "개는 모식도에는 그리지만 **중립축 계산에서 빠졌다**.");

    // ── ★AABB 가 포개지나. 포개진 것을 층처럼 그리면 가장 나쁜 거짓이다. ──
    // ★겹침을 **두 종류로 갈라야** 한다.
    //   · 솔리드끼리 겹치면 감긴/접힌 적층이다 — AABB 로는 층이 갈리지 않으므로 **거절한다.**
    //   · 셸이 끼면 겹치는 것이 **정상**이다. 셸은 중립면에 모델링되고 그 선언 두께(*SECTION_SHELL)
    //     는 메시에 자리를 차지하지 않으므로, ±T/2 띠가 이웃 솔리드를 먹는 것이 사실이다.
    //     실측 — 배터리 덱에서 겹침 66쌍의 최대값 0.153 이 파우치 셸 두께와 같다.
    long long overlapSolid = 0, overlapShell = 0;
    double worstSolid = 0.0, worstShell = 0.0;
    const double tol = 1e-9 * std::max(1.0, spanOf(bars));
    for (size_t i = 0; i < bars.size(); ++i) {
        const double lo1 = bars[i].c - 0.5 * bars[i].t;
        const double hi1 = bars[i].c + 0.5 * bars[i].t;
        const bool sh1 = (std::string(bars[i].kind) == "shell");
        for (size_t j = i + 1; j < bars.size(); ++j) {
            const double lo2 = bars[j].c - 0.5 * bars[j].t;
            const double hi2 = bars[j].c + 0.5 * bars[j].t;
            const double ov = std::min(hi1, hi2) - std::max(lo1, lo2);
            // 접한 것(ov == 0)은 포갠 것이 아니다 — 정합 적층은 경계를 공유한다.
            if (ov <= tol) continue;
            const bool sh2 = (std::string(bars[j].kind) == "shell");
            if (sh1 || sh2) { overlapShell++; worstShell = std::max(worstShell, ov); }
            else            { overlapSolid++; worstSolid = std::max(worstSolid, ov); }
        }
    }
    const long long overlapPairs = overlapSolid;
    const double worstOverlap = worstSolid;
    console.keyValue("Layers drawn", std::to_string(bars.size()) + "  (E 읽음 " +
                     std::to_string(na.layers.size()) + " · 두께만 " +
                     std::to_string(na.geomOnly.size()) + ")");
    console.keyValue("Overlapping (solid-solid)", std::to_string(overlapSolid));
    console.keyValue("Overlapping (shell band)", std::to_string(overlapShell));
    if (overlapShell > 0)
        console.info("셸이 낀 겹침 " + std::to_string(overlapShell) +
                     "쌍(최대 " + num("%.6g", worstShell) + ")은 **정상이다** — 셸은 중립면에 "
                     "모델링되고 *SECTION_SHELL 두께가 메시에 자리를 차지하지 않는다.");
    if (overlapPairs > 0) {
        const size_t n = bars.size();
        const long long allPairs = (long long)n * ((long long)n - 1) / 2;
        console.error("**솔리드끼리** 축 범위가 " + std::to_string(overlapPairs) + " 쌍 포개진다(전체 " +
                      std::to_string(allPairs) + " 쌍, 최대 겹침 " + num("%.6g", worstOverlap) + ").");
        console.info("  이 op 은 파트별 **축 범위**(AABB)만 쓴다 — 감긴/접힌 적층에서는 층이 갈리지");
        console.info("  않는다(실측: 감긴 덱의 세 파트가 z 범위가 전부 같다). 포개진 것을 층처럼");
        console.info("  그리면 가장 나쁜 거짓이다.");
        console.info("  → 실제 기하를 보려면 `section` 을 쓰라(평면으로 자르므로 정확하다).");
        if (!c.force) return 1;
        console.warning("force: true — 포개진 채로 그린다. 이 그림의 층 순서를 믿지 말라.");
    }

    const double barLo = loOf(bars), barHi = hiOf(bars);
    console.keyValue("Stack extent", num("%.12g", barLo) + " .. " + num("%.12g", barHi));
    console.keyValue("Total thickness (drawn)", num("%.12g", barHi - barLo));
    if (haveNeutral) {
        console.keyValue("Sum E*t", num("%.12g", na.sumEt));
        console.keyValue("Geometric mid-plane", num("%.12g", na.geometric));
        console.keyValue("Neutral axis", num("%.12g", na.neutral));
        console.keyValue("Bending stiffness D", num("%.12g", na.bendingStiffness) + " (per unit width)");
    }
    console.info("단위: 알 수 없다 — LS-DYNA 덱은 단위를 담지 않는다.");

    // ── 그림 ──
    const double M = 60.0, legendW = 300.0;
    const double plotW = c.width - M - legendW;
    const double plotH = c.height - 2 * M;
    if (plotW < 80 || plotH < 80) {
        console.error("내부 오류: 그림 자리가 음수다 — width·height 검증이 새어 나왔다.");
        return 1;
    }
    const double span = spanOf(bars);
    const double s = plotH / span;
    auto PY = [&](double v) { return (c.height - M) - (v - barLo) * s; };

    // ★두께에 비례해 그리되 **바닥값**을 둔다. 바닥 처리한 층은 두께가 과장되므로 **적는다** —
    //   적지 않으면 0.008 층과 0.07 층이 같게 보이는 그림이 그럴듯하게 나온다.
    long long floored = 0;
    for (const NaLayer& L : bars)
        if (L.t * s < c.minBarPx) floored++;

    std::string svgPath = c.output + "_stackdiagram.svg";
    std::ofstream g(svgPath);
    if (!g.is_open()) { console.error("Cannot write: " + svgPath); return 1; }
    char b[640];
    g << "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n";
    g << "<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"" << c.width << "\" height=\"" << c.height
      << "\" viewBox=\"0 0 " << c.width << " " << c.height
      << "\" font-family=\"Malgun Gothic, Apple SD Gothic Neo, Noto Sans KR, NanumGothic, sans-serif\">\n";
    g << "<rect width=\"" << c.width << "\" height=\"" << c.height << "\" fill=\"#ffffff\"/>\n";

    const double barX = M + 40.0, barW = std::min(plotW - 60.0, 240.0);
    bool stripped = false;
    int notUtf8 = 0;

    // 감싸는 파트 — 층 뒤에 테두리로. 쌓지 않는다(쌓으면 층 순서가 거짓이 된다).
    for (const NaLayer& L : encl) {
        const double yTop = PY(L.c + 0.5 * L.t), yBot = PY(L.c - 0.5 * L.t);
        std::snprintf(b, sizeof(b),
            "<rect x=\"%.2f\" y=\"%.2f\" width=\"%.2f\" height=\"%.2f\" fill=\"none\" stroke=\"%s\" stroke-width=\"1.4\" stroke-dasharray=\"6 3\"/>\n"
            "<text x=\"%.2f\" y=\"%.2f\" font-size=\"10\" fill=\"%s\">PID %d 감싸는 파트 (t=%.6g)</text>\n",
            barX - 12, yTop, barW + 24, std::max(yBot - yTop, 2.0), colorFor(L.pid),
            barX - 12, yTop - 3, colorFor(L.pid), L.pid, L.t);
        g << b;
    }

    // 층 바
    for (const NaLayer& L : bars) {
        const double yTop = PY(L.c + 0.5 * L.t);
        const double yBot = PY(L.c - 0.5 * L.t);
        double h = yBot - yTop;
        const bool wasFloored = (h < c.minBarPx);
        if (wasFloored) h = c.minBarPx;
        std::snprintf(b, sizeof(b),
            "<rect x=\"%.2f\" y=\"%.2f\" width=\"%.2f\" height=\"%.2f\" fill=\"%s\" stroke=\"#333\" stroke-width=\"0.5\"/>\n",
            barX, yTop, barW, h, colorFor(L.pid));
        g << b;
        // 두께를 **글자로** 적는다 — 바닥 처리했으면 그림이 아니라 이 숫자가 참이다
        std::snprintf(b, sizeof(b),
            "<text x=\"%.2f\" y=\"%.2f\" font-size=\"10\" fill=\"#333\">%.6g%s</text>\n",
            barX + barW + 6, yTop + std::max(h, 9.0) * 0.75, L.t, wasFloored ? "  (바닥 처리)" : "");
        g << b;
    }

    // 중립축과 기하 중심면 — §1-6 의 이야기가 이 두 선으로 보인다.
    // E 를 못 읽으면 **긋지 않는다** — 0 으로 계산한 선을 그으면 그것이 거짓이다.
    if (haveNeutral) {
        const double yN = PY(na.neutral), yG = PY(na.geometric);
        std::snprintf(b, sizeof(b),
            "<line x1=\"%.2f\" y1=\"%.2f\" x2=\"%.2f\" y2=\"%.2f\" stroke=\"#CC79A7\" stroke-width=\"1.6\"/>\n"
            "<text x=\"%.2f\" y=\"%.2f\" font-size=\"11\" fill=\"#CC79A7\">중립축 %.12g</text>\n",
            barX - 34, yN, barX + barW + 2, yN, barX - 34, yN - 4, na.neutral);
        g << b;
        std::snprintf(b, sizeof(b),
            "<line x1=\"%.2f\" y1=\"%.2f\" x2=\"%.2f\" y2=\"%.2f\" stroke=\"#0072B2\" stroke-width=\"1.2\" stroke-dasharray=\"5 3\"/>\n"
            "<text x=\"%.2f\" y=\"%.2f\" font-size=\"11\" fill=\"#0072B2\">기하 중심면 %.12g</text>\n",
            barX - 34, yG, barX + barW + 2, yG, barX - 34, yG + 12, na.geometric);
        g << b;
        // 축=0 — shellmap 이 중립면으로 보는 자리(§1-6)
        if (barLo <= 0.0 && barHi >= 0.0) {
            const double y0 = PY(0.0);
            std::snprintf(b, sizeof(b),
                "<line x1=\"%.2f\" y1=\"%.2f\" x2=\"%.2f\" y2=\"%.2f\" stroke=\"#999\" stroke-width=\"1\" stroke-dasharray=\"2 2\"/>\n"
                "<text x=\"%.2f\" y=\"%.2f\" font-size=\"10\" fill=\"#777\">%c = 0 (shellmap 이 중립면으로 보는 자리)</text>\n",
                barX - 34, y0, barX + barW + 2, y0, barX - 34, y0 - 4, AX[c.axis]);
            g << b;
        }
    }

    // 범례
    double ly = M;
    const double lx = c.width - legendW + 10;
    int shown = 0, omitted = 0;
    g << "<g font-size=\"12\" stroke=\"none\">\n";
    std::snprintf(b, sizeof(b),
        "<text x=\"%.1f\" y=\"%.1f\" font-weight=\"bold\" fill=\"#222\">적층 모식도 — 축 %c</text>\n",
        lx, ly, AX[c.axis]);
    g << b; ly += 20;
    for (const NaLayer& L : bars) {
        if (shown >= c.maxParts || ly > c.height - M - 70) { omitted = (int)bars.size() - shown; break; }
        ++shown;
        std::snprintf(b, sizeof(b), "<rect x=\"%.1f\" y=\"%.1f\" width=\"12\" height=\"12\" fill=\"%s\"/>\n",
                      lx, ly - 10, colorFor(L.pid));
        g << b;
        std::string title;
        auto pit = mesh.parts.find(L.pid);
        if (pit != mesh.parts.end()) {
            if (isUtf8(pit->second.name)) title = xesc(pit->second.name, &stripped);
            else { title = xesc(asciiOnly(pit->second.name), &stripped); notUtf8++; }
        }
        if (title.empty()) title = "pid " + std::to_string(L.pid);
        std::snprintf(b, sizeof(b), "<text x=\"%.1f\" y=\"%.1f\" fill=\"#222\">%d · %s</text>\n",
                      lx + 18, ly, L.pid, title.c_str());
        g << b; ly += 15;
        std::snprintf(b, sizeof(b),
            "<text x=\"%.1f\" y=\"%.1f\" font-size=\"10\" fill=\"#666\">%s · t=%.6g · 중심 %.6g · E=%.6g</text>\n",
            lx + 18, ly, L.kind, L.t, L.c, L.E);   // E=0 이면 "못 읽었다" 는 뜻이다
        g << b; ly += 14;
    }
    if (omitted > 0) {
        std::snprintf(b, sizeof(b), "<text x=\"%.1f\" y=\"%.1f\" font-size=\"11\" fill=\"#a33\">… 층 %d개를 뺐다 (전체 %zu)</text>\n",
                      lx, ly + 4, omitted, bars.size());
        g << b; ly += 18;
    }
    for (const NaLayer& L : encl) {
        if (ly > c.height - M - 60) break;
        std::snprintf(b, sizeof(b),
            "<text x=\"%.1f\" y=\"%.1f\" font-size=\"11\" fill=\"#666\">감싸는 파트 %d · t=%.6g (층이 아니다)</text>\n",
            lx, ly, L.pid, L.t);
        g << b; ly += 15;
    }
    g << "</g>\n";

    // ★꼬리말 — 그림이 거짓말하지 않게 하는 줄들
    double fy = c.height - 40;
    g << "<g font-size=\"11\" fill=\"#333\" stroke=\"none\">\n";
    if (haveNeutral) {
        std::snprintf(b, sizeof(b),
            "<text x=\"%.1f\" y=\"%.1f\">총두께 %.12g · ΣE·t %.6g · D %.6g · 중립축−기하중심 %.6g · 단위 없음(LS-DYNA 덱)</text>\n",
            M, fy, barHi - barLo, na.sumEt, na.bendingStiffness, na.neutral - na.geometric);
    } else {
        std::snprintf(b, sizeof(b),
            "<text x=\"%.1f\" y=\"%.1f\" fill=\"#a33\">총두께 %.12g · **E 를 읽은 층이 없어 중립축을 긋지 않았다**(*MAT 가 포함 파일에 있나?) · 단위 없음</text>\n",
            M, fy, barHi - barLo);
    }
    g << b; fy += 14;
    std::snprintf(b, sizeof(b),
        "<text x=\"%.1f\" y=\"%.1f\">층 %zu개(E 읽음 %zu · 두께만 %zu) · 제외 %zu개%s%s%s</text>\n",
        M, fy, bars.size(), na.layers.size(), na.geomOnly.size(), na.skipped.size() + encl.size(),
        notUtf8 ? " · 제목이 UTF-8 이 아닌 층 있음" : "",
        stripped ? " · 제목 제어문자를 ? 로 바꿨다" : "",
        overlapSolid > 0 ? " · ⚠ 솔리드끼리 AABB 가 포개진다(층 순서를 믿지 말라)"
                         : (overlapShell > 0 ? " · 셸 띠가 이웃을 먹는다(중립면 모델링이라 정상)" : ""));
    g << b; fy += 14;
    if (floored > 0) {
        std::snprintf(b, sizeof(b),
            "<text x=\"%.1f\" y=\"%.1f\" fill=\"#a33\">⚠ 층 %lld개는 %.0f px 로 **바닥 처리**했다 — 그 층의 두께는 그림이 아니라 **옆 숫자**가 참이다</text>\n",
            M, fy, floored, c.minBarPx);
        g << b; fy += 14;
    }
    std::snprintf(b, sizeof(b),
        "<text x=\"%.1f\" y=\"%.1f\" fill=\"#777\">모식도다 — 파트별 축 범위(AABB)만 쓴다. 실제 기하는 `section` 이 평면으로 잘라 보여 준다</text>\n",
        M, fy);
    g << b;
    g << "</g>\n</svg>\n";
    g.close();

    if (floored > 0)
        console.warning("층 " + std::to_string(floored) + "개는 " + num("%.0f", c.minBarPx) +
                        " px 로 바닥 처리했다 — 그 층의 두께는 그림이 아니라 글자가 참이다.");
    console.keyValue("Floored layers", std::to_string(floored));
    console.success("Wrote: " + svgPath);
    return 0;
}
