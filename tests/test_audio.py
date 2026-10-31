from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from vak.audio import SoundDeviceAudioCapture
from vak.config import AppConfig, AudioConfig, DesktopConfig, HotkeyConfig, SessionConfig


class FakeInputOutputPair:
    def __init__(self, input_index: int, output_index: int) -> None:
        self.input = input_index
        self.output = output_index


class FakeIndexedPair:
    def __init__(self, input_index: int, output_index: int) -> None:
        self._values = (input_index, output_index)

    def __getitem__(self, index: int) -> int:
        return self._values[index]


class FakeDefault:
    def __init__(self, device: object) -> None:
        self.device = device


class FakeSoundDevice:
    def __init__(self, default_device: object) -> None:
        self.default = FakeDefault(default_device)

    def query_devices(self, index: int):
        return DEVICES[index]


DEVICES = [
    {"name": "Speakers", "max_input_channels": 0},
    {"name": "USB Microphone", "max_input_channels": 1},
    {"name": "Webcam Microphone", "max_input_channels": 2},
]


def test_default_input_index_handles_pair_object() -> None:
    sd = FakeSoundDevice(FakeInputOutputPair(2, 0))

    assert SoundDeviceAudioCapture._default_input_index(sd) == 2


def test_default_input_index_handles_indexed_pair() -> None:
    sd = FakeSoundDevice(FakeIndexedPair(1, 0))

    assert SoundDeviceAudioCapture._default_input_index(sd) == 1


def test_selected_device_falls_back_to_first_input() -> None:
    audio = SoundDeviceAudioCapture(AudioConfig())
    sd = FakeSoundDevice(FakeInputOutputPair(0, 1))

    assert audio._selected_device(sd, DEVICES) == (1, "USB Microphone")


def test_config_save_and_load_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    config = replace(
        AppConfig(),
        hotkey=HotkeyConfig(key="ctrl+alt+space"),
        audio=replace(AppConfig().audio, device=1, log_input_devices=True),
        session=SessionConfig(debug_log_raw_rms=True, benchmark_enabled=True),
        desktop=DesktopConfig(start_with_windows=True),
    )

    config.save(path)
    loaded = AppConfig.load(path)

    assert loaded.hotkey.key == "ctrl+alt+space"
    assert loaded.audio.device == 1
    assert loaded.audio.log_input_devices
    assert loaded.session.debug_log_raw_rms
    assert loaded.session.benchmark_enabled
    assert loaded.desktop.start_with_windows
