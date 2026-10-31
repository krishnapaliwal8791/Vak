"""Speech recognition model catalog, storage, integrity verification, and background download management for Vāk."""

from __future__ import annotations

import hashlib
import logging
import os
import shutil
import tempfile
import threading
import urllib.request
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Final

logger = logging.getLogger(__name__)

HUGGINGFACE_WHISPER_BASE_URL: Final[str] = (
    "https://huggingface.co/ggerganov/whisper.cpp/resolve/main"
)


@dataclass(frozen=True)
class ModelInfo:
    model_id: str
    filename: str
    display_name: str
    size_mb: int
    quality_speed: str
    description: str
    url: str
    sha256: str | None
    sha1: str | None
    is_default: bool = False


# Explicitly supported English models for V1
SUPPORTED_ENGLISH_MODELS: Final[dict[str, ModelInfo]] = {
    "base.en": ModelInfo(
        model_id="base.en",
        filename="ggml-base.en.bin",
        display_name="Base English (Recommended)",
        size_mb=142,
        quality_speed="Fast & Balanced",
        description="Best general-purpose model for daily writing, coding, and notes with high accuracy and low latency.",
        url=f"{HUGGINGFACE_WHISPER_BASE_URL}/ggml-base.en.bin",
        sha256="a03779c86df3323075f5e796cb2ce5029f00ec8869eee3fdfb897afe36c6d002",
        sha1="137c40403d78fd54d454da0f9bd998f78703390c",
        is_default=True,
    ),
    "tiny.en": ModelInfo(
        model_id="tiny.en",
        filename="ggml-tiny.en.bin",
        display_name="Tiny English (Fastest)",
        size_mb=75,
        quality_speed="Ultra-Fast / Low CPU",
        description="Lowest memory footprint and instant response. Ideal for older hardware, tablets, or quick voice notes.",
        url=f"{HUGGINGFACE_WHISPER_BASE_URL}/ggml-tiny.en.bin",
        sha256=None,
        sha1="c78c86eb1a8faa21b369bcd33207cc90d64ae9df",
        is_default=False,
    ),
    "small.en": ModelInfo(
        model_id="small.en",
        filename="ggml-small.en.bin",
        display_name="Small English (High Accuracy)",
        size_mb=466,
        quality_speed="High Accuracy / Moderate CPU",
        description="Increased precision for complex jargon, diverse accents, and noisy environments. Requires more CPU.",
        url=f"{HUGGINGFACE_WHISPER_BASE_URL}/ggml-small.en.bin",
        sha256=None,
        sha1="db8a495a91d927739e50b3fc1cc4c6b8f6c2d022",
        is_default=False,
    ),
}


def get_default_model() -> ModelInfo:
    """Return the candidate default model (base.en)."""
    return SUPPORTED_ENGLISH_MODELS["base.en"]


def get_supported_models() -> list[ModelInfo]:
    """Return list of supported English models."""
    return list(SUPPORTED_ENGLISH_MODELS.values())


def get_default_models_dir() -> Path:
    """Return the dedicated user-writable model storage directory."""
    appdata = os.environ.get("APPDATA")
    if appdata:
        root = Path(appdata) / "Vak"
    else:
        root = Path.home() / ".vak"
    return root / "models"


def verify_model_integrity(
    path: Path,
    expected_sha256: str | None = None,
    expected_sha1: str | None = None,
) -> tuple[bool, str]:
    """
    Verify file integrity against trustworthy SHA256 or SHA1 checksums.
    Returns (is_valid, message).
    """
    if not path.exists() or not path.is_file():
        return False, f"File does not exist: {path}"

    try:
        size = path.stat().st_size
        if size == 0:
            return False, "File is empty (0 bytes)."

        h_sha256 = hashlib.sha256() if expected_sha256 else None
        h_sha1 = hashlib.sha1() if expected_sha1 else None

        with path.open("rb") as handle:
            while chunk := handle.read(131072):
                if h_sha256:
                    h_sha256.update(chunk)
                if h_sha1:
                    h_sha1.update(chunk)

        if expected_sha256 and h_sha256:
            actual = h_sha256.hexdigest().lower()
            if actual != expected_sha256.lower():
                return False, f"SHA-256 mismatch: expected {expected_sha256}, got {actual}"

        if expected_sha1 and h_sha1:
            actual = h_sha1.hexdigest().lower()
            if actual != expected_sha1.lower():
                return False, f"SHA-1 mismatch: expected {expected_sha1}, got {actual}"

        return True, "Integrity verified."
    except Exception as exc:
        return False, f"Failed to compute checksum: {exc}"


