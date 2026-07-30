"""
Main Producer Application
python -m producer.producer

"""

from __future__ import annotations

import logging
import time

from producer.telemetry_simulator import (
    VehicleTelemetryGenerator
)

from producer.eventhub_producer import (
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