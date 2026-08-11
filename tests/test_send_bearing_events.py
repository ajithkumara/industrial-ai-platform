"""
Manual smoke-test script: run directly (`python tests/test_send_bearing_events.py`)
to send a handful of bearing_sensor and bearing_inference events to the
real Azure Event Hub, using the exact same translate_sensor_record /
translate_inference_record functions edge/nats_bearing_bridge.py uses --
bypasses NATS entirely (useful when adaptive-edge-orchestrator isn't
running), but exercises the rest of the pipeline (consumer -> ADLS ->
DLT Bronze/Silver) identically to a real NATS-sourced event.

NOTE: guarded behind __main__ (requires real Event Hub credentials and
performs live sends) so pytest collection doesn't attempt this during CI.
"""

from config.logging import configure_logging
from edge.base_producer import EventHubProducer
from edge.nats_bearing_bridge import (
    translate_inference_record,
    translate_sensor_record,
)

# A spread of labels/modes so the resulting Bronze/Silver records actually
# demonstrate something (not just one row repeated) -- normal + each fault
# class from the CWRU label set, across both policy modes the thesis
# compares.
SENSOR_SAMPLES = [
    {
        "ts": "2026-08-11T09:00:00.000Z", "seq": 1, "sensor_id": "bearing.DE",
        "file": "normal_0hp.mat", "label": "normal", "window_idx": 1,
        "features": {"rms": 0.03, "peak": 0.09, "crest": 3.0, "kurtosis": 1.8,
                     "skew": 0.02, "variance": 0.001, "mean_abs": 0.02},
    },
    {
        "ts": "2026-08-11T09:00:01.000Z", "seq": 2, "sensor_id": "bearing.DE",
        "file": "ball_0hp.mat", "label": "ball", "window_idx": 2,
        "features": {"rms": 0.15, "peak": 0.52, "crest": 3.9, "kurtosis": 2.6,
                     "skew": -0.4, "variance": 0.018, "mean_abs": 0.11},
    },
    {
        "ts": "2026-08-11T09:00:02.000Z", "seq": 3, "sensor_id": "bearing.DE",
        "file": "inner_race_0hp.mat", "label": "inner_race", "window_idx": 3,
        "features": {"rms": 0.22, "peak": 0.68, "crest": 4.2, "kurtosis": 3.4,
                     "skew": -0.6, "variance": 0.031, "mean_abs": 0.17},
    },
    {
        "ts": "2026-08-11T09:00:03.000Z", "seq": 4, "sensor_id": "bearing.FE",
        "file": "outer_race_0hp.mat", "label": "outer_race", "window_idx": 4,
        "features": {"rms": 0.19, "peak": 0.61, "crest": 4.0, "kurtosis": 3.1,
                     "skew": -0.5, "variance": 0.027, "mean_abs": 0.15},
    },
]

INFERENCE_SAMPLES = [
    {
        "ts": "2026-08-11T09:00:00.100Z", "seq": 1, "sensor_id": "bearing.DE",
        "label": "normal", "anomaly": False, "anomaly_score": 0.04,
        "infer_ms": 3.1, "mode": "EDGE_AUTONOMOUS",
        "stats": {"total": 100, "anomalies": 3, "accuracy": 0.97, "elapsed_s": 12.0},
    },
    {
        "ts": "2026-08-11T09:00:01.100Z", "seq": 2, "sensor_id": "bearing.DE",
        "label": "ball", "anomaly": True, "anomaly_score": 0.71,
        "infer_ms": 4.5, "mode": "EDGE_AUTONOMOUS",
        "stats": {"total": 101, "anomalies": 4, "accuracy": 0.965, "elapsed_s": 12.5},
    },
    {
        "ts": "2026-08-11T09:00:02.100Z", "seq": 3, "sensor_id": "bearing.DE",
        "label": "inner_race", "anomaly": True, "anomaly_score": 0.91,
        "infer_ms": 39.8, "mode": "CLOUD_OPTIMISED",
        "stats": {"total": 102, "anomalies": 5, "accuracy": 0.971, "elapsed_s": 13.0},
    },
    {
        "ts": "2026-08-11T09:00:03.100Z", "seq": 4, "sensor_id": "bearing.FE",
        "label": "outer_race", "anomaly": True, "anomaly_score": 0.88,
        "infer_ms": 41.2, "mode": "CLOUD_OPTIMISED",
        "stats": {"total": 103, "anomalies": 6, "accuracy": 0.968, "elapsed_s": 13.6},
    },
]

if __name__ == "__main__":
    configure_logging()

    print("1. Creating producer...")
    producer = EventHubProducer()
    print("2. Producer created.")

    events = [translate_sensor_record(r) for r in SENSOR_SAMPLES] + [
        translate_inference_record(r) for r in INFERENCE_SAMPLES
    ]

    print(f"3. Sending {len(events)} bearing events "
          f"({len(SENSOR_SAMPLES)} sensor + {len(INFERENCE_SAMPLES)} inference)...")
    for e in events:
        print(f"   - {e['asset_type']:<18} event_id={e['event_id']} "
              f"device_id={e['device_id']} priority={e['priority']}")

    producer.send_events(events)
    print("4. Events sent.")

    producer.close()
    print("5. Producer closed.")
