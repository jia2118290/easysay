#!/bin/bash
# ==========================================================
# EasySay macOS 打包脚本
# 需要在 macOS 系统上执行（不能在 Windows/Linux 上交叉编译）
# ==========================================================
set -e

cd "$(dirname "$0")/.."

echo "[1/5] 安装依赖..."
pip install -r requirements.txt
pip install pyinstaller certifi

echo "[2/5] 下载静态编译版 ffmpeg（用于 pydub 拼接音频）..."
FFMPEG_DIR="build/ffmpeg"
mkdir -p "$FFMPEG_DIR"
# evermeet.cx 提供 Mac 静态编译的 ffmpeg（无外部 dylib 依赖，可随 App 分发）
curl -sL -o "$FFMPEG_DIR/ffmpeg.zip" "https://evermeet.cx/ffmpeg/getrelease/zip"
unzip -o "$FFMPEG_DIR/ffmpeg.zip" -d "$FFMPEG_DIR"
rm -f "$FFMPEG_DIR/ffmpeg.zip"
# evermeet zip 解压后文件名可能带版本号，统一重命名为 ffmpeg
find "$FFMPEG_DIR" -type f -name 'ffmpeg*' ! -name 'ffmpeg.zip' ! -name 'ffmpeg' -exec mv {} "$FFMPEG_DIR/ffmpeg" \;
chmod +x "$FFMPEG_DIR/ffmpeg"
echo "  ffmpeg 已就绪: $FFMPEG_DIR/ffmpeg"

echo "[3/5] 生成 Logo（如果尚未生成）..."
python3 build/make_logo.py

echo "[4/5] 开始打包..."
pyinstaller --noconfirm build/app.spec

echo "[5/5] 修正 App Bundle 内 ffmpeg 的可执行权限..."
# PyInstaller 会把 datas 文件复制到 Contents/Resources/ffmpeg/ffmpeg
# 需要确保文件有可执行权限，pydub 才能调用
FFMPEG_IN_APP="dist/EasySay.app/Contents/Resources/ffmpeg/ffmpeg"
if [ -f "$FFMPEG_IN_APP" ]; then
    chmod +x "$FFMPEG_IN_APP"
    echo "  已修正 $FFMPEG_IN_APP 权限"
fi
# macOS 签名后 Gatekeeper 允许运行；未签名 App 首次需右键打开
FFMPEG_IN_APP_XATTR_CHECK=$(xattr "$FFMPEG_IN_APP" 2>/dev/null || true)
if [ -n "$FFMPEG_IN_APP_XATTR_CHECK" ]; then
    xattr -cr "dist/EasySay.app" 2>/dev/null || true
    echo "  已清除 App Bundle 扩展属性（quarantine）"
fi

echo ""
echo "打包完成！App 位于 dist/EasySay.app"
echo "提示：未签名的 App 首次运行时，用户需要右键 -> 打开，绕过 Gatekeeper 拦截。"
echo "如需正式分发，建议使用 Apple Developer 账号进行签名和公证。"
