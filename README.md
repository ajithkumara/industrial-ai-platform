# Azure Industrial AI Platform

**A domain-agnostic, config-driven IoT telemetry platform on Azure Databricks.**

Streams telemetry from heterogeneous asset types (vehicles, industrial equipment, and beyond) through a single generic envelope, a single generic pipeline, and Unity Catalog-governed Medallion storage — where onboarding a new asset type is a YAML file, not a code change.

---

## Why this exists

Most IoT platforms hard-code a schema per device type: a `VehicleEvent` class here, a `BearingEvent` class there, an `if asset_type == "..."` branch wherever the two collide. Every new sensor category becomes a pull request that touches ingestion, transformation, and storage code.

This platform separates those concerns deliberately:

- **One envelope for everything.** Every device — a vehicle, a PLC, eventually a wind turbine — emits the same structural contract: `event_id`, `device_id`, `asset_type`, `timestamp`, `priority`, `schema_version`, and an opaque `payload`. Nothing upstream of Silver needs to know what's inside the payload.
- **Domain knowledge lives in config, not code.** Each asset type's actual fields — names, types, source paths inside `payload` — are declared in `config/asset_types/<asset_type>.yml`. The Silver flattening layer (`dlt/silver/flatten_payloads.py`) reads whatever configs exist at deploy time and dynamically registers one output table per asset type. Adding `wind_turbine.yml` produces a new Silver table with zero Python changes — this is enforced, not just aspirational: `tests/test_asset_type_config.py` proves a synthetic new asset type works through the same code path with nothing but a YAML file.
- **One production execution path.** A single Delta Live Tables (Lakeflow) pipeline owns Bronze → Silver → Gold end to end. There is no parallel Jobs-based pipeline quietly reprocessing the same data.

---

## Architecture

```
Edge Simulators (edge/)
   vehicle_producer.py, industrial_producer.py
        │  Generic TelemetryEvent envelope
        ▼
Azure Event Hubs
        │
        ▼
Consumer (consumer/)
   Pydantic validation → DLQ on malformed events
   Batch buffering → checkpoint only after durable write
        │
        ▼
ADLS Gen2 — landing/raw (JSONL)
        │
        ▼
┌───────────────────────────────────────────────┐
│  Delta Live Tables Pipeline (DLT)              │
│  industrial_ai_dlt_pipeline                    │
│                                                 │
│  Bronze   dlt/bronze/ingest_raw_events.py      │
│           Auto Loader (cloudFiles) streaming   │
│           → industrial_ai.bronze.telemetry_bronze
│                    │                           │
│  Silver   dlt/silver/clean_and_deduplicate.py  │
│           envelope validation, dedup by event_id
│           → industrial_ai.silver.cleaned_telemetry_events
│                    │                           │
│           dlt/silver/flatten_payloads.py       │
│           config-driven, one table per asset type
│           → industrial_ai.silver.silver_<asset_type>_telemetry
│                    │                           │
│  Gold     dlt/gold/asset_health_summary.py     │
│           → industrial_ai.gold.asset_health_summary
└───────────────────────────────────────────────┘
        │
        ▼
ML / Predictive Features (roadmap — see Status)
```

Governance sits underneath all of it: Unity Catalog (`industrial_ai` catalog, `bronze`/`silver`/`gold`/`serving` schemas), an Access Connector-backed Storage Credential, and an External Location over ADLS Gen2 — all provisioned by Terraform, authenticated via managed identity with no storage account keys in the data path.

---

## Tech stack

| Layer            | Technology                                          |
|-------------------|------------------------------------------------------|
| Ingestion         | Azure Event Hubs, Python consumer (`azure-eventhub`) |
| Processing        | Databricks Delta Live Tables (Lakeflow), PySpark      |
| Storage           | ADLS Gen2, Delta Lake                                 |
| Governance        | Unity Catalog (catalog, schemas, external location, storage credential, grants — all Terraform-managed) |
| Validation        | Pydantic v2                                           |
| Infrastructure    | Terraform                                             |
| Deployment        | Databricks Asset Bundles (DAB)                        |
| CI                | GitHub Actions (`pytest` on every push/PR)            |
| Language          | Python 3.11                                           |

---

## Repository structure

