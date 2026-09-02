output "namespace_id" {
  value       = azurerm_eventhub_namespace.ehns.id
  description = "Resource ID of the Event Hub namespace."
}

output "namespace_name" {
  value       = azurerm_eventhub_namespace.ehns.name
  description = "The Event Hub namespace name."
}

output "eventhub_name" {
  value       = azurerm_eventhub.hub.name
  description = "The Event Hub name."
}

output "producer_connection_string" {
  value       = azurerm_eventhub_authorization_rule.sender.primary_connection_string
  description = "Connection string for telemetry sender (producer)."
  sensitive   = true
}

output "consumer_connection_string" {
  value       = azurerm_eventhub_authorization_rule.reader.primary_connection_string
  description = "Connection string for telemetry reader (consumer)."
  sensitive   = true
}
