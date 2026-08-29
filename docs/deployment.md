# Deployment Guide

How the Industrial AI Platform is deployed to Azure, and the exact procedure to
rebuild it from Git in a **fresh subscription**.

## Deployment model

Two layers, clean boundary:

```
                Git (source of truth)
                       │
        ┌──────────────┴───────────────┐
        │                              │
        ▼                              ▼
   TERRAFORM                    DATABRICKS ASSET BUNDLE (DAB)
 (Infrastructure as Code)        (Workload as Code)
        │                              │
        ▼                              ▼
 Azure foundation:              Databricks workloads:
  RG, ADLS, Event Hubs,          DLT/Lakeflow pipeline,
  identity, RBAC,                Jobs (CloudForest,
  Databricks workspace,          Isolation Forest),
  Unity Catalog                  notebooks, params
        │                              ▲
        └────────  outputs  ───────────┘
        (workspace URL, storage account name feed DAB variables)
```

- **Terraform owns infrastructure.** It never manages runtime data (telemetry,
  models, predictions).
- **DAB owns workloads.** It never creates cloud infrastructure.
- The **Terraform output contract** connects them: DAB variables
  (`databricks_host`, `storage_account_name`) are sourced from Terraform
  outputs, so nothing is copy-pasted by hand.

## Terraform output contract

`terraform/environments/<env>` exposes (see `outputs.tf`):

| Output | Feeds |
|--------|-------|
| `databricks_workspace_url` | DAB `databricks_host` variable |
| `storage_account_name` | DAB `storage_account_name` variable |
| `unity_catalog_name` | reference (`industrial_ai`) |
| `eventhub_namespace_name`, `eventhub_name` | producer/consumer `.env` |
| `eventhub_producer_connection_string` (sensitive) | producer `.env` |
| `eventhub_consumer_connection_string` (sensitive) | consumer `.env` |
| `resource_group_name`, `log_analytics_workspace_id`, … | ops/reference |

## Authentication (local vs CI)

Never commit personal profiles or tokens.

- **Local dev:** `az login` for Terraform; `databricks auth login --host <url>`
  for the bundle. `databricks.yml` carries **no** profile — the CLI resolves
  auth from the environment.
- **CI (GitHub Actions):** an Azure service principal (`ARM_CLIENT_ID`,
  `ARM_CLIENT_SECRET`, `ARM_TENANT_ID`, `ARM_SUBSCRIPTION_ID` as repo secrets)
  for Terraform; a Databricks OAuth service principal (`DATABRICKS_HOST`,
  `DATABRICKS_CLIENT_ID`, `DATABRICKS_CLIENT_SECRET`) for the bundle.

---

## Fresh-Environment Rebuild Procedure

Rebuild the entire platform from Git in a new Azure subscription. Commands are
PowerShell; adjust paths for bash.

### 0. Prerequisites (MANUAL)
- Azure CLI, Terraform ≥ 1.5, Databricks CLI ≥ 0.220, Python 3.11.
- An Azure subscription where you are **Owner**.
- `az login` and `az account set --subscription <NEW_SUB_ID>`.

### 1. Bootstrap remote Terraform state (once per subscription)
```powershell
cd terraform\bootstrap
terraform init
terraform apply    # creates rg-terraform + a state storage account + container
```
Note the storage account name it outputs; put it in each
`terraform/environments/<env>/backend.hcl` (key stays per-env).

> MANUAL PREREQUISITE: storage account names are globally unique. If the
> bootstrap name is taken, choose another and update `backend.hcl`.

### 2. Provision infrastructure
```powershell
cd ..\environments\dev
terraform init -backend-config=backend.hcl
terraform validate
terraform plan  -var-file=terraform.tfvars   # review
terraform apply -var-file=terraform.tfvars
```
This creates the RG, ADLS Gen2, Event Hubs, identity + RBAC, the Databricks
workspace, and Unity Catalog (catalog `industrial_ai`; schemas
`bronze/silver/gold/serving/ml`).

### 3. Capture outputs
```powershell
terraform output                                   # human review
$DBX = terraform output -raw databricks_workspace_url
$SA  = terraform output -raw storage_account_name
```

### 4. Configure runtime secrets (MANUAL, never committed)
Populate `.env` at the repo root from the sensitive outputs:
```powershell
terraform output -raw eventhub_producer_connection_string   # -> EVENTHUB_CONNECTION_STRING
terraform output -raw eventhub_consumer_connection_string   # -> EVENTHUB_CONSUMER_CONNECTION_STRING
# STORAGE_ACCOUNT_NAME = $SA, etc. (see .env.example)
```

### 5. Deploy Databricks workloads (DAB)
```powershell
cd ..\..\..                     # repo root (where databricks.yml lives)
databricks auth login --host $DBX
$env:DATABRICKS_BUNDLE_VAR_databricks_host        = $DBX
$env:DATABRICKS_BUNDLE_VAR_storage_account_name   = $SA
databricks bundle validate -t dev
databricks bundle deploy   -t dev
```

### 6. Run the pipeline + jobs
```powershell
databricks bundle run industrial_ai_dlt_pipeline -t dev
# ML (deliberate, on-demand):
databricks bundle run bearing_isolation_forest_train -t dev
```

### 7. Smoke test
Run the cloud smoke checks in `docs/deployment.md` §Smoke test (below) or the
verification SQL in `docs/verification/`.

### 8. Tear down (when done / to save credit)
```powershell
cd terraform\environments\dev ; terraform destroy -var-file=terraform.tfvars
cd ..\..\bootstrap            ; terraform destroy
```

---

## Smoke test (post-deploy verification)

Confirm, without running expensive workloads:

1. **Storage** — `az storage container show -n datalake --account-name $SA` (MI auth).
2. **Event Hubs** — `az eventhubs eventhub show` for the namespace/hub.
3. **Databricks reachable** — `databricks current-user me`.
4. **Unity Catalog** — `databricks schemas list industrial_ai` shows
   `bronze silver gold serving ml`.
5. **ML namespace** — `industrial_ai.ml` exists (step 4).
6. **DLT** — pipeline `industrial_ai_dlt_pipeline` initializes (a validate/dry
   run is enough; a full run needs landed data).
7. **Verification SQL** — `docs/verification/cwru_verification_queries.sql`
   after an ingestion run.

## Cost safety

- DLT and the Isolation Forest jobs run **serverless** (scale-to-zero).
- `cloud_forest.yml` still uses a `Standard_DS3_v2` job cluster — see
  `docs/infrastructure.md` (known follow-up: this SKU hit capacity stockouts
  in CanadaCentral; consider serverless there too).
- Nothing is scheduled to run continuously except CloudForest scoring (every
  15 min) — disable that schedule in `cloud_forest.yml` for a cost-quiet dev
  environment.
- Always `terraform destroy` a throwaway environment when finished.
