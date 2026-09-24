# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['E:/VEO 3 TOOL/main.py'],
    pathex=[],
    binaries=[],
    datas=[('E:/VEO 3 TOOL/ui/styles/dark_theme.qss', 'ui/styles'), ('E:/VEO 3 TOOL/app_icon.ico', '.'), ('E:/VEO 3 TOOL/app_icon.png', '.'), ('E:/VEO 3 TOOL/.venv/Lib/site-packages/playwright/driver', 'playwright/driver'), ('E:/VEO 3 TOOL/.venv/Lib/site-packages/imageio_ffmpeg/binaries', 'imageio_ffmpeg/binaries')],
    hiddenimports=['PySide6', 'playwright', 'imageio_ffmpeg', 'PIL'],
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
    name='ChainedEvolutionStudio',
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
    icon=['E:/VEO 3 TOOL/app_icon.ico'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='ChainedEvolutionStudio',
)
