@echo off
chcp 65001 >nul
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
    echo 未找到 Python，请先安装 Python 并加入 PATH。
    pause
    exit /b 1
)

start "" /min powershell -NoProfile -WindowStyle Hidden -Command "Start-Sleep -Seconds 5; Start-Process 'http://127.0.0.1:8501'"
python -m streamlit run app.py

if errorlevel 1 (
    echo.
    echo 启动失败，请将本窗口中的错误截图发给我。
    pause
)

