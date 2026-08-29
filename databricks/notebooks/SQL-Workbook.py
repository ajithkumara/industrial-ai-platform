# Databricks notebook source
# MAGIC %sql
# MAGIC CREATE SCHEMA IF NOT EXISTS industrial_ai.ml
# MAGIC COMMENT 'Registered ML models (Isolation Forest baselines, CloudForest, etc.)';

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT COUNT(*) AS quarantined_rows
# MAGIC FROM industrial_ai.gold.bearing_ml_features_quarantine
# MAGIC WHERE dataset_run_id = 'cwru_exp_001';

# COMMAND ----------

# MAGIC %sql
# MAGIC -- No NULL/non-finite features, and quarantine is empty
# MAGIC SELECT COUNT(*) AS bad_feature_rows
# MAGIC FROM industrial_ai.gold.bearing_ml_features
# MAGIC WHERE dataset_run_id = 'cwru_exp_001'
# MAGIC   AND (rms IS NULL OR peak IS NULL OR crest IS NULL OR kurtosis IS NULL
# MAGIC        OR skew IS NULL OR variance IS NULL OR mean_abs IS NULL);
# MAGIC

# COMMAND ----------

# MAGIC %sql
# MAGIC -- VALIDATION and TEST both contain normal + fault classes
# MAGIC SELECT dataset_split, ground_truth_label, COUNT(*) AS n
# MAGIC FROM industrial_ai.gold.bearing_ml_features
# MAGIC WHERE dataset_run_id = 'cwru_exp_001'
# MAGIC   AND dataset_split IN ('VALIDATION', 'TEST')
# MAGIC GROUP BY dataset_split, ground_truth_label
# MAGIC ORDER BY dataset_split, ground_truth_label;

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT DISTINCT ground_truth_label
# MAGIC FROM industrial_ai.gold.bearing_ml_features
# MAGIC WHERE dataset_run_id = 'cwru_exp_001'
# MAGIC   AND dataset_split = 'TRAIN';
# MAGIC -- expect exactly one row: 'normal'

# COMMAND ----------

# MAGIC %sql
# MAGIC -- Split integrity: no source_file in more than one split
# MAGIC SELECT source_file, COUNT(DISTINCT dataset_split) AS split_count
# MAGIC FROM industrial_ai.gold.bearing_ml_features
# MAGIC WHERE dataset_run_id = 'cwru_exp_001'
# MAGIC GROUP BY source_file
# MAGIC HAVING COUNT(DISTINCT dataset_split) > 1;

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT COUNT(DISTINCT source_file) AS distinct_recordings,
# MAGIC        COUNT(*)                   AS total_windows
# MAGIC FROM industrial_ai.gold.bearing_ml_features
# MAGIC WHERE dataset_run_id = 'cwru_exp_001';

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT payload.*
# MAGIC FROM industrial_ai.bronze.telemetry_bronze
# MAGIC WHERE device_id = 'bearing.CWRU'
# MAGIC LIMIT 1;

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT COUNT(*) AS bronze_row_count
# MAGIC FROM industrial_ai.bronze.telemetry_bronze
# MAGIC WHERE payload.dataset_run_id = 'cwru_exp_001';

# COMMAND ----------

