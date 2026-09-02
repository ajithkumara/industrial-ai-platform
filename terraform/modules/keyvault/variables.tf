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
  description = "The suffix for naming resources (e.g. industrial-ai-dev)."
}

variable "databricks_mi_object_id" {
  type        = string
  description = "Object ID of the Databricks access connector managed identity. Granted Get/List on secrets."
  default     = ""
}

variable "eventhub_producer_connection_string" {
  type        = string
  description = "Event Hub producer (send-only) SAS connection string."
  sensitive   = true
}

variable "eventhub_consumer_connection_string" {
  type        = string
  description = "Event Hub consumer (listen-only) SAS connection string."
  sensitive   = true
}

variable "storage_primary_connection_string" {
  type        = string
  description = "ADLS Gen2 storage account primary connection string."
  sensitive   = true
}
