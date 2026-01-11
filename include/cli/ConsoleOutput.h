#pragma once

#include <string>
#include <iostream>

namespace KooRemapper {

/**
 * Console output with optional ANSI colors
 */
class ConsoleOutput {
public:
    // Color codes
    enum class Color {
        DEFAULT,
        RED,
        GREEN,
        YELLOW,
        BLUE,
        MAGENTA,
        CYAN,
        WHITE,
        BRIGHT_RED,
        BRIGHT_GREEN,
        BRIGHT_YELLOW,
        BRIGHT_BLUE,
        BRIGHT_CYAN
    };

    ConsoleOutput();

    /**
     * Enable/disable colors
     */
    void setColorsEnabled(bool enabled) { colorsEnabled_ = enabled; }
    bool colorsEnabled() const { return colorsEnabled_; }

    /**
     * Print colored text
     */
    void print(const std::string& text, Color color = Color::DEFAULT) const;
    void println(const std::string& text, Color color = Color::DEFAULT) const;

    /**
     * Print status messages
     */
    void info(const std::string& message) const;
    void success(const std::string& message) const;
    void warning(const std::string& message) const;
    void error(const std::string& message) const;

    /**
     * Print a progress bar
     */
    void progressBar(int percent, int width = 40) const;

    /**
     * Print a separator line
     */
    void separator(char ch = '-', int width = 60) const;

    /**
     * Print a header
     */
    void header(const std::string& text) const;

    /**
     * Print key-value pair
     */
    void keyValue(const std::string& key, const std::string& value,
                  int keyWidth = 25) const;

    /**
     * Clear current line (for progress updates)
     */
    void clearLine() const;

private:
    bool colorsEnabled_;

    std::string colorCode(Color color) const;
    std::string resetCode() const;
};

} // namespace KooRemapper
