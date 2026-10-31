from __future__ import annotations

import logging
from collections.abc import Callable

import numpy as np

from vak.config import AudioConfig

logger = logging.getLogger(__name__)

AudioChunkHandler = Callable[[np.ndarray], None]


class SoundDeviceAudioCapture:
    def __init__(self, config: AudioConfig) -> None:
        self.config = config
        self._stream = None
        self.selected_device_index: int | None = None
        self.selected_device_name: str | None = None

    def log_device_diagnostics(self) -> None:
        if not self.config.log_input_devices:
            return

        try:
            import sounddevice as sd
        except ImportError:
            logger.exception("audio.devices.startup failure reason=sounddevice_unavailable")
            return

        try:
            devices = sd.query_devices()
            default_input_index = self._default_input_index(sd)
            logger.info("audio.devices.startup available_input_devices_begin")
            for index, device in enumerate(devices):
                input_channels = int(device.get("max_input_channels", 0))
                if input_channels <= 0:
                    continue
                logger.info(
                    "audio.devices.input index=%s name=%r hostapi=%s max_input_channels=%s default_samplerate=%s is_default=%s",
                    index,
                    device.get("name"),
                    device.get("hostapi"),
                    input_channels,
                    device.get("default_samplerate"),
                    index == default_input_index,
                )
            logger.info("audio.devices.startup available_input_devices_end")
            selected_index, selected_name = self._selected_device(sd, devices)
            self.selected_device_index = selected_index
            self.selected_device_name = selected_name
            logger.info(
                "audio.devices.selected index=%s name=%r configured_device=%r default_input_index=%s",
                selected_index,
                selected_name,
                self.config.device,
                default_input_index,
            )
        except Exception:
            logger.exception("audio.devices.startup failure")

    def start(self, on_chunk: AudioChunkHandler) -> None:
        if self._stream is not None:
            logger.info("audio.capture.start skipped stream_already_active=true")
            return

        try:
            import sounddevice as sd
        except ImportError as exc:
            raise RuntimeError("sounddevice is required for microphone capture.") from exc

        def callback(indata: np.ndarray, _frames: int, _time: object, status: object) -> None:
            if status:
                logger.debug("Audio callback status: %s", status)
            mono = indata[:, 0].astype(np.float32, copy=True)
            on_chunk(mono)

        devices = sd.query_devices()
        selected_index, selected_name = self._selected_device(sd, devices)
        self.selected_device_index = selected_index
        self.selected_device_name = selected_name

        if selected_index is None and self.config.device is None:
            if not any(int(d.get("max_input_channels", 0)) > 0 for d in devices):
                raise RuntimeError("No microphone or audio input device found.")

        device_arg = selected_index if selected_index is not None else self.config.device
        try:
            self._stream = sd.InputStream(
                samplerate=self.config.sample_rate,
                channels=self.config.channels,
                blocksize=self.config.block_size,
                dtype="float32",
                device=device_arg,
                callback=callback,
            )
            self._stream.start()
        except Exception:
            if self._stream is not None:
                try:
                    self._stream.close()
                except Exception:
                    pass
                self._stream = None
            raise

        logger.info(
            "audio.capture.start sample_rate=%s channels=%s block_size=%s configured_device=%r selected_index=%s selected_name=%r",
            self.config.sample_rate,
            self.config.channels,
            self.config.block_size,
            self.config.device,
            selected_index,
            selected_name,
        )

    def stop(self) -> None:
        if self._stream is None:
            logger.info("audio.capture.stop skipped stream_active=false")
            return
        logger.info("audio.capture.stop requested")
        stream = self._stream
        self._stream = None
        stream.stop()
        stream.close()
        logger.info("audio.capture.stop complete")

    def selected_device_summary(self) -> str:
        return f"{self.selected_device_index}:{self.selected_device_name}"

    @staticmethod
    def _default_input_index(sd: object) -> int | None:
        default = getattr(sd, "default", None)
        if default is None:
            return None
        return SoundDeviceAudioCapture._extract_input_index(getattr(default, "device", None))

    @staticmethod
    def _extract_input_index(default_device: object) -> int | None:
        candidates: list[object] = []
        if isinstance(default_device, (list, tuple)):
            candidates.append(default_device[0] if default_device else None)
        else:
            for attr in ("input", "input_device", "in_device", "_input"):
                if hasattr(default_device, attr):
                    candidates.append(getattr(default_device, attr))
            try:
                candidates.append(default_device[0])  # type: ignore[index]
            except (TypeError, KeyError, IndexError, AttributeError):
                pass
            candidates.append(default_device)

        for candidate in candidates:
            try:
                index = int(candidate)
            except (TypeError, ValueError):
                continue
            if index >= 0:
                return index
        return None

    def _selected_device(self, sd: object, devices: object) -> tuple[int | None, str | None]:
        if isinstance(self.config.device, int):
            if self._is_input_device(devices, self.config.device):
                device = sd.query_devices(self.config.device)
                return self.config.device, str(device.get("name"))
            logger.warning(
                "audio.devices.configured_invalid index=%s fallback=first_available_input",
                self.config.device,
            )
            return self._first_input_device(devices)

        if isinstance(self.config.device, str):
            needle = self.config.device.casefold()
            for index, device in enumerate(devices):
                name = str(device.get("name", ""))
                if needle in name.casefold() and int(device.get("max_input_channels", 0)) > 0:
                    return index, name
            logger.warning(
                "audio.devices.configured_not_found name=%r fallback=first_available_input",
                self.config.device,
            )
            return self._first_input_device(devices)

        default_index = self._default_input_index(sd)
        if default_index is None or not self._is_input_device(devices, default_index):
            logger.warning(
                "audio.devices.default_input_unavailable default_index=%s fallback=first_available_input",
                default_index,
            )
            return self._first_input_device(devices)
        device = sd.query_devices(default_index)
        return default_index, str(device.get("name"))

    @staticmethod
    def _is_input_device(devices: object, index: int) -> bool:
        try:
            device = devices[index]  # type: ignore[index]
            input_channels = int(device.get("max_input_channels", 0))
        except (TypeError, KeyError, IndexError):
            return False
        return input_channels > 0

    @staticmethod
    def _first_input_device(devices: object) -> tuple[int | None, str | None]:
        for index, device in enumerate(devices):
            if int(device.get("max_input_channels", 0)) > 0:
                return index, str(device.get("name"))
        return None, None
