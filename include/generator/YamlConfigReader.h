#pragma once

#include "generator/VariableDensityConfig.h"
#include <string>
#include <map>
#include <vector>

namespace KooRemapper {

/**
 * Simple YAML parser for variable density mesh configuration
 * 
 * Supports basic YAML features:
 * - Key-value pairs
 * - Nested structures (indentation-based)
 * - Comments (#)
 * - String and numeric values
 */
class YamlConfigReader {
public:
    YamlConfigReader() = default;
    ~YamlConfigReader() = default;
    
    /**
     * Read configuration from YAML file
     * @param filename Path to YAML file
     * @return Parsed configuration
     * @throws std::runtime_error on parse errors
     */
    VariableDensityConfig readFile(const std::string& filename);
    
    /**
     * Read configuration from string
     * @param yamlContent YAML content as string
     * @return Parsed configuration
     */
    VariableDensityConfig readString(const std::string& yamlContent);
    
    /**
     * Get last error message
     */
    const std::string& getErrorMessage() const { return errorMessage_; }

private:
    std::string errorMessage_;
    
    // Simple nested map structure for YAML data
    struct YamlNode {
        std::string value;
        std::map<std::string, YamlNode> children;
        
        bool hasValue() const { return !value.empty(); }
        bool hasChildren() const { return !children.empty(); }
        
        const YamlNode* getChild(const std::string& key) const {
            auto it = children.find(key);
            return (it != children.end()) ? &it->second : nullptr;
        }
        
        double asDouble(double defaultVal = 0) const;
        int asInt(int defaultVal = 0) const;
        std::string asString(const std::string& defaultVal = "") const;
    };
    
    // Parse YAML content into node tree
    YamlNode parseYaml(const std::string& content);
    
    // Parse a single line
    struct ParsedLine {
        int indent;
        std::string key;
        std::string value;
        bool isComment;
        bool isEmpty;
    };
    ParsedLine parseLine(const std::string& line);
    
    // Convert node tree to config
    VariableDensityConfig nodeToConfig(const YamlNode& root);
    
    // Parse zone config from node
    ZoneConfig parseZoneConfig(const YamlNode* node);
    
    // Parse growth type
    GrowthType parseGrowthType(const std::string& str);
    
    // Helper: trim whitespace
    std::string trim(const std::string& str);
};

} // namespace KooRemapper
