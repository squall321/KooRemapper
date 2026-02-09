#pragma once

#include "squeeze/SqueezeConfig.h"
#include <string>

namespace KooRemapper {

/**
 * Reader for squeeze YAML configuration files
 *
 * Expected format:
 *   parts:
 *     - pid: 1
 *       eps_x: 0.0
 *       eps_y: 0.0
 *       eps_z: -0.02
 *     - pid: 3
 *       eps_x: -0.01
 *       eps_y: -0.01
 *   material:
 *     E: 210000.0
 *     nu: 0.3
 */
class SqueezeConfigReader {
public:
    SqueezeConfigReader() = default;

    /**
     * Read squeeze configuration from YAML file
     * @param filename Path to YAML file
     * @return Parsed configuration
     * @throws std::runtime_error on parse errors
     */
    SqueezeConfig readFile(const std::string& filename);

    /**
     * Read squeeze configuration from string
     * @param yamlContent YAML content as string
     * @return Parsed configuration
     */
    SqueezeConfig readString(const std::string& yamlContent);

    const std::string& getErrorMessage() const { return errorMessage_; }

private:
    std::string errorMessage_;

    std::string trim(const std::string& str);
};

} // namespace KooRemapper
