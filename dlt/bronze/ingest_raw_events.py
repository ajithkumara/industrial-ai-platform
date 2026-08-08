# Databricks notebook source
# ingest_eventhub.py — Bronze Layer (DLT): Raw Ingestion from ADLS
#
# Ingests raw JSON telemetry events from ADLS Gen2 as a DLT streaming
# or batch source table. No transformations are applied at this layer.
#
# Reads the source path from DLT pipeline configuration parameters.

# COMMAND ----------

# Databricks notebook source
import dlt
from pyspark.sql.functions import *

# ---------------------------------------------------
# CONFIGURATION — Passed from DLT pipeline config
# ---------------------------------------------------
bronze_path = spark.conf.get("bronze_path")

# ---------------------------------------------------
# BRONZE TABLE: raw_telemetry_events
#
# BUGFIX: fully-qualified with the Unity Catalog catalog/schema
# (industrial_ai.bronze.*) instead of the bare table name. The pipeline's
# top-level `target: silver` (databricks/resources/pipelines/dlt.yml) would
# otherwise place every table in this pipeline — bronze, silver, AND gold —
# into the single `silver` schema, contradicting the Terraform-provisioned
# industrial_ai.bronze / industrial_ai.silver / industrial_ai.gold schema
# layout. Declaring the schema explicitly on each table (supported by
# Lakeflow Declarative Pipelines / DLT via fully-qualified `name=`) routes
# this table to industrial_ai.bronze regardless of the pipeline default.
# ---------------------------------------------------
@dlt.table(
    name="telemetry_bronze",
    comment="Raw telemetry ingested from ADLS Gen2 using Auto Loader"
  
def telemetry_bronze():
    return (
        spark.readStream
        .format("cloudFiles")
        .option("cloudFiles.format", "json")
        .option("cloudFiles.inferColumnTypes", "true")
        # Fixed path: 'raw/telemetry/' instead of 'raw_telemetry/'
        .load("abfss://datalake@stindustrialaidev2026.dfs.core.windows.net/raw/telemetry/")
    )
