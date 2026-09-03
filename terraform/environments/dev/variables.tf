variable "project_name" {
  type        = string
  description = "The name of the project."
  default     = "industrial-ai"
}

variable "environment" {
  type        = string
  description = "The environment name (e.g. dev, test, prod)."
  default     = "dev"
}

variable "location" {
  type        = string
  description = "The Azure region."
  default     = "canadacentral"
}

variable "tags" {
  type        = map(string)
  description = "A mapping of tags to assign to the resource."
  default = {
    Project     = "Industrial AI Platform"
    ManagedBy   = "Terraform"
    Environment = "dev"
  }
}

variable "storage_account_name_override" {
  type        = string
  description = "Override the computed storage account name. Use when the default name is still reserved by a previous Azure subscription."
  default     = ""
}

variable "databricks_principal" {
  type        = string
  description = "The principal (user or group) to grant Unity Catalog permissions to. Defaults to current user if empty."
  default     = ""
}

variable "ci_principal_object_id" {
  type        = string
  description = "Object ID of the CI service principal. Grants it User Access Administrator scoped to the storage account only, so Terraform can manage role assignments there without hitting 403 under plain Contributor. See terraform/modules/rbac/variables.tf."
  default     = ""
}

