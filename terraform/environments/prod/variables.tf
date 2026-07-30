variable "project_name" {
  type        = string
  description = "The name of the project."
  default     = "industrial-ai"
}

variable "environment" {
  type        = string
  description = "The environment name (e.g. dev, test, prod)."
  default     = "prod"
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
    Environment = "prod"
  }
}
