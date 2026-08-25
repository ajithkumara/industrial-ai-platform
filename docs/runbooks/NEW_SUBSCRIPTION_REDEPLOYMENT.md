# New Subscription Redeployment Runbook

Written 2026-08-25. Use when moving from the expiring subscription to a new Azure subscription.  
Everything in this repo is IaC — a full environment rebuild is ~4 commands + secrets.

---

## Prerequisites

On the new subscription, before running anything:

- [ ] Azure subscription ID noted
- [ ] `az login` authenticated to new subscription: `az account set --subscription <new-id>`
- [ ] Databricks CLI installed: `pip install databricks-cli` or download from releases
- [ ] `azcopy` installed (for data restore)
- [ ] Backup folder from `scripts/backup_before_subscription_expiry.ps1` available

---

## Step 1 — Terraform Bootstrap (one-time, creates state storage)

```powershell
cd terraform\bootstrap
terraform init
terraform apply -var="location=canadacentral"
```

This creates:
- Resource group `rg-terraform`
- Storage account `stterraformstate2026aj` (or pick a new name — update `backend.tf` in each environment)
- Container `terraformstate`

**If restoring old state into new storage** (to avoid re-creating resources from scratch):
```powershell
az storage blob upload `
  --account-name <new-storage-account> `
  --container-name terraformstate `
  --name dev.terraform.tfstate `
  --file "$env:USERPROFILE\Desktop\industrial-ai-backup-*\terraform-state\remote_dev.terraform.tfstate"
```

---

## Step 2 — Provision All Azure Resources

```powershell
cd terraform\environments\dev
terraform init         # picks up the new backend
terraform apply
```

This provisions (all defined in `terraform/modules/`):
- Resource group
- ADLS Gen2 storage account + containers (bronze, silver, gold, raw, checkpoints)
- Event Hub namespace + hub + consumer group
- Azure Databricks workspace
- Access Connector + RBAC (Storage Blob Data Contributor on ADLS)
- Unity Catalog (catalog `industrial_ai`, schemas bronze/silver/gold/ml)
- External location + storage credential for Databricks → ADLS access
- Monitoring (Log Analytics, Application Insights)

After `apply`, Terraform outputs the new resource names. **Update `.env`** with new values:
```
EVENTHUB_CONNECTION_STRING=<new>
EVENTHUB_NAME=<same or new>
STORAGE_ACCOUNT_NAME=<new>
STORAGE_CONNECTION_STRING=<new>
...
```

---

## Step 3 — Unity Catalog ML Schema

Terraform creates bronze/silver/gold. The `ml` schema is also in Terraform now (`schema.tf`),  
but run this as a safety net before deploying jobs:

```sql
-- In Databricks SQL editor
CREATE SCHEMA IF NOT EXISTS industrial_ai.ml
  COMMENT 'Registered ML models (Isolation Forest baselines, CloudForest, etc.)';
```

---

## Step 4 — Databricks Bundle Deploy

Update `databricks.yml` with the new workspace host:
```yaml
workspace:
  host: https://<new-adb-workspace>.azuredatabricks.net
```

Then authenticate and deploy:
```powershell
databricks auth login --host https://<new-workspace>.azuredatabricks.net
git add -A && git commit -m "Update workspace host for new subscription"
databricks bundle deploy -t dev
```

This uploads and registers:
- DLT pipeline (`industrial_ai_dlt_pipeline`)
- Bearing Isolation Forest train + evaluate jobs
- CloudForest train + evaluate jobs

---

## Step 5 — Restore ADLS Data (optional)

The CWRU dataset is public and can be re-ingested by re-running the producer.  
If you want to restore the exported Delta tables instead:

```powershell
# Get new storage account SAS or use azcopy login
azcopy sync `
  "$env:USERPROFILE\Desktop\industrial-ai-backup-*\adls\bronze" `
  "https://<new-storage>.dfs.core.windows.net/bronze" `
  --recursive

azcopy sync `
  "$env:USERPROFILE\Desktop\industrial-ai-backup-*\adls\gold" `
  "https://<new-storage>.dfs.core.windows.net/gold" `
  --recursive
```

Alternatively, re-ingest from scratch (cleaner):
```powershell
# Update .env, then:
python scripts/send_cwru_to_eventhub.py   # or whatever the producer script is
# Then trigger DLT pipeline run
databricks pipelines start --pipeline-id <new-pipeline-id>
```

---

## Step 6 — Restore MLflow Model (optional)

If you need the exact trained model from the old run (not just re-training):

```powershell
# Register the saved model into the new UC registry
mlflow.register_model(
    f"file:///{backup_path}/mlflow-artifacts/{run_id}/edge_bearing_isolation_forest_model",
    "industrial_ai.ml.edge_bearing_isolation_forest"
)
```

Or just re-train on the new workspace — the CWRU results will be deterministic  
(same data + `random_seed=42` + same hyperparameters):

```powershell
databricks bundle run bearing_isolation_forest_train -t dev
```

---

## Step 7 — Databricks Secrets

Re-create secret scopes and insert the values from `.env`:

```powershell
databricks secrets create-scope --scope industrial-ai
databricks secrets put --scope industrial-ai --key eventhub-connection-string
# paste value from .env when prompted
databricks secrets put --scope industrial-ai --key storage-connection-string
# ... repeat for each secret the DLT pipeline notebooks reference
```

Check which keys the notebooks use:
```powershell
grep -r "dbutils.secrets.get" dlt/ ml/
```

---

## What Terraform Does NOT Manage (manual steps)

| Item | Action |
|------|--------|
| Databricks PAT / OAuth tokens | Re-authenticate: `databricks auth login` |
| `.env` file | Update from Terraform outputs after `apply` |
| MLflow experiment names | Auto-created on first run |
| DLT pipeline `dataset_run_id` | Set in bundle YAML — no change needed |
| CloudForest model weights | Re-train or restore from backup |

---

## Estimated Rebuild Time

| Step | Time |
|------|------|
| Bootstrap + terraform apply | ~15 min |
| Bundle deploy | ~3 min |
| CWRU re-ingest + DLT pipeline | ~10 min |
| IF model re-train | ~3 min |
| Total | **~35 min** |
