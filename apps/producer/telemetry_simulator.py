"""
Telemetry Simulator

Generates realistic vehicle telemetry for Azure Event Hub.
"""

from __future__ import annotations

import random
import uuid
from datetime import datetime, UTC


class VehicleTelemetryGenerator:
    """
    Generates mock vehicle telemetry.
    """

    VEHICLES = [
        "CAR-001",
        "CAR-002",
        "CAR-003",
        "CAR-004",
        "CAR-005",
    ]

    DRIVERS = [
        "DRV-101",
        "DRV-102",
        "DRV-103",
        "DRV-104",
        "DRV-105",
    ]

    def generate(self) -> dict:

        return {

            "eventId": str(uuid.uuid4()),

            "vehicleId": random.choice(self.VEHICLES),

            "driverId": random.choice(self.DRIVERS),

            "timestamp": datetime.now(UTC).isoformat(),

            "location": {
                "latitude": round(
                    random.uniform(43.42, 43.55), 6
                ),
                "longitude": round(
                    random.uniform(-79.79, -79.62), 6
                ),
            },

            "speedKmh": random.randint(0, 120),

            "heading": random.randint(0, 359),

            "fuelLevelPercent": random.randint(15, 100),

            "engineTemperatureC": round(
                random.uniform(78.0, 104.0),
                1
            ),

            "batteryVoltage": round(
                random.uniform(12.2, 14.4),
                2
            ),

            "odometerKm": round(
                random.uniform(1000, 90000),
                1
            ),

            "ignition": random.choice(
                [True, True, True, False]
            )
        }