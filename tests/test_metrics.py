from __future__ import annotations

import os
import time
from unittest.mock import patch

from vak.metrics import MetricDelta, MetricSample, RuntimeMetrics, _process_memory_mb


def test_process_memory_mb_returns_float_on_windows() -> None:
    """On Windows, _process_memory_mb() should return a positive float."""
    result = _process_memory_mb()
    if os.name == "nt":
        assert isinstance(result, float), f"Expected float, got {type(result)}"
        assert result > 0, f"Expected positive value, got {result}"
    else:
        assert result is None


def test_process_memory_mb_does_not_crash() -> None:
    """_process_memory_mb() must never raise — it returns None on failure."""
    # Call it twice to exercise both the configuration path and the cached path.
    result1 = _process_memory_mb()
    result2 = _process_memory_mb()
    for result in (result1, result2):
        assert result is None or (isinstance(result, float) and result > 0)


def test_process_memory_mb_returns_none_when_api_raises() -> None:
    """When the Win32 memory API raises, _process_memory_mb() returns None."""
    # Patch the entire function call chain to simulate a broken environment.
    with patch("vak.metrics._configure_win32_memory_api", side_effect=OSError("no psapi")):
        import vak.metrics

        original = vak.metrics._WIN32_API_CONFIGURED
        try:
            vak.metrics._WIN32_API_CONFIGURED = False
            result = _process_memory_mb()
            assert result is None
        finally:
            vak.metrics._WIN32_API_CONFIGURED = original


def test_runtime_metrics_sample() -> None:
    """RuntimeMetrics.sample() returns a valid MetricSample."""
    metrics = RuntimeMetrics()
    sample = metrics.sample()
    assert isinstance(sample, MetricSample)
    assert sample.wall_time > 0
    assert sample.process_time >= 0
    assert sample.memory_mb is None or sample.memory_mb > 0


def test_runtime_metrics_delta() -> None:
    """RuntimeMetrics.delta() returns a valid MetricDelta with non-negative values."""
    metrics = RuntimeMetrics()
    start = metrics.sample()
    # Burn a tiny amount of wall time so the delta is measurable.
    time.sleep(0.01)
    delta = metrics.delta(start)
    assert isinstance(delta, MetricDelta)
    assert delta.wall_seconds >= 0.005  # should be at least ~10ms
    assert delta.cpu_seconds >= 0
    assert delta.cpu_percent >= 0
    assert delta.memory_mb is None or delta.memory_mb > 0


def test_runtime_metrics_delta_with_explicit_end() -> None:
    """delta(start, end) uses the supplied end sample instead of taking a new one."""
    metrics = RuntimeMetrics()
    start = MetricSample(wall_time=100.0, process_time=50.0, memory_mb=10.0)
    end = MetricSample(wall_time=102.0, process_time=51.5, memory_mb=12.0)
    delta = metrics.delta(start, end)
    assert abs(delta.wall_seconds - 2.0) < 1e-6
    assert abs(delta.cpu_seconds - 1.5) < 1e-6
    assert delta.memory_mb == 12.0


def test_sample_with_unavailable_memory() -> None:
    """When memory measurement fails, sample() still works with memory_mb=None."""
    with patch("vak.metrics._process_memory_mb", return_value=None):
        metrics = RuntimeMetrics()
        sample = metrics.sample()
        assert sample.memory_mb is None
        assert sample.wall_time > 0
