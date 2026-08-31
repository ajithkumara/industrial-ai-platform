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

resource "databricks_schema" "bronze" {
  catalog_name = var.catalog_name
  name         = "bronze"
  comment      = "Bronze schema for raw data"
}

resource "databricks_schema" "silver" {
  catalog_name = var.catalog_name
  name         = "silver"
  comment      = "Silver schema for cleaned and conformed data"
}

resource "databricks_schema" "gold" {
  catalog_name = var.catalog_name
  name         = "gold"
  comment      = "Gold schema for business-level aggregates"
}

# 2026-08: registered models require a three-part Unity Catalog name
# (catalog.schema.model), same as tables -- ml/train_bearing_isolation_forest.py
# and (eventually) ml/cloud_forest/train_cloud_forest.py both need a schema
# to register into. Kept separate from bronze/silver/gold, which are
# reserved for data tables at specific medallion quality tiers, not model
# artifacts.
resource "databricks_schema" "ml" {
  catalog_name = var.catalog_name
  name         = "ml"
  comment      = "Registered ML models (Isolation Forest baselines, CloudForest, etc.)"
}