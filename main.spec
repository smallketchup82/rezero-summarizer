# -*- mode: python ; coding: utf-8 -*-

# Main.py
a = Analysis(
    ['src/main.py', 'src/version.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=['tiktoken_ext.openai_public', 'tiktoken_ext'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='sumzero',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    version="version.rc",
    icon='NONE'
)

# Downloader
downloader = Analysis(
    ['src/downloader.py', 'src/version.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
downloaderpyz = PYZ(downloader.pure)

downloaderexe = EXE(
    downloaderpyz,
    downloader.scripts,
    downloader.binaries,
    downloader.datas,
    [],
    name='sumzero-dl',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    version="version.rc",
    icon='NONE'
)