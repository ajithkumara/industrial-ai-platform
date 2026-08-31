# LEGACY / REFERENCE ONLY — standalone Unity Catalog stage

**Do not use this for new work.** It is superseded and not wired into any
environment.

## What this is
An earlier, standalone approach to provisioning Unity Catalog as a separate
Terraform state (`terraform/unity_catalog/dev` → `terraform/modules/unity_catalog/`).

## Why it is legacy
The **active** Unity Catalog resources live in
`terraform/modules/databricks/unity_catalog.tf`, which the canonical
`terraform/environments/dev` configuration calls via the `databricks` module.
That active path creates the storage credential, external location, catalog
`industrial_ai`, and schemas `bronze / silver / gold / serving / ml`.

This standalone stage:
- is **not referenced** by any environment (`environments/{dev,test,prod}`),
- points at a **non-existent backend** storage account
  (`stteraformstateajith2026` — a typo) that returns 404 on `terraform init`,
- duplicates (and has drifted from) the active schema set.

## Status
Retained for reference pending final confirmation it is safe to delete.
Tracked as a follow-up in `docs/infrastructure.md`. If you are provisioning a
fresh environment, ignore this directory entirely and use
`terraform/environments/<env>`.

## Related cleanup
`terraform/terraform.tfstate` at the repo root is a stray **local** state file
from an early local-backend experiment. It is gitignored (not committed) and
is not used by any active configuration; safe to delete from a working tree.
