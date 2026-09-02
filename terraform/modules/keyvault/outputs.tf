output "key_vault_id" {
  value       = azurerm_key_vault.kv.id
  description = "Resource ID of the Key Vault."
}

output "key_vault_name" {
  value       = azurerm_key_vault.kv.name
  description = "Name of the Key Vault."
}

output "key_vault_uri" {
  value       = azurerm_key_vault.kv.vault_uri
  description = "URI of the Key Vault (e.g. https://kv-industrial-ai-dev.vault.azure.net/)."
}

output "eventhub_producer_secret_name" {
  value       = azurerm_key_vault_secret.eventhub_producer.name
  description = "KV secret name for the Event Hub producer connection string."
}

output "eventhub_consumer_secret_name" {
  value       = azurerm_key_vault_secret.eventhub_consumer.name
  description = "KV secret name for the Event Hub consumer connection string."
}

output "storage_connection_string_secret_name" {
  value       = azurerm_key_vault_secret.storage_connection_string.name
  description = "KV secret name for the storage account primary connection string."
}
