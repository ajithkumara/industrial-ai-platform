"""
Azure Event Hub Consumer Application (Phase 1 Refactor)

Receives domain-agnostic telemetry events from Azure Event Hub,
validates them using Pydantic, routes invalid events to a Dead Letter Queue (DLQ),
and writes valid events to ADLS Gen2 Bronze via BatchBuffer.
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
# Event handler
# ---------------------------------------------------------------------------

def on_event(partition_context, event) -> None:
    event_body = event.body_as_str(encoding="UTF-8")
    
    # 1. SCHEMA VALIDATION (The Enterprise Contract)
    try:
        record = TelemetryEvent.model_validate_json(event_body)
        
    except ValidationError as ve:
        # DEAD LETTER QUEUE: Data is structurally invalid
        logger.warning(f"Schema validation failed. Routing to DLQ. Error: {ve}")
        storage_client.write_to_dlq(event_body, str(ve))
        update_and_return(partition_context, event)
        return
        
    except json.JSONDecodeError as je:
        # DEAD LETTER QUEUE: Data isn't even valid JSON
        logger.warning(f"Invalid JSON. Routing to DLQ. Error: {je}")
        storage_client.write_to_dlq(event_body, str(je))
        update_and_return(partition_context, event)
        return

    # 2. DOMAIN-AGNOSTIC LOGGING
    logger.info(
        "Received event | Partition: %s | Asset: %s | Device: %s | Priority: %s | EventID: %s",
        partition_context.partition_id,
        record.asset_type,
        record.device_id,
        record.priority,
        record.event_id[:8] # Log first 8 chars of UUID to keep logs clean
    )

    # 3. BUFFER FOR BRONZE (ADLS Gen2)
    #
    # NOTE: batch_buffer.add() may trigger a synchronous flush() to ADLS once
    # RAW_BATCH_SIZE events have accumulated. If that flush fails (e.g. ADLS
    # write error), the event is structurally VALID but NOT YET PERSISTED.
    # It must NOT be routed to the DLQ (it is not malformed data) and the
    # checkpoint must NOT be advanced (doing so would silently skip past
    # data that was never durably written, causing data loss on restart).
    # The event remains buffered in-memory and will be retried on the next
    # successful flush.
    try:
        batch_buffer.add(record.model_dump())
    except Exception as e:
        logger.error(
            "Failed to persist buffered batch while adding event %s: %s. "
            "Checkpoint will NOT be advanced; buffered events remain "
            "in-memory for retry on the next flush.",
            record.event_id,
            e,
        )
        return

    # 4. UPDATE CHECKPOINT — only after the event has been successfully
    # buffered/persisted (no exception raised above).
    update_and_return(partition_context, event)


def update_and_return(partition_context, event):
    """Helper to update checkpoint and return."""
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
    batch_buffer = BatchBuffer(storage_client)

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
        batch_buffer.flush()
    except Exception as e:
        logger.error("Consumer error: %s", e)


if __name__ == "__main__":
    main()