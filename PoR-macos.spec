# -*- mode: python ; coding: utf-8 -*-
"""macOS .app bundle spec for PoR-Final dynamic modifier.

Targets a Cocoa .app bundle. Run with:
    .venv/bin/pyinstaller PoR-macos.spec
"""
import os

block_cipher = None

a = Analysis(
    ['release/PoR.py'],
    pathex=['release'],
    binaries=[],
    datas=[],
    hiddenimports=['dolphin_memory_engine'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='PoR',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='PoR',
)

app = BUNDLE(
    coll,
    name='苍炎修改器.app',
    icon=None,        # macOS prefers .icns; .ico in resource/ unsuitable. Default Qt icon used.
    bundle_identifier='com.fe9.por-modifier',
    info_plist={
        'CFBundleShortVersionString': '1.0',
        'CFBundleVersion': '1.0',
        'NSHighResolutionCapable': True,
        'LSApplicationCategoryType': 'public.app-category.utilities',
    },
)
