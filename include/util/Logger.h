#pragma once

#include <string>
#include <fstream>
#include <memory>
#include <mutex>

namespace KooRemapper {

/**
 * Log levels
 */
enum class LogLevel {
    DEBUG,
    INFO,
    WARNING,
    ERROR
};

/**
 * Simple thread-safe logger
 */
class Logger {
public:
    static Logger& instance();

    /**
     * Set log level
     */
    void setLevel(LogLevel level) { level_ = level; }
    LogLevel getLevel() const { return level_; }

    /**
     * Enable/disable console output
     */
    void setConsoleEnabled(bool enabled) { consoleEnabled_ = enabled; }

    /**
     * Enable/disable file output
     */
    bool setFileOutput(const std::string& filename);
    void closeFileOutput();

    /**
     * Log messages
     */
    void debug(const std::string& message);
    void info(const std::string& message);
    void warning(const std::string& message);
    void error(const std::string& message);

    /**
     * Generic log
     */
    void log(LogLevel level, const std::string& message);

private:
    Logger();
    ~Logger();
    Logger(const Logger&) = delete;
    Logger& operator=(const Logger&) = delete;

    LogLevel level_;
    bool consoleEnabled_;
    std::unique_ptr<std::ofstream> fileStream_;
    std::mutex mutex_;

    std::string levelToString(LogLevel level) const;
    std::string getTimestamp() const;
};

// Convenience macros
#define LOG_DEBUG(msg) Logger::instance().debug(msg)
#define LOG_INFO(msg) Logger::instance().info(msg)
#define LOG_WARNING(msg) Logger::instance().warning(msg)
#define LOG_ERROR(msg) Logger::instance().error(msg)

} // namespace KooRemapper