```
industrial-ai-platform/
├── databricks.yml            Bundle definition — bundle root is the repo root
│                             (must be, since dlt/ and config/ below are
│                             outside databricks/ and DAB can't reference
│                             files outside its bundle root)
├── .github/workflows/       CI (tests), Databricks deploy, Terraform validate
├── config/
│   ├── environments/        dev.yaml / test.yaml / prod.yaml
│   └── asset_types/         vehicle.yml, industrial.yml, wind_turbine.yml
│                             — the config-driven Silver contract
├── shared/                  Generic TelemetryEvent (Pydantic), constants, logging
├── edge/                    Device/asset simulators (base_producer + per-type producers)
├── consumer/                Event Hub → validation → batching → ADLS landing
├── dlt/
│   ├── bronze/               Auto Loader ingestion (DLT)
│   ├── silver/                Envelope cleanup/dedup + config-driven flattening
│   ├── gold/                  Aggregations and health metrics
│   └── common/                Shared DLT helpers, config loader, expectations
├── databricks/
│   ├── resources/pipelines/   The one production DLT pipeline
│   ├── resources/jobs/        Non-production manual/backfill jobs (not deployed)
│   └── sql/                   Catalog/schema/grant reference SQL
├── ml/                       Feature store + anomaly model scaffolding (roadmap)
├── monitoring/               Alert rule definitions
├── terraform/                Azure infra, Databricks workspace, Unity Catalog
├── tests/                    pytest suite
└── docs/                     Architecture notes and diagrams
```

---

## Getting started

