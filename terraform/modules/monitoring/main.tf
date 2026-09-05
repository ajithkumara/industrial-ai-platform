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

# ── P0-03: Diagnostic Settings ───────────────────────────────────────────────
# Without these, AzureDiagnostics is empty and ALERT-01 (DLT failure query)
# never fires. Each setting routes the service's audit + diagnostic categories
# to the shared Log Analytics workspace.

resource "azurerm_monitor_diagnostic_setting" "storage" {
  name                       = "diag-storage-${var.name_suffix}"
  target_resource_id         = "${var.storage_account_id}/blobServices/default"
  log_analytics_workspace_id = azurerm_log_analytics_workspace.log_analytics.id

  enabled_log {
    category = "StorageRead"
  }
  enabled_log {
    category = "StorageWrite"
  }
  enabled_log {
    category = "StorageDelete"
  }
  metric {
    category = "Transaction"
    enabled  = true
  }
}

resource "azurerm_monitor_diagnostic_setting" "keyvault" {
  name                       = "diag-kv-${var.name_suffix}"
  target_resource_id         = var.key_vault_id
  log_analytics_workspace_id = azurerm_log_analytics_workspace.log_analytics.id

  enabled_log {
    category = "AuditEvent"
  }
  enabled_log {
    category = "AzurePolicyEvaluationDetails"
  }
  metric {
    category = "AllMetrics"
    enabled  = true
  }
}

resource "azurerm_monitor_diagnostic_setting" "eventhub" {
  name                       = "diag-eh-${var.name_suffix}"
  target_resource_id         = var.eventhub_namespace_id
  log_analytics_workspace_id = azurerm_log_analytics_workspace.log_analytics.id

  enabled_log {
    category = "OperationalLogs"
  }
  enabled_log {
    category = "AutoScaleLogs"
  }
  metric {
    category = "AllMetrics"
    enabled  = true
  }
}

resource "azurerm_monitor_diagnostic_setting" "databricks" {
  name                       = "diag-dbw-${var.name_suffix}"
  target_resource_id         = var.databricks_workspace_resource_id
  log_analytics_workspace_id = azurerm_log_analytics_workspace.log_analytics.id

  # Covers DLT pipeline runs, cluster events, job runs, UC access.
  # These are the categories that populate AzureDiagnostics for ALERT-01.
  enabled_log {
    category = "jobs"
  }
  enabled_log {
    category = "clusters"
  }
  enabled_log {
    category = "accounts"
  }
  enabled_log {
    category = "unityCatalog"
  }
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

# ── P1-13: Consumer Group Lag Alert ─────────────────────────────────────────
# Fires when the bronze-loader consumer group falls behind by > 1000 messages.
# High lag means the consumer is not keeping up with ingestion — either the
# consumer is down or ADLS writes are backed up.
resource "azurerm_monitor_metric_alert" "consumer_group_lag" {
  name                = "alert-consumer-lag-${var.name_suffix}"
  resource_group_name = var.resource_group_name
  description         = "P1-13: Consumer group 'bronze-loader' lag exceeds 1000 messages."
  severity            = 1
  enabled             = true
  frequency           = "PT5M"
  window_size         = "PT15M"
  auto_mitigate       = true

  scopes = [var.eventhub_namespace_id]

  # ConsumerGroupLag is only available on Standard+ SKU (already Standard).
  # Dimension filter scopes to the bronze-loader consumer group only.
  criteria {
    metric_namespace = "Microsoft.EventHub/namespaces"
    metric_name      = "ConsumerGroupLag"
    aggregation      = "Maximum"
    operator         = "GreaterThan"
    threshold        = 1000

    dimension {
      name     = "ConsumerGroup"
      operator = "Include"
      values   = ["bronze-loader"]
    }
  }

  action {
    action_group_id = azurerm_monitor_action_group.email.id
  }

  tags = var.tags
}

# ── P1-13: ADLS Write-Failure Alert (Log Analytics) ─────────────────────────
# Fires when StorageWrite operations on the datalake container return errors.
# Requires P0-03 diagnostic settings to be active (they route StorageWrite
# logs to the shared Log Analytics workspace).
resource "azurerm_monitor_scheduled_query_rules_alert_v2" "adls_write_failure" {
  name                = "alert-adls-write-failure-${var.name_suffix}"
  resource_group_name = var.resource_group_name
  location            = var.location
  description         = "P1-13: ADLS write errors detected — consumer may be dropping Bronze events."
  severity            = 1
  enabled             = true

  scopes                  = [azurerm_log_analytics_workspace.log_analytics.id]
  evaluation_frequency    = "PT5M"
  window_duration         = "PT15M"
  auto_mitigation_enabled = true

  criteria {
    query = <<-QUERY
      StorageBlobLogs
      | where OperationName == "PutBlob" or OperationName == "AppendFile"
      | where StatusCode >= 400
      | where Uri contains "/datalake/"
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
