"""
Cloud-only end-to-end acceptance test entry point.

python -m tests.integration.cloud_e2e_scenario [SCENARIO ...]
python -m tests.integration.cloud_e2e_scenario --all
python -m tests.integration.cloud_e2e_scenario --all --include-cloudforest-smoke

Sends synthetic bearing_sensor / bearing_inference / orchestrator_mode /
context_snapshot / cloud_validation events (see generate_bearing_events.py)
directly to the real Azure Event Hub via the existing EventHubProducer --
NO NATS, NO adaptive-edge-orchestrator, NO edge process involved. This
proves the cloud platform (Event Hub -> consumer -> Bronze -> Silver ->
Gold -> CloudForest) works as a standalone system before reconnecting the
real edge/thesis rig.

Writes tests/integration/expected_results.json with the exact expected
values for every scenario sent, and prints the Databricks SQL needed to
verify each one against the real Gold tables. This script does NOT
connect to Databricks itself (no SQL warehouse credentials assumed) --
run the printed queries in a Databricks SQL editor / notebook after the
DLT pipeline has processed the new landing files, and diff the results
against expected_results.json by eye or with a follow-up script once you
have SQL connector credentials configured.

NOTE: guarded behind __main__ (requires real Event Hub credentials and
performs live sends) so pytest collection doesn't attempt this during CI
-- same convention as tests/test_send.py and tests/test_send_bearing_events.py.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from config.logging import configure_logging
from edge.base_producer import EventHubProducer
from tests.integration.generate_bearing_events import (
    ALL_SCENARIOS,
    build_cloudforest_smoke_events,
)

_EXPECTED_RESULTS_PATH = Path(__file__).parent / "expected_results.json"


def _print_verification_queries(all_expected: dict) -> None:
    print("\n" + "=" * 78)
    print("VERIFICATION -- run these in a Databricks SQL editor once the DLT")
    print("pipeline has processed the newly-landed files, and compare against")
    print(f"{_EXPECTED_RESULTS_PATH}")
    print("=" * 78)

    if "A" in all_expected:
        print(
            "\n-- Scenario A: Bronze/Silver sanity (all 10 events present, "
            "no dupes)\n"
            "SELECT count(*) AS n FROM industrial_ai.silver.silver_bearing_inference_results "
            "WHERE mode = 'CLOUD_OPTIMISED' AND seq BETWEEN 1 AND 10;\n"
            "-- expect n = 10"
        )

    if "B" in all_expected:
        exp = all_expected["B"]["escalation_efficacy"]
        print(
            "\n-- Scenario B: gold.escalation_efficacy exact math\n"
            "SELECT * FROM industrial_ai.gold.escalation_efficacy "
            "WHERE mode = 'HYBRID' AND edge_confidence_bucket = 'low';\n"
            f"-- expect n_escalations={exp['n_escalations']}, "
            f"agreement_rate={exp['agreement_rate']:.4f}, "
            f"edge_accuracy={exp['edge_accuracy']:.4f}, "
            f"cloud_accuracy={exp['cloud_accuracy']:.4f}, "
            f"cloud_accuracy_improvement={exp['cloud_accuracy_improvement']:.4f}"
        )

    if "C" in all_expected:
        exp = all_expected["C"]
        print(
            "\n-- Scenario C: gold.mode_history trigger evidence\n"
            "SELECT from_mode, to_mode, trigger FROM industrial_ai.gold.mode_history "
            "WHERE device_id = 'edge-node-01' AND to_mode = 'EDGE_ONLY' "
            "ORDER BY transition_at DESC LIMIT 1;\n"
            f"-- expect from_mode={exp['expected_from_to'][0]}, "
            f"to_mode={exp['expected_from_to'][1]}, trigger={exp['expected_trigger']}"
        )

    if "D" in all_expected:
        exp = all_expected["D"]
        print(
            "\n-- Scenario D: gold.edge_autonomy continuity evidence\n"
            "SELECT n_events_during_outage, n_anomalies_during_outage, "
            "largest_inter_event_gap_s, outage_duration_s "
            "FROM industrial_ai.gold.edge_autonomy "
            "WHERE device_id = 'edge-node-01' ORDER BY window_started_at DESC LIMIT 1;\n"
            f"-- expect n_events_during_outage={exp['n_events_during_outage']}, "
            f"n_anomalies_during_outage={exp['n_anomalies_during_outage']}, "
            f"largest_inter_event_gap_s ~= {exp['expected_gap_s']}, "
            f"outage_duration_s ~= {exp['outage_duration_s']}"
        )

    if "E" in all_expected:
        exp = all_expected["E"]
        print(
            "\n-- Scenario E: gold.mode_history recovery sequence\n"
            "SELECT from_mode, to_mode, trigger FROM industrial_ai.gold.mode_history "
            "WHERE device_id = 'edge-node-01' ORDER BY transition_at DESC LIMIT 2;\n"
            f"-- expect (in order) {exp['expected_sequence']}, "
            f"trigger={exp['expected_trigger']} for both"
        )

    if "F" in all_expected:
        exp = all_expected["F"]["detection_performance"]
        print(
            "\n-- Scenario F: gold.detection_performance exact confusion matrix\n"
            "SELECT tp, fp, fn, tn, precision, recall, f1 "
            "FROM industrial_ai.gold.detection_performance "
            f"WHERE mode = '{exp['mode']}' AND model_version = '{exp['model_version']}';\n"
            f"-- expect tp={exp['tp']}, fp={exp['fp']}, fn={exp['fn']}, tn={exp['tn']}, "
            f"precision={exp['precision']:.6f}, recall={exp['recall']:.6f}, f1={exp['f1']:.6f}"
        )

    if "cloudforest_smoke" in all_expected:
        exp = all_expected["cloudforest_smoke"]
        print(
            "\n-- CloudForest smoke: run ml/cloud_forest/score_escalations.py "
            "(via the cloud_forest_score_escalations Databricks Job) AFTER "
            "these land, then:\n"
            "SELECT source_event_id, cloud_score, cloud_model_version "
            "FROM industrial_ai.silver.silver_cloud_validation_results "
            f"WHERE source_event_id IN {tuple(exp['inference_event_ids'])};\n"
            f"-- expect exactly {exp['n_pending_escalations']} rows, "
            "cloud_score in [0,1], cloud_model_version LIKE 'cloud_forest_bearing-v%'"
        )

    print("\n" + "=" * 78 + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "scenarios",
        nargs="*",
        choices=list(ALL_SCENARIOS.keys()) + [],
        help="Scenario letters to run (e.g. A B F). Ignored if --all is set.",
    )
    parser.add_argument("--all", action="store_true", help="Run all scenarios A-F.")
    parser.add_argument(
        "--include-cloudforest-smoke",
        action="store_true",
        help=(
            "Also send the CloudForest real-model smoke scenario "
            "(HYBRID events with no pre-built cloud_validation)."
        ),
    )
    args = parser.parse_args()

    selected = list(ALL_SCENARIOS.keys()) if args.all else args.scenarios
    if not selected and not args.include_cloudforest_smoke:
        parser.error("Specify scenario letters, --all, or --include-cloudforest-smoke.")

    configure_logging()

    print("1. Creating producer...")
    producer = EventHubProducer()
    print("2. Producer created.")

    all_events: list[dict] = []
    all_expected: dict = {}

    for letter in selected:
        events, expected = ALL_SCENARIOS[letter]()
        print(f"3.{letter} Scenario {letter}: {len(events)} event(s) -- {expected['scenario']}")
        all_events.extend(events)
        all_expected[letter] = expected

    if args.include_cloudforest_smoke:
        events, expected = build_cloudforest_smoke_events()
        print(f"3.smoke CloudForest smoke: {len(events)} event(s)")
        all_events.extend(events)
        all_expected["cloudforest_smoke"] = expected

    print(f"4. Sending {len(all_events)} total event(s)...")
    producer.send_events(all_events)
    print("5. Events sent.")

    producer.close()
    print("6. Producer closed.")

    _EXPECTED_RESULTS_PATH.write_text(json.dumps(all_expected, indent=2, default=str))
    print(f"7. Wrote expected results to {_EXPECTED_RESULTS_PATH}")

    _print_verification_queries(all_expected)


if __name__ == "__main__":
    main()
