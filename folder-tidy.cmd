@echo off
python "%~dp0folder_tidy.py" %*
exit /b %errorlevel%
