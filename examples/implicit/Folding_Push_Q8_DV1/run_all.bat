@echo off
REM Run all implicit YAML examples for Folding_Push_Q8_DV1_AdvancedRubber.k
REM Usage: run_all.bat [path\to\KooRemapper.exe]

setlocal enabledelayedexpansion

REM Resolve KooRemapper binary
if not "%~1"=="" (
    set KR=%~1
) else if exist "..\..\..\..\build\bin\Release\KooRemapper.exe" (
    set KR=..\..\..\..\build\bin\Release\KooRemapper.exe
) else (
    where KooRemapper.exe >nul 2>&1
    if !errorlevel! == 0 (
        set KR=KooRemapper.exe
    ) else (
        echo ERROR: KooRemapper.exe not found.
        echo Pass path as argument: run_all.bat C:\path\to\KooRemapper.exe
        exit /b 1
    )
)

set PASS=0
set FAIL=0
set DIR=%~dp0

echo KooRemapper : %KR%
echo Model       : Folding_Push_Q8_DV1_AdvancedRubber.k
echo Directory   : %DIR%
echo ========================================================

echo [Static  Lv1~8]
for %%L in (1 2 3 4 5 6 7 8) do call :run static_level%%L.yaml

echo.
echo [Dynamic Lv1~8]
for %%L in (1 2 3 4 5 6 7 8) do call :run dynamic_lv%%L.yaml

echo.
echo [Full Options]
call :run implicit_full.yaml

echo.
echo ========================================================
echo PASS: %PASS%  FAIL: %FAIL%
if %FAIL% == 0 ( exit /b 0 ) else ( exit /b 1 )

:run
set YAML=%DIR%%~1
set NAME=%~1
<nul set /p "=  %-36s  " >nul
echo|set /p "=  %NAME%"
%KR% implicit "%YAML%" >nul 2>&1
if %errorlevel% == 0 (
    echo   PASS
    set /a PASS+=1
) else (
    echo   FAIL
    set /a FAIL+=1
)
goto :eof
