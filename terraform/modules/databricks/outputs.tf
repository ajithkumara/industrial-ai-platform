output "workspace_url" {
  value       = azurerm_databricks_workspace.databricks.workspace_url
  description = "The URL of the Databricks workspace."
}

output "workspace_id" {
  value       = azurerm_databricks_workspace.databricks.workspace_id
  description = "The ID of the Databricks workspace."
}

output "workspace_resource_id" {
  value       = azurerm_databricks_workspace.databricks.id
  description = "The Azure Resource ID of the Databricks workspace."
}

output "catalog_name" {
  value       = databricks_catalog.industrial_ai.name
  description = "The name of the Unity Catalog."
}

output "storage_credential_name" {
  value       = databricks_storage_credential.external.name
  description = "The name of the Unity Catalog storage credential."
}

output "external_location_name" {
  value       = databricks_external_location.industrial_ai_lake.name
  description = "The name of the Unity Catalog external location."
}

