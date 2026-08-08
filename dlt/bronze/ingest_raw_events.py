# Databricks notebook source
import dlt
from pyspark.sql.functions import *
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
        # Fixed path: 'raw/telemetry/' instead of 'raw_telemetry/'
        .load("abfss://datalake@stindustrialaidev2026.dfs.core.windows.net/raw/telemetry/")
    )
