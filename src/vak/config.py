from __future__ import annotations

import os
import tempfile
import tomllib
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class HotkeyConfig:
    key: str = "f9"


@dataclass(frozen=True)
class AudioConfig:
    sample_rate: int = 16_000
    channels: int = 1
    block_ms: int = 32
    device: int | str | None = None
    log_input_devices: bool = False

    @property
    def block_size(self) -> int:
        return int(self.sample_rate * self.block_ms / 1000)


@dataclass(frozen=True)
class VadConfig:
    enabled: bool = True
    threshold: float = 0.5
    min_rms: float = 0.008
    allow_energy_fallback: bool = True


@dataclass(frozen=True)
class SttConfig:
    model_path: str = ""
    language: str = "en"
    threads: int = 4


@dataclass(frozen=True)
class InjectionConfig:
    restore_clipboard: bool = True
    paste_delay_seconds: float = 0.05


@dataclass(frozen=True)
class SessionConfig:
    max_session_seconds: float = 60.0
    min_transcribe_seconds: float = 0.25
    debug_log_raw_rms: bool = False
    benchmark_enabled: bool = False


@dataclass(frozen=True)
class DesktopConfig:
    start_with_windows: bool = False
    overlay_enabled: bool = True
    history_enabled: bool = True
    close_to_tray: bool = True
    theme: str = "dark"
    welcome_completed: bool = False


