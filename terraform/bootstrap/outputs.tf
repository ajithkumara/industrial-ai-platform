output "state_resource_group_name" {
  value       = azurerm_resource_group.state.name
  description = "Resource group holding the Terraform remote-state storage account."
}

output "state_storage_account_name" {
  value       = azurerm_storage_account.state.name
  description = "Globally-unique storage account that holds remote state. Referenced by each environment's generated backend.hcl."
}

output "state_container_name" {
  value       = azurerm_storage_container.state.name
  description = "Blob container holding the per-environment state files."
}

output "next_step" {
  value       = "backend.hcl files generated for: ${join(", ", var.environments)}. Next: cd ../environments/dev && terraform init -backend-config=backend.hcl"
  description = "What to do next."
}
