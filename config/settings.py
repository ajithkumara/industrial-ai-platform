"""
Application configuration.

Loads configuration from the .env file and exposes a single immutable
settings object that can be shared throughout the application.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

# ---------------------------------------------------------------------
# Base paths
# ---------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")

LOGS_DIR = BASE_DIR / "logs"
DATA_DIR = BASE_DIR / "data"

LOGS_DIR.mkdir(exist_ok=True)
DATA_DIR.mkdir(exist_ok=True)

CHECKPOINT_FILE = DATA_DIR / "checkpoints.json"
LOCAL_FALLBACK_DIR = DATA_DIR / "telemetry-data"

# ---------------------------------------------------------------------
# Configuration Models
# ---------------------------------------------------------------------


@dataclass(frozen=True)
class EventHubSettings:
    connection_string: str
    hub_name: str
    consumer_group: str


@dataclass(frozen=True)
class StorageSettings:
    account_name: str
    connection_string: str
    filesystem_name: str
    raw_folder: str
    raw_batch_size: int


@dataclass(frozen=True)
class NatsSettings:
    url: str
    bearing_sensor_subject: str
    bearing_inference_subject: str
    orchestrator_mode_subject: str
    context_snapshot_subject: str


@dataclass(frozen=True)
class AppSettings:
    eventhub: EventHubSettings
    storage: StorageSettings
    consumer_batch_size: int
    nats: NatsSettings


# ---------------------------------------------------------------------
# Build Settings Object
# ---------------------------------------------------------------------

settings = AppSettings(

    eventhub=EventHubSettings(

        connection_string=os.getenv(
            "EVENTHUB_CONNECTION_STRING", ""
        ),

        hub_name=os.getenv(
            "EVENTHUB_NAME", ""
        ),

        consumer_group=os.getenv(
            "CONSUMER_GROUP",
            "$Default",
        ),
    ),

    storage=StorageSettings(

        account_name=os.getenv(
            "STORAGE_ACCOUNT_NAME", ""
        ),

        connection_string=os.getenv(
            "STORAGE_CONNECTION_STRING", ""
        ),

        filesystem_name=os.getenv(
            "FILESYSTEM_NAME",
            "raw",
        ),

        raw_folder=os.getenv(
            "RAW_FOLDER",
            "raw/telemetry",
        ),

        raw_batch_size=int(
            os.getenv("RAW_BATCH_SIZE", "20")
        ),
    ),

    consumer_batch_size=int(
        os.getenv(
            "CONSUMER_BATCH_SIZE",
            "20",
        )
    ),

    # NATS -> Event Hub bridge settings (edge/nats_bearing_bridge.py), used
    # to bring adaptive-edge-orchestrator's bearing sensor/inference events
    # into this pipeline as new config-driven asset types. Kept out of
    # validate_settings() below deliberately -- unrelated to the core
    # consumer/edge producer path, so people not running the bridge
    # shouldn't be forced to configure it.
    #
    # ASSUMPTION (unverified -- built from pasted payload examples only,
    # no access to the adaptive-edge-orchestrator repo): subject names
    # below are guesses. sensors.bearing was stated explicitly; the
    # inference subject was not, "inference.bearing" is a placeholder.
    # Confirm both against the real sensor_replay.py / inference_engine.py
    # publish calls before running the bridge.
    nats=NatsSettings(
        url=os.getenv("NATS_URL", "nats://localhost:4222"),
        bearing_sensor_subject=os.getenv(
            "NATS_BEARING_SENSOR_SUBJECT", "sensors.bearing"
        ),
        bearing_inference_subject=os.getenv(
            "NATS_BEARING_INFERENCE_SUBJECT", "inference.bearing"
        ),
        # Mode transitions and context snapshots -- see Architecture v1.0
        # Section 3.3's topic table. Subject names UNVERIFIED against the
        # real repo, same caveat as the two subjects above.
        orchestrator_mode_subject=os.getenv(
            "NATS_ORCHESTRATOR_MODE_SUBJECT", "orchestrator.mode"
        ),
        context_snapshot_subject=os.getenv(
            "NATS_CONTEXT_SNAPSHOT_SUBJECT", "context.snapshot"
        ),
    ),
)


# ---------------------------------------------------------------------
# Consumer-specific connection string
# Uses EVENTHUB_CONSUMER_CONNECTION_STRING (telemetry-reader / Listen policy).
# Falls back to EVENTHUB_CONNECTION_STRING if not set.
# ---------------------------------------------------------------------

CONSUMER_CONNECTION_STRING: str = (
    os.getenv("EVENTHUB_CONSUMER_CONNECTION_STRING")
    or os.getenv("EVENTHUB_CONNECTION_STRING", "")
)

# ---------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------


def validate_settings() -> None:
    """
    Validate all required application settings.
    """

    missing = []

    if not settings.eventhub.connection_string:
        missing.append("EVENTHUB_CONNECTION_STRING")

    if not settings.eventhub.hub_name:
        missing.append("EVENTHUB_NAME")

    if not settings.storage.account_name:
        missing.append("STORAGE_ACCOUNT_NAME")

    if not settings.storage.connection_string:
        missing.append("STORAGE_CONNECTION_STRING")

    if not settings.storage.filesystem_name:
        missing.append("FILESYSTEM_NAME")

    if missing:
        raise ValueError(
            f"Missing configuration values: {', '.join(missing)}"
        )


# NOTE: validate_settings() is intentionally NOT called automatically at
# import time here. This module is imported transitively by almost every
# package in the repo (consumer/, edge/, tests/), including in CI and unit
# test contexts where no real Azure credentials are present. Previously,
# `validate_settings()` ran unconditionally on import, which meant simply
# importing `config.settings` (e.g. via `import consumer.batch_buffer`)
# raised ValueError outside a fully-configured environment, breaking
# `python -m pytest tests/` in CI. Entry points that require fully-populated
# settings (e.g. edge.base_producer.EventHubProducer.__init__,
# consumer.eventhub_consumer.main) call validate_settings() explicitly.