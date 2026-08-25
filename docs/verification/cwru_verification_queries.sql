-- =============================================================================
-- CWRU Real-Data Verification Queries
-- Scope: dataset_run_id = 'cwru_exp_001' (real CWRU bearing data, NOT the
-- synthetic acceptance-test scenarios). Run these after the DLT pipeline
-- has processed the 2,245 sent events, in order, top to bottom.
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 0. SANITY: did anything with this dataset_run_id land at all?
-- -----------------------------------------------------------------------------
SELECT COUNT(*) AS bronze_row_count
FROM industrial_ai.bronze.telemetry_raw
WHERE payload:dataset_run_id = 'cwru_exp_001';
-- Expect: 2245 (adjust path syntax if payload is already a struct, not JSON)

SELECT COUNT(*) AS silver_row_count
FROM industrial_ai.silver.telemetry_events   -- adjust table name if different
WHERE dataset_run_id = 'cwru_exp_001';
-- Expect: 2245

SELECT COUNT(*) AS gold_feature_row_count
FROM industrial_ai.gold.bearing_ml_features
WHERE dataset_run_id = 'cwru_exp_001';
-- Expect: 2245 minus any quarantined rows (should be 0 quarantined for real data
-- since cwru_loader.py's _compute_features already guards zero-rms/degenerate cases)

-- -----------------------------------------------------------------------------
-- 1. RECORDING / WINDOW COUNTS
-- -----------------------------------------------------------------------------
SELECT COUNT(DISTINCT source_file) AS distinct_recordings,
       COUNT(*)                   AS total_windows
FROM industrial_ai.gold.bearing_ml_features
WHERE dataset_run_id = 'cwru_exp_001';
-- Expect: 28 recordings, 2245 windows

-- -----------------------------------------------------------------------------
-- 2. SPLIT INTEGRITY: no source_file appears in more than one split
-- -----------------------------------------------------------------------------
SELECT source_file, COUNT(DISTINCT dataset_split) AS split_count
FROM industrial_ai.gold.bearing_ml_features
WHERE dataset_run_id = 'cwru_exp_001'
GROUP BY source_file
HAVING COUNT(DISTINCT dataset_split) > 1;
-- Expect: 0 rows returned

-- -----------------------------------------------------------------------------
-- 3. TRAIN split is normal-only
-- -----------------------------------------------------------------------------
SELECT DISTINCT label
FROM industrial_ai.gold.bearing_ml_features
WHERE dataset_run_id = 'cwru_exp_001'
  AND dataset_split = 'TRAIN';
-- Expect: single row, 'normal' (or whatever your normal-label string is)

-- -----------------------------------------------------------------------------
-- 4. VALIDATION and TEST both contain normal + fault classes
-- -----------------------------------------------------------------------------
SELECT dataset_split, label, COUNT(*) AS n
FROM industrial_ai.gold.bearing_ml_features
WHERE dataset_run_id = 'cwru_exp_001'
  AND dataset_split IN ('VALIDATION', 'TEST')
GROUP BY dataset_split, label
ORDER BY dataset_split, label;
-- Expect: both VALIDATION and TEST show 'normal' AND at least one fault class

-- -----------------------------------------------------------------------------
-- 5. Per-split, per-class recording counts (sanity check against the
--    2 TRAIN / 1 VALIDATION / 1 TEST manual override for Normal Baseline)
-- -----------------------------------------------------------------------------
SELECT dataset_split, label, COUNT(DISTINCT source_file) AS recordings, COUNT(*) AS windows
FROM industrial_ai.gold.bearing_ml_features
WHERE dataset_run_id = 'cwru_exp_001'
GROUP BY dataset_split, label
ORDER BY dataset_split, label;

-- -----------------------------------------------------------------------------
-- 6. No NULL / non-finite features
-- -----------------------------------------------------------------------------
SELECT COUNT(*) AS null_or_bad_feature_rows
FROM industrial_ai.gold.bearing_ml_features
WHERE dataset_run_id = 'cwru_exp_001'
  AND (
        rms IS NULL OR peak IS NULL OR crest IS NULL OR kurtosis IS NULL
     OR skew IS NULL OR variance IS NULL OR mean_abs IS NULL
     OR isnan(rms) OR isnan(peak) OR isnan(crest) OR isnan(kurtosis)
     OR isnan(skew) OR isnan(variance) OR isnan(mean_abs)
  );
-- Expect: 0

-- -----------------------------------------------------------------------------
-- 7. Quarantine table: should be empty for this dataset_run_id
-- -----------------------------------------------------------------------------
SELECT *
FROM industrial_ai.gold.bearing_ml_features_quarantine   -- adjust name if different
WHERE dataset_run_id = 'cwru_exp_001';
-- Expect: 0 rows

-- -----------------------------------------------------------------------------
-- 8. window_idx uniqueness within source_file
-- -----------------------------------------------------------------------------
SELECT source_file, window_idx, COUNT(*) AS dup_count
FROM industrial_ai.gold.bearing_ml_features
WHERE dataset_run_id = 'cwru_exp_001'
GROUP BY source_file, window_idx
HAVING COUNT(*) > 1;
-- Expect: 0 rows

-- -----------------------------------------------------------------------------
-- 9. Confirm this run is isolated from the synthetic baseline
--    (no crossover / no synthetic device_ids carrying this dataset_run_id)
-- -----------------------------------------------------------------------------
SELECT DISTINCT device_id
FROM industrial_ai.gold.bearing_ml_features
WHERE dataset_run_id = 'cwru_exp_001';
-- Expect: single value, 'bearing.CWRU'

SELECT COUNT(*)
FROM industrial_ai.gold.bearing_ml_features
WHERE dataset_run_id IS NULL OR dataset_run_id != 'cwru_exp_001'
  AND device_id = 'bearing.CWRU';
-- Expect: 0 (no CWRU rows missing/mismatched dataset_run_id)
