#!/bin/bash
# ==========================================================
# EasySay macOS 打包脚本
# 需要在 macOS 系统上执行（不能在 Windows/Linux 上交叉编译）
# ==========================================================
set -e

cd "$(dirname "$0")/.."

echo "[1/3] 安装依赖..."
pip install -r requirements.txt
pip install pyinstaller certifi

echo "[2/3] 生成 Logo（如果尚未生成）..."
python3 build/make_logo.py

echo "[3/3] 开始打包..."
pyinstaller --noconfirm build/app.spec

echo ""
echo "打包完成！App 位于 dist/EasySay.app"
echo "提示：未签名的 App 首次运行时，用户需要右键 -> 打开，绕过 Gatekeeper 拦截。"
echo "如需正式分发，建议使用 Apple Developer 账号进行签名和公证。"
