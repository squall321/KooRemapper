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
    result.isListItem = false;
    result.listIndex = -1;
    
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
    
    // Check for list item (starts with "- ")
    if (content.size() >= 2 && content[0] == '-' && (content[1] == ' ' || content[1] == '[')) {
        result.isListItem = true;
        // The value is everything after "- "
        if (content[1] == ' ') {
            result.value = trim(content.substr(2));
        } else {
            result.value = trim(content.substr(1));  // "- [x,y]" -> "[x,y]"
        }
        return result;
    }
    
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
    
    // Stack of (indent level, parent node pointer, list counter)
    struct StackEntry {
        int indent;
        YamlNode* node;
        int listCounter;
    };
    std::vector<StackEntry> nodeStack;
    nodeStack.push_back({-1, &root, 0});
    
    while (std::getline(stream, line)) {
        // Handle Windows line endings
        if (!line.empty() && line.back() == '\r') {
            line.pop_back();
        }
        
        ParsedLine parsed = parseLine(line);
        
        if (parsed.isEmpty || parsed.isComment) continue;
        
        // Find parent based on indentation
        while (nodeStack.size() > 1 && nodeStack.back().indent >= parsed.indent) {
            nodeStack.pop_back();
        }
        
        YamlNode* parent = nodeStack.back().node;
        
        if (parsed.isListItem) {
            // List item - use numeric key based on counter
            int& listCounter = nodeStack.back().listCounter;
            std::string key = std::to_string(listCounter++);
            
            YamlNode& newNode = parent->children[key];
            newNode.value = parsed.value;
            // List items typically don't have children in our use case
        } else {
            // Regular key-value pair
            YamlNode& newNode = parent->children[parsed.key];
            newNode.value = parsed.value;
            
            // Push to stack if this might have children
            if (parsed.value.empty()) {
                nodeStack.push_back({parsed.indent, &newNode, 0});
            }
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

// ============================================================
// Extended configuration (flat or curved)
// ============================================================

ExtendedMeshConfig YamlConfigReader::readExtendedFile(const std::string& filename) {
    std::ifstream file(filename);
    if (!file.is_open()) {
        throw std::runtime_error("Cannot open file: " + filename);
    }
    
    std::stringstream buffer;
    buffer << file.rdbuf();
    return readExtendedString(buffer.str());
}

ExtendedMeshConfig YamlConfigReader::readExtendedString(const std::string& yamlContent) {
    YamlNode root = parseYaml(yamlContent);
    return nodeToExtendedConfig(root);
}

MeshGenType YamlConfigReader::parseMeshType(const std::string& str) {
    std::string lower = str;
    std::transform(lower.begin(), lower.end(), lower.begin(), ::tolower);
    
    if (lower == "curved" || lower == "curve") {
        return MeshGenType::CURVED;
    }
    return MeshGenType::FLAT;
}

InterpolationType YamlConfigReader::parseInterpolationType(const std::string& str) {
    std::string lower = str;
    std::transform(lower.begin(), lower.end(), lower.begin(), ::tolower);
    
    if (lower == "linear") return InterpolationType::LINEAR;
    if (lower == "bspline" || lower == "b-spline") return InterpolationType::BSPLINE;
    return InterpolationType::CATMULL_ROM;  // Default
}

Vector2D YamlConfigReader::parsePoint(const std::string& str) {
    // Parse "[x, y]" or "x, y" format
    std::string s = trim(str);
    
    // Remove brackets if present
    if (!s.empty() && s.front() == '[') s = s.substr(1);
    if (!s.empty() && s.back() == ']') s.pop_back();
    
    // Find comma
    size_t commaPos = s.find(',');
    if (commaPos == std::string::npos) {
        return Vector2D(0, 0);
    }
    
    std::string xStr = trim(s.substr(0, commaPos));
    std::string yStr = trim(s.substr(commaPos + 1));
    
    double x = 0, y = 0;
    try {
        x = std::stod(xStr);
        y = std::stod(yStr);
    } catch (...) {}
    
    return Vector2D(x, y);
}

std::vector<Vector2D> YamlConfigReader::parseCenterlinePoints(const YamlNode* node) {
    std::vector<Vector2D> points;
    if (!node) return points;
    
    // Points are stored as children with numeric keys (from list parsing)
    // or as a single value with multiple lines
    
    // Check for child nodes (list items become children)
    if (!node->children.empty()) {
        // Collect all numeric-keyed children and sort them
        std::vector<std::pair<int, Vector2D>> indexedPoints;
        
        for (const auto& [key, child] : node->children) {
            try {
                int idx = std::stoi(key);
                Vector2D pt = parsePoint(child.value);
                indexedPoints.push_back({idx, pt});
            } catch (...) {
                // Non-numeric key, try to parse value
                Vector2D pt = parsePoint(child.value);
                if (pt.x != 0 || pt.y != 0) {
                    indexedPoints.push_back({static_cast<int>(indexedPoints.size()), pt});
                }
            }
        }
        
        // Sort by index
        std::sort(indexedPoints.begin(), indexedPoints.end(),
            [](const auto& a, const auto& b) { return a.first < b.first; });
        
        for (const auto& [idx, pt] : indexedPoints) {
            points.push_back(pt);
        }
    }
    
    return points;
}

CurvedMeshConfig YamlConfigReader::parseCurvedConfig(const YamlNode& root) {
    CurvedMeshConfig config;
    
    // Parse centerline points
    if (auto* pts = root.getChild("centerline_points")) {
        config.centerlinePoints = parseCenterlinePoints(pts);
    }
    
    // Parse interpolation type
    if (auto* interp = root.getChild("interpolation")) {
        config.interpolation = parseInterpolationType(interp->asString("catmull_rom"));
    }
    
    // Parse cross section (when no reference)
    if (auto* cs = root.getChild("cross_section")) {
        if (auto* w = cs->getChild("width")) {
            config.width = w->asDouble(1.0);
        }
        if (auto* t = cs->getChild("thickness")) {
            config.thickness = t->asDouble(1.0);
        }
    }
    
    // Parse element counts
    if (auto* e = root.getChild("elements_along_curve")) {
        config.elementsAlongCurve = e->asInt(10);
    }
    if (auto* ej = root.getChild("elements_j")) {
        config.elementsWidth = ej->asInt(5);
    }
    if (auto* ek = root.getChild("elements_k")) {
        config.elementsThickness = ek->asInt(5);
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

ExtendedMeshConfig YamlConfigReader::nodeToExtendedConfig(const YamlNode& root) {
    ExtendedMeshConfig config;
    
    // Parse type (default: flat)
    if (auto* typeNode = root.getChild("type")) {
        config.type = parseMeshType(typeNode->asString("flat"));
    }
    
    // Parse reference (shared by both types)
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
    
    if (config.type == MeshGenType::FLAT) {
        // Parse flat mesh config
        config.flatConfig = nodeToConfig(root);
        config.flatConfig.reference = config.reference;
    } else {
        // Parse curved mesh config
        config.curvedConfig = parseCurvedConfig(root);
    }
    
    return config;
}

} // namespace KooRemapper
