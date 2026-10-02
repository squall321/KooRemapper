// 2D 곡선을 폭 방향으로 쓸어 QUAD4 기준 셸 덱을 만드는 op — shellmap 의 기준면 공급원.
#include "refshell.h"

#include "cli/ConsoleOutput.h"
#include "parser/DeckWriter.h"
#include "util/YamlComment.h"

#include <algorithm>
#include <cmath>
#include <cstdio>
#include <fstream>
#include <sstream>
#include <string>
#include <vector>

using KooRemapper::ConsoleOutput;
using KooRemapper::yamlStripComment;

namespace {

struct Config {
    std::string curve;        // x,y 칸을 가진 CSV (foldsurface 산출물)
    std::string output;
    std::string partTitle = "Reference shell";
    double width = 0.0;
    int divisions = 0;        // 0 = CSV 점을 그대로 쓴다
    int widthDivisions = 0;   // 0 = 종횡비 1:1 로 자동
    double thickness = 0.0;
    double rho = 7.85e-9, E = 210000.0, nu = 0.3;
    int pid = 1, secid = 1, mid = 1;
};

struct P2 { double x = 0.0, y = 0.0; };

std::string trim(const std::string& s) {
    size_t a = s.find_first_not_of(" \t");
    if (a == std::string::npos) return "";
    size_t b = s.find_last_not_of(" \t\r");
    return s.substr(a, b - a + 1);
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
        std::string key = trim(t.substr(0, cp));
        std::string val = trim(yamlStripComment(t.substr(cp + 1)));
        if (val.empty()) continue;
        try {
            if      (key == "curve")            c.curve = val;
            else if (key == "output")           c.output = val;
            else if (key == "part_title")       c.partTitle = val;
            else if (key == "width")            c.width = std::stod(val);
            else if (key == "divisions")        c.divisions = std::stoi(val);
            else if (key == "width_divisions")  c.widthDivisions = std::stoi(val);
            else if (key == "thickness")        c.thickness = std::stod(val);
            else if (key == "rho")              c.rho = std::stod(val);
            else if (key == "E")                c.E = std::stod(val);
            else if (key == "nu")               c.nu = std::stod(val);
            else if (key == "pid")              c.pid = std::stoi(val);
            else if (key == "secid")            c.secid = std::stoi(val);
            else if (key == "mid")              c.mid = std::stoi(val);
            else console.warning("모르는 키는 무시한다: " + key);
        } catch (const std::exception&) {
            console.error("숫자를 읽을 수 없다: " + key + ": " + val);
            return false;
        }
    }
    return true;
}

// x,y 칸을 **이름으로** 찾는다 — 칸 순서에 기대면 CSV 가 바뀌면 조용히 틀린다.
bool readCurve(const std::string& path, std::vector<P2>& pts, ConsoleOutput& console) {
    std::ifstream f(path);
    if (!f.is_open()) { console.error("Cannot open curve: " + path); return false; }
    std::string ln;
    if (!std::getline(f, ln)) { console.error("빈 CSV: " + path); return false; }
    if (!ln.empty() && ln.back() == '\r') ln.pop_back();
    int ix = -1, iy = -1;
    {
        std::stringstream ss(ln);
        std::string cell;
        for (int i = 0; std::getline(ss, cell, ','); ++i) {
            const std::string h = trim(cell);
            if (h == "x") ix = i;
            else if (h == "y") iy = i;
        }
    }
    if (ix < 0 || iy < 0) {
        console.error("CSV 머리줄에 `x` 와 `y` 칸이 있어야 한다: " + path);
        return false;
    }
    int lineNo = 1;
    while (std::getline(f, ln)) {
        lineNo++;
        if (!ln.empty() && ln.back() == '\r') ln.pop_back();
        if (trim(ln).empty()) continue;
        std::vector<std::string> cells;
        std::stringstream ss(ln);
        std::string cell;
        while (std::getline(ss, cell, ',')) cells.push_back(trim(cell));
        if ((int)cells.size() <= std::max(ix, iy)) {
            console.error("칸이 부족하다 (" + path + ":" + std::to_string(lineNo) + ")");
            return false;
        }
        P2 p;
        try {
            p.x = std::stod(cells[ix]);
            p.y = std::stod(cells[iy]);
        } catch (const std::exception&) {
            console.error("숫자를 읽을 수 없다 (" + path + ":" + std::to_string(lineNo) + ")");
            return false;
        }
        pts.push_back(p);
    }
    if (pts.size() < 2) { console.error("곡선 점이 2개 미만이다: " + path); return false; }
    return true;
}

