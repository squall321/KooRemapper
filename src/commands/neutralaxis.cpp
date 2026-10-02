// 적층 단면의 EI 가중 중립축을 계산해 보고하는 op — shellmap 의 "z=0 이 중립축" 전제를 수치로 확인한다.
#include "neutralaxis.h"

#include "cli/ConsoleOutput.h"
#include "core/Mesh.h"
#include "core/Platform.h"
#include "parser/KFileReader.h"

#include <algorithm>
#include <cmath>
#include <cstdio>
#include <limits>
#include <map>
#include <string>
#include <vector>

using namespace KooRemapper;

namespace {

double axisCoord(const Node& n, int axis) {
    return axis == 0 ? n.position.x : (axis == 1 ? n.position.y : n.position.z);
}

std::string num(const char* f, double v) {
    char buf[64];
    std::snprintf(buf, sizeof(buf), f, v);
    return std::string(buf);
}

}  // namespace

NaResult computeNeutralAxis(const Mesh& mesh, int axis) {
    const char* axisName = axis == 0 ? "x" : (axis == 1 ? "y" : "z");
    NaResult R;

    // 파트별로 절점을 모은다. 요소 종류가 섞여 있을 수 있으니 셸 여부는 요소 단위로 센다.
    struct Acc {
        double lo = std::numeric_limits<double>::max();
        double hi = std::numeric_limits<double>::lowest();
        double sum = 0.0;
        long long n = 0;
        int elems = 0;
        int shellElems = 0;
    };
    std::map<int, Acc> acc;
    for (const auto& [eid, elem] : mesh.elements) {
        (void)eid;
        Acc& a = acc[elem.partId];
        a.elems++;
        if (elem.type == ElementType::QUAD4) a.shellElems++;
        for (int nid : elem.nodeIds) {
            if (nid <= 0) continue;
            auto it = mesh.nodes.find(nid);
            if (it == mesh.nodes.end()) continue;
            const double v = axisCoord(it->second, axis);
            a.lo = std::min(a.lo, v);
            a.hi = std::max(a.hi, v);
            a.sum += v;
            a.n++;
        }
    }

    for (const auto& [pid, a] : acc) {
        if (a.n == 0) {
            R.skipped.push_back("PID " + std::to_string(pid) + ": 절점을 못 찾았다");
            continue;
        }
        NaLayer L;
        L.pid = pid;
        L.elems = a.elems;

        auto pit = mesh.parts.find(pid);
        const bool allShell = (a.shellElems == a.elems);
        if (allShell) {
            L.kind = "shell";
            // 셸은 두께가 메시에 없다 — *SECTION_SHELL 에서 가져온다.
            double t = 0.0;
            if (pit != mesh.parts.end()) {
                auto sit = mesh.shellSections.find(pit->second.sectionId);
                if (sit != mesh.shellSections.end()) t = sit->second.thickness;
            }
            if (t <= 0.0) {
                R.skipped.push_back("PID " + std::to_string(pid) +
                                    ": 셸인데 *SECTION_SHELL 두께가 없다(SECID " +
                                    std::to_string(pit != mesh.parts.end() ? pit->second.sectionId : 0) + ")");
                continue;
            }
            L.t = t;
            L.c = a.sum / (double)a.n;  // 셸은 절점이 곧 중면이다
        } else {
            L.t = a.hi - a.lo;
            L.c = 0.5 * (a.lo + a.hi);  // 솔리드 층의 기하 중심
            if (L.t <= 0.0) {
                R.skipped.push_back("PID " + std::to_string(pid) + ": " + axisName +
                                    " 방향 두께가 0 이다(평면 솔리드?)");
                continue;
            }
        }

        if (pit == mesh.parts.end()) {
            R.skipped.push_back("PID " + std::to_string(pid) + ": *PART 카드가 없다");
            continue;
        }
        auto mit = mesh.materials.find(pit->second.materialId);
        if (mit == mesh.materials.end() || mit->second.E <= 0.0) {
            // `*MAT_VISCOELASTIC` 은 GI=0 이면 리더가 등록하지 않는다 — 조용히 0 으로 쓰지 않고 말한다.
            R.skipped.push_back("PID " + std::to_string(pid) + ": MID " +
                                std::to_string(pit->second.materialId) + " 의 E 를 못 읽었다");
            continue;
        }
        L.E = mit->second.E;
        R.layers.push_back(L);
    }

    if (R.layers.empty()) return R;

    std::sort(R.layers.begin(), R.layers.end(),
              [](const NaLayer& a, const NaLayer& b) { return a.c < b.c; });

    double sumTz = 0.0, sumEtz = 0.0;
    for (const auto& L : R.layers) {
        R.sumT += L.t;
        sumTz += L.t * L.c;
        R.sumEt += L.E * L.t;
        sumEtz += L.E * L.t * L.c;
    }
    R.geometric = sumTz / R.sumT;
    R.neutral = sumEtz / R.sumEt;

    // 중립축에 대한 단위폭 굽힘강성 D = Σ Eᵢ(tᵢ³/12 + tᵢ·dᵢ²)
    R.stackLo = std::numeric_limits<double>::max();
    R.stackHi = std::numeric_limits<double>::lowest();
    for (const auto& L : R.layers) {
        const double d = L.c - R.neutral;
        R.bendingStiffness += L.E * (L.t * L.t * L.t / 12.0 + L.t * d * d);
        R.stackLo = std::min(R.stackLo, L.c - 0.5 * L.t);
        R.stackHi = std::max(R.stackHi, L.c + 0.5 * L.t);
    }
    R.ok = true;
    return R;
}

