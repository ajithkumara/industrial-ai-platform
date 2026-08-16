# Cloud-Only Acceptance Runbook

**Goal:** prove the cloud platform works end to end — Event Hub → Bronze → Silver → Gold → CloudForest — using synthetic data only. **No NATS, no `adaptive-edge-orchestrator`, no edge process.**

The point is not "the notebooks ran." It is that scenarios with **pre-computed known answers** reproduce those answers exactly. If Scenario F returns precision 0.941176 and Scenario B returns agreement 0.5, the measurement instrument is trustworthy and every later evaluation number inherits that trust.

**Time:** ~45 min, most of it waiting on the DLT pipeline.

---

## 0. Prerequisites

| Requirement | Check |
|---|---|
| Databricks CLI authenticated | `databricks auth profiles` shows `canada-central-dev` |
| `.env` populated | Event Hub + storage connection strings present |
| Python ≥ 3.11 | `python --version` (3.10 breaks two consumer modules) |
| Clean git state | Everything committed — see §1 |

**Know your batch size before you start:**

```powershell
Select-String -Path .env -Pattern "RAW_BATCH_SIZE"
```

This run sends **181 events**, of which **177 reach the consumer's buffer**. With `RAW_BATCH_SIZE=50` that is 3 automatic flushes (150 events) leaving **27 events stranded in memory**. They only land when the consumer is stopped with **Ctrl+C**. Closing the terminal window instead loses them — this exact failure cost a debugging session previously. Either accept it and press Ctrl+C properly, or set `RAW_BATCH_SIZE=10` for this run.

---

## 1. Pre-flight

```powershell
cd C:\Users\Laptop\Documents\workspace\industrial-ai-platform

if (Test-Path .git\index.lock) { Remove-Item .git\index.lock }   # OneDrive artefact
git status
```

Confirm the new files are listed, then:

```powershell
python -m pytest tests/ -q
```

**Expect: 91 passed.** If anything fails, stop — do not deploy a failing instrument.

```powershell
git add -A
git commit -m "Add data-quality scenarios, payload sizing, leakage-safe ML feature dataset"
git push
```

---

## 2. Validate and deploy

```powershell
databricks bundle validate -t dev
```

**Expect:** `Validation OK!`

```powershell
databricks bundle deploy -t dev
databricks bundle summary -t dev
```

**Expect:** the pipeline resource plus the two CloudForest jobs. The pipeline should now carry **10 notebooks** (1 Bronze, 2 Silver, 7 Gold).

---

## 3. Start the consumer

**Separate terminal, leave it running:**

```powershell
cd C:\Users\Laptop\Documents\workspace\industrial-ai-platform
python -m consumer.eventhub_consumer
```

Wait for `Waiting for events...` before sending anything. The consumer starts at `@latest` when no checkpoint exists, so **events sent before it is listening are lost.**

---

## 4. Send the synthetic events

**Third terminal:**

```powershell
cd C:\Users\Laptop\Documents\workspace\industrial-ai-platform
python -m tests.integration.cloud_e2e_scenario --all --data-quality --include-cloudforest-smoke
```

**Expect: 181 events sent**, and `expected_results.json` written. The console prints every verification query with its expected value — keep that output.

Breakdown:

| Group | Events | Notes |
|---|---|---|
| A normal operation | 20 | 10 sensor + 10 inference |
| B edge uncertain (HYBRID) | 18 | 6 sensor + 6 inference + 6 pre-built cloud_validation |
| C edge-only | 7 | context + mode transition + 5 inference |
| D autonomous | 11 | context ×2 + mode + 8 inference |
| E recovery | 3 | 2 mode transitions + 1 context |
| F confusion matrix | 100 | inference only |
| CloudForest smoke | 10 | 5 sensor + 5 inference, **no** cloud_validation |
| Data quality DQ1–DQ11 | 12 | 4 of these must be rejected |

---

## 5. Flush and stop the consumer

