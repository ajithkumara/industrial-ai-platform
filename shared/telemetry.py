"""
Shared Telemetry Schema

Defines the domain-agnostic Generic Envelope used by the producer and consumer.
Any asset type (vehicle, machine, sensor) is supported via the `payload` field.

Author: Ajith Kumara
Project: Industrial AI Platform
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class TelemetryEvent(BaseModel):
    """
    Generic telemetry envelope.

    All asset types share this outer envelope.  Asset-specific data lives
    inside `payload` as an arbitrary dict so the consumer remains
    domain-agnostic — it validates structure, not content.

    Fields
    ------
    event_id : str
        UUID that uniquely identifies this event.
    device_id : str
        Identifier of the device / sensor that emitted the event.
    asset_type : str
        Category of the asset (e.g. 'vehicle', 'cnc_machine', 'wind_turbine').
    timestamp : str
        ISO-8601 UTC timestamp of when the event was recorded on the device.
    priority : str
        Routing priority: 'low' | 'normal' | 'high' | 'critical'.
    schema_version : str
        Semantic version of this envelope schema (e.g. '1.0.0').
    payload : dict[str, Any]
        Asset-specific telemetry fields — unvalidated at the envelope level.
    """

    event_id: str = Field(..., description="UUID for the event")
    device_id: str = Field(..., description="Source device / sensor ID")
    asset_type: str = Field(..., description="Asset category")
    timestamp: str = Field(..., description="ISO-8601 UTC timestamp")
    priority: str = Field(
        default="normal",
        description="Routing priority: low | normal | high | critical",
    )
    schema_version: str = Field(
        default="1.0.0",
        description="Envelope schema version",
    )
    payload: dict[str, Any] = Field(
        default_factory=dict,
        description="Asset-specific telemetry fields",
    )

    model_config = {"extra": "forbid"}
