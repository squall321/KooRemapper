// 메시를 평면으로 잘라 요소 다각형을 내는 op — 그림의 엔진. 모서리∩평면이라 거짓말할 경로가 없다.
//
// 왜 면이 아니라 **모서리** 기반인가 (2026-10-03 실측).
//   `Element::getValidFaceIndices()` 의 면 테이블은 육면체 기준이고 `isFaceDegenerate` 는
//   `fn[0]==fn[1] && fn[2]==fn[3]` 만 본다. TET4 는 `n5..n8 = n4` 로 저장되므로 면 0 은
//   `[n0,n3,n3,n3]`, 면 3 은 `[n3,n2,n3,n3]` 이 되는데 **둘 다 그 검사를 통과한다** — 면이 아니라
//   변으로 찌그러진 가짜 면이다. 그래서 면으로 단면을 짜면 TET 덱이 틀린다.
//   모서리 기반은 그것을 피해 가지만, **육면체 12 모서리 표를 그대로 쓰면 안 된다** — 그 표를
//   TET4 저장에 적용하면 모서리 `(n0,n2)` 가 빠진다(실측). 그래서 종류별 모서리 표를 둔다.
#include "section.h"

#include "cli/ConsoleOutput.h"
#include "core/Mesh.h"
#include "core/Platform.h"
#include "parser/IncludeScan.h"
#include "parser/KFileReader.h"
#include "util/YamlComment.h"

#include <algorithm>
#include <cmath>
#include <cstdio>
#include <fstream>
#include <limits>
#include <map>
#include <set>
#include <string>
#include <vector>

using namespace KooRemapper;

namespace {

struct Config {
    std::string model, output;
    int axis = -1;          // -1 = auto
    double at = 0.0;
    bool hasAt = false;
    int maxParts = 60;
    int width = 1200, height = 900;
    bool isotropic = false;   // true = 등축(배율 1). 기본은 비등방 + 배율을 **적는다**
    bool svg = true;
};

struct P2 { double u = 0.0, v = 0.0; };

struct Poly {
    int pid = 0;
    bool shell = false;     // 셸은 선분이다(두께가 메시에 없다)
    std::vector<P2> pts;
};

std::string trim(const std::string& s) {
    size_t a = s.find_first_not_of(" \t");
    if (a == std::string::npos) return "";
    size_t b = s.find_last_not_of(" \t\r");
    return s.substr(a, b - a + 1);
}

std::string jesc(const std::string& s) {
    std::string out;
    out.reserve(s.size() + 8);
    for (char c : s) {
        switch (c) {
            case '"':  out += "\\\""; break;
            case '\\': out += "\\\\"; break;
            case '\n': out += "\\n"; break;
            case '\r': break;
            case '\t': out += "\\t"; break;
            default:
                if (static_cast<unsigned char>(c) < 0x20) { /* 제어문자는 버린다 */ }
                else out += c;
        }
    }
    return out;
}

// XML 이스케이프. 파트 제목은 `*PART` 다음 줄의 **자유 텍스트**라 무엇이든 들어 있다 —
// STEP 라벨과 같은 노출이다. 그리고 XML 1.0 은 제어문자를 담지 못해 **이름에 \x01 하나면 SVG 가
// 통째로 안 읽힌다**(StepForge 실측). 그래서 지우지 않고 보이는 기호로 바꾸고, 바꿨다는 사실을
// 매니페스트에 싣는다.
std::string xesc(const std::string& s, bool* stripped = nullptr) {
    std::string out;
    out.reserve(s.size() + 16);
    for (char ch : s) {
        const unsigned char u = static_cast<unsigned char>(ch);
        switch (ch) {
            case '&': out += "&amp;";  continue;
            case '<': out += "&lt;";   continue;
            case '>': out += "&gt;";   continue;
            case '"': out += "&quot;"; continue;
            case '\'': out += "&apos;"; continue;
            default: break;
        }
        if (u < 0x20 || u == 0x7F) {
            out += '?';                       // 보이는 자리표시 — 지우면 사라진 줄 모른다
            if (stripped) *stripped = true;
            continue;
        }
        out += ch;
    }
    return out;
}

// 색맹 안전 범주 색(Okabe-Ito). **pid 로 고정**한다 — 호출마다 바뀌면 두 그림을 견줄 수 없다.
const char* colorFor(int pid) {
    static const char* P[] = {"#0072B2","#E69F00","#009E73","#CC79A7",
                              "#56B4E9","#D55E00","#F0E442","#999999"};
    const int n = 8;
    int k = pid % n;
    if (k < 0) k += n;
    return P[k];
}

double coordOf(const Node& n, int axis) {
    return axis == 0 ? n.position.x : (axis == 1 ? n.position.y : n.position.z);
}

// 절단면의 2D 기저 — 오른손 방향을 지킨다(뒤집히면 감김이 뒤집혀 채움이 거짓이 된다).
//   axis z → (u,v) = (x,y)   axis x → (y,z)   axis y → (z,x)
P2 to2d(const Vector3D& p, int axis) {
    if (axis == 2) return {p.x, p.y};
    if (axis == 0) return {p.y, p.z};
    return {p.z, p.x};
}

// 종류별 모서리 표. 저장 규약: TET4 는 n4..n7=n3, PENTA6 는 n2=n3·n6=n7 로 정규화돼 있다
// (`KFileReader::detectAndNormalizePenta6`).
const std::vector<std::pair<int,int>>& edgesFor(ElementType t) {
    static const std::vector<std::pair<int,int>> hex = {
        {0,1},{1,2},{2,3},{3,0},{4,5},{5,6},{6,7},{7,4},{0,4},{1,5},{2,6},{3,7}};
    static const std::vector<std::pair<int,int>> tet = {
        {0,1},{1,2},{2,0},{0,3},{1,3},{2,3}};
    static const std::vector<std::pair<int,int>> wedge = {
        {0,1},{1,2},{2,0},{4,5},{5,6},{6,4},{0,4},{1,5},{2,6}};
    static const std::vector<std::pair<int,int>> quad = {
        {0,1},{1,2},{2,3},{3,0}};
    switch (t) {
        case ElementType::TET4:
        case ElementType::TET10:   return tet;
        case ElementType::PENTA6:  return wedge;
        case ElementType::QUAD4:   return quad;
        default:                   return hex;   // HEX8 · HEX20 (모서리 절점만 쓴다)
    }
}

}  // namespace

