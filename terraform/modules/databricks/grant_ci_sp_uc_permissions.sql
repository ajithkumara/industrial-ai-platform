-- ============================================================================
-- Unity Catalog grants for the CI/CD Service Principal
-- ----------------------------------------------------------------------------
-- WHY THIS EXISTS (NOT IN TERRAFORM):
-- `databricks_storage_credential`, `databricks_external_location`, and
-- `databricks_catalog` in unity_catalog.tf require the Terraform-executing
-- identity to be a Unity Catalog metastore admin. The CI SP has been granted
-- MANAGE on the storage credential (sufficient for Terraform to read/manage
-- it -- see unity_catalog.tf), but MANAGE alone does not grant USE_CATALOG /
-- USE_SCHEMA / file read-write, which the Databricks Bundle Deploy step needs
-- to create the DLT pipeline, jobs, and registered models under
-- industrial_ai.*. Metastore-admin-only operations (like these GRANTs) cannot
-- be run by a non-admin, personal-Microsoft-account owner via the Databricks
-- Account Console either (see docs/deployment/uc-ci-sp-grants.md for why).
--
-- Run this ONCE per (metastore, catalog, service principal) combination:
--   - After a fresh `terraform apply` creates industrial_ai catalog/schemas
--     for the first time in a NEW subscription / NEW workspace / NEW metastore
--   - After rotating to a NEW CI service principal (different Application ID)
--
-- HOW TO RUN:
--   1. Open the target Databricks workspace -> SQL Editor
--   2. Replace <CI_SP_APPLICATION_ID> below with the SP's Application
--      (Client) ID -- the same value stored as the AZURE_CLIENT_ID GitHub
--      secret. This must be the literal GUID; UC does not resolve grants by
--      SP display name.
--   3. IMPORTANT: some AI "quick fix" / autocomplete features in the SQL
--      editor (e.g. Databricks Genie Code Quick Fix) will silently rewrite
--      backticks (`) into smart quotes ('), which breaks this syntax with
--      PARSE_SYNTAX_ERROR. Turn that feature OFF before running, or retype
--      the backticks manually after pasting.
--   4. Run this whole script (or run statement-by-statement).
--   5. Verify with: SHOW GRANTS ON CATALOG industrial_ai;
-- ============================================================================

GRANT USE CATALOG ON CATALOG industrial_ai TO `<CI_SP_APPLICATION_ID>`;

GRANT USE SCHEMA, CREATE TABLE, MODIFY, SELECT
  ON SCHEMA industrial_ai.bronze TO `<CI_SP_APPLICATION_ID>`;
GRANT USE SCHEMA, CREATE TABLE, MODIFY, SELECT
  ON SCHEMA industrial_ai.silver TO `<CI_SP_APPLICATION_ID>`;
GRANT USE SCHEMA, CREATE TABLE, MODIFY, SELECT
  ON SCHEMA industrial_ai.gold TO `<CI_SP_APPLICATION_ID>`;
GRANT USE SCHEMA, CREATE TABLE, MODIFY, SELECT
  ON SCHEMA industrial_ai.serving TO `<CI_SP_APPLICATION_ID>`;
GRANT USE SCHEMA, CREATE TABLE, MODIFY, SELECT
  ON SCHEMA industrial_ai.ml TO `<CI_SP_APPLICATION_ID>`;

GRANT READ FILES, WRITE FILES
  ON EXTERNAL LOCATION industrial_ai_lake TO `<CI_SP_APPLICATION_ID>`;

-- Verification:
-- SHOW GRANTS ON CATALOG industrial_ai;
-- SHOW GRANTS ON EXTERNAL LOCATION industrial_ai_lake;
