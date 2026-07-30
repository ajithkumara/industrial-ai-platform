from dataclasses import dataclass, asdict, field
import json


@dataclass
class TelemetryRecord:
    """
    Matches the payload emitted by VehicleTelemetryGenerator.
    """

    eventId: str
    vehicleId: str
    driverId: str
    timestamp: str
    location: dict
    speedKmh: float
    heading: int
    fuelLevelPercent: int
    engineTemperatureC: float
    batteryVoltage: float
    odometerKm: float
    ignition: bool

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict())

    @classmethod
    def from_dict(cls, data: dict) -> "TelemetryRecord":
        return cls(
            eventId=data.get("eventId", ""),
            vehicleId=data.get("vehicleId", ""),
            driverId=data.get("driverId", ""),
            timestamp=data.get("timestamp", ""),
            location=data.get("location", {}),
            speedKmh=float(data.get("speedKmh", 0)),
            heading=int(data.get("heading", 0)),
            fuelLevelPercent=int(data.get("fuelLevelPercent", 0)),
            engineTemperatureC=float(data.get("engineTemperatureC", 0)),
            batteryVoltage=float(data.get("batteryVoltage", 0)),
            odometerKm=float(data.get("odometerKm", 0)),
            ignition=bool(data.get("ignition", False)),
        )

    @classmethod
    def from_json(cls, json_str: str) -> "TelemetryRecord":
        return cls.from_dict(json.loads(json_str))
