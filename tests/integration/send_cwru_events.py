"""
Sender for real CWRU dataset events built by ml/cwru_loader.py.

Flow (mandatory, not optional):

    DRY RUN (always runs first, no network connection made)
        -> print recordings, classes, splits, event count, payload size
    EXPLICIT CONFIRMATION (only when --send is passed)
        -> typed "yes" required, unless --yes is also passed
    BATCHED EVENT HUB SEND
        -> chunked by serialized byte size, not just event count, since
           2,245 real events at ~450-600 bytes each can exceed a single
           1 MB Event Hub batch (unlike the 181-event synthetic run)

Every event sent carries dataset_run_id (default: ml.cwru_loader.DATASET_RUN_ID)
so this run is queryable separately from synthetic acceptance-test data
already sitting in the same Bronze/Silver/Gold tables -- see
config/asset_types/bearing_sensor.yml and docs/runbooks/CLOUD_ACCEPTANCE_RUNBOOK.md.

Usage:
    python -m tests.integration.send_cwru_events                # dry run only
    python -m tests.integration.send_cwru_events --send         # dry run, then prompts, then sends
    python -m tests.integration.send_cwru_events --send --yes   # dry run, then sends without prompting
"""

from __future__ import annotations

import argparse
import json
import sys

from ml import cwru_loader as loader

# Conservative headroom under Event Hub's standard-tier 1 MiB batch limit;
# EventData framing overhead means the raw JSON byte budget must stay
# below the hard limit, not equal to it.
DEFAULT_MAX_BATCH_BYTES = 900_000


def _serialized_size(event: dict) -> int:
    """Matches EventHubProducer._to_event_data's exact serialization convention."""
    return len(
        json.dumps(event, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    )


def chunk_events_by_size(
    events: list[dict], max_bytes: int = DEFAULT_MAX_BATCH_BYTES
) -> list[list[dict]]:
    """
    Greedily pack events into batches so each batch's total serialized size
    stays under max_bytes. Pure function, no network calls -- fully
    testable offline.
    """
    if not events:
        return []

    batches: list[list[dict]] = []
    current: list[dict] = []
    current_size = 0

    for event in events:
        size = _serialized_size(event)
        if size > max_bytes:
            raise ValueError(
                f"Single event ({size} bytes) exceeds max_bytes ({max_bytes}) "
                f"on its own -- cannot batch it. event_id={event.get('event_id')}"
            )
        if current and current_size + size > max_bytes:
            batches.append(current)
            current = []
            current_size = 0
        current.append(event)
        current_size += size

    if current:
        batches.append(current)

    return batches


def total_payload_bytes(events: list[dict]) -> int:
    return sum(_serialized_size(e) for e in events)


def print_dry_run(events: list[dict], summary, splits, max_bytes: int) -> None:
    loader.print_summary(summary, splits)
    total_bytes = total_payload_bytes(events)
    batches = chunk_events_by_size(events, max_bytes)
    print()
    print(f"dataset_run_id:      {events[0]['payload']['dataset_run_id'] if events else '(none)'}")
    print(f"recordings:          {len(summary)}")
    print(f"events (windows):    {len(events)}")
    print(f"total payload size:  {total_bytes:,} bytes ({total_bytes / 1024:.1f} KiB)")
    print(f"batches required:    {len(batches)} (max {max_bytes:,} bytes/batch)")
    print(
        f"\nNOTE: {len(events)} windows from {len(summary)} independent "
        f"recordings -- the recording is the unit of independence, not "
        f"the window. See ml/cwru_loader.py module docstring."
    )


def send(events: list[dict], max_bytes: int) -> None:
    from edge.base_producer import EventHubProducer  # deferred: requires Azure config

    batches = chunk_events_by_size(events, max_bytes)
    producer = EventHubProducer()
    try:
        for i, batch in enumerate(batches, start=1):
            print(f"Sending batch {i}/{len(batches)} ({len(batch)} events)...")
            producer.send_events(batch)
        print(f"Done. Sent {len(events)} events in {len(batches)} batch(es).")
    finally:
        producer.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--send", action="store_true", help="Actually send after the dry run (default: dry run only).")
    parser.add_argument("--yes", action="store_true", help="Skip the typed confirmation prompt (still requires --send).")
    parser.add_argument("--dataset-run-id", default=loader.DATASET_RUN_ID, help=f"Default: {loader.DATASET_RUN_ID}")
    parser.add_argument("--max-batch-bytes", type=int, default=DEFAULT_MAX_BATCH_BYTES)
    args = parser.parse_args()

    events, summary = loader.build_events(dataset_run_id=args.dataset_run_id)
    splits = loader.assign_splits([r.source_file for r in summary])

    print_dry_run(events, summary, splits, args.max_batch_bytes)

    if not args.send:
        print("\nDry run only (pass --send to actually transmit). Nothing was sent.")
        return

    if not args.yes:
        print(
            f"\nAbout to send {len(events)} REAL events with "
            f"dataset_run_id='{args.dataset_run_id}' to Event Hub."
        )
        confirmation = input("Type 'yes' to proceed: ").strip().lower()
        if confirmation != "yes":
            print("Not confirmed. Nothing was sent.")
            sys.exit(1)

    send(events, args.max_batch_bytes)


if __name__ == "__main__":
    main()
