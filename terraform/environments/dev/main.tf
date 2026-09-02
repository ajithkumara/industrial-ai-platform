data "azurerm_subscription" "current" {}

locals {
  name_suffix              = "${var.project_name}-${var.environment}"
  name_suffix_alphanumeric = replace(local.name_suffix, "-", "")

  # Ensure storage account name is valid (lowercase, alphanumeric, max 24 chars).
  # If storage_account_name_override is set in tfvars, use it directly (needed when
  # Azure is still holding the default name from a previous subscription).
  storage_account_name = (
    var.storage_account_name_override != "" ?
    var.storage_account_name_override :
    lower(substr("st${local.name_suffix_alphanumeric}2026", 0, 24))
  )
}

module "resource_group" {
  source       = "../../modules/resource_group"
  project_name = var.project_name
  environment  = var.environment
  location     = var.location
  tags         = var.tags
}

module "storage" {
  source               = "../../modules/storage"
  resource_group_name  = module.resource_group.name
  location             = module.resource_group.location
  tags                 = var.tags
  storage_account_name = local.storage_account_name
}

module "eventhub" {
  source              = "../../modules/eventhub"
  resource_group_name = module.resource_group.name
  location            = module.resource_group.location
  tags                = var.tags
  name_suffix         = local.name_suffix
}

module "databricks" {
  source                        = "../../modules/databricks"
  resource_group_name           = module.resource_group.name
  location                      = module.resource_group.location
  tags                          = var.tags
  name_suffix                   = local.name_suffix
  environment                   = var.environment
  storage_account_name          = local.storage_account_name
  storage_container_name        = module.storage.datalake_container_name
  access_connector_id           = module.access_connector.id
  access_connector_principal_id = module.rbac.principal_id
  principal                     = var.databricks_principal

  depends_on = [module.rbac]
}

module "access_connector" {
  source              = "../../modules/access_connector"
  resource_group_name = module.resource_group.name
  location            = module.resource_group.location
  tags                = var.tags
  name_suffix         = local.name_suffix
}

module "rbac" {
  source       = "../../modules/rbac"
  scope        = module.storage.id
  principal_id = module.access_connector.principal_id
}

module "keyvault" {
  source                              = "../../modules/keyvault"
  resource_group_name                 = module.resource_group.name
  location                            = module.resource_group.location
  tags                                = var.tags
  name_suffix                         = local.name_suffix
  databricks_mi_object_id             = module.access_connector.principal_id
  eventhub_producer_connection_string = module.eventhub.producer_connection_string
  eventhub_consumer_connection_string = module.eventhub.consumer_connection_string
  storage_primary_connection_string   = module.storage.primary_connection_string

  depends_on = [module.resource_group]
}

module "monitoring" {
  source                = "../../modules/monitoring"
  resource_group_name   = module.resource_group.name
  location              = module.resource_group.location
  tags                  = var.tags
  name_suffix           = local.name_suffix
  eventhub_namespace_id = module.eventhub.namespace_id
  subscription_id       = data.azurerm_subscription.current.id
}