int runNeutralAxis(const std::string& meshFile, int axis, ConsoleOutput& console) {
    const char* axisName = axis == 0 ? "x" : (axis == 1 ? "y" : "z");

    console.info("Loading mesh: " + meshFile);
    KFileReader reader;
    Mesh mesh;
    try {
        mesh = reader.readFile(meshFile);
    } catch (const std::exception& e) {
        console.error("Failed to load mesh: " + std::string(e.what()));
        return 1;
    }

    const NaResult R = computeNeutralAxis(mesh, axis);

    console.header("Neutral axis (EI-weighted): " + Platform::getFilename(meshFile));
    console.keyValue("Axis", axisName);

    for (const auto& s : R.skipped) console.warning("제외: " + s);

    if (!R.ok) {
        console.error("EI 를 더할 층이 없다 — 두께와 E 를 모두 읽은 파트가 0개다.");
        return 1;
    }

    console.keyValue("Layers used", std::to_string(R.layers.size()));
    console.println("");
    console.println("  PID   Type         Thickness            Center                 E               E*t");
    for (const auto& L : R.layers) {
        char row[160];
        std::snprintf(row, sizeof(row), "%5d   %-5s %17.12g %17.12g %17.12g %17.12g",
                      L.pid, L.kind, L.t, L.c, L.E, L.E * L.t);
        console.println(row);
    }
    console.println("");

    console.keyValue("Total thickness", num("%.12g", R.sumT));
    console.keyValue("Sum E*t", num("%.12g", R.sumEt));
    console.keyValue("Geometric mid-plane", num("%.12g", R.geometric));
    console.keyValue("Neutral axis", num("%.12g", R.neutral));
    console.keyValue("Neutral - geometric", num("%.12g", R.neutral - R.geometric));
    console.keyValue("Offset from " + std::string(axisName) + "=0", num("%.12g", R.neutral));
    console.keyValue("Bending stiffness D", num("%.12g", R.bendingStiffness) + " (per unit width)");
    console.keyValue("Stack extent", num("%.12g", R.stackLo) + " .. " + num("%.12g", R.stackHi));

    // shellmap 은 평면 덱의 축=0 을 중립면으로 보고 그 좌표를 법선 오프셋으로 쓴다(§1-6).
    // 그래서 재야 할 것은 "축=0 이 중립축에서 얼마나 떨어졌나" 다. 적층의 실제 범위로 판정한다 —
    // |z_n| 을 두께의 절반과 바로 비교하면 적층이 원점에 걸쳐 있을 때만 맞는 말이 된다.
    const std::string ax(axisName);
    if (R.stackLo > 0.0 || R.stackHi < 0.0) {
        console.warning(ax + "=0 이 적층 밖에 있다 — shellmap 은 " + ax +
                        "=0 을 중립면으로 본다. 적층을 중립축 기준으로 옮기고 쓰라.");
    } else if (std::fabs(R.neutral) > 0.5 * R.sumT) {
        console.warning(ax + "=0 이 중립축에서 두께의 절반 넘게 떨어져 있다 — shellmap 은 " + ax +
                        "=0 을 중립면으로 본다. 그만큼 법선 오프셋이 어긋난다.");
    } else if (std::fabs(R.neutral) > 1e-9 * std::max(1.0, R.sumT)) {
        console.info("참고: shellmap 은 " + ax + "=0 을 중립면으로 본다 — 위 오프셋만큼 어긋나 있다.");
    }

    return 0;
}
