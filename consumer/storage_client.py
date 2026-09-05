"""
Azure Data Lake Storage Client

Handles uploading raw telemetry batches to Azure Data Lake Storage Gen2.

Author: Ajith Kumara
Project: Azure Telemetry Platform
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
UTC = timezone.utc  # compat: datetime.UTC was added in Python 3.11
from pathlib import PurePosixPath
from typing import Final

from azure.storage.filedatalake import DataLakeServiceClient

from config.settings import settings

logger = logging.getLogger(__name__)


class StorageClient:
    """
    Azure Data Lake Storage Gen2 Client.

    Responsibilities
    ----------------
    - Connect to ADLS Gen2
    - Create partition folders
    - Convert telemetry into JSONL
    - Upload telemetry batches

    Does NOT
    --------
    - Read Event Hub
    - Manage checkpoints
    - Validate telemetry records
    """

    def __init__(self) -> None:

        self.raw_folder: str = settings.storage.raw_folder
        self.dlq_folder: str = f"{self.raw_folder}/_dlq"

        logger.info(
            "Connecting to Storage Account '%s'...",
            settings.storage.account_name,
        )

        self.service_client = (
            DataLakeServiceClient.from_connection_string(
                settings.storage.connection_string
            )
        )

        self.file_system = (
            self.service_client.get_file_system_client(
                settings.storage.filesystem_name
            )
        )

        logger.info(
            "Connected to filesystem '%s'.",
            settings.storage.filesystem_name,
        )

    # ----------------------------------------------------------

    @staticmethod
    def _utc_now() -> datetime:
        return datetime.now(UTC)

    # ----------------------------------------------------------

    def _build_directory(self, base_folder: str | None = None) -> str:

        now = self._utc_now()
        folder = base_folder if base_folder is not None else self.raw_folder

        return str(
            PurePosixPath(
                folder,
                f"year={now.year}",
                f"month={now.month:02}",
                f"day={now.day:02}",
            )
        )

    # ----------------------------------------------------------

    def _build_filename(self, prefix: str = "telemetry", ext: str = "jsonl") -> str:

        now = self._utc_now()

        timestamp = now.strftime("%Y%m%d_%H%M%S")

        unique = uuid.uuid4().hex[:8]

        return f"{prefix}_{timestamp}_{unique}.{ext}"

    # ----------------------------------------------------------

    @staticmethod
    def _events_to_jsonl(events: list[dict]) -> bytes:

        lines = [
            json.dumps(
                event,
                separators=(",", ":"),
                ensure_ascii=False,
            )
            for event in events
        ]

        return ("\n".join(lines)).encode("utf-8")

    # ----------------------------------------------------------

    def _ensure_directory(self, directory: str) -> None:
        """Create the ADLS directory if it does not already exist."""
        try:
            self.file_system.get_directory_client(directory).create_directory()
        except Exception:
            pass  # Directory already exists — safe to continue

    # ----------------------------------------------------------

    def upload_batch(
        self,
        events: list[dict],
    ) -> str:
        """
        Upload a telemetry batch to ADLS Gen2 Bronze container.

        Parameters
        ----------
        events : list[dict]
            Telemetry events.

        Returns
        -------
        str
            Uploaded ADLS file path.
        """

        if not events:
            raise ValueError("Telemetry batch is empty.")

        directory = self._build_directory(self.raw_folder)
        filename = self._build_filename(prefix="telemetry", ext="jsonl")
        file_path = str(PurePosixPath(directory, filename))

        logger.info(
            "Uploading %d telemetry event(s)...",
            len(events),
        )

        self._ensure_directory(directory)

        file_client = self.file_system.get_file_client(file_path)
        file_client.upload_data(
            self._events_to_jsonl(events),
            overwrite=True,
        )

        logger.info("Successfully uploaded '%s'", file_path)

        return file_path

    # ----------------------------------------------------------

    def write_to_dlq(self, raw_body: str, error_reason: str) -> str:
        """
        Write a failed / invalid event to the Dead Letter Queue (DLQ).

        The DLQ lives at ``<raw_folder>/_dlq/year=.../month=.../day=.../``
        so it is partitioned identically to the main Bronze data but
        physically isolated for easy discovery and replay.

        Each DLQ file is a single JSON object containing:
        - ``raw_body``     – the original Event Hub message as received
        - ``error_reason`` – the validation / parsing error description
        - ``dlq_timestamp``– UTC timestamp of when the event was rejected

        Parameters
        ----------
        raw_body : str
            The raw Event Hub message body that failed validation.
        error_reason : str
            Human-readable description of why the event was rejected.

        Returns
        -------
        str
            Uploaded ADLS DLQ file path.
        """

        directory = self._build_directory(self.dlq_folder)
        filename = self._build_filename(prefix="dlq", ext="json")
        file_path = str(PurePosixPath(directory, filename))

        dlq_record = json.dumps(
            {
                "raw_body": raw_body,
                "error_reason": error_reason,
                "dlq_timestamp": self._utc_now().isoformat(),
            },
            ensure_ascii=False,
            indent=2,
        ).encode("utf-8")

        logger.warning(
            "Writing rejected event to DLQ: '%s' | Reason: %s",
            file_path,
            error_reason,
        )

        self._ensure_directory(directory)

        file_client = self.file_system.get_file_client(file_path)
        file_client.upload_data(dlq_record, overwrite=True)

        logger.info("DLQ event written to '%s'", file_path)

        return file_path