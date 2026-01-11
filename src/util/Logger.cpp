#include "util/Logger.h"
#include <iostream>
#include <chrono>
#include <iomanip>
#include <sstream>

namespace KooRemapper {

Logger& Logger::instance() {
    static Logger instance;
    return instance;
}

Logger::Logger()
    : level_(LogLevel::INFO), consoleEnabled_(true)
{}

Logger::~Logger() {
    closeFileOutput();
}

bool Logger::setFileOutput(const std::string& filename) {
    std::lock_guard<std::mutex> lock(mutex_);

    closeFileOutput();

    fileStream_ = std::make_unique<std::ofstream>(filename);
    return fileStream_->is_open();
}

void Logger::closeFileOutput() {
    if (fileStream_) {
        fileStream_->close();
        fileStream_.reset();
    }
}

std::string Logger::levelToString(LogLevel level) const {
    switch (level) {
        case LogLevel::DEBUG:   return "DEBUG";
        case LogLevel::INFO:    return "INFO";
        case LogLevel::WARNING: return "WARN";
        case LogLevel::ERROR:   return "ERROR";
        default:                return "UNKNOWN";
    }
}

std::string Logger::getTimestamp() const {
    auto now = std::chrono::system_clock::now();
    auto time = std::chrono::system_clock::to_time_t(now);
    auto ms = std::chrono::duration_cast<std::chrono::milliseconds>(
        now.time_since_epoch()) % 1000;

    std::stringstream ss;
    ss << std::put_time(std::localtime(&time), "%Y-%m-%d %H:%M:%S");
    ss << '.' << std::setfill('0') << std::setw(3) << ms.count();

    return ss.str();
}

void Logger::log(LogLevel level, const std::string& message) {
    if (level < level_) return;

    std::lock_guard<std::mutex> lock(mutex_);

    std::string timestamp = getTimestamp();
    std::string levelStr = levelToString(level);
    std::string formatted = "[" + timestamp + "] [" + levelStr + "] " + message;

    if (consoleEnabled_) {
        std::ostream& out = (level >= LogLevel::WARNING) ? std::cerr : std::cout;
        out << formatted << "\n";
    }

    if (fileStream_ && fileStream_->is_open()) {
        *fileStream_ << formatted << "\n";
        fileStream_->flush();
    }
}

void Logger::debug(const std::string& message) {
    log(LogLevel::DEBUG, message);
}

void Logger::info(const std::string& message) {
    log(LogLevel::INFO, message);
}

void Logger::warning(const std::string& message) {
    log(LogLevel::WARNING, message);
}

void Logger::error(const std::string& message) {
    log(LogLevel::ERROR, message);
}

} // namespace KooRemapper
