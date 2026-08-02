provider "azurerm" {
  features {
    resource_group {
      prevent_deletion_if_contains_resources = false
    }
  }

  skip_provider_registration = true
}

provider "databricks" {
  host                        = "https://${module.databricks.workspace_url}"
  azure_workspace_resource_id = module.databricks.workspace_resource_id
}