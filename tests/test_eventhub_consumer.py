"""
Unit tests for consumer/eventhub_consumer.py's on_event() handler.

P0-01 contract (checkpoint ordering fix)
-----------------------------------------
After the fix, the checkpoint responsibility has moved from on_event() into
BatchBuffer.flush().  on_event() must:

  - Call batch_buffer.add(event_data, partition_id, offset, sequence_number)
    for every valid event (so BatchBuffer has the metadata it needs to
    checkpoint after the write).
  - NOT call checkpoint_manager.update_checkpoint() itself for buffered
    events — that is now BatchBuffer's job.
  - Still call checkpoint_manager.update_checkpoint() immediately for
    DLQ events (write_to_dlq is synchronous, so checkpointing right away
    is correct for that path).
  - NOT call checkpoint_manager.update_checkpoint() when batch_buffer.add()
    raises (write failed — checkpoint must not advance).

The per-flush checkpoint behaviour (last offset per partition, called only
after upload_batch succeeds) is covered exhaustively in test_batch_buffer.py.
"""

from __future__ import annotations

import json
import uuid

import pytest

import consumer.eventhub_consumer as consumer_module


class FakeCheckpointManager:
    def __init__(self):
        self.updates: list[dict] = []

    def update_checkpoint(self, partition_id, offset, sequence_number):
        self.updates.append(
            {
                "partition_id": partition_id,
                "offset": offset,
                "sequence_number": sequence_number,
            }
        )


class FakeBatchBuffer:
    """
    Test double for consumer.batch_buffer.BatchBuffer.

    Updated for P0-01: add() now accepts partition_id, offset, sequence_number
    keyword arguments alongside the event dict.  The fake records each call
    so tests can assert the correct arguments were passed.
    """

    def __init__(self, fail: bool = False):
        self.fail = fail
        # Each entry: (event_dict, partition_id, offset, sequence_number)
        self.added: list[tuple] = []

    def add(
        self,
        event: dict,
        partition_id: str,
        offset: str,
        sequence_number: int,
    ) -> None:
        if self.fail:
            raise RuntimeError("Simulated ADLS write failure")
        self.added.append((event, partition_id, offset, sequence_number))


class FakeStorageClient:
    def __init__(self):
        self.dlq_writes: list[tuple[str, str]] = []

    def write_to_dlq(self, raw_body: str, error_reason: str) -> str:
        self.dlq_writes.append((raw_body, error_reason))
        return "fake/dlq/path.json"


class FakePartitionContext:
    def __init__(self, partition_id="0"):
        self.partition_id = partition_id


class FakeEvent:
    def __init__(self, body: dict, offset="100", sequence_number=1):
        self._body = json.dumps(body)
        self.offset = offset
        self.sequence_number = sequence_number

    def body_as_str(self, encoding="UTF-8"):
        return self._body


def _valid_telemetry_body():
    return {
        "event_id": str(uuid.uuid4()),
        "device_id": "CAR-001",
        "asset_type": "vehicle",
        "timestamp": "2026-08-07T12:00:00+00:00",
        "priority": "normal",
        "schema_version": "1.0.0",
        "payload": {"speed_kmh": 42},
    }


@pytest.fixture(autouse=True)
def _restore_module_singletons():
    """Ensure module-level singletons are restored after each test."""
    original = (
        consumer_module.checkpoint_manager,
        consumer_module.storage_client,
        consumer_module.batch_buffer,
    )
    yield
    (
        consumer_module.checkpoint_manager,
        consumer_module.storage_client,
        consumer_module.batch_buffer,
    ) = original


def test_valid_event_passed_to_buffer_with_partition_metadata(monkeypatch):
    """
    P0-01: on_event must pass partition_id, offset, and sequence_number to
    batch_buffer.add() so BatchBuffer can checkpoint the correct offset after
    the batch is durably written.

    on_event itself must NOT call checkpoint_manager.update_checkpoint() for
    a buffered event — that is exclusively BatchBuffer.flush()'s job.
    """
    fake_checkpoint = FakeCheckpointManager()
    fake_buffer = FakeBatchBuffer(fail=False)
    monkeypatch.setattr(consumer_module, "checkpoint_manager", fake_checkpoint)
    monkeypatch.setattr(consumer_module, "batch_buffer", fake_buffer)
    monkeypatch.setattr(consumer_module, "storage_client", FakeStorageClient())

    event = FakeEvent(_valid_telemetry_body(), offset="100", sequence_number=42)
    consumer_module.on_event(FakePartitionContext(partition_id="0"), event)

    # add() was called once with the correct metadata.
    assert len(fake_buffer.added) == 1
    _, partition_id, offset, sequence_number = fake_buffer.added[0]
    assert partition_id == "0"
    assert offset == "100"
    assert sequence_number == 42

    # on_event must NOT checkpoint — that is BatchBuffer's responsibility.
    assert len(fake_checkpoint.updates) == 0, (
        "on_event() advanced the checkpoint for a buffered event. "
        "This is the P0-01 bug — checkpoint must only fire inside "
        "BatchBuffer.flush() after the write is confirmed."
    )


def test_failed_write_does_not_advance_checkpoint(monkeypatch):
    """
    If batch_buffer.add() raises (ADLS write failure), on_event must swallow
    the error (log it) and must NOT advance the checkpoint.
    """
    fake_checkpoint = FakeCheckpointManager()
    fake_buffer = FakeBatchBuffer(fail=True)
    monkeypatch.setattr(consumer_module, "checkpoint_manager", fake_checkpoint)
    monkeypatch.setattr(consumer_module, "batch_buffer", fake_buffer)
    monkeypatch.setattr(consumer_module, "storage_client", FakeStorageClient())

    event = FakeEvent(_valid_telemetry_body())
    consumer_module.on_event(FakePartitionContext(), event)

    assert len(fake_checkpoint.updates) == 0


def test_invalid_schema_routes_to_dlq_and_still_advances_checkpoint(monkeypatch):
    """
    Structurally invalid events are a different failure mode from a failed
    ADLS write: they can never be successfully processed, so they are
    routed to the DLQ and the checkpoint IS advanced immediately (write_to_dlq
    is synchronous — the DLQ file is durable before on_event returns, so
    checkpointing right away is correct).
    """
    fake_checkpoint = FakeCheckpointManager()
    fake_buffer = FakeBatchBuffer(fail=False)
    fake_storage = FakeStorageClient()
    monkeypatch.setattr(consumer_module, "checkpoint_manager", fake_checkpoint)
    monkeypatch.setattr(consumer_module, "batch_buffer", fake_buffer)
    monkeypatch.setattr(consumer_module, "storage_client", fake_storage)

    bad_body = {"device_id": "CAR-001"}  # missing required envelope fields
    event = FakeEvent(bad_body)
    consumer_module.on_event(FakePartitionContext(), event)

    assert len(fake_storage.dlq_writes) == 1
    # DLQ path: checkpoint IS advanced immediately (write is synchronous).
    assert len(fake_checkpoint.updates) == 1
    assert len(fake_buffer.added) == 0
