// 접힘 곡면(평면 elastica)의 중심선을 푸는 op — 정점 곡률을 고정하고 B 를 연속법+이분법으로 찾는다.
#include "foldsurface.h"

#include "cli/ConsoleOutput.h"
#include "util/YamlComment.h"

#include <algorithm>
#include <cmath>
#include <cstdio>
#include <fstream>
#include <limits>
#include <string>
#include <vector>

using KooRemapper::ConsoleOutput;
using KooRemapper::yamlStripComment;

namespace {

struct Config {
    std::string output;
    double arcLength = 0.0;   // 굽힘 영역의 호 길이 L
    double foldAngle = 0.0;   // 접선 총회전 α [deg]
    double minRadius = 0.0;   // 목표 최소 곡률반경 R
    int points = 201;
};

std::string trim(const std::string& s) {
    size_t a = s.find_first_not_of(" \t");
    if (a == std::string::npos) return "";
    size_t b = s.find_last_not_of(" \t\r");
    return s.substr(a, b - a + 1);
}

// 평면 elastica: (x, y, θ, κ)' = (cosθ, sinθ, κ, -B sinθ)
struct State {
    double x = 0.0, y = 0.0, th = 0.0, k = 0.0;
};

State deriv(const State& s, double B) {
    State d;
    d.x = std::cos(s.th);
    d.y = std::sin(s.th);
    d.th = s.k;
    d.k = -B * std::sin(s.th);
    return d;
}

State step(const State& s, double B, double h) {
    State a = deriv(s, B);
    State s2{s.x + 0.5 * h * a.x, s.y + 0.5 * h * a.y, s.th + 0.5 * h * a.th, s.k + 0.5 * h * a.k};
    State b = deriv(s2, B);
    State s3{s.x + 0.5 * h * b.x, s.y + 0.5 * h * b.y, s.th + 0.5 * h * b.th, s.k + 0.5 * h * b.k};
    State c = deriv(s3, B);
    State s4{s.x + h * c.x, s.y + h * c.y, s.th + h * c.th, s.k + h * c.k};
    State e = deriv(s4, B);
    State out;
    out.x = s.x + h / 6.0 * (a.x + 2 * b.x + 2 * c.x + e.x);
    out.y = s.y + h / 6.0 * (a.y + 2 * b.y + 2 * c.y + e.y);
    out.th = s.th + h / 6.0 * (a.th + 2 * b.th + 2 * c.th + e.th);
    out.k = s.k + h / 6.0 * (a.k + 2 * b.k + 2 * c.k + e.k);
    return out;
}

// 정점(s=0, θ=0, κ=κ0)에서 반길이 L2 까지 적분한다. trace 를 주면 매 단계를 담는다.
State integrateHalf(double B, double k0, double L2, int nsteps, std::vector<State>* trace) {
    State s;
    s.k = k0;
    if (trace) { trace->clear(); trace->reserve(nsteps + 1); trace->push_back(s); }
    const double h = L2 / nsteps;
    for (int i = 0; i < nsteps; ++i) {
        s = step(s, B, h);
        if (trace) trace->push_back(s);
    }
    return s;
}

bool parseYaml(const std::string& path, Config& c, ConsoleOutput& console) {
    std::ifstream f(path);
    if (!f.is_open()) { console.error("Cannot open: " + path); return false; }
    KooRemapper::yamlSkipBOM(f);   // 윈도우 편집기의 BOM 이 첫 키를 망가뜨린다
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
            if (key == "output") c.output = val;
            else if (key == "arc_length") c.arcLength = std::stod(val);
            else if (key == "fold_angle") c.foldAngle = std::stod(val);
            else if (key == "min_radius") c.minRadius = std::stod(val);
            else if (key == "points") c.points = std::stoi(val);
            else console.warning("모르는 키는 무시한다: " + key);
        } catch (const std::exception&) {
            console.error("숫자를 읽을 수 없다: " + key + ": " + val);
            return false;
        }
    }
    return true;
}

std::string num(const char* f, double v) {
    char b[64];
    std::snprintf(b, sizeof(b), f, v);
    return std::string(b);
}

}  // namespace

