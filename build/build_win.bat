@echo off
REM ==========================================================
REM EasySay Windows 打包脚本
REM 需要在 Windows 系统上执行（不能在 Mac/Linux 上交叉编译）
REM ==========================================================

cd /d "%~dp0\.."

echo [1/3] 安装依赖...
pip install -r requirements.txt
pip install pyinstaller certifi

echo [2/3] 生成 Logo（如果尚未生成）...
python build\make_logo.py

echo [3/3] 开始打包...
pyinstaller --noconfirm build\app.spec

echo.
echo 打包完成！可执行文件位于 dist\EasySay\EasySay.exe
pause
