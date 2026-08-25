"""
Manual smoke-test script: run directly (`python tests/test_send.py`) to send
a single test event to the real Azure Event Hub.

NOTE: guarded behind __main__ (requires real Event Hub credentials and
performs a live send) so pytest collection doesn't attempt this during CI.
"""

from config.logging import configure_logging
from edge.base_producer import EventHubProducer

if __name__ == "__main__":
    configure_logging()

    print("1. Creating producer...")

    producer = EventHubProducer()

    print("2. Producer created.")

    print("3. Sending event...")

    producer.send_events([
        {
            "message": "Hello Azure!",
            "course": "Cloud Computing",
            "student": "Ajith",
        }
    ])

    print("4. Event sent.")

    producer.close()

    print("5. Producer closed.")