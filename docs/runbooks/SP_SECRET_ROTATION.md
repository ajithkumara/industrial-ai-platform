# Service Principal Secret Rotation Runbook

**Applies to:** All environments (dev / test / prod)  
**Frequency:** Every 90 days (or immediately on suspected compromise)  
**Owner:** Platform Engineering

---

## Context

After P1-08 (GitHub OIDC), CI/CD no longer uses a static SP client secret for
Terraform apply. However, a client secret still exists on the Azure AD App
Registration and is used for:

- Local developer Terraform runs (`az login` delegates to this SP)
- Any non-GitHub automation that calls Azure APIs directly

Secrets must be rotated before they expire to avoid service disruption.

---

## Pre-rotation Checklist

- [ ] Confirm the current secret expiry in Azure Portal → App Registrations → Certificates & Secrets
- [ ] Identify all consumers of the secret (check Key Vault references, `.env` files, any non-GitHub pipelines)
- [ ] Schedule the rotation outside business hours if prod is affected
- [ ] Notify the team in Slack `#platform-ops` at least 24 hours in advance

---

## Rotation Steps

### 1. Create a new secret

```bash
# App Registration Object ID — find in Azure Portal
APP_OBJECT_ID="<your-app-object-id>"

az ad app credential reset \
  --id "$APP_OBJECT_ID" \
  --append \
  --years 1 \
  --display-name "CI-$(date +%Y-%m-%d)"
```

Copy the returned `password` value — it is shown only once.

### 2. Update Key Vault (if stored there)

```bash
KEY_VAULT_NAME="kv-industrial-ai-dev"   # adjust per environment

az keyvault secret set \
  --vault-name "$KEY_VAULT_NAME" \
  --name "sp-client-secret" \
  --value "<new-secret>"
```

### 3. Update GitHub repository variables (only if used in any workflow)

GitHub Settings → Secrets and variables → Actions → Update `AZURE_CLIENT_SECRET`
(note: P1-08 removed this from the main CI workflow, but it may still exist for
 manual dispatch workflows — verify before skipping).

### 4. Update `.env.example` / developer onboarding docs if the secret name changed

### 5. Smoke-test the new secret

```bash
# Export new credentials locally
export ARM_CLIENT_ID="<client-id>"
export ARM_CLIENT_SECRET="<new-secret>"
export ARM_TENANT_ID="<tenant-id>"
export ARM_SUBSCRIPTION_ID="<subscription-id>"

# Verify Terraform can authenticate
cd terraform/environments/dev
terraform init -backend-config=backend.hcl
terraform plan -target=module.resource_group
```

Expected: plan completes with no auth errors.

### 6. Delete the old secret

```bash
# List credentials to find the old one's key ID
az ad app credential list --id "$APP_OBJECT_ID" --query "[].{id:keyId, displayName:displayName, endDate:endDateTime}"

# Delete by key ID
az ad app credential delete \
  --id "$APP_OBJECT_ID" \
  --key-id "<old-key-id>"
```

### 7. Verify deletion

```bash
az ad app credential list --id "$APP_OBJECT_ID"
```

Only the new credential should appear.

---

## OIDC Bootstrap (one-time, per environment)

GitHub OIDC (P1-08) requires a **federated identity credential** on the App
Registration — this is a one-time setup per environment, not part of the
90-day rotation cycle.

```bash
# Replace placeholders with your GitHub org/repo and environment name
az ad app federated-credential create \
  --id "$APP_OBJECT_ID" \
  --parameters '{
    "name": "github-actions-dev",
    "issuer": "https://token.actions.githubusercontent.com",
    "subject": "repo:<ORG>/<REPO>:environment:dev",
    "audiences": ["api://AzureADTokenExchange"]
  }'
```

Repeat for `test` and `prod` environments, changing `subject` accordingly:
- `repo:<ORG>/<REPO>:environment:test`
- `repo:<ORG>/<REPO>:ref:refs/heads/main` (for push-triggered prod deploys)

---

## Escalation

If the secret has already expired and CI is broken:

1. Create a new secret (Step 1 above) — takes ~2 minutes
2. Update GitHub Actions secret immediately (Step 3)
3. Re-run the failed workflow
4. Complete the full rotation checklist retroactively
