#pragma once

#include <string>

// Platform-specific path separator
#ifdef PLATFORM_WINDOWS
    #define PATH_SEPARATOR '\\'
    #define PATH_SEPARATOR_STR "\\"
#else
    #define PATH_SEPARATOR '/'
    #define PATH_SEPARATOR_STR "/"
#endif

// Platform-specific line ending
#ifdef PLATFORM_WINDOWS
    #define LINE_ENDING "\r\n"
#else
    #define LINE_ENDING "\n"
#endif

namespace KooRemapper {
namespace Platform {

    /**
     * Get the path to the current executable
     */
    std::string getExecutablePath();

    /**
     * Normalize path separators for the current platform
     */
    std::string normalizePath(const std::string& path);

    /**
     * Check if a file exists
     */
    bool fileExists(const std::string& path);

    /**
     * Create a directory (including parent directories)
     */
    bool createDirectory(const std::string& path);

    /**
     * Normalize line endings to LF
     */
    std::string normalizeLineEndings(const std::string& content);

    /**
     * Enable ANSI color support (Windows-specific)
     * Returns true if ANSI colors are supported
     */
    bool enableAnsiColors();

    /**
     * Get the current working directory
     */
    std::string getCurrentDirectory();

    /**
     * Extract filename from path
     */
    std::string getFilename(const std::string& path);

    /**
     * Extract directory from path
     */
    std::string getDirectory(const std::string& path);

} // namespace Platform
} // namespace KooRemapper
