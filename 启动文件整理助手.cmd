@echo off
where pythonw >nul 2>nul
if errorlevel 1 (
    echo Python was not found. Please install Python 3.10 or later with Tk support.
    pause
    exit /b 1
)
start "" pythonw "%~dp0folder_tidy_gui.py"
