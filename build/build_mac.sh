#!/bin/bash
# ==========================================================
# EasySay macOS 打包脚本
# 需要在 macOS 系统上执行（不能在 Windows/Linux 上交叉编译）
# ==========================================================
set -e

cd "$(dirname "$0")/.."
PROJECT_ROOT="$(pwd)"

# ---------- 自动检测虚拟环境 ----------
# 优先使用与手动打包一致的 venv，避免 Python 版本 / ABI 不匹配
VENV_DIR=""
for _candidate in "$HOME/env312" "$PROJECT_ROOT/venv" "$PROJECT_ROOT/.venv"; do
    if [ -f "$_candidate/bin/python" ]; then
        VENV_DIR="$_candidate"
        break
    fi
done

if [ -n "$VENV_DIR" ]; then
    echo "[INFO] 使用虚拟环境: $VENV_DIR"
    PYTHON="$VENV_DIR/bin/python"
    PIP="$VENV_DIR/bin/pip"
else
    echo "[INFO] 未找到虚拟环境，使用系统默认 Python"
    PYTHON="python3"
    PIP="pip3"
fi

# ---------- 1. 确认依赖 ----------
echo "[1/4] 确认依赖..."
$PIP install -r requirements.txt --quiet

# ---------- 2. 生成 Logo ----------
echo "[2/4] 生成 Logo（如果尚未生成）..."
$PYTHON build/make_logo.py

# ---------- 3. 打包 ----------
echo "[3/4] 开始打包..."
$PYTHON -m PyInstaller --noconfirm build/app.spec

# ---------- 4. 修正权限 ----------
echo "[4/4] 修正 App Bundle 内 ffmpeg/ffprobe 的可执行权限..."
FFMPEG_IN_APP="dist/EasySay.app/Contents/Resources/ffmpeg/ffmpeg"
FFPROBE_IN_APP="dist/EasySay.app/Contents/Resources/ffmpeg/ffprobe"

if [ -f "$FFMPEG_IN_APP" ]; then
    chmod +x "$FFMPEG_IN_APP"
    echo "  已修正 $FFMPEG_IN_APP 权限"
fi
if [ -f "$FFPROBE_IN_APP" ]; then
    chmod +x "$FFPROBE_IN_APP"
    echo "  已修正 $FFPROBE_IN_APP 权限"
fi

# 清除隔离属性（避免 Gatekeeper 拦截 ffmpeg 等二进制）
if [ -d "dist/EasySay.app" ]; then
    xattr -cr "dist/EasySay.app" 2>/dev/null || true
    echo "  已清除 App Bundle 扩展属性（quarantine）"
fi

echo ""
echo "打包完成！App 位于 dist/EasySay.app"
echo "提示：未签名的 App 首次运行时，用户需要右键 -> 打开，绕过 Gatekeeper 拦截。"
echo "如需正式分发，建议使用 Apple Developer 账号进行签名和公证。"
