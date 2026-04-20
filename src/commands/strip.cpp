#include "strip.h"
#include "cli/ConsoleOutput.h"

#include <string>
#include <vector>
#include <set>
#include <fstream>
#include <sstream>
#include <algorithm>

using KooRemapper::ConsoleOutput;

// ─────────────────────────────────────────────────────────────
// Minimal YAML helpers
// ─────────────────────────────────────────────────────────────

static std::string st_trim(const std::string& s) {
    size_t a = s.find_first_not_of(" \t\r\n");
    if (a == std::string::npos) return "";
    size_t b = s.find_last_not_of(" \t\r\n");
    return s.substr(a, b - a + 1);
}

static std::string st_stripQuotes(const std::string& s) {
    if (s.size() >= 2 &&
        ((s.front() == '"' && s.back() == '"') ||
         (s.front() == '\'' && s.back() == '\'')))
        return s.substr(1, s.size() - 2);
    return s;
}

static std::string st_toUpper(const std::string& s) {
    std::string r = s;
    for (auto& c : r) c = (char)toupper((unsigned char)c);
    return r;
}

// ─────────────────────────────────────────────────────────────
// runStrip
// ─────────────────────────────────────────────────────────────

int runStrip(const std::string& yamlFile, ConsoleOutput& console)
{
    // --- Parse YAML config ---
    std::ifstream yf(yamlFile);
    if (!yf.is_open()) {
        console.error("Cannot open config: " + yamlFile);
        return 1;
    }

    std::string modelPath, outputPath;
    std::vector<std::string> stripKeywords;
    bool inKeywordsList = false;

    std::string yline;
    while (std::getline(yf, yline)) {
        std::string trimmed = st_trim(yline);
        if (trimmed.empty() || trimmed[0] == '#') continue;

        // Count indent for list detection
        int indent = 0;
        while (indent < (int)yline.size() && yline[indent] == ' ') ++indent;

        // List item under keywords:
        if (inKeywordsList && trimmed.size() > 2 && trimmed[0] == '-') {
            if (indent <= 0) { inKeywordsList = false; }
            else {
                std::string val = st_trim(trimmed.substr(1));
                val = st_stripQuotes(val);
                if (!val.empty()) stripKeywords.push_back(val);
                continue;
            }
        }

        // Top-level key: value
        size_t colon = trimmed.find(':');
        if (colon == std::string::npos) continue;

        std::string key = st_trim(trimmed.substr(0, colon));
        std::string val = st_trim(trimmed.substr(colon + 1));
        val = st_stripQuotes(val);

        if (key == "model" || key == "input") {
            modelPath = val;
        } else if (key == "output") {
            outputPath = val;
        } else if (key == "keywords") {
            inKeywordsList = true;
            // Inline list: keywords: ["*NODE", "*ELEMENT_SOLID"]
            if (!val.empty() && val[0] == '[') {
                // Parse inline array
                std::string inner = val.substr(1);
                size_t rb = inner.rfind(']');
                if (rb != std::string::npos) inner = inner.substr(0, rb);
                std::istringstream ss(inner);
                std::string tok;
                while (std::getline(ss, tok, ',')) {
                    tok = st_trim(tok);
                    tok = st_stripQuotes(tok);
                    if (!tok.empty()) stripKeywords.push_back(tok);
                }
                inKeywordsList = false;
            }
        } else {
            inKeywordsList = false;
        }
    }
    yf.close();

    // Resolve paths relative to config dir
    std::string configDir;
    {
        size_t sep = yamlFile.find_last_of("/\\");
        if (sep != std::string::npos)
            configDir = yamlFile.substr(0, sep + 1);
    }
    auto resolvePath = [&](const std::string& p) -> std::string {
        if (p.empty()) return p;
        if (p.size() >= 2 && (p[1] == ':' || p[0] == '/' || p[0] == '\\')) return p;
        if (p.find('/') == std::string::npos && p.find('\\') == std::string::npos)
            return configDir + p;
        return configDir + p;
    };
    modelPath = resolvePath(modelPath);
    outputPath = resolvePath(outputPath);

    // Validate
    if (modelPath.empty()) {
        console.error("'model' (or 'input') is required in YAML config");
        return 1;
    }
    if (outputPath.empty()) {
        // Default: input_stripped.k
        size_t dot = modelPath.rfind('.');
        if (dot != std::string::npos)
            outputPath = modelPath.substr(0, dot) + "_stripped" + modelPath.substr(dot);
        else
            outputPath = modelPath + "_stripped";
    }
    if (stripKeywords.empty()) {
        console.error("'keywords' list is required (nothing to strip)");
        return 1;
    }

    // Build uppercase match set for keywords
    // Each entry is matched as a PREFIX of the line's keyword.
    // e.g. "*NODE" matches "*NODE", "*NODE_TITLE", etc.
    // e.g. "*ELEMENT" matches "*ELEMENT_SOLID", "*ELEMENT_SHELL", etc.
    std::set<std::string> stripSet;
    for (auto& kw : stripKeywords) {
        std::string up = st_toUpper(kw);
        // Ensure leading *
        if (!up.empty() && up[0] != '*') up = "*" + up;
        stripSet.insert(up);
    }

    console.info("Strip keywords from: " + modelPath);
    for (auto& kw : stripKeywords)
        console.info("  strip: " + kw);

    // --- Read input file ---
    std::ifstream inf(modelPath);
    if (!inf.is_open()) {
        console.error("Cannot open input: " + modelPath);
        return 1;
    }

    std::ofstream outf(outputPath);
    if (!outf.is_open()) {
        console.error("Cannot open output: " + outputPath);
        return 1;
    }

    // Line-by-line processing
    bool skipping = false;
    long long totalLines = 0;
    long long skippedLines = 0;
    std::string line;

    while (std::getline(inf, line)) {
        ++totalLines;

        // Check if this line starts a new keyword block
        if (!line.empty() && line[0] == '*') {
            std::string upper = st_toUpper(st_trim(line));

            // Check if any strip keyword is a prefix of this keyword line
            bool shouldStrip = false;
            for (const auto& sk : stripSet) {
                if (upper.size() >= sk.size() &&
                    upper.compare(0, sk.size(), sk) == 0) {
                    // Make sure it's a complete keyword match:
                    // either exact length, or next char is space/underscore/newline
                    if (upper.size() == sk.size() ||
                        upper[sk.size()] == ' ' ||
                        upper[sk.size()] == '_' ||
                        upper[sk.size()] == '\t') {
                        shouldStrip = true;
                        break;
                    }
                }
            }

            if (shouldStrip) {
                skipping = true;
                ++skippedLines;
                continue;
            } else {
                skipping = false;
            }
        }

        if (skipping) {
            ++skippedLines;
            continue;
        }

        outf << line << "\n";
    }

    inf.close();
    outf.close();

    console.info("Output: " + outputPath);
    console.info("  Total lines: " + std::to_string(totalLines));
    console.info("  Stripped:     " + std::to_string(skippedLines));
    console.info("  Remaining:    " + std::to_string(totalLines - skippedLines));

    return 0;
}
