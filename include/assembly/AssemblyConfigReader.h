#pragma once

#include "assembly/AssemblyConfig.h"
#include <string>

// Knowledge graph (lat.md):
//   @lat: [[modules/assembly]]

namespace KooRemapper {

class AssemblyConfigReader {
public:
    AssemblyConfigReader() = default;

    AssemblyConfig readFile(const std::string& filename);
    AssemblyConfig readString(const std::string& yamlContent);

    const std::string& getErrorMessage() const { return errorMessage_; }

    // 오퍼레이션 값 검증(위반 시 std::runtime_error) — 단독 명령도 assemble 과 같은 규칙으로 검사한다
    static void validateOperation(const AssemblyOperation& op, size_t index);

private:
    std::string errorMessage_;
    std::string trim(const std::string& str);
};

} // namespace KooRemapper
