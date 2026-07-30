"""
Azure Event Hub Consumer

Receives telemetry events from Azure Event Hub.
"""

from __future__ import annotations

import json
import logging
from typing import Callable

from azure.eventhub import EventData
from azure.eventhub import EventHubConsumerClient

from config.settings import settings, validate_settings


class EventHubConsumer:
    """
    Wrapper around Azure EventHubConsumerClient.

    Responsibilities
    ----------------
    - Connect to Event Hub
    - Receive events
    - Deserialize JSON
    - Pass Python dictionaries to a callback

    Does NOT:
    - Write to storage
    - Batch events
    - Perform checkpointing (added later)
    """

    def __init__(self) -> None:

        validate_settings()

        self._logger = logging.getLogger(__name__)

        self._client = EventHubConsumerClient.from_connection_string(
            conn_str=settings.eventhub.connection_string,
            consumer_group=settings.eventhub.consumer_group,
            eventhub_name=settings.eventhub.hub_name,
        )

        self._logger.info(
            "Connected to Event Hub '%s'",
            settings.eventhub.hub_name,
        )

    def receive(
        self,
        on_event_callback: Callable[[dict], None],
    ) -> None:
        """
        Start receiving events forever.

        Parameters
        ----------
        on_event_callback:
            Function called for every event.
            Receives a Python dictionary.
        """

        def _on_event(
            partition_context,
            event: EventData,
        ) -> None:

            try:

                payload = json.loads(
                    event.body_as_str(encoding="UTF-8")
                )

                self._logger.info(
                    "Received event %s",
                    payload.get("eventId", "<unknown>"),
                )

                on_event_callback(payload)

            except Exception:
                self._logger.exception(
                    "Failed to process Event Hub message."
                )

        self._logger.info("Waiting for telemetry events...")

        self._client.receive(
            on_event=_on_event,
            starting_position="-1",   # Read only new events after the consumer starts
        )

    def close(self) -> None:

        self._client.close()

        self._logger.info(
            "Event Hub consumer closed."
        )