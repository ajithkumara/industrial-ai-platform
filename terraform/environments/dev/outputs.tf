output "resource_group_name" {
  value       = module.resource_group.name
  description = "The name of the resource group."
}

output "storage_account_name" {
  value       = module.storage.name
  description = "The name of the ADLS Gen2 storage account."
}

output "storage_account_primary_connection_string" {
  value       = module.storage.primary_connection_string
  description = "The primary connection string for the storage account."
  sensitive   = true
}

output "eventhub_namespace_name" {
  value       = module.eventhub.namespace_name
  description = "The Event Hub namespace name."
}

output "eventhub_name" {
  value       = module.eventhub.eventhub_name
  description = "The Event Hub name."
}

output "eventhub_producer_connection_string" {
  value       = module.eventhub.producer_connection_string
  description = "Connection string for telemetry sender (producer)."
  sensitive   = true
}

output "eventhub_consumer_connection_string" {
  value       = module.eventhub.consumer_connection_string
  description = "Connection string for telemetry reader (consumer)."
  sensitive   = true
}

output "databricks_workspace_url" {
  value       = module.databricks.workspace_url
  description = "The URL of the Databricks workspace."
}

output "databricks_access_connector_id" {
  value       = module.access_connector.id
  description = "The ID of the Databricks Access Connector."
}

output "databricks_workspace_id" {
  value       = module.databricks.workspace_id
  description = "The numeric workspace ID of the Databricks workspace."
}

output "log_analytics_workspace_id" {
  value       = module.monitoring.log_analytics_workspace_id
  description = "The Workspace ID of the Log Analytics workspace."
}

output "app_insights_instrumentation_key" {
  value       = module.monitoring.app_insights_instrumentation_key
  description = "The Instrumentation Key of the Application Insights instance."
  sensitive   = true
}

output "app_insights_connection_string" {
  value       = module.monitoring.app_insights_connection_string
  description = "The Connection String of the Application Insights instance."
  sensitive   = true
}

output "unity_catalog_name" {
  value       = module.databricks.catalog_name
  description = "The name of the Unity Catalog."
}

output "unity_catalog_storage_credential_name" {
  value       = module.databricks.storage_credential_name
  description = "The name of the Databricks Unity Catalog storage credential."
}

output "unity_catalog_external_location_name" {
  value       = module.databricks.external_location_name
  description = "The name of the Databricks Unity Catalog external location."
}

