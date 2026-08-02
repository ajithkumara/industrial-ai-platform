"""
eventhub_consumer.py — RETIRED

This module has been superseded by apps/consumer/consumer.py,
which handles Event Hub reception, Pydantic validation, DLQ routing,
and file-based checkpointing directly via EventHubConsumerClient.

Do NOT import EventHubConsumer from here. It is kept only to preserve
git history. The class below will raise NotImplementedError if instantiated.
"""

from __future__ import annotations


class EventHubConsumer:
    """
    DEPRECATED — use apps/consumer/consumer.py instead.
    """

    def __init__(self) -> None:
        raise NotImplementedError(
            "EventHubConsumer is retired. "
            "Run 'python -m apps.consumer.consumer' instead."
        )