// 자유면만 뽑아 직교투영·깊이정렬로 그리는 op — 전체 와이어프레임은 검은 덩어리가 된다.
//
// 왜 자유면만인가 (실측). 배터리 적층 273,600 HEX8 에서 전체 면 843,123 중 자유면은
// **44,646(5.3%)** 뿐이다 — 나머지 90% 는 묻혀서 보이지 않는 선이고, 그려도 느리기만 하다.
// 그리고 전체 모서리를 그리면 `ink_ratio`(그린 선 길이 px ÷ 캔버스 픽셀)가 **5.49** 로 픽셀마다
// 평균 5.5번 칠한다. 자유면만이면 0.68 이다.
//
// 왜 **종류별 면 테이블**인가 (실측). 공용 면 테이블은 육면체 기준이고 `isFaceDegenerate` 는
// `fn[0]==fn[1] && fn[2]==fn[3]` 만 본다. TET4 는 `n5..n8 = n4` 로 저장되므로 면 0·3 이 변으로
// 찌그러진 **가짜 면으로 통과**하고, 면 4 는 사면체의 네 꼭짓점을 잇는 **비평면 사각형**이 된다.
// 그 표로 자유면을 세면 TET 덱의 표면이 틀린다 — `extract-surface` 가 실제로 그렇다(TET4 하나에서
// 자유면 5개를 내고 그중 3개가 가짜다). 그래서 여기서는 종류별 표를 쓴다.
#include "surfview.h"

#include "cli/ConsoleOutput.h"
#include "core/Mesh.h"
#include "core/Platform.h"
#include "parser/KFileReader.h"
#include "util/FigureSvg.h"
#include "util/YamlComment.h"

#include <algorithm>
#include <array>
#include <cmath>
#include <cstdio>
#include <fstream>
#include <map>
#include <set>
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
    double azim = 35.0, elev = 25.0;   // 보는 방향(도)
    int width = 1200, height = 900;
    int maxParts = 60;
    bool wire = false;                 // true = 음영 대신 모서리만
};

// 삼각형 하나. 자유면 판정은 **면** 단위로 하고, 그린 것은 삼각형이다.
struct Tri { int pid; int n[3]; };

std::string trim(const std::string& s) {
    size_t a = s.find_first_not_of(" \t");
    if (a == std::string::npos) return "";
    size_t b = s.find_last_not_of(" \t\r");
    return s.substr(a, b - a + 1);
}

// ── 종류별 면 테이블. 각 면은 절점 3개(삼각형) 또는 4개(사각형)다. ──
struct FaceDef { int n; int v[4]; };

const std::vector<FaceDef>& facesFor(ElementType t) {
    static const std::vector<FaceDef> hex = {
        {4,{0,3,2,1}}, {4,{4,5,6,7}}, {4,{0,1,5,4}},
        {4,{1,2,6,5}}, {4,{2,3,7,6}}, {4,{3,0,4,7}}};
    static const std::vector<FaceDef> tet = {
        {3,{0,2,1,0}}, {3,{0,1,3,0}}, {3,{1,2,3,0}}, {3,{2,0,3,0}}};
    static const std::vector<FaceDef> wedge = {
        {3,{0,2,1,0}}, {3,{4,5,6,0}},
        {4,{0,1,5,4}}, {4,{1,2,6,5}}, {4,{2,0,4,6}}};
    static const std::vector<FaceDef> quad = {{4,{0,1,2,3}}};
    switch (t) {
        case ElementType::TET4:
        case ElementType::TET10:  return tet;
        case ElementType::PENTA6: return wedge;
        case ElementType::QUAD4:  return quad;
        default:                  return hex;   // HEX8 · HEX20 (모서리 절점만)
    }
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
            if      (key == "model")     c.model = val;
            else if (key == "output")    c.output = val;
            else if (key == "azimuth")   c.azim = std::stod(val);
            else if (key == "elevation") c.elev = std::stod(val);
            else if (key == "width")     c.width = std::stoi(val);
            else if (key == "height")    c.height = std::stoi(val);
            else if (key == "max_parts") c.maxParts = std::stoi(val);
            else if (key == "wire")      c.wire = (val == "true" || val == "yes" || val == "1");
            else console.warning("모르는 키는 무시한다: " + key);
        } catch (const std::exception&) {
            console.error("숫자를 읽을 수 없다: " + key + ": " + val);
            return false;
        }
    }
    return true;
}

}  // namespace

