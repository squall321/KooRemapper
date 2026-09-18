// CNRB 체결점을 '두 강체 + 제로길이 discrete beam(ELFORM=6)' 유격 조인트로 쪼개는 op 의 공개 인터페이스
#pragma once
#include "cli/ConsoleOutput.h"
#include <string>
#include <vector>

// Knowledge graph (lat.md):
//   @lat: [[modules/commands]]
//   @lat: [[commands/cnrb2spring]]

// 단독: KooRemapper cnrb2spring config.yaml
int runCnrb2Spring(const std::string& yamlFile, KooRemapper::ConsoleOutput& console);

struct Cnrb2SpringConfig {
    std::vector<int> targetPids;      // 비면 덱의 모든 CNRB
    char   axis        = 0;           // 'x'|'y'|'z' — 0 이면 미지정(오류)
    double gap         = 0.1;         // 반경 유격 ±[mm]
    double kEngage     = 1.0e5;       // 유격 소진 후 전단 강성 [N/mm]
    double kAxial      = 1.0e7;       // 축방향(로컬 r) 강성 [N/mm]
    double kRot        = 1.0e7;       // 회전 3자유도 강성 [N*mm/rad]. 0 이면 회전을 풀어 둔다
    double curveRange  = 1.0;         // 곡선 가로축 반범위 [mm]
    int    nodeIdStart = 90000001;
    int    elemIdStart = 9900001;
    int    cardIdStart = 990001;
    std::string pidRefs = "strict";   // strict|warn
};

// 핵심 변환 — 원문 줄 버퍼를 그 자리에서 고친다.
// 단독 경로와 (뒷날) assemble 경로가 같은 함수를 불러 같은 알고리즘·같은 출력을 내게 하는 자리다.
// 변환한 조인트 수를 돌려주고, 오류면 -1(이때 lines 는 고치지 않는다).
int cnrb2spring_apply(std::vector<std::string>& lines,
                      const Cnrb2SpringConfig& cfg,
                      KooRemapper::ConsoleOutput& console);