### Prerequisites
- Azure subscription with rights to create resource groups, storage, Event Hubs, and a Databricks workspace
- [Terraform](https://developer.hashicorp.com/terraform) >= 1.5
- [Databricks CLI](https://docs.databricks.com/en/dev-tools/cli/install.html) >= 0.200
- Python 3.11

### 1. Clone and install
```bash
git clone <this-repo-url>
cd industrial-ai-platform
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure local runtime credentials
The consumer and edge simulators read Azure credentials from a `.env` file at the repo root (never committed — see `.gitignore`). Create one with:

```
EVENTHUB_CONNECTION_STRING=<sender-policy connection string>
EVENTHUB_CONSUMER_CONNECTION_STRING=<reader-policy connection string, falls back to EVENTHUB_CONNECTION_STRING>
EVENTHUB_NAME=<event hub name>
CONSUMER_GROUP=$Default
STORAGE_ACCOUNT_NAME=<adls account name>
STORAGE_CONNECTION_STRING=<adls connection string>
FILESYSTEM_NAME=raw
RAW_FOLDER=raw/telemetry
RAW_BATCH_SIZE=20
CONSUMER_BATCH_SIZE=20

# Optional -- only needed to run edge.run_nats_bridge (see "Bringing in
# other event sources" below). All have working defaults.
NATS_URL=nats://localhost:4222
NATS_BEARING_SENSOR_SUBJECT=sensors.bearing
NATS_BEARING_INFERENCE_SUBJECT=inference.bearing
```

`RAW_BATCH_SIZE` and `CONSUMER_BATCH_SIZE` are deliberately separate: `CONSUMER_BATCH_SIZE` governs how many Event Hub records are processed per consumer batch, while `RAW_BATCH_SIZE` governs how many validated events accumulate before one JSONL file is written to ADLS — the latter is what actually controls file size in landing/raw.

Configuration is validated explicitly at each entry point (`consumer.eventhub_consumer.main()`, `edge.base_producer`), not on import — so `pytest` and tooling can safely import these modules without real credentials present.

### 3. Provision infrastructure and Unity Catalog
```bash
cd terraform/environments/dev
terraform init
terraform apply
```
This provisions the resource group, storage account and ADLS filesystem, Event Hub namespace, Databricks workspace, Access Connector, and the full Unity Catalog stack — Storage Credential, External Location, the `industrial_ai` catalog, and its `bronze`/`silver`/`gold`/`serving` schemas with grants — with no manual console steps.

### 4. Deploy the Databricks bundle and run the pipeline
The bundle root is the repository root (`databricks.yml` lives at the top level, not inside `databricks/`) — this is required because the pipeline's source notebooks (`dlt/`) and asset-type configs (`config/asset_types/`) live outside `databricks/`, and Databricks Asset Bundles cannot reference files outside their bundle root. Run these from the repo root:
```bash
databricks bundle validate --target dev
databricks bundle deploy --target dev
databricks bundle run industrial_ai_dlt_pipeline
```
`industrial_ai_dlt_pipeline` is the sole production execution path for Bronze → Silver → Gold. The standalone job definitions under `databricks/resources/jobs/` invoke the same underlying DLT-decorated notebooks and are intentionally excluded from `databricks.yml`'s bundle `include:` — they exist only as reference/manual-backfill material and are not deployed.

### 5. Run the simulators (optional, local testing)
```bash
python -m edge.run_simulator
python -m consumer.eventhub_consumer
```

---

## Adding a new asset type

This is the platform's core extensibility test. To onboard, say, `wind_turbine`:

1. Add `config/asset_types/wind_turbine.yml` describing `asset_type`, `silver_table`, and a `fields` list of `source` (dotted path into `payload`) / `target` (output column) / `type` (Spark type) mappings.
2. Deploy. `dlt/silver/flatten_payloads.py` discovers the new config automatically and registers a new DLT table — **no changes to any `.py` file required.**

`tests/test_asset_type_config.py` enforces this: it onboards a synthetic asset type at test time using only a YAML file and confirms it flows through the same loader `flatten_payloads.py` uses in production.

### Bringing in other event sources

Not every telemetry source publishes directly to Event Hub. `edge/nats_bearing_bridge.py` is the reference example of bridging a different transport in: it subscribes to NATS subjects (used by a separate research project, `adaptive-edge-orchestrator`, for bearing-fault-classification sensor and inference events), translates each message into the generic `TelemetryEvent` envelope, and republishes onto Event Hub via the existing `EventHubProducer` — no changes to the consumer, Bronze, or the generic Silver flattener. The two new asset types it introduces (`bearing_sensor`, `bearing_inference`, see `config/asset_types/`) are just more proof that config-driven onboarding works for real, unrelated domains, not only synthetic tests.

Run it with `python -m edge.run_nats_bridge` once NATS is reachable and Event Hub credentials are configured.

**Caveat:** this bridge and its two asset-type configs were built from pasted payload examples, without access to the `adaptive-edge-orchestrator` source. The NATS subject names, field names, and types should be verified against the real `sensor_replay.py`/`inference_engine.py` publish calls before relying on this in practice — see the caveat comment at the top of `edge/nats_bearing_bridge.py`.

---

## Testing

```bash
python -m pytest tests/ -v
```
Runs in CI on every push/PR via `.github/workflows/ci-cd.yml` against Python 3.11. Covers envelope validation, batch buffering (including the failed-write-does-not-advance-checkpoint invariant), config loading, and config-driven Silver flattening.

---

## Security notes

- All ADLS access in the deployed pipeline goes through Unity Catalog's Storage Credential (Access Connector managed identity) — no storage account keys or SAS tokens in Databricks configuration.
- Local `.env`, Terraform state, and Terraform variable/output files are excluded from version control (see `.gitignore`). Terraform outputs in particular can contain live connection strings — treat any tracked `outputs.json` as a credential-rotation event, not just a file to delete.
- Runtime configuration validation happens explicitly at application entry points rather than on import, so credentials are never required just to load or test the codebase.

---

## Status

| Component | State |
|---|---|
| Generic envelope, consumer, edge (vehicle) | Implemented and tested |
| Config-driven Silver flattening | Implemented; vehicle config verified against the real producer payload |
| Bronze / Silver / Gold DLT pipeline | Implemented, single production execution path |
| Industrial asset type | Config and producer are intentional placeholders — no fabricated schema until a real industrial payload contract exists |
| Predictive features (Gold) | Stub, not yet wired into the pipeline |
| ML feature store / anomaly model | Scaffolding only |
| `databricks bundle validate` / `terraform validate` in CI | Not yet automated end-to-end — run manually against a network-reachable workspace before deploying |

### Roadmap
- [ ] Real industrial telemetry contract + producer implementation
- [ ] Gold predictive features, wired into the DLT pipeline
- [ ] Gold KPI dashboard (Databricks SQL or Power BI)
- [ ] Alerting via Azure Monitor / PagerDuty, driven by `monitoring/alert_rules.json`
- [ ] Automated `databricks bundle validate` and `terraform validate` in CI

---

## License

All rights reserved. This repository is shared publicly for portfolio and technical-evaluation purposes only — see [`LICENSE`](./LICENSE) for details. It is not open source and may not be reused, redistributed, or incorporated into other projects without written permission.

**Author:** Ajith Kumara — [aakumara@gmail.com](mailto:aakumara@gmail.com)
