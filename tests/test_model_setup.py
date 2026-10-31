"""Tests for speech recognition model catalog, integrity verification, background downloader, and setup dialog."""

from __future__ import annotations

import hashlib
import io
import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch
import urllib.error

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from vak.config import AppConfig, DesktopConfig, SttConfig
from vak.history import HistoryStore
from vak.models import (
    ModelDownloadWorker,
    ModelInfo,
    get_default_model,
    get_default_models_dir,
    get_supported_models,
    verify_model_integrity,
)
from vak.stt import ModelStatus, validate_model_path
from vak.ui.bridge import UiBridge
from vak.ui.pages.settings import SettingsPage
from vak.ui.theme import DARK_THEME, LIGHT_THEME
from vak.ui.widgets.model_setup_dialog import ModelSetupDialog
from vak.ui.window import MainWindow


@pytest.fixture(scope="session")
def qapp():
    """Ensure a headless QApplication exists for tests."""
    app = QApplication.instance()
    if app is None:
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        app = QApplication(["-platform", "offscreen"])
    return app


def test_supported_models_catalogue():
    models = get_supported_models()
    assert len(models) == 3

    model_ids = [m.model_id for m in models]
    assert "base.en" in model_ids
    assert "tiny.en" in model_ids
    assert "small.en" in model_ids

    default_model = get_default_model()
    assert default_model.model_id == "base.en"
    assert default_model.filename == "ggml-base.en.bin"
    assert default_model.is_default is True
    assert default_model.size_mb == 142
    assert default_model.sha256 == "a03779c86df3323075f5e796cb2ce5029f00ec8869eee3fdfb897afe36c6d002"
    assert default_model.sha1 == "137c40403d78fd54d454da0f9bd998f78703390c"

    for m in models:
        assert m.url.startswith("https://huggingface.co/ggerganov/whisper.cpp/resolve/main/")
        assert m.filename.endswith(".bin")
        assert m.size_mb > 0
        assert m.quality_speed != ""


def test_verify_model_integrity(tmp_path):
    test_file = tmp_path / "sample_model.bin"
    payload = b"test model contents for verification"
    test_file.write_bytes(payload)

    exp_sha256 = hashlib.sha256(payload).hexdigest()
    exp_sha1 = hashlib.sha1(payload).hexdigest()

    # Valid
    valid, msg = verify_model_integrity(test_file, expected_sha256=exp_sha256, expected_sha1=exp_sha1)
    assert valid is True
    assert "verified" in msg.lower()

    # Tampered sha256
    valid, msg = verify_model_integrity(test_file, expected_sha256="0000000000000000000000000000000000000000000000000000000000000000")
    assert valid is False
    assert "SHA-256 mismatch" in msg

    # Non-existent file
    valid, msg = verify_model_integrity(tmp_path / "non_existent.bin")
    assert valid is False
    assert "does not exist" in msg

    # Empty 0-byte file
    empty_file = tmp_path / "empty.bin"
    empty_file.write_bytes(b"")
    valid, msg = verify_model_integrity(empty_file)
    assert valid is False
    assert "empty" in msg


class MockHttpResponse:
    def __init__(self, data: bytes):
        self._data = data
        self._io = io.BytesIO(data)
        self.headers = {"Content-Length": str(len(data))}

    def read(self, chunk_size: int = 65536) -> bytes:
        return self._io.read(chunk_size)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass


