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
# BUGFIX: fully-qualified with industrial_ai.silver.* so this table lands
# in the Terraform-provisioned `silver` schema regardless of the pipeline's
# `target: silver` default (see dlt/bronze/ingest_raw_events.py for the
# full explanation). Upstream read updated to the bronze table's own
# fully-qualified name (industrial_ai.bronze.raw_telemetry_events).
# ---------------------------------------------------
@dlt.table(
    name="industrial_ai.silver.cleaned_telemetry_events",
    comment="Cleansed and deduplicated telemetry envelope from the bronze layer.",
    table_properties={"quality": "silver"},
)
@dlt.expect_or_drop("valid_event_id",   "event_id IS NOT NULL")
@dlt.expect_or_drop("valid_device_id", "device_id IS NOT NULL")
@dlt.expect_or_drop("valid_asset_type", "asset_type IS NOT NULL")
@dlt.expect_or_drop("valid_timestamp",  "timestamp IS NOT NULL")
def cleaned_telemetry_events():
    df = (
        dlt.read("industrial_ai.bronze.raw_telemetry_events")
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
