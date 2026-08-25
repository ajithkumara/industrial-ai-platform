-- Unity Catalog schema setup for industrial_ai catalog.
--
-- Run these once in a Databricks SQL editor (or %sql notebook cell) before
-- deploying any pipeline or job that writes to the corresponding schema.
-- Terraform (terraform/modules/unity_catalog/schema.tf) owns the permanent
-- IaC definition; this file is the "run it now without waiting for terraform apply"
-- escape hatch used during iterative development.
--
-- Safe to re-run: all statements use IF NOT EXISTS.

-- Medallion data tiers (created by terraform on initial workspace provisioning)
CREATE SCHEMA IF NOT EXISTS industrial_ai.bronze
  COMMENT 'Raw, immutable ingest layer (DLT Bronze)';

CREATE SCHEMA IF NOT EXISTS industrial_ai.silver
  COMMENT 'Cleaned and conformed layer (DLT Silver)';

CREATE SCHEMA IF NOT EXISTS industrial_ai.gold
  COMMENT 'Feature-engineered, business-level aggregates (DLT Gold)';

-- ML model registry (added 2026-08: Unity Catalog requires a three-part
-- catalog.schema.model name for registered models -- bare model names are
-- rejected at registration time, unlike the legacy workspace registry).
-- See terraform/modules/unity_catalog/schema.tf for the Terraform resource.
CREATE SCHEMA IF NOT EXISTS industrial_ai.ml
  COMMENT 'Registered ML models (Isolation Forest baselines, CloudForest, etc.)';
