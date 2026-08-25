# backup_before_subscription_expiry.ps1
#
# Run this BEFORE the Azure subscription expires (2026-08-26).
# Creates a timestamped backup folder with everything NOT in git:
#   - .env (connection strings / secrets)
#   - Terraform state files (local + pull from Azure Storage remote)
#   - MLflow artifacts (trained model + frozen_threshold.json)
#   - ADLS Gen2 data export (Bronze/Silver/Gold containers)
#
# Usage (from repo root in PowerShell):
#   .\scripts\backup_before_subscription_expiry.ps1
#
# Prerequisites:
#   - az CLI authenticated  (az login)
#   - databricks CLI authenticated (databricks auth login ...)
#   - azcopy installed  (https://learn.microsoft.com/en-us/azure/storage/common/storage-use-azcopy-v10)

$ErrorActionPreference = "Stop"
$TIMESTAMP = Get-Date -Format "yyyyMMdd_HHmmss"
$BACKUP_ROOT = "$env:USERPROFILE\Desktop\industrial-ai-backup-$TIMESTAMP"
New-Item -ItemType Directory -Force -Path $BACKUP_ROOT | Out-Null
Write-Host "==> Backup folder: $BACKUP_ROOT" -ForegroundColor Cyan

# -----------------------------------------------------------------------
# 1. .env  (connection strings — the most critical thing)
# -----------------------------------------------------------------------
Write-Host "`n[1/5] Backing up .env ..." -ForegroundColor Yellow
Copy-Item ".env" "$BACKUP_ROOT\.env"
Write-Host "    OK: .env"

# -----------------------------------------------------------------------
# 2. Terraform state files
# -----------------------------------------------------------------------
Write-Host "`n[2/5] Backing up Terraform state files ..." -ForegroundColor Yellow

# Local state (unity_catalog and root)
$tfStates = @(
    "terraform\terraform.tfstate",
    "terraform\terraform.tfstate.backup",
    "terraform\unity_catalog\dev\terraform.tfstate"
)
foreach ($f in $tfStates) {
    if (Test-Path $f) {
        $dest = "$BACKUP_ROOT\terraform-state\$($f.Replace('\','_'))"
        Copy-Item $f $dest -Force
        Write-Host "    OK: $f"
    }
}

# Remote state from Azure Storage (dev environment)
Write-Host "    Downloading remote state from Azure Storage ..."
$STORAGE_ACCOUNT = "stterraformstate2026aj"
$CONTAINER       = "terraformstate"
$KEY             = "dev.terraform.tfstate"
New-Item -ItemType Directory -Force -Path "$BACKUP_ROOT\terraform-state" | Out-Null

az storage blob download `
    --account-name $STORAGE_ACCOUNT `
    --container-name $CONTAINER `
    --name $KEY `
    --file "$BACKUP_ROOT\terraform-state\remote_dev.terraform.tfstate" `
    --auth-mode login 2>&1 | Write-Host
Write-Host "    OK: remote dev.terraform.tfstate"

# -----------------------------------------------------------------------
# 3. MLflow artifacts (trained model + frozen threshold)
# -----------------------------------------------------------------------
Write-Host "`n[3/5] Backing up MLflow artifacts ..." -ForegroundColor Yellow
Write-Host "    Listing recent training runs ..."

# List the last 5 runs of the training job (ID 302930446376341)
$runs = databricks runs list --job-id 302930446376341 --output json 2>$null | ConvertFrom-Json
if ($runs) {
    $runs | Select-Object -First 5 | ForEach-Object {
        $runId = $_.run_id
        Write-Host "    Downloading artifacts for run_id=$runId ..."
        $dest = "$BACKUP_ROOT\mlflow-artifacts\$runId"
        New-Item -ItemType Directory -Force -Path $dest | Out-Null
        databricks runs download-artifacts `
            --run-id $runId `
            --artifact-path "." `
            --target-dir $dest 2>&1 | Write-Host
        Write-Host "    OK: run $runId"
    }
} else {
    Write-Host "    WARNING: Could not list runs. Download manually from MLflow UI."
    Write-Host "    URL: https://adb-7405614704586834.14.azuredatabricks.net/#mlflow/experiments"
}

# -----------------------------------------------------------------------
# 4. ADLS Gen2 data (Delta tables: Bronze / Silver / Gold)
# -----------------------------------------------------------------------
Write-Host "`n[4/5] Backing up ADLS Gen2 Delta tables ..." -ForegroundColor Yellow
Write-Host "    Loading storage account name from .env ..."

$envVars = @{}
Get-Content ".env" | Where-Object { $_ -match "^\s*[^#]" -and $_ -match "=" } | ForEach-Object {
    $parts = $_ -split "=", 2
    $envVars[$parts[0].Trim()] = $parts[1].Trim()
}
$STORAGE_ACCT = $envVars["STORAGE_ACCOUNT_NAME"]
Write-Host "    Storage account: $STORAGE_ACCT"

$containers = @("bronze", "silver", "gold", $envVars["RAW_CONTAINER"], $envVars["CHECKPOINT_CONTAINER"])
$containers = $containers | Where-Object { $_ } | Select-Object -Unique

foreach ($container in $containers) {
    Write-Host "    Syncing container: $container ..."
    $dest = "$BACKUP_ROOT\adls\$container"
    New-Item -ItemType Directory -Force -Path $dest | Out-Null
    azcopy sync `
        "https://$STORAGE_ACCT.dfs.core.windows.net/$container" `
        $dest `
        --recursive `
        --trusted-microsoft-suffixes="*.dfs.core.windows.net" 2>&1 | Write-Host
    Write-Host "    OK: $container"
}

# -----------------------------------------------------------------------
# 5. Databricks secrets scopes
# -----------------------------------------------------------------------
Write-Host "`n[5/5] Listing Databricks secrets scopes ..." -ForegroundColor Yellow
$scopes = databricks secrets list-scopes --output json 2>$null | ConvertFrom-Json
if ($scopes) {
    $scopes | ConvertTo-Json | Out-File "$BACKUP_ROOT\databricks-secret-scopes.json"
    Write-Host "    NOTE: Secret VALUES cannot be exported from Databricks (by design)."
    Write-Host "    Scope names saved. Re-create scopes + secrets manually on new subscription."
    Write-Host "    Values are in .env (backed up in step 1)."
} else {
    Write-Host "    No secret scopes found (or not accessible)."
}

# -----------------------------------------------------------------------
# Summary
# -----------------------------------------------------------------------
Write-Host "`n============================================================" -ForegroundColor Cyan
Write-Host " BACKUP COMPLETE: $BACKUP_ROOT" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host @"

Contents:
  .env                          <- connection strings (KEEP SECURE)
  terraform-state\              <- tfstate files (local + remote)
  mlflow-artifacts\             <- trained model + frozen_threshold.json
  adls\                         <- Bronze/Silver/Gold Delta tables
  databricks-secret-scopes.json <- scope names (values are in .env)

Next step: see docs/runbooks/NEW_SUBSCRIPTION_REDEPLOYMENT.md

"@ -ForegroundColor White
