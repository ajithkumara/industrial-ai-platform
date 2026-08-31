# Infrastructure Overview

Canonical Infrastructure-as-Code layout and the resource inventory. See
[deployment.md](deployment.md) for the deploy procedure and
[disaster-recovery.md](disaster-recovery.md) for recovery.

## Canonical Terraform architecture

```
terraform/
  bootstrap/                 # one-time: remote state storage (rg-terraform)
  modules/
    resource_group/
    storage/                 # ADLS Gen2 + datalake container
    eventhub/                # namespace + hub + consumer group
    access_connector/        # Databricks Access Connector (managed identity)
    rbac/                    # Storage Blob Data role assignment
    databricks/              # workspace + INLINE Unity Catalog
      unity_catalog.tf       #   storage credential, external location,
                             #   catalog "industrial_ai",
                             #   schemas: bronze/silver/gold/serving/ml
    monitoring/              # Log Analytics + App Insights
  environments/
    dev/  test/  prod/       # one root config per environment
  unity_catalog/             # LEGACY / REFERENCE ONLY (see its README)
```

## Active resource inventory

| Resource | Module | Terraform-managed |
|----------|--------|-------------------|
| Resource Group | resource_group | ✅ |
| ADLS Gen2 storage + `datalake` container | storage | ✅ |
| Event Hub namespace + hub + consumer group | eventhub | ✅ |
| Databricks Access Connector (MI) | access_connector | ✅ |
| Storage Blob Data RBAC assignment | rbac | ✅ |
| Databricks workspace | databricks | ✅ |
| UC storage credential + external location | databricks/unity_catalog.tf | ✅ |
| UC catalog `industrial_ai` | databricks/unity_catalog.tf | ✅ |
| UC schemas bronze/silver/gold/serving/**ml** | databricks/unity_catalog.tf | ✅ |
| Log Analytics + App Insights | monitoring | ✅ |
| Databricks-managed RG (VNet, NAT, MI, dbstorage) | (auto, by workspace) | ⚙️ implicit |
| DLT pipeline, CloudForest + Isolation Forest jobs | **DAB**, not Terraform | ✅ (workload) |

## Infrastructure vs runtime boundary

Terraform creates **infrastructure only**. It does **not** manage: telemetry
records, CWRU runtime data, model predictions, streaming output, or
runtime-generated parquet. Those are runtime concerns (DLT/Jobs/consumer).

## Known follow-ups (not yet actioned)

- **`cloud_forest.yml` compute**: uses a `Standard_DS3_v2` job cluster, which
  hit `CLOUD_PROVIDER_RESOURCE_STOCKOUT` in CanadaCentral (2026-08). The DLT
  pipeline and Isolation Forest jobs already run serverless. Consider moving
  CloudForest to serverless too for portability + cost.
- **Legacy UC path**: `terraform/unity_catalog/` + `modules/unity_catalog/` are
  marked REFERENCE ONLY (dead backend, superseded). Safe to delete once
  confirmed unused; retained for now.
- **Stray state file**: `terraform/terraform.tfstate` at the repo root is a
  leftover local-backend file (gitignored, unused) — safe to delete.
- **`config/environments/*.yaml`**: a config-as-code scaffold; `load_config()`
  in `shared/config.py` is not yet wired into runtime code.
