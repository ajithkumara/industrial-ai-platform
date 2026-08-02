output "id" {
  value       = azurerm_storage_account.storage.id
  description = "The ID of the storage account."
}

output "name" {
  value       = azurerm_storage_account.storage.name
  description = "The name of the storage account."
}

output "primary_connection_string" {
  value       = azurerm_storage_account.storage.primary_connection_string
  description = "The primary connection string for the storage account."
  sensitive   = true
}

output "datalake_container_name" {
  value       = azurerm_storage_data_lake_gen2_filesystem.datalake.name
  description = "The name of the datalake container."
}