int runSection(const std::string& yamlFile, ConsoleOutput& console) {
    Config c;
    {
        std::ifstream f(yamlFile);
        if (!f.is_open()) { console.error("Cannot open: " + yamlFile); return 1; }
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
                else if (key == "max_parts") c.maxParts = std::stoi(val);
                else if (key == "width")     c.width = std::stoi(val);
                else if (key == "height")    c.height = std::stoi(val);
                else if (key == "isotropic") c.isotropic = (val == "true" || val == "yes" || val == "1");
                else if (key == "svg")       c.svg = !(val == "false" || val == "no" || val == "0");
                else if (key == "at")        { c.at = std::stod(val); c.hasAt = true; }
                else if (key == "axis") {
                    if      (val == "x")    c.axis = 0;
                    else if (val == "y")    c.axis = 1;
                    else if (val == "z")    c.axis = 2;
                    else if (val == "auto") c.axis = -1;
                    else { console.error("axis: 는 x, y, z, auto 중 하나여야 한다 (받은 값: " + val + ")"); return 1; }
                }
                else console.warning("모르는 키는 무시한다: " + key);
            } catch (const std::exception&) {
                console.error("숫자를 읽을 수 없다: " + key + ": " + val);
                return 1;
            }
        }
    }
    if (c.model.empty())  { console.error("model: 이 필요하다"); return 1; }
    if (c.output.empty()) { console.error("output: 이 필요하다"); return 1; }
    if (c.maxParts < 1)   { console.error("max_parts 는 1 이상이어야 한다"); return 1; }
    // 여백(70×2) + 범례(260) + 그림(최소 100) 이 들어가야 한다. **앞에서** 거른다 —
    // 뒤에서 걸면 JSON 을 먼저 쓰고 실패해 반쪽 산출물이 남는다(내 첫 판이 그랬다).
    if (c.width < 430 || c.height < 240) {
        console.error("width 는 430 이상, height 는 240 이상이어야 한다 — "
                      "여백 70x2 + 범례 260 + 그림 자리가 들어가야 한다. "
                      "(받은 값: " + std::to_string(c.width) + "x" + std::to_string(c.height) + ")");
        return 1;
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
        // 리더는 `*INCLUDE` 안을 **읽지 않는다**(의도된 것이다). 실사용 덱은 거의 언제나
        // 나뉘어 있으므로(실측: 마스터가 737바이트에 INCLUDE 7 · PART 0 · NODE 0) 어느 파일을
        // 지목해야 하는지까지 말해 준다. 판정은 공용 스캐너를 쓴다 — 이 리포에서 같은 판정이
        // 셋으로 갈려 `*INCLUDE_PATH` 를 파일로 세는 오탐이 있었다.
        std::vector<std::string> rawLines;
        {
            std::ifstream f(c.model);
            std::string ln;
            while (std::getline(f, ln)) {
                if (!ln.empty() && ln.back() == '\r') ln.pop_back();
                rawLines.push_back(ln);
            }
        }
        const auto un = include_scan::scan(rawLines);
        if (un.count > 0) {
            console.info("  이 덱은 `*INCLUDE` 로 쪼개져 있고 리더는 그 안을 읽지 않는다 — " +
                         std::to_string(un.count) + "개:");
            for (const auto& nm : un.names) console.info("    " + nm);
            if (un.truncatedNames) console.info("    …");
            console.info("  기하가 든 파일(보통 `*NODE`·`*ELEMENT_*` 가 있는 메시 파일)을 model: 에 지목하라.");
        }
        return 1;
    }

    console.header("Section (plane cut): " + Platform::getFilename(c.model));

    auto [bmin, bmax] = mesh.getBoundingBox();
    const Vector3D ext = bmax - bmin;
    const double extArr[3] = {ext.x, ext.y, ext.z};
    const double minArr[3] = {bmin.x, bmin.y, bmin.z};

    // ── 자르는 알맹이. 평면 axis=val 로 자르고 다각형을 모은다 ──
    struct CutStat {
        std::set<int> pids;
        long long polys = 0;
        double uMin = 1e300, uMax = -1e300, vMin = 1e300, vMax = -1e300;
        double uExt() const { return (uMax > uMin) ? uMax - uMin : 0.0; }
        double vExt() const { return (vMax > vMin) ? vMax - vMin : 0.0; }
        // 한 방향이 다른 방향의 1e-6 도 안 되면 단면이 **선에 가깝다** — 축 자동선택이 집으면
        // 쓸모없는 그림이 나온다(실측: 호 셸을 x 로 자르면 extent 0.000000 x 1.0).
        bool degenerate() const {
            const double big = std::max(uExt(), vExt());
            const double small = std::min(uExt(), vExt());
            return big <= 0.0 || small < 1e-6 * big;
        }
    };
    auto cut = [&](int axis, double val, std::vector<Poly>* out,
                   long long* nodeHits, long long* thinCuts) -> CutStat {
        CutStat st;
        std::set<int>& hitPids = st.pids;
        if (nodeHits) *nodeHits = 0;
        if (thinCuts) *thinCuts = 0;
        // 평면 위에 놓인 절점 수 — 층 경계에 정확히 걸렸는지 본다
        if (nodeHits) {
            const double tol = 1e-12 * std::max(1.0, extArr[axis]);
            for (const auto& [nid, n] : mesh.nodes) {
                (void)nid;
                if (std::fabs(coordOf(n, axis) - val) <= tol) (*nodeHits)++;
            }
        }
        for (const auto& [eid, elem] : mesh.elements) {
            (void)eid;
            const auto& edges = edgesFor(elem.type);
            // 요소 크기로 중복 판정 공차를 잡는다 — 절대 공차를 박으면 단위가 다른 덱에서 틀린다
            double elemScale = 0.0;
            Vector3D cen(0, 0, 0);
            int nValid = 0;
            {
                Vector3D lo(1e300, 1e300, 1e300), hi(-1e300, -1e300, -1e300);
                for (int k = 0; k < Element::NUM_NODES; ++k) {
                    const int nid = elem.nodeIds[k];
                    if (nid <= 0) continue;
                    auto it = mesh.nodes.find(nid);
                    if (it == mesh.nodes.end()) continue;
                    const Vector3D& p = it->second.position;
                    lo.x = std::min(lo.x, p.x); lo.y = std::min(lo.y, p.y); lo.z = std::min(lo.z, p.z);
                    hi.x = std::max(hi.x, p.x); hi.y = std::max(hi.y, p.y); hi.z = std::max(hi.z, p.z);
                    cen = cen + p;
                    ++nValid;
                }
                if (nValid == 0) continue;
                cen = cen * (1.0 / (double)nValid);
                const Vector3D d = hi - lo;
                elemScale = std::max(d.x, std::max(d.y, d.z));
            }
            if (elemScale <= 0.0) continue;
            const double dedup = 1e-9 * elemScale;

            std::vector<P2> pts;
            for (const auto& [a, b] : edges) {
                const int na = elem.nodeIds[a], nb = elem.nodeIds[b];
                if (na <= 0 || nb <= 0 || na == nb) continue;
                auto ia = mesh.nodes.find(na), ib = mesh.nodes.find(nb);
                if (ia == mesh.nodes.end() || ib == mesh.nodes.end()) continue;
                const Vector3D& pa = ia->second.position;
                const Vector3D& pb = ib->second.position;
                const double da = coordOf(ia->second, axis) - val;
                const double db = coordOf(ib->second, axis) - val;
                if (da == db) continue;                      // 평면과 평행한 모서리
                if ((da > 0.0) == (db > 0.0)) continue;      // 같은 쪽
                const double t = da / (da - db);
                if (t < 0.0 || t > 1.0) continue;
                const Vector3D q = pa + (pb - pa) * t;
                const P2 p = to2d(q, axis);
                bool dup = false;
                for (const P2& e : pts)
                    if (std::fabs(e.u - p.u) <= dedup && std::fabs(e.v - p.v) <= dedup) { dup = true; break; }
                if (!dup) pts.push_back(p);
            }
            if (pts.size() < 2) continue;
            if (pts.size() == 2) {
                // 선분 — 셸을 자르면 이것이 나온다(두께가 메시에 없다). 솔리드에서 나오면
                // 평면이 변·꼭짓점을 스친 퇴화 절단이다.
                if (thinCuts && elem.type != ElementType::QUAD4) (*thinCuts)++;
                if (elem.type == ElementType::QUAD4) {
                    // ⚠ 세는 것과 내보내는 것을 **분리한다** — 축 자동선택은 out=nullptr 로 도는데
                    //   여기서 셈까지 건너뛰면 셸만 있는 덱이 "세 축 다 0" 으로 거절됐다(실측).
                    hitPids.insert(elem.partId);
                    st.polys++;
                    for (const P2& q : pts) {
                        st.uMin = std::min(st.uMin, q.u); st.uMax = std::max(st.uMax, q.u);
                        st.vMin = std::min(st.vMin, q.v); st.vMax = std::max(st.vMax, q.v);
                    }
                    if (out) {
                        Poly p;
                        p.pid = elem.partId;
                        p.shell = true;
                        p.pts = pts;
                        out->push_back(p);
                    }
                }
                continue;
            }
            // 각도 정렬 — 볼록 단면에서 맞다. 뒤집힌 요소(음수 야코비안)에서는 순서가 틀릴 수
            // 있으므로 음수 개수를 매니페스트에 함께 싣는다.
            const P2 cc = to2d(cen, axis);
            std::sort(pts.begin(), pts.end(), [&](const P2& a, const P2& b) {
                return std::atan2(a.v - cc.v, a.u - cc.u) < std::atan2(b.v - cc.v, b.u - cc.u);
            });
            if (out) {
                Poly p;
                p.pid = elem.partId;
                p.pts = pts;
                out->push_back(p);
            }
            hitPids.insert(elem.partId);
            st.polys++;
            for (const P2& q : pts) {
                st.uMin = std::min(st.uMin, q.u); st.uMax = std::max(st.uMax, q.u);
                st.vMin = std::min(st.vMin, q.v); st.vMax = std::max(st.vMax, q.v);
            }
        }
        return st;
    };

    // ── 축 선택. "적층 방향에 수직" 이 규칙이 아니다 — 이 덱에서 층이 어느 축으로 쌓였나다.
    //    실측: 배터리 덱은 z=const 가 61 파트 중 1개만 맞고 x·y 는 56개. 감긴 덱은 반대다. ──
    int axis = c.axis;
    std::string axisWhy;
    const char* AX = "xyz";
    if (axis < 0) {
        // 규칙은 **"적층 방향에 수직" 이 아니다** — 이 덱에서 층이 어느 축으로 쌓였나다.
        //   ① 퇴화(단면이 선에 가까운) 축을 먼저 뺀다  ② 파트를 가장 많이 만나는 축
        //   ③ 동점이면 다각형이 많은 축(정보가 더 많다)
        // 실측 — 배터리 덱은 z 가 61 중 1파트. 호 셸은 세 축이 1파트 동점인데 x 는 extent 0 이고
        // z(48 다각형)가 쓸모 있는 호 단면이다.
        int best = -1;
        size_t bestHit = 0;
        long long bestPolys = 0;
        std::string tally;
        CutStat stats[3];
        for (int a = 0; a < 3; ++a) {
            const double mid = minArr[a] + 0.5 * extArr[a];
            stats[a] = cut(a, mid, nullptr, nullptr, nullptr);
            char t[128];
            std::snprintf(t, sizeof(t), "%s%c=%zu파트/%lld다각형%s",
                          tally.empty() ? "" : " · ", AX[a], stats[a].pids.size(),
                          stats[a].polys, stats[a].degenerate() ? "(선에 가깝다)" : "");
            tally += t;
        }
        for (int pass = 0; pass < 2; ++pass) {
            for (int a = 0; a < 3; ++a) {
                if (pass == 0 && stats[a].degenerate()) continue;   // 1차: 퇴화는 뺀다
                const size_t hit = stats[a].pids.size();
                if (hit == 0) continue;
                if (hit > bestHit || (hit == bestHit && stats[a].polys > bestPolys)) {
                    bestHit = hit; bestPolys = stats[a].polys; best = a;
                }
            }
            if (best >= 0) break;   // 2차는 전부 퇴화일 때만 돈다
        }
        if (best < 0 || bestHit == 0) {
            console.error("세 축 어디로도 자를 수 없다 — 어느 평면도 요소를 만나지 않는다.");
            console.info("  축별 결과: " + tally);
            return 1;
        }
        axis = best;
        axisWhy = "auto (" + tally + ")";
        if (bestHit <= 1)
            console.warning("어느 축으로 잘라도 파트 1개만 만난다 — 적층이라면 축이 맞는지 보라.");
        if (stats[axis].degenerate())
            console.warning("고른 축의 단면이 선에 가깝다 — 세 축이 모두 그렇다. 축을 직접 주라.");
    } else {
        axisWhy = "config: axis 를 지정했다";
    }
    const double atDefault = minArr[axis] + 0.5 * extArr[axis];
    double at = c.hasAt ? c.at : atDefault;

    // ── ★평면이 절점층에 걸렸으면 ε 비켜 다시 자른다.
    //    실측: 배터리 z=0.528(층 경계)에서 다각형 4,800 → 9,600(두 배), 절점 적중 115,200.
    //    사용자가 가장 보고 싶은 자리가 바로 이 퇴화 케이스다. 공차 0 을 쓰지 않는다. ──
    std::vector<Poly> polys;
    long long nodeHits = 0, thinCuts = 0;
    std::set<int> hitPids = cut(axis, at, &polys, &nodeHits, &thinCuts).pids;
    double nudge = 0.0;
    if (nodeHits > 0) {
        nudge = 1e-6 * std::max(1.0, extArr[axis]);
        polys.clear();
        long long h2 = 0, t2 = 0;
        hitPids = cut(axis, at + nudge, &polys, &h2, &t2).pids;
        nodeHits = h2 == 0 ? nodeHits : h2;   // 비킨 뒤에도 걸리면 그 수를 쓴다
        thinCuts = t2;
        at += nudge;
    }

    if (polys.empty()) {
        console.error("이 평면은 아무 요소도 자르지 않는다 — 그림을 내지 않는다.");
        console.info("  축 " + std::string(1, AX[axis]) + " · 위치 " + std::to_string(at));
        console.info("  셸만 있는 덱을 셸 평면과 평행한 축으로 자르면 이렇게 된다. axis 를 바꿔 보라.");
        return 1;
    }

    // ── 파트 메타 ──
    struct PartInfo {
        int pid = 0;
        std::string title;
        long long polys = 0;
        bool shell = false;
        double thickness = 0.0;
        std::string thickWhy;
        double E = 0.0;
        // 단면 안에서 이 파트가 차지하는 2D 범위 — 그리는 쪽이 **최소 피처**를 알아야
        // 선 굵기가 층을 먹는지 판정할 수 있다(실측: 실제 셸 적층 두께 0.008~0.153).
        double uMin = 1e300, uMax = -1e300, vMin = 1e300, vMax = -1e300;
        double uExt() const { return (uMax > uMin) ? uMax - uMin : 0.0; }
        double vExt() const { return (vMax > vMin) ? vMax - vMin : 0.0; }
        double thin() const { return std::min(uExt(), vExt()); }
    };
    std::map<int, PartInfo> pinfo;
    for (const Poly& p : polys) {
        PartInfo& pi = pinfo[p.pid];
        pi.pid = p.pid;
        pi.polys++;
        if (p.shell) pi.shell = true;
        for (const P2& q : p.pts) {
            pi.uMin = std::min(pi.uMin, q.u); pi.uMax = std::max(pi.uMax, q.u);
            pi.vMin = std::min(pi.vMin, q.v); pi.vMax = std::max(pi.vMax, q.v);
        }
    }
    for (auto& [pid, pi] : pinfo) {
        auto pit = mesh.parts.find(pid);
        if (pit == mesh.parts.end()) {
            pi.thickWhy = "*PART 카드가 없다";
            continue;
        }
        pi.title = pit->second.name;
        auto mit = mesh.materials.find(pit->second.materialId);
        if (mit != mesh.materials.end()) pi.E = mit->second.E;
        if (pi.shell) {
            auto sit = mesh.shellSections.find(pit->second.sectionId);
            if (sit != mesh.shellSections.end() && sit->second.thickness > 0) {
                pi.thickness = sit->second.thickness;
                pi.thickWhy = "*SECTION_SHELL T1 에서 읽었다 — 메시가 아니다";
            } else {
                pi.thickWhy = "셸인데 *SECTION_SHELL 두께가 없다 — 선으로 그린다. 0 으로 쓰지 않는다";
            }
        }
    }

    // ── 야코비안 — 음수면 꼭짓점 순서가 뒤집혀 채움이 거짓이 된다.
    //    추적 덱 489장 중 111장이 정상 픽스처인데 음수다. 셸은 제외하고 그 수를 적는다. ──
    long long shellsExcluded = 0;
    for (const auto& [eid, e] : mesh.elements) {
        (void)eid;
        if (e.type == ElementType::QUAD4) shellsExcluded++;
    }

    // 단면의 2D 범위
    double uMin = 1e300, uMax = -1e300, vMin = 1e300, vMax = -1e300;
    for (const Poly& p : polys)
        for (const P2& q : p.pts) {
            uMin = std::min(uMin, q.u); uMax = std::max(uMax, q.u);
            vMin = std::min(vMin, q.v); vMax = std::max(vMax, q.v);
        }
    const double uExt = uMax - uMin, vExt = vMax - vMin;

    const char* UV[3][2] = {{"y","z"},{"z","x"},{"x","y"}};
    console.keyValue("Axis", std::string(1, AX[axis]));
    console.keyValue("Axis chosen", axisWhy);
    console.keyValue("Position", std::to_string(at) + (nudge > 0 ? "  (ε 비켰다)" : ""));
    console.keyValue("Plane 2D basis", std::string("(") + UV[axis][0] + ", " + UV[axis][1] + ")");
    console.keyValue("Polygons", std::to_string(polys.size()));
    console.keyValue("Parts hit / total", std::to_string(hitPids.size()) + " / " +
                     std::to_string(mesh.parts.size()));
    console.keyValue("Node-on-plane hits", std::to_string(nodeHits));
    console.keyValue("Degenerate cuts (<3 pts)", std::to_string(thinCuts));
    console.keyValue("Section extent", std::to_string(uExt) + " x " + std::to_string(vExt));
    {
        const double big = std::max(uExt, vExt), small = std::min(uExt, vExt);
        if (big <= 0.0) {
            console.warning("단면이 한 점이다 — 그릴 것이 없다.");
        } else if (small < 1e-6 * big) {
            // 0 으로 나누면 1e21 같은 쓰레기 비가 찍힌다(실측). 비를 내지 않고 사실을 말한다.
            console.warning("단면이 **선에 가깝다** — 한 방향 범위가 " + std::to_string(small) +
                            " 다. 축을 바꾸면 2차원 단면이 나온다.");
        } else {
            const double ar = big / small;
            console.keyValue("Section aspect", std::to_string(ar) + " : 1");
            if (ar > 20.0)
                console.info("참고: 종횡비가 커서 등축으로 그리면 얇은 쪽이 보이지 않는다 — "
                             "그리는 쪽이 축마다 축척을 따로 잡고 배율을 적어야 한다.");
        }
    }
    // 최소 피처 — 가장 얇은 파트의 얇은 쪽 범위. 그리는 쪽이 이것으로 과장 배율과
    // 선 굵기 경고를 정한다. 셸은 두께가 메시에 없으니 *SECTION_SHELL 값을 쓴다.
    double minFeature = 1e300;
    int minFeaturePid = 0;
    for (const auto& [pid, pi] : pinfo) {
        const double t = pi.shell ? (pi.thickness > 0 ? pi.thickness : 0.0) : pi.thin();
        if (t > 0.0 && t < minFeature) { minFeature = t; minFeaturePid = pid; }
    }
    if (minFeature < 1e300) {
        const double big = std::max(uExt, vExt);
        console.keyValue("Min feature", std::to_string(minFeature) + "  (PID " +
                         std::to_string(minFeaturePid) + ")");
        if (big > 0.0)
            console.keyValue("Min feature / extent", std::to_string(minFeature / big) +
                             "  → 1200px 등축이면 " + std::to_string(minFeature / big * 1200.0) + " px");
    } else {
        minFeature = 0.0;
        console.warning("최소 피처를 못 구했다 — 두께를 읽은 파트가 없다.");
    }
    console.info("단위: 알 수 없다 — LS-DYNA 덱은 단위를 담지 않는다.");

    // ── 산출 JSON ──
    const std::string outPath = c.output + "_section.json";
    std::ofstream o(outPath);
    if (!o.is_open()) { console.error("Cannot write: " + outPath); return 1; }
    char buf[512];
    o << "{\n";
    o << "  \"model\": \"" << jesc(c.model) << "\",\n";
    o << "  \"axis\": \"" << AX[axis] << "\",\n";
    std::snprintf(buf, sizeof(buf), "  \"at\": %.17g,\n", at); o << buf;
    std::snprintf(buf, sizeof(buf), "  \"nudge\": %.17g,\n", nudge); o << buf;
    o << "  \"axis_chosen_because\": \"" << jesc(axisWhy) << "\",\n";
    o << "  \"basis\": [\"" << UV[axis][0] << "\", \"" << UV[axis][1] << "\"],\n";
    o << "  \"units\": \"unknown — LS-DYNA decks carry no units\",\n";
    o << "  \"polygons\": " << polys.size() << ",\n";
    o << "  \"parts_hit\": " << hitPids.size() << ",\n";
    o << "  \"parts_total\": " << mesh.parts.size() << ",\n";
    o << "  \"node_plane_hits\": " << nodeHits << ",\n";
    o << "  \"degenerate_cuts\": " << thinCuts << ",\n";
    o << "  \"shells_excluded_from_jacobian\": " << shellsExcluded << ",\n";
    std::snprintf(buf, sizeof(buf), "  \"extent\": [%.17g, %.17g],\n", uExt, vExt); o << buf;
    std::snprintf(buf, sizeof(buf), "  \"bounds\": [%.17g, %.17g, %.17g, %.17g],\n",
                  uMin, vMin, uMax, vMax); o << buf;
    std::snprintf(buf, sizeof(buf), "  \"min_feature\": %.17g,\n", minFeature); o << buf;
    o << "  \"min_feature_pid\": " << minFeaturePid << ",\n";
    o << "  \"parts\": [\n";
    bool firstP = true;
    for (const auto& [pid, pi] : pinfo) {
        if (!firstP) o << ",\n";
        firstP = false;
        o << "    {\"pid\": " << pid
          << ", \"title\": \"" << jesc(pi.title) << "\""
          << ", \"polys\": " << pi.polys
          << ", \"shell\": " << (pi.shell ? "true" : "false");
        o << ", \"thickness\": ";
        if (pi.thickness > 0) {
            std::snprintf(buf, sizeof(buf), "%.17g", pi.thickness);
            o << buf;
        } else {
            o << "null";
        }
        o << ", \"thickness_note\": \"" << jesc(pi.thickWhy) << "\"";
        std::snprintf(buf, sizeof(buf), ", \"E\": %.17g", pi.E);
        o << buf;
        std::snprintf(buf, sizeof(buf), ", \"extent\": [%.9g, %.9g], \"thin\": %.9g",
                      pi.uExt(), pi.vExt(), pi.thin());
        o << buf << "}";
    }
    o << "\n  ],\n";
    o << "  \"polys\": [\n";
    bool first = true;
    for (const Poly& p : polys) {
        if (!first) o << ",\n";
        first = false;
        o << "    {\"pid\": " << p.pid << ", \"shell\": " << (p.shell ? "true" : "false") << ", \"pts\": [";
        for (size_t i = 0; i < p.pts.size(); ++i) {
            std::snprintf(buf, sizeof(buf), "%s[%.9g,%.9g]", i ? "," : "", p.pts[i].u, p.pts[i].v);
            o << buf;
        }
        o << "]}";
    }
    o << "\n  ]\n}\n";
    o.close();

    console.success("Wrote: " + outPath);

    // ── 그림(SVG). 구현을 **한 자리**에 둔다 — 프런트와 MCP 가 각각 그리면 둘이 갈린다.
    //    외부 의존성 0: 문자열을 쓰지만 파트 제목은 전부 xesc 를 지난다.
    if (!c.svg) return 0;
    const std::string svgPath = c.output + "_section.svg";
    std::ofstream g(svgPath);
    if (!g.is_open()) { console.error("Cannot write: " + svgPath); return 1; }

    const double M = 70.0;                       // 여백 — 눈금자·꼬리말 자리
    const double legendW = 260.0;
    const double plotW = c.width - M - legendW;
    const double plotH = c.height - 2 * M;
    if (plotW < 100 || plotH < 100) {
        console.error("내부 오류: 그림 자리가 음수다 — width·height 검증이 새어 나왔다.");
        return 1;
    }
    // ★비등방 축척이 **기본**이다. 실측 — 실제 적층은 가로:최박층이 1:9,375 라 등축으로 그리면
    //   층이 보이지 않는다(1200px 에서 0.128 px). 그래서 두 축을 따로 잡고 **배율을 적는다.**
    //   적지 않으면 두께를 과장한 그림이 그럴듯하게 나온다 — 그것이 가장 나쁜 실패다.
    double sx = (uExt > 0) ? plotW / uExt : 1.0;
    double sy = (vExt > 0) ? plotH / vExt : 1.0;
    if (c.isotropic) { const double m2 = std::min(sx, sy); sx = sy = m2; }
    // ★사람이 읽을 값으로 적는다. `sy/sx` 는 **역수**가 될 수 있다 — 실측 배터리 덱(축 y, 기저
    //   (z,x))은 얇은 축이 u 이고 sy/sx = 0.0289 가 찍혔는데 실제로는 **u 가 34.6배 확대**된
    //   것이다. 그래서 '어느 축이 몇 배 확대됐나' 로 적는다.
    const int magAxisIdx = (sx >= sy) ? 0 : 1;                 // 0 = u(가로), 1 = v(세로)
    const double magnify = (std::min(sx, sy) > 0) ? std::max(sx, sy) / std::min(sx, sy) : 1.0;
    const char* magAxisName = UV[axis][magAxisIdx];

    auto PX = [&](double u) { return M + (u - uMin) * sx; };
    auto PY = [&](double v) { return (c.height - M) - (v - vMin) * sy; };   // y 를 위로

    g << "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n";
    g << "<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"" << c.width
      << "\" height=\"" << c.height << "\" viewBox=\"0 0 " << c.width << " " << c.height
      << "\" font-family=\"Malgun Gothic, Apple SD Gothic Neo, Noto Sans KR, NanumGothic, sans-serif\">\n";
    g << "<rect width=\"" << c.width << "\" height=\"" << c.height << "\" fill=\"#ffffff\"/>\n";

    // 다각형 — 선 굵기를 모델 단위로 환산해 최소 피처와 견준다
    const double strokePx = 0.6;
    const double mmPerPxX = (sx > 0) ? 1.0 / sx : 0.0;
    const double mmPerPxY = (sy > 0) ? 1.0 / sy : 0.0;
    // ★최소 피처가 **몇 픽셀**인가 — 그것이 판정 기준이다. 선 굵기를 **긴 축**의 해상도와
    //   견주면 엉뚱한 답이 나온다(층을 덮는 획은 **얇은 축 방향**이다). 그래서 그 파트가 얇은
    //   방향의 축척을 쓴다. 1.5px 미만이면 획을 줄여도 보이지 않는다.
    double minFeaturePx = 0.0;
    if (minFeature > 0.0) {
        const PartInfo* mp = nullptr;
        auto it = pinfo.find(minFeaturePid);
        if (it != pinfo.end()) mp = &it->second;
        const bool thinIsU = mp ? (mp->uExt() <= mp->vExt()) : (uExt <= vExt);
        minFeaturePx = minFeature * (thinIsU ? sx : sy);
    }
    const bool featureTooThin = (minFeature > 0.0 && minFeaturePx < 1.5);
    const bool strokeEatsFeature = (minFeature > 0.0 && strokePx >= minFeaturePx);

    g << "<g stroke=\"#333333\" stroke-width=\"" << strokePx << "\" stroke-linejoin=\"round\">\n";
    for (const Poly& p : polys) {
        const char* col = colorFor(p.pid);
        if (p.shell) {
            // 셸은 두께가 메시에 없다 — 아는 경우에만 띠로, 모르면 **점선**으로 그린다.
            const PartInfo& pi = pinfo[p.pid];
            if (pi.thickness > 0 && p.pts.size() == 2) {
                const double du = p.pts[1].u - p.pts[0].u, dv = p.pts[1].v - p.pts[0].v;
                const double L = std::sqrt(du * du + dv * dv);
                if (L > 0) {
                    const double nu = -dv / L * 0.5 * pi.thickness;
                    const double nv =  du / L * 0.5 * pi.thickness;
                    char b[256];
                    std::snprintf(b, sizeof(b),
                        "<polygon points=\"%.3f,%.3f %.3f,%.3f %.3f,%.3f %.3f,%.3f\" fill=\"%s\" fill-opacity=\"0.85\"/>\n",
                        PX(p.pts[0].u + nu), PY(p.pts[0].v + nv), PX(p.pts[1].u + nu), PY(p.pts[1].v + nv),
                        PX(p.pts[1].u - nu), PY(p.pts[1].v - nv), PX(p.pts[0].u - nu), PY(p.pts[0].v - nv), col);
                    g << b;
                    continue;
                }
            }
            char b[256];
            std::snprintf(b, sizeof(b),
                "<line x1=\"%.3f\" y1=\"%.3f\" x2=\"%.3f\" y2=\"%.3f\" stroke=\"%s\" stroke-width=\"1.4\" stroke-dasharray=\"4 3\"/>\n",
                PX(p.pts[0].u), PY(p.pts[0].v), PX(p.pts[1].u), PY(p.pts[1].v), col);
            g << b;
            continue;
        }
        g << "<polygon fill=\"" << col << "\" points=\"";
        for (size_t i = 0; i < p.pts.size(); ++i) {
            char b[64];
            std::snprintf(b, sizeof(b), "%s%.3f,%.3f", i ? " " : "", PX(p.pts[i].u), PY(p.pts[i].v));
            g << b;
        }
        g << "\"/>\n";
    }
    g << "</g>\n";

    // 눈금자를 **두 축에 각각** 둔다 — 하나만 두면 과장된 축에서 사람이 잘못 읽는다
    auto niceStep = [](double span) {
        if (span <= 0) return 1.0;
        const double raw = span / 4.0;
        const double mag = std::pow(10.0, std::floor(std::log10(raw)));
        const double n = raw / mag;
        const double m = (n < 1.5) ? 1.0 : (n < 3.5) ? 2.0 : (n < 7.5) ? 5.0 : 10.0;
        return m * mag;
    };
    char b[512];
    const double stepU = niceStep(uExt), stepV = niceStep(vExt);
    g << "<g font-size=\"11\" fill=\"#444444\" stroke=\"none\">\n";
    std::snprintf(b, sizeof(b),
        "<line x1=\"%.2f\" y1=\"%.2f\" x2=\"%.2f\" y2=\"%.2f\" stroke=\"#444\" stroke-width=\"1\"/>\n",
        PX(uMin), c.height - M + 14, PX(uMin + stepU), c.height - M + 14);
    g << b;
    std::snprintf(b, sizeof(b), "<text x=\"%.2f\" y=\"%.2f\">%s %.6g (%s)</text>\n",
                  PX(uMin), c.height - M + 30, UV[axis][0], stepU, "가로 눈금");
    g << b;
    std::snprintf(b, sizeof(b),
        "<line x1=\"%.2f\" y1=\"%.2f\" x2=\"%.2f\" y2=\"%.2f\" stroke=\"#444\" stroke-width=\"1\"/>\n",
        M - 16, PY(vMin), M - 16, PY(vMin + stepV));
    g << b;
    std::snprintf(b, sizeof(b), "<text x=\"%.2f\" y=\"%.2f\" transform=\"rotate(-90 %.2f %.2f)\">%s %.6g (세로 눈금)</text>\n",
                  M - 22, PY(vMin), M - 22, PY(vMin), UV[axis][1], stepV);
    g << b;
    g << "</g>\n";

    // 범례를 **그림 안에 굽는다** — 따로 떨어지면 내보낸 SVG 가 혼자 못 선다
    double ly = M;
    const double lx = c.width - legendW + 10;
    g << "<g font-size=\"12\" stroke=\"none\">\n";
    std::snprintf(b, sizeof(b), "<text x=\"%.1f\" y=\"%.1f\" font-weight=\"bold\" fill=\"#222\">단면 — 축 %c = %.6g</text>\n",
                  lx, ly, AX[axis], at);
    g << b; ly += 20;
    bool titleStripped = false;
    int shown = 0, omitted = 0;
    for (const auto& [pid, pi] : pinfo) {
        if (shown >= c.maxParts) { omitted++; continue; }
        ++shown;
        std::snprintf(b, sizeof(b), "<rect x=\"%.1f\" y=\"%.1f\" width=\"12\" height=\"12\" fill=\"%s\"/>\n",
                      lx, ly - 10, colorFor(pid));
        g << b;
        const std::string t = pi.title.empty() ? ("pid " + std::to_string(pid)) : xesc(pi.title, &titleStripped);
        std::snprintf(b, sizeof(b), "<text x=\"%.1f\" y=\"%.1f\" fill=\"#222\">%d · %s</text>\n",
                      lx + 18, ly, pid, t.c_str());
        g << b; ly += 15;
        if (pi.shell) {
            if (pi.thickness > 0)
                std::snprintf(b, sizeof(b), "<text x=\"%.1f\" y=\"%.1f\" font-size=\"10\" fill=\"#666\">셸 t=%.6g (*SECTION_SHELL)</text>\n",
                              lx + 18, ly, pi.thickness);
            else
                std::snprintf(b, sizeof(b), "<text x=\"%.1f\" y=\"%.1f\" font-size=\"10\" fill=\"#a33\">셸 두께 없음 — 점선</text>\n",
                              lx + 18, ly);
            g << b; ly += 14;
        } else {
            std::snprintf(b, sizeof(b), "<text x=\"%.1f\" y=\"%.1f\" font-size=\"10\" fill=\"#666\">두께(단면) %.6g · E %.6g</text>\n",
                          lx + 18, ly, pi.thin(), pi.E);
            g << b; ly += 14;
        }
        if (ly > c.height - M - 90) { omitted = (int)pinfo.size() - shown; break; }
    }
    if (omitted > 0) {
        std::snprintf(b, sizeof(b), "<text x=\"%.1f\" y=\"%.1f\" font-size=\"11\" fill=\"#a33\">… 파트 %d개를 뺐다 (전체 %zu)</text>\n",
                      lx, ly + 4, omitted, pinfo.size());
        g << b; ly += 18;
    }
    g << "</g>\n";

    // ★꼬리말 — 그림이 거짓말하지 않게 하는 줄들. **배율을 적는 것이 기능의 일부다.**
    double fy = c.height - 34;
    g << "<g font-size=\"11\" fill=\"#333\" stroke=\"none\">\n";
    std::snprintf(b, sizeof(b),
        "<text x=\"%.1f\" y=\"%.1f\">%s 축 %.4g배 확대 (가로 %.6g/px · 세로 %.6g/px) · 단위 없음(LS-DYNA 덱)</text>\n",
        M, fy, magAxisName, magnify, mmPerPxX, mmPerPxY);
    g << b; fy += 14;
    std::snprintf(b, sizeof(b),
        "<text x=\"%.1f\" y=\"%.1f\">파트 %zu/%zu · 다각형 %zu · 최소피처 %.6g = %.2f px%s%s</text>\n",
        M, fy, hitPids.size(), mesh.parts.size(), polys.size(), minFeature, minFeaturePx,
        nudge > 0 ? " · 평면이 절점층에 걸려 ε 비켰다" : "",
        titleStripped ? " · 제목에 제어문자가 있어 ? 로 바꿨다" : "");
    g << b; fy += 14;
    if (featureTooThin) {
        std::snprintf(b, sizeof(b),
            "<text x=\"%.1f\" y=\"%.1f\" fill=\"#a33\">⚠ 최소피처가 %.2f px 다 — 이 그림에서 그 층은 보이지 않는다(획을 줄여도 안 보인다)</text>\n",
            M, fy, minFeaturePx);
        g << b;
    } else if (strokeEatsFeature) {
        std::snprintf(b, sizeof(b),
            "<text x=\"%.1f\" y=\"%.1f\" fill=\"#a33\">⚠ 선 굵기(%.2f px)가 최소피처(%.2f px)만 하다 — 층이 붙어 보이는 것은 획이다</text>\n",
            M, fy, strokePx, minFeaturePx);
        g << b;
    }
    g << "</g>\n</svg>\n";
    g.close();

    if (featureTooThin)
        console.warning("최소 피처가 " + std::to_string(minFeaturePx) +
                        " px 다 — 이 그림에서 그 층은 보이지 않는다. width·height 를 키우거나 "
                        "범위를 좁히라(획을 줄여도 안 보인다).");
    else if (strokeEatsFeature)
        console.warning("선 굵기가 최소 피처만 하다 — 층이 붙어 보이는 것은 기하가 아니라 획이다.");
    console.keyValue("Magnified axis", std::string(magAxisName) + "  x" +
                     std::to_string(magnify) + (c.isotropic ? "  (등축이라 1)" : ""));
    console.keyValue("Min feature in px", std::to_string(minFeaturePx));
    console.success("Wrote: " + svgPath);
    return 0;
}