def test_model_download_worker_success(tmp_path):
    payload = b"dummy speech model binary payload"
    sha256_val = hashlib.sha256(payload).hexdigest()
    sha1_val = hashlib.sha1(payload).hexdigest()

    test_model = ModelInfo(
        model_id="test.en",
        filename="ggml-test.en.bin",
        display_name="Test Model",
        size_mb=1,
        quality_speed="Fast",
        description="Testing",
        url="https://example.com/model.bin",
        sha256=sha256_val,
        sha1=sha1_val,
    )

    progress_events = []
    finished_paths = []
    error_events = []

    worker = ModelDownloadWorker(
        model=test_model,
        destination_dir=tmp_path,
        chunk_size=8,
        on_progress=lambda d, t: progress_events.append((d, t)),
        on_finished=lambda p: finished_paths.append(p),
        on_error=lambda e: error_events.append(e),
    )

    with patch("urllib.request.urlopen", return_value=MockHttpResponse(payload)):
        worker.start()
        worker._thread.join(timeout=5)

    assert not error_events
    assert len(finished_paths) == 1
    final_file = Path(finished_paths[0])
    assert final_file.exists()
    assert final_file.name == "ggml-test.en.bin"
    assert final_file.read_bytes() == payload
    assert len(progress_events) > 0
    # Last progress event should indicate full size
    assert progress_events[-1] == (len(payload), len(payload))

    # Verify no leftover .part_* files remain
    part_files = list(tmp_path.glob("*.part_*"))
    assert len(part_files) == 0


def test_model_download_worker_duplicate_prevention(tmp_path):
    payload = b"existing verified model binary"
    sha256_val = hashlib.sha256(payload).hexdigest()

    test_model = ModelInfo(
        model_id="dup.en",
        filename="ggml-dup.en.bin",
        display_name="Dup Model",
        size_mb=1,
        quality_speed="Fast",
        description="Testing",
        url="https://example.com/dup.bin",
        sha256=sha256_val,
        sha1=None,
    )

    # Pre-create the model with valid hash
    target = tmp_path / "ggml-dup.en.bin"
    target.write_bytes(payload)

    finished_paths = []
    with patch("urllib.request.urlopen") as mock_urlopen:
        worker = ModelDownloadWorker(
            model=test_model,
            destination_dir=tmp_path,
            on_finished=lambda p: finished_paths.append(p),
        )
        worker.start()
        worker._thread.join(timeout=5)

        # urlopen should not be called because existing model is valid
        mock_urlopen.assert_not_called()

    assert finished_paths == [str(target.resolve())]


def test_model_download_worker_cancellation(tmp_path):
    test_model = ModelInfo(
        model_id="cancel.en",
        filename="ggml-cancel.en.bin",
        display_name="Cancel Model",
        size_mb=1,
        quality_speed="Fast",
        description="Testing",
        url="https://example.com/cancel.bin",
        sha256=None,
        sha1=None,
    )

    cancelled_events = []

    # Mock response that yields indefinitely or long enough
    class SlowResponse:
        def __init__(self):
            self.headers = {"Content-Length": "1000000"}

        def read(self, chunk_size=65536):
            import time
            time.sleep(0.05)
            return b"A" * 1024

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

    worker = ModelDownloadWorker(
        model=test_model,
        destination_dir=tmp_path,
        chunk_size=1024,
        on_cancelled=lambda: cancelled_events.append(True),
    )

    with patch("urllib.request.urlopen", return_value=SlowResponse()):
        worker.start()
        import time
        time.sleep(0.08)
        worker.cancel()
        worker._thread.join(timeout=5)

    assert cancelled_events == [True]
    # No .part_* files left behind
    assert len(list(tmp_path.glob("*.part_*"))) == 0
    # Final file was not created
    assert not (tmp_path / "ggml-cancel.en.bin").exists()


def test_model_download_worker_network_error(tmp_path):
    test_model = get_default_model()
    errors = []

    worker = ModelDownloadWorker(
        model=test_model,
        destination_dir=tmp_path,
        on_error=lambda err: errors.append(err),
    )

    with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("Network unreachable")):
        worker.start()
        worker._thread.join(timeout=5)

    assert len(errors) == 1
    assert "Network unreachable" in errors[0]
    assert len(list(tmp_path.glob("*.part_*"))) == 0


