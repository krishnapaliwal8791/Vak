from __future__ import annotations

import ctypes
import os
import time
from dataclasses import dataclass


@dataclass(frozen=True)
class MetricSample:
    wall_time: float
    process_time: float
    memory_mb: float | None


@dataclass(frozen=True)
class MetricDelta:
    wall_seconds: float
    cpu_seconds: float
    cpu_percent: float
    memory_mb: float | None


class RuntimeMetrics:
    def sample(self) -> MetricSample:
        return MetricSample(
            wall_time=time.monotonic(),
            process_time=time.process_time(),
            memory_mb=_process_memory_mb(),
        )

    def delta(self, start: MetricSample, end: MetricSample | None = None) -> MetricDelta:
        final = end or self.sample()
        wall_seconds = max(final.wall_time - start.wall_time, 0.0)
        cpu_seconds = max(final.process_time - start.process_time, 0.0)
        cpu_percent = 0.0
        if wall_seconds > 0:
            cpu_percent = (cpu_seconds / wall_seconds) * 100 / max(os.cpu_count() or 1, 1)
        return MetricDelta(
            wall_seconds=wall_seconds,
            cpu_seconds=cpu_seconds,
            cpu_percent=cpu_percent,
            memory_mb=final.memory_mb,
        )


class _ProcessMemoryCounters(ctypes.Structure):
    """PROCESS_MEMORY_COUNTERS structure for GetProcessMemoryInfo."""

    _fields_ = [
        ("cb", ctypes.c_ulong),
        ("PageFaultCount", ctypes.c_ulong),
        ("PeakWorkingSetSize", ctypes.c_size_t),
        ("WorkingSetSize", ctypes.c_size_t),
        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
        ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
        ("PagefileUsage", ctypes.c_size_t),
        ("PeakPagefileUsage", ctypes.c_size_t),
    ]


def _configure_win32_memory_api() -> None:
    """Declare argtypes and restype for the Win32 memory API calls.

    Without these declarations, ctypes defaults to c_int (32-bit) for
    return values and parameters.  On 64-bit Python the pseudo-handle
    returned by GetCurrentProcess() (0xFFFFFFFFFFFFFFFF) is truncated
    to 0xFFFFFFFF, which the kernel rejects with STATUS_INVALID_HANDLE
    (0xc0000008) — a structured exception that kills the process before
    Python's try/except can intervene.
    """
    from ctypes import wintypes

    kernel32 = ctypes.windll.kernel32
    kernel32.GetCurrentProcess.argtypes = []
    kernel32.GetCurrentProcess.restype = wintypes.HANDLE

    psapi = ctypes.windll.psapi
    psapi.GetProcessMemoryInfo.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(_ProcessMemoryCounters),
        wintypes.DWORD,
    ]
    psapi.GetProcessMemoryInfo.restype = wintypes.BOOL


_WIN32_API_CONFIGURED = False


def _process_memory_mb() -> float | None:
    """Return the current process working-set size in MiB, or None on failure."""
    if os.name != "nt":
        return None

    global _WIN32_API_CONFIGURED  # noqa: PLW0603
    try:
        if not _WIN32_API_CONFIGURED:
            _configure_win32_memory_api()
            _WIN32_API_CONFIGURED = True

        kernel32 = ctypes.windll.kernel32
        psapi = ctypes.windll.psapi
        counters = _ProcessMemoryCounters()
        counters.cb = ctypes.sizeof(counters)
        handle = kernel32.GetCurrentProcess()
        ok = psapi.GetProcessMemoryInfo(
            handle, ctypes.byref(counters), counters.cb
        )
    except (AttributeError, OSError, ValueError, ctypes.ArgumentError):
        return None
    if not ok:
        return None
    return counters.WorkingSetSize / (1024 * 1024)
