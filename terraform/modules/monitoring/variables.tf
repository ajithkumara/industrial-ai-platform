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
  description = "Resource ID of the Event Hub namespace (used for the lag metric alert)."
}

variable "subscription_id" {
  type        = string
  description = "Azure subscription ID (used for the cost budget alert)."
}
