variable "scope" {
  type        = string
  description = "The scope at which the role assignment should be applied (e.g., storage account ID)."
}

variable "principal_id" {
  type        = string
  description = "The principal ID of the identity receiving the role assignment."
}

variable "role_definition_name" {
  type        = string
  description = "The name of the role to assign."
  default     = "Storage Blob Data Contributor"
}

variable "ci_principal_object_id" {
  type        = string
  description = <<-EOT
    Object ID (not the Application/Client ID) of the CI service principal.
    Grants it "User Access Administrator" scoped to `var.scope` only, so it
    can manage (including replace/delete) role assignments at that scope
    without hitting 403 AuthorizationFailed under plain Contributor. Empty
    string skips this grant (e.g. for local/manual runs). Find the object ID
    with: az ad sp show --id <AZURE_CLIENT_ID> --query id -o tsv
  EOT
  default     = ""
}
