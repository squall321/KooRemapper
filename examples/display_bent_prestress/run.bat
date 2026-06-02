@echo off
REM ============================================================
REM  Display Bent Prestress  —  single-YAML assemble path
REM ------------------------------------------------------------
REM  Modern path: prestress.yaml's `replace` op accepts the 3D
REM  HEX8 simple_bent_display.k directly via `simple_bent:` key.
REM  KooRemapper auto-extracts the top free-face shell in memory,
REM  maps detail_flat onto it, and computes Kirchhoff prestress.
REM
REM  Inputs (must exist in this folder):
REM    simple_bent_display.k     3D HEX8 bent reference
REM    detail_flat_display.k     3D HEX8 flat detail with *MAT_*
REM
REM  Outputs:
REM    detail_bent_display.k         mapped + MAT/PART/SECTION
REM                                  + *INCLUDE detail_bent_display.dynain
REM    detail_bent_display.dynain    *INITIAL_STRESS_SOLID
REM
REM  Usage:    run.bat
REM  Cleanup:  run.bat clean
REM
REM  Alternative: run_standalone.bat uses the older `map` +
REM  `prestress` 2-command chain (same result, 2 commands).
REM ============================================================

setlocal

set "EXE=%KOOREMAPPER%"
if "%EXE%"=="" set "EXE=%~dp0..\..\build\bin\Release\KooRemapper.exe"
if not exist "%EXE%" set "EXE=%~dp0..\..\build\windows\bin\Release\KooRemapper.exe"
if not exist "%EXE%" set "EXE=KooRemapper.exe"

cd /d "%~dp0"

if /I "%1"=="clean" (
    echo Cleaning generated files...
    del /q detail_bent_display.k detail_bent_display.dynain 2>nul
    echo Done.
    exit /b 0
)

if not exist "simple_bent_display.k" (
    echo [ERROR] simple_bent_display.k not found in %CD%
    exit /b 1
)
if not exist "detail_flat_display.k" (
    echo [ERROR] detail_flat_display.k not found in %CD%
    exit /b 1
)

echo.
echo === assemble ===  prestress.yaml
"%EXE%" assemble prestress.yaml
if errorlevel 1 (
    echo [FAIL] assemble failed.
    exit /b 1
)

echo.
echo ============================================================
echo  Done.
echo    detail_bent_display.k        ^<- feed this to LS-DYNA
echo                                    (contains *INCLUDE detail_bent_display.dynain)
echo    detail_bent_display.dynain   ^<- *INITIAL_STRESS_SOLID
echo ============================================================
endlocal
