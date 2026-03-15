#include "squeeze/SqueezeConfigReader.h"
#include <fstream>
#include <sstream>
#include <stdexcept>
#include <algorithm>

namespace KooRemapper {

std::string SqueezeConfigReader::trim(const std::string& str) {
    size_t start = 0;
    size_t end = str.length();
    while (start < end && std::isspace(str[start])) start++;
    while (end > start && std::isspace(str[end - 1])) end--;
    return str.substr(start, end - start);
}

SqueezeConfig SqueezeConfigReader::readFile(const std::string& filename) {
    std::ifstream file(filename);
    if (!file.is_open()) {
        throw std::runtime_error("Cannot open squeeze config: " + filename);
    }
    std::stringstream buffer;
    buffer << file.rdbuf();
    return readString(buffer.str());
}

SqueezeConfig SqueezeConfigReader::readString(const std::string& yamlContent) {
    SqueezeConfig config;

    std::istringstream stream(yamlContent);
    std::string line;

    enum class Section { NONE, PARTS, MATERIAL };
    Section section = Section::NONE;
    bool inPartItem = false;

    while (std::getline(stream, line)) {
        // Handle Windows line endings
        if (!line.empty() && line.back() == '\r') {
            line.pop_back();
        }

        std::string trimmed = trim(line);

        // Skip empty lines and comments
        if (trimmed.empty() || trimmed[0] == '#') continue;

        // Count leading spaces for indentation
        int indent = 0;
        while (indent < static_cast<int>(line.length()) && line[indent] == ' ') {
            indent++;
        }

        // Top-level section detection (indent 0)
        if (indent == 0) {
            if (trimmed == "parts:" || trimmed == "parts") {
                section = Section::PARTS;
                inPartItem = false;
                continue;
            }
            if (trimmed == "material:" || trimmed == "material") {
                section = Section::MATERIAL;
                inPartItem = false;
                continue;
            }
        }

        // Parse based on current section
        if (section == Section::PARTS) {
            // List item start: "- pid: N" or "  - pid: N"
            if (trimmed.size() >= 2 && trimmed[0] == '-' && trimmed[1] == ' ') {
                std::string afterDash = trim(trimmed.substr(2));

                // Parse "pid: N"
                size_t colonPos = afterDash.find(':');
                if (colonPos != std::string::npos) {
                    std::string key = trim(afterDash.substr(0, colonPos));
                    std::string val = trim(afterDash.substr(colonPos + 1));

                    PartSqueezeConfig part;
                    if (key == "pid") {
                        try { part.pid = std::stoi(val); } catch (...) {}
                    }
                    config.parts.push_back(part);
                    inPartItem = true;
                }
                continue;
            }

            // Sub-key of current part item (e.g., "eps_x: -0.02")
            if (inPartItem && !config.parts.empty()) {
                size_t colonPos = trimmed.find(':');
                if (colonPos != std::string::npos) {
                    std::string key = trim(trimmed.substr(0, colonPos));
                    std::string val = trim(trimmed.substr(colonPos + 1));

                    auto& part = config.parts.back();
                    try {
                        if (key == "pid") part.pid = std::stoi(val);
                        else if (key == "eps_x") part.eps_x = std::stod(val);
                        else if (key == "eps_y") part.eps_y = std::stod(val);
                        else if (key == "eps_z") part.eps_z = std::stod(val);
                        else if (key == "swelling") part.swelling = std::stod(val);
                    } catch (...) {}
                }
            }
        }
        else if (section == Section::MATERIAL) {
            size_t colonPos = trimmed.find(':');
            if (colonPos != std::string::npos) {
                std::string key = trim(trimmed.substr(0, colonPos));
                std::string val = trim(trimmed.substr(colonPos + 1));

                try {
                    if (key == "E") config.E = std::stod(val);
                    else if (key == "nu") config.nu = std::stod(val);
                } catch (...) {}
            }
        }
    }

    // Validate
    if (config.parts.empty()) {
        throw std::runtime_error("No parts defined in squeeze config");
    }

    for (const auto& part : config.parts) {
        if (part.pid <= 0) {
            throw std::runtime_error("Invalid part ID in squeeze config");
        }
    }

    return config;
}

} // namespace KooRemapper
