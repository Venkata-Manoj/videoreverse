@ECHO OFF
REM VideoReverse Test Runner for Windows

echo ================================================
echo   VideoReverse - Test Suite (Windows)
echo ================================================
echo.

REM Run unit tests
echo Running unit tests...
node src\run_tests.js -- tests\unit\

if %ERRORLEVEL% neq 0 (
    echo.
    echo Unit tests failed!
    exit /b 1
)

echo.
echo All tests passed!
exit /b 0