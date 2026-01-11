#include "cli/ArgumentParser.h"
#include <iostream>
#include <iomanip>
#include <algorithm>
#include <sstream>

namespace KooRemapper {

ArgumentParser::ArgumentParser(const std::string& programName, const std::string& description)
    : programName_(programName), description_(description)
{}

void ArgumentParser::addPositional(const std::string& name, const std::string& help,
                                   bool required) {
    PositionalArg arg;
    arg.name = name;
    arg.help = help;
    arg.required = required;
    positionals_.push_back(arg);
}

void ArgumentParser::addOption(const std::string& shortFlag, const std::string& longFlag,
                               const std::string& help, const std::string& defaultValue,
                               bool hasValue) {
    Option opt;
    opt.shortFlag = shortFlag;
    opt.longFlag = longFlag;
    opt.help = help;
    opt.defaultValue = defaultValue;
    opt.hasValue = hasValue;
    opt.isFlag = false;
    opt.value = defaultValue;
    opt.wasSet = false;

    std::string key = normalizeFlag(longFlag.empty() ? shortFlag : longFlag);
    options_[key] = opt;

    if (!shortFlag.empty()) {
        flagMap_[normalizeFlag(shortFlag)] = key;
    }
    if (!longFlag.empty()) {
        flagMap_[normalizeFlag(longFlag)] = key;
    }
}

void ArgumentParser::addFlag(const std::string& shortFlag, const std::string& longFlag,
                             const std::string& help) {
    Option opt;
    opt.shortFlag = shortFlag;
    opt.longFlag = longFlag;
    opt.help = help;
    opt.defaultValue = "false";
    opt.hasValue = false;
    opt.isFlag = true;
    opt.value = "false";
    opt.wasSet = false;

    std::string key = normalizeFlag(longFlag.empty() ? shortFlag : longFlag);
    options_[key] = opt;

    if (!shortFlag.empty()) {
        flagMap_[normalizeFlag(shortFlag)] = key;
    }
    if (!longFlag.empty()) {
        flagMap_[normalizeFlag(longFlag)] = key;
    }
}

std::string ArgumentParser::normalizeFlag(const std::string& flag) const {
    std::string result = flag;
    // Remove leading dashes
    while (!result.empty() && result[0] == '-') {
        result.erase(0, 1);
    }
    return result;
}

bool ArgumentParser::parse(int argc, char* argv[]) {
    errorMessage_.clear();

    std::vector<std::string> args;
    for (int i = 1; i < argc; ++i) {
        args.push_back(argv[i]);
    }

    size_t positionalIndex = 0;

    for (size_t i = 0; i < args.size(); ++i) {
        const std::string& arg = args[i];

        if (arg.empty()) continue;

        if (arg[0] == '-') {
            // Option or flag
            std::string flagName = normalizeFlag(arg);

            // Check for --flag=value syntax
            std::string value;
            size_t eqPos = flagName.find('=');
            if (eqPos != std::string::npos) {
                value = flagName.substr(eqPos + 1);
                flagName = flagName.substr(0, eqPos);
            }

            // Find the option
            auto mapIt = flagMap_.find(flagName);
            if (mapIt == flagMap_.end()) {
                errorMessage_ = "Unknown option: " + arg;
                return false;
            }

            std::string optKey = mapIt->second;
            auto& opt = options_[optKey];

            if (opt.isFlag) {
                opt.value = "true";
                opt.wasSet = true;
            } else if (opt.hasValue) {
                if (!value.empty()) {
                    opt.value = value;
                } else if (i + 1 < args.size() && args[i + 1][0] != '-') {
                    opt.value = args[++i];
                } else {
                    errorMessage_ = "Option " + arg + " requires a value";
                    return false;
                }
                opt.wasSet = true;
            }
        } else {
            // Positional argument
            if (positionalIndex < positionals_.size()) {
                positionals_[positionalIndex].value = arg;
                ++positionalIndex;
            } else {
                errorMessage_ = "Unexpected argument: " + arg;
                return false;
            }
        }
    }

    // Check required positionals
    for (const auto& pos : positionals_) {
        if (pos.required && pos.value.empty()) {
            errorMessage_ = "Missing required argument: " + pos.name;
            return false;
        }
    }

    return true;
}

std::string ArgumentParser::getPositional(const std::string& name) const {
    for (const auto& pos : positionals_) {
        if (pos.name == name) {
            return pos.value;
        }
    }
    return "";
}

std::string ArgumentParser::getOption(const std::string& name) const {
    std::string key = normalizeFlag(name);

    // Check direct key
    auto it = options_.find(key);
    if (it != options_.end()) {
        return it->second.value;
    }

    // Check via flag map
    auto mapIt = flagMap_.find(key);
    if (mapIt != flagMap_.end()) {
        auto optIt = options_.find(mapIt->second);
        if (optIt != options_.end()) {
            return optIt->second.value;
        }
    }

    return "";
}

bool ArgumentParser::hasFlag(const std::string& name) const {
    return getOption(name) == "true";
}

bool ArgumentParser::hasOption(const std::string& name) const {
    std::string key = normalizeFlag(name);

    auto mapIt = flagMap_.find(key);
    if (mapIt != flagMap_.end()) {
        auto optIt = options_.find(mapIt->second);
        if (optIt != options_.end()) {
            return optIt->second.wasSet;
        }
    }

    auto it = options_.find(key);
    if (it != options_.end()) {
        return it->second.wasSet;
    }

    return false;
}

std::optional<int> ArgumentParser::getInt(const std::string& name) const {
    std::string val = getOption(name);
    if (val.empty()) return std::nullopt;

    try {
        return std::stoi(val);
    } catch (...) {
        return std::nullopt;
    }
}

std::optional<double> ArgumentParser::getDouble(const std::string& name) const {
    std::string val = getOption(name);
    if (val.empty()) return std::nullopt;

    try {
        return std::stod(val);
    } catch (...) {
        return std::nullopt;
    }
}

void ArgumentParser::printHelp() const {
    std::cout << description_ << "\n\n";
    std::cout << "Usage: " << programName_;

    // Print options placeholder
    if (!options_.empty()) {
        std::cout << " [OPTIONS]";
    }

    // Print positional arguments
    for (const auto& pos : positionals_) {
        if (pos.required) {
            std::cout << " <" << pos.name << ">";
        } else {
            std::cout << " [" << pos.name << "]";
        }
    }
    std::cout << "\n\n";

    // Print positional argument descriptions
    if (!positionals_.empty()) {
        std::cout << "Arguments:\n";
        for (const auto& pos : positionals_) {
            std::cout << "  " << std::left << std::setw(20) << pos.name
                      << pos.help << "\n";
        }
        std::cout << "\n";
    }

    // Print options
    if (!options_.empty()) {
        std::cout << "Options:\n";

        // Collect unique options (avoid duplicates from short/long mapping)
        std::vector<const Option*> uniqueOptions;
        for (const auto& pair : options_) {
            bool found = false;
            for (const auto* opt : uniqueOptions) {
                if (opt->longFlag == pair.second.longFlag &&
                    opt->shortFlag == pair.second.shortFlag) {
                    found = true;
                    break;
                }
            }
            if (!found) {
                uniqueOptions.push_back(&pair.second);
            }
        }

        for (const auto* opt : uniqueOptions) {
            std::string flags;
            if (!opt->shortFlag.empty()) {
                flags += "-" + opt->shortFlag;
            }
            if (!opt->longFlag.empty()) {
                if (!flags.empty()) flags += ", ";
                flags += "--" + opt->longFlag;
            }
            if (opt->hasValue && !opt->isFlag) {
                flags += " <value>";
            }

            std::cout << "  " << std::left << std::setw(30) << flags
                      << opt->help;

            if (!opt->defaultValue.empty() && !opt->isFlag) {
                std::cout << " (default: " << opt->defaultValue << ")";
            }
            std::cout << "\n";
        }
    }
}

void ArgumentParser::printVersion(const std::string& version) const {
    std::cout << programName_ << " version " << version << "\n";
}

} // namespace KooRemapper
