# Databricks notebook source
# mlflow_artifact_backup.py — Daily MLflow model artifact backup
#
# P1-15: Copies Production and Staging registered model artifacts to a
# versioned ADLS path that is independent of the Databricks MLflow store.
# This protects against:
#   - Accidental model deletion via the UI or API
#   - Workspace corruption / data loss events
#   - Subscription migration (backup survives even if workspace is recreated)
#
# Backup path structure:
#   abfss://<container>@<account>.dfs.core.windows.net/<prefix>/<date>/<model>/<version>/

import shutil
import os
from datetime import datetime, timezone
from pathlib import Path

import mlflow
from mlflow.tracking import MlflowClient

# ── Parameters ───────────────────────────────────────────────────────────────
backup_container = dbutils.widgets.get("backup_container") if "backup_container" in [w.name for w in dbutils.widgets.getAll()] else "datalake"
backup_prefix    = dbutils.widgets.get("backup_prefix")    if "backup_prefix"    in [w.name for w in dbutils.widgets.getAll()] else "mlflow-backup"

STAGES_TO_BACKUP = {"Production", "Staging"}
TODAY = datetime.now(timezone.utc).strftime("%Y-%m-%d")

# Resolve storage account name from Spark config (set in bundle deployment)
storage_account = spark.conf.get("spark.databricks.clusterUsageTags.clusterOwnerOrgId", "")
# Fall back to reading from environment / cluster config
storage_account = spark.conf.get("fs.azure.account.name", storage_account)

client = MlflowClient()
models = client.search_registered_models()

backed_up = []
errors = []

for model in models:
    for mv in client.get_latest_versions(model.name, stages=list(STAGES_TO_BACKUP)):
        src_uri = mv.source  # e.g. dbfs:/databricks/mlflow-tracking/.../artifacts/model
        backup_path = (
            f"abfss://{backup_container}@{storage_account}.dfs.core.windows.net"
            f"/{backup_prefix}/{TODAY}/{model.name}/v{mv.version}"
        )
        try:
            print(f"Copying {model.name} v{mv.version} ({mv.current_stage}) → {backup_path}")
            dbutils.fs.cp(src_uri, backup_path, recurse=True)
            backed_up.append(f"{model.name} v{mv.version} ({mv.current_stage})")
            print(f"  ✓ done")
        except Exception as e:
            msg = f"FAILED {model.name} v{mv.version}: {e}"
            print(msg)
            errors.append(msg)

print(f"\nBacked up {len(backed_up)} model version(s):")
for item in backed_up:
    print(f"  • {item}")

if errors:
    raise RuntimeError(
        f"MLflow backup failed for {len(errors)} model version(s):\n" + "\n".join(errors)
    )

print("MLflow artifact backup complete.")
