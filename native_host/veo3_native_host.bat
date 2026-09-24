@echo off
set SCRIPT_DIR=%~dp0
if exist "%SCRIPT_DIR%..\.venv\Scripts\python.exe" (
    "%SCRIPT_DIR%..\.venv\Scripts\python.exe" "%SCRIPT_DIR%veo3_native_host.py"
) else if exist "%SCRIPT_DIR%python.exe" (
    "%SCRIPT_DIR%python.exe" "%SCRIPT_DIR%veo3_native_host.py"
) else (
    python "%SCRIPT_DIR%veo3_native_host.py"
)
