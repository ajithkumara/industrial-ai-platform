# Databricks notebook source
# clean_data.py — Silver Layer (DLT): Cleansing & Transformation
#
# Reads from the Bronze DLT table, applies schema enforcement,
# type casting, and data quality expectations.

# COMMAND ----------

import dlt
from pyspark.sql.functions import col, to_timestamp

# ---------------------------------------------------
# SILVER TABLE: telemetry_events
# ---------------------------------------------------
@dlt.table(
    name="telemetry_events",
    comment="Cleansed and typed telemetry events from the bronze layer.",
    table_properties={"quality": "silver"},
)
@dlt.expect_or_drop("valid_event_id",   "eventId IS NOT NULL")
@dlt.expect_or_drop("valid_vehicle_id", "vehicleId IS NOT NULL")
@dlt.expect_or_drop("valid_timestamp",  "timestamp IS NOT NULL")
def telemetry_events():
    return (
        dlt.read("raw_telemetry_events")
        .select(
            col("eventId"),
            col("vehicleId"),
            col("driverId"),
            col("batteryVoltage").cast("double"),
            col("engineTemperatureC").cast("double"),
            col("fuelLevelPercent").cast("double"),
            col("heading").cast("double"),
            col("ignition").cast("boolean"),
            col("odometerKm").cast("double"),
            col("speedKmh").cast("double"),
            col("location.latitude").alias("latitude"),
            col("location.longitude").alias("longitude"),
            to_timestamp(col("timestamp")).alias("timestamp"),
        )
    )
