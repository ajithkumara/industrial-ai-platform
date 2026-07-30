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
from datetime import UTC, datetime
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

    RAW_FOLDER: Final[str] = "bronze"

    def __init__(self) -> None:

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

    def _build_directory(self) -> str:

        now = self._utc_now()

        return str(
            PurePosixPath(
                self.RAW_FOLDER,
                f"year={now.year}",
                f"month={now.month:02}",
                f"day={now.day:02}",
            )
        )

    # ----------------------------------------------------------

    def _build_filename(self) -> str:

        now = self._utc_now()

        timestamp = now.strftime("%Y%m%d_%H%M%S")

        unique = uuid.uuid4().hex[:8]

        return f"telemetry_{timestamp}_{unique}.jsonl"

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

    def upload_batch(
        self,
        events: list[dict],
    ) -> str:
        """
        Upload a telemetry batch to ADLS Gen2.

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

        directory = self._build_directory()

        filename = self._build_filename()

        file_path = str(
            PurePosixPath(
                directory,
                filename,
            )
        )

        logger.info(
            "Uploading %d telemetry event(s)...",
            len(events),
        )

        directory_client = (
            self.file_system.get_directory_client(directory)
        )

        try:
            directory_client.create_directory()
        except Exception:
            # Directory probably already exists
            pass

        file_client = (
            self.file_system.get_file_client(file_path)
        )

        file_client.upload_data(
            self._events_to_jsonl(events),
            overwrite=True,
        )

        logger.info(
            "Successfully uploaded '%s'",
            file_path,
        )

        return file_path