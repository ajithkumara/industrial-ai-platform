"""
Azure Event Hub Consumer Application

Receives telemetry events from Azure Event Hub and writes
them to ADLS Gen2 in batches via BatchBuffer.

Author: Ajith Kumara
Project: Azure Telemetry Platform
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from azure.eventhub import EventHubConsumerClient

from config.settings import (
    CONSUMER_CONNECTION_STRING,
    DATA_DIR,
    LOCAL_FALLBACK_DIR,
    LOGS_DIR,
    settings,
)
from consumer.batch_buffer import BatchBuffer
from consumer.checkpoint import FileCheckpointManager
from consumer.storage_client import StorageClient
from shared.telemetry import TelemetryRecord
from utils.logger import setup_logger

# ---------------------------------------------------------------------------
# Module-level singletons
# ---------------------------------------------------------------------------

logger = setup_logger(
    "consumer",
    LOGS_DIR / "consumer.log",
)

checkpoint_manager = FileCheckpointManager(
    DATA_DIR / "checkpoints.json"
)

storage_client = StorageClient()

batch_buffer = BatchBuffer(storage_client)


# ---------------------------------------------------------------------------
# Event handler
# ---------------------------------------------------------------------------

def on_event(partition_context, event) -> None:
    try:
        event_body = event.body_as_str(encoding="UTF-8")

        record = TelemetryRecord.from_json(event_body)

        logger.info(
            "Received event from Partition %s: vehicle=%s speed=%s km/h ignition=%s",
            partition_context.partition_id,
            record.vehicleId,
            record.speedKmh,
            record.ignition,
        )

        # Buffer the event — flushes automatically when batch is full
        try:
            batch_buffer.add(record.to_dict())

        except Exception:
            # Local fallback when buffering / upload fails
            LOCAL_FALLBACK_DIR.mkdir(parents=True, exist_ok=True)

            filename = (
                f"telemetry_"
                f"{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')}"
                f".json"
            )

            fallback_path = LOCAL_FALLBACK_DIR / filename

            with open(fallback_path, "w") as f:
                f.write(record.to_json())

            logger.info("Saved locally (fallback) to %s", fallback_path)

        # Update checkpoint after every event
        checkpoint_manager.update_checkpoint(
            partition_id=partition_context.partition_id,
            offset=event.offset,
            sequence_number=event.sequence_number,
        )

    except Exception as e:
        logger.error("Error processing event: %s", e)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:

    logger.info(
        "Starting consumer for Event Hub '%s'...",
        settings.eventhub.hub_name,
    )
    logger.info(
        "Consumer Group: %s",
        settings.eventhub.consumer_group,
    )

    consumer = EventHubConsumerClient.from_connection_string(
        conn_str=CONSUMER_CONNECTION_STRING,
        consumer_group=settings.eventhub.consumer_group,
        eventhub_name=settings.eventhub.hub_name,
    )

    # Resume from saved checkpoints if available
    starting_positions = "-1"
    try:
        stored_checkpoints = checkpoint_manager.checkpoints
        if stored_checkpoints:
            starting_positions = {
                pid: cp["offset"]
                for pid, cp in stored_checkpoints.items()
            }
            logger.info(
                "Resuming partitions from checkpoints: %s",
                starting_positions,
            )
    except Exception as e:
        logger.warning(
            "Could not build starting positions: %s. Defaulting to beginning.",
            e,
        )

    try:
        with consumer:
            logger.info("Waiting for events...")
            consumer.receive(
                on_event=on_event,
                starting_position=starting_positions,
            )
    except KeyboardInterrupt:
        logger.info("Consumer stopped by user.")

        # Flush any remaining buffered events before shutdown
        batch_buffer.flush()

    except Exception as e:
        logger.error("Consumer error: %s", e)


if __name__ == "__main__":
    main()
