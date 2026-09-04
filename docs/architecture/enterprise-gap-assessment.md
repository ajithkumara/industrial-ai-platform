# Industrial AI Platform — Enterprise Architecture Gap Assessment

**Scope:** Forensic, read-only review of the Azure implementation (`industrial-ai-platform` repo) against Fortune-500 / enterprise production standards. No code was modified, committed, or deleted during this review.

**Method:** Five parallel forensic passes across the repo (ingestion/medallion pipeline, ML/MLOps, security/IAM/networking, CI/CD/IaC, observability/DR), each requiring file-path evidence for every claim. This document is my own synthesis and judgment applied to that evidence — the scoring, prioritization, and verdict are mine, not automated.

---

## STEP 1 — Repository Forensic Review (capability inventory)

| Capability | Status | Evidence |
|---|---|---|
| Event Hub ingestion | IMPLEMENTED | `terraform/modules/eventhub/main.tf` |
| Consumer schema validation (Pydantic envelope) | IMPLEMENTED | `shared/telemetry_event.py`, `consumer/eventhub_consumer.py:68-83` |
| Dead-letter queue | IMPLEMENTED | `consumer/storage_client.py:176-229` (`_dlq/year=/month=/day=/`) |
| Retry with backoff / circuit breaker | MISSING | No `tenacity`/`backoff` library use anywhere; failed flush just stays in memory buffer, no max-attempts |
| Consumer checkpointing | TECHNICALLY UNSAFE | `consumer/checkpoint.py` — local JSON file, advances **before** confirmed ADLS flush (`consumer/eventhub_consumer.py:105-119`); a crash between add() and flush loses events permanently with no re-delivery |
| Bronze immutability | IMPLEMENTED | `dlt/bronze/ingest_raw_events.py` — pure Auto Loader append, proven by `tests/integration/data_quality_scenarios.py` DQ2 |
| Bronze lineage metadata | PARTIALLY IMPLEMENTED | `_source_file`, `_ingested_at` columns only; no pipeline-run-ID lineage |
| Bronze retention/lifecycle policy | MISSING | No `azurerm_storage_management_policy` anywhere |
| Silver data-quality expectations | IMPLEMENTED | `dlt/silver/clean_and_deduplicate.py:38-41` (`@dlt.expect_or_drop`) — note: `dlt/common/expectations.py` is an **empty stub**, real logic lives elsewhere |
| Silver deduplication | IMPLEMENTED | `dlt/silver/clean_and_deduplicate.py:58-60` (window + `event_id`) |
| Silver quarantine (queryable) | MISSING | Malformed Silver rows are dropped, not quarantined; true quarantine table exists only at Gold |
| Gold ML feature table | IMPLEMENTED | `dlt/gold/bearing_ml_features.py` — 7 time-domain features, cross-verified against `ml/feature_spec.py` by `tests/test_feature_spec.py` |
| Gold quarantine table | IMPLEMENTED | `bearing_ml_features_quarantine` |
| Gold governance (UC grants) | IMPLEMENTED (dual path) | Terraform-managed per-schema grants (`terraform/modules/databricks/unity_catalog.tf:80-91`) + manually-run broader SQL grants (`grant_ci_sp_uc_permissions.sql`) |
| Placeholder Gold table | PLACEHOLDER | `dlt/gold/predictive_features.py` — `raise NotImplementedError`, excluded from the deployed pipeline |
| Empty "common" modules | PLACEHOLDER | `dlt/common/schemas.py`, `shared/schemas.py`, `shared/helpers.py` — docstring-only or `pass`-bodied, contradicting their promising filenames |
| Recording-level train/val/test split | IMPLEMENTED | `dlt/gold/bearing_ml_features.py:98-149`, enforced by `tests/test_train_bearing_isolation_forest_contract.py::test_training_script_never_reads_test_split` |
| Frozen validation-only threshold | IMPLEMENTED | `ml/train_bearing_isolation_forest.py:120-223`, read-not-recomputed at TEST, enforced by contract test |
| MLflow tracking | IMPLEMENTED (manual, no autolog, no pinned experiment location) | `ml/train_bearing_isolation_forest.py:181-249` |
| UC model registry | PARTIALLY IMPLEMENTED (inconsistent) | Edge model uses `industrial_ai.ml.*` (three-part, tested); CloudForest uses a bare name `cloud_forest_bearing` (not UC-qualified) |
| Model drift / champion-challenger | MISSING | Explicitly deferred to a separate, absent "thesis stack" repo per `docs/architecture/PLATFORM_THESIS_REVIEW_2026-08.md:233` |
| Model promotion gate | MISSING | Scoring job loads `"latest"` registered version by number, no alias, no approval step |
| VNet / private endpoints | MISSING (CRITICAL) | Zero `azurerm_virtual_network`/`azurerm_private_endpoint` resources anywhere |
| Storage account public access | TECHNICALLY UNSAFE | No `network_rules`; confirmed live default `public_network_access_enabled: true` |
| Key Vault public access | TECHNICALLY UNSAFE | No `network_acls` |
| Diagnostic settings / audit logging | MISSING | Zero `azurerm_monitor_diagnostic_setting` resources anywhere — Key Vault, Storage, Databricks audit trails are not captured |
| GitHub OIDC to Azure | MISSING | Static `AZURE_CLIENT_SECRET` used throughout, no federated credential |
| CI unit tests | IMPLEMENTED | `tests/` (14 files), run via `pytest tests/` in `ci.yml` |
| Contract tests (ML) | IMPLEMENTED | `tests/test_train_bearing_isolation_forest_contract.py` |
| SAST / secret scanning / dependency scanning / container scanning / SBOM | MISSING (all) | Zero tooling found repo-wide |
| Terraform plan-on-PR | PARTIALLY IMPLEMENTED | Runs, but PR comment doesn't show the actual diff, only "review the Actions log" |
| `test`/`prod` Terraform environments | TECHNICALLY UNSAFE / broken | Stale copies of an old `dev/main.tf`, missing required module arguments, `backend.tf` declares `local` backend while `bootstrap` generates azurerm `backend.hcl` for them — **neither environment can currently `plan` successfully** |
| `prevent_destroy` on critical resources | MISSING | Zero `lifecycle` blocks anywhere — directly implicated in the 2026-09-02 storage-account near-destroy incident |
| Monitoring alerts (3 rules) | PARTIALLY IMPLEMENTED | Defined and wired to an action group, but ALERT-01 (DLT failure) reads `AzureDiagnostics`, which nothing populates (no diagnostic setting) — **likely non-functional** |
| Dashboards | MISSING | Explicitly an open TODO in `README.md:235` |
| ML job failure alerting | MISSING | No `email_notifications`/`on_failure` block in any Databricks job YAML |
| Documentation (architecture/runbooks) | IMPLEMENTED, unusually strong | `docs/architecture/*`, `docs/deployment/*`, `docs/runbooks/*` — includes a self-critical thesis review and a live-incident-derived migration runbook |

