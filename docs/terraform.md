# Terraform Infrastructure Documentation

This document explains the modular, multi-environment Infrastructure as Code (IaC) architecture of the Azure Industrial AI Platform.

---

## 1. Directory Structure

The project has transitioned from a monolithic layout to a modular design separating reusable component logic from deployment environment configurations:

```
terraform/
├── modules/                   # Reusable, independent infrastructure modules
│   ├── resource_group/        # Resource group definition
│   ├── storage/               # ADLS Gen2 Storage Account & containers
│   ├── eventhub/              # Event Hubs Namespace, Hub, Consumer Groups, & Keys
│   ├── databricks/            # Databricks Workspace
│   ├── access_connector/      # Azure Databricks Access Connector (for Unity Catalog)
│   ├── rbac/                  # Resource Access Control assignments (RBAC)
│   └── monitoring/            # Log Analytics & Application Insights
│
├── environments/              # Deployments targeting target environments
│   ├── dev/                   # Development environment (Default)
│   ├── test/                  # Test environment
│   └── prod/                  # Production environment
│
└── legacy/                    # Old monolithic configuration files (saved for reference)
```

---

## 2. Reusable Modules

All resources are partitioned into self-contained modules located in the `terraform/modules/` directory. Each module conforms to standard practices by maintaining:
* `main.tf`: Core resource declarations.
* `variables.tf`: Explicit inputs expected by the module.
* `outputs.tf`: Exports resource attributes needed by downstream modules.

---

## 3. Variable and Naming Strategy

We use standard inputs to generate predictable resource names, preventing name collisions across environments:

* `project_name` (e.g., `industrial-ai`)
* `environment` (e.g., `dev`, `test`, `prod`)
* `location` (e.g., `canadacentral`)

Within the environment `main.tf` files, resource names are derived dynamically to guarantee consistency:
```hcl
locals {
  name_suffix              = "${var.project_name}-${var.environment}"
  name_suffix_alphanumeric = replace(local.name_suffix, "-", "")
  storage_account_name     = lower(substr("st${local.name_suffix_alphanumeric}", 0, 24))
}
```

This enforces consistent naming conventions:
* Resource Group: `rg-industrial-ai-dev`
* Storage Account: `stindustrialaidev`
* Event Hub Namespace: `ehns-industrial-ai-dev`
* Databricks Workspace: `dbw-industrial-ai-dev`
* Databricks Access Connector: `dbac-industrial-ai-dev`

---

## 4. State Management and Remote Backend

**This has already been completed for `dev`.** `terraform/environments/dev/backend.tf`
is configured with an `azurerm` remote backend (Azure Storage Account
`stterraformstate2026aj`, container `terraformstate`, key
`dev.terraform.tfstate`) — state is NOT local for the applied `dev`
environment. The steps below describe how to set up (or migrate) a remote
backend for a new environment that does not have one yet:

1. Create a shared Azure Storage Account specifically for Terraform states.
2. In the target environment's `backend.tf` (e.g. `terraform/environments/dev/backend.tf`), uncomment the `backend "azurerm"` block and configure the credentials:
```hcl
terraform {
  backend "azurerm" {
    resource_group_name  = "rg-terraform-state"
    storage_account_name = "sttfstatedev"
    container_name       = "tfstate"
    key                  = "dev.terraform.tfstate"
  }
}
```
3. Run `terraform init -migrate-state` to migrate local state files securely to Azure.

---

## 5. How to Deploy an Environment

To deploy a specific environment (e.g. `dev`), execute the following commands:

```bash
# 1. Log in to Azure CLI and set your target subscription
az login
az account set --subscription <YOUR_SUBSCRIPTION_ID>

# 2. Navigate to the environment folder
cd terraform/environments/dev

# 3. Initialize Terraform providers and state
terraform init

# 4. Generate and inspect the deployment plan
terraform plan

# 5. Apply the plan to provision the infrastructure
terraform apply
```

---

## 6. How to Add a New Environment

To add a new environment (e.g., `staging`):

1. Create a new directory under `terraform/environments/staging/`.
2. Copy `versions.tf`, `providers.tf`, `variables.tf`, `backend.tf`, `main.tf`, and `outputs.tf` from another environment (e.g. `dev`).
3. Modify the default values in `variables.tf` and `terraform.tfvars` to match the new environment configuration (e.g., `environment = "staging"`).
4. Run `terraform init` inside the staging directory.

---

## 7. Progressive Maturity Path

This infrastructure follows a progressive roadmap:
* **Stage 1 (Done)**: Provision standard, modular Azure resources using a local backend.
* **Stage 2 (Done for `dev`)**: Transition from local backend to Azure Storage remote state backend (`backend.tf`).
* **Stage 3 (Done)**: Extend the `databricks` module using the Databricks provider to deploy Unity Catalog objects (storage credential, external location, catalog `industrial_ai`, schemas `bronze`/`silver`/`gold`/`serving`, grants) as code.
* **Stage 4 (Current)**: Enable automated validation (`terraform fmt` & `terraform validate`) and integration checks via GitHub Actions (`.github/workflows/terraform.yml`, currently pointed at `terraform/environments/dev`).
