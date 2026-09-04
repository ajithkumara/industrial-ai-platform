resource "azurerm_eventhub_namespace" "ehns" {
  name                = "ehns-${var.name_suffix}"
  location            = var.location
  resource_group_name = var.resource_group_name
  sku                 = "Standard"
  capacity            = 1

  tags = var.tags
}

resource "azurerm_eventhub" "hub" {
  name                = "telemetryhub"
  namespace_name      = azurerm_eventhub_namespace.ehns.name
  resource_group_name = var.resource_group_name
  partition_count     = 2
  message_retention   = 7  # P1-14: 7-day retention — minimum replay window for incident recovery
}

# Explicitly provision a custom consumer group
resource "azurerm_eventhub_consumer_group" "bronze_loader" {
  name                = "bronze-loader"
  namespace_name      = azurerm_eventhub_namespace.ehns.name
  eventhub_name       = azurerm_eventhub.hub.name
  resource_group_name = var.resource_group_name
}

# Authorization Rule for Event Hub Producer (Send only)
resource "azurerm_eventhub_authorization_rule" "sender" {
  name                = "telemetry-sender"
  namespace_name      = azurerm_eventhub_namespace.ehns.name
  eventhub_name       = azurerm_eventhub.hub.name
  resource_group_name = var.resource_group_name
  listen              = false
  send                = true
  manage              = false
}

# Authorization Rule for Event Hub Consumer (Listen only)
resource "azurerm_eventhub_authorization_rule" "reader" {
  name                = "telemetry-reader"
  namespace_name      = azurerm_eventhub_namespace.ehns.name
  eventhub_name       = azurerm_eventhub.hub.name
  resource_group_name = var.resource_group_name
  listen              = true
  send                = false
  manage              = false
}
