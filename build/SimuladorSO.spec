# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_data_files
from PyInstaller.utils.hooks import copy_metadata

datas = [('C:/Users/pedro/Documents/GitHub/sim-escalonador/assets', 'assets')]
datas += collect_data_files('customtkinter')
datas += copy_metadata('customtkinter')
datas += copy_metadata('drawsvg')
datas += copy_metadata('darkdetect')
datas += copy_metadata('packaging')


a = Analysis(
    ['C:/Users/pedro/Documents/GitHub/sim-escalonador/gui.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=[],
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
    name='SimuladorSO',
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
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='SimuladorSO',
)
