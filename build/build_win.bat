@echo off
REM ==========================================================
REM EasySay Windows 打包脚本
REM 需要在 Windows 系统上执行（不能在 Mac/Linux 上交叉编译）
REM ==========================================================

cd /d "%~dp0\.."

echo [1/5] 安装依赖...
python -m pip install -r requirements.txt --quiet

REM Pillow 是 make_logo.py 的依赖，requirements.txt 里没有，单独安装
python -m pip install Pillow --quiet

echo [2/5] 下载静态编译版 ffmpeg / ffprobe（用于 pydub 拼接音频）...
if not exist "build\ffmpeg" mkdir "build\ffmpeg"

REM gyan.dev essentials 包包含 ffmpeg.exe + ffprobe.exe，都是静态链接无需额外 DLL
set "FFMPEG_ZIP=build\ffmpeg\ffmpeg.7z"
curl -sL -o "%FFMPEG_ZIP%" "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.7z"

where 7z >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo 错误：需要 7-Zip 来解压 ffmpeg，请先安装 https://www.7-zip.org/
    exit /b 1
)

REM 提取 ffmpeg.exe 和 ffprobe.exe（gyan 包内路径为 ffmpeg-X.X-.../bin/*.exe）
7z e "%FFMPEG_ZIP%" -o"build\ffmpeg" -r ffmpeg.exe -y
7z e "%FFMPEG_ZIP%" -o"build\ffmpeg" -r ffprobe.exe -y
del "%FFMPEG_ZIP%"
echo   ffmpeg / ffprobe 已就绪: build\ffmpeg\

echo [3/5] 生成 Logo（如果尚未生成）...
python build\make_logo.py

echo [4/5] 开始打包...
python -m PyInstaller --noconfirm build\app.spec

echo [5/5] 确认打包结果...
if exist "dist\EasySay.exe" (
    echo   已生成 dist\EasySay.exe
) else if exist "dist\EasySay\EasySay.exe" (
    echo   已生成 dist\EasySay\EasySay.exe
) else (
    echo   警告：未找到生成的 exe 文件，请检查上一步打包日志
)

echo.
echo 打包完成！
pause