int runSurfView(const std::string& yamlFile, ConsoleOutput& console) {
    Config c;
    if (!parseYaml(yamlFile, c, console)) return 1;
    if (c.model.empty())  { console.error("model: 이 필요하다"); return 1; }
    if (c.output.empty()) { console.error("output: 이 필요하다"); return 1; }
    if (c.width < 430 || c.height < 240) {
        console.error("width 는 430 이상, height 는 240 이상이어야 한다 — "
                      "여백과 범례가 들어가야 한다.");
        return 1;
    }
    if (c.maxParts < 1) { console.error("max_parts 는 1 이상이어야 한다"); return 1; }

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

    {
        // ★2차 솔리드는 **그리지 않는다.** 같은 말을 세 그림 op 이 함께 쓴다(갈리면 못 믿는다).
        const auto bad2nd = figure::secondOrderSolidPids(mesh);
        if (!bad2nd.empty()) {
            console.error(figure::secondOrderSolidWhy(bad2nd));
            for (const auto& l : figure::secondOrderSolidAdvice()) console.info("  " + l);
            return 1;
        }
    }

    console.header("Surface view (free faces): " + Platform::getFilename(c.model));

    // ── 자유면. 면 키(정렬한 절점 목록)가 한 번만 나오면 자유면이다. ──
    // 삼각형으로 쪼개기 **전에** 면 단위로 센다 — 쪼갠 뒤 세면 사각형을 어느 대각선으로
    // 쪼갰냐에 따라 이웃과 키가 안 맞는다.
    std::map<std::vector<int>, std::pair<int, std::pair<int, int>>> faceCount;  // key → (count, (eid, faceIdx))
    long long degenerateFaces = 0;
    for (const auto& [eid, elem] : mesh.elements) {
        const auto& defs = facesFor(elem.type);
        for (size_t fi = 0; fi < defs.size(); ++fi) {
            const FaceDef& fd = defs[fi];
            std::vector<int> ids;
            for (int k = 0; k < fd.n; ++k) {
                const int nid = elem.nodeIds[fd.v[k]];
                if (nid > 0) ids.push_back(nid);
            }
            std::vector<int> uniq = ids;
            std::sort(uniq.begin(), uniq.end());
            uniq.erase(std::unique(uniq.begin(), uniq.end()), uniq.end());
            if (uniq.size() < 3) { degenerateFaces++; continue; }   // 변으로 찌그러진 면
            auto it = faceCount.find(uniq);
            if (it == faceCount.end()) faceCount[uniq] = {1, {eid, (int)fi}};
            else it->second.first++;
        }
    }

    // 자유면을 삼각형으로 쪼갠다(사각형 → 2개). 이것이 `modelmeta` 가 맞는 까닭이기도 하다.
    std::vector<Tri> tris;
    long long freeFaces = 0, totalFaces = (long long)faceCount.size();
    for (const auto& [key, v] : faceCount) {
        if (v.first != 1) continue;
        ++freeFaces;
        const auto eit = mesh.elements.find(v.second.first);
        if (eit == mesh.elements.end()) continue;
        const Element& e = eit->second;
        const FaceDef& fd = facesFor(e.type)[v.second.second];
        int id[4] = {0, 0, 0, 0};
        for (int k = 0; k < fd.n; ++k) id[k] = e.nodeIds[fd.v[k]];
        if (fd.n == 3) {
            tris.push_back({e.partId, {id[0], id[1], id[2]}});
        } else {
            tris.push_back({e.partId, {id[0], id[1], id[2]}});
            tris.push_back({e.partId, {id[0], id[2], id[3]}});
        }
    }
    if (tris.empty()) {
        console.error("자유면이 없다 — 그림을 내지 않는다.");
        return 1;
    }

    // ── 직교투영. 보는 방향에서 (u,v) 와 깊이 w 를 얻는다. ──
    const double az = c.azim * M_PI / 180.0, el = c.elev * M_PI / 180.0;
    const Vector3D dir(std::cos(el) * std::cos(az), std::cos(el) * std::sin(az), std::sin(el));
    Vector3D up(0, 0, 1);
    if (std::fabs(dir.z) > 0.999) up = Vector3D(0, 1, 0);
    Vector3D right = dir.cross(up);
    right = right * (1.0 / std::max(1e-12, right.magnitude()));
    Vector3D vUp = right.cross(dir);
    vUp = vUp * (1.0 / std::max(1e-12, vUp.magnitude()));

    struct PTri { int pid; double u[3], v[3]; double depth; double shade; bool flipped; };
    std::vector<PTri> ptris;
    ptris.reserve(tris.size());
    long double uMin = 1e300, uMax = -1e300, vMin = 1e300, vMax = -1e300;
    long long flippedCount = 0, missingNode = 0;
    for (const Tri& t : tris) {
        Vector3D p[3];
        bool ok = true;
        for (int k = 0; k < 3; ++k) {
            auto it = mesh.nodes.find(t.n[k]);
            if (it == mesh.nodes.end()) { ok = false; break; }
            p[k] = it->second.position;
        }
        if (!ok) { missingNode++; continue; }
        PTri q;
        q.pid = t.pid;
        double dsum = 0;
        for (int k = 0; k < 3; ++k) {
            q.u[k] = p[k].dot(right);
            q.v[k] = p[k].dot(vUp);
            dsum += p[k].dot(dir);
            uMin = std::min(uMin, (long double)q.u[k]); uMax = std::max(uMax, (long double)q.u[k]);
            vMin = std::min(vMin, (long double)q.v[k]); vMax = std::max(vMax, (long double)q.v[k]);
        }
        q.depth = dsum / 3.0;
        // 평면 음영 — 면 법선과 보는 방향의 각. ⚠ 뒤집힌 요소(음수 야코비안)에서는 법선이
        // 뒤집혀 **음영이 거짓말한다**. 그래서 부호를 쓰지 않고 |cos| 를 쓰고, 뒤집힌(보는 쪽을
        // 등진) 면 수를 세서 보고한다. 추적 덱 489장 중 111장이 정상 픽스처인데 음수 야코비안이다.
        const Vector3D n = (p[1] - p[0]).cross(p[2] - p[0]);
        const double nm = n.magnitude();
        const double cosang = (nm > 0) ? (n.dot(dir) / nm) : 0.0;
        q.flipped = (cosang < 0.0);
        if (q.flipped) flippedCount++;
        q.shade = 0.35 + 0.65 * std::fabs(cosang);
        ptris.push_back(q);
    }
    if (ptris.empty()) { console.error("투영할 삼각형이 없다."); return 1; }

    // 깊이정렬 — 멀리 있는 것을 먼저 그린다(화가 알고리즘). 삼각형끼리 뚫고 지나가면 틀릴 수
    // 있는데, 자유면만 그리므로 교차가 드물다. 그 한계를 매니페스트에 적는다.
    std::sort(ptris.begin(), ptris.end(),
              [](const PTri& a, const PTri& b) { return a.depth < b.depth; });

    const double uE = (double)(uMax - uMin), vE = (double)(vMax - vMin);
    std::set<int> pids;
    for (const PTri& q : ptris) pids.insert(q.pid);

    console.keyValue("View (azim, elev)", std::to_string(c.azim) + ", " + std::to_string(c.elev));
    console.keyValue("Faces total / free", std::to_string(totalFaces) + " / " + std::to_string(freeFaces));
    {
        char b[96];
        std::snprintf(b, sizeof(b), "%.2f %%", totalFaces ? 100.0 * (double)freeFaces / (double)totalFaces : 0.0);
        console.keyValue("Free face share", b);
    }
    console.keyValue("Triangles drawn", std::to_string(ptris.size()));
    console.keyValue("Degenerate faces skipped", std::to_string(degenerateFaces));
    console.keyValue("Parts", std::to_string(pids.size()) + " / " + std::to_string(mesh.parts.size()));
    console.keyValue("Back-facing triangles", std::to_string(flippedCount));
    if (missingNode > 0)
        console.warning("절점을 못 찾은 삼각형 " + std::to_string(missingNode) + "개를 건너뛰었다.");
    console.info("단위: 알 수 없다 — LS-DYNA 덱은 단위를 담지 않는다.");

    // ── 그림 ──
    const double M = 70.0, legendW = 260.0;
    const double plotW = c.width - M - legendW, plotH = c.height - 2 * M;
    const double s = std::min(uE > 0 ? plotW / uE : 1.0, vE > 0 ? plotH / vE : 1.0);
    // ★자유면 뷰는 **등축**이다 — 3D 형상을 비등방으로 늘이면 모양 자체가 거짓이 된다.
    //   그래서 적층은 이 그림에서 얇게 보인다. 그것이 사실이고, 층을 보려면 `section` 을 쓴다.
    auto PX = [&](double u) { return M + (u - (double)uMin) * s; };
    auto PY = [&](double v) { return (c.height - M) - (v - (double)vMin) * s; };

    // ink_ratio — 모서리를 그렸을 때 포화하나. 1.0 을 넘으면 선을 더 그려도 새로 보이는 것이 없다.
    double inkLen = 0.0;
    for (const PTri& q : ptris)
        for (int k = 0; k < 3; ++k) {
            const int k2 = (k + 1) % 3;
            inkLen += std::hypot(PX(q.u[k]) - PX(q.u[k2]), PY(q.v[k]) - PY(q.v[k2]));
        }
    const double inkRatio = inkLen / (double)(c.width * c.height);
    console.keyValue("ink_ratio (edges)", std::to_string(inkRatio));
    if (c.wire && inkRatio > 1.0)
        console.warning("ink_ratio 가 " + std::to_string(inkRatio) +
                        " 다 — 모서리를 그려도 픽셀이 포화해 새로 보이는 것이 없다. "
                        "음영(wire: false)을 쓰거나 범위를 좁히라.");

    const std::string svgPath = c.output + "_surface.svg";
    std::ofstream g(svgPath);
    if (!g.is_open()) { console.error("Cannot write: " + svgPath); return 1; }
    char b[512];
    g << "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n";
    g << "<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"" << c.width << "\" height=\"" << c.height
      << "\" viewBox=\"0 0 " << c.width << " " << c.height
      << "\" font-family=\"Malgun Gothic, Apple SD Gothic Neo, Noto Sans KR, NanumGothic, sans-serif\">\n";
    g << "<rect width=\"" << c.width << "\" height=\"" << c.height << "\" fill=\"#ffffff\"/>\n";
    g << "<g>\n";
    for (const PTri& q : ptris) {
        const char* col = colorFor(q.pid);
        if (c.wire) {
            std::snprintf(b, sizeof(b),
                "<polygon points=\"%.2f,%.2f %.2f,%.2f %.2f,%.2f\" fill=\"none\" stroke=\"%s\" stroke-width=\"0.4\"/>\n",
                PX(q.u[0]), PY(q.v[0]), PX(q.u[1]), PY(q.v[1]), PX(q.u[2]), PY(q.v[2]), col);
        } else {
            std::snprintf(b, sizeof(b),
                "<polygon points=\"%.2f,%.2f %.2f,%.2f %.2f,%.2f\" fill=\"%s\" fill-opacity=\"%.3f\" stroke=\"none\"/>\n",
                PX(q.u[0]), PY(q.v[0]), PX(q.u[1]), PY(q.v[1]), PX(q.u[2]), PY(q.v[2]), col, q.shade);
        }
        g << b;
    }
    g << "</g>\n";

    // 범례 — 그림 안에 굽는다
    bool stripped = false;
    int notUtf8 = 0, shown = 0, omitted = 0;
    double ly = M;
    const double lx = c.width - legendW + 10;
    g << "<g font-size=\"12\" stroke=\"none\">\n";
    std::snprintf(b, sizeof(b),
        "<text x=\"%.1f\" y=\"%.1f\" font-weight=\"bold\" fill=\"#222\">자유면 — 보는 방향 (%.0f, %.0f)</text>\n",
        lx, ly, c.azim, c.elev);
    g << b; ly += 20;
    for (int pid : pids) {
        if (shown >= c.maxParts || ly > c.height - M - 80) { omitted = (int)pids.size() - shown; break; }
        ++shown;
        std::snprintf(b, sizeof(b), "<rect x=\"%.1f\" y=\"%.1f\" width=\"12\" height=\"12\" fill=\"%s\"/>\n",
                      lx, ly - 10, colorFor(pid));
        g << b;
        std::string title;
        auto pit = mesh.parts.find(pid);
        if (pit != mesh.parts.end()) {
            if (isUtf8(pit->second.name)) title = xesc(pit->second.name, &stripped);
            else { title = xesc(asciiOnly(pit->second.name), &stripped); notUtf8++; }
        }
        if (title.empty()) title = "pid " + std::to_string(pid);
        std::snprintf(b, sizeof(b), "<text x=\"%.1f\" y=\"%.1f\" fill=\"#222\">%d · %s</text>\n",
                      lx + 18, ly, pid, title.c_str());
        g << b; ly += 16;
    }
    if (omitted > 0) {
        std::snprintf(b, sizeof(b), "<text x=\"%.1f\" y=\"%.1f\" font-size=\"11\" fill=\"#a33\">… 파트 %d개를 뺐다 (전체 %zu)</text>\n",
                      lx, ly + 4, omitted, pids.size());
        g << b;
    }
    g << "</g>\n";

    // ★꼬리말 — 그림이 거짓말하지 않게 하는 줄들
    double fy = c.height - 34;
    g << "<g font-size=\"11\" fill=\"#333\" stroke=\"none\">\n";
    std::snprintf(b, sizeof(b),
        "<text x=\"%.1f\" y=\"%.1f\">자유면 %lld / 전체 면 %lld (%.2f%%) · 삼각형 %zu · **등축** · 단위 없음(LS-DYNA 덱)</text>\n",
        M, fy, freeFaces, totalFaces, totalFaces ? 100.0 * (double)freeFaces / (double)totalFaces : 0.0,
        ptris.size());
    g << b; fy += 14;
    std::snprintf(b, sizeof(b),
        "<text x=\"%.1f\" y=\"%.1f\">파트 %zu/%zu · 등진 삼각형 %lld · 찌그러진 면 %lld 건너뜀 · ink_ratio %.3f%s%s</text>\n",
        M, fy, pids.size(), mesh.parts.size(), flippedCount, degenerateFaces, inkRatio,
        notUtf8 ? " · 제목이 UTF-8 이 아닌 파트 있음" : "",
        stripped ? " · 제목 제어문자를 ? 로 바꿨다" : "");
    g << b; fy += 14;
    std::snprintf(b, sizeof(b),
        "<text x=\"%.1f\" y=\"%.1f\" fill=\"#a33\">⚠ 깊이정렬은 삼각형 중심 기준이다 — 서로 뚫고 지나가는 면은 순서가 틀릴 수 있다. 층 두께를 보려면 section 을 쓰라(이 그림은 등축이다)</text>\n",
        M, fy);
    g << b;
    g << "</g>\n</svg>\n";
    g.close();

    // ★크기를 재서 말한다. **솎지 않는다** — 음영 뷰에서 삼각형을 빼면 그림에 구멍이 뚫려
    //   거짓이 된다. 대신 큰 것을 큰 것이라고 말하고 어디서 걸리는지 알려 준다.
    //   MCP `download_result` 는 기본 5MB 에서 자른다(`KOORM_MCP_MAX_DOWNLOAD_BYTES`).
    {
        std::ifstream sz(svgPath, std::ios::binary | std::ios::ate);
        const long long bytes = sz.is_open() ? (long long)sz.tellg() : -1;
        if (bytes > 0) {
            char bb[128];
            std::snprintf(bb, sizeof(bb), "%.2f MB", (double)bytes / 1048576.0);
            console.keyValue("SVG size", bb);
            if (bytes > 5 * 1024 * 1024) {
                console.warning("SVG 가 5MB 를 넘는다 — MCP `download_result` 가 대화로 실어나르기엔 "
                                "크다고 거절한다. `save_result_to_path` 로 디스크에 받거나, 보는 "
                                "방향·범위를 좁히라. 삼각형을 **솎지는 않았다**(구멍이 뚫리면 "
                                "그림이 거짓이 된다).");
            }
        }
    }
    console.success("Wrote: " + svgPath);
    return 0;
}