@dataclass(frozen=True)
class AppConfig:
    hotkey: HotkeyConfig = HotkeyConfig()
    audio: AudioConfig = AudioConfig()
    vad: VadConfig = VadConfig()
    stt: SttConfig = SttConfig()
    injection: InjectionConfig = InjectionConfig()
    session: SessionConfig = SessionConfig()
    desktop: DesktopConfig = DesktopConfig()
    tray_enabled: bool = True

    @staticmethod
    def default_path() -> Path:
        appdata = os.environ.get("APPDATA")
        if appdata:
            return Path(appdata) / "Vak" / "config.toml"
        return Path.home() / ".vak" / "config.toml"

    @classmethod
    def load(cls, path: Path | None = None) -> "AppConfig":
        config_path = path or cls.default_path()
        if not config_path.exists():
            return cls()

        try:
            with config_path.open("rb") as handle:
                data = tomllib.load(handle)
        except Exception:
            return cls()

        return cls(
            hotkey=HotkeyConfig(key=data.get("hotkey", HotkeyConfig.key)),
            audio=AudioConfig(
                sample_rate=data.get("sample_rate", AudioConfig.sample_rate),
                channels=data.get("channels", AudioConfig.channels),
                block_ms=data.get("block_ms", AudioConfig.block_ms),
                device=_empty_to_none(data.get("device", AudioConfig.device)),
                log_input_devices=data.get(
                    "debug_log_input_devices", AudioConfig.log_input_devices
                ),
            ),
            vad=VadConfig(
                enabled=data.get("vad_enabled", VadConfig.enabled),
                threshold=data.get("vad_threshold", VadConfig.threshold),
                min_rms=data.get("vad_min_rms", VadConfig.min_rms),
                allow_energy_fallback=data.get(
                    "allow_energy_vad_fallback", VadConfig.allow_energy_fallback
                ),
            ),
            stt=SttConfig(
                model_path=data.get("model_path", SttConfig.model_path),
                language=data.get("language", SttConfig.language),
                threads=data.get("threads", SttConfig.threads),
            ),
            injection=InjectionConfig(
                restore_clipboard=data.get(
                    "restore_clipboard", InjectionConfig.restore_clipboard
                ),
                paste_delay_seconds=data.get(
                    "paste_delay_seconds", InjectionConfig.paste_delay_seconds
                ),
            ),
            session=SessionConfig(
                max_session_seconds=data.get(
                    "max_session_seconds", SessionConfig.max_session_seconds
                ),
                min_transcribe_seconds=data.get(
                    "min_transcribe_seconds", SessionConfig.min_transcribe_seconds
                ),
                debug_log_raw_rms=data.get(
                    "debug_log_raw_rms", SessionConfig.debug_log_raw_rms
                ),
                benchmark_enabled=data.get(
                    "benchmark_enabled", SessionConfig.benchmark_enabled
                ),
            ),
            desktop=DesktopConfig(
                start_with_windows=data.get(
                    "start_with_windows", DesktopConfig.start_with_windows
                ),
                overlay_enabled=data.get(
                    "overlay_enabled", DesktopConfig.overlay_enabled
                ),
                history_enabled=data.get(
                    "history_enabled", DesktopConfig.history_enabled
                ),
                close_to_tray=data.get(
                    "close_to_tray", DesktopConfig.close_to_tray
                ),
                theme=data.get(
                    "theme", DesktopConfig.theme
                ),
                welcome_completed=data.get(
                    "welcome_completed", DesktopConfig.welcome_completed
                ),
            ),
            tray_enabled=data.get("tray_enabled", cls.tray_enabled),
        )

    def validate(self) -> None:
        errors: list[str] = []
        if not self.hotkey.key or not self.hotkey.key.strip():
            errors.append("Hotkey cannot be empty.")
        if self.audio.sample_rate <= 0:
            errors.append(f"Sample rate must be positive, got {self.audio.sample_rate}.")
        if self.audio.channels <= 0:
            errors.append(f"Channels must be positive, got {self.audio.channels}.")
        if self.audio.block_ms <= 0:
            errors.append(f"Block ms must be positive, got {self.audio.block_ms}.")
        if self.session.max_session_seconds <= 0:
            errors.append(
                f"Max session seconds must be positive, got {self.session.max_session_seconds}."
            )
        if self.session.min_transcribe_seconds <= 0:
            errors.append(
                f"Min transcribe seconds must be positive, got {self.session.min_transcribe_seconds}."
            )
        if not (0.0 <= self.vad.threshold <= 1.0):
            errors.append(f"VAD threshold must be between 0.0 and 1.0, got {self.vad.threshold}.")
        if self.vad.min_rms < 0.0:
            errors.append(f"VAD min RMS must be non-negative, got {self.vad.min_rms}.")
        if self.injection.paste_delay_seconds < 0.0:
            errors.append(
                f"Paste delay seconds must be non-negative, got {self.injection.paste_delay_seconds}."
            )
        if self.desktop.theme not in ("dark", "light"):
            errors.append(f"Theme must be 'dark' or 'light', got '{self.desktop.theme}'.")
        if errors:
            raise ValueError("; ".join(errors))

    def save(self, path: Path | None = None) -> None:
        self.validate()
        config_path = path or self.default_path()
        config_path.parent.mkdir(parents=True, exist_ok=True)
        content = "\n".join(
            [
                f"hotkey = {_toml_value(self.hotkey.key)}",
                f"model_path = {_toml_value(self.stt.model_path)}",
                f"sample_rate = {self.audio.sample_rate}",
                f"channels = {self.audio.channels}",
                f"block_ms = {self.audio.block_ms}",
                f"device = {_toml_value(self.audio.device)}",
                f"vad_enabled = {_toml_value(self.vad.enabled)}",
                f"vad_threshold = {self.vad.threshold}",
                f"vad_min_rms = {self.vad.min_rms}",
                f"allow_energy_vad_fallback = {_toml_value(self.vad.allow_energy_fallback)}",
                f"debug_log_input_devices = {_toml_value(self.audio.log_input_devices)}",
                f"debug_log_raw_rms = {_toml_value(self.session.debug_log_raw_rms)}",
                f"benchmark_enabled = {_toml_value(self.session.benchmark_enabled)}",
                f"tray_enabled = {_toml_value(self.tray_enabled)}",
                f"start_with_windows = {_toml_value(self.desktop.start_with_windows)}",
                f"overlay_enabled = {_toml_value(self.desktop.overlay_enabled)}",
                f"history_enabled = {_toml_value(self.desktop.history_enabled)}",
                f"close_to_tray = {_toml_value(self.desktop.close_to_tray)}",
                f"theme = {_toml_value(self.desktop.theme)}",
                f"welcome_completed = {_toml_value(self.desktop.welcome_completed)}",
                f"language = {_toml_value(self.stt.language)}",
                f"threads = {self.stt.threads}",
                f"restore_clipboard = {_toml_value(self.injection.restore_clipboard)}",
                f"paste_delay_seconds = {self.injection.paste_delay_seconds}",
                f"max_session_seconds = {self.session.max_session_seconds}",
                f"min_transcribe_seconds = {self.session.min_transcribe_seconds}",
                "",
            ]
        )
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            delete=False,
            dir=config_path.parent,
            prefix="config.",
            suffix=".tmp",
        ) as handle:
            handle.write(content)
            temp_path = Path(handle.name)
        temp_path.replace(config_path)


def _toml_value(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return '""'
    if isinstance(value, (int, float)):
        return str(value)
    escaped = str(value).replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _empty_to_none(value: object) -> object:
    return None if value == "" else value
