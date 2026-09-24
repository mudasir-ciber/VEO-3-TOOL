@echo off
setlocal
echo ============================================================
echo   Installing VEO 3 Native Messaging Host in Windows Registry
echo ============================================================

set SCRIPT_DIR=%~dp0
set MANIFEST_PATH=%SCRIPT_DIR%com.veo3.studio.bridge.json

REM Add registry key for current user
REG ADD "HKCU\Software\Google\Chrome\NativeMessagingHosts\com.veo3.studio.bridge" /ve /t REG_SZ /d "%MANIFEST_PATH%" /f

if %ERRORLEVEL% EQU 0 (
    echo.
    echo [SUCCESS] VEO 3 Native Messaging Host registered successfully!
    echo Manifest: %MANIFEST_PATH%
) else (
    echo.
    echo [ERROR] Failed to register Native Messaging Host in Registry.
)
echo ============================================================
pause
