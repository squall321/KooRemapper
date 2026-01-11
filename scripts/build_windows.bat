@echo off
setlocal enabledelayedexpansion

echo ============================================
echo  KooRemapper Build Script for Windows
echo ============================================
echo.

:: Check for CMake
where cmake >nul 2>nul
if %errorlevel% neq 0 (
    echo ERROR: CMake not found in PATH
    echo Please install CMake and add it to PATH
    pause
    exit /b 1
)

:: Get script directory and project root
set "SCRIPT_DIR=%~dp0"
set "PROJECT_ROOT=%SCRIPT_DIR%.."
cd /d "%PROJECT_ROOT%"

:: Create build directory
set "BUILD_DIR=build\windows"
if not exist "%BUILD_DIR%" mkdir "%BUILD_DIR%"

:: Configure
echo [1/2] Configuring with CMake...
cmake -G "Visual Studio 17 2022" -A x64 -S . -B "%BUILD_DIR%"
if %errorlevel% neq 0 (
    echo.
    echo ERROR: CMake configuration failed
    pause
    exit /b 1
)

:: Build
echo.
echo [2/2] Building Release configuration...
cmake --build "%BUILD_DIR%" --config Release -j
if %errorlevel% neq 0 (
    echo.
    echo ERROR: Build failed
    pause
    exit /b 1
)

echo.
echo ============================================
echo  Build completed successfully!
echo  Executable: %BUILD_DIR%\bin\Release\KooRemapper.exe
echo ============================================
pause