In the consumer terminal, watch for `Buffered N/…`. When the sender has finished:

**Press Ctrl+C in the consumer terminal.** Do not close the window.

**Expect:** a final flush, then `Consumer stopped by user.`

Confirm in Azure Storage Explorer that new files exist under:

```
raw/telemetry/year=YYYY/month=MM/day=DD/
raw/telemetry/_dlq/year=YYYY/month=MM/day=DD/
```

**Checkpoint 1 — the DLQ is the first real assertion.**

**Expect exactly 4 DLQ files.** They correspond to the four gate-1 rejections:

| Scenario | Why rejected |
|---|---|
| DQ3 | missing `event_id` |
| DQ4 | unexpected extra envelope field (`extra="forbid"`) |
| DQ5 | `payload` sent as a string, not an object |
| DQ6 | empty-string `event_id` (`min_length=1`) |

More than 4 means something legitimate is being rejected. Fewer means a gate is not holding — **DQ6 in particular is the regression guard for the empty-`event_id` defect this suite found.**

---

## 6. Run the pipeline

```powershell
databricks bundle run industrial_ai_dlt_pipeline -t dev
```

Watch for `UPDATE_PROGRESS` → `COMPLETED`. Expected new tables:

```
industrial_ai.gold.mode_history
industrial_ai.gold.detection_performance
industrial_ai.gold.edge_autonomy
industrial_ai.gold.cloud_egress
industrial_ai.gold.escalation_efficacy
industrial_ai.gold.bearing_ml_features
industrial_ai.gold.bearing_ml_features_quarantine
```

---

## 7. Verification

Run each in a Databricks SQL editor. Queries are scoped by `seq` ranges and device IDs so prior runs do not interfere.

### 7.1 Bronze — raw evidence, duplicates retained

```sql
SELECT count(*) AS bronze_rows
FROM industrial_ai.bronze.telemetry_bronze
WHERE device_id = 'bearing.DQ';
```
**Expect 8** — DQ1 (1) + DQ2 (2, both retained) + DQ7, DQ8, DQ9, DQ10, DQ11 (1 each). DQ3–DQ6 never arrive.

### 7.2 Silver — canonical, deduplicated

```sql
SELECT count(*) AS silver_rows
FROM industrial_ai.silver.cleaned_telemetry_events
WHERE device_id = 'bearing.DQ';
```
**Expect 6** — 8 Bronze rows, minus DQ2's duplicate collapsed by dedup, minus DQ7 dropped by the `valid_timestamp` expectation.

This single pair of numbers (**8 → 6**) demonstrates Bronze immutability *and* Silver canonicalisation together.

```sql
-- DQ7: reached Bronze, refused by Silver
SELECT 'bronze' AS layer, count(*) FROM industrial_ai.bronze.telemetry_bronze
WHERE timestamp = 'not-a-real-timestamp'
UNION ALL
SELECT 'silver', count(*) FROM industrial_ai.silver.cleaned_telemetry_events
WHERE device_id='bearing.DQ' AND timestamp IS NULL;
```
**Expect bronze = 1, silver = 0.**

```sql
-- DQ8: unmodelled domain degrades gracefully
SELECT
  (SELECT count(*) FROM industrial_ai.silver.cleaned_telemetry_events
     WHERE asset_type='mystery_sensor') AS in_generic_silver,
  (SELECT count(*) FROM industrial_ai.silver.silver_bearing_sensor_telemetry
     WHERE device_id='bearing.DQ' AND source_file='normal_0hp.mat'
       AND ground_truth_label='normal') AS in_flattened;
```
**Expect `in_generic_silver` = 1.** An unknown asset type must remain queryable and must **not** fail the pipeline update.

### 7.3 Gold — Scenario F, exact confusion matrix

**The single most important assertion in this runbook.**

```sql
SELECT tp, fp, fn, tn, precision, recall, f1
FROM industrial_ai.gold.detection_performance
WHERE mode = 'CLOUD_OPTIMISED' AND model_version = 'edge-v1.0-synthetic';
```

