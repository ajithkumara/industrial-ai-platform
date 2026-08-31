# Remote state on Azure Storage. Values are supplied at init time from the
# auto-generated backend.hcl (produced by terraform/bootstrap), so no
# subscription-specific storage account name is hardcoded here:
#
#   terraform init -backend-config=backend.hcl
#
# This keeps the same code valid across subscriptions/environments.
terraform {
  backend "azurerm" {}
}