class ModelDownloadWorker:
    """
    Background downloader for Whisper models.
    Supports progress tracking, cancellation, retry, atomic file moves,
    incomplete file cleanup, and duplicate download prevention.
    """

    def __init__(
        self,
        model: ModelInfo,
        destination_dir: Path | None = None,
        on_progress: callable | None = None,
        on_status: callable | None = None,
        on_finished: callable | None = None,
        on_error: callable | None = None,
        on_cancelled: callable | None = None,
        chunk_size: int = 65536,
    ) -> None:
        self.model = model
        self.destination_dir = destination_dir or get_default_models_dir()
        self.on_progress = on_progress
        self.on_status = on_status
        self.on_finished = on_finished
        self.on_error = on_error
        self.on_cancelled = on_cancelled
        self.chunk_size = chunk_size

        self._cancelled = threading.Event()
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._active = False

    @property
    def is_running(self) -> bool:
        return self._active

    def start(self) -> None:
        with self._lock:
            if self._active:
                return
            self._cancelled.clear()
            self._active = True
            self._thread = threading.Thread(
                target=self._run,
                name=f"vak-model-download-{self.model.model_id}",
                daemon=True,
            )
            self._thread.start()

    def cancel(self) -> None:
        self._cancelled.set()

    def _run(self) -> None:
        temp_file: Path | None = None
        target_file = self.destination_dir / self.model.filename

        try:
            self.destination_dir.mkdir(parents=True, exist_ok=True)

            # Duplicate-download prevention: Check if already present and valid
            if target_file.exists():
                self._report_status("Checking existing model file...")
                valid, msg = verify_model_integrity(
                    target_file, self.model.sha256, self.model.sha1
                )
                if valid:
                    logger.info("Model %s already exists and is valid: %s", self.model.model_id, target_file)
                    self._report_status("Model file ready.")
                    if self.on_progress:
                        self.on_progress(target_file.stat().st_size, target_file.stat().st_size)
                    if self.on_finished:
                        self.on_finished(str(target_file.resolve()))
                    return
                else:
                    logger.warning("Existing model file failed verification (%s); re-downloading.", msg)

            self._report_status(f"Connecting to download {self.model.display_name}...")

            # Clean up old temporary part files from earlier aborted attempts
            try:
                for old_part in self.destination_dir.glob(f"{self.model.filename}.part_*"):
                    old_part.unlink(missing_ok=True)
            except Exception:
                pass

            temp_file = self.destination_dir / f"{self.model.filename}.part_{uuid.uuid4().hex[:8]}"

            req = urllib.request.Request(
                self.model.url,
                headers={"User-Agent": "Vak-SpeechAI/0.1.0 (+https://vak.lordk22.in)"},
            )

            h_sha256 = hashlib.sha256() if self.model.sha256 else None
            h_sha1 = hashlib.sha1() if self.model.sha1 else None
            downloaded_bytes = 0

            with urllib.request.urlopen(req, timeout=30) as response:
                total_bytes = int(response.headers.get("Content-Length", 0))
                self._report_status(f"Downloading {self.model.filename}...")

                with temp_file.open("wb") as handle:
                    while True:
                        if self._cancelled.is_set():
                            logger.info("Download cancelled by user.")
                            handle.close()
                            self._cleanup_temp(temp_file)
                            if self.on_cancelled:
                                self.on_cancelled()
                            return

                        chunk = response.read(self.chunk_size)
                        if not chunk:
                            break

                        handle.write(chunk)
                        downloaded_bytes += len(chunk)

                        if h_sha256:
                            h_sha256.update(chunk)
                        if h_sha1:
                            h_sha1.update(chunk)

                        if self.on_progress:
                            self.on_progress(downloaded_bytes, total_bytes)

            if self._cancelled.is_set():
                self._cleanup_temp(temp_file)
                if self.on_cancelled:
                    self.on_cancelled()
                return

            # Verification of download completeness
            if total_bytes > 0 and downloaded_bytes != total_bytes:
                raise IOError(
                    f"Incomplete download: received {downloaded_bytes} bytes of expected {total_bytes} bytes."
                )

            self._report_status("Verifying model integrity...")

            if self.model.sha256 and h_sha256:
                actual_sha256 = h_sha256.hexdigest().lower()
                if actual_sha256 != self.model.sha256.lower():
                    raise ValueError(
                        f"Integrity check failed (SHA-256 mismatch): expected {self.model.sha256}, got {actual_sha256}"
                    )

            if self.model.sha1 and h_sha1:
                actual_sha1 = h_sha1.hexdigest().lower()
                if actual_sha1 != self.model.sha1.lower():
                    raise ValueError(
                        f"Integrity check failed (SHA-1 mismatch): expected {self.model.sha1}, got {actual_sha1}"
                    )

            # Atomic move from temp to final destination
            self._report_status("Finalizing model file...")
            temp_file.replace(target_file)
            temp_file = None  # Successfully moved

            logger.info("Model download complete and verified: %s", target_file)
            self._report_status("Model setup complete.")

            if self.on_finished:
                self.on_finished(str(target_file.resolve()))

        except Exception as exc:
            logger.exception("Model download failed: %s", exc)
            self._cleanup_temp(temp_file)
            if self._cancelled.is_set():
                if self.on_cancelled:
                    self.on_cancelled()
            else:
                if self.on_error:
                    self.on_error(str(exc))
        finally:
            with self._lock:
                self._active = False

    def _cleanup_temp(self, temp_file: Path | None) -> None:
        if temp_file and temp_file.exists():
            try:
                temp_file.unlink(missing_ok=True)
            except Exception as exc:
                logger.warning("Failed to clean up temporary file %s: %s", temp_file, exc)

    def _report_status(self, message: str) -> None:
        if self.on_status:
            self.on_status(message)
