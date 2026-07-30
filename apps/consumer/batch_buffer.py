"""
Batch Buffer

Collects telemetry events and writes them to ADLS in batches.
"""

from __future__ import annotations

import logging
from typing import Any

from consumer.storage_client import StorageClient
from config.settings import settings


class BatchBuffer:
    """
    Buffers telemetry events before writing to ADLS.
    """

    def __init__(self, storage_client: StorageClient):

        self._logger = logging.getLogger(__name__)

        self._storage_client = storage_client

        self._buffer: list[dict[str, Any]] = []

        self._batch_size = settings.storage.raw_batch_size

    def add(self, event: dict[str, Any]) -> None:
        """
        Add an event to the buffer.
        """

        self._buffer.append(event)

        self._logger.info(
            "Buffered %d/%d events",
            len(self._buffer),
            self._batch_size,
        )

        if len(self._buffer) >= self._batch_size:
            self.flush()

    def flush(self) -> None:
        """
        Write buffered events to ADLS.
        """

        if not self._buffer:
            return

        self._logger.info(
            "Writing %d events to ADLS...",
            len(self._buffer),
        )

        self._storage_client.upload_batch(self._buffer)

        self._buffer.clear()

        self._logger.info("Batch written successfully.")

    def pending_events(self) -> int:
        """
        Returns number of events currently buffered.
        """

        return len(self._buffer)