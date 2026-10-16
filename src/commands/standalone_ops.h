#pragma once
#include <string>

// Knowledge graph (lat.md):
//   @lat: [[modules/commands]]

namespace KooRemapper { class ConsoleOutput; }

int runWrap(const std::string& yamlFile, KooRemapper::ConsoleOutput& console);
int runUpdate(const std::string& yamlFile, KooRemapper::ConsoleOutput& console);
int runRestack(const std::string& yamlFile, KooRemapper::ConsoleOutput& console);
int runBend(const std::string& yamlFile, KooRemapper::ConsoleOutput& console);
int runIndent(const std::string& yamlFile, KooRemapper::ConsoleOutput& console);
int runFormstrain(const std::string& yamlFile, KooRemapper::ConsoleOutput& console);
int runConvert(const std::string& yamlFile, KooRemapper::ConsoleOutput& console);
int runRefine(const std::string& yamlFile, KooRemapper::ConsoleOutput& console);
int runElform(const std::string& yamlFile, KooRemapper::ConsoleOutput& console);
int runDisconnect(const std::string& yamlFile, KooRemapper::ConsoleOutput& console);
int runIga(const std::string& yamlFile, KooRemapper::ConsoleOutput& console);
int runWarpage(const std::string& yamlFile, KooRemapper::ConsoleOutput& console);
int runOffset(const std::string& yamlFile, KooRemapper::ConsoleOutput& console);
// StepForge 조각을 기존 덱에 넣는다(경계 합의 §3-3 — 우리 몫)
int runCadSolidMerge(const std::string& yamlFile, KooRemapper::ConsoleOutput& console);
// 이 덱(인클루드 닫힘)의 번호 바닥 — StepForge 조각을 요청할 때 줄 시작 번호를 내고 대응표를 대조한다(경계 Q5·Q7)
int runIdFloor(const std::string& yamlFile, KooRemapper::ConsoleOutput& console);
// 재메시 뒤 덧붙인 블록의 절점 번호를 (파트 이름, 좌표)로 새 덱 번호에 다시 묶는다(StepForge 경계 11행)
int runRebindAfterRemesh(const std::string& yamlFile, KooRemapper::ConsoleOutput& console);
