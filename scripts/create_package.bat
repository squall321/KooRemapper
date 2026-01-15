@echo off
REM KooRemapper 배포 패키지 생성 스크립트 (Windows)

echo ============================================================
echo   KooRemapper 배포 패키지 생성
echo ============================================================
echo.

REM 버전 설정
set VERSION=1.0.0
set PACKAGE_NAME=KooRemapper_v%VERSION%_Windows

REM 기존 패키지 폴더 삭제
if exist "%PACKAGE_NAME%" (
    echo [1/6] 기존 패키지 폴더 삭제...
    rmdir /s /q "%PACKAGE_NAME%"
)

REM 패키지 폴더 생성
echo [2/6] 패키지 폴더 생성...
mkdir "%PACKAGE_NAME%"
mkdir "%PACKAGE_NAME%\examples"
mkdir "%PACKAGE_NAME%\docs"

REM 실행파일 복사
echo [3/6] 실행파일 복사...
copy "build\bin\Release\KooRemapper.exe" "%PACKAGE_NAME%\" >nul
if errorlevel 1 (
    echo [오류] 실행파일을 찾을 수 없습니다. 먼저 빌드를 실행하세요.
    pause
    exit /b 1
)

REM 문서 복사
echo [4/6] 문서 복사...
copy "README.md" "%PACKAGE_NAME%\" >nul
copy "DEPLOYMENT.md" "%PACKAGE_NAME%\docs\" >nul

REM 예제 파일 복사
echo [5/6] 예제 파일 복사...
if exist "examples\arc30\arc30_bent.k" (
    copy "examples\arc30\arc30_bent.k" "%PACKAGE_NAME%\examples\" >nul
)
if exist "build\bin\Release\test_vardens.yaml" (
    copy "build\bin\Release\test_vardens.yaml" "%PACKAGE_NAME%\examples\vardens.yaml" >nul
)

REM 간단한 시작 가이드 생성
echo [6/6] 시작 가이드 생성...
(
echo # KooRemapper 빠른 시작
echo.
echo ## 1. 버전 확인
echo KooRemapper.exe version
echo.
echo ## 2. 도움말
echo KooRemapper.exe help
echo.
echo ## 3. 예제 생성
echo KooRemapper.exe generate arc test_arc
echo.
echo ## 4. 자세한 사용법
echo README.md를 참조하세요.
) > "%PACKAGE_NAME%\QUICKSTART.md"

REM ZIP 압축
echo.
echo 배포 패키지가 생성되었습니다: %PACKAGE_NAME%
echo.
echo ZIP 파일로 압축하려면:
echo   powershell Compress-Archive -Path %PACKAGE_NAME% -DestinationPath %PACKAGE_NAME%.zip
echo.
pause