std::string num(const char* f, double v) {
    char b[64];
    std::snprintf(b, sizeof(b), f, v);
    return std::string(b);
}

}  // namespace

int runRefShell(const std::string& yamlFile, ConsoleOutput& console) {
    Config c;
    if (!parseYaml(yamlFile, c, console)) return 1;
    if (c.curve.empty())  { console.error("curve: (CSV 경로)가 필요하다"); return 1; }
    if (c.output.empty()) { console.error("output: 이 필요하다"); return 1; }
    if (c.width <= 0)     { console.error("width: 가 0 보다 커야 한다"); return 1; }
    if (c.thickness <= 0) { console.error("thickness: 가 0 보다 커야 한다"); return 1; }
    if (c.divisions < 0 || c.widthDivisions < 0) { console.error("분할 수는 음수가 될 수 없다"); return 1; }

    std::vector<P2> raw;
    if (!readCurve(c.curve, raw, console)) return 1;

    // 입력 폴리라인의 길이 — 이것이 "목표 길이" 다
    std::vector<double> cum(raw.size(), 0.0);
    for (size_t i = 1; i < raw.size(); ++i)
        cum[i] = cum[i - 1] + std::hypot(raw[i].x - raw[i - 1].x, raw[i].y - raw[i - 1].y);
    const double inputLen = cum.back();
    if (inputLen <= 0) { console.error("곡선 길이가 0 이다"); return 1; }

    // 곡선 방향 분할 — divisions 를 주면 **등현 길이**로 다시 뽑는다(종횡비를 맞추려면 필요하다)
    std::vector<P2> pts;
    if (c.divisions == 0) {
        pts = raw;
    } else {
        pts.resize(c.divisions + 1);
        size_t seg = 0;
        for (int k = 0; k <= c.divisions; ++k) {
            const double t = inputLen * (double)k / c.divisions;
            while (seg + 2 < raw.size() && cum[seg + 1] < t) seg++;
            const double d = cum[seg + 1] - cum[seg];
            const double f = (d > 0) ? (t - cum[seg]) / d : 0.0;
            pts[k].x = raw[seg].x + f * (raw[seg + 1].x - raw[seg].x);
            pts[k].y = raw[seg].y + f * (raw[seg + 1].y - raw[seg].y);
        }
    }

    const int ns = (int)pts.size() - 1;              // 곡선 방향 요소 수
    double chordSum = 0.0;
    for (size_t i = 1; i < pts.size(); ++i)
        chordSum += std::hypot(pts[i].x - pts[i - 1].x, pts[i].y - pts[i - 1].y);
    const double dsAvg = chordSum / ns;

    // 폭 방향 분할 — 0 이면 종횡비 1:1
    int nw = c.widthDivisions;
    if (nw == 0) nw = std::max(1, (int)std::lround(c.width / dsAvg));
    const double dw = c.width / nw;

    console.header("Reference shell (QUAD4)");
    console.keyValue("Curve", c.curve);
    console.keyValue("Curve points", std::to_string(pts.size()));
    console.keyValue("Input polyline length", num("%.12g", inputLen));
    console.keyValue("Chord sum", num("%.12g", chordSum));
    const double lenDevPct = 100.0 * (chordSum - inputLen) / inputLen;
    console.keyValue("Length deviation", num("%.4g", lenDevPct) + " %");
    console.keyValue("Divisions (curve x width)", std::to_string(ns) + " x " + std::to_string(nw));
    console.keyValue("Element size (curve)", num("%.12g", dsAvg));
    console.keyValue("Element size (width)", num("%.12g", dw));
    console.keyValue("Aspect ratio", num("%.6g", dw / dsAvg));

    if (std::fabs(lenDevPct) > 0.01)
        console.warning("현 합이 입력 길이에서 " + num("%.4g", lenDevPct) +
                        "% 벗어났다 — divisions 를 늘리라(현은 호보다 짧다).");
    const double aspect = dw / dsAvg;
    if (aspect > 2.0 || aspect < 0.5)
        console.warning("종횡비가 " + num("%.4g", aspect) +
                        " 다 — width_divisions 를 0 으로 두면 1:1 로 맞춘다.");

    // 덱 — 새로 만드는 덱이라 LF 로 쓴다. 쓰기는 공용 계층(DeckWriter)을 지난다.
    KooRemapper::DeckWriter w(c.output, KooRemapper::DeckNewline::LF);
    if (!w.ok()) { console.error("Cannot write: " + c.output); return 1; }
    std::ostream& o = w.stream();
    char buf[256];

    o << "$# KooRemapper refshell\n";
    o << "$# curve: " << c.curve << "\n";
    std::snprintf(buf, sizeof(buf), "$# grid: %d x %d (curve x width), width %.12g\n", ns, nw, c.width);
    o << buf;
    o << "*KEYWORD\n*NODE\n";
    o << "$#   nid               x               y               z\n";
    for (int i = 0; i <= ns; ++i) {
        for (int j = 0; j <= nw; ++j) {
            const int nid = i * (nw + 1) + j + 1;
            std::snprintf(buf, sizeof(buf), "%8d%16.9f%16.9f%16.9f\n",
                          nid, pts[i].x, pts[i].y, j * dw);
            o << buf;
        }
    }
    o << "*ELEMENT_SHELL\n";
    o << "$#   eid     pid      n1      n2      n3      n4\n";
    int eid = 0;
    for (int i = 0; i < ns; ++i) {
        for (int j = 0; j < nw; ++j) {
            // 격자 꼭짓점: a=(i,j) b=(i+1,j) c=(i+1,j+1) d=(i,j+1)
            // 감김은 **(a, d, c, b)** 다 — 법선이 곡선 진행방향 û 에 대해 ŵ x û 쪽을 향한다
            // (폭을 +z 로 쓸면, x-y 평면 곡선의 오목한 쪽이다).
            const int a = i * (nw + 1) + j + 1;
            const int b = (i + 1) * (nw + 1) + j + 1;
            const int cc = (i + 1) * (nw + 1) + j + 2;
            const int d = i * (nw + 1) + j + 2;
            std::snprintf(buf, sizeof(buf), "%8d%8d%8d%8d%8d%8d\n", ++eid, c.pid, a, d, cc, b);
            o << buf;
        }
    }
    o << "*PART\n" << c.partTitle << "\n";
    std::snprintf(buf, sizeof(buf), "%10d%10d%10d\n", c.pid, c.secid, c.mid);
    o << buf;
    o << "*SECTION_SHELL\n";
    std::snprintf(buf, sizeof(buf), "%10d%10d\n", c.secid, 2);
    o << buf;
    std::snprintf(buf, sizeof(buf), "%10.6g%10.6g%10.6g%10.6g\n",
                  c.thickness, c.thickness, c.thickness, c.thickness);
    o << buf;
    o << "*MAT_ELASTIC\n";
    std::snprintf(buf, sizeof(buf), "%10d%10.4g%10.6g%10.4g\n", c.mid, c.rho, c.E, c.nu);
    o << buf;
    o << "*END\n";
    w.close();

    console.keyValue("Nodes", std::to_string((ns + 1) * (nw + 1)));
    console.keyValue("Elements", std::to_string(eid));
    console.success("Wrote: " + c.output);
    return 0;
}
