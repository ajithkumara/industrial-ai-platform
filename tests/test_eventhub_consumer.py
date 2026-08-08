"""
Unit tests for consumer/eventhub_consumer.py's on_event() handler.

Proves the Phase 2 checkpoint/data-loss invariant end-to-end at the
consumer level (not just inside BatchBuffer, see tests/test_batch_buffer.py):

  - A successfully buffered/persisted event advances the checkpoint.
  - An event that fails to persist (ADLS write error surfaced through
    batch_buffer.add()) must NOT advance the checkpoint, so it is retried
    (via Event Hub redelivery) instead of being silently lost.

These tests import consumer.eventhub_consumer directly. That import used to
construct live Azure clients (StorageClient) at module scope and would
crash without real credentials; this is now deferred to main(), so the
module-level singletons (checkpoint_manager/storage_client/batch_buffer)
start out as None and are monkeypatched here with fakes.
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
    def __init__(self, fail: bool = False):
        self.fail = fail
        self.added: list[dict] = []

    def add(self, event: dict) -> None:
        if self.fail:
            raise RuntimeError("Simulated ADLS write failure")
        self.added.append(event)


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


def test_successful_write_advances_checkpoint(monkeypatch):
    fake_checkpoint = FakeCheckpointManager()
    fake_buffer = FakeBatchBuffer(fail=False)
    monkeypatch.setattr(consumer_module, "checkpoint_manager", fake_checkpoint)
    monkeypatch.setattr(consumer_module, "batch_buffer", fake_buffer)
    monkeypatch.setattr(consumer_module, "storage_client", FakeStorageClient())

    event = FakeEvent(_valid_telemetry_body())
    consumer_module.on_event(FakePartitionContext(), event)

    assert len(fake_buffer.added) == 1
    assert len(fake_checkpoint.updates) == 1
    assert fake_checkpoint.updates[0]["offset"] == "100"


def test_failed_write_does_not_advance_checkpoint(monkeypatch):
    fake_checkpoint = FakeCheckpointManager()
    fake_buffer = FakeBatchBuffer(fail=True)  # simulates ADLS write failure
    monkeypatch.setattr(consumer_module, "checkpoint_manager", fake_checkpoint)
    monkeypatch.setattr(consumer_module, "batch_buffer", fake_buffer)
    monkeypatch.setattr(consumer_module, "storage_client", FakeStorageClient())

    event = FakeEvent(_valid_telemetry_body())
    # on_event must swallow the buffering failure (log it) rather than
    # propagate it, but must NOT advance the checkpoint.
    consumer_module.on_event(FakePartitionContext(), event)

    assert len(fake_checkpoint.updates) == 0


def test_invalid_schema_routes_to_dlq_and_still_advances_checkpoint(monkeypatch):
    """
    Structurally invalid events are a different failure mode from a failed
    ADLS write: they can never be successfully processed, so they are
    routed to the DLQ and the checkpoint IS advanced (there is nothing to
    retry — retrying would just fail validation again).
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
    assert len(fake_checkpoint.updates) == 1
    assert len(fake_buffer.added) == 0
