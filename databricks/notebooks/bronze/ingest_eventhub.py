# Databricks notebook source
# ingest_eventhub.py — Bronze Layer (DLT): Raw Ingestion from ADLS
#
# Ingests raw JSON telemetry events from ADLS Gen2 as a DLT streaming
# or batch source table. No transformations are applied at this layer.
#
# Reads the source path from DLT pipeline configuration parameters.

# COMMAND ----------

import dlt
from pyspark.sql.functions import col, input_file_name, current_timestamp

# ---------------------------------------------------
# CONFIGURATION — Passed from DLT pipeline config
# ---------------------------------------------------
bronze_path = spark.conf.get("bronze_path")

# ---------------------------------------------------
# BRONZE TABLE: raw_telemetry_events
# ---------------------------------------------------
@dlt.table(
    name="raw_telemetry_events",
    comment="Raw JSON telemetry events ingested from ADLS Gen2 bronze zone.",
    table_properties={"quality": "bronze"},
)
def raw_telemetry_events():
    # Append wildcard to pick up all partitioned subdirectories (year=/month=/day=/)
    return (
        spark.read
        .option("multiLine", False)
        .option("recursiveFileLookup", "true")
        .json(bronze_path)
        .withColumn("_source_file", input_file_name())
        .withColumn("_ingested_at", current_timestamp())
    )
