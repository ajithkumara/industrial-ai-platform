"""
Edge Simulator Entry Point
python -m edge.run_simulator

"""

from __future__ import annotations

import logging
import time

from .vehicle_producer import (
    VehicleTelemetryGenerator
)

from .base_producer import (
    EventHubProducer
)


logging.basicConfig(

    level=logging.INFO,

    format=(
        "%(asctime)s | "
        "%(levelname)s | "
        "%(message)s"
    )
)


logger = logging.getLogger(__name__)


def main():

    logger.info("Starting Producer...")

    generator = VehicleTelemetryGenerator()

    producer = EventHubProducer()

    try:

        while True:

            telemetry = generator.generate()

            logger.info(telemetry)

            producer.send_events(
                [telemetry]
            )

            time.sleep(3)

    except KeyboardInterrupt:

        logger.info(
            "Stopping Producer..."
        )

    finally:

        producer.close()


if __name__ == "__main__":

    main()