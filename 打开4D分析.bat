@echo off
cd /d "%~dp0python"
python app.py
if errorlevel 1 pause
