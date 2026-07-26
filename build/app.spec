# -*- mode: python ; coding: utf-8 -*-
"""
EasySay PyInstaller 打包配置

用法（在项目根目录下执行）：
    pyinstaller build/app.spec
"""
import os
import sys

import certifi

PROJECT_ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))  # noqa: F821

block_cipher = None

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
        (certifi.where(), "certifi"),
    ],
    hiddenimports=[
        "edge_tts",
        "edge_tts.exceptions",
        "certifi",
        "sounddevice",
        "azure.cognitiveservices.speech",
        "pydub",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    cipher=block_cipher,
)

# --- 打包 ffmpeg / ffprobe（pydub 依赖） ---
_ffmpeg_src = os.path.join(PROJECT_ROOT, "build", "ffmpeg", "ffmpeg")
_ffprobe_src = os.path.join(PROJECT_ROOT, "build", "ffmpeg", "ffprobe")
if os.path.exists(_ffmpeg_src):
    a.datas.append((os.path.join("ffmpeg", "ffmpeg"), _ffmpeg_src, "DATA"))
if os.path.exists(_ffprobe_src):
    a.datas.append((os.path.join("ffmpeg", "ffprobe"), _ffprobe_src, "DATA"))

# --- 添加 Azure Speech SDK 原生动态库 ---
import azure.cognitiveservices.speech as _azsdk
_azsdk_dir = os.path.dirname(_azsdk.__file__)
for _f in os.listdir(_azsdk_dir):
    if _f.endswith(".dylib") or _f.endswith(".so"):
        _fp = os.path.join(_azsdk_dir, _f)
        a.binaries.append((_f, _fp, "BINARY"))

# --- 添加 sounddevice 的 PortAudio 原生库 ---
import sounddevice as _sd
_sd_dir = os.path.dirname(_sd.__file__)
_portaudio_dir = os.path.join(_sd_dir, "_sounddevice_data", "portaudio-binaries")
if os.path.isdir(_portaudio_dir):
    for _f in os.listdir(_portaudio_dir):
        if _f.endswith(".dylib") or _f.endswith(".so"):
            _fp = os.path.join(_portaudio_dir, _f)
            a.binaries.append((_f, _fp, "BINARY"))

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
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon_file,
)

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
            "NSMicrophoneUsageDescription": "EasySay 需要使用麦克风进行录音和发音评测",
        },
    )
