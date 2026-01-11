#include "cli/ConsoleOutput.h"
#include "core/Platform.h"
#include <iomanip>
#include <sstream>

namespace KooRemapper {

ConsoleOutput::ConsoleOutput()
    : colorsEnabled_(true)
{
    // Try to enable ANSI colors
    colorsEnabled_ = Platform::enableAnsiColors();
}

std::string ConsoleOutput::colorCode(Color color) const {
    if (!colorsEnabled_) return "";

    switch (color) {
        case Color::RED:           return "\033[31m";
        case Color::GREEN:         return "\033[32m";
        case Color::YELLOW:        return "\033[33m";
        case Color::BLUE:          return "\033[34m";
        case Color::MAGENTA:       return "\033[35m";
        case Color::CYAN:          return "\033[36m";
        case Color::WHITE:         return "\033[37m";
        case Color::BRIGHT_RED:    return "\033[91m";
        case Color::BRIGHT_GREEN:  return "\033[92m";
        case Color::BRIGHT_YELLOW: return "\033[93m";
        case Color::BRIGHT_BLUE:   return "\033[94m";
        case Color::BRIGHT_CYAN:   return "\033[96m";
        default:                   return "\033[0m";
    }
}

std::string ConsoleOutput::resetCode() const {
    return colorsEnabled_ ? "\033[0m" : "";
}

void ConsoleOutput::print(const std::string& text, Color color) const {
    std::cout << colorCode(color) << text << resetCode();
}

void ConsoleOutput::println(const std::string& text, Color color) const {
    print(text, color);
    std::cout << "\n";
}

void ConsoleOutput::info(const std::string& message) const {
    print("[INFO] ", Color::CYAN);
    println(message);
}

void ConsoleOutput::success(const std::string& message) const {
    print("[OK] ", Color::BRIGHT_GREEN);
    println(message);
}

void ConsoleOutput::warning(const std::string& message) const {
    print("[WARN] ", Color::BRIGHT_YELLOW);
    println(message);
}

void ConsoleOutput::error(const std::string& message) const {
    print("[ERROR] ", Color::BRIGHT_RED);
    println(message);
}

void ConsoleOutput::progressBar(int percent, int width) const {
    percent = std::max(0, std::min(100, percent));

    int filled = (width * percent) / 100;
    int empty = width - filled;

    std::cout << "\r[";

    if (colorsEnabled_) {
        std::cout << colorCode(Color::BRIGHT_GREEN);
    }

    for (int i = 0; i < filled; ++i) {
        std::cout << "=";
    }

    if (filled < width) {
        std::cout << ">";
        for (int i = 1; i < empty; ++i) {
            std::cout << " ";
        }
    }

    if (colorsEnabled_) {
        std::cout << resetCode();
    }

    std::cout << "] " << std::setw(3) << percent << "%" << std::flush;
}

void ConsoleOutput::separator(char ch, int width) const {
    println(std::string(width, ch), Color::DEFAULT);
}

void ConsoleOutput::header(const std::string& text) const {
    separator('=');
    println(text, Color::BRIGHT_BLUE);
    separator('=');
}

void ConsoleOutput::keyValue(const std::string& key, const std::string& value,
                             int keyWidth) const {
    std::cout << std::left << std::setw(keyWidth) << (key + ":") << value << "\n";
}

void ConsoleOutput::clearLine() const {
    std::cout << "\r" << std::string(80, ' ') << "\r" << std::flush;
}

} // namespace KooRemapper