| Column | Expected |
|---|---|
| tp | 80 |
| fp | 5 |
| fn | 10 |
| tn | 5 |
| precision | 0.941176… |
| recall | 0.888889… |
| f1 | 0.914286… |

Exact match ⇒ the Gold aggregation logic is correct and every later F1 figure is trustworthy. Any deviation ⇒ stop and fix before running real experiments.

### 7.4 Gold — Scenario B, escalation efficacy

```sql
SELECT n_escalations, agreement_rate, edge_accuracy,
       cloud_accuracy, cloud_accuracy_improvement
FROM industrial_ai.gold.escalation_efficacy
WHERE mode = 'HYBRID' AND edge_confidence_bucket = 'low';
```

| Column | Expected |
|---|---|
| n_escalations | 6 |
| agreement_rate | 0.5 |
| edge_accuracy | 0.5 |
| cloud_accuracy | 1.0 |
| cloud_accuracy_improvement | 0.5 |

This is the C4 evidence path proven with a known answer, before any real model is involved.

### 7.5 Gold — orchestration evidence

```sql
SELECT from_mode, to_mode, trigger, mode_switch_latency_s
FROM industrial_ai.gold.mode_history
WHERE device_id = 'edge-node-01'
ORDER BY transition_at;
```
**Expect 4 transitions:** `CLOUD_OPTIMISED→EDGE_ONLY` (trigger `cpu`), `EDGE_ONLY→EDGE_AUTONOMOUS` (`network`), `EDGE_AUTONOMOUS→HYBRID` (`recovery`), `HYBRID→CLOUD_OPTIMISED` (`recovery`).

The `trigger` column populated with distinct values is the direct evidence for gap claims C1/C2 — mode changes are driven by live context, not fixed at design time.

```sql
SELECT n_events_during_outage, n_anomalies_during_outage,
       largest_inter_event_gap_s, outage_duration_s
FROM industrial_ai.gold.edge_autonomy
WHERE device_id = 'edge-node-01'
ORDER BY window_started_at DESC LIMIT 1;
```
**Expect:** 8 events, 1 anomaly, largest gap ≈ 2.0 s, duration ≈ 14 s. A stable small gap is continuity evidence (H2).

### 7.6 Gold — ML feature dataset and quarantine

```sql
SELECT
  (SELECT count(*) FROM industrial_ai.gold.bearing_ml_features) AS features,
  (SELECT count(*) FROM industrial_ai.gold.bearing_ml_features_quarantine) AS quarantined;
```
**Expect features = 24, quarantined = 2.**

The 2 quarantined rows are **DQ9** (missing `rms`) and **DQ10** (uncastable `kurtosis`) — the proof that invalid rows are rejected with a reason rather than silently NULL-filled into training data.

```sql
SELECT event_id, quarantine_missing_columns, quarantine_reason
FROM industrial_ai.gold.bearing_ml_features_quarantine;
```
**Expect** one row naming `rms`, one naming `kurtosis`.

```sql
-- No feature column may ever be NULL in the feature table
SELECT count(*) AS must_be_zero
FROM industrial_ai.gold.bearing_ml_features
WHERE rms IS NULL OR peak IS NULL OR crest IS NULL OR kurtosis IS NULL
   OR skew IS NULL OR variance IS NULL OR mean_abs IS NULL;
```
**Expect 0.** (`@dlt.expect_or_fail` should have failed the update otherwise.)

```sql
-- Leakage guard: no recording may appear in two splits
SELECT source_file, count(DISTINCT dataset_split) AS n_splits
FROM industrial_ai.gold.bearing_ml_features
GROUP BY source_file HAVING count(DISTINCT dataset_split) > 1;
```
**Expect 0 rows.** Any row here is recording-level leakage and invalidates every reported metric.

