# Combined Architecture & Thesis Review — August 2026

**Scope:** `industrial-ai-platform` (Azure Databricks) + AdaptiveOrchestrator thesis project (`adaptive-edge-orchestrator`), reviewed against the three uploaded academic documents: System Architecture v1.0 (Feb 2026, approved by Dr. Thushari Silva), Sprint Test Report v3 (5 Mar 2026), and Product Roadmap V1/V2/V3.

**Reviewer stance:** CTO / Principal Data & ML Architect / Thesis Supervisor perspective. Everything below was verified against the actual repository state and the actual document text — not assumed.

---

## THE CENTRAL FINDING (read this first)

You do not have one system. You have **two systems**, and the single most important decision in this review is to stop treating them as one:

1. **AdaptiveOrchestrator** (thesis) — local Docker + NATS JetStream + local Kafka/Spark + Delta-on-S3 + AWS Free Tier (CloudWatch, Lambda), ap-south-1. The research contribution is the **Policy Executor** (runtime-adaptive edge–cloud orchestration). This architecture is *approved by your supervisor* and the architecture document itself says: *"Any design decision not recorded here has not been made."*

2. **industrial-ai-platform** (portfolio/product) — Azure Event Hub → consumer → ADLS → DLT Bronze/Silver/Gold under Unity Catalog, config-driven multi-domain flattening. Proven end-to-end in a real deployed pipeline across three live domains (vehicle, bearing_sensor, bearing_inference).

The NATS bridge you built (Phase 1) connects them. That was the right build — but only if its role is understood correctly:

> **The Azure platform is the *research archive and analytics side-channel* for thesis data, and a working prototype of the Roadmap's V3 cloud layer. It is NOT the thesis evaluation platform, and thesis evaluation data must never depend on it.**

Three reasons this boundary is non-negotiable:

- **Academic:** Your approved architecture doc does not contain Azure, Event Hub, or Databricks anywhere. Rerouting evaluation through them would be an unapproved architecture change weeks before submission.
- **Scientific:** H1/H2/H3 measurements (latency, autonomy, egress cost) must be captured at the edge and in the AWS path defined in the doc. Adding an Azure hop adds confounds and destroys the cost-audit comparison (S5).
- **Practical:** The sprint report targets submission in **late May 2026. It is now August.** You are behind schedule. Every hour spent on platform features that don't produce thesis evidence is an hour taken from Sprints 4–10.

The good news: the Product Roadmap V3 explicitly names **Databricks + Unity Catalog + Delta Lake** as the production equivalents of the V1 stack. So the Azure platform is a legitimate early rehearsal of V3 — a strong interview story ("I prototyped the commercial cloud analytics layer before the thesis was even defended"). The only inconsistency is cloud: the roadmap says AWS; the platform is Azure. Resolve it by wording the roadmap's V3 as "Databricks (cloud-agnostic — validated on Azure)" rather than pretending they're the same deployment.

---

## PART 1 — ACADEMIC REQUIREMENTS (extracted from the documents)

### Research questions (Sprint Report §6)
- RQ1: How can orchestration dynamically allocate tasks at runtime?
- RQ2: What signals are effective as inputs to the decision engine? (RTT, CPU, anomaly severity; hysteresis)
- RQ3: Performance trade-off between accuracy, latency, and resource use?
- RQ4: Can the framework be validated on real constrained hardware (simulated Jetson Nano profile)?

### Hypotheses (Sprint Report §1.2, updated v3)
- **H1:** F1 ≥ 0.95 equivalent to cloud-only baseline during normal operation.
- **H2:** **100% edge inference continuity during WAN outages of ANY duration** (upgraded from "99% up to 60 min"), via the three-tier retention architecture (NATS JetStream hot / SQLite warm / append-only JSONL cold; ANOMALY events never dropped).
- **H3:** ≥ 40% cloud operational cost reduction vs static cloud-offload baseline.

### Research contribution (precisely scoped)
The Policy Executor and its context-aware decision engine — runtime-adaptive orchestration. Supporting contributions: evidence-based threshold calibration (P95 × multiplier, Sprint 3) and the three-tier retention policy. **Everything else — Kafka, Spark, Delta, SHAP, CloudWatch — is explicitly declared "standard infrastructure" by your own architecture doc.** The examiner will judge the Policy Executor and the evaluation rigor, not the plumbing.

### Required experiments & evidence
- 5 tc netem scenarios (S1 baseline, S2 blackout 30 min, S3 satellite 900 ms, S4 CPU storm, S5 cost audit) → `logs/s1–s5_results.json`
- Threshold sweep + calibration sensitivity analysis (1.5×/2.0×/2.5×)
- 30-minute soak test; buffer overflow/flush integrity tests
- Sprint 10: bootstrap CI, paired t-test, Cohen's d, ablation study vs 3 static baselines
- Datasets: CWRU (12 kHz vibration) + SKAB. Metrics: F1/precision/recall, mode-switch latency, autonomy %, egress event counts.

