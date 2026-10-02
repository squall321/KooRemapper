// 접힌 덱에서 군별 강체변환(힌지 축·각·피벗)을 역산하는 op — 피벗 산포를 반드시 함께 보고한다.
#include "linkage_fit.h"

#include "cli/ConsoleOutput.h"
#include "core/Matrix3x3.h"
#include "core/Mesh.h"
#include "parser/KFileReader.h"
#include "util/YamlComment.h"

#include <algorithm>
#include <cmath>
#include <cstdio>
#include <fstream>
#include <map>
#include <set>
#include <string>
#include <vector>

using KooRemapper::ConsoleOutput;
using KooRemapper::KFileReader;
using KooRemapper::Matrix3x3;
using KooRemapper::Mesh;
using KooRemapper::Vector3D;
using KooRemapper::yamlStripComment;

namespace {

struct Config {
    std::string reference, folded, output;
    double angleTol = 0.5;   // deg
    double pivotTol = 0.5;   // 길이 단위
};

// 한 파트의 강체변환 적합 결과
struct Fit {
    int pid = 0;
    long long nodes = 0;
    double angleDeg = 0.0;
    Vector3D axis{0, 0, 1};
    Vector3D pivot{0, 0, 0};
    double slide = 0.0;       // 축 방향 이동(나사 운동이면 0 이 아니다)
    Vector3D translation{0, 0, 0};
    double rmsResidual = 0.0;
    double maxResidual = 0.0;
    bool pureTranslation = false;
    bool rigid = true;
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

// 대칭 4x4 의 최대 고유벡터 — 순환 Jacobi. 외부 선형대수 없이 자체완결하게 둔다.
void jacobi4(double a[4][4], double v[4][4]) {
    for (int i = 0; i < 4; ++i)
        for (int j = 0; j < 4; ++j) v[i][j] = (i == j) ? 1.0 : 0.0;
    for (int sweep = 0; sweep < 64; ++sweep) {
        double off = 0.0;
        for (int i = 0; i < 4; ++i)
            for (int j = i + 1; j < 4; ++j) off += a[i][j] * a[i][j];
        if (off < 1e-30) return;
        for (int p = 0; p < 3; ++p) {
            for (int q = p + 1; q < 4; ++q) {
                if (std::fabs(a[p][q]) < 1e-300) continue;
                const double theta = 0.5 * (a[q][q] - a[p][p]) / a[p][q];
                const double t = (theta >= 0 ? 1.0 : -1.0) /
                                 (std::fabs(theta) + std::sqrt(theta * theta + 1.0));
                const double c = 1.0 / std::sqrt(t * t + 1.0);
                const double s = t * c;
                for (int k = 0; k < 4; ++k) {
                    const double akp = a[k][p], akq = a[k][q];
                    a[k][p] = c * akp - s * akq;
                    a[k][q] = s * akp + c * akq;
                }
                for (int k = 0; k < 4; ++k) {
                    const double apk = a[p][k], aqk = a[q][k];
                    a[p][k] = c * apk - s * aqk;
                    a[q][k] = s * apk + c * aqk;
                }
                for (int k = 0; k < 4; ++k) {
                    const double vkp = v[k][p], vkq = v[k][q];
                    v[k][p] = c * vkp - s * vkq;
                    v[k][q] = s * vkp + c * vkq;
                }
            }
        }
    }
}

// Horn 의 사원수법으로 ref -> def 의 최적 회전을 구한다(최소제곱).
Matrix3x3 optimalRotation(const Matrix3x3& H) {
    const double sxx = H.m[0][0], sxy = H.m[0][1], sxz = H.m[0][2];
    const double syx = H.m[1][0], syy = H.m[1][1], syz = H.m[1][2];
    const double szx = H.m[2][0], szy = H.m[2][1], szz = H.m[2][2];
    double N[4][4] = {
        {sxx + syy + szz, syz - szy,        szx - sxz,        sxy - syx},
        {syz - szy,       sxx - syy - szz,  sxy + syx,        szx + sxz},
        {szx - sxz,       sxy + syx,       -sxx + syy - szz,  syz + szy},
        {sxy - syx,       szx + sxz,        syz + szy,       -sxx - syy + szz}};
    double V[4][4];
    jacobi4(N, V);
    int best = 0;
    for (int i = 1; i < 4; ++i)
        if (N[i][i] > N[best][best]) best = i;
    double w = V[0][best], x = V[1][best], y = V[2][best], z = V[3][best];
    const double n = std::sqrt(w * w + x * x + y * y + z * z);
    if (n < 1e-300) return Matrix3x3::identity();
    w /= n; x /= n; y /= n; z /= n;
    return Matrix3x3(
        1 - 2 * (y * y + z * z), 2 * (x * y - w * z),     2 * (x * z + w * y),
        2 * (x * y + w * z),     1 - 2 * (x * x + z * z), 2 * (y * z - w * x),
        2 * (x * z - w * y),     2 * (y * z + w * x),     1 - 2 * (x * x + y * y));
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
            if      (key == "reference") c.reference = val;
            else if (key == "folded")    c.folded = val;
            else if (key == "output")    c.output = val;
            else if (key == "angle_tol") c.angleTol = std::stod(val);
            else if (key == "pivot_tol") c.pivotTol = std::stod(val);
            else console.warning("모르는 키는 무시한다: " + key);
        } catch (const std::exception&) {
            console.error("숫자를 읽을 수 없다: " + key + ": " + val);
            return false;
        }
    }
    return true;
}

}  // namespace