*(This table condenses ~150 individually-verified findings from the five forensic passes; the full file-by-file evidence is preserved in this session's research and available on request.)*

---

## STEP 2 — Enterprise Data Engineering Assessment

**Ingestion** is the weakest link in the otherwise-solid medallion chain. The DLQ and Pydantic contract enforcement are genuine strengths — most portfolio projects don't have either. But two things would fail in production: (1) the checkpoint-advances-before-flush ordering bug is a real correctness defect, not a hardening gap — it silently loses data on crash, already happened once during testing per the project's own docs; (2) there is no backpressure control (`maxEventsPerTrigger` equivalent) and Event Hub is fixed at 1 throughput unit / 2 partitions with no autoscale — this ceiling will be hit long before "10,000 assets."

**Bronze** is architecturally correct (immutable append, ingestion metadata, DLQ before it) but has no retention/lifecycle policy — unbounded storage growth is a cost and compliance gap, not just a nice-to-have.

**Silver** has real DLT expectations and deterministic dedup — genuinely good. The gap is that failed rows are *dropped*, not *quarantined* at this layer (only Gold quarantines), so a silent data-quality regression at Silver is invisible without checking DLT's internal event log.

**Gold** is the strongest layer: feature/spec consistency is enforced by an actual test (`test_feature_spec.py`), not just documentation discipline. The quarantine table is a genuine engineering strength. The one real ML-data risk: no `partitionBy`/`OPTIMIZE`/`ZORDER`/`VACUUM` anywhere in the repo — at CWRU-dataset scale this doesn't matter; at "10,000 assets" scale, small-file accumulation from 20-event batch writes will degrade query performance materially.

**ML data lineage** end-to-end (raw event → feature → model → prediction) exists but is *reconstructible by joining IDs across tables*, not a first-class lineage record. This is acceptable for a research/portfolio project; it would not satisfy a regulated-industry audit requirement.

**What would fail under high-volume industrial load specifically:** the Event Hub capacity ceiling, the small-file problem from unbatched/under-batched writes, the lack of any compaction job, and the consumer's single-instance local checkpoint (no consumer-group scale-out — acknowledged directly in the project's own thesis review doc).

---

## STEP 3 — Reliability / SRE Assessment

There is no formal retry/backoff, no circuit breaker, and no timeout policy anywhere in the ingestion path. Failure isolation exists only at the DLQ boundary (malformed events don't block the pipeline) — there is no isolation for *infrastructure* failures (e.g., a transient ADLS 503 doesn't get retried with backoff, it just sits in the buffer for the next flush attempt indefinitely).

Semantics are effectively **at-most-once with a data-loss window** at the consumer (checkpoint-before-flush), and **at-least-once with dedup** from Bronze into Silver (duplicates land in Bronze, get deduplicated at Silver by `event_id`) — this is an inconsistent semantics story across the pipeline, worth fixing before calling this "production reliable."

**What an enterprise implementation should actually look like** for this specific pipeline:
- Consumer: advance the checkpoint *only after* a confirmed durable write (flush-then-checkpoint, not add-then-checkpoint), with an exponential-backoff retry (e.g., `tenacity`) around the ADLS write, and a dead-letter path for exhausted retries (already exists for schema failures — extend it to infra failures).
- Event Hub: enable auto-inflate (`auto_inflate_enabled = true`) with a defined max throughput-unit ceiling, and raise `message_retention` to at least 3-7 days to give a real replay window if the consumer is down for a maintenance window.
- DLT: Databricks-managed Structured Streaming checkpointing is already enterprise-appropriate — no change needed there.
- Model serving/scoring job failures: currently silent. An enterprise implementation adds `email_notifications`/`webhook_notifications` on job failure, minimum.

**Disaster recovery mechanics** (zone/region/service failure) are addressed narrowly: the platform survived one real disaster (subscription expiry) by rebuilding infrastructure from Git — that path is proven. Storage/Event Hub/Databricks-native regional failure is *not* addressed (LRS-only storage, no geo-redundancy anywhere).

---

## STEP 4 — Security / Zero Trust Review

