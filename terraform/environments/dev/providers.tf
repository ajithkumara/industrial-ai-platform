provider "azurerm" {
  features {
    resource_group {
      prevent_deletion_if_contains_resources = false
    }
  }

  skip_provider_registration = true

  # P1-08: GitHub OIDC — Terraform authenticates via a short-lived OIDC
  # token from GitHub Actions instead of a static client_secret.
  # ARM_CLIENT_ID, ARM_TENANT_ID, ARM_SUBSCRIPTION_ID are set as env vars
  # in ci.yml. No ARM_CLIENT_SECRET is required when use_oidc = true.
  # For local runs: remove use_oidc and authenticate with `az login`.
  use_oidc = true
}

provider "databricks" {
  host                        = "https://${module.databricks.workspace_url}"
  azure_workspace_resource_id = module.databricks.workspace_resource_id
}