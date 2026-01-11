#pragma once

#include <chrono>
#include <string>

namespace KooRemapper {

/**
 * Simple timer for measuring execution time
 */
class Timer {
public:
    Timer();

    /**
     * Start/restart the timer
     */
    void start();

    /**
     * Stop the timer
     */
    void stop();

    /**
     * Get elapsed time in milliseconds
     */
    double elapsedMs() const;

    /**
     * Get elapsed time in seconds
     */
    double elapsedSec() const;

    /**
     * Get formatted elapsed time string
     */
    std::string elapsedString() const;

    /**
     * Check if timer is running
     */
    bool isRunning() const { return running_; }

private:
    using Clock = std::chrono::high_resolution_clock;
    using TimePoint = std::chrono::time_point<Clock>;

    TimePoint startTime_;
    TimePoint endTime_;
    bool running_;
};

/**
 * RAII-style scoped timer that logs on destruction
 */
class ScopedTimer {
public:
    explicit ScopedTimer(const std::string& name);
    ~ScopedTimer();

private:
    std::string name_;
    Timer timer_;
};

} // namespace KooRemapper
