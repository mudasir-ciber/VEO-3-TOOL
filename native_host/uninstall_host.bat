@echo off
setlocal
echo ============================================================
echo   Uninstalling VEO 3 Native Messaging Host from Registry
echo ============================================================

REG DELETE "HKCU\Software\Google\Chrome\NativeMessagingHosts\com.veo3.studio.bridge" /f

if %ERRORLEVEL% EQU 0 (
    echo.
    echo [SUCCESS] VEO 3 Native Messaging Host unregistered.
) else (
    echo.
    echo [INFO] Registry key not found or already removed.
)
echo ============================================================
pause
