@echo off
title Chained Evolution Studio
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Virtual environment not found. Please ensure dependencies are installed.
    pause
    exit /b 1
)

echo Starting Chained Evolution Studio...
start "" ".venv\Scripts\python.exe" main.py
exit /b 0
