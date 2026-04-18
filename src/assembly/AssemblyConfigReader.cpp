#include "assembly/AssemblyConfigReader.h"
#include "validation/MaterialCardValidator.h"
#include <fstream>
#include <sstream>
#include <stdexcept>
#include <algorithm>
#include <iostream>

namespace KooRemapper {

std::string AssemblyConfigReader::trim(const std::string& str) {
    size_t start = 0;
    size_t end = str.length();
    while (start < end && std::isspace(str[start])) start++;
    while (end > start && std::isspace(str[end - 1])) end--;
    return str.substr(start, end - start);
}

static std::string stripComment(const std::string& str) {
    size_t pos = str.find('#');
    if (pos != std::string::npos) {
        // Remove everything from '#' onward, then trim
        std::string result = str.substr(0, pos);
        // Trim trailing whitespace before comment
        size_t end = result.length();
        while (end > 0 && std::isspace(result[end - 1])) end--;
        return result.substr(0, end);
    }
    return str;
}

static int countIndent(const std::string& line) {
    int n = 0;
    while (n < static_cast<int>(line.length()) && line[n] == ' ') n++;
    return n;
}

static std::string stripQuotes(const std::string& s) {
    if (s.size() >= 2 && ((s.front()=='"' && s.back()=='"') || (s.front()=='\'' && s.back()=='\'')))
        return s.substr(1, s.size()-2);
    return s;
}

AssemblyConfig AssemblyConfigReader::readFile(const std::string& filename) {
    std::ifstream file(filename);
    if (!file.is_open()) {
        throw std::runtime_error("Cannot open assembly config: " + filename);
    }
    std::stringstream buffer;
    buffer << file.rdbuf();
    return readString(buffer.str());
}

AssemblyConfig AssemblyConfigReader::readString(const std::string& yamlContent) {
    AssemblyConfig config;

    // Collect all lines first (needed for multi-line block lookahead)
    std::vector<std::string> lines;
    {
        std::istringstream stream(yamlContent);
        std::string line;
        while (std::getline(stream, line)) {
            if (!line.empty() && line.back() == '\r') line.pop_back();
            lines.push_back(line);
        }
    }

    enum class Section { NONE, OPERATIONS, MATERIAL };
    Section section = Section::NONE;
    bool inOperationItem = false;
    bool inLayersList = false;
    bool inLayerItem = false;
    int layersKeyIndent = 0;   // indent of "layers:" key, used to guard layer item detection
    bool inTargetsList = false;
    bool inTargetItem = false;
    int targetsKeyIndent = 0;  // indent of "targets:" key for IGA
    bool inDataBboxSection = false;
    int dataBboxIndent = 0;    // indent of "data_bbox:" key for warpage
    bool readingMaterialCard = false;
    bool readingCzmMaterialCard = false;
    int materialCardBaseIndent = 0;
    enum class MaterialCardTarget { NONE, RESTACK_LAYER, OFFSET, OFFSET_CZM, OFFSET_MULTI };
    MaterialCardTarget materialCardTarget = MaterialCardTarget::NONE;
    bool inShapeSection = false;
    bool inPointsList = false;
    bool inMaterialCardsList = false;
    int materialCardsKeyIndent = 0;
    bool readingMaterialCardsItem = false;
    bool inMatdbRulesList = false;
    bool inMatdbRuleItem = false;
    int matdbRulesKeyIndent = 0;
    bool inLoadCasesList = false;
    bool inLoadCaseItem = false;
    int loadCasesKeyIndent = 0;
    bool inLoadCurveList = false;
    int loadCurveKeyIndent = 0;
    bool inContactActionsList = false;
    bool inContactActionItem = false;
    int contactActionsKeyIndent = 0;
    bool inContactSlave = false;
    bool inContactMaster = false;
    bool inBoundaryList = false;
    bool inBoundaryItem = false;
    int boundaryListKeyIndent = 0;
    bool inRbeList = false;
    bool inRbeItem = false;
    int rbeListKeyIndent = 0;

    for (size_t li = 0; li < lines.size(); ++li) {
        const std::string& line = lines[li];
        std::string trimmed = trim(line);
        int indent = countIndent(line);

        // Multi-line material_card block reading
        if (readingMaterialCard || readingCzmMaterialCard || readingMaterialCardsItem) {
            if (trimmed.empty()) {
                // Empty line inside block → include as blank line
                if (!config.operations.empty()) {
                    if (materialCardTarget == MaterialCardTarget::RESTACK_LAYER &&
                        config.operations.back().type == AssemblyOperation::RESTACK &&
                        !config.operations.back().restack.layers.empty()) {
                        config.operations.back().restack.layers.back().materialCard += "\n";
                    } else if (materialCardTarget == MaterialCardTarget::OFFSET &&
                               config.operations.back().type == AssemblyOperation::OFFSET) {
                        config.operations.back().offset.materialCard += "\n";
                    } else if (materialCardTarget == MaterialCardTarget::OFFSET_CZM &&
                               config.operations.back().type == AssemblyOperation::OFFSET) {
                        config.operations.back().offset.czmMaterialCard += "\n";
                    } else if (materialCardTarget == MaterialCardTarget::OFFSET_MULTI &&
                               config.operations.back().type == AssemblyOperation::OFFSET &&
                               !config.operations.back().offset.materialCards.empty()) {
                        config.operations.back().offset.materialCards.back() += "\n";
                    }
                }
                continue;
            }
            if (indent >= materialCardBaseIndent) {
                // Part of the multi-line block - strip the block indentation
                std::string content = line.substr(materialCardBaseIndent);
                // Trim trailing spaces
                size_t end = content.find_last_not_of(" \t\r");
                if (end != std::string::npos) content = content.substr(0, end + 1);

                if (!config.operations.empty()) {
                    if (materialCardTarget == MaterialCardTarget::RESTACK_LAYER &&
                        config.operations.back().type == AssemblyOperation::RESTACK &&
                        !config.operations.back().restack.layers.empty()) {
                        auto& card = config.operations.back().restack.layers.back().materialCard;
                        if (!card.empty()) card += "\n";
                        card += content;
                    } else if (materialCardTarget == MaterialCardTarget::OFFSET &&
                               config.operations.back().type == AssemblyOperation::OFFSET) {
                        auto& card = config.operations.back().offset.materialCard;
                        if (!card.empty()) card += "\n";
                        card += content;
                    } else if (materialCardTarget == MaterialCardTarget::OFFSET_CZM &&
                               config.operations.back().type == AssemblyOperation::OFFSET) {
                        auto& card = config.operations.back().offset.czmMaterialCard;
                        if (!card.empty()) card += "\n";
                        card += content;
                    } else if (materialCardTarget == MaterialCardTarget::OFFSET_MULTI &&
                               config.operations.back().type == AssemblyOperation::OFFSET &&
                               !config.operations.back().offset.materialCards.empty()) {
                        auto& card = config.operations.back().offset.materialCards.back();
                        if (!card.empty()) card += "\n";
                        card += content;
                    }
                }
                continue;
            }
            // Indentation decreased → end of block
            readingMaterialCard = false;
            readingCzmMaterialCard = false;
            readingMaterialCardsItem = false;
            materialCardTarget = MaterialCardTarget::NONE;
            // Fall through to process this line normally
        }

        if (trimmed.empty() || trimmed[0] == '#') continue;

        // Top-level keys (indent 0)
        if (indent == 0) {
            inLayersList = false;
            inLayerItem = false;
            inTargetsList = false;
            inTargetItem = false;
            inOperationItem = false;

            size_t colonPos = trimmed.find(':');
            if (colonPos != std::string::npos) {
                std::string key = trim(trimmed.substr(0, colonPos));
                std::string val = trim(trimmed.substr(colonPos + 1));

                if (key == "base_model") {
                    config.baseModel = val;
                    section = Section::NONE;
                } else if (key == "output") {
                    config.output = val;
                    section = Section::NONE;
                } else if (key == "dynamic_relaxation") {
                    config.dynamicRelaxation = (val == "true" || val == "yes" || val == "1");
                    section = Section::NONE;
                } else if (key == "dynain_embed") {
                    config.dynainEmbed = (val == "true" || val == "yes" || val == "1");
                    section = Section::NONE;
                } else if (key == "operations") {
                    section = Section::OPERATIONS;
                    inOperationItem = false;
                } else if (key == "material") {
                    section = Section::MATERIAL;
                    inOperationItem = false;
                }
            }
            continue;
        }

        // Parse based on current section
        if (section == Section::OPERATIONS) {
            // Exit layer context if we've dedented back to or below the layers: key level
            if ((inLayersList || inLayerItem) && indent <= layersKeyIndent) {
                inLayersList = false;
                inLayerItem = false;
            }

            // Exit targets context if we've dedented back to or below the targets: key level
            if ((inTargetsList || inTargetItem) && indent <= targetsKeyIndent) {
                inTargetsList = false;
                inTargetItem = false;
            }

            // --- IGA targets list items: "    - target_pid: 3" ---
            if (inTargetsList && indent > targetsKeyIndent && trimmed[0] == '-' && trimmed.size() >= 2 && trimmed[1] == ' ') {
                std::string afterDash = trim(trimmed.substr(2));
                size_t colonPos = afterDash.find(':');
                if (colonPos != std::string::npos) {
                    std::string key = trim(afterDash.substr(0, colonPos));
                    std::string val = trim(afterDash.substr(colonPos + 1));

                    if (!config.operations.empty() &&
                        config.operations.back().type == AssemblyOperation::IGA) {
                        IGATargetConfig tgt;
                        if (key == "target_pid") {
                            try { tgt.targetPid = std::stoi(val); } catch (...) {}
                        }
                        config.operations.back().iga.targets.push_back(tgt);
                        inTargetItem = true;
                    }
                }
                continue;
            }

            // --- IGA target item sub-keys ---
            if (inTargetItem && !config.operations.empty() &&
                config.operations.back().type == AssemblyOperation::IGA &&
                !config.operations.back().iga.targets.empty()) {
                size_t colonPos = trimmed.find(':');
                if (colonPos != std::string::npos) {
                    std::string key = trim(trimmed.substr(0, colonPos));
                    std::string val = trim(trimmed.substr(colonPos + 1));
                    auto& tgt = config.operations.back().iga.targets.back();
                    try {
                        if (key == "target_pid") tgt.targetPid = std::stoi(val);
                        else if (key == "element_size") tgt.elementSize = std::stod(val);
                        else if (key == "element_size_r") tgt.elementSizeR = std::stod(val);
                        else if (key == "element_size_s") tgt.elementSizeS = std::stod(val);
                        else if (key == "element_size_t") tgt.elementSizeT = std::stod(val);
                        else if (key == "offset") tgt.offset = std::stod(val);
                        else if (key == "bbox_scale") tgt.bboxScale = std::stod(val);
                        else if (key == "bbox_scale_r") tgt.bboxScaleR = std::stod(val);
                        else if (key == "bbox_scale_s") tgt.bboxScaleS = std::stod(val);
                        else if (key == "bbox_scale_t") tgt.bboxScaleT = std::stod(val);
                        else if (key == "ir") tgt.ir = std::stoi(val);
                        else if (key == "styp") tgt.styp = std::stoi(val);
                        else if (key == "tollg") tgt.tollg = std::stod(val);
                        else if (key == "pr") tgt.pr = std::stoi(val);
                        else if (key == "ps") tgt.ps = std::stoi(val);
                        else if (key == "pt") tgt.pt = std::stoi(val);
                        else if (key == "nisr") tgt.nisr = std::stoi(val);
                        else if (key == "niss") tgt.niss = std::stoi(val);
                        else if (key == "nist") tgt.nist = std::stoi(val);
                    } catch (...) {}
                    continue;
                }
            }

            // --- Layer list items: "      - thickness: 0.5" ---
            // Only match if indent is strictly greater than layers: key indent (to avoid matching next operation's "  - type:")
            if (inLayersList && indent > layersKeyIndent && trimmed[0] == '-' && trimmed.size() >= 2 && trimmed[1] == ' ') {
                std::string afterDash = trim(trimmed.substr(2));
                size_t colonPos = afterDash.find(':');
                if (colonPos != std::string::npos) {
                    std::string key = trim(afterDash.substr(0, colonPos));
                    std::string val = trim(afterDash.substr(colonPos + 1));

                    if (!config.operations.empty() &&
                        config.operations.back().type == AssemblyOperation::RESTACK) {
                        RestackLayer layer;
                        if (key == "thickness") {
                            try { layer.thickness = std::stod(val); } catch (...) {}
                        } else if (key == "title" || key == "name") {
                            layer.title = val;
                        }
                        config.operations.back().restack.layers.push_back(layer);
                        inLayerItem = true;
                    }
                }
                continue;
            }

            // --- Layer item sub-keys: "        material_card: |" ---
            if (inLayerItem && !inOperationItem) {
                // This shouldn't happen - inLayerItem implies we're inside layers
            }
            if (inLayerItem) {
                size_t colonPos = trimmed.find(':');
                if (colonPos != std::string::npos) {
                    std::string key = trim(trimmed.substr(0, colonPos));
                    std::string val = trim(trimmed.substr(colonPos + 1));

                    if (!config.operations.empty() &&
                        config.operations.back().type == AssemblyOperation::RESTACK &&
                        !config.operations.back().restack.layers.empty()) {
                        auto& layer = config.operations.back().restack.layers.back();
                        if (key == "thickness") {
                            try { layer.thickness = std::stod(val); } catch (...) {}
                        } else if (key == "num_elements" || key == "nz") {
                            try { layer.numElements = std::stoi(val); } catch (...) {}
                        } else if (key == "element_type") {
                            layer.elementType = val;
                        } else if (key == "title" || key == "name") {
                            layer.title = val;
                        } else if (key == "czm_normal") {
                            try { layer.czmNormal = std::stod(val); } catch (...) {}
                        } else if (key == "czm_shear") {
                            try { layer.czmShear = std::stod(val); } catch (...) {}
                        } else if (key == "material_card") {
                            if (val == "|") {
                                // Multi-line block: find indentation of first content line
                                readingMaterialCard = true;
                                materialCardTarget = MaterialCardTarget::RESTACK_LAYER;
                                // Look ahead to find the indentation of the first content line
                                materialCardBaseIndent = indent + 2; // default
                                for (size_t ahead = li + 1; ahead < lines.size(); ++ahead) {
                                    std::string aheadTrimmed = trim(lines[ahead]);
                                    if (!aheadTrimmed.empty() && aheadTrimmed[0] != '#') {
                                        materialCardBaseIndent = countIndent(lines[ahead]);
                                        break;
                                    }
                                }
                                layer.materialCard = "";
                            } else {
                                // Single-line value
                                layer.materialCard = val;
                            }
                        }
                    }
                    continue;
                }
            }

            // --- Matdb materials rule list items: "      - match: STS304" ---
            if (inMatdbRulesList && indent > matdbRulesKeyIndent && trimmed[0] == '-' && trimmed.size() >= 2 && trimmed[1] == ' ') {
                std::string afterDash = trim(trimmed.substr(2));
                size_t colonPos = afterDash.find(':');
                if (colonPos != std::string::npos) {
                    std::string key = trim(afterDash.substr(0, colonPos));
                    std::string val = trim(afterDash.substr(colonPos + 1));

                    if (!config.operations.empty() &&
                        config.operations.back().type == AssemblyOperation::MATDB) {
                        MatdbMaterialRule rule;
                        if (key == "match") rule.match = stripQuotes(val);
                        else if (key == "match_part") rule.matchPart = stripQuotes(val);
                        else if (key == "mid") { try { rule.mid = std::stoi(val); } catch (...) {} }
                        config.operations.back().matdb.rules.push_back(rule);
                        inMatdbRuleItem = true;
                    }
                }
                continue;
            }

            // --- Matdb rule item sub-keys ---
            if (inMatdbRuleItem && indent > matdbRulesKeyIndent) {
                size_t colonPos = trimmed.find(':');
                if (colonPos != std::string::npos) {
                    std::string key = trim(trimmed.substr(0, colonPos));
                    std::string val = trim(trimmed.substr(colonPos + 1));

                    if (!config.operations.empty() &&
                        config.operations.back().type == AssemblyOperation::MATDB &&
                        !config.operations.back().matdb.rules.empty()) {
                        auto& rule = config.operations.back().matdb.rules.back();
                        if (key == "match") rule.match = stripQuotes(val);
                        else if (key == "match_part") rule.matchPart = stripQuotes(val);
                        else if (key == "mid") { try { rule.mid = std::stoi(val); } catch (...) {} }
                        else if (key == "mat_type") rule.matType = stripQuotes(val);
                        else if (key == "thermal") {
                            if (val == "false" || val == "no" || val == "0") rule.thermalOverride = 0;
                            else if (val == "true" || val == "yes" || val == "1") rule.thermalOverride = 1;
                        }
                    }
                    continue;
                }
            }

            // Exit matdb rules list when indent decreases
            if (inMatdbRulesList && indent <= matdbRulesKeyIndent) {
                inMatdbRulesList = false;
                inMatdbRuleItem = false;
            }

            // --- Load cases curve points: "        - [0.0, 1.0]" ---
            if (inLoadCurveList && indent > loadCurveKeyIndent && trimmed[0] == '-' && trimmed.size() >= 2 && trimmed[1] == ' ') {
                std::string rest = trim(trimmed.substr(2));
                if (!rest.empty() && rest.front() == '[' && rest.back() == ']') {
                    rest = rest.substr(1, rest.size()-2);
                    size_t comma = rest.find(',');
                    if (comma != std::string::npos &&
                        !config.operations.empty() &&
                        config.operations.back().type == AssemblyOperation::LOAD &&
                        !config.operations.back().load.loads.empty()) {
                        LoadCurvePoint pt;
                        try {
                            pt.time = std::stod(trim(rest.substr(0, comma)));
                            pt.value = std::stod(trim(rest.substr(comma+1)));
                            config.operations.back().load.loads.back().curve.push_back(pt);
                        } catch(...) {}
                    }
                }
                continue;
            }

            // Exit load curve list when indent decreases
            if (inLoadCurveList && indent <= loadCurveKeyIndent) {
                inLoadCurveList = false;
            }

            // --- Contact actions list items: "      - action: create" ---
            if (inContactActionsList && indent > contactActionsKeyIndent && trimmed[0] == '-' && trimmed.size() >= 2 && trimmed[1] == ' ') {
                std::string afterDash = trim(trimmed.substr(2));
                size_t colonPos = afterDash.find(':');
                if (colonPos != std::string::npos &&
                    !config.operations.empty() &&
                    config.operations.back().type == AssemblyOperation::CONTACT) {
                    std::string key = trim(afterDash.substr(0, colonPos));
                    std::string val = stripQuotes(trim(afterDash.substr(colonPos + 1)));
                    ContactAction cact;
                    if (key == "action") cact.action = val;
                    else if (key == "type") cact.type = val;
                    config.operations.back().contact.actions.push_back(cact);
                    inContactActionItem = true;
                    inContactSlave = false;
                    inContactMaster = false;
                }
                continue;
            }

            // --- Contact action item sub-keys ---
            if (inContactActionItem && indent > contactActionsKeyIndent) {
                size_t colonPos = trimmed.find(':');
                if (colonPos != std::string::npos &&
                    !config.operations.empty() &&
                    config.operations.back().type == AssemblyOperation::CONTACT &&
                    !config.operations.back().contact.actions.empty()) {
                    std::string key = trim(trimmed.substr(0, colonPos));
                    std::string val = stripQuotes(trim(trimmed.substr(colonPos + 1)));
                    auto& cact = config.operations.back().contact.actions.back();

                    // Slave/master sub-sections
                    if (key == "slave") {
                        inContactSlave = true; inContactMaster = false;
                        // inline: slave: {pid: 3}  or slave with pid on same line
                        if (!val.empty()) {
                            try { cact.slave.pid = std::stoi(val); } catch(...) {}
                        }
                    } else if (key == "master") {
                        inContactMaster = true; inContactSlave = false;
                        if (!val.empty()) {
                            try { cact.master.pid = std::stoi(val); } catch(...) {}
                        }
                    } else if (key == "pid") {
                        if (inContactSlave) { try { cact.slave.pid = std::stoi(val); } catch(...) {} }
                        else if (inContactMaster) { try { cact.master.pid = std::stoi(val); } catch(...) {} }
                    } else if (key == "as_segment") {
                        bool bval = (val == "true" || val == "yes" || val == "1");
                        if (inContactSlave) cact.slave.asSegment = bval;
                        else if (inContactMaster) cact.master.asSegment = bval;
                    } else if (key == "facing") {
                        bool bval = (val == "true" || val == "yes" || val == "1");
                        if (inContactSlave) cact.slave.facing = bval;
                        else if (inContactMaster) cact.master.facing = bval;
                    } else if (key == "pids" && !val.empty() && val.front() == '[' && val.back() == ']') {
                        std::string inner = val.substr(1, val.size()-2);
                        std::istringstream iss(inner);
                        std::string tok;
                        std::vector<int>& target = inContactSlave ? cact.slave.pids : cact.master.pids;
                        while (std::getline(iss, tok, ',')) {
                            try { target.push_back(std::stoi(trim(tok))); } catch(...) {}
                        }
                    } else if (key == "action") cact.action = val;
                    else if (key == "type" || key == "contact_type") cact.type = val;
                    else if (key == "friction") { try { cact.friction = std::stod(val); } catch(...) {} }
                    else if (key == "title") cact.title = val;
                    else if (key == "title_prefix") cact.titlePrefix = val;
                    else if (key == "scope") cact.scope = val;
                    else if (key == "tolerance") { try { cact.tolerance = std::stod(val); } catch(...) {} }
                    else if (key == "normal_angle") { try { cact.normalAngle = std::stod(val); } catch(...) {} }
                    else if (key == "auto_create") cact.autoCreate = (val == "true" || val == "yes" || val == "1");
                    else if (key == "skip_existing") cact.skipExisting = val;
                    else if (key == "subtract_existing") cact.subtractExisting = (val == "true" || val == "yes" || val == "1");
                    else if (key == "include" && !val.empty() && val.front() == '[' && val.back() == ']') {
                        std::string inner = val.substr(1, val.size()-2);
                        std::istringstream iss(inner);
                        std::string tok;
                        while (std::getline(iss, tok, ',')) cact.includeKeys.push_back(trim(tok));
                    } else if (key == "exclude" && !val.empty() && val.front() == '[' && val.back() == ']') {
                        std::string inner = val.substr(1, val.size()-2);
                        std::istringstream iss(inner);
                        std::string tok;
                        while (std::getline(iss, tok, ',')) cact.excludeKeys.push_back(trim(tok));
                    }
                    continue;
                }
            }

            // Exit contact actions list when indent decreases
            if (inContactActionsList && indent <= contactActionsKeyIndent) {
                inContactActionsList = false;
                inContactActionItem = false;
                inContactSlave = false;
                inContactMaster = false;
            }

            // --- Load cases list items: "      - part: 3" ---
            if (inLoadCasesList && !inLoadCurveList && indent > loadCasesKeyIndent && trimmed[0] == '-' && trimmed.size() >= 2 && trimmed[1] == ' ') {
                std::string afterDash = trim(trimmed.substr(2));
                size_t colonPos = afterDash.find(':');
                if (colonPos != std::string::npos &&
                    !config.operations.empty() &&
                    config.operations.back().type == AssemblyOperation::LOAD) {
                    std::string key = trim(afterDash.substr(0, colonPos));
                    std::string val = stripQuotes(trim(afterDash.substr(colonPos + 1)));
                    LoadCase lcase;
                    if (key == "part") {
                        try { lcase.pid = std::stoi(val); } catch(...) { lcase.partName = val; }
                    } else if (key == "mode") lcase.mode = val;
                    else if (key == "value") { try { lcase.value = std::stod(val); } catch(...) {} }
                    else if (key == "select") lcase.select = val;
                    config.operations.back().load.loads.push_back(lcase);
                    inLoadCaseItem = true;
                    inLoadCurveList = false;
                }
                continue;
            }

            // --- Load case item sub-keys ---
            if (inLoadCaseItem && indent > loadCasesKeyIndent) {
                size_t colonPos = trimmed.find(':');
                if (colonPos != std::string::npos &&
                    !config.operations.empty() &&
                    config.operations.back().type == AssemblyOperation::LOAD &&
                    !config.operations.back().load.loads.empty()) {
                    std::string key = trim(trimmed.substr(0, colonPos));
                    std::string val = stripQuotes(trim(trimmed.substr(colonPos + 1)));
                    auto& lcase = config.operations.back().load.loads.back();

                    if (key == "curve") {
                        inLoadCurveList = true;
                        loadCurveKeyIndent = indent;
                    } else if (key == "direction" && !val.empty() && val.front() == '[' && val.back() == ']') {
                        std::string inner = val.substr(1, val.size()-2);
                        std::istringstream iss(inner);
                        std::string tok;
                        int di = 0;
                        while (std::getline(iss, tok, ',') && di < 3) {
                            try { lcase.direction[di] = std::stod(trim(tok)); } catch(...) {}
                            di++;
                        }
                    } else if (key == "part") {
                        try { lcase.pid = std::stoi(val); } catch(...) { lcase.partName = val; }
                    } else if (key == "mode") lcase.mode = val;
                    else if (key == "value") { try { lcase.value = std::stod(val); } catch(...) {} }
                    else if (key == "select") lcase.select = val;
                    else if (key == "angle") { try { lcase.angle = std::stod(val); } catch(...) {} }
                    else if (key == "set_id") { try { lcase.setId = std::stoi(val); } catch(...) {} }
                    else if (key == "contact_id") { try { lcase.contactId = std::stoi(val); } catch(...) {} }
                    continue;
                }
            }

            // Exit load cases list when indent decreases
            if (inLoadCasesList && indent <= loadCasesKeyIndent) {
                inLoadCasesList = false;
                inLoadCaseItem = false;
                inLoadCurveList = false;
            }

            // --- Boundary list items: "      - part: 3" ---
            if (inBoundaryList && indent > boundaryListKeyIndent && trimmed[0] == '-' && trimmed.size() >= 2 && trimmed[1] == ' ') {
                std::string afterDash = trim(trimmed.substr(2));
                size_t colonPos = afterDash.find(':');
                if (colonPos != std::string::npos &&
                    !config.operations.empty() &&
                    config.operations.back().type == AssemblyOperation::BOUNDARY) {
                    std::string key = trim(afterDash.substr(0, colonPos));
                    std::string val = stripQuotes(trim(afterDash.substr(colonPos + 1)));
                    BoundaryCase bcase;
                    if (key == "part") {
                        try { bcase.pid = std::stoi(val); } catch(...) { bcase.partName = val; }
                    } else if (key == "dof") bcase.dof = val;
                    else if (key == "select") bcase.select = val;
                    config.operations.back().boundary.boundaries.push_back(bcase);
                    inBoundaryItem = true;
                }
                continue;
            }

            // --- Boundary item sub-keys ---
            if (inBoundaryItem && indent > boundaryListKeyIndent) {
                size_t colonPos = trimmed.find(':');
                if (colonPos != std::string::npos &&
                    !config.operations.empty() &&
                    config.operations.back().type == AssemblyOperation::BOUNDARY &&
                    !config.operations.back().boundary.boundaries.empty()) {
                    std::string key = trim(trimmed.substr(0, colonPos));
                    std::string val = stripQuotes(trim(trimmed.substr(colonPos + 1)));
                    auto& bcase = config.operations.back().boundary.boundaries.back();

                    if (key == "part") {
                        try { bcase.pid = std::stoi(val); } catch(...) { bcase.partName = val; }
                    } else if (key == "dof") bcase.dof = val;
                    else if (key == "select") bcase.select = val;
                    else if (key == "angle") { try { bcase.angle = std::stod(val); } catch(...) {} }
                    else if (key == "set_id") { try { bcase.setId = std::stoi(val); } catch(...) {} }
                    else if (key == "dofx") { try { bcase.dofx = std::stoi(val); } catch(...) {} }
                    else if (key == "dofy") { try { bcase.dofy = std::stoi(val); } catch(...) {} }
                    else if (key == "dofz") { try { bcase.dofz = std::stoi(val); } catch(...) {} }
                    else if (key == "dofrx") { try { bcase.dofrx = std::stoi(val); } catch(...) {} }
                    else if (key == "dofry") { try { bcase.dofry = std::stoi(val); } catch(...) {} }
                    else if (key == "dofrz") { try { bcase.dofrz = std::stoi(val); } catch(...) {} }
                    else if (key == "direction" && !val.empty() && val.front() == '[' && val.back() == ']') {
                        std::string inner = val.substr(1, val.size()-2);
                        std::istringstream iss(inner);
                        std::string tok;
                        int di = 0;
                        while (std::getline(iss, tok, ',') && di < 3) {
                            try { bcase.direction[di] = std::stod(trim(tok)); } catch(...) {}
                            di++;
                        }
                    }
                    continue;
                }
            }

            // Exit boundary list when indent decreases
            if (inBoundaryList && indent <= boundaryListKeyIndent) {
                inBoundaryList = false;
                inBoundaryItem = false;
            }

            // --- RBE list items: "      - part: 9" ---
            if (inRbeList && indent > rbeListKeyIndent && trimmed[0] == '-' && trimmed.size() >= 2 && trimmed[1] == ' ') {
                std::string afterDash = trim(trimmed.substr(2));
                size_t colonPos = afterDash.find(':');
                if (colonPos != std::string::npos &&
                    !config.operations.empty() &&
                    config.operations.back().type == AssemblyOperation::RBE) {
                    std::string key = trim(afterDash.substr(0, colonPos));
                    std::string val = stripQuotes(trim(afterDash.substr(colonPos + 1)));
                    RbeCase rcase;
                    if (key == "part") {
                        try { rcase.pid = std::stoi(val); } catch(...) { rcase.partName = val; }
                    } else if (key == "select") rcase.select = val;
                    else if (key == "type") rcase.type = val;
                    else if (key == "mode") rcase.mode = val;
                    config.operations.back().rbe.constraints.push_back(rcase);
                    inRbeItem = true;
                }
                continue;
            }

            // --- RBE item sub-keys ---
            if (inRbeItem && indent > rbeListKeyIndent) {
                size_t colonPos = trimmed.find(':');
                if (colonPos != std::string::npos &&
                    !config.operations.empty() &&
                    config.operations.back().type == AssemblyOperation::RBE &&
                    !config.operations.back().rbe.constraints.empty()) {
                    std::string key = trim(trimmed.substr(0, colonPos));
                    std::string val = stripQuotes(trim(trimmed.substr(colonPos + 1)));
                    auto& rcase = config.operations.back().rbe.constraints.back();

                    if (key == "part") {
                        try { rcase.pid = std::stoi(val); } catch(...) { rcase.partName = val; }
                    } else if (key == "select") rcase.select = val;
                    else if (key == "type") rcase.type = val;
                    else if (key == "mode") rcase.mode = val;
                    else if (key == "angle") { try { rcase.angle = std::stod(val); } catch(...) {} }
                    else if (key == "direction" && !val.empty() && val.front() == '[' && val.back() == ']') {
                        std::string inner = val.substr(1, val.size()-2);
                        std::istringstream iss(inner);
                        std::string tok;
                        int di = 0;
                        while (std::getline(iss, tok, ',') && di < 3) {
                            try { rcase.direction[di] = std::stod(trim(tok)); } catch(...) {}
                            di++;
                        }
                    }
                    continue;
                }
            }

            // Exit RBE list when indent decreases
            if (inRbeList && indent <= rbeListKeyIndent) {
                inRbeList = false;
                inRbeItem = false;
            }

            // --- Operation list item start: "  - type: replace" ---
            if (!inPointsList && !inMatdbRulesList && !inLoadCasesList && !inContactActionsList && !inBoundaryList && !inRbeList && trimmed[0] == '-' && trimmed.size() >= 2 && trimmed[1] == ' ') {
                inLayersList = false;
                inLayerItem = false;
                inTargetsList = false;
                inTargetItem = false;
                inDataBboxSection = false;
                inShapeSection = false;
                inPointsList = false;
                inMatdbRulesList = false;
                inMatdbRuleItem = false;

                std::string afterDash = trim(trimmed.substr(2));
                size_t colonPos = afterDash.find(':');
                if (colonPos != std::string::npos) {
                    std::string key = trim(afterDash.substr(0, colonPos));
                    std::string val = trim(afterDash.substr(colonPos + 1));

                    AssemblyOperation op;
                    if (key == "type") {
                        if (val == "replace") {
                            op.type = AssemblyOperation::REPLACE;
                        } else if (val == "squeeze") {
                            op.type = AssemblyOperation::SQUEEZE;
                        } else if (val == "restack") {
                            op.type = AssemblyOperation::RESTACK;
                        } else if (val == "bend") {
                            op.type = AssemblyOperation::BEND;
                        } else if (val == "indent") {
                            op.type = AssemblyOperation::INDENT;
                        } else if (val == "formstrain") {
                            op.type = AssemblyOperation::FORMSTRAIN;
                        } else if (val == "tet10") {
                            op.type = AssemblyOperation::TET10_CONVERT;
                            op.tet10.convertType = "tet10";
                        } else if (val == "hex20") {
                            op.type = AssemblyOperation::TET10_CONVERT;
                            op.tet10.convertType = "hex20";
                        } else if (val == "quad8") {
                            op.type = AssemblyOperation::TET10_CONVERT;
                            op.tet10.convertType = "quad8";
                        } else if (val == "tria6") {
                            op.type = AssemblyOperation::TET10_CONVERT;
                            op.tet10.convertType = "tria6";
                        } else if (val == "refine") {
                            op.type = AssemblyOperation::REFINE;
                        } else if (val == "elform") {
                            op.type = AssemblyOperation::ELFORM;
                        } else if (val == "disconnect") {
                            op.type = AssemblyOperation::DISCONNECT;
                        } else if (val == "iga") {
                            op.type = AssemblyOperation::IGA;
                        } else if (val == "warpage") {
                            op.type = AssemblyOperation::WARPAGE;
                        } else if (val == "offset") {
                            op.type = AssemblyOperation::OFFSET;
                        } else if (val == "matswap") {
                            op.type = AssemblyOperation::MATSWAP;
                        } else if (val == "matdb") {
                            op.type = AssemblyOperation::MATDB;
                        } else if (val == "load") {
                            op.type = AssemblyOperation::LOAD;
                        } else if (val == "contact") {
                            op.type = AssemblyOperation::CONTACT;
                        } else if (val == "boundary") {
                            op.type = AssemblyOperation::BOUNDARY;
                        } else if (val == "rbe") {
                            op.type = AssemblyOperation::RBE;
                        } else if (val == "wrap") {
                            op.type = AssemblyOperation::WRAP;
                        } else if (val == "update") {
                            op.type = AssemblyOperation::UPDATE;
                        } else if (val == "database") {
                            op.type = AssemblyOperation::DATABASE;
                        } else if (val == "control") {
                            op.type = AssemblyOperation::CONTROL;
                        } else if (val == "generate") {
                            op.type = AssemblyOperation::GENERATE;
                        } else if (val == "fillet") {
                            op.type = AssemblyOperation::FILLET;
                        } else if (val == "cnrb2solid") {
                            op.type = AssemblyOperation::CNRB2SOLID;
                        } else if (val == "hfdamp") {
                            op.type = AssemblyOperation::HFDAMP;
                        } else if (val == "battery") {
                            op.type = AssemblyOperation::BATTERY;
                        } else if (val == "split") {
                            op.type = AssemblyOperation::SPLIT;
                        } else {
                            throw std::runtime_error("Unknown operation type: " + val);
                        }
                    }
                    config.operations.push_back(op);
                    inOperationItem = true;
                    continue;
                }
                // If no colon found (e.g., "- |"), don't continue - let other logic handle it
            }

            // --- Indent shape points list: "        - [20, 15]" ---
            if (inPointsList && !config.operations.empty() &&
                config.operations.back().type == AssemblyOperation::INDENT) {
                if (trimmed[0] == '-' && trimmed.size() >= 2) {
                    // Parse "- [x, y]" format
                    std::string after = trim(trimmed.substr(1));
                    // Strip brackets
                    if (!after.empty() && after.front() == '[') after = after.substr(1);
                    if (!after.empty() && after.back() == ']') after.pop_back();
                    // Split by comma
                    size_t commaPos = after.find(',');
                    if (commaPos != std::string::npos) {
                        try {
                            double x1 = std::stod(trim(after.substr(0, commaPos)));
                            double x2 = std::stod(trim(after.substr(commaPos + 1)));
                            config.operations.back().indent.points.push_back({x1, x2});
                        } catch (...) {}
                    }
                    continue;
                }
                // Not a list item → end of points list
                inPointsList = false;
            }

            // --- data_bbox sub-keys ---
            if (inDataBboxSection && !config.operations.empty() &&
                config.operations.back().type == AssemblyOperation::WARPAGE) {
                // Check if we've left the data_bbox section
                if (indent <= dataBboxIndent) {
                    inDataBboxSection = false;
                } else {
                    size_t colonPos = trimmed.find(':');
                    if (colonPos != std::string::npos) {
                        std::string key = trim(trimmed.substr(0, colonPos));
                        std::string val = trim(trimmed.substr(colonPos + 1));
                        auto& wp = config.operations.back().warpage;
                        try {
                            if (key == "x_min") wp.dataBboxXmin = std::stod(val);
                            else if (key == "x_max") wp.dataBboxXmax = std::stod(val);
                            else if (key == "y_min") wp.dataBboxYmin = std::stod(val);
                            else if (key == "y_max") wp.dataBboxYmax = std::stod(val);
                        } catch (...) {}
                    }
                    continue;  // Skip normal processing for data_bbox sub-keys
                }
            }

            // --- Operation sub-keys ---
            if (inOperationItem && !config.operations.empty()) {
                size_t colonPos = trimmed.find(':');
                if (colonPos != std::string::npos) {
                    std::string key = trim(trimmed.substr(0, colonPos));
                    std::string val = trim(stripComment(trimmed.substr(colonPos + 1)));

                    auto& op = config.operations.back();
                    try {
                        if (key == "target_pid" ||
                            (key == "pid" &&
                             op.type != AssemblyOperation::MATSWAP &&
                             op.type != AssemblyOperation::MATDB &&
                             op.type != AssemblyOperation::CONTROL)) {
                            // Helper lambda: set single PID on the relevant struct
                            auto setSingle = [&](int pid) {
                                if (op.type == AssemblyOperation::REPLACE)       op.replace.targetPid    = pid;
                                else if (op.type == AssemblyOperation::SQUEEZE)  op.squeeze.targetPid    = pid;
                                else if (op.type == AssemblyOperation::RESTACK)  op.restack.targetPid    = pid;
                                else if (op.type == AssemblyOperation::BEND)     op.bend.targetPid       = pid;
                                else if (op.type == AssemblyOperation::INDENT)   op.indent.targetPid     = pid;
                                else if (op.type == AssemblyOperation::FORMSTRAIN) op.formstrain.targetPid = pid;
                                else if (op.type == AssemblyOperation::TET10_CONVERT) op.tet10.targetPid  = pid;
                                else if (op.type == AssemblyOperation::REFINE)   op.refine.targetPid     = pid;
                                else if (op.type == AssemblyOperation::ELFORM)   op.elform.targetPid     = pid;
                                else if (op.type == AssemblyOperation::DISCONNECT) op.disconnect.targetPid = pid;
                                else if (op.type == AssemblyOperation::WARPAGE)  op.warpage.targetPid    = pid;
                                else if (op.type == AssemblyOperation::FILLET)   op.fillet.targetPid     = pid;
                                else if (op.type == AssemblyOperation::SPLIT)    op.split.targetPid      = pid;
                            };
                            // Helper: push to targetPids list on structs that support it
                            auto pushMulti = [&](int pid) {
                                if (op.type == AssemblyOperation::BEND)          op.bend.targetPids.push_back(pid);
                                else if (op.type == AssemblyOperation::FORMSTRAIN)    op.formstrain.targetPids.push_back(pid);
                                else if (op.type == AssemblyOperation::TET10_CONVERT) op.tet10.targetPids.push_back(pid);
                                else if (op.type == AssemblyOperation::REFINE)   op.refine.targetPids.push_back(pid);
                                else if (op.type == AssemblyOperation::ELFORM)   op.elform.targetPids.push_back(pid);
                                else if (op.type == AssemblyOperation::WARPAGE)  op.warpage.targetPids.push_back(pid);
                                else if (op.type == AssemblyOperation::FILLET)   op.fillet.targetPids.push_back(pid);
                                else if (op.type == AssemblyOperation::SPLIT)    op.split.targetPids.push_back(pid);
                                else setSingle(pid); // ops without multi-pid: use first value
                            };

                            std::string v = val;
                            // Normalize case for "all"
                            std::string vl = v;
                            for (auto& c : vl) c = (char)tolower((unsigned char)c);

                            // Helper: expand a single token that may be "N", "N-M" range
                            auto expandToken = [](const std::string& tok, std::vector<int>& out) {
                                size_t a = tok.find_first_not_of(" \t");
                                if (a == std::string::npos) return;
                                std::string s = tok.substr(a);
                                // Trim trailing whitespace
                                size_t b = s.find_last_not_of(" \t");
                                if (b != std::string::npos) s = s.substr(0, b + 1);
                                // Check for range: "N-M"
                                size_t dash = s.find('-', s[0] == '-' ? 1 : 0);
                                if (dash != std::string::npos && dash > 0 && dash < s.size() - 1) {
                                    int lo = std::stoi(s.substr(0, dash));
                                    int hi = std::stoi(s.substr(dash + 1));
                                    if (lo > hi) std::swap(lo, hi);
                                    for (int p = lo; p <= hi; ++p) out.push_back(p);
                                } else {
                                    out.push_back(std::stoi(s));
                                }
                            };

                            if (vl == "all") {
                                setSingle(0);  // 0 = all
                            } else if (!v.empty() && v.front() == '[') {
                                // List: [1, 2, 3] or [1-3, 5, 7-9]
                                std::string inner = v.substr(1, v.size() - 2);
                                std::istringstream ss(inner);
                                std::string tok;
                                bool first = true;
                                while (std::getline(ss, tok, ',')) {
                                    std::vector<int> pids;
                                    expandToken(tok, pids);
                                    for (int pid : pids) {
                                        if (first) { setSingle(-1); first = false; }
                                        pushMulti(pid);
                                    }
                                }
                            } else {
                                // Single value or range: "3" or "1-5"
                                std::vector<int> pids;
                                expandToken(v, pids);
                                if (pids.size() == 1) {
                                    setSingle(pids[0]);
                                } else {
                                    setSingle(-1);
                                    for (int pid : pids) pushMulti(pid);
                                }
                            }
                        } else if (key == "source_pid") {
                            int pid = std::stoi(val);
                            if (op.type == AssemblyOperation::OFFSET) {
                                op.offset.sourcePid = pid;
                            }
                        } else if (op.type == AssemblyOperation::BEND) {
                            if (key == "plane") op.bend.plane = val;
                            else if (key == "mode") op.bend.mode = val;
                            else if (key == "source") op.bend.source = val;
                            else if (key == "dat_file") op.bend.datFile = val;
                            else if (key == "dat_top") op.bend.datTop = val;
                            else if (key == "dat_bottom") op.bend.datBottom = val;
                            else if (key == "expression") {
                                // Strip surrounding quotes if present
                                if (val.size() >= 2 &&
                                    ((val.front() == '"' && val.back() == '"') ||
                                     (val.front() == '\'' && val.back() == '\''))) {
                                    op.bend.expression = val.substr(1, val.size() - 2);
                                } else {
                                    op.bend.expression = val;
                                }
                            }
                        } else if (op.type == AssemblyOperation::REPLACE) {
                            if (key == "detail_flat") op.replace.detailFlat = val;
                            else if (key == "shell_bent") op.replace.shellBent = val;
                            else if (key == "prestress") op.replace.prestress = (val == "true" || val == "yes" || val == "1");
                        } else if (op.type == AssemblyOperation::SQUEEZE) {
                            if (key == "eps_x") op.squeeze.eps_x = std::stod(val);
                            else if (key == "eps_y") op.squeeze.eps_y = std::stod(val);
                            else if (key == "eps_z") op.squeeze.eps_z = std::stod(val);
                        } else if (op.type == AssemblyOperation::RESTACK) {
                            if (key == "direction") op.restack.direction = val;
                            else if (key == "element_type") op.restack.elementType = val;
                            else if (key == "element_size") { try { op.restack.elementSize = std::stod(val); } catch (...) {} }
                            else if (key == "interface_contact") op.restack.interfaceContact = val;
                            else if (key == "czm_normal") { try { op.restack.czmNormal = std::stod(val); } catch (...) {} }
                            else if (key == "czm_shear")  { try { op.restack.czmShear  = std::stod(val); } catch (...) {} }
                            else if (key == "drop_height") { try { op.restack.dropHeight = std::stod(val); } catch (...) {} }
                            else if (key == "layers") {
                                inLayersList = true;
                                inLayerItem = false;
                                layersKeyIndent = indent;
                            }
                        } else if (op.type == AssemblyOperation::INDENT) {
                            if (key == "plane") op.indent.plane = val;
                            else if (key == "direction") op.indent.direction = val;
                            else if (key == "depth") op.indent.depth = std::stod(val);
                            else if (key == "r1") op.indent.r1 = std::stod(val);
                            else if (key == "r2") op.indent.r2 = std::stod(val);
                            else if (key == "bottom_ratio") op.indent.bottomRatio = std::stod(val);
                            else if (key == "stress") op.indent.stress = (val == "true" || val == "yes" || val == "1");
                            else if (key == "shell_thickness") op.indent.shellThickness = std::stod(val);
                            else if (key == "shape") {
                                inShapeSection = true;
                                inPointsList = false;
                            }
                            else if (inShapeSection && key == "type") op.indent.shapeType = val;
                            else if (inShapeSection && key == "points") {
                                inPointsList = true;
                            }
                        } else if (op.type == AssemblyOperation::FORMSTRAIN) {
                            if (key == "shell_thickness") op.formstrain.shellThickness = std::stod(val);
                            else if (key == "min_curvature") op.formstrain.minCurvature = std::stod(val);
                        } else if (op.type == AssemblyOperation::TET10_CONVERT) {
                            if (key == "elform") op.tet10.elform = std::stoi(val);
                        } else if (op.type == AssemblyOperation::REFINE) {
                            if (key == "ratio") op.refine.ratio = std::stoi(val);
                        } else if (op.type == AssemblyOperation::ELFORM) {
                            if (key == "target_elform") {
                                // Strip quotes if present
                                if (val.size() >= 2 &&
                                    ((val.front() == '"' && val.back() == '"') ||
                                     (val.front() == '\'' && val.back() == '\''))) {
                                    op.elform.targetElform = val.substr(1, val.size() - 2);
                                } else {
                                    op.elform.targetElform = val;
                                }
                            }
                        } else if (op.type == AssemblyOperation::DISCONNECT) {
                            if (key == "mode") op.disconnect.mode = val;
                            else if (key == "cohesive_part_id") op.disconnect.cohesivePartId = std::stoi(val);
                            else if (key == "failure_strain") op.disconnect.failureStrain = std::stod(val);
                        } else if (op.type == AssemblyOperation::IGA) {
                            if (key == "targets") {
                                inTargetsList = true;
                                inTargetItem = false;
                                targetsKeyIndent = indent;
                            }
                        } else if (op.type == AssemblyOperation::WARPAGE) {
                            if (key == "dat_file") op.warpage.datFile = val;
                            else if (key == "plane") op.warpage.plane = val;
                            else if (key == "deflection_axis") op.warpage.deflectionAxis = val;
                            else if (key == "unit") op.warpage.unit = val;
                            else if (key == "mask_value") op.warpage.maskValue = std::stod(val);
                            else if (key == "noise_threshold") op.warpage.noiseThreshold = std::stod(val);
                            else if (key == "morph_factor") op.warpage.morphFactor = std::stod(val);
                            else if (key == "mode") op.warpage.mode = val;
                            else if (key == "finite_strain") {
                                bool newVal = (val == "true" || val == "yes" || val == "1");
                                std::cout << "[YAML DEBUG] finite_strain: val='" << val << "' -> " << (newVal ? "TRUE" : "FALSE") << "\n";
                                op.warpage.useFiniteStrain = newVal;
                            }
                            else if (key == "outside_behavior") op.warpage.outsideBehavior = val;
                            else if (key == "debug") op.warpage.debug = (val == "true" || val == "yes" || val == "1");
                            else if (key == "debug_prefix") op.warpage.debugPrefix = val;
                            else if (key == "data_bbox") {
                                inDataBboxSection = true;
                                dataBboxIndent = indent;
                                op.warpage.hasDataBbox = true;
                            }
                        } else if (op.type == AssemblyOperation::OFFSET) {
                            if (key == "offset_direction") op.offset.offsetDirection = val;
                            else if (key == "thickness") op.offset.thickness = std::stod(val);
                            else if (key == "thickness_formula") op.offset.thicknessFormula = val;
                            else if (key == "num_layers") op.offset.numLayers = std::stoi(val);
                            else if (key == "use_local_normals") op.offset.useLocalNormals = (val == "true" || val == "True" || val == "1");
                            // Region selection
                            else if (key == "bbox_xmin") { op.offset.region.useBoundingBox = true; op.offset.region.xMin = std::stod(val); }
                            else if (key == "bbox_xmax") { op.offset.region.useBoundingBox = true; op.offset.region.xMax = std::stod(val); }
                            else if (key == "bbox_ymin") { op.offset.region.useBoundingBox = true; op.offset.region.yMin = std::stod(val); }
                            else if (key == "bbox_ymax") { op.offset.region.useBoundingBox = true; op.offset.region.yMax = std::stod(val); }
                            else if (key == "bbox_zmin") { op.offset.region.useBoundingBox = true; op.offset.region.zMin = std::stod(val); }
                            else if (key == "bbox_zmax") { op.offset.region.useBoundingBox = true; op.offset.region.zMax = std::stod(val); }
                            else if (key == "node_id_min") op.offset.region.nodeIdMin = std::stoi(val);
                            else if (key == "node_id_max") op.offset.region.nodeIdMax = std::stoi(val);
                            else if (key == "element_id_min") op.offset.region.elementIdMin = std::stoi(val);
                            else if (key == "element_id_max") op.offset.region.elementIdMax = std::stoi(val);
                            else if (key == "element_type") op.offset.elementType = val;
                            else if (key == "connection_mode") op.offset.connectionMode = val;
                            else if (key == "czm_part_id") op.offset.czmPartId = std::stoi(val);
                            else if (key == "czm_mid") op.offset.czmMid = std::stoi(val);
                            else if (key == "prestress_mode") op.offset.prestressMode = val;
                            else if (key == "inner_offset") op.offset.innerOffset = std::stod(val);
                            else if (key == "outer_offset") op.offset.outerOffset = std::stod(val);
                            else if (key == "new_pid") op.offset.newPid = std::stoi(val);
                            else if (key == "new_secid") op.offset.newSecid = std::stoi(val);
                            else if (key == "new_mid") op.offset.newMid = std::stoi(val);
                            else if (key == "part_title") op.offset.partTitle = val;
                            else if (key == "shell_thickness") op.offset.shellThickness = std::stod(val);
                            else if (key == "shell_offset") op.offset.shellOffset = std::stod(val);
                            else if (key == "material_card") {
                                // Multi-line block starts
                                readingMaterialCard = true;
                                materialCardTarget = MaterialCardTarget::OFFSET;
                                materialCardBaseIndent = indent + 2;
                                for (size_t ahead = li + 1; ahead < lines.size(); ++ahead) {
                                    std::string aheadTrimmed = trim(lines[ahead]);
                                    if (!aheadTrimmed.empty() && aheadTrimmed[0] != '#') {
                                        materialCardBaseIndent = countIndent(lines[ahead]);
                                        break;
                                    }
                                }
                                if (val == "|") {
                                    op.offset.materialCard = "";
                                } else {
                                    op.offset.materialCard = val;
                                }
                            }
                            else if (key == "czm_material_card") {
                                // Multi-line block starts
                                readingCzmMaterialCard = true;
                                materialCardTarget = MaterialCardTarget::OFFSET_CZM;
                                materialCardBaseIndent = indent + 2;
                                for (size_t ahead = li + 1; ahead < lines.size(); ++ahead) {
                                    std::string aheadTrimmed = trim(lines[ahead]);
                                    if (!aheadTrimmed.empty() && aheadTrimmed[0] != '#') {
                                        materialCardBaseIndent = countIndent(lines[ahead]);
                                        break;
                                    }
                                }
                                if (val == "|") {
                                    op.offset.czmMaterialCard = "";
                                } else {
                                    op.offset.czmMaterialCard = val;
                                }
                            }
                            else if (key == "material_cards") {
                                // Array of material cards
                                inMaterialCardsList = true;
                                materialCardsKeyIndent = indent;
                            }
                        } else if (op.type == AssemblyOperation::MATSWAP) {
                            auto parseIntList = [&](const std::string& raw, std::vector<int>& out) {
                                std::string lv = raw;
                                if (!lv.empty() && lv.front() == '[') lv = lv.substr(1);
                                if (!lv.empty() && lv.back() == ']') lv.pop_back();
                                std::istringstream ss(lv);
                                std::string tok;
                                while (std::getline(ss, tok, ',')) {
                                    std::string t = trim(tok);
                                    if (!t.empty()) out.push_back(std::stoi(t));
                                }
                            };
                            if (key == "bundle") {
                                op.matswap.bundleFile = val;
                            } else if (key == "pid") {
                                op.matswap.pids = { std::stoi(val) };
                            } else if (key == "pids") {
                                parseIntList(val, op.matswap.pids);
                            } else if (key == "mid") {
                                op.matswap.mids = { std::stoi(val) };
                            } else if (key == "mids") {
                                parseIntList(val, op.matswap.mids);
                            } else if (key == "swap_all") {
                                op.matswap.swapAll = (val == "true" || val == "yes" || val == "1");
                            }
                        } else if (op.type == AssemblyOperation::LOAD) {
                            if (key == "loads") {
                                inLoadCasesList = true;
                                loadCasesKeyIndent = indent;
                            }
                        } else if (op.type == AssemblyOperation::CONTACT) {
                            if (key == "contacts" || key == "actions") {
                                inContactActionsList = true;
                                contactActionsKeyIndent = indent;
                            }
                        } else if (op.type == AssemblyOperation::BOUNDARY) {
                            if (key == "boundaries") {
                                inBoundaryList = true;
                                boundaryListKeyIndent = indent;
                            }
                        } else if (op.type == AssemblyOperation::RBE) {
                            if (key == "constraints" || key == "rbe") {
                                inRbeList = true;
                                rbeListKeyIndent = indent;
                            }
                        } else if (op.type == AssemblyOperation::WRAP) {
                            if (key == "target_pid") {
                                if (!val.empty() && val.front() == '[') {
                                    // Parse bracket list [10, 11, 12]
                                    std::string inner = val.substr(1, val.size() - 2);
                                    std::istringstream iss(inner);
                                    std::string tok;
                                    while (std::getline(iss, tok, ',')) {
                                        try { op.wrap.targetPids.push_back(std::stoi(trim(tok))); } catch (...) {}
                                    }
                                } else {
                                    try { op.wrap.targetPids.push_back(std::stoi(val)); } catch (...) {}
                                }
                            } else if (key == "axis") {
                                op.wrap.axis = val;
                            } else if (key == "tension") {
                                try { op.wrap.tension = std::stod(val); } catch (...) {}
                            } else if (key == "center") {
                                if (!val.empty() && val.front() == '[') {
                                    std::string inner = val.substr(1, val.size() - 2);
                                    size_t comma = inner.find(',');
                                    if (comma != std::string::npos) {
                                        try {
                                            op.wrap.centerA = std::stod(trim(inner.substr(0, comma)));
                                            op.wrap.centerB = std::stod(trim(inner.substr(comma + 1)));
                                            op.wrap.autoCenter = false;
                                        } catch (...) {}
                                    }
                                }
                            }
                        } else if (op.type == AssemblyOperation::UPDATE) {
                            if (key == "dynain") {
                                op.update.dynainFile = val;
                            }
                        } else if (op.type == AssemblyOperation::GENERATE) {
                            auto& g = op.generate;
                            try {
                                if      (key == "shape")      g.shape     = val;
                                else if (key == "lx")         g.lx        = std::stod(val);
                                else if (key == "ly")         g.ly        = std::stod(val);
                                else if (key == "lz")         g.lz        = std::stod(val);
                                else if (key == "nx")         g.nx        = std::stoi(val);
                                else if (key == "ny")         g.ny        = std::stoi(val);
                                else if (key == "nz")         g.nz        = std::stoi(val);
                                else if (key == "rho")        g.rho       = std::stod(val);
                                else if (key == "E")          g.E         = std::stod(val);
                                else if (key == "nu")         g.nu        = std::stod(val);
                                else if (key == "mid")        g.mid       = std::stoi(val);
                                else if (key == "secid")      g.secid     = std::stoi(val);
                                else if (key == "pid")        g.pid       = std::stoi(val);
                                else if (key == "part_title") g.partTitle = val;
                            } catch (...) {}
                        } else if (op.type == AssemblyOperation::CONTROL) {
                            auto& ct = op.control;
                            try {
                                if      (key == "endtime") { ct.endtime = std::stod(val); }
                                else if (key == "tssfac")  { ct.tssfac  = std::stod(val); }
                                else if (key == "dt2ms")   { ct.dt2ms   = std::stod(val); ct.setDt2ms = true; }
                                else if (key == "hgen")    { ct.hgen    = std::stoi(val); }
                                else if (key == "rwen")    { ct.rwen    = std::stoi(val); }
                                else if (key == "slnten")  { ct.slnten  = std::stoi(val); }
                                else if (key == "rylen")   { ct.rylen   = std::stoi(val); }
                                else if (key == "ihq")     { ct.ihq     = std::stoi(val); }
                                else if (key == "qh")      { ct.qh      = std::stod(val); }
                                else if (key == "q1")      { ct.q1      = std::stod(val); }
                                else if (key == "q2")      { ct.q2      = std::stod(val); }
                                else if (key == "bulk_type") { ct.bulkType = std::stoi(val); }
                                else if (key == "energy") {
                                    // shorthand: energy: true → hgen=rwen=2, slnten=rylen=1
                                    if (val == "true" || val == "yes" || val == "1") {
                                        ct.hgen = 2; ct.rwen = 2; ct.slnten = 1; ct.rylen = 1;
                                    }
                                }
                            } catch (...) {}
                        } else if (op.type == AssemblyOperation::DATABASE) {
                            if (key == "preset") {
                                op.database.preset = val;
                            } else if (key == "dt") {
                                try { op.database.dt = std::stod(val); } catch (...) {}
                            } else if (key == "dt_plot") {
                                try { op.database.dtPlot = std::stod(val); } catch (...) {}
                            } else if (key == "dt_thdt") {
                                try { op.database.dtThdt = std::stod(val); } catch (...) {}
                            } else if (key == "extent") {
                                op.database.extentBinary = (val == "true" || val == "yes" || val == "1");
                            } else if (key == "neiph") {
                                try { op.database.neiph = std::stoi(val); } catch (...) {}
                            }
                        } else if (op.type == AssemblyOperation::FILLET) {
                            if (key == "target_pid") {
                                try { op.fillet.targetPid = std::stoi(val); } catch (...) {}
                            } else if (key == "radius") {
                                try { op.fillet.radius = std::stod(val); } catch (...) {}
                            } else if (key == "face") {
                                // Single face: face: z_max
                                op.fillet.faces.clear();
                                op.fillet.faces.push_back(val);
                            } else if (key == "faces") {
                                // Inline list: faces: [z_max, z_min]
                                op.fillet.faces.clear();
                                std::string list = val;
                                // Strip brackets
                                if (!list.empty() && list.front() == '[') list = list.substr(1);
                                if (!list.empty() && list.back()  == ']') list.pop_back();
                                std::istringstream ss(list);
                                std::string tok;
                                while (std::getline(ss, tok, ',')) {
                                    // trim
                                    size_t a = tok.find_first_not_of(" \t");
                                    size_t b = tok.find_last_not_of(" \t");
                                    if (a != std::string::npos)
                                        op.fillet.faces.push_back(tok.substr(a, b - a + 1));
                                }
                            } else if (key == "angle_min") {
                                try { op.fillet.angleMin = std::stod(val); } catch (...) {}
                            } else if (key == "angle_max") {
                                try { op.fillet.angleMax = std::stod(val); } catch (...) {}
                            } else if (key == "fix_jacobian") {
                                op.fillet.fixJacobian = (val == "true" || val == "1" || val == "yes");
                            } else if (key == "smooth_iter") {
                                try { op.fillet.smoothIter = std::stoi(val); } catch (...) {}
                            }
                        } else if (op.type == AssemblyOperation::MATDB) {
                            if (key == "database") {
                                op.matdb.databasePath = val;
                            } else if (key == "mat_type") {
                                op.matdb.globalMatType = val;
                            } else if (key == "thermal") {
                                op.matdb.globalThermal = (val == "true" || val == "yes" || val == "1");
                            } else if (key == "materials") {
                                inMatdbRulesList = true;
                                matdbRulesKeyIndent = indent;
                            }
                        } else if (op.type == AssemblyOperation::CNRB2SOLID) {
                            if      (key == "E")                   op.cnrb2solid.E               = std::stod(val);
                            else if (key == "PR" || key == "pr")   op.cnrb2solid.PR              = std::stod(val);
                            else if (key == "RHO" || key == "rho") op.cnrb2solid.RHO             = std::stod(val);
                            else if (key == "radius_scale")        op.cnrb2solid.radiusScale     = std::stod(val);
                            else if (key == "num_circum_nodes")    op.cnrb2solid.numCircumNodes  = std::stoi(val);
                            else if (key == "inner_radius_ratio")  op.cnrb2solid.innerRadiusRatio = std::stod(val);
                            else if (key == "axis_direction")      op.cnrb2solid.axisDirection   = val;
                            else if (key == "z_tolerance")         op.cnrb2solid.zTolerance      = std::stod(val);
                            else if (key == "r_tolerance")         op.cnrb2solid.rTolerance      = std::stod(val);
                            else if (key == "head_offset_r")       op.cnrb2solid.headOffsetR     = std::stod(val);
                            else if (key == "head_thickness")      op.cnrb2solid.headThickness   = std::stod(val);
                            else if (key == "head_position")       op.cnrb2solid.headPosition    = val;
                        } else if (op.type == AssemblyOperation::HFDAMP) {
                            if      (key == "dt_target")   op.hfdamp.dtTarget   = std::stod(val);
                            else if (key == "cdamp")       op.hfdamp.cdamp      = std::stod(val);
                            else if (key == "fhigh_ratio") op.hfdamp.fhighRatio = std::stod(val);
                            else if (key == "mode")        op.hfdamp.mode       = val;
                            else if (key == "tssfac")      op.hfdamp.tssfac     = std::stod(val);
                        } else if (op.type == AssemblyOperation::SPLIT) {
                            if      (key == "direction")   op.split.direction  = val;
                            else if (key == "divisions")   op.split.divisions  = std::stoi(val);
                            else if (key == "target_pid") {
                                try { op.split.targetPid = std::stoi(val); } catch (...) {}
                            }
                        } else if (op.type == AssemblyOperation::BATTERY) {
                            if      (key == "config")         op.battery.configFile   = val;
                            else if (key == "output")         op.battery.output        = val;
                            else if (key == "node_id_offset") op.battery.nodeIdOffset  = std::stoi(val);
                            else if (key == "elem_id_offset") op.battery.elemIdOffset  = std::stoi(val);
                            else if (key == "use_include")    op.battery.useInclude    = (val == "true" || val == "1");
                        }
                    } catch (...) {}
                }

                // Material cards list items: "        - |"
                if (inMaterialCardsList && indent > materialCardsKeyIndent &&
                    trimmed.size() >= 1 && trimmed[0] == '-' && trimmed.size() >= 2) {
                    std::string afterDash = trim(trimmed.substr(1));
                    if (afterDash == "|" || afterDash.empty()) {
                        // Start new material card
                        if (!config.operations.empty() &&
                            config.operations.back().type == AssemblyOperation::OFFSET) {
                            config.operations.back().offset.materialCards.push_back("");
                            readingMaterialCardsItem = true;
                            materialCardTarget = MaterialCardTarget::OFFSET_MULTI;
                            materialCardBaseIndent = indent + 2;
                            // Look ahead for actual content indentation
                            for (size_t ahead = li + 1; ahead < lines.size(); ++ahead) {
                                std::string aheadTrimmed = trim(lines[ahead]);
                                if (!aheadTrimmed.empty() && aheadTrimmed[0] != '#') {
                                    materialCardBaseIndent = countIndent(lines[ahead]);
                                    break;
                                }
                            }
                        }
                    }
                }

                // Exit material_cards list when indent decreases
                if (inMaterialCardsList && indent < materialCardsKeyIndent) {
                    inMaterialCardsList = false;
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
    if (config.baseModel.empty()) {
        // Allowed if first operation is 'generate'
        bool hasGenerate = !config.operations.empty() &&
                           config.operations[0].type == AssemblyOperation::GENERATE;
        if (!hasGenerate) {
            throw std::runtime_error("base_model not specified in assembly config");
        }
    }
    if (config.output.empty()) {
        throw std::runtime_error("output not specified in assembly config");
    }
    if (config.operations.empty()) {
        throw std::runtime_error("No operations defined in assembly config");
    }

    for (size_t i = 0; i < config.operations.size(); ++i) {
        const auto& op = config.operations[i];
        if (op.type == AssemblyOperation::REPLACE) {
            if (op.replace.targetPid <= 0)
                throw std::runtime_error("Operation " + std::to_string(i+1) + ": missing target_pid");
            if (op.replace.detailFlat.empty())
                throw std::runtime_error("Operation " + std::to_string(i+1) + ": missing detail_flat");
            if (op.replace.shellBent.empty())
                throw std::runtime_error("Operation " + std::to_string(i+1) + ": missing shell_bent");
        } else if (op.type == AssemblyOperation::SQUEEZE) {
            if (op.squeeze.targetPid <= 0)
                throw std::runtime_error("Operation " + std::to_string(i+1) + ": missing target_pid");
        } else if (op.type == AssemblyOperation::RESTACK) {
            if (op.restack.targetPid <= 0)
                throw std::runtime_error("Operation " + std::to_string(i+1) + ": missing target_pid");
            if (op.restack.layers.empty())
                throw std::runtime_error("Operation " + std::to_string(i+1) + ": no layers defined for restack");
            for (size_t j = 0; j < op.restack.layers.size(); ++j) {
                if (op.restack.layers[j].thickness <= 0)
                    throw std::runtime_error("Operation " + std::to_string(i+1) +
                        ": layer " + std::to_string(j+1) + " has invalid thickness");
                if (op.restack.layers[j].materialCard.empty())
                    throw std::runtime_error("Operation " + std::to_string(i+1) +
                        ": layer " + std::to_string(j+1) + " has no material_card");
            }
        } else if (op.type == AssemblyOperation::BEND) {
            if (op.bend.targetPid <= 0 && op.bend.targetPid != 0 && op.bend.targetPids.empty())
                throw std::runtime_error("Operation " + std::to_string(i+1) + ": missing target_pid for bend");
            if (op.bend.plane != "xy" && op.bend.plane != "yz" && op.bend.plane != "zx")
                throw std::runtime_error("Operation " + std::to_string(i+1) + ": invalid plane '" +
                    op.bend.plane + "' (must be xy, yz, or zx)");
            if (op.bend.mode != "deform" && op.bend.mode != "stress")
                throw std::runtime_error("Operation " + std::to_string(i+1) + ": invalid mode '" +
                    op.bend.mode + "' (must be deform or stress)");
            if (op.bend.source != "dat" && op.bend.source != "dat_pair" && op.bend.source != "formula")
                throw std::runtime_error("Operation " + std::to_string(i+1) + ": invalid source '" +
                    op.bend.source + "' (must be dat, dat_pair, or formula)");
            if (op.bend.source == "dat" && op.bend.datFile.empty())
                throw std::runtime_error("Operation " + std::to_string(i+1) + ": dat source requires dat_file");
            if (op.bend.source == "dat_pair") {
                if (op.bend.datTop.empty() || op.bend.datBottom.empty())
                    throw std::runtime_error("Operation " + std::to_string(i+1) + ": dat_pair source requires dat_top and dat_bottom");
            }
            if (op.bend.source == "formula" && op.bend.expression.empty())
                throw std::runtime_error("Operation " + std::to_string(i+1) + ": formula source requires expression");
        } else if (op.type == AssemblyOperation::IGA) {
            if (op.iga.targets.empty())
                throw std::runtime_error("Operation " + std::to_string(i+1) + ": no targets defined for iga");
            for (size_t j = 0; j < op.iga.targets.size(); ++j) {
                if (op.iga.targets[j].targetPid <= 0)
                    throw std::runtime_error("Operation " + std::to_string(i+1) +
                        ": iga target " + std::to_string(j+1) + " missing target_pid");
                if (op.iga.targets[j].elementSize <= 0)
                    throw std::runtime_error("Operation " + std::to_string(i+1) +
                        ": iga target " + std::to_string(j+1) + " element_size must be positive");
            }
        } else if (op.type == AssemblyOperation::WARPAGE) {
            std::string pfx = "Operation " + std::to_string(i+1) + " (warpage): ";
            if (op.warpage.targetPid <= 0)
                throw std::runtime_error(pfx + "missing target_pid");
            if (op.warpage.datFile.empty())
                throw std::runtime_error(pfx + "missing dat_file");
            if (op.warpage.plane != "xy" && op.warpage.plane != "yz" && op.warpage.plane != "zx")
                throw std::runtime_error(pfx + "invalid plane '" + op.warpage.plane + "'");
            if (op.warpage.unit != "um" && op.warpage.unit != "mm" && op.warpage.unit != "m")
                throw std::runtime_error(pfx + "invalid unit '" + op.warpage.unit + "'");
            if (op.warpage.morphFactor <= 0.0)
                throw std::runtime_error(pfx + "morph_factor must be positive");
            if (op.warpage.mode != "prestress" && op.warpage.mode != "deform")
                throw std::runtime_error(pfx + "invalid mode '" + op.warpage.mode + "'");
            if (op.warpage.outsideBehavior != "zero" &&
                op.warpage.outsideBehavior != "clamp" &&
                op.warpage.outsideBehavior != "extrapolate")
                throw std::runtime_error(pfx + "invalid outside_behavior '" + op.warpage.outsideBehavior + "'");
            if (op.warpage.hasDataBbox) {
                if (op.warpage.dataBboxXmax <= op.warpage.dataBboxXmin)
                    throw std::runtime_error(pfx + "data_bbox: x_max must be > x_min");
                if (op.warpage.dataBboxYmax <= op.warpage.dataBboxYmin)
                    throw std::runtime_error(pfx + "data_bbox: y_max must be > y_min");
            }
        } else if (op.type == AssemblyOperation::OFFSET) {
            std::string pfx = "Operation " + std::to_string(i+1) + " (offset): ";

            if (op.offset.sourcePid <= 0)
                throw std::runtime_error(pfx + "source_pid required");

            // Prestress mode validation
            bool isDualOffset = (op.offset.prestressMode == "dual_offset");
            if (isDualOffset) {
                // Dual offset mode: inner/outer required
                if (op.offset.innerOffset >= 0.0)
                    throw std::runtime_error(pfx + "inner_offset must be < 0 (inward)");
                if (op.offset.outerOffset <= 0.0)
                    throw std::runtime_error(pfx + "outer_offset must be > 0 (outward)");
                if (op.offset.innerOffset >= op.offset.outerOffset)
                    throw std::runtime_error(pfx + "inner_offset must be < outer_offset");
            } else {
                // Normal mode: thickness required
                if (op.offset.thickness <= 0.0)
                    throw std::runtime_error(pfx + "thickness must be > 0");
            }

            if (op.offset.numLayers < 1)
                throw std::runtime_error(pfx + "num_layers must be >= 1");

            std::string etype = op.offset.elementType;
            if (etype != "solid" && etype != "tshell" && etype != "shell")
                throw std::runtime_error(pfx + "element_type must be solid|tshell|shell");

            // Connection mode validation
            std::string cmode = op.offset.connectionMode;
            if (cmode != "tied" && cmode != "czm" && cmode != "contact")
                throw std::runtime_error(pfx + "connection_mode must be tied|czm|contact");

            // Material card validation
            if (!op.offset.materialCard.empty()) {
                MaterialCardValidator validator;
                auto result = validator.validate(op.offset.materialCard, true);

                // Print warnings
                for (const auto& warning : result.warnings) {
                    std::cout << "[WARNING] " << pfx << "material_card: " << warning << "\n";
                }

                // Errors are fatal
                if (!result.errors.empty()) {
                    std::string errMsg = pfx + "material_card validation failed:\n";
                    for (const auto& error : result.errors) {
                        errMsg += "  - " + error + "\n";
                    }
                    throw std::runtime_error(errMsg);
                }
            }

            // CZM material card validation
            if (cmode == "czm" && !op.offset.czmMaterialCard.empty()) {
                MaterialCardValidator validator;
                auto result = validator.validate(op.offset.czmMaterialCard, true);

                // Print warnings
                for (const auto& warning : result.warnings) {
                    std::cout << "[WARNING] " << pfx << "czm_material_card: " << warning << "\n";
                }

                // Errors are fatal
                if (!result.errors.empty()) {
                    std::string errMsg = pfx + "czm_material_card validation failed:\n";
                    for (const auto& error : result.errors) {
                        errMsg += "  - " + error + "\n";
                    }
                    throw std::runtime_error(errMsg);
                }
            }

        } else if (op.type == AssemblyOperation::INDENT) {
            std::string pfx = "Operation " + std::to_string(i+1) + " (indent): ";
            if (op.indent.targetPid <= 0)
                throw std::runtime_error(pfx + "missing target_pid");
            if (op.indent.plane != "xy" && op.indent.plane != "yz" && op.indent.plane != "zx")
                throw std::runtime_error(pfx + "invalid plane '" + op.indent.plane + "'");
            std::string dir = op.indent.direction;
            if (dir != "+z" && dir != "-z" && dir != "+x" && dir != "-x" &&
                dir != "+y" && dir != "-y")
                throw std::runtime_error(pfx + "invalid direction '" + dir + "'");
            if (op.indent.depth == 0.0)
                throw std::runtime_error(pfx + "depth must be non-zero (positive=indent, negative=emboss)");
            if (op.indent.r1 <= 0.0 || op.indent.r2 <= 0.0)
                throw std::runtime_error(pfx + "r1 and r2 must be positive");
            if (op.indent.shapeType != "polygon" && op.indent.shapeType != "spline")
                throw std::runtime_error(pfx + "invalid shape type '" + op.indent.shapeType + "'");
            if (op.indent.points.size() < 3)
                throw std::runtime_error(pfx + "shape requires at least 3 points");
        }
    }

    return config;
}

} // namespace KooRemapper
