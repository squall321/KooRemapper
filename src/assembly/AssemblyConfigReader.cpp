#include "assembly/AssemblyConfigReader.h"
#include <fstream>
#include <sstream>
#include <stdexcept>
#include <algorithm>

namespace KooRemapper {

std::string AssemblyConfigReader::trim(const std::string& str) {
    size_t start = 0;
    size_t end = str.length();
    while (start < end && std::isspace(str[start])) start++;
    while (end > start && std::isspace(str[end - 1])) end--;
    return str.substr(start, end - start);
}

static int countIndent(const std::string& line) {
    int n = 0;
    while (n < static_cast<int>(line.length()) && line[n] == ' ') n++;
    return n;
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
    bool readingMaterialCard = false;
    int materialCardBaseIndent = 0;
    bool inShapeSection = false;
    bool inPointsList = false;

    for (size_t li = 0; li < lines.size(); ++li) {
        const std::string& line = lines[li];
        std::string trimmed = trim(line);
        int indent = countIndent(line);

        // Multi-line material_card block reading
        if (readingMaterialCard) {
            if (trimmed.empty()) {
                // Empty line inside block → include as blank line
                if (!config.operations.empty() &&
                    config.operations.back().type == AssemblyOperation::RESTACK &&
                    !config.operations.back().restack.layers.empty()) {
                    config.operations.back().restack.layers.back().materialCard += "\n";
                }
                continue;
            }
            if (indent >= materialCardBaseIndent) {
                // Part of the multi-line block - strip the block indentation
                std::string content = line.substr(materialCardBaseIndent);
                // Trim trailing spaces
                size_t end = content.find_last_not_of(" \t\r");
                if (end != std::string::npos) content = content.substr(0, end + 1);

                if (!config.operations.empty() &&
                    config.operations.back().type == AssemblyOperation::RESTACK &&
                    !config.operations.back().restack.layers.empty()) {
                    auto& card = config.operations.back().restack.layers.back().materialCard;
                    if (!card.empty()) card += "\n";
                    card += content;
                }
                continue;
            }
            // Indentation decreased → end of block
            readingMaterialCard = false;
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
                        } else if (key == "material_card") {
                            if (val == "|") {
                                // Multi-line block: find indentation of first content line
                                readingMaterialCard = true;
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

            // --- Operation list item start: "  - type: replace" ---
            if (!inPointsList && trimmed[0] == '-' && trimmed.size() >= 2 && trimmed[1] == ' ') {
                inLayersList = false;
                inLayerItem = false;
                inTargetsList = false;
                inTargetItem = false;
                inShapeSection = false;
                inPointsList = false;

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
                        } else {
                            throw std::runtime_error("Unknown operation type: " + val);
                        }
                    }
                    config.operations.push_back(op);
                    inOperationItem = true;
                }
                continue;
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

            // --- Operation sub-keys ---
            if (inOperationItem && !config.operations.empty()) {
                size_t colonPos = trimmed.find(':');
                if (colonPos != std::string::npos) {
                    std::string key = trim(trimmed.substr(0, colonPos));
                    std::string val = trim(trimmed.substr(colonPos + 1));

                    auto& op = config.operations.back();
                    try {
                        if (key == "target_pid") {
                            int pid = std::stoi(val);
                            if (op.type == AssemblyOperation::REPLACE) {
                                op.replace.targetPid = pid;
                            } else if (op.type == AssemblyOperation::SQUEEZE) {
                                op.squeeze.targetPid = pid;
                            } else if (op.type == AssemblyOperation::RESTACK) {
                                op.restack.targetPid = pid;
                            } else if (op.type == AssemblyOperation::BEND) {
                                op.bend.targetPid = pid;
                            } else if (op.type == AssemblyOperation::INDENT) {
                                op.indent.targetPid = pid;
                            } else if (op.type == AssemblyOperation::FORMSTRAIN) {
                                op.formstrain.targetPid = pid;
                            } else if (op.type == AssemblyOperation::TET10_CONVERT) {
                                op.tet10.targetPid = pid;
                            } else if (op.type == AssemblyOperation::REFINE) {
                                op.refine.targetPid = pid;
                            } else if (op.type == AssemblyOperation::ELFORM) {
                                op.elform.targetPid = pid;
                            } else if (op.type == AssemblyOperation::DISCONNECT) {
                                op.disconnect.targetPid = pid;
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
                        }
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
    if (config.baseModel.empty()) {
        throw std::runtime_error("base_model not specified in assembly config");
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
            if (op.bend.targetPid <= 0)
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
