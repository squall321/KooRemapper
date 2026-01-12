#include "generator/YamlConfigReader.h"
#include <fstream>
#include <sstream>
#include <algorithm>
#include <stdexcept>
#include <stack>

namespace KooRemapper {

double YamlConfigReader::YamlNode::asDouble(double defaultVal) const {
    if (value.empty()) return defaultVal;
    try {
        return std::stod(value);
    } catch (...) {
        return defaultVal;
    }
}

int YamlConfigReader::YamlNode::asInt(int defaultVal) const {
    if (value.empty()) return defaultVal;
    try {
        return std::stoi(value);
    } catch (...) {
        return defaultVal;
    }
}

std::string YamlConfigReader::YamlNode::asString(const std::string& defaultVal) const {
    return value.empty() ? defaultVal : value;
}

VariableDensityConfig YamlConfigReader::readFile(const std::string& filename) {
    std::ifstream file(filename);
    if (!file.is_open()) {
        throw std::runtime_error("Cannot open file: " + filename);
    }
    
    std::stringstream buffer;
    buffer << file.rdbuf();
    return readString(buffer.str());
}

VariableDensityConfig YamlConfigReader::readString(const std::string& yamlContent) {
    YamlNode root = parseYaml(yamlContent);
    return nodeToConfig(root);
}

std::string YamlConfigReader::trim(const std::string& str) {
    size_t start = 0;
    size_t end = str.length();
    
    while (start < end && std::isspace(str[start])) start++;
    while (end > start && std::isspace(str[end - 1])) end--;
    
    return str.substr(start, end - start);
}

YamlConfigReader::ParsedLine YamlConfigReader::parseLine(const std::string& line) {
    ParsedLine result;
    result.indent = 0;
    result.isComment = false;
    result.isEmpty = true;
    
    if (line.empty()) return result;
    
    // Count leading spaces
    while (result.indent < static_cast<int>(line.length()) && line[result.indent] == ' ') {
        result.indent++;
    }
    
    // Check if empty or comment
    std::string content = trim(line);
    if (content.empty()) return result;
    if (content[0] == '#') {
        result.isComment = true;
        return result;
    }
    
    result.isEmpty = false;
    
    // Find colon separator
    size_t colonPos = content.find(':');
    if (colonPos == std::string::npos) {
        result.key = content;
        return result;
    }
    
    result.key = trim(content.substr(0, colonPos));
    if (colonPos + 1 < content.length()) {
        result.value = trim(content.substr(colonPos + 1));
        // Remove quotes if present
        if (result.value.length() >= 2) {
            if ((result.value.front() == '"' && result.value.back() == '"') ||
                (result.value.front() == '\'' && result.value.back() == '\'')) {
                result.value = result.value.substr(1, result.value.length() - 2);
            }
        }
    }
    
    return result;
}

YamlConfigReader::YamlNode YamlConfigReader::parseYaml(const std::string& content) {
    YamlNode root;
    
    std::istringstream stream(content);
    std::string line;
    
    // Stack of (indent level, parent node pointer)
    std::vector<std::pair<int, YamlNode*>> nodeStack;
    nodeStack.push_back({-1, &root});
    
    while (std::getline(stream, line)) {
        // Handle Windows line endings
        if (!line.empty() && line.back() == '\r') {
            line.pop_back();
        }
        
        ParsedLine parsed = parseLine(line);
        
        if (parsed.isEmpty || parsed.isComment) continue;
        
        // Find parent based on indentation
        while (nodeStack.size() > 1 && nodeStack.back().first >= parsed.indent) {
            nodeStack.pop_back();
        }
        
        YamlNode* parent = nodeStack.back().second;
        
        // Add new node
        YamlNode& newNode = parent->children[parsed.key];
        newNode.value = parsed.value;
        
        // Push to stack if this might have children
        if (parsed.value.empty()) {
            nodeStack.push_back({parsed.indent, &newNode});
        }
    }
    
    return root;
}

GrowthType YamlConfigReader::parseGrowthType(const std::string& str) {
    std::string lower = str;
    std::transform(lower.begin(), lower.end(), lower.begin(), ::tolower);
    
    if (lower == "geometric") return GrowthType::GEOMETRIC;
    if (lower == "exponential") return GrowthType::EXPONENTIAL;
    return GrowthType::LINEAR;
}

ZoneConfig YamlConfigReader::parseZoneConfig(const YamlNode* node) {
    ZoneConfig config;
    if (!node) return config;
    
    if (auto* length = node->getChild("length")) {
        config.length = length->asDouble(0);
    }
    if (auto* num = node->getChild("num_elements")) {
        config.numElements = num->asInt(0);
    }
    if (auto* growth = node->getChild("growth_type")) {
        config.growthType = parseGrowthType(growth->asString("linear"));
    }
    
    return config;
}

VariableDensityConfig YamlConfigReader::nodeToConfig(const YamlNode& root) {
    VariableDensityConfig config;
    
    // Parse reference
    if (auto* ref = root.getChild("reference")) {
        if (auto* flatMesh = ref->getChild("flat_mesh")) {
            config.reference.flatMeshFile = flatMesh->asString();
        }
        if (auto* dims = ref->getChild("dimensions")) {
            if (auto* li = dims->getChild("length_i")) {
                config.reference.lengthI = li->asDouble();
            }
            if (auto* lj = dims->getChild("length_j")) {
                config.reference.lengthJ = lj->asDouble();
            }
            if (auto* lk = dims->getChild("length_k")) {
                config.reference.lengthK = lk->asDouble();
            }
        }
    }
    
    // Parse elements J, K
    if (auto* ej = root.getChild("elements_j")) {
        config.elementsJ = ej->asInt(10);
    }
    if (auto* ek = root.getChild("elements_k")) {
        config.elementsK = ek->asInt(5);
    }
    
    // Parse variable density zones
    if (auto* vd = root.getChild("variable_density")) {
        config.zone1_denseStart = parseZoneConfig(vd->getChild("zone1_dense_start"));
        config.zone2_increasing = parseZoneConfig(vd->getChild("zone2_increasing"));
        config.zone3_sparse = parseZoneConfig(vd->getChild("zone3_sparse"));
        config.zone4_decreasing = parseZoneConfig(vd->getChild("zone4_decreasing"));
        config.zone5_denseEnd = parseZoneConfig(vd->getChild("zone5_dense_end"));
    }
    
    // Parse options
    if (auto* opts = root.getChild("options")) {
        if (auto* center = opts->getChild("center_at_origin")) {
            std::string val = center->asString("false");
            std::transform(val.begin(), val.end(), val.begin(), ::tolower);
            config.centerAtOrigin = (val == "true" || val == "yes" || val == "1");
        }
    }
    
    return config;
}

} // namespace KooRemapper
