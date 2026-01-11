#include "util/Timer.h"
#include "util/Logger.h"
#include <sstream>
#include <iomanip>

namespace KooRemapper {

Timer::Timer()
    : running_(false)
{
    start();
}

void Timer::start() {
    startTime_ = Clock::now();
    running_ = true;
}

void Timer::stop() {
    if (running_) {
        endTime_ = Clock::now();
        running_ = false;
    }
}

double Timer::elapsedMs() const {
    TimePoint end = running_ ? Clock::now() : endTime_;
    auto duration = std::chrono::duration_cast<std::chrono::microseconds>(end - startTime_);
    return duration.count() / 1000.0;
}

double Timer::elapsedSec() const {
    return elapsedMs() / 1000.0;
}

std::string Timer::elapsedString() const {
    double ms = elapsedMs();
    std::stringstream ss;

    if (ms < 1000) {
        ss << std::fixed << std::setprecision(2) << ms << " ms";
    } else if (ms < 60000) {
        ss << std::fixed << std::setprecision(2) << (ms / 1000.0) << " s";
    } else {
        int minutes = static_cast<int>(ms / 60000);
        double seconds = (ms - minutes * 60000) / 1000.0;
        ss << minutes << " m " << std::fixed << std::setprecision(1) << seconds << " s";
    }

    return ss.str();
}

ScopedTimer::ScopedTimer(const std::string& name)
    : name_(name)
{
    timer_.start();
}

ScopedTimer::~ScopedTimer() {
    timer_.stop();
    LOG_INFO(name_ + " completed in " + timer_.elapsedString());
}

} // namespace KooRemapper
