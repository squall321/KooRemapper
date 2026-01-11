#pragma once

#include <string>
#include <vector>
#include <map>
#include <optional>

namespace KooRemapper {

/**
 * Command-line argument parser
 */
class ArgumentParser {
public:
    ArgumentParser(const std::string& programName, const std::string& description);

    /**
     * Add a positional argument
     */
    void addPositional(const std::string& name, const std::string& help,
                       bool required = true);

    /**
     * Add an optional flag/option
     */
    void addOption(const std::string& shortFlag, const std::string& longFlag,
                   const std::string& help, const std::string& defaultValue = "",
                   bool hasValue = true);

    /**
     * Add a boolean flag (no value)
     */
    void addFlag(const std::string& shortFlag, const std::string& longFlag,
                 const std::string& help);

    /**
     * Parse command-line arguments
     * @return true if parsing succeeded
     */
    bool parse(int argc, char* argv[]);

    /**
     * Get positional argument value
     */
    std::string getPositional(const std::string& name) const;

    /**
     * Get option value
     */
    std::string getOption(const std::string& name) const;

    /**
     * Check if a flag is set
     */
    bool hasFlag(const std::string& name) const;

    /**
     * Check if an option was provided
     */
    bool hasOption(const std::string& name) const;

    /**
     * Get parsed integer option
     */
    std::optional<int> getInt(const std::string& name) const;

    /**
     * Get parsed double option
     */
    std::optional<double> getDouble(const std::string& name) const;

    /**
     * Get error message
     */
    const std::string& getError() const { return errorMessage_; }

    /**
     * Print help message
     */
    void printHelp() const;

    /**
     * Print version
     */
    void printVersion(const std::string& version) const;

private:
    struct PositionalArg {
        std::string name;
        std::string help;
        bool required;
        std::string value;
    };

    struct Option {
        std::string shortFlag;
        std::string longFlag;
        std::string help;
        std::string defaultValue;
        bool hasValue;
        bool isFlag;
        std::string value;
        bool wasSet;
    };

    std::string programName_;
    std::string description_;
    std::vector<PositionalArg> positionals_;
    std::map<std::string, Option> options_;
    std::map<std::string, std::string> flagMap_;  // short -> long mapping
    std::string errorMessage_;

    std::string normalizeFlag(const std::string& flag) const;
};

} // namespace KooRemapper
