from config.logging import configure_logging

configure_logging()

from producer.eventhub_producer import EventHubProducer

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