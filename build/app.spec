# -*- mode: python ; coding: utf-8 -*-
"""
EasySay PyInstaller 打包配置

用法（在项目根目录下执行）：
    pyinstaller build/app.spec

注意：
  - Windows 和 macOS 必须分别在对应系统上执行打包，不能交叉编译
  - SPECPATH 是 PyInstaller 提供的内置变量，指向本 spec 文件所在目录（build/）
"""
import os
import sys

import certifi

PROJECT_ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))  # noqa: F821  (SPECPATH 由 PyInstaller 注入)

block_cipher = None

# 根据操作系统选择图标文件
if sys.platform == "win32":
    icon_file = os.path.join(PROJECT_ROOT, "app", "resources", "icons", "app.ico")
elif sys.platform == "darwin":
    icon_file = os.path.join(PROJECT_ROOT, "app", "resources", "icons", "app.icns")
else:
    icon_file = os.path.join(PROJECT_ROOT, "app", "resources", "icons", "app.png")

a = Analysis(
    [os.path.join(PROJECT_ROOT, "main.py")],
    pathex=[PROJECT_ROOT],
    binaries=[],
    datas=[
        (os.path.join(PROJECT_ROOT, "app", "data", "voices.json"), os.path.join("app", "data")),
        (os.path.join(PROJECT_ROOT, "app", "resources"), os.path.join("app", "resources")),
        (certifi.where(), "certifi"),  # 修复打包后 SSL 证书缺失导致 edge_tts 请求失败的问题
    ],
    hiddenimports=[
        "edge_tts",
        "edge_tts.exceptions",
        "certifi",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    cipher=block_cipher,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="EasySay",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,          # 不弹黑框控制台窗口
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon_file,
)

# macOS 下额外生成 .app Bundle
if sys.platform == "darwin":
    app = BUNDLE(
        exe,
        name="EasySay.app",
        icon=icon_file,
        bundle_identifier="com.easysaystudio.easysay",
        info_plist={
            "CFBundleName": "EasySay",
            "CFBundleDisplayName": "EasySay",
            "CFBundleShortVersionString": "1.0.0",
            "NSHighResolutionCapable": True,
        },
    )
