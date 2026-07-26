@echo off
REM ==========================================================
REM EasySay Windows 打包脚本
REM 需要在 Windows 系统上执行（不能在 Mac/Linux 上交叉编译）
REM ==========================================================

cd /d "%~dp0\.."

echo [1/5] 安装依赖...
pip install -r requirements.txt
pip install pyinstaller certifi

echo [2/5] 下载静态编译版 ffmpeg（用于 pydub 拼接音频）...
if not exist "build\ffmpeg" mkdir "build\ffmpeg"
REM gyan.dev 提供 Windows 静态编译的 ffmpeg（无外部 DLL 依赖，可随 App 分发）
curl -sL -o "build\ffmpeg\ffmpeg.7z" "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.7z"
if exist "build\ffmpeg\ffmpeg.exe" del "build\ffmpeg\ffmpeg.exe"
REM 用 7z 解压，只提取 ffmpeg.exe；如果系统没有 7z，需要先安装
where 7z >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo 错误：需要 7-Zip 来解压 ffmpeg，请先安装 https://www.7-zip.org/
    exit /b 1
)
7z e "build\ffmpeg\ffmpeg.7z" -o"build\ffmpeg" -r ffmpeg.exe -y
del "build\ffmpeg\ffmpeg.7z"
echo   ffmpeg 已就绪: build\ffmpeg\ffmpeg.exe

echo [3/5] 生成 Logo（如果尚未生成）...
python build\make_logo.py

echo [4/5] 开始打包...
pyinstaller --noconfirm build\app.spec

echo [5/5] 修正打包后 ffmpeg 的可执行权限...
if exist "dist\EasySay\ffmpeg\ffmpeg.exe" (
    echo   已确认 ffmpeg.exe 在 dist\EasySay\ffmpeg\ffmpeg.exe
)

echo.
echo 打包完成！可执行文件位于 dist\EasySay\EasySay.exe
pause
