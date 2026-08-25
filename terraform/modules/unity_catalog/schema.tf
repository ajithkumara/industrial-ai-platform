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
