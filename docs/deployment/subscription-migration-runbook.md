# Subscription Migration Runbook

This is the step-by-step procedure to redeploy the Industrial AI Platform into a
**new Azure subscription** (e.g. moving off a trial subscription, disaster
recovery into a different subscription, or setting up a second environment).

Terraform manages almost everything, but three things sit outside Terraform's
control and must be redone by hand whenever the subscription (or the identity
running CI) changes. This runbook covers all three, plus the Terraform steps
around them.

## Overview: what is / isn't automated

| Component | Automated? | Notes |
|---|---|---|
| Resource group, storage, Event Hub, Key Vault, monitoring, Databricks workspace, RBAC | Yes (Terraform) | Re-running `terraform apply` against a new subscription recreates all of this. |
| Terraform remote state backend | Semi-automated | `terraform/bootstrap` module creates it in one command, but must be run manually once per subscription (chicken-and-egg: state backend can't store its own state). |
| Storage account global name | Manual input | Storage account names are globally unique across all of Azure. A GitHub Actions **repository variable** controls this — no code change needed, but the value may need to change. |
| Unity Catalog grants for the CI service principal | Manual (SQL) | Requires metastore-admin privileges that neither the CI SP nor a personal Microsoft account holds. Must be run once per (metastore, catalog, SP) combination via the Databricks SQL Editor. |

---

## Step 1 — Create the new Service Principal

```bash
az login
az account set --subscription <NEW_SUBSCRIPTION_ID>

az ad sp create-for-rbac \
  --name "sp-industrial-ai-github-ci" \
  --role Contributor \
  --scopes /subscriptions/<NEW_SUBSCRIPTION_ID>
```

Save the output: `appId` (client ID), `password` (client secret), `tenant`.

## Step 2 — Update GitHub repository secrets

Repo → Settings → Secrets and variables → Actions → Secrets:

| Secret | Value |
|---|---|
| `AZURE_CLIENT_ID` | `appId` from Step 1 |
| `AZURE_CLIENT_SECRET` | `password` from Step 1 |
| `AZURE_TENANT_ID` | `tenant` from Step 1 |
| `AZURE_SUBSCRIPTION_ID` | new subscription ID |

Do **not** re-add `DATABRICKS_TOKEN` or `DATABRICKS_HOST` as repository secrets
— these are derived dynamically from Terraform outputs in `ci.yml`. If they
exist as leftover secrets from a previous setup, delete them; GitHub injects
every repository secret as an env var, and a stray PAT will collide with the
SP's Azure AD auth ("more than one authorization method configured" error).

## Step 3 — Bootstrap the Terraform remote-state backend

Run **once per subscription**, locally, using the new SP or your own account
with Contributor on the new subscription:

```bash
az login
az account set --subscription <NEW_SUBSCRIPTION_ID>

cd terraform/bootstrap
terraform init
terraform apply
```

This creates `rg-terraform`, a globally-unique `sttfstate<random>` storage
account, a `terraformstate` container, and — critically — **regenerates
`backend.hcl` in each of `terraform/environments/{dev,test,prod}`** pointing
at the new storage account. Commit the updated `backend.hcl` files:

```bash
git add terraform/environments/*/backend.hcl
git commit -m "chore: point backend.hcl at new subscription's state storage"
git push
```

`ci.yml` runs `terraform init -backend-config=backend.hcl` — once this file is
committed, CI automatically uses the correct backend with no workflow edits.

## Step 4 — Set the storage account name variable

Storage account names must be globally unique across every Azure subscription
worldwide, so the old name may already exist (yours or someone else's) in the
new subscription's region. Repo → Settings → Secrets and variables → Actions
→ Variables tab → **New repository variable**:

| Variable | Value |
|---|---|
| `STORAGE_ACCOUNT_NAME_OVERRIDE` | a new globally-unique name, e.g. `stindai2026c` (lowercase alphanumeric, ≤24 chars) |

`ci.yml` reads this via `${{ vars.STORAGE_ACCOUNT_NAME_OVERRIDE }}` — no
workflow file edit needed to change subscriptions or rename the account later.

## Step 5 — Run Terraform apply (via CI or locally)

Push to `main` (or open/merge a PR) to trigger `ci.yml`'s `terraform-apply`
job, which runs Terraform for all modules except `module.databricks`'s Unity
Catalog resources are included, but note the constraint in Step 6 — plus the
Databricks Bundle Deploy.

The first run will likely fail at the **Databricks Bundle Deploy** step with a
`403 PERMISSION_DENIED ... does not have USE CATALOG` error. This is expected
— proceed to Step 6.

## Step 6 — Grant the new CI SP Unity Catalog permissions

This is the one step that cannot be automated by Terraform or CI, because it
requires **Unity Catalog metastore-admin** privileges, which neither the CI SP
nor a personal Microsoft account (e.g. a `@gmail.com`/`@outlook.com` sign-in)
can hold or grant to others.

1. Open the Databricks workspace → **SQL Editor**.
2. Open `terraform/modules/databricks/grant_ci_sp_uc_permissions.sql` in this
   repo.
3. Replace every `<CI_SP_APPLICATION_ID>` placeholder with the new SP's
   Application (Client) ID — the same GUID as `AZURE_CLIENT_ID`.
4. **Turn off any SQL editor AI auto-correct feature** (e.g. Databricks
   "Genie Code Quick Fix") before running — it has been observed silently
   rewriting the required backticks (`` ` ``) into smart quotes (`'`),
   which breaks the grant statements with `PARSE_SYNTAX_ERROR`.
5. Run the script.
6. Verify: `SHOW GRANTS ON CATALOG industrial_ai;` should list the new SP
   with `USE CATALOG`.

## Step 7 — Retrigger CI

```bash
git commit --allow-empty -m "ci: retrigger after subscription migration"
git push
```

The `terraform-apply` job should now complete Terraform apply, export
outputs, and successfully run `databricks bundle deploy -t dev`.

---

## Known limitation: different Azure AD tenant

Everything above assumes the new subscription is in the **same Azure AD
tenant** as the original Databricks account/metastore. If the new
subscription lives in a **different tenant entirely**, the existing
Databricks account and Unity Catalog metastore cannot be reused — a new
Databricks account must be created and a metastore attached via the
Databricks Account Console (which itself requires an organizational, not
personal, Microsoft account to sign in). That step is outside the scope of
this runbook and Terraform's control.
