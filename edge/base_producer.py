"""
Azure Event Hub Producer

Handles sending telemetry events to Azure Event Hub.

Author: Ajith Kumara
Project: Azure Telemetry Platform
"""

from __future__ import annotations

import json
import logging
from typing import Final

from azure.eventhub import EventData, EventHubProducerClient

from config.settings import settings, validate_settings


class EventHubProducer:
    """
    Sends telemetry events to Azure Event Hub.

    Responsibilities
    ----------------
    - Create Event Hub batches
    - Serialize telemetry events
    - Send batches
    """

    def __init__(self) -> None:
        validate_settings()

        self._logger = logging.getLogger(__name__)

        self._producer = EventHubProducerClient.from_connection_string(
            conn_str=settings.eventhub.connection_string,
            eventhub_name=settings.eventhub.hub_name,
        )
        print("🚀 PRODUCER STARTING...")
        print("Namespace:", settings.eventhub.connection_string.split(";")[1])
        print("EventHub:", settings.eventhub.hub_name)
        print("ConsumerGroup N/A (producer)")
        self._logger.info(
            "Connected to Event Hub '%s'.",
            settings.eventhub.hub_name,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _to_event_data(event: dict) -> EventData:
        """
        Convert a Python dictionary into an EventData object.
        """

        payload = json.dumps(
            event,
            separators=(",", ":"),
            ensure_ascii=False,
        )

        return EventData(payload)

    # ------------------------------------------------------------------
    # Public methods
    # ------------------------------------------------------------------

    def send_events(self, events: list[dict]) -> None:
        """
        Send a batch of telemetry events.

        Parameters
        ----------
        events : list[dict]
            List of telemetry events.
        """

        if not events:
            self._logger.warning("No telemetry events to send.")
            return

        batch = self._producer.create_batch()

        for event in events:
            batch.add(self._to_event_data(event))

        self._producer.send_batch(batch)

        self._logger.info(
            "Successfully sent %d event(s) to Event Hub '%s'.",
            len(events),
            settings.eventhub.hub_name,
        )

    def close(self) -> None:
        """
        Close the Event Hub producer.
        """

        self._producer.close()

        self._logger.info(
            "Event Hub producer closed."
        )