| Severity | Finding | Evidence |
|---|---|---|
| **CRITICAL** | No VNet or private endpoints anywhere — storage, Key Vault, Event Hub, Databricks all reachable over public internet, gated by auth only | Zero `azurerm_virtual_network`/`azurerm_private_endpoint` resources repo-wide |
| **HIGH** | Storage account has no `network_rules`; confirmed live `public_network_access_enabled: true` | `terraform/modules/storage/main.tf`, `current-state.json:1259` |
| **HIGH** | Key Vault has no `network_acls`, publicly reachable, stores raw account-key/SAS connection strings | `terraform/modules/keyvault/main.tf` |
| **HIGH** | CI service principal holds subscription-wide `Contributor` **plus** storage-scoped `User Access Administrator`, authenticated via a static (non-OIDC, non-rotated) GitHub secret | `docs/deployment/subscription-migration-runbook.md` Step 1; `terraform/modules/rbac/main.tf` |
| **HIGH** | Storage account keys (not managed identity/OAuth) used by the ingestion consumer/producer application layer, and the raw key material is itself stored in Key Vault | `consumer/storage_client.py:54-58`, `.env.example:33` |
| **HIGH** | No diagnostic settings anywhere — Key Vault access, Storage access, Databricks/Unity Catalog audit trails are not captured, despite a Log Analytics workspace existing | Zero `azurerm_monitor_diagnostic_setting` resources |
| **HIGH** | No credential rotation automation or documented periodic process for the SP secret | Zero "rotat*" hits in `docs/` |
| **MEDIUM** | Databricks workspace uses default managed (non-VNet-injected) network | `terraform/modules/databricks/main.tf` — no `custom_parameters` |
| **MEDIUM** | `min_tls_version` not explicitly pinned on storage account (relies on provider default) | `terraform/modules/storage/main.tf` |
| **MEDIUM** | Key Vault uses legacy access policies (not RBAC); prod has no Key Vault module deployed at all, making the "purge protection true for prod" comment undeliverable | `terraform/modules/keyvault/main.tf:10`, `terraform/environments/prod/main.tf` |
| **MEDIUM** | Broad manual SQL grants to the CI SP on all UC schemas (`MODIFY`, `SELECT`) exist entirely outside Terraform state — untracked, undriftable | `grant_ci_sp_uc_permissions.sql` |
| **MEDIUM** | Workflow-level (not job-scoped) secret env vars in `ci.yml` widen blast radius unnecessarily | `.github/workflows/ci.yml:19-24` |
| **LOW** | No customer-managed keys for storage/Key Vault encryption at rest (Azure-managed keys only — acceptable default, not itself dangerous) | — |
| **LOW (positive finding)** | No hardcoded credentials committed anywhere; `.env`/tfstate correctly gitignored; Unity Catalog Terraform-managed grants are genuinely least-privilege per schema; Databricks-to-storage access correctly uses managed identity, not keys | `.gitignore`, `terraform/modules/access_connector/`, `terraform/modules/databricks/unity_catalog.tf` |

**What would concern a Fortune-500 security review most:** the combination of a publicly-reachable data plane, a single static credential with subscription-wide write access plus self-service RBAC-escalation rights, and zero audit trail to detect misuse of any of it. Individually each is a known/common gap in early-stage platforms; together, an attacker who obtains the GitHub `AZURE_CLIENT_SECRET` has essentially unaudited, unlogged control of the subscription and the data plane, with no rotation forcing time-boxed exposure.

---

## STEP 5 — Data Governance

Real governance exists at the **access-control** layer (Unity Catalog per-schema grants, tested and Terraform-managed) — this is more than most early-stage platforms have. What's missing is everything upstream of access control:

- **Data classification**: nothing in the repo tags data as PII/sensitive/regulated. The CWRU bearing dataset is public research data, so this hasn't mattered yet — it will the moment real industrial customer telemetry (which may include facility location, operator IDs, etc.) enters the pipeline.
- **Data contracts**: the Pydantic `TelemetryEvent` envelope functions as a lightweight, code-enforced contract — genuinely good practice — but there's no formal schema-registry-style versioning/compatibility-checking, and no equivalent contract for the asset-type-specific payload fields (only a config-driven, defensive-cast handling of missing fields).
- **Retention/deletion policy**: none. No lifecycle management, no documented "how do we delete a customer's data on request" procedure — this would be a hard blocker for any regulated-industry (e.g., GDPR-relevant) deployment.
- **Environment isolation**: nominally dev/test/prod, but test/prod are non-functional Terraform configurations today (see Step 9) — there is currently exactly one real environment.
- **Auditability**: blocked by the same diagnostic-settings gap noted in Security — without audit logs, "who accessed what" cannot be answered.

**What's required for regulated enterprise environments** (this is a "future" requirement, not a "now" one, given the current dataset is public research data): a data classification tag on every table/column, a documented retention/deletion SLA per data category, diagnostic-settings-driven audit logging routed to an immutable log sink, and a formal data-product ownership model (who owns `industrial_ai.gold.bearing_ml_features` and answers for its quality SLA).

---

## STEP 6 — Observability

**What exists today, verified:**

| Metric | Purpose | Collection | Threshold | Severity | Functional? |
|---|---|---|---|---|---|
| DLT pipeline failure | Detect Bronze/Silver/Gold pipeline breakage | Scheduled KQL query on `AzureDiagnostics` | `Count > 0` / 15 min | 1 | **Likely broken** — no diagnostic setting feeds this table |
| Event Hub `IncomingMessages` | Detect producer silence | Azure Monitor metric alert | `< 1` / 15 min | 2 | Yes |
| Subscription cost | Budget overrun | Consumption budget | 80% of $50/month | 2 | Yes |

**What's missing, with what I'd recommend:**

| Metric | Purpose | Collection mechanism | Alert threshold | Severity |
|---|---|---|---|---|
| Databricks/Storage/KeyVault diagnostic logs | Enables ALERT-01 to actually work + audit trail | `azurerm_monitor_diagnostic_setting` → Log Analytics | N/A (prerequisite) | Blocker for existing alert |
| Consumer→ADLS write failure rate | Catch the checkpoint/flush correctness gap in real time | App-level custom metric (App Insights already provisioned, unused) | >0 sustained 5 min | High |
| DLQ / quarantine row count | Catch silent data-quality regressions | Scheduled query on `_dlq` path + `bearing_ml_features_quarantine` | Rate-of-change threshold, e.g. >5% of batch | Medium |
| Databricks Job failure (CloudForest score, IF train/eval) | Catch silent ML pipeline breakage | `email_notifications`/`webhook_notifications` on the job resource | Any failure | High |
| Ingestion→Gold freshness | Detect a stalled pipeline that isn't technically "failed" | Query `last_seen_at` in `asset_health_summary` vs now | >30 min staleness | Medium |
| Prediction volume / anomaly rate | Cheapest possible drift proxy without building full drift infra | Scheduled query on scoring output table, week-over-week | >2x or <0.5x baseline | Low-Medium |

**Could an SRE run this at 2 AM today?** No. There is no dashboard, the one pipeline-failure alert is likely non-functional, no job-failure notification exists, and nothing signals data-quality regression short of manually querying tables. This is the single most actionable gap to close before calling any part of this "production."

---

## STEP 7 — ML / MLOps Maturity

This is, by a clear margin, the **strongest area of the platform** and deserves to be named as such — the discipline here exceeds most industry MLOps setups I've reviewed at this project stage:

