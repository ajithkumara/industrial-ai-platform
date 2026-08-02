output "role_assignment_id" {
  value       = azurerm_role_assignment.role_assignment.id
  description = "The ID of the role assignment."
}

output "principal_id" {
  value       = azurerm_role_assignment.role_assignment.principal_id
  description = "The principal ID of the assigned role."
}
