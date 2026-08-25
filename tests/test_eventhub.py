"""
Manual smoke-test script: run directly (`python tests/test_eventhub.py`) to
verify a live connection can be established to the Azure Event Hub.

NOTE: guarded behind __main__ (requires real Event Hub credentials) so
pytest collection doesn't attempt a live network connection during CI.
"""

from edge.base_producer import EventHubProducer

if __name__ == "__main__":
    producer = EventHubProducer()

    print("Connected successfully.")

    producer.close()

    print("Closed successfully.")