int runLinkageFit(const std::string& yamlFile, ConsoleOutput& console) {
    Config c;
    if (!parseYaml(yamlFile, c, console)) return 1;
    if (c.reference.empty()) { console.error("reference: 가 필요하다"); return 1; }
    if (c.folded.empty())    { console.error("folded: 가 필요하다"); return 1; }
    if (c.output.empty())    { console.error("output: 이 필요하다"); return 1; }
    if (c.angleTol < 0 || c.pivotTol < 0) { console.error("허용값은 음수가 될 수 없다"); return 1; }

    KFileReader r1, r2;
    Mesh ref, def;
    try {
        ref = r1.readFile(c.reference);
        def = r2.readFile(c.folded);
    } catch (const std::exception& e) {
        console.error("Failed to load: " + std::string(e.what()));
        return 1;
    }

    console.header("Linkage fit (per-part rigid transforms)");
    console.keyValue("Reference", c.reference);
    console.keyValue("Folded", c.folded);

    // 파트별 절점 — 요소에서 모은다(절점 자체에는 파트가 없다)
    std::map<int, std::set<int>> partNodes;
    for (const auto& [eid, e] : ref.elements) {
        (void)eid;
        for (int nid : e.nodeIds)
            if (nid > 0) partNodes[e.partId].insert(nid);
    }
    if (partNodes.empty()) { console.error("파트를 못 찾았다 — 요소가 없다."); return 1; }

    // 두 덱의 절점 집합이 같아야 한다 — 다르면 어느 절점이 짝이 없는지 말한다
    long long missing = 0;
    for (const auto& [nid, n] : ref.nodes) {
        (void)n;
        if (def.nodes.find(nid) == def.nodes.end()) missing++;
    }
    if (missing > 0) {
        console.error("접힌 덱에 없는 절점이 " + std::to_string(missing) +
                      "개다 — 두 덱의 위상이 같아야 한다.");
        return 1;
    }

    std::vector<Fit> fits;
    for (const auto& [pid, nids] : partNodes) {
        Fit F;
        F.pid = pid;
        std::vector<Vector3D> P, Q;
        P.reserve(nids.size());
        Q.reserve(nids.size());
        for (int nid : nids) {
            auto a = ref.nodes.find(nid);
            auto b = def.nodes.find(nid);
            if (a == ref.nodes.end() || b == def.nodes.end()) continue;
            P.push_back(a->second.position);
            Q.push_back(b->second.position);
        }
        F.nodes = (long long)P.size();
        if (F.nodes < 3) {
            console.warning("PID " + std::to_string(pid) + ": 절점이 " +
                            std::to_string(F.nodes) + "개뿐이라 강체변환을 정할 수 없다 — 건너뛴다.");
            continue;
        }

        Vector3D pc(0, 0, 0), qc(0, 0, 0);
        for (size_t i = 0; i < P.size(); ++i) { pc = pc + P[i]; qc = qc + Q[i]; }
        pc = pc * (1.0 / (double)P.size());
        qc = qc * (1.0 / (double)P.size());

        Matrix3x3 H = Matrix3x3::zero();
        for (size_t i = 0; i < P.size(); ++i)
            H = H + Matrix3x3::outerProduct(P[i] - pc, Q[i] - qc);
        const Matrix3x3 R = optimalRotation(H);
        const Vector3D t = qc - R * pc;
        F.translation = t;

        // 잔차 — 이 값이 크면 그 군은 강체가 아니다(그렇게 말해야 한다)
        double sum2 = 0.0;
        for (size_t i = 0; i < P.size(); ++i) {
            const Vector3D d = (R * P[i] + t) - Q[i];
            const double m = d.magnitude();
            sum2 += m * m;
            F.maxResidual = std::max(F.maxResidual, m);
        }
        F.rmsResidual = std::sqrt(sum2 / (double)P.size());

        // 축·각 — 회전행렬에서 뽑는다
        const double cosT = std::min(1.0, std::max(-1.0, 0.5 * (R.trace() - 1.0)));
        const double ang = std::acos(cosT);
        F.angleDeg = ang * 180.0 / M_PI;
        if (ang < 1e-12) {
            F.pureTranslation = true;
            F.axis = Vector3D(0, 0, 1);
            F.pivot = pc;
            F.slide = t.magnitude();
        } else {
            Vector3D n(R.m[2][1] - R.m[1][2], R.m[0][2] - R.m[2][0], R.m[1][0] - R.m[0][1]);
            const double nm = n.magnitude();
            if (nm > 1e-12) {
                F.axis = n * (1.0 / nm);
            } else {
                // 180도 — (R+I) 의 열에서 축을 뽑는다
                Matrix3x3 M = R + Matrix3x3::identity();
                Vector3D best = M.col(0);
                for (int j = 1; j < 3; ++j)
                    if (M.col(j).magnitude() > best.magnitude()) best = M.col(j);
                const double bm = best.magnitude();
                F.axis = (bm > 1e-12) ? best * (1.0 / bm) : Vector3D(0, 0, 1);
            }
            // 피벗 — (I-R)p = t 는 축 방향으로 특이하다. n nᵀ 를 더해 정칙화하고 축 좌표는
            // 파트 중심에 맞춘다(축 위 어느 점이든 같은 변환이라 '가장 가까운 점' 을 고른다).
            F.slide = t.dot(F.axis);
            const Vector3D tPerp = t - F.axis * F.slide;
            const Matrix3x3 M = (Matrix3x3::identity() - R) + Matrix3x3::outerProduct(F.axis, F.axis);
            const Vector3D rhs = tPerp + F.axis * pc.dot(F.axis);
            if (std::fabs(M.determinant()) < 1e-14) {
                console.warning("PID " + std::to_string(pid) + ": 피벗을 정할 수 없다(퇴화).");
                F.pivot = pc;
            } else {
                F.pivot = M.inverse() * rhs;
            }
        }
        fits.push_back(F);
    }

    if (fits.empty()) { console.error("적합할 파트가 없다."); return 1; }

    // 파트 표
    console.keyValue("Parts fitted", std::to_string(fits.size()));
    console.println("");
    console.println("  PID     angle[deg]            axis                        pivot                  slide     RMS resid");
    for (const Fit& F : fits) {
        char row[256];
        std::snprintf(row, sizeof(row),
                      "%5d %12.6f  (%7.4f %7.4f %7.4f)  (%9.4f %9.4f %9.4f) %10.4g %12.4g",
                      F.pid, F.angleDeg, F.axis.x, F.axis.y, F.axis.z,
                      F.pivot.x, F.pivot.y, F.pivot.z, F.slide, F.rmsResidual);
        console.println(row);
    }
    console.println("");

    // 강체가 아닌 파트 — 모델 치수에 견주어 판단한다
    auto [bmin, bmax] = ref.getBoundingBox();
    const double modelSize = (bmax - bmin).magnitude();
    for (Fit& F : fits) {
        if (F.rmsResidual > 1e-6 * std::max(1.0, modelSize)) {
            F.rigid = false;
            console.warning("PID " + std::to_string(F.pid) + ": 강체가 아니다 — RMS 잔차 " +
                            num("%.6g", F.rmsResidual) + " (최대 " + num("%.6g", F.maxResidual) +
                            "). 변형이 섞인 파트는 힌지로 환원되지 않는다.");
        }
    }

    // 군으로 묶는다 — 각·축·피벗·축이동이 **모두** 맞아야 한다
    std::vector<std::vector<size_t>> groups;
    std::vector<bool> used(fits.size(), false);
    for (size_t i = 0; i < fits.size(); ++i) {
        if (used[i]) continue;
        std::vector<size_t> g{i};
        used[i] = true;
        for (size_t j = i + 1; j < fits.size(); ++j) {
            if (used[j]) continue;
            const Fit& A = fits[i];
            const Fit& B = fits[j];
            if (std::fabs(A.angleDeg - B.angleDeg) > c.angleTol) continue;
            if (!A.pureTranslation && !B.pureTranslation) {
                const double dot = std::min(1.0, std::max(-1.0, A.axis.dot(B.axis)));
                if (std::acos(std::fabs(dot)) * 180.0 / M_PI > c.angleTol) continue;
                if ((A.pivot - B.pivot).magnitude() > c.pivotTol) continue;
                if (std::fabs(A.slide - B.slide) > c.pivotTol) continue;
            }
            g.push_back(j);
            used[j] = true;
        }
        groups.push_back(g);
    }

    console.keyValue("Groups", std::to_string(groups.size()));

    // ★ 피벗 산포 — 각도만으로 묶으면 조용히 틀린다(보고 실측 5.41mm). 숫자로 보여 준다.
    console.println("");
    console.println("  group   parts                 angle[deg]      피벗 산포      축 산포[deg]");
    for (size_t gi = 0; gi < groups.size(); ++gi) {
        double pivScatter = 0.0, axisScatter = 0.0;
        for (size_t a = 0; a < groups[gi].size(); ++a) {
            for (size_t b = a + 1; b < groups[gi].size(); ++b) {
                const Fit& A = fits[groups[gi][a]];
                const Fit& B = fits[groups[gi][b]];
                pivScatter = std::max(pivScatter, (A.pivot - B.pivot).magnitude());
                const double dot = std::min(1.0, std::max(-1.0, std::fabs(A.axis.dot(B.axis))));
                axisScatter = std::max(axisScatter, std::acos(dot) * 180.0 / M_PI);
            }
        }
        std::string parts;
        for (size_t k : groups[gi]) parts += (parts.empty() ? "" : ",") + std::to_string(fits[k].pid);
        if (parts.size() > 20) parts = parts.substr(0, 17) + "...";
        char row[256];
        std::snprintf(row, sizeof(row), "%7zu   %-20s %12.6f %14.6g %16.6g",
                      gi + 1, parts.c_str(), fits[groups[gi][0]].angleDeg, pivScatter, axisScatter);
        console.println(row);
    }
    console.println("");

    // 각도만으로 묶으면 어떻게 되는지 — 그 위험을 숫자로 적는다
    {
        std::vector<bool> seen(fits.size(), false);
        for (size_t i = 0; i < fits.size(); ++i) {
            if (seen[i]) continue;
            std::vector<size_t> byAngle{i};
            seen[i] = true;
            for (size_t j = i + 1; j < fits.size(); ++j) {
                if (seen[j]) continue;
                if (std::fabs(fits[i].angleDeg - fits[j].angleDeg) <= c.angleTol) {
                    byAngle.push_back(j);
                    seen[j] = true;
                }
            }
            if (byAngle.size() < 2) continue;
            double sc = 0.0;
            for (size_t a = 0; a < byAngle.size(); ++a)
                for (size_t b = a + 1; b < byAngle.size(); ++b)
                    sc = std::max(sc, (fits[byAngle[a]].pivot - fits[byAngle[b]].pivot).magnitude());
            if (sc > c.pivotTol) {
                console.warning("각 " + num("%.4f", fits[i].angleDeg) + "도 파트 " +
                                std::to_string(byAngle.size()) +
                                "개를 **각도만으로** 묶으면 피벗이 " + num("%.6g", sc) +
                                " 만큼 흩어진다 — 서로 다른 힌지다. 각도만으로 묶지 말라.");
            }
        }
    }

    // 산출 — applyfold 가 읽을 수 있는 형태로 쓴다
    const std::string outPath = c.output + ".yaml";
    std::ofstream out(outPath);
    if (!out.is_open()) { console.error("Cannot write: " + outPath); return 1; }
    out << "# KooRemapper linkage-fit 산출 — applyfold 가 읽는다\n";
    out << "# reference: " << c.reference << "\n# folded: " << c.folded << "\n";
    out << "groups:\n";
    char buf[512];
    for (const auto& g : groups) {
        const Fit& A = fits[g[0]];
        std::string parts;
        for (size_t k : g) parts += (parts.empty() ? "" : ", ") + std::to_string(fits[k].pid);
        out << "  - parts: [" << parts << "]\n";
        std::snprintf(buf, sizeof(buf), "    angle: %.12g\n", A.angleDeg);           out << buf;
        std::snprintf(buf, sizeof(buf), "    axis: [%.12g, %.12g, %.12g]\n",
                      A.axis.x, A.axis.y, A.axis.z);                                 out << buf;
        std::snprintf(buf, sizeof(buf), "    pivot: [%.12g, %.12g, %.12g]\n",
                      A.pivot.x, A.pivot.y, A.pivot.z);                              out << buf;
        std::snprintf(buf, sizeof(buf), "    slide: %.12g\n", A.slide);              out << buf;
        if (A.pureTranslation) {
            std::snprintf(buf, sizeof(buf), "    translation: [%.12g, %.12g, %.12g]\n",
                          A.translation.x, A.translation.y, A.translation.z);        out << buf;
        }
        std::snprintf(buf, sizeof(buf), "    rms_residual: %.6g\n", A.rmsResidual);  out << buf;
    }
    out.close();
    console.success("Wrote: " + outPath);
    return 0;
}
