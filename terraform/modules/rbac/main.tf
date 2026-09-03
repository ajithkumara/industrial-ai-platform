resource "azurerm_role_assignment" "role_assignment" {
  scope                = var.scope
  role_definition_name = var.role_definition_name
  principal_id         = var.principal_id
}

# ----------------------------------------------------------------------------
# Grant the Terraform-executing identity (in CI, the CI service principal)
# User Access Administrator scoped to this same resource ONLY. Azure's
# built-in "Contributor" role explicitly excludes
# Microsoft.Authorization/*/Write and .../Delete, so a Contributor-only SP
# cannot create OR delete role assignments -- including the one above. This
# caused a real incident (2026-09-02): Terraform tried to replace
# azurerm_role_assignment.role_assignment (forced by an unrelated storage
# account rename) and failed with 403 AuthorizationFailed on the delete,
# after already destroying dependent resources. See
# docs/deployment/subscription-migration-runbook.md.
#
# BOOTSTRAP NOTE: this resource has the same chicken-and-egg problem it
# fixes -- a Contributor-only SP cannot create it either. It must be applied
# ONCE by a higher-privileged identity (e.g. the subscription Owner, via
# `terraform apply -target=module.rbac` run locally with `az login`), after
# which it is in state and the CI SP can refresh/manage it going forward.
#
# ci_principal_object_id is passed explicitly (not read from
# data.azurerm_client_config.current) because that data source resolves to
# whichever identity is CURRENTLY authenticated -- which is the point of this
# bootstrap (a higher-privileged human identity, not the CI SP) the first
# time this runs. Using the data source here would grant the human running
# the bootstrap this role instead of the CI SP.
# ----------------------------------------------------------------------------
resource "azurerm_role_assignment" "ci_principal_user_access_administrator" {
  count                = var.ci_principal_object_id != "" ? 1 : 0
  scope                = var.scope
  role_definition_name = "User Access Administrator"
  principal_id         = var.ci_principal_object_id
}
