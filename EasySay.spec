# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[('app/data/voices.json', 'app/data'), ('app/resources', 'app/resources'), ('/Users/jiachangqiang/env312/lib/python3.12/site-packages/certifi/cacert.pem', 'certifi'), ('build/ffmpeg/ffmpeg', 'ffmpeg'), ('build/ffmpeg/ffprobe', 'ffmpeg')],
    hiddenimports=['edge_tts', 'edge_tts.exceptions', 'certifi'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='EasySay',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['app/resources/icons/app.icns'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='EasySay',
)
app = BUNDLE(
    coll,
    name='EasySay.app',
    icon='app/resources/icons/app.icns',
    bundle_identifier=None,
)
