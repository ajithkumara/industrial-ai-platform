# Local backend config for local development and testing.
# To migrate to Azure Remote Backend, uncomment the block below and run:
# terraform init -migrate-state

terraform {
  backend "azurerm" {
    resource_group_name  = "rg-terraform"
    storage_account_name = "stterraformstate2026aj"
    container_name       = "terraformstate"
    key                  = "dev.terraform.tfstate"
  }
}
