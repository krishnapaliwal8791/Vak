"""Comprehensive verification script for packaged Vak Windows release."""
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

# Ensure UTF-8 output
sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
DIST_VAK = ROOT / "dist" / "Vak"
INTERNAL = DIST_VAK / "_internal"

print(f"[*] Testing packaged distribution at: {DIST_VAK}")

# Check 1: Executable
vak_exe = DIST_VAK / "Vak.exe"
assert vak_exe.exists(), f"Vak.exe missing at {vak_exe}"
print(f"[+] Found Vak.exe ({vak_exe.stat().st_size:,} bytes)")

# Check 2: Branding assets
branding_root = INTERNAL / "assets" / "branding"
assert branding_root.exists(), f"Branding root missing at {branding_root}"
ico_file = branding_root / "ico" / "vak.ico"
assert ico_file.exists(), f"vak.ico missing at {ico_file}"
png_file = branding_root / "png" / "vak-icon-256.png"
assert png_file.exists(), f"vak-icon-256.png missing at {png_file}"
svg_file = branding_root / "svg" / "vak-logo-dark.svg"
assert svg_file.exists(), f"vak-logo-dark.svg missing at {svg_file}"
print("[+] Branding assets verified (ico, png, svg)")

# Check 3: Qt Plugins
qwindows = INTERNAL / "PySide6" / "plugins" / "platforms" / "qwindows.dll"
assert qwindows.exists(), f"qwindows.dll missing at {qwindows}"
print("[+] Qt platform plugin qwindows.dll verified")

# Check 4: PyWhisperCpp native libraries
pyd_files = list(INTERNAL.glob("_pywhispercpp*.pyd"))
assert len(pyd_files) > 0, "No _pywhispercpp*.pyd found"
whisper_dlls = list(INTERNAL.glob("whisper-*.dll"))
assert len(whisper_dlls) > 0, "No whisper-*.dll found"
ggml_dlls = list(INTERNAL.glob("ggml-*.dll"))
assert len(ggml_dlls) > 0, "No ggml-*.dll found"
print(f"[+] PyWhisperCpp native binaries verified ({len(whisper_dlls)} whisper DLLs, {len(ggml_dlls)} ggml DLLs)")

# Check 5: Silero VAD assets
silero_dir = INTERNAL / "silero_vad"
assert silero_dir.exists(), "silero_vad directory missing"
jit_file = silero_dir / "data" / "silero_vad.jit"
assert jit_file.exists(), "silero_vad.jit missing"
print("[+] Silero VAD assets verified")

# Check 6: Portaudio dynamic library
sounddevice_dir = INTERNAL / "_sounddevice_data" / "portaudio-binaries"
assert sounddevice_dir.exists(), "portaudio-binaries missing"
portaudio_dlls = list(sounddevice_dir.glob("*.dll"))
assert len(portaudio_dlls) > 0, "No portaudio DLLs found"
print(f"[+] PortAudio binaries verified ({[p.name for p in portaudio_dlls]})")

# Check 7: UI Dashboard and Settings page instantiation under simulated frozen environment
os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.frozen = True
sys._MEIPASS = str(INTERNAL)
sys.executable = str(vak_exe)

from PySide6.QtWidgets import QApplication
from vak.config import AppConfig
from vak.history import HistoryStore
from vak.ui.bridge import UiBridge
from vak.ui.window import MainWindow
from vak.ui.widgets.model_setup_dialog import ModelSetupDialog
from vak.models import get_supported_models, get_default_model
from vak.stt import WhisperCppTranscriber

qapp = QApplication.instance() or QApplication(["-platform", "offscreen"])

with tempfile.TemporaryDirectory() as tmp_dir:
    cfg_path = Path(tmp_dir) / "config.toml"
    cfg = AppConfig()
    cfg.save(cfg_path)
    bridge = UiBridge()
    history = HistoryStore(path=Path(tmp_dir) / "history.json")

    # Verify MainWindow (Dashboard + Settings)
    win = MainWindow(config=cfg, config_path=cfg_path, bridge=bridge, history_store=history)
    assert win.stack.count() == 6, f"Expected 6 stack pages, got {win.stack.count()}"
    # Select Settings page
    win.sidebar.select_page(4)
    win._on_nav_changed(4)
    assert win.stack.currentIndex() == 4
    print("[+] MainWindow Dashboard and Settings page navigation verified")

    # Verify ModelSetupDialog
    dialog = ModelSetupDialog(is_first_launch=False)
    models = get_supported_models()
    assert len(models) == 3
    default_m = get_default_model()
    assert default_m.model_id == "base.en"
    print(f"[+] ModelSetupDialog and catalog verified (default: {default_m.model_id}, {default_m.size_mb} MB)")

    # Verify pywhispercpp speech transcription if test model exists
    test_model = Path("C:/models/ggml-base.en.bin")
    if test_model.exists():
        import numpy as np
        from vak.config import SttConfig
        stt_cfg = SttConfig(model_path=str(test_model), threads=2, language="en")
        transcriber = WhisperCppTranscriber(config=stt_cfg)
        # Create 1 second of silence
        dummy_audio = np.zeros(16000, dtype=np.float32)
        text = transcriber.transcribe(dummy_audio, 16000)
        print(f"[+] Transcriber initialized & executed transcription cleanly: result='{text}'")

print("\n[SUCCESS] All packaged component checks PASSED!")
