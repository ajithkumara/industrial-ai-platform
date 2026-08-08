"""
Unit tests for consumer/batch_buffer.py.

Verifies the batching semantics described in the architecture:
 - RAW_BATCH_SIZE controls how many validated events accumulate before a
   JSONL file is written (flush to ADLS via the storage client).
 - Memory stays bounded (buffer clears after a successful flush).
 - A failed ADLS write (storage_client.upload_batch raising) must NOT
   silently discard the buffered events, so they can be retried.
"""

import pytest

from consumer.batch_buffer import BatchBuffer


class FakeStorageClient:
    """Test double for consumer.storage_client.StorageClient."""

    def __init__(self, fail_on_call: int | None = None):
        self.calls: list[list[dict]] = []
        self.fail_on_call = fail_on_call

    def upload_batch(self, events):
        call_number = len(self.calls) + 1
        if self.fail_on_call is not None and call_number == self.fail_on_call:
            raise RuntimeError("Simulated ADLS write failure")
        # Record a shallow copy since BatchBuffer clears its internal list
        # immediately after this call returns.
        self.calls.append(list(events))
        return f"fake/path/batch_{call_number}.jsonl"


@pytest.fixture(autouse=True)
def _small_batch_size(monkeypatch):
    """Force a small, deterministic batch size for these tests."""
    monkeypatch.setenv("RAW_BATCH_SIZE", "3")
    yield


def _reload_batch_buffer_module():
    # BatchBuffer reads settings.storage.raw_batch_size at construction time
    # via the module-level `settings` singleton, which is built once at
    # import time of config.settings. Re-import config.settings fresh so the
    # monkeypatched RAW_BATCH_SIZE env var takes effect for this test.
    import importlib

    import config.settings as settings_module

    importlib.reload(settings_module)
    return settings_module


def test_buffer_flushes_once_batch_size_reached():
    settings_module = _reload_batch_buffer_module()

    storage = FakeStorageClient()
    buffer = BatchBuffer.__new__(BatchBuffer)
    buffer._logger = __import__("logging").getLogger("test")
    buffer._storage_client = storage
    buffer._buffer = []
    buffer._batch_size = settings_module.settings.storage.raw_batch_size  # 3

    buffer.add({"event_id": "1"})
    buffer.add({"event_id": "2"})
    assert buffer.pending_events() == 2
    assert len(storage.calls) == 0  # not flushed yet

    buffer.add({"event_id": "3"})  # hits batch_size=3 -> triggers flush()

    assert len(storage.calls) == 1
    assert len(storage.calls[0]) == 3
    assert buffer.pending_events() == 0  # buffer cleared after successful flush


def test_failed_flush_does_not_silently_drop_events():
    """
    If the ADLS write fails, the events must remain in the buffer (not be
    lost) so a caller can decide how to react (e.g. not advance a
    checkpoint) and retry later.
    """
    storage = FakeStorageClient(fail_on_call=1)
    buffer = BatchBuffer.__new__(BatchBuffer)
    buffer._logger = __import__("logging").getLogger("test")
    buffer._storage_client = storage
    buffer._buffer = []
    buffer._batch_size = 2

    buffer.add({"event_id": "1"})

    with pytest.raises(RuntimeError):
        buffer.add({"event_id": "2"})  # reaches batch_size=2 -> flush() raises

    # Buffer must still hold both events — nothing was cleared/lost.
    assert buffer.pending_events() == 2


def test_pending_events_reports_buffer_depth():
    storage = FakeStorageClient()
    buffer = BatchBuffer.__new__(BatchBuffer)
    buffer._logger = __import__("logging").getLogger("test")
    buffer._storage_client = storage
    buffer._buffer = []
    buffer._batch_size = 10

    assert buffer.pending_events() == 0
    buffer.add({"event_id": "1"})
    assert buffer.pending_events() == 1
