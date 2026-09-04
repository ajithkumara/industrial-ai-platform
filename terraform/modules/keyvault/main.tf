data "azurerm_client_config" "current" {}

resource "azurerm_key_vault" "kv" {
  name                        = "kv-${var.name_suffix}"
  location                    = var.location
  resource_group_name         = var.resource_group_name
  tenant_id                   = data.azurerm_client_config.current.tenant_id
  sku_name                    = "standard"
  soft_delete_retention_days  = 7
  purge_protection_enabled    = false  # false for dev; set true for prod

  # P0-02: Prevent accidental Key Vault destruction.
  # Losing the Key Vault deletes all stored connection strings (Event Hub,
  # storage). Even with soft-delete, recreation requires manual secret
  # re-entry and a new access-policy bootstrap run.
  lifecycle {
    prevent_destroy = true
  }

  # Allow the deploying identity (SP or user) to manage secrets
  access_policy {
    tenant_id = data.azurerm_client_config.current.tenant_id
    object_id = data.azurerm_client_config.current.object_id

    secret_permissions = [
      "Get", "List", "Set", "Delete", "Recover", "Backup", "Restore"
    ]
  }

  # Allow the Databricks access connector MI to read secrets at runtime
  dynamic "access_policy" {
    for_each = var.databricks_mi_object_id != "" ? [1] : []
    content {
      tenant_id = data.azurerm_client_config.current.tenant_id
      object_id = var.databricks_mi_object_id
      secret_permissions = ["Get", "List"]
    }
  }

  tags = var.tags
}

# ── Secrets ───────────────────────────────────────────────────────────────────

resource "azurerm_key_vault_secret" "eventhub_producer" {
  name         = "eventhub-producer-connection-string"
  value        = var.eventhub_producer_connection_string
  key_vault_id = azurerm_key_vault.kv.id

  tags = var.tags
}

resource "azurerm_key_vault_secret" "eventhub_consumer" {
  name         = "eventhub-consumer-connection-string"
  value        = var.eventhub_consumer_connection_string
  key_vault_id = azurerm_key_vault.kv.id

  tags = var.tags
}

resource "azurerm_key_vault_secret" "storage_connection_string" {
  name         = "storage-primary-connection-string"
  value        = var.storage_primary_connection_string
  key_vault_id = azurerm_key_vault.kv.id

  tags = var.tags
}
