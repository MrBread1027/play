@echo off
chcp 65001 >nul
cd /d "%~dp0python"
echo 正在更新资料...
python app.py update
python app.py serve 8000
pause
