# ============================================================================
# LEGACY / REFERENCE ONLY -- NOT part of the active deployment.
#
# This standalone Unity Catalog stage (terraform/unity_catalog/dev + this
# modules/unity_catalog/) is SUPERSEDED by the inline UC resources in
# terraform/modules/databricks/unity_catalog.tf, which the canonical
# terraform/environments/dev configuration actually calls (via the "databricks"
# module). The active path creates the storage credential, external location,
# catalog "industrial_ai", and schemas (bronze/silver/gold/serving/ml).
#
# This module is retained for reference only. It is NOT wired into any
# environment, and its root config (terraform/unity_catalog/dev) points at a
# non-existent backend storage account (stteraformstateajith2026, a typo) that
# 404s on init. Do NOT use it for new work. Kept (not deleted) pending final
# confirmation it is safe to remove; see docs/infrastructure.md.
# ============================================================================

resource "databricks_storage_credential" "external_mi" {
  name = "mi_credential_${var.name_suffix}"
  azure_managed_identity {
    access_connector_id = var.access_connector_id
  }
}