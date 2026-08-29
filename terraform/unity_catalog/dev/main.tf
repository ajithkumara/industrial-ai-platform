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

module "unity_catalog" {
  source               = "../../modules/unity_catalog"
  environment          = var.environment
  location             = var.location
  name_suffix          = var.name_suffix
  storage_account_name = var.storage_account_name
  access_connector_id  = var.access_connector_id
  databricks_host      = var.databricks_host
  workspace_id         = var.workspace_id
  catalog_name         = var.catalog_name
}