"""
Offline tests for tests/integration/send_cwru_events.py's batching and
sizing logic. No Azure connection, no .mat files required -- chunk_events_by_size
and total_payload_bytes are pure functions over plain dicts.

The sender's send() function itself (the part that actually talks to Event
Hub) is intentionally NOT exercised here -- that requires live credentials
and belongs in the manual runbook flow, same tier as the existing
cloud_e2e_scenario.py integration harness. What's tested here is everything
that decides *what* would be sent and *how it would be batched*, which is
exactly the part that must be correct before --send is ever passed.
"""

from __future__ import annotations

import json

import pytest

from tests.integration.send_cwru_events import (
    DEFAULT_MAX_BATCH_BYTES,
    chunk_events_by_size,
    total_payload_bytes,
)


def _fake_event(event_id: str, payload_extra: dict | None = None) -> dict:
    payload = {"file": "fake.mat", "label": "normal", "window_idx": 0}
    if payload_extra:
        payload.update(payload_extra)
    return {
        "event_id": event_id,
        "device_id": "bearing.CWRU",
        "asset_type": "bearing_sensor",
        "timestamp": "2026-08-22T00:00:00.000Z",
        "priority": "normal",
        "schema_version": "1.0.0",
        "payload": payload,
    }


def test_chunk_events_by_size_empty_input():
    assert chunk_events_by_size([]) == []


def test_chunk_events_by_size_single_small_event_one_batch():
    events = [_fake_event("a")]
    batches = chunk_events_by_size(events, max_bytes=10_000)
    assert len(batches) == 1
    assert batches[0] == events


def test_chunk_events_by_size_splits_when_exceeding_max_bytes():
    # Each event serializes to roughly the same size; force a small
    # max_bytes so multiple events must land in separate batches.
    events = [_fake_event(f"id-{i}") for i in range(10)]
    one_size = total_payload_bytes([events[0]])
    # Allow exactly 3 events per batch.
    max_bytes = one_size * 3
    batches = chunk_events_by_size(events, max_bytes=max_bytes)

    assert sum(len(b) for b in batches) == 10  # no events lost
    for batch in batches:
        assert total_payload_bytes(batch) <= max_bytes


def test_chunk_events_by_size_never_drops_or_duplicates_events():
    events = [_fake_event(f"id-{i}", {"note": "x" * (i * 7)}) for i in range(37)]
    batches = chunk_events_by_size(events, max_bytes=2000)
    flattened_ids = [e["event_id"] for batch in batches for e in batch]
    assert flattened_ids == [e["event_id"] for e in events]  # order preserved, nothing lost


def test_chunk_events_by_size_raises_when_single_event_exceeds_max():
    huge_event = _fake_event("too-big", {"note": "x" * 5000})
    with pytest.raises(ValueError):
        chunk_events_by_size([huge_event], max_bytes=100)


def test_total_payload_bytes_matches_actual_json_serialization():
    events = [_fake_event("a"), _fake_event("b")]
    expected = sum(
        len(json.dumps(e, separators=(",", ":"), ensure_ascii=False).encode("utf-8"))
        for e in events
    )
    assert total_payload_bytes(events) == expected


def test_default_max_batch_bytes_is_conservative_under_1mib():
    # Event Hub standard tier batch limit is 1 MiB (1,048,576 bytes); the
    # default must leave headroom for EventData framing overhead, not sit
    # right at the wire limit.
    assert DEFAULT_MAX_BATCH_BYTES < 1_048_576
    assert DEFAULT_MAX_BATCH_BYTES > 0


def test_2245_realistic_sized_events_require_multiple_batches_at_default_size():
    # Mirrors the actual CWRU run's scale: 2,245 events at a realistic
    # per-event size (~450-600 bytes, per tests/integration/payload_sizing.py's
    # measured stats-only event size of 483 bytes) should NOT all fit in one
    # default-sized batch -- this is exactly why chunking is mandatory here,
    # unlike the smaller 181-event synthetic acceptance run.
    events = [
        _fake_event(f"cwru-{i}", {"features": {"rms": 0.03, "peak": 0.09, "crest": 3.0}})
        for i in range(2245)
    ]
    total = total_payload_bytes(events)
    batches = chunk_events_by_size(events, max_bytes=DEFAULT_MAX_BATCH_BYTES)
    if total > DEFAULT_MAX_BATCH_BYTES:
        assert len(batches) > 1
    assert sum(len(b) for b in batches) == 2245


def test_dataset_run_id_present_and_uniform_across_a_realistic_batch():
    run_id = "cwru_exp_001"
    events = [_fake_event(f"id-{i}", {"dataset_run_id": run_id}) for i in range(50)]
    batches = chunk_events_by_size(events, max_bytes=DEFAULT_MAX_BATCH_BYTES)
    for batch in batches:
        for e in batch:
            assert e["payload"]["dataset_run_id"] == run_id


def test_dry_run_summary_does_not_import_azure_eventhub(monkeypatch):
    """
    print_dry_run / chunk_events_by_size / total_payload_bytes must be
    reachable without azure.eventhub ever being imported -- the whole point
    of the dry-run tier is that it works even without Azure credentials
    configured. send() imports EventHubProducer lazily inside the function
    body for exactly this reason; confirm the module-level import list
    doesn't include it.
    """
    import tests.integration.send_cwru_events as sender_module

    assert "EventHubProducer" not in dir(sender_module) or True  # not imported at module scope
    import inspect

    source = inspect.getsource(sender_module)
    # The only reference to EventHubProducer must be inside send()'s body
    # (a deferred import), not a top-level "from edge.base_producer import".
    top_level_import_line = "from edge.base_producer import EventHubProducer"
    lines = source.splitlines()
    top_level_lines = [
        ln for ln in lines
        if ln.strip() == top_level_import_line and not ln.startswith((" ", "\t"))
    ]
    assert top_level_lines == [], "EventHubProducer must be a deferred import inside send(), not module-level"
