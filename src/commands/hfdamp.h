#pragma once
#include "cli/ConsoleOutput.h"
#include <string>
#include <vector>

// Knowledge graph (lat.md):
//   @lat: [[modules/commands]]

// ================================================================
// hfdamp - High-Frequency Damping generator
// Inserts *DAMPING_FREQUENCY_RANGE_DEFORM into a K-file.
//
// FLOW  = 1 / (2 * dt_target)
// FHIGH = FLOW * fhigh_ratio
// Targets frequencies corresponding to elements with dt <= dt_target.
// ================================================================

// Standalone command: KooRemapper hfdamp config.yaml
int runHFDamp(const std::string& yamlFile, KooRemapper::ConsoleOutput& console);

struct HFDampConfig {
    double dtTarget     = 0.0;      // REQUIRED: target timestep [model time units]
    double cdamp        = 0.99;     // Fraction of critical damping (0 < cdamp <= 1)
    double fhighRatio   = 100.0;    // FHIGH = FLOW * fhigh_ratio  (10~300 recommended)
    std::string mode    = "global"; // "global" | "selective"
    double tssfac       = 0.9;      // Timestep safety factor for element dt estimate
};

// Core transform: inserts damping keyword(s) into raw K-file lines.
// maxSetId is updated if a new *SET_PART_LIST is created.
// Returns 0 on success, -1 on error (dtTarget not set, etc.)
//
// `analysis` 가 있으면 선택형의 파트·요소·재질을 **그 줄**(인클루드 닫힘을 펼친 것)에서 읽는다 — 감쇠 키워드는
// 여전히 `lines`(주 덱)에 넣는다. 예전에는 주 덱만 봐서, 메시를 인클루드한 마스터 덱에서 「dt 조건을 만족하는
// 파트가 없다」며 **전체 감쇠(PSID=0)로 조용히 바꿨다**(2026-10-16 실측). `analysisComplete` 가 거짓이면(닫힘을
// 다 못 읽음) 파트를 못 찾았을 때 전체로 바꾸지 않고 거절한다.
int hfdamp_apply(std::vector<std::string>& lines,
                 const HFDampConfig& cfg,
                 int& maxSetId,
                 KooRemapper::ConsoleOutput& console,
                 const std::vector<std::string>* analysis = nullptr,
                 bool analysisComplete = true);
