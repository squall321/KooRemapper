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

private:
    std::string errorMessage_;
    std::string trim(const std::string& str);
};

} // namespace KooRemapper
