from __future__ import annotations

import tempfile
from pathlib import Path

from vak.history import HistoryEntry, HistoryStore


def test_history_store_add_and_retrieve():
    with tempfile.TemporaryDirectory() as tmp_dir:
        store_path = Path(tmp_dir) / "test_history.json"
        store = HistoryStore(path=store_path)

        assert store.get_all() == []

        entry = store.add("Hello world this is a test", duration_seconds=2.5)
        assert entry is not None
        assert entry.text == "Hello world this is a test"
        assert entry.word_count == 6
        assert entry.duration_seconds == 2.5

        all_entries = store.get_all()
        assert len(all_entries) == 1
        assert all_entries[0].id == entry.id


def test_history_store_persistence():
    with tempfile.TemporaryDirectory() as tmp_dir:
        store_path = Path(tmp_dir) / "test_history.json"
        store1 = HistoryStore(path=store_path)
        store1.add("Persisted text", duration_seconds=1.2)

        store2 = HistoryStore(path=store_path)
        assert len(store2.get_all()) == 1
        assert store2.get_all()[0].text == "Persisted text"


def test_history_store_search_and_delete():
    with tempfile.TemporaryDirectory() as tmp_dir:
        store_path = Path(tmp_dir) / "test_history.json"
        store = HistoryStore(path=store_path)

        e1 = store.add("First sentence dictation")
        e2 = store.add("Second random note")

        results = store.search("dictation")
        assert len(results) == 1
        assert results[0].id == e1.id

        results = store.search("NOTE")
        assert len(results) == 1
        assert results[0].id == e2.id

        assert store.delete(e1.id) is True
        assert len(store.get_all()) == 1
        assert store.get_all()[0].id == e2.id

        store.clear()
        assert len(store.get_all()) == 0


def test_history_store_disabled():
    with tempfile.TemporaryDirectory() as tmp_dir:
        store_path = Path(tmp_dir) / "test_history.json"
        store = HistoryStore(path=store_path, enabled=False)
        entry = store.add("Ignored speech")
        assert entry is None
        assert store.get_all() == []
