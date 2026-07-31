// K파일 구조화 메타 추출 op — 파트별 기하 메트릭·재료·접촉 connectivity를 JSON으로 출력
#pragma once
#include <string>

// Knowledge graph (lat.md):
//   @lat: [[modules/commands]]

namespace KooRemapper { class ConsoleOutput; }

int runModelmeta(const std::string& yamlFile, KooRemapper::ConsoleOutput& console);
