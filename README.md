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
azure-telemetry-platform/
├── .github/workflows/       # CI/CD pipelines
├── apps/
│   ├── consumer/            # Event Hub consumer application
│   └── producer/            # Telemetry producer / simulator
├── config/                  # Environment configs (dev/test/prod YAML + settings)
├── databricks/
│   ├── bundles/industrial_ai/   # Databricks Asset Bundle (DAB)
│   │   └── resources/
│   │       ├── jobs/        # Per-layer job definitions
│   │       └── pipelines/   # DLT pipeline definition
│   ├── notebooks/           # Medallion layer notebooks
│   │   ├── bronze/
│   │   ├── silver/
│   │   └── gold/
│   └── sql/                 # SQL scripts for catalog/grants/schemas
├── docs/architecture/       # Architecture diagrams
├── local/                   # Local runtime files (checkpoints etc.)
├── shared/                  # Shared Python library (telemetry model, schemas, helpers)
├── terraform/
│   ├── bootstrap/           # Remote state storage setup
│   ├── environments/        # Environment-level Terraform (dev/test/prod)
│   ├── modules/             # Reusable Terraform modules
│   └── unity_catalog/       # Unity Catalog management (schemas, credentials)
├── tests/                   # Python unit tests
└── utils/                   # Shared utilities (logging)
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
cp config/dev.yaml .env.yaml
# Edit values for your Azure subscription
```

### 3. Deploy infrastructure
```bash
cd terraform/environments/dev
terraform init
terraform apply
```

### 4. Deploy Unity Catalog resources
```bash
cd terraform/unity_catalog/dev
terraform init
terraform apply
```

### 5. Deploy Databricks Assets
```bash
cd databricks/bundles/industrial_ai
databricks bundle deploy --target dev
```

---

## Deployment Steps

| Step | Command | Description |
|------|---------|-------------|
| 1 | `terraform apply` in `environments/dev` | Provision Azure resources |
| 2 | `terraform apply` in `unity_catalog/dev` | Create catalog, schemas, credentials |
| 3 | `databricks bundle deploy` | Deploy notebooks and jobs to Databricks |
| 4 | `databricks bundle run industrial_ai_bronze_job` | Run the Bronze ingestion job |

---

## Future Enhancements

- [ ] Event Hub → Spark Structured Streaming (real-time bronze ingestion)
- [ ] Silver deduplication with Delta MERGE
- [ ] Gold KPI dashboard (Databricks SQL or Power BI)
- [ ] Unity Catalog volumes for checkpoints and schemas
- [ ] Alerting via Azure Monitor / PagerDuty
- [ ] Full end-to-end CI/CD with GitHub Actions
