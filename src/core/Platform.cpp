#include "core/Platform.h"
#include <algorithm>
#include <fstream>

#ifdef PLATFORM_WINDOWS
    #include <windows.h>
    #include <direct.h>
    #define getcwd _getcwd
#else
    #include <unistd.h>
    #include <sys/stat.h>
    #include <limits.h>
    #ifdef PLATFORM_MACOS
        #include <mach-o/dyld.h>
    #endif
#endif

namespace KooRemapper {
namespace Platform {

std::string getExecutablePath() {
#ifdef PLATFORM_WINDOWS
    char buffer[MAX_PATH];
    GetModuleFileNameA(NULL, buffer, MAX_PATH);
    return std::string(buffer);
#elif defined(PLATFORM_LINUX)
    char buffer[PATH_MAX];
    ssize_t len = readlink("/proc/self/exe", buffer, sizeof(buffer) - 1);
    if (len != -1) {
        buffer[len] = '\0';
        return std::string(buffer);
    }
    return "";
#elif defined(PLATFORM_MACOS)
    char buffer[PATH_MAX];
    uint32_t size = sizeof(buffer);
    if (_NSGetExecutablePath(buffer, &size) == 0) {
        return std::string(buffer);
    }
    return "";
#else
    return "";
#endif
}

std::string normalizePath(const std::string& path) {
    std::string result = path;
#ifdef PLATFORM_WINDOWS
    std::replace(result.begin(), result.end(), '/', '\\');
#else
    std::replace(result.begin(), result.end(), '\\', '/');
#endif
    return result;
}

bool fileExists(const std::string& path) {
    std::ifstream file(path);
    return file.good();
}

bool createDirectory(const std::string& path) {
#ifdef PLATFORM_WINDOWS
    return _mkdir(path.c_str()) == 0 || errno == EEXIST;
#else
    return mkdir(path.c_str(), 0755) == 0 || errno == EEXIST;
#endif
}

std::string normalizeLineEndings(const std::string& content) {
    std::string result;
    result.reserve(content.size());

    for (size_t i = 0; i < content.size(); ++i) {
        if (content[i] == '\r') {
            // Skip \r if followed by \n (CRLF -> LF)
            if (i + 1 < content.size() && content[i + 1] == '\n') {
                continue;
            }
            // Convert standalone \r to \n
            result += '\n';
        } else {
            result += content[i];
        }
    }

    return result;
}

bool enableAnsiColors() {
#ifdef PLATFORM_WINDOWS
    HANDLE hOut = GetStdHandle(STD_OUTPUT_HANDLE);
    if (hOut == INVALID_HANDLE_VALUE) {
        return false;
    }

    DWORD dwMode = 0;
    if (!GetConsoleMode(hOut, &dwMode)) {
        return false;
    }

    dwMode |= ENABLE_VIRTUAL_TERMINAL_PROCESSING;
    return SetConsoleMode(hOut, dwMode) != 0;
#else
    // Unix-like systems support ANSI by default if connected to a terminal
    return isatty(STDOUT_FILENO) != 0;
#endif
}

std::string getCurrentDirectory() {
    char buffer[4096];
    if (getcwd(buffer, sizeof(buffer)) != nullptr) {
        return std::string(buffer);
    }
    return "";
}

std::string getFilename(const std::string& path) {
    size_t pos = path.find_last_of("/\\");
    if (pos != std::string::npos) {
        return path.substr(pos + 1);
    }
    return path;
}

std::string getDirectory(const std::string& path) {
    size_t pos = path.find_last_of("/\\");
    if (pos != std::string::npos) {
        return path.substr(0, pos);
    }
    return ".";
}

} // namespace Platform
} // namespace KooRemapper
