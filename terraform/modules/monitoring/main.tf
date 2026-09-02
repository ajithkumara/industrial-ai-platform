resource "azurerm_log_analytics_workspace" "log_analytics" {
  name                = "law-${var.name_suffix}"
  location            = var.location
  resource_group_name = var.resource_group_name
  sku                 = "PerGB2018"
  retention_in_days   = 30

  tags = var.tags
}

resource "azurerm_application_insights" "app_insights" {
  name                = "appi-${var.name_suffix}"
  location            = var.location
  resource_group_name = var.resource_group_name
  workspace_id        = azurerm_log_analytics_workspace.log_analytics.id
  application_type    = "web"

  tags = var.tags
}

# ── Action Group ─────────────────────────────────────────────────────────────
# Single action group used by all alert rules below.
# Email: aakumara@gmail.com
resource "azurerm_monitor_action_group" "email" {
  name                = "ag-${var.name_suffix}"
  resource_group_name = var.resource_group_name
  short_name          = "indai-dev"

  email_receiver {
    name                    = "Ajith Kumara"
    email_address           = "aakumara@gmail.com"
    use_common_alert_schema = true
  }

  tags = var.tags
}

# ── ALERT-01: DLT Pipeline Failure (Log Analytics query) ────────────────────
resource "azurerm_monitor_scheduled_query_rules_alert_v2" "dlt_failure" {
  name                = "alert-dlt-pipeline-failure-${var.name_suffix}"
  resource_group_name = var.resource_group_name
  location            = var.location
  description         = "Fires when industrial_ai_dlt_pipeline records a failed update."
  severity            = 1
  enabled             = true

  scopes                  = [azurerm_log_analytics_workspace.log_analytics.id]
  evaluation_frequency    = "PT5M"
  window_duration         = "PT15M"
  auto_mitigation_enabled = true

  criteria {
    query                   = <<-QUERY
      AzureDiagnostics
      | where ResourceProvider == "MICROSOFT.DATABRICKS"
      | where ResultType == "Failed"
      | where ResourceId contains "dbw-industrial-ai-dev"
    QUERY
    time_aggregation_method = "Count"
    threshold               = 0
    operator                = "GreaterThan"

    failing_periods {
      minimum_failing_periods_to_trigger_alert = 1
      number_of_evaluation_periods             = 1
    }
  }

  action {
    action_groups = [azurerm_monitor_action_group.email.id]
  }

  tags = var.tags
}

# ── ALERT-02: Event Hub Incoming Message Lag (metric alert) ─────────────────
resource "azurerm_monitor_metric_alert" "eventhub_lag" {
  name                = "alert-eventhub-lag-${var.name_suffix}"
  resource_group_name = var.resource_group_name
  description         = "Fires when Event Hub receives no messages for 15 minutes."
  severity            = 2
  enabled             = true
  frequency           = "PT5M"
  window_size         = "PT15M"
  auto_mitigate       = true

  scopes = [var.eventhub_namespace_id]

  criteria {
    metric_namespace = "Microsoft.EventHub/namespaces"
    metric_name      = "IncomingMessages"
    aggregation      = "Total"
    operator         = "LessThan"
    threshold        = 1
  }

  action {
    action_group_id = azurerm_monitor_action_group.email.id
  }

  tags = var.tags
}

# ── ALERT-03: Subscription Cost Budget ───────────────────────────────────────
resource "azurerm_consumption_budget_subscription" "dev" {
  name            = "budget-industrial-ai-dev"
  subscription_id = var.subscription_id
  amount          = 50
  time_grain      = "Monthly"

  time_period {
    start_date = "2026-09-01T00:00:00Z"
  }

  notification {
    enabled        = true
    threshold      = 80
    operator       = "GreaterThan"
    threshold_type = "Actual"
    contact_emails = ["aakumara@gmail.com"]
  }
}
