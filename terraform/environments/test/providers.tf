provider "azurerm" {
  features {
    resource_group {
      prevent_deletion_if_contains_resources = false
    }
  }

  skip_provider_registration = true

  # P1-08: GitHub OIDC — no ARM_CLIENT_SECRET required.
  use_oidc = true
}
