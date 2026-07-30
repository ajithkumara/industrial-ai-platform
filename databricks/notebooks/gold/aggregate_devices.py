# Databricks notebook source
# aggregate_devices.py — Gold Layer (DLT): Aggregated KPI Metrics
#
# Reads from the Silver DLT table and produces vehicle-level
# KPI aggregations (avg speed, engine temp, fuel, max odometer).

# COMMAND ----------

import dlt
from pyspark.sql.functions import avg, max, min, count, date_trunc, col

# ---------------------------------------------------
# GOLD TABLE: vehicle_kpis
# ---------------------------------------------------
@dlt.table(
    name="vehicle_kpis",
    comment="Vehicle-level daily KPI aggregations from silver telemetry events.",
    table_properties={"quality": "gold"},
)
def vehicle_kpis():
    return (
        dlt.read("telemetry_events")
        .withColumn("date", date_trunc("day", col("timestamp")))
        .groupBy("vehicleId", "date")
        .agg(
            count("eventId").alias("total_events"),
            avg("speedKmh").alias("avg_speed_kmh"),
            max("speedKmh").alias("max_speed_kmh"),
            min("speedKmh").alias("min_speed_kmh"),
            avg("engineTemperatureC").alias("avg_engine_temp_c"),
            avg("fuelLevelPercent").alias("avg_fuel_level_pct"),
            avg("batteryVoltage").alias("avg_battery_voltage"),
            max("odometerKm").alias("max_odometer_km"),
        )
    )
