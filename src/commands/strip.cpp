#include "strip.h"
#include "parser/IncludeClosure.h"   // FlatDeck — flatten_includes(2026-10-17)
#include "parser/IncludeScan.h"      // 덱이 쪼개져 있나 — 안내·거절
#include "parser/DeckWriter.h"
#include "util/YamlComment.h"
#include "cli/ConsoleOutput.h"

#include <string>
#include <vector>
#include <set>
#include <fstream>
#include <sstream>
#include <algorithm>

// Knowledge graph (lat.md):
//   @lat: [[modules/commands]]
//   @lat: [[commands/strip]]

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
    {   // 탭으로 들여쓴 YAML 은 블록이 통째로 무너져 조용히 아무 일도 안 했다 — 파싱 전에 거른다
        std::string tabLine;
        if (KooRemapper::yamlScanTabIndent(yamlFile, tabLine)) {
            console.error(KooRemapper::yamlTabIndentMessage("strip", tabLine));
            return 1;
        }
    }
    // --- Parse YAML config ---
    std::ifstream yf(yamlFile);
    if (!yf.is_open()) {
        console.error("Cannot open config: " + yamlFile);
        return 1;
    }
    KooRemapper::yamlSkipBOM(yf);   // 윈도우 편집기가 붙인 BOM 이 첫 키를 망가뜨렸다

    std::string modelPath, outputPath;
    bool flattenIncludes = false;   // `flatten_includes: true` — 인클루드 닫힘을 펼쳐 한 덱으로(2026-10-17)
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
                std::string val = st_trim(KooRemapper::yamlStripComment(trimmed.substr(1)));
                val = st_stripQuotes(val);
                if (!val.empty()) stripKeywords.push_back(val);
                continue;
            }
        }

        // Top-level key: value
        size_t colon = trimmed.find(':');
        if (colon == std::string::npos) continue;

        std::string key = st_trim(trimmed.substr(0, colon));
        std::string val = st_trim(KooRemapper::yamlStripComment(trimmed.substr(colon + 1)));
        val = st_stripQuotes(val);

        if (key == "flatten_includes") {
            bool ok = true;
            flattenIncludes = KooRemapper::yamlBoolValue(val, ok);
            if (!ok) console.warning("flatten_includes 값 「" + val + "」 을 참·거짓으로 읽지 못했다 — true 로 주라(지금은 펼치지 않는다)");
        } else if (key == "model" || key == "input") {
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
            configDir = yamlFile.substr(0, sep);
    }
    auto resolvePath = [&](const std::string& p) -> std::string {
        return KooRemapper::yamlResolvePath(configDir, p);   // YAML 폴더 기준(절대 경로는 그대로)
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

    // ★인클루드(2026-10-17) — strip 은 주 덱 줄만 거른다. 인클루드 안의 카드는 걸러지지 않고 *INCLUDE 줄로 남거나(그 줄을
    //   지우면) 통째로 사라진다 — 어느 쪽이든 「이 키워드를 뺀 덱」이 아니다. 펼치지 않으면 멈춘다.
    // ★`flatten_includes`(2026-10-17) — 인클루드 닫힘을 펼친 덱(주 덱 옆 임시 파일)을 읽고 고친다 · 산출은 홀로 선다
    const std::string modelOrig = modelPath;
    KooRemapper::include_closure::FlatDeck flat;
    if (flattenIncludes) {
        std::string why;
        if (!flat.make(modelPath, why)) { console.error("flatten_includes: " + why); return 1; }
        if (flat.active()) {
            console.info("flatten_includes: 인클루드 " + std::to_string(flat.files()) +
                         "개를 펼쳐 한 덱으로 고친다 — 산출은 홀로 선다");
            modelPath = flat.path();
        }
    }
    if (!flat.active() && KooRemapper::include_scan::scanFile(modelPath).count > 0) {
        // 남길 키워드가 인클루드 안에도 있을 때만 멈춘다 — 그 밖의 인클루드 카드는 strip 이 어차피 버리는 것이다
        std::vector<std::string> mainLines;
        {
            std::ifstream mf(modelPath);
            for (std::string l; std::getline(mf, l);) { if (!l.empty() && l.back() == '\r') l.pop_back(); mainLines.push_back(l); }
        }
        const auto clo = KooRemapper::include_closure::read(modelPath, mainLines);
        for (const auto& fl : clo.files)
            for (const auto& l : fl.lines) {
                if (l.empty() || l[0] != '*') continue;
                const std::string up = st_toUpper(l.substr(0, l.find_first_of(" \t")));
                for (const auto& want : stripSet) {
                    if (up.rfind(want, 0) != 0) continue;
                    console.error("남길 키워드 " + want + " 가 인클루드 「" + fl.path + "」 안에도 있다 — 주 덱만 거르면 그 카드가 "
                                  "조용히 빠진다. `flatten_includes: true` 를 주면 닫힘을 펼쳐 한 덱에서 거른다");
                    return 1;
                }
            }
    }

    // --- Read input file ---
    std::ifstream inf(modelPath);
    if (!inf.is_open()) {
        console.error("Cannot open input: " + modelPath);
        return 1;
    }

    KooRemapper::DeckWriter outf_w(outputPath, KooRemapper::deck_newline::detect(modelOrig));
    if (!outf_w.ok()) {
        console.error("Cannot open output: " + outputPath);
        return 1;
    }
    std::ostream& outf = outf_w.stream();

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
    outf_w.close();

    console.info("Output: " + outputPath);
    console.info("  Total lines: " + std::to_string(totalLines));
    console.info("  Stripped:     " + std::to_string(skippedLines));
    console.info("  Remaining:    " + std::to_string(totalLines - skippedLines));

    return 0;
}