```sql
-- Unsupervised contract: only normal windows are training-eligible
SELECT dataset_split, ground_truth_label, is_training_eligible, count(*)
FROM industrial_ai.gold.bearing_ml_features
GROUP BY 1,2,3 ORDER BY 1,2;
```
**Expect** `is_training_eligible = true` **only** where `dataset_split='TRAIN'` and `ground_truth_label='normal'`.

---

## 8. CloudForest (optional, after §7 passes)

Only meaningful once the feature table is populated.

```powershell
databricks bundle run cloud_forest_train -t dev
databricks bundle run cloud_forest_score_escalations -t dev
```

```sql
SELECT source_event_id, cloud_score, cloud_model_version, agrees_with_edge
FROM industrial_ai.silver.silver_cloud_validation_results
WHERE cloud_model_version LIKE 'cloud_forest_bearing-v%';
```
**Expect 5 rows** — one per CloudForest smoke escalation — with `cloud_score` in [0, 1].

Structural assertion only. Exact agreement values are **not** predictable from a real trained model, unlike Scenario B's pre-computed path.

---

## 9. Known gaps — expected, not failures

| Observation | Why | Action |
|---|---|---|
| `sampling_rate_hz` is NULL everywhere | Generators do not emit it yet; the column was added for future spectral work | None. Required only once waveforms flow. |
| Splits are degenerate (e.g. all normal → TRAIN) | Synthetic data has ~4 distinct `source_file` values | Expected. The split *logic* is proven by unit tests; balance needs real CWRU recordings. |
| `spectral` feature group absent | Needs waveforms from the edge | Deferred by design. |
| `gold.cloud_egress` percentages look extreme | `stats_total` is synthetic | Meaningful only with real orchestrator data. |
| Two test modules skipped on Python 3.10 | `datetime.UTC` needs 3.11 | CI runs 3.11. |

---

## 10. Troubleshooting

**No rows in Bronze after sending.** Almost always the flush. Check the consumer's last log line — if it shows `Buffered 27/50`, those events never flushed. Re-run with Ctrl+C, or lower `RAW_BATCH_SIZE`.

**Consumer received nothing.** It starts at `@latest`; events sent before it was listening are gone. Start the consumer first, wait for `Waiting for events...`, then send.

**`Table … is already managed by pipeline …`.** An orphaned pipeline owns the table. Delete the old pipeline in the Databricks UI. Streaming tables cannot be renamed as a workaround.

**`FIELD_NOT_FOUND` for a configured field.** Auto Loader infers `payload` from observed JSON only. The schema-aware fallback in `flatten_payloads.py` should emit a typed NULL instead — if it raises, that fallback has regressed.

**`databricks bundle validate` complains about paths.** The bundle root is the repository root. Do not move `databricks.yml`.

**More than 4 DLQ files.** Something valid is being rejected. Inspect the DLQ JSON — each records `raw_body` and `error_reason`.

**Scenario F numbers are off.** Do not adjust the expected values. Check first for a duplicate send (the same run executed twice) — deterministic IDs mean Silver should dedup it, so wrong counts here suggest the dedup window or the confusion-matrix logic itself is at fault.

---

## 11. Definition of done

- [ ] 91 unit tests pass locally
- [ ] `bundle validate` and `deploy` succeed
- [ ] Exactly 4 DLQ files, matching DQ3–DQ6
- [ ] Bronze 8 → Silver 6 for `bearing.DQ`
- [ ] DQ8 present in generic Silver, pipeline did not fail
- [ ] **Scenario F: tp/fp/fn/tn = 80/5/10/5, F1 = 0.914286**
- [ ] **Scenario B: agreement 0.5, edge 0.5, cloud 1.0**
- [ ] 4 mode transitions with correct triggers
- [ ] Features 24 / quarantined 2, naming `rms` and `kurtosis`
- [ ] No recording spans two splits
- [ ] No NULL feature column

All ticked ⇒ the cloud platform is a verified measurement instrument, and §7.2 of the thesis (System Validation) can be written from this run.
