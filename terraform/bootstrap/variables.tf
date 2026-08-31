variable "state_resource_group_name" {
  type        = string
  description = "Resource group that holds the Terraform remote-state storage account."
  default     = "rg-terraform"
}

variable "location" {
  type        = string
  description = "Azure region for the state storage account."
  default     = "canadacentral"
}

variable "state_container_name" {
  type        = string
  description = "Blob container that holds the state files."
  default     = "terraformstate"
}

variable "environments" {
  type        = list(string)
  description = "Environments to generate backend.hcl files for."
  default     = ["dev", "test", "prod"]
}

variable "tags" {
  type        = map(string)
  description = "Tags applied to the state resources."
  default = {
    Project   = "Industrial AI Platform"
    ManagedBy = "Terraform"
    Purpose   = "terraform-remote-state"
  }
}
