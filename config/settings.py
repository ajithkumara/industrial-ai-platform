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
class AppSettings:
    eventhub: EventHubSettings
    storage: StorageSettings
    consumer_batch_size: int


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