# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for PortPilot.
# Build from venv: .venv\Scripts\Activate.ps1 ; pip install pyinstaller ; pyinstaller portpilot.spec

from pathlib import Path

block_cipher = None

_icon = Path('assets/icon.ico')
datas_list = [('assets/icon.ico', 'assets')] if _icon.exists() else []

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=datas_list,
    hiddenimports=[
        'PySide6.QtCore', 'PySide6.QtGui', 'PySide6.QtWidgets',
        'sshtunnel', 'paramiko',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='PortPilot',
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
    entitlements=None,
    icon='assets/icon.ico' if _icon.exists() else None,
)
