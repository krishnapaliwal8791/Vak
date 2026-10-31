from __future__ import annotations

import logging
import os
import threading
import tkinter as tk
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from vak.config import AppConfig, DesktopConfig, HotkeyConfig
from vak.startup import apply_start_with_windows
from vak.stt import ModelStatus, validate_model_path

logger = logging.getLogger(__name__)


class SettingsWindow:
    def __init__(
        self,
        config_path: Path,
        on_restart: Callable[[], None],
        on_quit: Callable[[], None],
    ) -> None:
        self.config_path = config_path
        self.on_restart = on_restart
        self.on_quit = on_quit
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()

    def show(self) -> None:
        with self._lock:
            if self._thread and self._thread.is_alive():
                return
            self._thread = threading.Thread(target=self._run, name="vak-settings", daemon=True)
            self._thread.start()

    def _run(self) -> None:
        try:
            _SettingsUi(self.config_path, self.on_restart, self.on_quit).run()
        except Exception:
            logger.exception("Settings window failed")


class _SettingsUi:
    def __init__(
        self,
        config_path: Path,
        on_restart: Callable[[], None],
        on_quit: Callable[[], None],
    ) -> None:
        self.config_path = config_path
        self.on_restart = on_restart
        self.on_quit = on_quit
        self.config = AppConfig.load(config_path)
        self.root = tk.Tk()
        self.root.title("Vak Settings")
        self.root.resizable(False, False)
        self.hotkey_var = tk.StringVar(value=self.config.hotkey.key)
        self.model_var = tk.StringVar(value=self.config.stt.model_path)
        self.microphone_var = tk.StringVar(value=_device_to_display(self.config.audio.device))
        self.startup_var = tk.BooleanVar(value=self.config.desktop.start_with_windows)
        self.benchmark_var = tk.BooleanVar(value=self.config.session.benchmark_enabled)
        self.debug_var = tk.BooleanVar(
            value=self.config.audio.log_input_devices or self.config.session.debug_log_raw_rms
        )
        self.model_status_var = tk.StringVar(value="")
        self.model_options = _model_options(self.config.stt.model_path)
        self.microphone_options = _input_device_options()

    def run(self) -> None:
        self._build()
        self.root.mainloop()

    def _build(self) -> None:
        frame = ttk.Frame(self.root, padding=16)
        frame.grid(row=0, column=0, sticky="nsew")

        ttk.Label(frame, text="Hotkey").grid(row=0, column=0, sticky="w", pady=4)
        ttk.Entry(frame, textvariable=self.hotkey_var, width=34).grid(
            row=0, column=1, sticky="ew", pady=4
        )

        ttk.Label(frame, text="Model").grid(row=1, column=0, sticky="w", pady=4)
        ttk.Combobox(frame, textvariable=self.model_var, values=self.model_options, width=42).grid(
            row=1, column=1, sticky="ew", pady=4
        )
        ttk.Button(frame, text="Browse", command=self._browse_model).grid(
            row=1, column=2, padx=(8, 0), pady=4
        )
        self.model_status_label = ttk.Label(
            frame, textvariable=self.model_status_var, font=("TkDefaultFont", 8)
        )
        self.model_status_label.grid(row=2, column=1, sticky="w", padx=2, pady=(0, 4))

        ttk.Label(frame, text="Microphone").grid(row=3, column=0, sticky="w", pady=4)
        ttk.Combobox(
            frame,
            textvariable=self.microphone_var,
            values=self.microphone_options,
            width=42,
            state="readonly" if self.microphone_options else "normal",
        ).grid(row=3, column=1, sticky="ew", pady=4)

        ttk.Checkbutton(frame, text="Start with Windows", variable=self.startup_var).grid(
            row=4, column=1, sticky="w", pady=(10, 2)
        )
        ttk.Checkbutton(frame, text="Benchmark logging", variable=self.benchmark_var).grid(
            row=5, column=1, sticky="w", pady=2
        )
        ttk.Checkbutton(frame, text="Debug microphone logging", variable=self.debug_var).grid(
            row=6, column=1, sticky="w", pady=2
        )

        buttons = ttk.Frame(frame)
        buttons.grid(row=7, column=0, columnspan=3, sticky="e", pady=(16, 0))
        ttk.Button(buttons, text="Save settings", command=self._save).grid(row=0, column=0, padx=4)
        ttk.Button(buttons, text="Restart Vak", command=self._restart).grid(row=0, column=1, padx=4)
        ttk.Button(buttons, text="Open logs folder", command=self._open_logs).grid(
            row=0, column=2, padx=4
        )
        ttk.Button(buttons, text="Quit Vak", command=self._quit).grid(row=0, column=3, padx=4)

        self.model_var.trace_add("write", lambda *_: self._update_model_status())
        self._update_model_status()

    def _update_model_status(self) -> None:
        path = self.model_var.get().strip()
        status, message = validate_model_path(path)
        if status is ModelStatus.AVAILABLE:
            self.model_status_var.set("Model file found and ready.")
        elif status is ModelStatus.NOT_CONFIGURED:
            self.model_status_var.set("No model configured (required for dictation).")
        elif status is ModelStatus.NOT_FOUND:
            self.model_status_var.set("Model file not found on disk.")
        else:
            self.model_status_var.set(f"Invalid path: {message}")

    def _browse_model(self) -> None:
        path = filedialog.askopenfilename(
            title="Select whisper.cpp model",
            filetypes=[("Whisper model", "*.bin"), ("All files", "*.*")],
        )
        if path:
            self.model_var.set(path)

    def _save(self) -> None:
        try:
            config = self._config_from_fields()
            config.save(self.config_path)
            apply_start_with_windows(config.desktop.start_with_windows)
        except Exception as exc:
            logger.exception("Failed to save settings")
            messagebox.showerror("Vak Settings", f"Could not save settings:\n{exc}")
            return
        self.config = config
        messagebox.showinfo("Vak Settings", "Settings saved. Restart Vak to apply changes.")

    def _restart(self) -> None:
        self._save()
        self.on_restart()
        self.root.destroy()

    def _open_logs(self) -> None:
        logs_dir = _app_data_dir()
        logs_dir.mkdir(parents=True, exist_ok=True)
        os.startfile(str(logs_dir))

    def _quit(self) -> None:
        self.on_quit()
        self.root.destroy()

    def _config_from_fields(self) -> AppConfig:
        debug_enabled = self.debug_var.get()
        hotkey_str = self.hotkey_var.get().strip()
        if not hotkey_str:
            raise ValueError("Hotkey cannot be empty. Please enter a valid key (e.g. f9).")
        config = replace(
            self.config,
            hotkey=HotkeyConfig(key=hotkey_str),
            audio=replace(
                self.config.audio,
                device=_display_to_device(self.microphone_var.get()),
                log_input_devices=debug_enabled,
            ),
            stt=replace(self.config.stt, model_path=self.model_var.get().strip()),
            session=replace(
                self.config.session,
                benchmark_enabled=self.benchmark_var.get(),
                debug_log_raw_rms=debug_enabled,
            ),
            desktop=DesktopConfig(start_with_windows=self.startup_var.get()),
        )
        config.validate()
        return config


def _model_options(current: str) -> list[str]:
    options = []
    if current:
        options.append(current)
    for root in [Path("C:/models"), Path.home() / "Models"]:
        if root.exists():
            options.extend(str(path) for path in root.glob("*.bin"))
    return sorted(set(options))


def _input_device_options() -> list[str]:
    try:
        import sounddevice as sd
    except ImportError:
        return []
    options = ["Default"]
    try:
        for index, device in enumerate(sd.query_devices()):
            if int(device.get("max_input_channels", 0)) > 0:
                options.append(f"{index}: {device.get('name')}")
    except Exception:
        logger.exception("Failed to enumerate microphones")
    return options


def _device_to_display(device: int | str | None) -> str:
    return "Default" if device is None else str(device)


def _display_to_device(value: str) -> int | str | None:
    cleaned = value.strip()
    if not cleaned or cleaned == "Default":
        return None
    if ":" in cleaned:
        prefix = cleaned.split(":", 1)[0]
        if prefix.isdigit():
            return int(prefix)
    return cleaned


def _app_data_dir() -> Path:
    appdata = os.environ.get("APPDATA")
    if appdata:
        return Path(appdata) / "Vak"
    return Path.home() / ".vak"