- Recording-level train/val/test separation is not just implemented, it's **enforced by a source-inspection test** (`test_training_script_never_reads_test_split`) that would fail CI if someone accidentally read TEST data during training.
- The frozen-threshold methodology (select on VALIDATION, freeze as an artifact, read-don't-recompute at TEST) is genuinely rigorous and, again, test-enforced.
- `dataset_run_id` isolation prevents synthetic/test data from contaminating real experiment analysis.
- Feature-spec consistency between the DLT notebook and the pure-Python spec module is enforced by a dedicated test, not just a comment promising they match.

**Where it falls short of production MLOps** (expected — this is honestly labeled a baseline, and correctly so):
- No drift detection of any kind (explicitly deferred to a separate, currently-absent repo).
- No model promotion gate — the scoring job takes whatever is numerically "latest," with no staging/approval/alias step. A bad retrain would be live within 15 minutes with nobody in the loop.
- CloudForest doesn't follow the same UC-naming discipline as the edge model (bare registry name, not three-part) and isn't seed-pinned as an MLflow param — an inconsistency between the two model families that should be closed since the pattern to follow already exists and is tested.
- No experiment location pinned (`mlflow.set_experiment` never called) — runs land wherever the default resolves, which is fragile.

**Verdict on Isolation Forest specifically:** it is intentionally, correctly a baseline — the split/threshold/reproducibility discipline around it is what should be preserved and *extended* to CloudForest and any future model, not replaced. Do not swap the algorithm; close the promotion-gate and drift gaps around it instead.

---

## STEP 8 — CI/CD and DevSecOps

CI/CD mechanics are real and working (this entire session is evidence of that) — Python tests, Terraform validate/plan, Databricks bundle validate all run and gate merges. What's absent is every *security* layer of DevSecOps: no SAST, no secret scanning, no dependency scanning, no SBOM, no artifact signing. For a platform destined to become a company/commercial product, this is a Roadmap-B item, not urgent today given no external attack surface yet — but it should be added before any customer data flows through this pipeline.

**Concrete gaps worth naming precisely:**
- The Terraform-plan-on-PR comment doesn't show the actual plan diff — reviewers have to leave the PR to see what will change. Cheap to fix, meaningfully improves review quality.
- No OIDC federation to Azure — every workflow uses a static, non-rotated `AZURE_CLIENT_SECRET`. This is the single highest-leverage CI/CD security fix available (eliminates a standing credential entirely).
- No automated rollback and no post-deploy smoke test — `terraform apply -auto-approve` on push to main with no health check afterward means a "successful" deploy could still leave the platform broken with nothing catching it. `docs/deployment.md` documents manual smoke-test steps that exist but aren't run in CI.

---

## STEP 9 — Infrastructure-as-Code Maturity

**The `dev` environment is genuinely well-built** — modular, mostly parameterized, with a real one-command bootstrap for a brand-new subscription's remote state backend. This session proved it works end-to-end against a fresh subscription.

**The claimed 3-environment structure is not real today.** This is the single most important finding in this entire assessment, because it directly contradicts the "deployable to a new environment without editing files" goal stated in the request:

- `terraform/environments/test/main.tf` and `.../prod/main.tf` are byte-identical stale copies of an old `dev/main.tf`, missing required arguments that the current `databricks` and `monitoring` modules need. **`terraform plan` against either would fail immediately** with "Missing required argument."
- Their `backend.tf` files declare a `local` backend, while `terraform/bootstrap` generates real `azurerm` `backend.hcl` files for them anyway — these are incompatible; `terraform init -backend-config=backend.hcl` against test/prod as currently written would error.
- The `monitoring` module hardcodes `"dev"` into an action-group short name, a KQL query filter, and (critically) a **subscription-scoped** consumption budget resource name — meaning even after fixing the module-argument issue above, deploying `monitoring` to test or prod in the *same subscription* as dev would collide on the budget resource.

**Conceptual deployment path test (NEW SUBSCRIPTION → bootstrap → init → plan → apply → bundle deploy → verify), traced against `dev` only:**
This session executed this path for real. The remaining manual steps, none of which can currently be automated away, are: (1) committing the bootstrap-generated `backend.hcl` files back to git, (2) hand-editing and running a `.sql` file to grant Unity Catalog permissions (blocked on Databricks metastore-admin requirements, not a code gap), and (3) a one-time local `terraform apply -target=module.rbac` run with Owner credentials to bootstrap the CI SP's self-management rights. All three are honestly documented in `docs/deployment/subscription-migration-runbook.md` — this is a real strength: the gaps are *known and written down*, not hidden.

**Destroy safety is genuinely absent** — zero `lifecycle { prevent_destroy }` blocks anywhere, which is exactly what allowed the 2026-09-02 near-miss (an unset variable nearly triggered a full storage-account destroy/recreate, caught only by an unrelated permissions error, not by any safeguard).

---

## STEP 10 — Cloud-Agnostic Architecture Mapping

| Concept | Current Azure implementation | AWS equivalent | Abstraction needed? |
|---|---|---|---|
| Event streaming | Azure Event Hubs | Amazon Kinesis Data Streams / MSK | **Yes** — different partitioning/consumer-group models; abstract at the "event transport" interface, not the wire protocol |
| Object storage | ADLS Gen2 | S3 | **Yes, lightly** — both are object stores with hierarchical-namespace-like semantics; a thin `StorageClient` interface (already partially present in `consumer/storage_client.py`) is enough, no need for a heavy abstraction layer |
| Identity | Managed Identity + Service Principal | IAM Role + IAM User/OIDC | **Yes** — fundamentally different models (Azure AD vs IAM); this is domain logic that must be reimplemented per cloud, not abstracted away |
| Secrets | Key Vault | Secrets Manager / Parameter Store | **Yes, lightly** — both are simple KV secret stores; a thin interface is reasonable |
| Monitoring/alerting | Azure Monitor + Log Analytics | CloudWatch + CloudWatch Logs | **No** — alerting rules are different enough (KQL vs CloudWatch Logs Insights/metric filters) that native reimplementation per cloud is cheaper and clearer than a forced abstraction |
| Compute orchestration | Databricks (Azure-hosted) | Databricks (AWS-hosted) | **Cloud-neutral at the platform layer** — DLT pipelines, notebooks, job YAMLs, and Unity Catalog are largely portable as-is; only the underlying cloud resource (workspace, storage credential, network) changes |
| ML tracking | MLflow (via Databricks-managed) | MLflow (via Databricks-managed) | **Cloud-neutral** — no change needed |
| Data governance | Unity Catalog | Unity Catalog (AWS Databricks) | **Cloud-neutral** — same model, different underlying storage credential mechanism |
| IaC tooling | Terraform (azurerm + databricks providers) | Terraform (aws + databricks providers) | **Domain logic reusable, provider-specific resources are not** — the module *pattern* (bootstrap, per-env backend, tagging convention) is directly reusable; the resource blocks inside each module are not |
| CI/CD | GitHub Actions | GitHub Actions | **Cloud-neutral** — the workflow structure carries over; only the auth step (`ARM_*` → `AWS_*`/OIDC) changes |
| Domain/business logic | `dlt/`, `ml/`, `shared/telemetry_event.py`, feature engineering | Same | **Fully cloud-neutral already** — this is the platform's actual IP and requires zero change for AWS |

**Where I would *not* force abstraction:** monitoring/alerting (KQL and CloudWatch Insights are different enough that a forced common abstraction would be worse than two native implementations) and the Terraform resource layer itself (an abstraction layer over Terraform providers is a well-known anti-pattern — Terraform's module system is already the right abstraction boundary).

**Where abstraction is genuinely valuable:** the object-storage client and the event-transport producer/consumer interface, because the application code (`consumer/`, `edge/`) that talks to them is real business logic worth keeping cloud-neutral, and the interfaces are narrow enough (put/get/list; publish/subscribe) that a thin adapter is cheap and won't rot.

---

## STEP 11 — Cost Architecture

**Real cost controls already in place:** serverless Databricks compute for all active jobs (good default — no idle cluster cost), a single consumption budget alert at 80% of $50/month.

**Cost traps identified:**
- No storage lifecycle policy — Bronze/raw data will accumulate indefinitely at Hot tier with no cool/archive tiering, which is pure waste for data that's mostly write-once/rarely-read after processing.
- The monitoring module's hardcoded subscription-scoped budget means you cannot have a separate budget per environment even once test/prod are fixed — everything competes against one $50 ceiling.
- No per-resource-group or per-tag cost allocation — impossible to answer "what does the ML training workload cost vs. the ingestion path" without manually cross-referencing the Azure Cost Management portal.
- Log Analytics retention is a flat 30 days for everything — fine for dev, but this is a cost lever worth tuning per environment once test/prod exist for real.

**DEV/TEST/PROD cost control design** (for when the environments are actually fixed):
- DEV: short Log Analytics retention (7-14 days), aggressive lifecycle policy (move to Cool after 7 days), tight budget, serverless-only compute (already the case).
- TEST: similar to dev, but retained slightly longer to support longer-running validation cycles.
- PROD: longer Log Analytics retention (90+ days for audit/compliance), lifecycle policy tuned to actual data-access patterns (not yet known), budget sized to real workload, per-resource-group or per-tag budget alerts rather than one subscription-wide number.
- Cross-cutting: consistent `CostCenter`/`Environment` tags already exist via the `tags` variable pattern — this is a good foundation to build tag-based cost allocation on top of.

---

## STEP 12 — Performance / Scale

Assuming growth to 10,000 → 100,000 → 1,000,000 assets, the architectural bottlenecks, in the order they'd actually be hit:

1. **Event Hub throughput** (hit first, likely well before 10,000 assets sending regular telemetry): fixed at 1 throughput unit, 2 partitions, no autoscale. This is a configuration fix (`auto_inflate_enabled`, more partitions), not an architecture rework — but it will be the first wall hit.
2. **Consumer single-instance checkpoint**: the current consumer cannot scale out across multiple instances/consumer groups — this caps ingestion throughput regardless of how much Event Hub capacity exists behind it. This needs the checkpoint model reworked to a distributed one (or, more simply, moving ingestion fully into a Databricks Structured Streaming job instead of the standalone Python consumer, which would inherit DLT's already-correct distributed checkpointing).
3. **Small-file accumulation**: 20-event batch writes at low asset counts are fine; at high asset counts this produces a large number of small files with no compaction job to clean them up — Delta table read performance degrades. Fix is adding a scheduled `OPTIMIZE`/`VACUUM` job, which doesn't exist today at any scale.
4. **No partitioning on Delta tables**: irrelevant at CWRU-dataset scale, becomes a real query-performance problem once Gold tables hold telemetry from thousands of assets over months — needs partition columns (likely `event_date`, possibly `asset_type`).
5. **ML feature computation**: currently batch/notebook-based reading a single gold table with a `WHERE dataset_run_id = ...` filter — this pattern scales fine as long as the table itself is partitioned/optimized (see #4); no separate bottleneck identified here specifically.
6. **Serving queries**: no serving layer currently exists beyond ad-hoc SQL against Gold tables — this needs to be designed, not just scaled, once there's an actual serving requirement (e.g., a dashboard or API reading current asset health).

None of these require rearchitecting the medallion pattern itself — all six are hardening/scaling additions to the existing design, consistent with the "harden, don't rewrite" principle.

---

## STEP 13 — Multi-Tenancy

**Current state: not designed for multi-tenancy at all.** The Unity Catalog catalog name `industrial_ai` is hardcoded (not parameterized per tenant), there's no tenant-ID column or schema-per-tenant pattern, no row-level security, and `dataset_run_id` — the closest thing to a partitioning concept in the ML layer — is explicitly for isolating experiment runs, not tenants.

**Realistic multi-tenant model, if/when this becomes commercial**, in order of increasing isolation (and cost):
- **Row-level (cheapest, weakest isolation):** add a `tenant_id` column everywhere, enforce via Unity Catalog row-level security policies (a real UC feature, not yet used here) or view-based filtering. Fastest to build, hardest to fully trust for a security-sensitive industrial customer.
- **Schema-per-tenant (moderate isolation, moderate cost):** one Unity Catalog catalog, one schema set per tenant (`tenant_a.gold.bearing_ml_features`, `tenant_b.gold.bearing_ml_features`), UC grants scoped per schema — this reuses the exact grant pattern already built and tested in `terraform/modules/databricks/unity_catalog.tf`, just parameterized per tenant instead of hardcoded to one catalog.
- **Catalog-per-tenant (strongest isolation, highest cost/complexity):** full storage-account/catalog isolation per tenant — appropriate only for the largest/most security-sensitive customers, likely not needed for most.

Given the existing UC grant pattern is already schema-scoped and Terraform-driven, **schema-per-tenant is the natural next step** when multi-tenancy becomes a real requirement — it's an extension of what's already built, not a new pattern.

---

## STEP 14 — Disaster Recovery / Business Continuity

**RPO/RTO: not formally defined anywhere today.** `docs/disaster-recovery.md` gives an informal ~30-45 minute rebuild-time figure, which functions as a de facto RTO but isn't labeled as one, and no RPO is stated — meaning data loss for anything not manually exported before an incident is implicitly unbounded.

**What can be reconstructed from IaC alone (no backup needed):** resource group, storage account, Event Hub namespace, Databricks workspace, Unity Catalog catalog/schema/grants, DLT pipeline definitions, job definitions — all of this is genuinely code-as-config and was proven reconstructible during the real 2026-08-26 subscription-expiry incident.

**What requires backup and currently doesn't have automated backup:**
- ADLS Bronze/Silver/Gold data itself — LRS-only, versioning **disabled** (confirmed in live state), no lifecycle policy. A storage-account-level incident (like the near-miss this session hit) had no safety net beyond luck.
- Event Hub in-flight data — 1-day retention means anything not consumed within 24 hours is gone forever; there's no Capture feature enabled to persist raw events to storage as a durability backstop.
- MLflow model artifacts / trained models — one manual, non-scheduled backup script exists (`scripts/backup_before_subscription_expiry.ps1`) that must be run *before* a known-upcoming incident; there is no automated, scheduled backup, and the restore path is marked "(optional)" in its own runbook, with no evidence it's ever actually been exercised end-to-end (the real 2026-08-26 recovery re-ingested and retrained from scratch rather than restoring from this backup).
- Key Vault — soft-delete on (7-day window) but purge protection off, meaning the recovery window isn't guaranteed.

**Recommended enterprise DR design for this platform:**
- RPO target: 24 hours for ML artifacts (daily automated backup, not manual/pre-incident-only), near-zero for Terraform state (already versioned) — Event Hub retention should rise to 3-7 days minimum to give the consumer downtime tolerance.
- RTO target: keep the proven ~30-45 minute infra-rebuild-from-Git figure, but *formally document it* as the RTO and add the missing storage-versioning/lifecycle piece so data isn't the long pole in a real recovery.
- Enable ADLS blob versioning (currently off — cheap, high-value fix) as a first line of defense against exactly the kind of accidental-destroy incident that already happened once.
- Automate the existing manual backup script on a schedule (e.g., weekly) rather than relying on someone remembering to run it before a known event.
- Actually test the restore path once, end-to-end, and document the result — right now only the "rebuild clean" path has been proven, not "restore from backup."

---

## STEP 15 — Architectural Maturity Scorecard

Scoring: 0=absent, 1=experimental, 2=basic, 3=production-capable, 4=enterprise-grade, 5=Fortune-500 mature.

| # | Category | Score | Rationale (one line) |
|---|---|---|---|
| 1 | Data ingestion | **2** | Real DLQ + validation, but a checkpoint/flush correctness bug and no backpressure control |
| 2 | Data engineering | **3** | Genuinely solid medallion pattern; scale landmines (no partitioning/compaction) not yet hit |
| 3 | Data quality | **3** | Real expectations + quarantine + tests, but Silver drops rather than quarantines |
| 4 | Data governance | **2** | Strong UC access control; no classification, retention, or contract-versioning layer |
| 5 | Security | **1** | Critical network exposure + credential-scope combination with no audit trail |
| 6 | Reliability | **2** | Inconsistent delivery semantics, no retry/backoff, one proven single-instance bottleneck |
| 7 | Observability | **2** | Three alerts exist, one is likely non-functional, no dashboards, no ML-failure alerting |
| 8 | MLOps | **3** | The standout area — test-enforced split/threshold discipline; no drift/promotion gate |
| 9 | CI/CD | **2** | Real, working pipeline; no rollback, weak PR plan visibility |
| 10 | DevSecOps | **1** | Zero security scanning tooling of any kind |
| 11 | Infrastructure-as-Code | **2** | `dev` is strong; the claimed 3-environment structure is currently non-functional |
| 12 | Disaster recovery | **2** | One real incident survived via IaC rebuild; data-layer backup is manual/unproven |
| 13 | Cost engineering | **2** | Sensible serverless defaults; no lifecycle policy, no per-resource cost allocation |
| 14 | Scalability | **1** | Multiple concrete bottlenecks that would hit well before "10,000 assets" |
| 15 | Multi-tenancy | **0** | Not designed for at all — single hardcoded catalog |
| 16 | Cloud portability | **1** | Domain logic is portable; every infra layer is currently Azure-specific with no adapter |
| 17 | Documentation | **4** | A genuine strength — self-critical, incident-derived, unusually thorough |
| 18 | Operational readiness | **1** | No dashboard, one broken alert, no ML job failure notification — not 2-AM-operable today |

**Overall maturity score: 1.9 / 5** — between "basic" and "production-capable." This is an honest, unusually well-engineered *research/portfolio-grade platform with real production discipline in its ML and data-quality layers*, but it is not yet production-capable as a whole, primarily due to security and operational-readiness gaps rather than data-engineering weakness.

---

## STEP 16 — Gap Prioritization

| Priority | Gap | Why it matters | Evidence | Recommended solution | Effort | Risk if deferred | Dependencies | Do now? |
|---|---|---|---|---|---|---|---|---|
| **P0** | No `prevent_destroy` on storage/Key Vault | Already caused one near-total-data-loss incident | `docs/deployment/subscription-migration-runbook.md` 2026-09-02 incident | Add `lifecycle { prevent_destroy = true }` to storage account + Key Vault resources | 1 hour | High (recurrence) | None | **Yes** |
| **P0** | Consumer checkpoint advances before confirmed flush | Silent, permanent data loss on crash | `consumer/eventhub_consumer.py:105-119` | Reorder: flush → confirm → checkpoint | 2-4 hours | High (silent data loss) | None | **Yes** |
| **P0** | Storage account + Key Vault publicly accessible, no diagnostic logging | Unauditable, unrestricted access to all platform data | Confirmed via `current-state.json` + zero diagnostic-setting resources | At minimum: add diagnostic settings routing to Log Analytics (cheap, immediate audit trail). Network restriction (private endpoints) is P1, not P0, given no production customer data yet | 1 day (diagnostics only) | High (undetectable breach) | None | **Yes, diagnostics; defer network isolation** |
| **P1** | `test`/`prod` Terraform environments are non-functional | Claimed multi-env story is false; would break on first real use | Stale `main.tf`, missing required args, incompatible backends | Regenerate `test`/`prod` from current `dev/main.tf` pattern; fix `monitoring` module's hardcoded "dev" strings | 1-2 days | Medium (blocks any real promotion pipeline) | None | Before AWS work begins |
| **P1** | Static, non-rotated `AZURE_CLIENT_SECRET`, no OIDC | Standing credential risk with subscription-wide + self-escalation rights | `.github/workflows/*.yml` | Migrate to GitHub OIDC federated credential | 1 day | High (long-lived credential compromise) | Azure AD app registration change | Before any customer/production data |
| **P1** | ALERT-01 likely non-functional (no diagnostic setting feeds `AzureDiagnostics`) | The one pipeline-failure alert doesn't actually fire | Cross-referenced monitoring module + zero diagnostic settings | Same diagnostic-settings fix as above closes this too | Included above | Medium | P0 diagnostics fix | Yes, bundled |
| **P1** | No ML job failure notification | Silent scoring/training failures | No `email_notifications` block in any job YAML | Add `email_notifications.on_failure` to all 4 job resources | 2-4 hours | Medium | None | Yes |
| **P1** | No storage lifecycle policy / no Delta compaction job | Unbounded cost growth + future query-perf collapse | Zero `azurerm_storage_management_policy`, zero `OPTIMIZE`/`VACUUM` | Add lifecycle policy (Hot→Cool after N days) + scheduled `OPTIMIZE`/`VACUUM` job | 1-2 days | Medium (cost + future perf) | None | Before scale-up, not before AWS |
| **P2** | No model promotion gate (scoring always loads "latest") | A bad retrain goes live automatically within 15 minutes | `ml/cloud_forest/score_escalations.py:75-89` | Adopt UC model aliases (`@champion`), require alias update as the promotion step | 1-2 days | Medium (once retraining is automated — currently manual, so lower urgency today) | None | Roadmap B |
| **P2** | No SAST/secret-scanning/dependency-scanning in CI | No automated defense against introduced vulnerabilities | Zero tooling found | Add GitHub native secret scanning + Dependabot + CodeQL (all free for public/most repos) | 1 day | Low today, rises with contributors/customers | None | Roadmap B |
| **P2** | No dashboard | Can't observe platform health without querying tables by hand | `README.md:235` open TODO | Build a Databricks SQL/Lakeview dashboard on top of existing Gold tables | 2-3 days | Low-Medium | None | Roadmap B |
| **P3** | Multi-tenancy | Not needed until there's a second tenant | N/A | Schema-per-tenant extension of existing UC grant pattern when needed | N/A | Low today | UC grant module refactor | Defer to Roadmap C |
| **P3** | Cloud abstraction layer for storage/events | Premature before AWS implementation exists to abstract against | N/A | Build the AWS implementation first, extract the common interface *after*, from two real implementations, not in advance | N/A | Low | AWS implementation | Defer — do NOT build speculative abstraction now |

---

## STEP 17 — Rework Justification (why nothing above says "rewrite")

Every recommendation in Step 16 is a HARDEN/PARAMETERIZE/OBSERVE/GOVERN/AUTOMATE action, not a REWRITE. Specifically:

- The medallion pipeline, DLT expectations, and ML train/test discipline are **not touched** — they're the strongest part of the platform and the evidence shows it.
- The checkpoint fix is a **reordering of two existing lines**, not a redesign of the consumer.
- `prevent_destroy` and diagnostic settings are **additive Terraform blocks**, not module rewrites.
- Fixing `test`/`prod` means **copying the working `dev` pattern**, not inventing a new one.
- OIDC migration changes **how CI authenticates**, not what it does.
- The model promotion gate adds **an alias-based indirection layer** on top of the existing, working UC registry — CloudForest and Isolation Forest stay exactly as they are.

Nothing in this assessment recommends replacing Terraform, Databricks, Event Hubs, Unity Catalog, MLflow, or Isolation Forest/CloudForest. The gaps found are real but are hardening gaps in an otherwise sound architecture, not signs of a wrong architecture.

---

## STEP 18 — Roadmaps

### Roadmap A — Next 1 day (materially improves production readiness, minimal effort)
1. Add `lifecycle { prevent_destroy = true }` to the storage account and Key Vault Terraform resources.
2. Fix the consumer checkpoint ordering bug (flush-confirm-then-checkpoint).
3. Add `azurerm_monitor_diagnostic_setting` resources routing Storage, Key Vault, and Databricks logs to the existing Log Analytics workspace (fixes ALERT-01 and closes the audit-log gap simultaneously).
4. Add `email_notifications.on_failure` to all four Databricks job resources.
5. Enable ADLS blob versioning (one-line Terraform change, closes a real backup gap cheaply).

### Roadmap B — Next 1–2 weeks (enterprise hardening)
1. Regenerate `test`/`prod` Terraform environments from the current working `dev` pattern; parameterize the `monitoring` module so it no longer hardcodes "dev."
2. Migrate CI/CD Azure authentication to GitHub OIDC, retire the static `AZURE_CLIENT_SECRET`.
3. Add a storage lifecycle policy and a scheduled Delta `OPTIMIZE`/`VACUUM` job.
4. Add GitHub native secret scanning + Dependabot + CodeQL to the repo.
5. Build a minimal Gold-layer dashboard (Databricks SQL/Lakeview) covering pipeline freshness, quarantine rate, and job success/failure.
6. Adopt Unity Catalog model aliases (`@champion`) for both model families as the promotion mechanism, closing the CloudForest naming inconsistency at the same time.
7. Raise Event Hub message retention (1 day → 3-7 days) and evaluate enabling autoscale.
8. Automate the existing manual model-backup script on a schedule; test the restore path once and document the result.

### Roadmap C — Future company platform (do not build yet)
1. Network isolation: VNet injection for Databricks, private endpoints for storage/Key Vault/Event Hub — appropriate once real customer data is in the pipeline, premature before then.
2. Formal data classification and retention/deletion policy per data category — needed before any regulated-industry customer.
3. Schema-per-tenant multi-tenancy model, extending the existing UC grant pattern.
4. Drift/model-monitoring infrastructure (data drift, feature drift, prediction-distribution tracking) — the platform's own docs already correctly identify this as a distinct future system, not a gap to close today.
5. A genuine cloud-storage/event-transport abstraction layer — build only after the AWS implementation exists as a second real reference point, extracted from two working implementations rather than designed speculatively.
6. CMK encryption, formal RPO/RTO SLAs, and audit-log immutability — compliance-grade requirements appropriate once there's a compliance-scope customer.

---

## STEP 19 — AWS Readiness Gate

**YES — ready for AWS, with 4 specific fixes done first (all are Roadmap A, one day of work):**

1. `prevent_destroy` on critical resources.
2. The consumer checkpoint ordering fix.
3. Diagnostic settings (fixes the broken alert and the audit gap in one move).
4. Job failure notifications.

These four are chosen as gates — not the full Roadmap A/B list — because they are the items that would otherwise get **copy-pasted into the AWS implementation as-is**, propagating the same correctness bug and the same "no safety net" pattern into a second cloud. Everything else in Roadmap A/B (test/prod environments, OIDC, lifecycle policies, dashboards) can proceed in parallel with AWS work or after it — they don't risk contaminating the AWS reference architecture if deferred.

The medallion pattern, the UC governance model, the ML train/test isolation discipline, the Terraform module/bootstrap pattern, and the documentation discipline are all genuinely good reference material worth replicating into AWS as-is.

---

## STEP 20 — Final Executive Report

### Executive Verdict

**This is a strong engineering prototype — not yet production-capable, and not yet enterprise-ready.**

I'm choosing this category deliberately over "academic prototype" because the ML train/test discipline, the DLT data-quality expectations, the working end-to-end CI/CD (proven repeatedly in this session), and the incident-derived documentation all exceed what "academic prototype" implies. I'm choosing it over "production-capable" because of the security posture (Step 4) and operational-readiness score (Step 6/15) — a platform that's publicly network-exposed with a self-escalating static credential and no audit trail is not production-capable regardless of how good its data pipeline is, and the "could an SRE run this at 2 AM" test fails today. The overall 1.9/5 score reflects that this platform is unevenly mature: genuinely excellent in ML/data-quality discipline and documentation, genuinely weak in security and operational observability — an honest, defensible research/portfolio platform, not yet a defensible production system.

### Top 10 Changes I Should Make

1. Fix the consumer checkpoint-before-flush ordering bug (real data-loss defect).
2. Add `prevent_destroy` to storage account and Key Vault.
3. Add diagnostic settings for Storage/Key Vault/Databricks (fixes the broken alert + closes the audit gap).
4. Add job-failure notifications to all four Databricks jobs.
5. Migrate to GitHub OIDC, retire the static Azure client secret.
6. Fix `test`/`prod` Terraform environments to match the working `dev` pattern.
7. Add a storage lifecycle policy and a scheduled `OPTIMIZE`/`VACUUM` job.
8. Adopt Unity Catalog model aliases as the promotion mechanism for both model families.
9. Add GitHub native secret scanning + Dependabot + CodeQL.
10. Build a minimal operational dashboard over the existing Gold tables.

### What NOT to Change

- The medallion Bronze/Silver/Gold pattern and its DLT expectations.
- The recording-level train/val/test split methodology and its test enforcement.
- The frozen-validation-threshold methodology.
- Isolation Forest / CloudForest as the model choice — both are appropriately scoped baselines; the gap is lifecycle automation around them, not the algorithm.
- The Unity Catalog per-schema grant pattern — it's genuinely least-privilege and should be extended (e.g., to multi-tenancy), not replaced.
- The Terraform bootstrap module pattern — it works, proven twice in this session.
- MLflow as the tracking/registry tool.
- Databricks Asset Bundles as the deployment mechanism.

### Recommended Target Architecture

**Azure:** current architecture, hardened per Roadmap A/B — same services, same modules, with network isolation, diagnostic logging, credential rotation via OIDC, and a real 3-environment promotion pipeline added on top.

**AWS:** Kinesis (or MSK) replacing Event Hubs, S3 replacing ADLS Gen2, IAM roles/OIDC replacing managed identity/service principals, Secrets Manager replacing Key Vault, CloudWatch replacing Azure Monitor — with Databricks (AWS-hosted), Unity Catalog, MLflow, DLT pipelines, and all `dlt/`/`ml/`/`shared/` domain logic carried over largely unchanged, since that layer is already cloud-neutral.

**Cloud-neutral core:** the medallion data model, the Pydantic event contract, the ML feature/split/threshold/registry discipline, and the Terraform module *pattern* (not the provider-specific resources) — these are the platform's actual reusable IP and should be treated as the stable center around which both cloud implementations rotate.

### Recommended Next Sequence

1. Execute Roadmap A (1 day) — this is the AWS readiness gate.
2. Begin AWS implementation in parallel with Roadmap B — Roadmap B items (OIDC, test/prod fix, dashboards, lifecycle policies) don't block AWS and shouldn't delay it.
3. After both Azure and AWS implementations exist, extract the cloud-storage/event-transport abstraction layer from the two real implementations (not before — avoid speculative abstraction).
4. Roadmap C items (network isolation, multi-tenancy, drift infrastructure, compliance-grade controls) become relevant only once there's a real trigger for them: a production customer, a second tenant, or a regulated-industry deployment target respectively. Building them earlier is effort spent on requirements that don't exist yet.

---

*This assessment is intentionally critical, per the request. The honest read is: this platform's data and ML engineering discipline is genuinely above-average for its stage: its security and operational-readiness posture is genuinely below where it needs to be before real data flows through it. Both things are true at once, and the roadmap above is sequenced to close the gap that matters most first.*
