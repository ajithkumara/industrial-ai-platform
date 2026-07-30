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
