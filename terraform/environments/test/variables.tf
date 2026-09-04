variable "project_name" {
  type        = string
  description = "The name of the project."
  default     = "industrial-ai"
}

variable "environment" {
  type        = string
  description = "The environment name (e.g. dev, test, prod)."
  default     = "test"
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
    Environment = "test"
  }
}

# P1-06: Match dev — required to avoid storage-account rename/destroy on first apply.
variable "storage_account_name_override" {
  type        = string
  description = "Override the computed storage account name. Required when the default name is already reserved in Azure."
  default     = ""
}

variable "databricks_principal" {
  type        = string
  description = "The principal (user or group) to grant Unity Catalog permissions to. Defaults to current user if empty."
  default     = ""
}

variable "ci_principal_object_id" {
  type        = string
  description = "Object ID of the CI service principal. Grants User Access Administrator scoped to storage account."
  default     = ""
}
