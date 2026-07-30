from azure.eventhub import EventHubConsumerClient
from config.settings import settings

print("\n==============================")
print("🚀 CONSUMER STARTING")
print("==============================")

print("Namespace:", settings.eventhub.connection_string.split(";")[1])
print("EventHub:", settings.eventhub.hub_name)
print("ConsumerGroup:", "$Default")
print("==============================\n")


def on_event(partition_context, event):
    print("\n🔥🔥 EVENT RECEIVED 🔥🔥")
    print("Partition :", partition_context.partition_id)
    print("Offset    :", event.offset)
    print("Sequence  :", event.sequence_number)
    print("Body      :", event.body_as_str())
    print("==============================\n")

    # checkpoint (important for proper streaming)
    partition_context.update_checkpoint(event)


client = EventHubConsumerClient.from_connection_string(
    conn_str=settings.eventhub.connection_string,
    consumer_group="$Default",
    eventhub_name=settings.eventhub.hub_name,
)

print("👂 Listening for events...\n")

with client:
    client.receive(
        on_event=on_event,
        starting_position="@latest",
        prefetch=1,
    )