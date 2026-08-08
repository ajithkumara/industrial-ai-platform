# Azure Industrial AI Platform

A production-style, cloud-native telemetry data platform built on **Azure Databricks**, **Azure Event Hubs**, **ADLS Gen2**, and **Unity Catalog** — using a Medallion Architecture (Bronze → Silver → Gold) for streaming IoT telemetry data.

---

## Architecture Overview

```
IoT Devices / Simulator
        │
        ▼
Azure Event Hubs
        │
        ▼
Databricks Structured Streaming
        │
   ┌────┴────┐
   │  Bronze │  Raw JSON ingestion (Delta)
   └────┬────┘
        │
   ┌────┴────┐
   │  Silver │  Cleansed, typed, deduplicated
   └────┬────┘
        │
   ┌────┴────┐
   │   Gold  │  KPI aggregations, device health
   └─────────┘
        │
   Unity Catalog (dbw_industrial_ai_dev_*)
```

---

## Tech Stack

| Layer            | Technology                           |
|------------------|--------------------------------------|
| Streaming        | Azure Event Hubs                     |
| Processing       | Azure Databricks (Structured Stream) |
| Storage          | ADLS Gen2 (Delta format)             |
| Governance       | Unity Catalog                        |
| Infrastructure   | Terraform                            |
| Deployments      | Databricks Asset Bundles (DAB)       |
| CI/CD            | GitHub Actions                       |
| Language         | Python                               |

---

## Folder Structure

```
industrial-ai-platform/
├── .github/
│   └── workflows/
│       ├── ci-cd.yml
│       └── databricks_deploy.yml
├── config/
│   ├── environments/
│   └── asset_types/
├── shared/
├── edge/
├── consumer/
├── dlt/
│   ├── bronze/
│   ├── silver/
│   ├── gold/
│   └── common/
├── ml/
├── databricks/
├── monitoring/
├── terraform/
├── tests/
├── docs/
├── .env.example
├── .gitignore
├── README.md
└── requirements.txt
```

---

## Setup Instructions

### Prerequisites
- Azure subscription
- Terraform >= 1.5
- Databricks CLI >= 0.200
- Python >= 3.11

### 1. Clone the repository
```bash
git clone https://github.com/your-org/azure-telemetry-platform.git
cd azure-telemetry-platform
```

### 2. Configure environment
```bash
cp config/environments/dev.yaml .env.yaml
# Edit values for your Azure subscription
```
Runtime secrets (Event Hub connection strings, storage account keys, etc.)
used by `consumer/` and `edge/` are read from a separate `.env` file at the
repo root (see `config/settings.py`) — this is not committed to git.

### 3. Deploy infrastructure & Unity Catalog
```bash
cd terraform/environments/dev
terraform init
terraform apply
```
*(Running `terraform apply` fully provisions Azure Infrastructure, Databricks Workspace, Unity Catalog Storage Credentials, External Location, Catalog `industrial_ai`, Schemas `bronze`/`silver`/`gold`/`serving`, and Grants with zero manual configuration required).*

### 4. Deploy Databricks Assets & DLT Pipeline
```bash
cd databricks
databricks bundle validate --target dev
databricks bundle deploy --target dev
```

---

## Deployment Steps

| Step | Command | Description |
|------|---------|-------------|
| 1 | `terraform init && terraform apply` in `environments/dev` | Provision Azure resources, Databricks workspace, and Unity Catalog (credential, location, catalog, schemas, grants) |
| 2 | `databricks bundle deploy --target dev` | Deploy the DAB: notebook source files and the `industrial_ai_dlt_pipeline` DLT pipeline |
| 3 | `databricks bundle run industrial_ai_dlt_pipeline` | Run the DLT pipeline (Bronze → Silver → Gold). This is the only production execution path for these transformations; the standalone jobs under `databricks/resources/jobs/` are not deployed (see comments in those files) |

---

## Future Enhancements

- [ ] Event Hub → Spark Structured Streaming (real-time bronze ingestion)
- [ ] Silver deduplication with Delta MERGE
- [ ] Gold KPI dashboard (Databricks SQL or Power BI)
- [ ] Unity Catalog volumes for checkpoints and schemas
- [ ] Alerting via Azure Monitor / PagerDuty
- [ ] Full end-to-end CI/CD with GitHub Actions
