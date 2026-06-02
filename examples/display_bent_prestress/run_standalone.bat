@echo off
REM ============================================================
REM  Display Bent Prestress  —  legacy 2-command chain
REM ------------------------------------------------------------
REM  Uses the standalone `map` + `prestress` commands. No
REM  assemble, no YAML, no extract-surface prep — direct 3D HEX8
REM  bent ref + 3D HEX8 flat detail → 3D bent mesh + dynain.
REM
REM  Inputs (must exist in this folder):
REM    simple_bent_display.k     3D HEX8 bent reference
REM    detail_flat_display.k     3D HEX8 flat detail with *MAT_*
REM
REM  Outputs:
REM    detail_bent_display.k         mapped bent geometry, MAT/PART/SECTION
REM                                  preserved from detail_flat (commit bf53a7f)
REM                                  + *INCLUDE detail_bent_display.dynain
REM    detail_bent_display.dynain    *INITIAL_STRESS_SOLID, Green-Lagrange
REM                                  → Hooke from detail_flat's *MAT_ELASTIC
REM
REM  Usage:    run_standalone.bat
REM  Cleanup:  run_standalone.bat clean
REM ============================================================

setlocal

REM Resolve KooRemapper.exe — env var override, then common build paths
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
echo === Step 1/2 ===  map  (3D bent ref + 3D flat detail ^-^> 3D bent detail)
"%EXE%" map simple_bent_display.k detail_flat_display.k detail_bent_display.k
if errorlevel 1 (
    echo [FAIL] map failed.
    exit /b 1
)

echo.
echo === Step 2/2 ===  prestress  (flat + bent ^-^> *INITIAL_STRESS_SOLID dynain)
"%EXE%" prestress detail_flat_display.k detail_bent_display.k detail_bent_display.dynain
if errorlevel 1 (
    echo [FAIL] prestress failed.
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
