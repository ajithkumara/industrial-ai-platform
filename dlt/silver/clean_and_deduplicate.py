# Databricks notebook source
# clean_and_deduplicate.py — Silver Layer (DLT): Cleansing & Transformation
#
# Reads from the Bronze DLT table, applies envelope validation,
# deduplicates by event_id, and normalizes timestamps.
# Domain-agnostic.

import dlt
from pyspark.sql.functions import col, to_timestamp, row_number
from pyspark.sql.window import Window

# ---------------------------------------------------
# SILVER TABLE: cleaned_telemetry_events
#
# Fully-qualified with industrial_ai.silver.* so this table lands in the
# Terraform-provisioned `silver` schema regardless of the pipeline's
# `target: bronze` default. Upstream read uses the bronze table's short
# name ("telemetry_bronze", as registered in
# dlt/bronze/ingest_raw_events.py) — within a single DLT pipeline,
# dlt.read() resolves other tables in that same pipeline by their
# registered name, not by fully-qualified catalog.schema.table.
# ---------------------------------------------------
@dlt.table(
    name="industrial_ai.silver.cleaned_telemetry_events",
    comment="Cleansed and deduplicated telemetry envelope from the bronze layer.",
    table_properties={"quality": "silver"},
)
# TRIM(...) <> '' in addition to IS NOT NULL: an empty (or whitespace-only)
# string satisfies IS NOT NULL, so the previous expectations admitted events
# with event_id="" into Silver. Because every such event shares that key,
# the dedup window below would collapse unrelated events into one row --
# silent data loss. Found by the DQ6 scenario in
# tests/integration/data_quality_scenarios.py. This is the second of two
# defences; the first is min_length=1 on shared/telemetry_event.py, which
# rejects these at the consumer before they ever reach Bronze. Both are kept
# so that anything reaching Bronze by another path (backfill, replay, direct
# write) is still caught here.
@dlt.expect_or_drop("valid_event_id",   "event_id IS NOT NULL AND TRIM(event_id) <> ''")
@dlt.expect_or_drop("valid_device_id",  "device_id IS NOT NULL AND TRIM(device_id) <> ''")
@dlt.expect_or_drop("valid_asset_type", "asset_type IS NOT NULL AND TRIM(asset_type) <> ''")
@dlt.expect_or_drop("valid_timestamp",  "timestamp IS NOT NULL")
def cleaned_telemetry_events():
    df = (
        dlt.read("telemetry_bronze")
        .select(
            col("event_id"),
            col("device_id"),
            col("asset_type"),
            col("schema_version"),
            col("priority"),
            col("payload"),
            to_timestamp(col("timestamp")).alias("timestamp"),
            col("_source_file"),
            col("_ingested_at")
        )
    )

    # Deduplicate by event_id, keeping the most recent _ingested_at
    window_spec = Window.partitionBy("event_id").orderBy(col("_ingested_at").desc())
    deduped_df = df.withColumn("rn", row_number().over(window_spec)).filter(col("rn") == 1).drop("rn")

    return deduped_df
