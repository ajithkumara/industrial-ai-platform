variable "resource_group_name" {
  type        = string
  description = "The name of the resource group."
}

variable "location" {
  type        = string
  description = "The Azure region."
}

variable "tags" {
  type        = map(string)
  description = "A mapping of tags to assign to the resource."
}

variable "name_suffix" {
  type        = string
  description = "The suffix for naming resources (e.g. project-env)."
}

variable "eventhub_namespace_id" {
  type        = string
  description = "Resource ID of the Event Hub namespace (used for the lag metric alert and diagnostic settings)."
}

variable "subscription_id" {
  type        = string
  description = "Azure subscription ID (used for the cost budget alert)."
}

# P0-03: Diagnostic settings targets
variable "storage_account_id" {
  type        = string
  description = "Resource ID of the data storage account (ADLS Gen2) — for diagnostic settings."
}

variable "key_vault_id" {
  type        = string
  description = "Resource ID of the Key Vault — for diagnostic settings."
}

variable "databricks_workspace_resource_id" {
  type        = string
  description = "Resource ID of the Databricks workspace — for diagnostic settings."
}