# MAGIC %sql
# MAGIC DESCRIBE industrial_ai.bronze.telemetry_bronze;

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT COUNT(*) AS bronze_row_count
# MAGIC FROM industrial_ai.bronze.telemetry_bronze
# MAGIC WHERE payload:dataset_run_id = 'cwru_exp_001';

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT
# MAGIC   (SELECT count(*) FROM industrial_ai.silver.cleaned_telemetry_events
# MAGIC      WHERE asset_type='mystery_sensor') AS in_generic_silver,
# MAGIC   (SELECT count(*) FROM industrial_ai.silver.silver_bearing_sensor_telemetry
# MAGIC      WHERE device_id='bearing.DQ' AND source_file='normal_0hp.mat'
# MAGIC        AND ground_truth_label='normal') AS in_flattened;

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT source_file, count(DISTINCT dataset_split) AS n_splits
# MAGIC FROM industrial_ai.gold.bearing_ml_features
# MAGIC GROUP BY source_file HAVING count(DISTINCT dataset_split) > 1;

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT count(*) AS must_be_zero
# MAGIC FROM industrial_ai.gold.bearing_ml_features
# MAGIC WHERE rms IS NULL OR peak IS NULL OR crest IS NULL OR kurtosis IS NULL
# MAGIC    OR skew IS NULL OR variance IS NULL OR mean_abs IS NULL;

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT event_id, quarantine_missing_columns, quarantine_reason
# MAGIC FROM industrial_ai.gold.bearing_ml_features_quarantine;

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT source_file, device_id, ground_truth_label, dataset_split, count(*)
# MAGIC FROM industrial_ai.gold.bearing_ml_features
# MAGIC GROUP BY 1,2,3,4
# MAGIC ORDER BY 1,2;

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT
# MAGIC   (SELECT count(*) FROM industrial_ai.gold.bearing_ml_features) AS features,
# MAGIC   (SELECT count(*) FROM industrial_ai.gold.bearing_ml_features_quarantine) AS quarantined;

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT n_events_during_outage, n_anomalies_during_outage,
# MAGIC        largest_inter_event_gap_s, outage_duration_s
# MAGIC FROM industrial_ai.gold.edge_autonomy
# MAGIC WHERE device_id = 'edge-node-01'
# MAGIC ORDER BY window_started_at DESC LIMIT 1;

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT DISTINCT device_id FROM industrial_ai.gold.edge_autonomy;

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT window_id, window_started_at, window_ended_at,
# MAGIC        n_events_during_outage, n_anomalies_during_outage,
# MAGIC        largest_inter_event_gap_s, outage_duration_s
# MAGIC FROM industrial_ai.gold.edge_autonomy
# MAGIC WHERE device_id = 'bearing.DE'
# MAGIC ORDER BY window_started_at;

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT device_id, cloud_reachable, count(*)
# MAGIC FROM industrial_ai.silver.silver_context_snapshot
# MAGIC WHERE device_id = 'edge-node-01'
# MAGIC GROUP BY 1, 2;

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT DISTINCT device_id FROM industrial_ai.silver.silver_context_snapshot
# MAGIC WHERE device_id LIKE '%edge-node%';

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT DISTINCT device_id FROM industrial_ai.gold.edge_autonomy;

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT
# MAGIC   (SELECT count(*) FROM industrial_ai.gold.bearing_ml_features) AS features,
# MAGIC   (SELECT count(*) FROM industrial_ai.gold.bearing_ml_features_quarantine) AS quarantined;

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT n_events_during_outage, n_anomalies_during_outage,
# MAGIC        largest_inter_event_gap_s, outage_duration_s
# MAGIC FROM industrial_ai.gold.edge_autonomy
# MAGIC WHERE device_id = 'bearing.DE'
# MAGIC ORDER BY window_started_at DESC LIMIT 1;

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT from_mode, to_mode, trigger, mode_switch_latency_s
# MAGIC FROM industrial_ai.gold.mode_history
# MAGIC WHERE device_id = 'edge-node-01'
# MAGIC ORDER BY transition_at;

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT n_escalations, agreement_rate, edge_accuracy,
# MAGIC        cloud_accuracy, cloud_accuracy_improvement
# MAGIC FROM industrial_ai.gold.escalation_efficacy
# MAGIC WHERE mode = 'HYBRID' AND edge_confidence_bucket = 'low';

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT tp, fp, fn, tn, precision, recall, f1
# MAGIC FROM industrial_ai.gold.detection_performance
# MAGIC WHERE mode = 'CLOUD_OPTIMISED' AND model_version = 'edge-v1.0-synthetic';

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT count(*) AS silver_rows
# MAGIC FROM industrial_ai.silver.cleaned_telemetry_events
# MAGIC WHERE device_id = 'bearing.DQ';

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT count(*) AS bronze_rows
# MAGIC FROM industrial_ai.bronze.telemetry_bronze
# MAGIC WHERE device_id = 'bearing.DQ';

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT
# MAGIC     asset_type,
# MAGIC     COUNT(*) AS silver_rows,
# MAGIC     COUNT(DISTINCT event_id) AS silver_distinct_events
# MAGIC FROM (
# MAGIC     SELECT event_id, asset_type
# MAGIC     FROM industrial_ai.silver.silver_bearing_sensor_telemetry
# MAGIC
# MAGIC     UNION ALL
# MAGIC
# MAGIC     SELECT event_id, asset_type
# MAGIC     FROM industrial_ai.silver.silver_bearing_inference_results
# MAGIC )
# MAGIC GROUP BY asset_type;

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT
# MAGIC     asset_type,
# MAGIC     COUNT(*) AS rows,
# MAGIC     COUNT(DISTINCT event_id) AS distinct_events
# MAGIC FROM industrial_ai.bronze.telemetry_bronze
# MAGIC WHERE asset_type IN ('bearing_sensor', 'bearing_inference')
# MAGIC GROUP BY asset_type;

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT * FROM industrial_ai.silver.silver_bearing_inference_results ORDER BY timestamp DESC;

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT * FROM industrial_ai.silver.silver_bearing_sensor_telemetry ORDER BY timestamp DESC;
# MAGIC

