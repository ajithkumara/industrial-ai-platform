provider "azurerm" {
  features {}
  # Subscription comes from the CLI context (az account set / ARM_SUBSCRIPTION_ID).
  # skip_provider_registration=false so a brand-new subscription gets the
  # required resource providers registered automatically during apply.
  skip_provider_registration = false
}