### Academic vs engineering requirements — the hard boundary
| | Academic (mandatory, approved) | Engineering (optional, portfolio) |
|---|---|---|
| Cloud | AWS Free Tier, ap-south-1 | Azure (Canada Central) |
| Storage | Delta on S3, partitioned date+mode | ADLS + Unity Catalog medallion |
| Streaming | Local Kafka (KRaft) + NATS | Event Hub |
| Evidence | Local JSONL logs + S3 Delta + CloudWatch screenshots | Bronze/Silver/Gold tables |
| Evaluation | tc netem scenarios, statistical tests | End-to-end pipeline runs |

**Do not silently move anything from the left column to the right column.**

### Terminology that must be preserved — and one conflict found
The Architecture v1.0 doc defines modes **EDGE_ONLY / HYBRID / CLOUD_OPTIMISED**. The Sprint Report v3 defines **CLOUD_OPTIMISED / EDGE_ONLY / EDGE_AUTONOMOUS** (HYBRID absent; EDGE_AUTONOMOUS added for total outage). Your bearing_inference sample payloads use EDGE_AUTONOMOUS and CLOUD_OPTIMISED. **This drift must be reconciled in the thesis** — an examiner will catch it. Recommendation: treat the Sprint Report v3 taxonomy as current (it's later and empirically validated), formally deprecate/redefine HYBRID in the thesis (e.g., as the SHAP-explanation path within CLOUD_OPTIMISED), and update the architecture doc to v1.1. The platform's `bearing_inference.yml` accepts `mode` as a free string, so no platform change is required — that was the right call.

---

## PART 2 — WHAT THE PLATFORM ACTUALLY IS (verified, not assumed)

### Proven end-to-end in the real deployed system
- Edge producers → Event Hub → Python consumer (Pydantic envelope validation, batching, checkpointing) → ADLS `raw/telemetry/year=/month=/day=/` JSONL
- DLT pipeline (Databricks Asset Bundle, bundle root at repo root, validated/deployed/run against the live workspace): Auto Loader Bronze (`telemetry_bronze` + `_source_file`/`_ingested_at` from `_metadata`) → Silver `cleaned_telemetry_events` (envelope cleanup + dedup-by-`event_id`, most-recent-by-`_ingested_at`) → config-driven flattened Silver tables → Gold `asset_health_summary`
- **Three domains live with real data:** vehicle (885 records), bearing_sensor and bearing_inference (verified 16 Bronze → 8 deduplicated Silver rows, correct priority mapping, correctly flattened features/mode/anomaly columns)
- Deterministic `uuid5` event IDs proven to collapse duplicate delivery in production, not just in unit tests
- 35 unit tests passing; CI (pytest, bundle validate, terraform validate) wired with correct triggers
- Terraform: modular (resource_group, storage, eventhub, databricks, unity_catalog, rbac, monitoring), dev environment actually applied

### Scaffolding, stubs, and dead weight (the honest list)
| Item | State | Risk |
|---|---|---|
| `ml/train_anomaly_model.py`, `ml/feature_store_setup.py` | `pass` stubs | **Misleading.** An interviewer opening `ml/` sees empty functions under an ambitious name. Delete the directory or replace with a README pointing at the thesis repo's real ML. |
| `monitoring/alert_rules.json` | `{"rules": []}` | Implies observability that doesn't exist. Delete or implement minimally. |
| `dlt/common/expectations.py` | Empty docstring | **No DLT expectations exist anywhere in the pipeline.** The file name promises data quality gates; none are applied. |
| `dlt/common/schemas.py`, `shared/schemas.py`, `shared/helpers.py` | Empty/stub | Dead. Delete. |
| `edge/industrial_producer.py` | Empty class stub | `industrial.yml` config also has zero fields. Either mark both as explicit placeholders or remove. |
| `databricks/resources/jobs/*.yml` | Dead but honestly documented | Acceptable — headers clearly state NOT DEPLOYED and why. This is actually good practice. |
| `terraform/unity_catalog/dev/` | Legacy duplicate of `terraform/modules/unity_catalog` + `environments/dev` path; still git-tracked | Confusing double execution path in IaC. Remove from git. |
| `dlt/gold/predictive_features.py` | `NotImplementedError`, decorator removed | Fine — honestly labeled. |
| Phase 1 work (bridge, bearing configs, tests, README) | **Entirely uncommitted** | All of it is sitting as modified/untracked files. Commit it. |

### Environment note
`tests/test_batch_buffer.py` and `tests/test_eventhub_consumer.py` require Python ≥ 3.11 (`datetime.UTC`). CI uses 3.11 so they pass there, but the floor is undocumented — add `requires-python = ">=3.11"` / README note.

---

## PART 3 — ACTUAL DATA FLOWS AND THE ARCHITECTURE ANSWER

### Flow A — Ultra-low-latency edge path (thesis-owned, milliseconds)
```
Sensor replay (CWRU/SKAB) → NATS sensors.raw → Isolation Forest (edge)
  → Policy Executor (<10ms decision) → { buffer | local alert | cloud.ingest }
```
This loop must complete locally with zero dependency on any cloud — that IS hypothesis H2. Nothing in the Azure platform may ever sit inside this loop.

### Flow B — Cloud analytics / research archive path (minutes, eventually consistent)
```
Thesis (approved):  cloud.ingest → Kafka → Spark Streaming → Delta on S3 → evaluation queries
Platform (side-channel): NATS → nats_bearing_bridge (translate → generic envelope)
  → Event Hub → consumer → ADLS JSONL → Bronze → Silver (dedup + flatten) → Gold
```

### The answer to "one pipeline or several?" — Option C + D hybrid, derived not assumed
- **One shared platform** (envelope → Bronze → Silver generic → config-driven flatten) for all *analytics* domains — already built and proven. New domains enter via a YAML file and an adapter. Correct.
- **The edge decision loop stays a separate system** — not because of taste, but because its latency budget (<10 ms) and offline-autonomy requirement are physically incompatible with any cloud pipeline. Two coordinated paths, joined by an async, fire-and-forget bridge.
- **Credit card fraud (future): separate pipeline AND separate boundary** (Part 7).

The bridge is correctly non-blocking and translate-only. Keep it that way: if Event Hub is down, the thesis system must not notice.

---

## PART 4 — SENSOR/ML CONCEPT SEPARATION (this needs fixing)

The platform currently stores three conceptually different things and mostly keeps them separate — but two conflations exist:

**Problem 4a — ground truth vs prediction are conflated (HIGH, research-integrity risk).**
In `bearing_inference` events, `label` is the *dataset ground-truth class* (CWRU fault label from the replayed file) while `anomaly`/`anomaly_score` are the *model's prediction*. They sit side-by-side with nothing marking which is which. In a thesis context this is dangerous: F1 computed from a table where nobody remembers which column was ground truth is indefensible. Fix cheaply in the YAML mapping: `payload.label` → target `ground_truth_label` (and same in `bearing_sensor.yml`). Bronze keeps the raw payload untouched either way. Document it in the config comment.

**Problem 4b — per-event vs per-run data are mixed (MEDIUM).**
`stats.total/anomalies/accuracy/elapsed_s` are cumulative run statistics embedded in every inference event, then flattened into per-row `stats_*` columns. That's a denormalized snapshot repeated per event — queries like "final run accuracy" become "max by timestamp" hacks. Acceptable short-term; the clean fix is a fourth event type (`inference_run_summary`) emitted once per run/window. Low priority, but be conscious of it.

**What's missing as first-class metadata (HIGH value for thesis, LOW effort):**
| Concept | Current state | Fix |
|---|---|---|
| Model version | Absent from inference events | Add `model_version` to bridge translation + YAML. The defensive null-fallback flattening means you can ship the config *before* the payload carries the field — schema evolution for free. |
| Policy/threshold version | Absent | Add `policy_version` / `calibration_tag` (Sprint 3's `environment_tag` fits perfectly). |
| Context at event time | `latency_ms`, `cpu_pct`, `cloud_reachable` are in the thesis Delta schema but not bridged | Add optional fields to `bearing_inference.yml`. |
| Mode transitions | **Not bridged at all** | See Part 5 — this is the biggest gap. |

---

## PART 5 — THESIS INTEGRATION: WHAT DATA MUST EXIST, WHERE

Rule established above: **primary evidence lives in the approved AWS/local path.** The platform's role is secondary verification, richer exploration, and portfolio demonstration. Within that role, per metric:

| Thesis metric | Data that must exist | Captured where | Stored (primary) | Platform (secondary) | Thesis use |
|---|---|---|---|---|---|
| Mode switch latency (<5s) | Mode transition events with trigger + context + timestamps | Policy Executor (`orchestrator.mode`) | `logs/*.jsonl` + Delta/S3 | **Missing — add `orchestrator_mode.yml` asset type** | S3 figure: transition timeline |
| Edge autonomy % (H2) | Per-event mode + cloud_reachable + inference count during outage window | Inference Engine + Policy Executor | Delta/S3 `mode`, `cloud_reachable` columns | bearing_inference + optional fields (Part 4) | S2 table |
| F1/precision/recall (H1) | prediction + ground truth per event, per mode, per model_version | Inference events | Delta/S3 | `silver_bearing_inference_results` after the `ground_truth_label` rename | S1 baseline + per-mode comparison |
| Inference latency P99 | `infer_ms` per event | Inference Engine | Delta/S3 | Already flattened ✓ | RQ3/RQ4 |
| Egress reduction (H3) | Count of events actually sent to cloud vs generated, per mode | Policy Executor routing counters | `s5_results.json` | Gold aggregation over mode history | S5 cost bar chart |
| Buffer integrity | buffered/dropped/flushed counters | NATS Buffer | JSONL + test logs | Not needed | H2 evidence |

**The single highest-value platform addition for the thesis: bridge the `orchestrator.mode` transition events** as a third asset type (`config/asset_types/orchestrator_mode.yml`: from_mode, to_mode, trigger, latency_ms, cpu_pct, timestamp). Mode history is, in your own architecture doc's words, "the primary evidence for the thesis evaluation." Once it's in Silver, one Gold table (`gold.mode_history_daily` or per-scenario) gives you cross-checks of every S1–S5 figure — computed independently from your local logs, which is a genuinely nice defense answer ("the numbers reconcile across two independent storage paths").

**What would weaken the thesis if not captured:** model_version on every inference (reproducibility), calibration tag (which thresholds were live), and explicit event-time vs ingestion-time (you already have both — say so in the methodology chapter).

---

## PART 6 — MULTI-DOMAIN PLATFORM DESIGN

### Common platform capabilities (keep, already correct)
Generic envelope + Pydantic validation; deterministic event IDs; transport ingestion (Event Hub consumer); Bronze Auto Loader; Silver envelope cleanup + dedup; **config-driven flattening (the crown jewel — five domains onboarded, two with zero Python changes, proven live)**; schema-aware null fallback; Terraform modules; DAB deployment; CI.

### Domain-specific (keep isolated)
YAML field mappings per asset type; domain producers/adapters (vehicle simulator, NATS bridge); domain Gold tables; domain ML (lives in the thesis repo — correctly NOT in this platform).

### Where NOT to abstract (explicit anti-recommendations)
- **No feature-engineering framework.** One consumer domain (bearing) does not justify a framework. Write plain Gold SQL/PySpark per domain until three domains demand the same pattern.
- **No model registry / feature store in this platform.** MLflow lives in the thesis stack (Sprint/V2 scope). The `ml/` stubs pretending otherwise should go.
- **No transport abstraction layer.** You have exactly two transports (Event Hub, NATS-via-bridge). The bridge *is* the abstraction. A `GenericTransport` interface now would be premature.
- **No streaming Silver→Gold real-time serving.** Nothing consumes it.

The platform's abstraction level is currently right-sized. The main multi-domain gap is honesty, not capability: `industrial.yml` and `wind_turbine.yml` have no producers and (for industrial) no fields — label them as placeholders in the README table of asset types.

---

## PART 7 — CREDIT CARD / HIGH-SENSITIVITY DOMAIN

Answer: **B + D — reuse patterns and code templates, isolate runtime and data entirely. Separate repo, separate Azure resources, separate Unity Catalog catalog (or workspace), separate IAM.** Not fear-driven — layer-by-layer:

**Legitimately reusable (copy, don't share):** envelope concept + Pydantic validation pattern; deterministic-ID dedup design; config-driven flattening code; Terraform *modules* (instantiate with new state, new resource group); DAB/CI templates; medallion layout.

**Must be isolated:** Event Hub namespace, storage account, catalog, workspace, service principals, secrets, network boundary, audit/retention policies. Sharing any runtime infrastructure with vehicle telemetry gives you the worst of both worlds: PCI-scope creep over the IoT platform and no benefit.

**Pragmatic de-fanging:** for a portfolio project, never touch real PANs — use synthetic/tokenized data (e.g., the ULB/Kaggle fraud dataset, already PCA-anonymized). Then the compliance burden collapses to "demonstrate that you *designed* the isolation," which is exactly the interview skill. **Defer entirely until after thesis submission** (this was already Phase 3 — confirmed correct).

---

## PART 8 — PLATFORM REVIEW AGAINST SENIOR-PLATFORM STANDARDS

**Strong:** event-driven design; idempotency (deterministic IDs, production-proven); dedup semantics (effectively-once into Silver over at-least-once transport — the correct, honest pattern); replayability (immutable Bronze + JSONL landing); medallion boundaries clean; Unity Catalog governance; IaC modularity; bundle-root/config-resolution correctness (hard-won through real debugging); CI with path-scoped triggers; test coverage of the config machinery including negative tests.

**Gaps, ranked:**

1. **No data-quality gates (HIGH).** Zero `@dlt.expect` anywhere. Minimum viable: on Silver — `expect_or_drop("valid_event_id", "event_id IS NOT NULL")`, valid timestamp, `asset_type IS NOT NULL`, priority in allowed set; quarantine metrics come free in the DLT event log. One afternoon of work; disproportionate credibility gain.
2. **Consumer durability (HIGH for prod, known-issue for demo).** Flush happens on batch-size or Ctrl+C only — you *personally lost 8 events to this* during testing. Add a time-based flush (e.g., every 30 s). Checkpoints in a local JSON file mean no multi-instance story and loss on machine death; fine for a dev demo, must be stated as a limitation. Also: single consumer, no consumer-group scale-out, no poison-message DLQ path to a quarantine container.
3. **Schema-inference collision risk (MEDIUM, grows with domains).** All payloads share one inferred `payload` struct in Bronze. Two asset types using the same key with different types (e.g., `payload.status` string vs int) will fight in schema evolution. Mitigations when it bites: `cloudFiles.schemaHints`, rescue-data column, or per-asset-type landing prefixes. Document the risk now; act when domain #6 arrives.
4. **Observability (MEDIUM).** No pipeline freshness/failure alerting. Minimum viable: a scheduled query over the DLT event log + one email alert; or a tiny Gold `pipeline_health` table. Do not build Prometheus/Grafana here — that stack belongs to the thesis edge system where it's already specified.
5. **Schema evolution policy (LOW-MEDIUM).** `schema_version` exists in the envelope but nothing enforces or branches on it. Fine for now; write down the policy (additive-only changes; new version = new field, never a type change).
6. **Secrets (LOW).** Connection strings in `.env`/GitHub secrets is acceptable at this scale; managed identity is the stated future path. Don't build it now.

---

## PART 9 — PROBLEM REGISTER

| # | Problem | Severity | Why it matters | Fix | Academic impact | Engineering impact |
|---|---|---|---|---|---|---|
| P1 | Thesis/platform architecture conflation — risk of evaluation depending on Azure | **Critical** | Unapproved architecture change; confounded measurements; examiner risk | Adopt the boundary in this review; state it in README + thesis | Protects defensibility | Clarifies platform role |
| P2 | Schedule: submission targeted late May 2026; it is August | **Critical** | The best architecture in the world doesn't defend a late thesis | Freeze platform features; execute Sprints 4–10 only; re-plan dates with supervisor | Existential | None |
| P3 | Ground truth vs prediction conflated (`label` in inference events) | High | F1 evidence integrity | Rename target to `ground_truth_label` in both bearing YAMLs | Protects H1 evidence | Trivial |
| P4 | Mode taxonomy drift (HYBRID vs EDGE_AUTONOMOUS) across docs/configs | High | Examiner will find it; metrics keyed on mode strings | Reconcile to Sprint-v3 taxonomy; arch doc v1.1; document in bridge | Consistency of all mode-based claims | Trivial |
| P5 | Mode-transition + context events not bridged — the primary thesis evidence type is absent from the platform | High | Platform can't support thesis analytics without it | Add `orchestrator_mode.yml` (+ optional context fields on inference) | Enables independent cross-check | One YAML + bridge function |
| P6 | Zero DLT expectations / quality gates | High | "Data quality framework" claimed by structure, absent in fact | Minimum expectation set on Silver | Cleaner evaluation data | Half a day |
| P7 | Consumer flush/checkpoint durability (observed data-sit incident) | Medium | Real data-loss window; single-instance checkpoint | Time-based flush; document limitation | Avoids lost test evidence | Small |
| P8 | Misleading stubs (`ml/`, `monitoring/`, empty schemas/expectations/helpers, `industrial_producer`) | Medium | Interview credibility — empty `pass` under ambitious names reads worse than absence | Delete or replace with pointer READMEs | None | Portfolio polish |
| P9 | `terraform/unity_catalog/dev/` legacy duplicate still tracked | Medium | Two IaC paths for the same resources = drift hazard | `git rm -r`, keep modules+environments path | None | IaC hygiene |
| P10 | Payload struct schema-collision risk as domains grow | Medium | Future pipeline breakage | Document; schemaHints when needed | None | Future-proofing |
| P11 | Missing model_version/policy_version on inference events | Medium | ML reproducibility | Optional YAML fields now (null-safe), bridge fields when thesis emits them | Reproducibility chapter | Trivial |
| P12 | Unverified NATS subject names/payload shapes in bridge (documented assumption) | Medium | Bridge may not match real orchestrator | Verify against `adaptive-edge-orchestrator` repo; one-line fixes | Correct data capture | Already flagged in docstrings ✓ |
| P13 | Phase 1 work uncommitted; Python ≥3.11 floor undocumented; `stats_*` per-event denormalization; no bearing Gold table | Low | Housekeeping | Commit; README note; defer the rest | Minor | Minor |

---

## PART 10 — WHAT NOT TO BUILD (enforced simplicity)

Applying the six-question test (what problem / why this project / academic value / product value / complexity / can managed services do it simpler), the following are **rejected**:

- **Kubernetes / EKS** — Roadmap V3 concern (Month 9+). Zero thesis value, high complexity. Docker Compose is your approved edge substrate.
- **Kafka in the Azure platform** — Event Hub is the managed equivalent and is proven. Kafka stays in the thesis stack where the doc requires it (hands-on skill goal already satisfied there).
- **Feature store, model registry, drift infra in the Azure platform** — duplicate of thesis-stack MLflow/KS-test scope. One system owns ML lifecycle: the thesis stack.
- **Microservices / service mesh / REST config APIs** — V2/V3 roadmap items. Not now.
- **Prometheus/Grafana for the Azure platform** — belongs to the thesis edge system only, where it's specified and produces thesis screenshots.
- **Real-time Silver→serving path, streaming Gold** — no consumer exists.
- **Multi-tenancy, billing, OTA** — V3. Listed in the roadmap; that's where they stay.

What earns its complexity: DLT expectations (quality), one mode-transition YAML (thesis evidence), time-based consumer flush (fixes an observed failure), stub deletion (honesty). All are days, not weeks.

---

## PART 11 — TARGET ARCHITECTURE

```
════════════════ THESIS SYSTEM (AdaptiveOrchestrator — AWS/local, approved) ════════════════

 CWRU/SKAB replay ──► NATS sensors.raw ──► Isolation Forest (edge, ≤50ms P99)
                                            │
        context.snapshot (RTT/CPU 1s) ──► POLICY EXECUTOR ★ (<10ms)  ◄─ calibration.json
                                            │
              ┌─────────────────────────────┼──────────────────────────────┐
        EDGE_AUTONOMOUS / EDGE_ONLY    CLOUD_OPTIMISED                 alerts
        3-tier buffer (JetStream/      cloud.ingest ► Kafka ►      MQTT/FastAPI/
        SQLite/JSONL cold store)       Spark ► Delta on S3         Lambda→SES
                                            │
                              CloudWatch (5 metrics) + evaluation logs s1–s5
                              ══ PRIMARY THESIS EVIDENCE — never routed via Azure ══

─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ async, fire-and-forget, non-blocking ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─
                     nats_bearing_bridge (translate → generic envelope)

════════════ ANALYTICS PLATFORM (industrial-ai-platform — Azure, portfolio/V3) ════════════

 DOMAIN ADAPTERS                 SHARED PLATFORM                        DOMAIN OUTPUTS
 vehicle simulator ─┐
 industrial (stub) ─┤   Event Hub ► consumer (validate/batch/ckpt)   silver_vehicle_telemetry
 NATS bridge:       ├─►   ► ADLS JSONL (date-partitioned)            silver_bearing_sensor_telemetry
   bearing_sensor   │     ► BRONZE telemetry_bronze (Auto Loader)    silver_bearing_inference_results
   bearing_inference│     ► SILVER cleaned_telemetry_events          [ADD] silver_orchestrator_mode
   [ADD] mode trans─┘        (dedup by deterministic event_id)          │
                          ► config/asset_types/*.yml flattening      GOLD asset_health_summary
                             (zero-code domain onboarding)           [ADD] gold mode-history/H-metrics
                          Unity Catalog ▪ Terraform ▪ DAB ▪ CI          │
                                                              BI / research cross-checks / demos

 FUTURE, ISOLATED: credit-card fraud = separate repo + separate catalog/workspace/IAM;
                   reuses patterns and Terraform modules by instantiation, never runtime infra.
```

Shared vs domain-specific: everything between Event Hub and `cleaned_telemetry_events` is shared and frozen; everything past flattening is per-domain YAML + per-domain Gold.

---

## PART 12 — TWO EXPLICIT SCOPES

### Final Year Project / Portfolio scope (industrial-ai-platform)
Cloud-native multi-domain telemetry lakehouse: Azure Event Hub ingestion; Python consumer with validation/batching/checkpointing; ADLS landing; DLT medallion under Unity Catalog; config-driven domain onboarding (5 domains, 3 live with real data); Terraform IaC; DAB deployment; CI; test suite. Deliverables: the working deployed pipeline, this review's fixes (expectations, mode-transition domain, hygiene), README + architecture docs. **Definition of done: it already substantially is** — remaining work is hardening and honesty, not features.

### Thesis scope (AdaptiveOrchestrator — unchanged from approved docs)
Research question: can runtime-adaptive orchestration eliminate the three static-partitioning failure modes (blindness, contention, waste)? Independent variables: network profile (tc netem S1–S5), CPU load, anomaly severity, policy thresholds. Dependent: F1/precision/recall, mode-switch latency, autonomy %, egress events, inference latency. Baselines: 3 static configurations (cloud-only, edge-only, fixed-hybrid). Statistics: bootstrap CI, paired t-test, Cohen's d, ablation. Datasets: CWRU + SKAB. Reproducibility: version-controlled scenario scripts, calibration.json, pinned dependencies, declared Sprint-0 baseline.

**The thesis is NOT "I built a pipeline."** The pipeline is Chapter 4 infrastructure. The contribution defended in Chapters 6–7 is: (1) the runtime policy mechanism, (2) evidence-based threshold calibration beating hardcoded values (your CPU-dilution finding is *empirical proof* thresholds don't transfer between environments — use it prominently), (3) the three-tier retention removing the outage-duration ceiling. The Azure platform appears, at most, as a short "industrial integration" subsection or appendix demonstrating generalizability — explicitly out of the evaluation path.

---

## PART 13 — KEEP / CHANGE / ADD / REMOVE / DEFER / ISOLATE / PROMOTE

**KEEP:** generic envelope + Pydantic; deterministic event IDs; Bronze/Silver/Gold as built; config-driven flattening with null-fallback; bundle-root layout; Terraform modules+environments path; CI; the bridge's fire-and-forget design; honest "NOT DEPLOYED" job YAMLs.

**CHANGE:** `label` → `ground_truth_label` in both bearing YAMLs (P3); reconcile mode taxonomy across thesis docs (P4); consumer adds time-based flush (P7); README gains a "Relationship to AdaptiveOrchestrator (thesis)" section codifying the Part-3 boundary.

**ADD:** `orchestrator_mode.yml` asset type + bridge translator (P5); minimum DLT expectation set on Silver (P6); optional `model_version`/`policy_version`/`latency_ms`/`cloud_reachable` fields on `bearing_inference.yml` (P11); Python ≥3.11 note; one Gold mode-history table (post-thesis if time is short).

**REMOVE:** `ml/` stubs, `monitoring/alert_rules.json`, `shared/schemas.py`, `shared/helpers.py`, `dlt/common/schemas.py` (empty), `edge/industrial_producer.py` stub, `terraform/unity_catalog/dev/` from git, `local/checkpoints_old..json`.

**DEFER:** batch analytics jobs (old Phase 2); Grafana/Prometheus on Azure; feature store/registry in platform; streaming serving; multi-region/prod Terraform apply.

**ISOLATE:** credit-card fraud (separate everything at runtime, shared patterns only); thesis evaluation path (never through Azure).

**PROMOTE:** the config-driven flattening from "feature" to headline platform capability in README/interviews — it is the differentiator, now proven across three live domains including a real research workload; the schema-aware null fallback deserves explicit mention as deliberate schema-evolution design.

---

## PART 14 — PRIORITIZED ROADMAP

**PHASE 0 — Academic alignment & schedule triage (this week)**
Objective: eliminate the P1/P2 risks. Actions: agree revised thesis timeline with Dr. Silva; adopt Sprint-v3 mode taxonomy and update arch doc to v1.1; write the README boundary section; commit all Phase 1 work. Code: none beyond docs. Definition of done: supervisor-acknowledged plan; clean `git status`. Academic value: existential. Dependencies: none.

**PHASE 1 — Thesis execution (dominant priority until submission)**
Objective: Sprints 4–10 of the approved plan (Isolation Forest F1>0.80 → Policy Executor → buffer/recovery → drift → SHAP → integration → formal evaluation), then thesis writing. All in `adaptive-edge-orchestrator`. The Azure platform is frozen except Phase-2 items below. Definition of done: `logs/s1–s5_results.json` exist and support H1–H3; chapters drafted. **Nothing in this review's platform work list may preempt this phase.**

**PHASE 2 — Thin platform additions serving the thesis (≤2 days total, interleaved)**
Objective: make the platform a genuine research archive. Actions: P3 rename; `orchestrator_mode.yml` + bridge translator + tests; optional inference metadata fields; Silver expectations; verify real NATS subjects against the orchestrator repo (P12). Definition of done: mode transitions visible in Silver; expectations green in a pipeline run. Academic value: independent cross-check of every thesis figure. Engineering value: quality gates.

**PHASE 3 — Silver/Gold production hardening (post-submission)**
Objective: close P6–P10 fully. Actions: consumer time-flush + DLQ quarantine path; pipeline-health observability (DLT event log query + alert); stub removal; IaC cleanup; schema-collision documentation; Gold bearing/mode tables. Definition of done: problem register P6–P10 closed.

**PHASE 4 — ML experimentation/evaluation enrichment (optional, post-thesis)**
Objective: turn archived thesis data into portfolio analytics — per-mode F1 dashboards, egress-reduction visualizations from Gold. Academic value: defense-demo material. Engineering value: end-to-end ML-adjacent story on Databricks.

**PHASE 5 — Multi-domain validation (post-thesis)**
Objective: make `industrial`/`wind_turbine` real or delete them; one new real domain end-to-end (vehicle tracking with GPS fields is the natural money-making candidate). Definition of done: no placeholder configs without producers, or placeholders clearly labeled.

**PHASE 6 — Production hardening (aligns with Roadmap V2 timeframe)**
Objective: managed identity, prod environment apply, retention policies, cost controls, monitoring maturity.

**PHASE 7 — Optional future domains (Roadmap V3 timeframe)**
Credit-card fraud in its own isolated stack; vehicle tracking as product; multi-tenant considerations — all per the V3 roadmap, funded by a defended thesis and a real job.

---

## PART 15 — FINAL CTO VERDICT

**1. Is the current architecture fundamentally sound?** Yes. Both systems are individually well-designed; the platform's core patterns (deterministic idempotency, config-driven onboarding, medallion discipline, IaC) are correct and — unusually for a portfolio project — *proven against a live deployment with real debugging history*. The unsound part was never the architecture; it was the blurred boundary between the two systems, which this review closes.

**2. Suitable as a reusable IoT/data/ML platform foundation?** Yes for IoT/data: three live domains, zero-code onboarding demonstrated. The ML layer is not in this platform and should not be until after the thesis — the thesis stack owns ML lifecycle for now.

**3. Academically suitable for the thesis?** As a *side-channel and generalizability demonstration*, yes. As the thesis platform, **no — and it must not try to be.** The approved architecture is AWS/local; the contribution is the Policy Executor; the examiner's evidence is S1–S5. Keep it that way.

**4. Missing for the thesis?** Time, above all (P2). Then: Sprints 4–10 themselves; mode-taxonomy reconciliation; ground-truth labeling discipline; model/policy version metadata; and the mode-transition event type if you want the platform to contribute cross-checks.

**5. Missing for a Silicon-Valley-level system?** Data-quality gates, consumer durability, observability, DLQ, schema-evolution policy — all named with fixes in Parts 8–9. Note what's *not* missing: correctness under retries, reproducible infra, honest documentation of dead paths. Many funded startups ship worse.

**6. Build next?** Phase 0 this week, then Sprint 4 of the thesis. On the platform: only the ≤2-day Phase-2 list.

**7. Explicitly NOT build?** Everything in Part 10. Especially: no Kafka on Azure, no K8s, no feature store, no second ML stack, no fraud pipeline until the thesis is bound.

**8. If this were my platform?** I would make exactly one strategic change: declare in writing that `industrial-ai-platform` is the V3 cloud-analytics prototype of the AdaptiveOrchestrator roadmap (cloud-agnostic Databricks, validated on Azure), and that the thesis evaluation stack is a separate, frozen, approved artifact. That one sentence turns an apparent inconsistency into a deliberate strategy — and it happens to be true.

**9. What makes this impressive in a senior interview?** Not the component list — the *decisions*: deterministic IDs proven to collapse production duplicates; config-only domain onboarding demonstrated live three times; a bundle-root migration debugged against real DAB constraints; schema-aware null fallback as deliberate evolution design; and the discipline to keep an ultra-low-latency edge loop out of the cloud path. Tell it as a decisions-and-trade-offs story, with the Bronze 16→8 Silver dedup screenshot as the proof.

**10. What makes the thesis academically strong?** The claim discipline you already have (precisely scoped contribution, quantified hypotheses, statistical tests planned) plus three things to protect: run the ablation honestly (which signals actually matter — RTT alone may do most of the work; report it either way), keep the CPU-dilution finding front and center as empirical motivation for calibration, and reconcile the mode taxonomy before an examiner does it for you. The platform buys you generalizability language ("the same event contract onboarded vehicle telemetry and bearing research data unchanged") — one paragraph, not a chapter.

**Bottom line:** strong platform, defensible thesis, one dangerous blur between them, and a calendar that is now the real critical path. Fix the boundary in writing, spend two days on the thin platform additions, then give the thesis everything until it's submitted.