def test_model_setup_dialog_views(qapp, tmp_path):
    dialog = ModelSetupDialog(is_first_launch=True)

    # Initial view is Selection (page 0)
    assert dialog.stack.currentIndex() == 0
    assert dialog.simple_model_title.text() != ""
    assert "142 MB" in dialog.btn_simple_download.text()

    # Advanced section is initially hidden
    assert dialog.advanced_container.isHidden() is True
    dialog._toggle_advanced_view()
    assert dialog.advanced_container.isHidden() is False
    assert len(dialog.model_radios) == 3

    # Theme application
    dialog.apply_theme(DARK_THEME)
    dialog.apply_theme(LIGHT_THEME)


def test_model_setup_dialog_local_file_selection(qapp, tmp_path):
    configured_paths = []
    dialog = ModelSetupDialog(
        is_first_launch=True,
        on_configured=lambda p: configured_paths.append(p),
    )

    valid_file = tmp_path / "local-model.bin"
    valid_file.write_bytes(b"valid model binary content")

    with patch("PySide6.QtWidgets.QFileDialog.getOpenFileName", return_value=(str(valid_file), "")):
        dialog.btn_browse_local.click()

    assert configured_paths == [str(valid_file)]
    assert dialog.stack.currentIndex() == 2  # Success page


def test_onboarding_sequence_coordination(qapp, tmp_path):
    config_path = tmp_path / "config.toml"
    config = AppConfig(
        desktop=DesktopConfig(welcome_completed=False),
        stt=SttConfig(model_path=""),
    )
    config.save(config_path)

    bridge = UiBridge()
    history_store = HistoryStore(path=tmp_path / "history.json")

    window = MainWindow(
        config=config,
        config_path=config_path,
        bridge=bridge,
        history_store=history_store,
    )

    assert window.is_model_ready() is False

    # Start onboarding: welcome screen is shown first
    window.start_onboarding_sequence()
    assert hasattr(window, "welcome_dialog")
    assert window.welcome_dialog.isVisible()

    # User completes welcome screen
    window.welcome_dialog.btn_get_started.click()
    assert window.config.desktop.welcome_completed is True

    # After welcome, because model is missing, model setup dialog opens!
    assert hasattr(window, "model_setup_dialog")
    assert window.model_setup_dialog is not None
    assert window.model_setup_dialog.isVisible()


def test_onboarding_sequence_when_model_already_ready(qapp, tmp_path):
    model_file = tmp_path / "ready-model.bin"
    model_file.write_bytes(b"some whisper bytes")

    config_path = tmp_path / "config.toml"
    config = AppConfig(
        desktop=DesktopConfig(welcome_completed=True),
        stt=SttConfig(model_path=str(model_file)),
    )
    config.save(config_path)

    bridge = UiBridge()
    history_store = HistoryStore(path=tmp_path / "history.json")

    window = MainWindow(
        config=config,
        config_path=config_path,
        bridge=bridge,
        history_store=history_store,
    )

    assert window.is_model_ready() is True

    window.start_onboarding_sequence()
    # Neither dialog should open
    assert not hasattr(window, "welcome_dialog") or window.welcome_dialog is None
    assert not hasattr(window, "model_setup_dialog") or window.model_setup_dialog is None


def test_settings_page_model_integration(qapp, tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    config_path = tmp_path / "config.toml"
    config = AppConfig()
    config.save(config_path)

    settings = SettingsPage(config=config, config_path=config_path)

    # Verify language is English and locked
    assert settings.cb_language.currentText() == "en"
    assert settings.cb_language.isEnabled() is False

    # Verify model discovery includes default models dir
    models_dir = get_default_models_dir()
    models_dir.mkdir(parents=True, exist_ok=True)
    test_discovered = models_dir / "ggml-discovered.bin"
    test_discovered.write_bytes(b"model data")

    discovered = settings._discover_models("")
    assert any("ggml-discovered.bin" in p for p in discovered)
