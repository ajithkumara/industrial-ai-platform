# Wait for Azure RBAC propagation to complete before validating storage credential & external location
resource "time_sleep" "wait_for_rbac" {
  create_duration = "60s"

  triggers = {
    access_connector_id           = var.access_connector_id
    access_connector_principal_id = var.access_connector_principal_id
    storage_account_name          = var.storage_account_name
  }
}

# Unity Catalog Storage Credential using Azure Access Connector (System-Assigned Managed Identity)
resource "databricks_storage_credential" "external" {
  name = "dbac-${var.name_suffix}"

  azure_managed_identity {
    access_connector_id = var.access_connector_id
  }

  comment    = "Storage Credential for Industrial AI Data Lake via Azure Access Connector Managed Identity"
  depends_on = [time_sleep.wait_for_rbac]
}

# Unity Catalog External Location pointing to ADLS Gen2 datalake container
resource "databricks_external_location" "industrial_ai_lake" {
  name            = "industrial_ai_lake"
  url             = "abfss://${var.storage_container_name}@${var.storage_account_name}.dfs.core.windows.net/"
  credential_name = databricks_storage_credential.external.name
  comment         = "External Location for Industrial AI Medallion Lakehouse"
  skip_validation = false

  depends_on = [databricks_storage_credential.external]
}

# Unity Catalog Industrial AI Catalog
resource "databricks_catalog" "industrial_ai" {
  name         = "industrial_ai"
  comment      = "Industrial AI Medallion Data Governance Catalog"
  storage_root = databricks_external_location.industrial_ai_lake.url

  depends_on = [databricks_external_location.industrial_ai_lake]
}

# Unity Catalog Schemas for Medallion Layers, Serving & ML registry.
#
# "ml" holds registered models (Isolation Forest baseline, CloudForest). It is
# REQUIRED by ml/train_bearing_isolation_forest.py, which registers models
# under the three-part UC name industrial_ai.ml.<model>. Without it, a fresh
# deployment fails model registration with SCHEMA_DOES_NOT_EXIST (this was
# previously worked around by a manual `CREATE SCHEMA` -- now provisioned as
# code so the platform is reproducible end to end).
resource "databricks_schema" "schemas" {
  for_each     = toset(["bronze", "silver", "gold", "serving", "ml"])
  catalog_name = databricks_catalog.industrial_ai.name
  name         = each.value
  comment      = "Schema for ${each.value} layer"

  depends_on = [databricks_catalog.industrial_ai]
}

data "databricks_current_user" "me" {}

locals {
  effective_principal = var.principal != "" ? var.principal : data.databricks_current_user.me.user_name
}

# Grants for Catalog (Least Privilege)
resource "databricks_grants" "catalog_grants" {
  count   = local.effective_principal != "" ? 1 : 0
  catalog = databricks_catalog.industrial_ai.name

  grant {
    principal  = local.effective_principal
    privileges = ["USE_CATALOG"]
  }

  depends_on = [databricks_catalog.industrial_ai]
}

# Grants for Schemas (Least Privilege)
resource "databricks_grants" "schema_grants" {
  for_each = local.effective_principal != "" ? databricks_schema.schemas : {}
  schema   = "${databricks_catalog.industrial_ai.name}.${each.key}"

  grant {
    principal  = local.effective_principal
    privileges = ["USE_SCHEMA", "CREATE_TABLE"]
  }

  depends_on = [databricks_schema.schemas]
}

# Grants for External Location (Least Privilege)
resource "databricks_grants" "external_location_grants" {
  count             = local.effective_principal != "" ? 1 : 0
  external_location = databricks_external_location.industrial_ai_lake.name

  grant {
    principal  = local.effective_principal
    privileges = ["READ_FILES", "WRITE_FILES", "CREATE_EXTERNAL_TABLE"]
  }

  depends_on = [databricks_external_location.industrial_ai_lake]
}

