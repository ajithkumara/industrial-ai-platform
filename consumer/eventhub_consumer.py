"""
Azure Event Hub Consumer Application (Phase 1 Refactor)

Receives domain-agnostic telemetry events from Azure Event Hub,
validates them using Pydantic, routes invalid events to a Dead Letter Queue (DLQ),
and writes valid events to ADLS Gen2 Bronze via BatchBuffer.

P0-01 FIX — checkpoint ordering
================================
The previous implementation called update_checkpoint() inside on_event()
immediately after batch_buffer.add() returned, regardless of whether a
flush had occurred.  For events that were only buffered (not yet flushed),
this advanced the checkpoint past data that was still only in memory.  A
process crash between the add() and the next flush() permanently lost
those events.

The fix: checkpoint_fn is injected into BatchBuffer.  BatchBuffer calls it
only after upload_batch() confirms the write, once per partition, using the
last offset in the flushed batch.  on_event() no longer calls
update_checkpoint() for buffered events at all.

DLQ events (validation failures) still checkpoint immediately because
StorageClient.write_to_dlq() writes synchronously before on_event returns.
That path is correct and unchanged.

Delivery semantics
------------------
- At-least-once: on crash + restart, events since the last flushed
  checkpoint are re-read from Event Hubs and re-written to ADLS.
- Silver deduplication by event_id makes replay idempotent.
- Loss window: zero for crashes that happen after the last successful flush.
  A process crash with buffered-but-unflushed events causes those events to
  be re-delivered on restart, not lost.  (Previously: they were lost.)
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from azure.eventhub import EventHubConsumerClient
from pydantic import ValidationError

from config.settings import (
    CONSUMER_CONNECTION_STRING,
    settings,
    validate_settings,
)
from .batch_buffer import BatchBuffer
from .checkpoint import FileCheckpointManager
from .storage_client import StorageClient
from shared.telemetry_event import TelemetryEvent
from shared.logger import setup_logger

# ---------------------------------------------------------------------------
# Module-level singletons
#
# BUGFIX: checkpoint_manager/storage_client/batch_buffer were previously
# constructed here, at module import time. StorageClient.__init__ opens a
# real Azure Data Lake connection (DataLakeServiceClient.from_connection_string)
# using settings.storage.connection_string, which raises ValueError when
# that setting is empty/malformed. Since config/settings.py no longer
# validates configuration on import (see that module's Phase 5 fix), simply
# `import consumer.eventhub_consumer` — e.g. from a test file, from `python
# -c`, or from any tool that transitively imports this module without a
# real .env/production credentials present — used to crash before ever
# reaching main()'s explicit validate_settings() call. These singletons are
# now created lazily inside main(), the same explicit entry point that
# already owns configuration validation, so importing this module is safe
# in CI/tests, and construction still happens exactly once before the
# consumer starts receiving events.
# ---------------------------------------------------------------------------

logger = setup_logger(
    "consumer",
    # LOGS_DIR / "consumer.log", # Ensure LOGS_DIR is defined in your settings
)

# For local dev, file-based checkpoints are fine.
# In production, Databricks Structured Streaming handles checkpoints natively.
checkpoint_manager: FileCheckpointManager | None = None
storage_client: StorageClient | None = None
batch_buffer: BatchBuffer | None = None


# ---------------------------------------------------------------------------
# Checkpoint callback (injected into BatchBuffer — P0-01 fix)
# ---------------------------------------------------------------------------

def _do_checkpoint(partition_id: str, offset: str, sequence_number: int) -> None:
    """
    Called by BatchBuffer.flush() after a batch has been durably written.

    This is the ONLY place where Event Hub offsets are advanced for buffered
    events.  It is never called for events that are merely in the in-memory
    buffer.
    """
    checkpoint_manager.update_checkpoint(
        partition_id=partition_id,
        offset=offset,
        sequence_number=sequence_number,
    )


# ---------------------------------------------------------------------------
# Event handler
# ---------------------------------------------------------------------------

def on_event(partition_context, event) -> None:
    event_body = event.body_as_str(encoding="UTF-8")

    # 1. SCHEMA VALIDATION (The Enterprise Contract)
    try:
        record = TelemetryEvent.model_validate_json(event_body)

    except ValidationError as ve:
        # DEAD LETTER QUEUE: Data is structurally invalid.
        # write_to_dlq() is synchronous — the DLQ file is durable before we
        # return.  It is safe to checkpoint immediately here.
        logger.warning(f"Schema validation failed. Routing to DLQ. Error: {ve}")
        storage_client.write_to_dlq(event_body, str(ve))
        _checkpoint_event(partition_context, event)
        return

    except json.JSONDecodeError as je:
        # DEAD LETTER QUEUE: Data isn't even valid JSON.
        logger.warning(f"Invalid JSON. Routing to DLQ. Error: {je}")
        storage_client.write_to_dlq(event_body, str(je))
        _checkpoint_event(partition_context, event)
        return

    # 2. DOMAIN-AGNOSTIC LOGGING
    logger.info(
        "Received event | Partition: %s | Asset: %s | Device: %s | Priority: %s | EventID: %s",
        partition_context.partition_id,
        record.asset_type,
        record.device_id,
        record.priority,
        record.event_id[:8]  # Log first 8 chars of UUID to keep logs clean
    )

    # 3. BUFFER FOR BRONZE (ADLS Gen2)
    #
    # P0-01 FIX: batch_buffer.add() now stores the event's partition metadata
    # (partition_id, offset, sequence_number) alongside the event dict.
    # BatchBuffer.flush() uses those to checkpoint the last offset per
    # partition AFTER upload_batch() confirms the write.
    #
    # Crucially: on_event does NOT call any checkpoint function here.
    # The checkpoint is advanced inside BatchBuffer.flush() only — meaning
    # only after the batch is durably in ADLS.
    #
    # If flush() raises (e.g. ADLS write error), the exception propagates,
    # the buffer is not cleared, and the checkpoint is not advanced.  The
    # same events will be retried on the next flush().
    try:
        batch_buffer.add(
            event=record.model_dump(),
            partition_id=partition_context.partition_id,
            offset=event.offset,
            sequence_number=event.sequence_number,
        )
    except Exception as e:
        logger.error(
            "Failed to persist buffered batch while adding event %s: %s. "
            "Checkpoint will NOT be advanced; buffered events remain "
            "in-memory for retry on the next flush.",
            record.event_id,
            e,
        )
        # Do NOT call _checkpoint_event here — the write failed.
        return

    # NOTE: No checkpoint call here.  See P0-01 fix explanation above.
    # The checkpoint is issued by BatchBuffer.flush() after durable write.


def _checkpoint_event(partition_context, event) -> None:
    """
    Advance the checkpoint for a single event whose durability is already
    guaranteed (DLQ write confirmed, or shutdown flush confirmed).

    This replaces the old update_and_return() helper, with a name that
    makes the caller's intent explicit.
    """
    checkpoint_manager.update_checkpoint(
        partition_id=partition_context.partition_id,
        offset=event.offset,
        sequence_number=event.sequence_number,
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    # Fail fast if required configuration is missing. (config.settings no
    # longer validates automatically on import — see config/settings.py.)
    validate_settings()

    # Construct the live-credential-requiring singletons here (see the
    # "Module-level singletons" comment above for why this moved out of
    # module scope) — after validate_settings() has already confirmed the
    # required configuration is present.
    global checkpoint_manager, storage_client, batch_buffer
    checkpoint_manager = FileCheckpointManager("local/checkpoints.json")
    storage_client = StorageClient()

    # P0-01 FIX: inject _do_checkpoint so BatchBuffer can checkpoint after
    # each successful flush, not after each add().
    batch_buffer = BatchBuffer(storage_client, checkpoint_fn=_do_checkpoint)

    logger.info("Starting consumer for Event Hub '%s'...", settings.eventhub.hub_name)
    logger.info("Consumer Group: %s", settings.eventhub.consumer_group)

    consumer = EventHubConsumerClient.from_connection_string(
        conn_str=CONSUMER_CONNECTION_STRING,
        consumer_group=settings.eventhub.consumer_group,
        eventhub_name=settings.eventhub.hub_name,
    )

    # Resume from saved checkpoints if available.
    # Fall back to "@latest" (new events only) when no checkpoint exists.
    # Use "-1" here only if you want to replay ALL history on first start.
    starting_positions = "@latest"
    try:
        stored_checkpoints = checkpoint_manager.checkpoints
        if stored_checkpoints:
            starting_positions = {
                pid: cp["offset"]
                for pid, cp in stored_checkpoints.items()
            }
            logger.info("Resuming partitions from checkpoints: %s", starting_positions)
        else:
            logger.info("No checkpoints found. Starting from @latest (new events only).")
    except Exception as e:
        logger.warning("Could not build starting positions: %s. Defaulting to @latest.", e)

    try:
        with consumer:
            logger.info("Waiting for events...")
            consumer.receive(
                on_event=on_event,
                starting_position=starting_positions,
            )
    except KeyboardInterrupt:
        logger.info("Consumer stopped by user.")
        # Flush any buffered events before exiting.
        # BatchBuffer.flush() will checkpoint after the write confirms.
        batch_buffer.flush()
    except Exception as e:
        logger.error("Consumer error: %s", e)


if __name__ == "__main__":
    main()
