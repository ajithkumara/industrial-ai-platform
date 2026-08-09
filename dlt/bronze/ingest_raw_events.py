# Databricks notebook source
import dlt
from pyspark.sql.functions import *

# BUGFIX: previously hardcoded the ADLS source path here, ignoring the
# `bronze_path` value already defined in the pipeline's `configuration:`
# block (databricks/resources/pipelines/dlt.yml). That meant the dev
# storage account/path was baked into the notebook itself, so the same
# code could not be pointed at a different environment (test/prod)
# without editing Python. Now reads the path from pipeline configuration,
# matching how bronze_path is already declared for this pipeline.
bronze_path = spark.conf.get("bronze_path")

@dlt.table(
    name="telemetry_bronze",
    comment="Raw telemetry ingested from ADLS Gen2 using Auto Loader"
)
def telemetry_bronze():
    return (
        spark.readStream
        .format("cloudFiles")
        .option("cloudFiles.format", "json")
        .option("cloudFiles.inferColumnTypes", "true")
        .load(bronze_path)
    )