int runFoldSurface(const std::string& yamlFile, ConsoleOutput& console) {
    Config c;
    if (!parseYaml(yamlFile, c, console)) return 1;

    if (c.output.empty()) { console.error("output: 이 필요하다"); return 1; }
    if (c.arcLength <= 0) { console.error("arc_length: 가 0 보다 커야 한다"); return 1; }
    if (c.minRadius <= 0) { console.error("min_radius: 가 0 보다 커야 한다"); return 1; }
    if (c.foldAngle <= 0 || c.foldAngle >= 360.0) {
        console.error("fold_angle: 은 0 과 360 도 사이여야 한다 (접선 총회전)");
        return 1;
    }
    if (c.points < 3) { console.error("points: 가 3 이상이어야 한다"); return 1; }

    const double L = c.arcLength;
    const double L2 = 0.5 * L;
    const double k0 = 1.0 / c.minRadius;          // 정점 곡률 = 목표 최소반경의 역수
    const double alpha = c.foldAngle * M_PI / 180.0;
    const double half = 0.5 * alpha;              // 반쪽이 돌아야 하는 각

    console.header("Fold surface (planar elastica)");
    console.keyValue("Arc length L", num("%.12g", L));
    console.keyValue("Fold angle (turn)", num("%.12g", c.foldAngle) + " deg");
    console.keyValue("Target min radius", num("%.12g", c.minRadius));

    // 원호(B=0)가 돌 수 있는 최대 각. 이보다 더 돌려면 반경이 더 작아져야 한다.
    const double turnMax = L / c.minRadius;
    if (alpha > turnMax) {
        console.error("이 길이와 최소반경으로는 그 각이 안 나온다 — B=0(원호)가 상한이다.");
        console.info("  최대 회전 = L/R = " + num("%.12g", turnMax * 180.0 / M_PI) + " deg");
        console.info("  이 각을 내려면 R <= " + num("%.12g", L / alpha) +
                     " 또는 L >= " + num("%.12g", alpha * c.minRadius) + " 가 필요하다.");
        return 1;
    }

    // θ 가 α/2 에 닿으려면 pendulum 의 되돌이점이 그보다 멀어야 한다:
    //   κ² = κ0² - 2B(1-cosθ)  →  B <= κ0² / (2(1-cos(α/2)))
    // 그래서 탐색 구간이 **유한하게 닫힌다.** elastica 는 다중해지만 이 구간을 연속법으로
    // 훑어 **첫 교차**를 집으면 분기가 결정론적으로 정해진다(뒤집힘이 가장 적은 해).
    const double oneMinusCos = 1.0 - std::cos(half);
    const double Bmax = (oneMinusCos > 0.0) ? (k0 * k0 / (2.0 * oneMinusCos))
                                            : std::numeric_limits<double>::max();

    const int nsteps = 20000;
    auto residual = [&](double B) {
        return integrateHalf(B, k0, L2, nsteps, nullptr).th - half;
    };

    double B = 0.0;
    const double r0 = residual(0.0);
    // r0 <= 0 은 α 가 원호 상한에 닿은 것이다. 해석적 상한 검사(L/R)는 이미 지났으니 여기서
    // 음수가 나오는 폭은 적분 누적 반올림(20000 단계에서 ~1e-12)뿐이다 — B=0 이 답이다.
    if (r0 <= 0.0) {
        B = 0.0;
    } else {
        // 연속법 — 0 에서 Bmax 까지 훑어 첫 부호 변화를 찾는다
        const int sweep = 20000;
        double bLo = 0.0, rLo = r0, bHi = -1.0, rHi = 0.0;
        for (int i = 1; i <= sweep; ++i) {
            const double b = Bmax * (double)i / sweep;
            const double r = residual(b);
            if ((rLo > 0.0) != (r > 0.0)) { bHi = b; rHi = r; break; }
            bLo = b; rLo = r;
        }
        if (bHi < 0.0) {
            console.error("해를 찾지 못했다 — 구간 [0, Bmax] 에서 부호가 바뀌지 않는다.");
            console.info("  Bmax = " + num("%.12g", Bmax) + ", 잔차(0) = " + num("%.6g", r0) +
                         ", 잔차(Bmax) = " + num("%.6g", rLo));
            return 1;
        }
        for (int i = 0; i < 200; ++i) {
            const double bm = 0.5 * (bLo + bHi);
            const double rm = residual(bm);
            if ((rLo > 0.0) != (rm > 0.0)) { bHi = bm; rHi = rm; }
            else { bLo = bm; rLo = rm; }
            if (bHi - bLo < 1e-16 * std::max(1.0, bHi)) break;
        }
        (void)rHi;
        B = 0.5 * (bLo + bHi);
    }

    std::vector<State> tr;
    const State endHalf = integrateHalf(B, k0, L2, nsteps, &tr);
    const double turnResidual = 2.0 * endHalf.th - alpha;

    // 뒤집힘(κ 부호 변화) 수 — 반쪽에서 세고 대칭이므로 두 배다
    int flipsHalf = 0;
    for (size_t i = 1; i < tr.size(); ++i)
        if ((tr[i - 1].k > 0.0) != (tr[i].k > 0.0)) flipsHalf++;

    // 곡률 최대가 정말 정점인가 — 그렇지 않으면 "최소반경 = 목표" 가 거짓말이 된다
    double kAbsMax = 0.0;
    for (const State& s : tr) kAbsMax = std::max(kAbsMax, std::fabs(s.k));

    // 굽힘 에너지 ∫κ²/2 ds (단위 EI 당), 전체 곡선
    double energy = 0.0;
    const double h = L2 / nsteps;
    for (size_t i = 1; i < tr.size(); ++i)
        energy += 0.5 * h * (0.5 * tr[i - 1].k * tr[i - 1].k + 0.5 * tr[i].k * tr[i].k) * 2.0;

    console.keyValue("B (force parameter)", num("%.12g", B));
    console.keyValue("B upper bound", num("%.12g", Bmax));
    console.keyValue("Achieved min radius", num("%.12g", 1.0 / kAbsMax));
    console.keyValue("Turn residual", num("%.3g", turnResidual) + " rad");
    console.keyValue("Curvature sign flips", std::to_string(2 * flipsHalf));
    console.keyValue("End separation", num("%.12g", 2.0 * std::fabs(endHalf.x)));
    console.keyValue("Apex-to-end height", num("%.12g", std::fabs(endHalf.y)));
    console.keyValue("Bending energy / EI", num("%.12g", energy));

    if (std::fabs(1.0 / kAbsMax - c.minRadius) > 1e-6 * c.minRadius) {
        console.error("최소 곡률반경이 목표와 다르다 — 정점이 곡률 최대가 아니다.");
        return 1;
    }
    if (std::fabs(turnResidual) > 1e-8) {
        console.error("끝점 잔차가 남았다 — BVP 가 안 풀렸다. 숫자를 내지 않는다.");
        return 1;
    }
    if (flipsHalf > 0) {
        console.warning("굽힘 영역이 " + std::to_string(2 * flipsHalf) +
                        "번 뒤집히는 물결 모양이다 — 이 길이로 이 각을 이 반경으로 접으면 그렇게 된다.");
        console.info("  단순한 한 방향 굽힘을 원하면 arc_length 를 R*α = " +
                     num("%.12g", c.minRadius * alpha) + " 에 가깝게 잡으라.");
    }

    // 전체 곡선 — 정점 기준 반쪽을 거울로 붙인다(ODE 가 x→-x, θ→-θ 에 대해 정확히 대칭이다)
    const int halfPts = (c.points + 1) / 2;
    const std::string csvPath = c.output + "_curve.csv";
    std::ofstream out(csvPath);
    if (!out.is_open()) { console.error("Cannot write: " + csvPath); return 1; }
    out << "s,x,y,theta_deg,curvature,radius\n";
    auto emit = [&](double s, const State& st, int mirror) {
        const double x = mirror ? -st.x : st.x;
        const double th = mirror ? -st.th : st.th;
        const double r = (std::fabs(st.k) > 0.0) ? 1.0 / std::fabs(st.k)
                                                 : std::numeric_limits<double>::infinity();
        char buf[256];
        std::snprintf(buf, sizeof(buf), "%.12g,%.12g,%.12g,%.12g,%.12g,%.12g\n",
                      s, x, st.y, th * 180.0 / M_PI, st.k, r);
        out << buf;
    };
    for (int i = halfPts - 1; i >= 0; --i) {          // 거울 반쪽: s = 0 .. L/2
        const size_t idx = (size_t)((double)i / (halfPts - 1) * nsteps);
        emit(L2 - (double)i / (halfPts - 1) * L2, tr[idx], 1);
    }
    for (int i = 1; i < halfPts; ++i) {               // 원본 반쪽: s = L/2 .. L
        const size_t idx = (size_t)((double)i / (halfPts - 1) * nsteps);
        emit(L2 + (double)i / (halfPts - 1) * L2, tr[idx], 0);
    }
    out.close();
    console.success("Wrote: " + csvPath + " (" + std::to_string(2 * halfPts - 1) + " points)");
    return 0;
}
