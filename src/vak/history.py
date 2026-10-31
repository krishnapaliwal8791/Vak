from __future__ import annotations

import json
import logging
import os
import threading
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)


def _app_data_dir() -> Path:
    appdata = os.environ.get("APPDATA")
    if appdata:
        return Path(appdata) / "Vak"
    return Path.home() / ".vak"


@dataclass
class HistoryEntry:
    id: str
    timestamp: str  # ISO 8601 string
    text: str
    duration_seconds: float
    word_count: int

    @classmethod
    def create(cls, text: str, duration_seconds: float = 0.0) -> HistoryEntry:
        cleaned = text.strip()
        words = len(cleaned.split()) if cleaned else 0
        return cls(
            id=str(uuid.uuid4()),
            timestamp=datetime.now(timezone.utc).isoformat(),
            text=cleaned,
            duration_seconds=round(max(0.0, duration_seconds), 2),
            word_count=words,
        )


class HistoryStore:
    def __init__(self, path: Path | None = None, enabled: bool = True, max_entries: int = 500) -> None:
        self.path = path or (_app_data_dir() / "history.json")
        self.enabled = enabled
        self.max_entries = max_entries
        self._lock = threading.Lock()
        self._entries: list[HistoryEntry] = []
        self._load()

    def _load(self) -> None:
        with self._lock:
            if not self.path.exists():
                self._entries = []
                return
            try:
                with self.path.open("r", encoding="utf-8") as handle:
                    data = json.load(handle)
                if isinstance(data, list):
                    self._entries = [
                        HistoryEntry(
                            id=item.get("id", str(uuid.uuid4())),
                            timestamp=item.get("timestamp", ""),
                            text=item.get("text", ""),
                            duration_seconds=float(item.get("duration_seconds", 0.0)),
                            word_count=int(item.get("word_count", 0)),
                        )
                        for item in data
                        if isinstance(item, dict) and item.get("text")
                    ]
            except Exception as exc:
                logger.warning("Failed to load history from %s: %s", self.path, exc)
                self._entries = []

    def _save(self) -> None:
        # Caller must hold _lock
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temp_path = self.path.with_suffix(".tmp")
            data = [asdict(entry) for entry in self._entries]
            with temp_path.open("w", encoding="utf-8") as handle:
                json.dump(data, handle, ensure_ascii=False, indent=2)
            temp_path.replace(self.path)
        except Exception as exc:
            logger.warning("Failed to save history to %s: %s", self.path, exc)

    def add(self, text: str, duration_seconds: float = 0.0) -> HistoryEntry | None:
        if not self.enabled:
            return None
        cleaned = text.strip()
        if not cleaned:
            return None
        entry = HistoryEntry.create(cleaned, duration_seconds)
        with self._lock:
            self._entries.insert(0, entry)
            if len(self._entries) > self.max_entries:
                self._entries = self._entries[: self.max_entries]
            self._save()
        logger.info("history.added id=%s words=%s", entry.id, entry.word_count)
        return entry

    def get_all(self) -> list[HistoryEntry]:
        with self._lock:
            return list(self._entries)

    def search(self, query: str) -> list[HistoryEntry]:
        q = query.strip().lower()
        with self._lock:
            if not q:
                return list(self._entries)
            return [e for e in self._entries if q in e.text.lower()]

    def delete(self, entry_id: str) -> bool:
        with self._lock:
            initial_count = len(self._entries)
            self._entries = [e for e in self._entries if e.id != entry_id]
            if len(self._entries) != initial_count:
                self._save()
                return True
            return False

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()
            self._save()
        logger.info("history.cleared")
