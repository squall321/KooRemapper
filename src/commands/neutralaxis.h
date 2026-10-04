#pragma once
// 적층 단면의 EI 가중 중립축을 계산해 보고하는 op — shellmap 의 "z=0 이 중립축" 전제를 수치로 확인한다.
#include <string>
#include <vector>

namespace KooRemapper { class ConsoleOutput; class Mesh; }

// Knowledge graph (lat.md):
//   @lat: [[modules/commands]]
//   @lat: [[commands/neutralaxis]]

// 한 파트 = 적층의 한 층.
struct NaLayer {
    int pid = 0;
    const char* kind = "solid";
    double t = 0.0;    // 축 방향 두께
    double c = 0.0;    // 축 방향 중심
    double E = 0.0;
    int elems = 0;
};

struct NaResult {
    bool ok = false;                       // 쓸 층이 하나라도 있었나
    std::vector<NaLayer> layers;           // 축 방향 중심 순으로 정렬 (E 를 읽은 것만)
    // 두께는 읽었지만 **E 를 못 읽은** 층(E = 0). 중립축 계산에는 쓰지 않는다 — 0 으로 쓰면
    // 가중이 거짓이 된다. 다만 **층 모식도는 E 가 필요 없으므로** 그쪽이 쓸 수 있게 남긴다.
    // 실측 — 실제 전지 과제는 `*MAT` 가 포함 파일에 있어 메시 덱만 보면 E 가 전부 비어 있다.
    std::vector<NaLayer> geomOnly;
    std::vector<std::string> skipped;      // 제외한 파트와 그 이유
    double neutral = 0.0;                  // z_n = ΣEtz / ΣEt
    double geometric = 0.0;                // Σtz / Σt
    double sumT = 0.0, sumEt = 0.0;
    double stackLo = 0.0, stackHi = 0.0;   // 적층이 차지한 축 범위
    double bendingStiffness = 0.0;         // D = ΣE(t³/12 + t·d²)
};

// axis: 0=x, 1=y, 2=z. 두께나 E 를 못 읽은 파트는 **제외하고 skipped 에 이유를 남긴다.**
NaResult computeNeutralAxis(const KooRemapper::Mesh& mesh, int axis);

int runNeutralAxis(const std::string& meshFile, int axis, KooRemapper::ConsoleOutput& console);
