# -*- mode: python ; coding: utf-8 -*-

import importlib.util
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs

# Resolve ROOT reliably, handling current working directory, SPECPATH, and Unicode paths
ROOT = None
spec_candidates = []
if "SPECPATH" in globals():
    sp = Path(SPECPATH).resolve()
    spec_candidates.append(sp if sp.is_dir() and (sp / "assets").exists() else sp.parent)
spec_candidates.extend([Path.cwd(), Path.cwd().parent])

for candidate in spec_candidates:
    if candidate and (candidate / "assets" / "branding" / "ico" / "vak.ico").exists():
        ROOT = candidate.resolve()
        break

if ROOT is None and "SPECPATH" in globals():
    sp_parent = Path(SPECPATH).resolve().parent
    if sp_parent.parent.exists():
        for sibling in sp_parent.parent.iterdir():
            if sibling.is_dir() and (sibling / "assets" / "branding" / "ico" / "vak.ico").exists():
                ROOT = sibling.resolve()
                break

if ROOT is None:
    ROOT = Path(SPECPATH).resolve().parent if "SPECPATH" in globals() else Path.cwd()

ENTRYPOINT = ROOT / "packaging" / "entrypoint.py"
SRC = ROOT / "src"
ICON = ROOT / "assets" / "branding" / "ico" / "vak.ico"

binaries = []
for package in ["sounddevice"]:
    binaries += collect_dynamic_libs(package)

# Explicitly collect delvewheel-bundled native libraries for pywhispercpp
_pw_spec = importlib.util.find_spec("pywhispercpp")
if _pw_spec and _pw_spec.origin:
    sp_dir = Path(_pw_spec.origin).parent.parent
    for pattern in [
        "whisper-*.dll",
        "ggml-*.dll",
        "msvcp140-*.dll",
        "vcomp140-*.dll",
        "_pywhispercpp*.pyd",
    ]:
        for dll in sp_dir.glob(pattern):
            binaries.append((str(dll), "."))

datas = [
    (str(ROOT / "assets" / "branding"), "assets/branding"),
]
for package in ["pywhispercpp", "silero_vad"]:
    datas += collect_data_files(package)

a = Analysis(
    [str(ENTRYPOINT)],
    pathex=[str(SRC)],
    binaries=binaries,
    datas=datas,
    hiddenimports=[
        "keyboard",
        "PIL",
        "PIL.Image",
        "PIL.ImageDraw",
        "pystray",
        "pystray._win32",
        "pywhispercpp",
        "pywhispercpp.model",
        "silero_vad",
        "sounddevice",
        "torch",
        "PySide6.QtCore",
        "PySide6.QtGui",
        "PySide6.QtWidgets",
        "PySide6.QtSvg",
        "PySide6.QtSvgWidgets",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tests"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Vak",
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
    icon=str(ICON) if ICON.exists() else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="Vak",
)