# COMMAND ----------

# MAGIC %sql
# MAGIC -- Should show 8 DISTINCT event_ids here, not 16 -- this is the real test
# MAGIC SELECT event_id, device_id, asset_type, timestamp, priority
# MAGIC FROM industrial_ai.silver.cleaned_telemetry_events
# MAGIC WHERE asset_type IN ('bearing_sensor', 'bearing_inference')
# MAGIC ORDER BY timestamp DESC;

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT event_id, device_id, asset_type, timestamp, priority
# MAGIC FROM industrial_ai.bronze.telemetry_bronze
# MAGIC WHERE asset_type IN ('bearing_sensor', 'bearing_inference')
# MAGIC ORDER BY timestamp DESC;

# COMMAND ----------

# MAGIC %sql
# MAGIC -- Bronze: raw envelope, both asset types mixed in with everything else
# MAGIC SELECT event_id, device_id, asset_type, timestamp, priority, payload
# MAGIC FROM industrial_ai.bronze.telemetry_bronze
# MAGIC WHERE asset_type IN ('bearing_sensor', 'bearing_inference')
# MAGIC ORDER BY timestamp DESC;

# COMMAND ----------

# MAGIC %sql
# MAGIC -- Bronze: raw envelope, both asset types mixed in with everything else
# MAGIC SELECT event_id, device_id, asset_type, timestamp, priority, payload
# MAGIC FROM industrial_ai.bronze.telemetry_bronze
# MAGIC WHERE asset_type IN ('bearing_sensor', 'bearing_inference')
# MAGIC ORDER BY timestamp DESC;
# MAGIC
# MAGIC -- Silver: envelope-validated/deduplicated, still asset-agnostic
# MAGIC SELECT event_id, device_id, asset_type, timestamp, priority
# MAGIC FROM industrial_ai.silver.cleaned_telemetry_events
# MAGIC WHERE asset_type IN ('bearing_sensor', 'bearing_inference')
# MAGIC ORDER BY timestamp DESC;
# MAGIC
# MAGIC -- Silver: config-driven flattened output, one table per asset type
# MAGIC SELECT * FROM industrial_ai.silver.silver_bearing_sensor_telemetry ORDER BY timestamp DESC;
# MAGIC SELECT * FROM industrial_ai.silver.silver_bearing_inference_results ORDER BY timestamp DESC;

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT * FROM industrial_ai.gold.asset_health_summary;

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT * FROM industrial_ai.silver.silver_vehicle_telemetry LIMIT 10;

# COMMAND ----------

df = spark.read.json(
    "abfss://datalake@stindustrialaidev2026.dfs.core.windows.net/bronze/"
)

display(df)

# COMMAND ----------

display(dbutils.fs.ls(
    "abfss://datalake@stindustrialaidev2026.dfs.core.windows.net/raw/telemetry/"
))

# COMMAND ----------

display(dbutils.fs.ls(
    "abfss://datalake@stindustrialaidev2026.dfs.core.windows.net/"
))

# COMMAND ----------

# MAGIC %sql
# MAGIC SHOW CATALOGS;

# COMMAND ----------

# MAGIC %sql
# MAGIC SHOW EXTERNAL LOCATIONS;

# COMMAND ----------

# MAGIC %sql
# MAGIC SHOW STORAGE CREDENTIALS;

# COMMAND ----------

# MAGIC %sql
# MAGIC SHOW EXTERNAL LOCATIONS;

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT current_metastore();

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT current_schema();

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT current_catalog();

# COMMAND ----------

# MAGIC %sql
# MAGIC DESCRIBE EXTERNAL LOCATION industrial_ai_lake;

# COMMAND ----------

# MAGIC %sql
# MAGIC CREATE STORAGE CREDENTIAL adls_credential
# MAGIC WITH AZURE MANAGED IDENTITY;

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT current_catalog();

# COMMAND ----------

spark.version