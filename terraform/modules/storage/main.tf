resource "azurerm_storage_account" "storage" {
  name                     = var.storage_account_name
  resource_group_name      = var.resource_group_name
  location                 = var.location
  account_tier             = "Standard"
  account_replication_type = "LRS"
  account_kind             = "StorageV2"
  is_hns_enabled           = true # Enable hierarchical namespace for ADLS Gen2

  # P0-05: Enable blob versioning — protects Bronze/Silver/Gold data from
  # accidental overwrites and enables point-in-time recovery of individual blobs.
  blob_properties {
    versioning_enabled = true
  }

  tags = var.tags

  # P0-02: Guard against accidental destroy.
  # A storage account rename (e.g. if STORAGE_ACCOUNT_NAME_OVERRIDE is unset)
  # forces a destroy/recreate and permanently deletes all ADLS data.
  # This block makes `terraform plan` fail with an explicit error before any
  # destroy is attempted — the operator must remove this block intentionally.
  lifecycle {
    prevent_destroy = true
  }
}

resource "azurerm_storage_data_lake_gen2_filesystem" "datalake" {
  name               = "datalake"
  storage_account_id = azurerm_storage_account.storage.id

  # P0-02: Destroying the datalake filesystem deletes all Bronze/Silver/Gold data.
  lifecycle {
    prevent_destroy = true
  }
}

resource "azurerm_storage_data_lake_gen2_filesystem" "checkpoint" {
  name               = "checkpoint"
  storage_account_id = azurerm_storage_account.storage.id

  # P0-02: Destroying the checkpoint filesystem loses all consumer offset state,
  # forcing a full re-read from the oldest available Event Hubs offset.
  lifecycle {
    prevent_destroy = true
  }
}

# P1-09: Lifecycle management — move cold Bronze/Silver/Gold data to cheaper
# storage tiers automatically. Raw telemetry (Bronze) is queried heavily for
# the first 30 days then rarely; Gold aggregates are small and stay hot.
# Checkpoints must never be tiered — they are read on every consumer restart.
resource "azurerm_storage_management_policy" "lifecycle" {
  storage_account_id = azurerm_storage_account.storage.id

  rule {
    name    = "bronze-tier-down"
    enabled = true
    filters {
      prefix_match = ["datalake/raw/"]
      blob_types   = ["blockBlob"]
    }
    actions {
      base_blob {
        tier_to_cool_after_days_since_modification_greater_than    = 30
        tier_to_archive_after_days_since_modification_greater_than = 90
      }
    }
  }

  rule {
    name    = "silver-tier-down"
    enabled = true
    filters {
      prefix_match = ["datalake/silver/"]
      blob_types   = ["blockBlob"]
    }
    actions {
      base_blob {
        tier_to_cool_after_days_since_modification_greater_than    = 60
        tier_to_archive_after_days_since_modification_greater_than = 180
      }
    }
  }
}
