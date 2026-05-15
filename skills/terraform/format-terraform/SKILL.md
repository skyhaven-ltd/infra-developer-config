---
name: format-terraform
description: Enforce Terraform file structure, tfvars area comment blocks, naming, tagging, pinning, and formatting standards — objective pass/fail checks
---

Terraform linter. Hard requirements — every deviation is a finding. Scan all `.tf` and `.tfvars` files in the repo. Report all violations, then offer to auto-fix.

## Rules

### 1. Directory Layout

- All `.tf` files under `infra/`. Flag any `.tf` outside `infra/`.
- All `.tfvars` under `infra/vars/`.
- Required: `infra/vars/globals.tfvars` + one per environment (e.g. `dev.tfvars`, `prd.tfvars`).
- `globals.tfvars` = shared values that genuinely vary between deployments. Environment files = values that differ per env (SKUs, counts, flags).
- Do not require these baseline naming/location values in any `.tfvars`; they may be hardcoded as variable defaults instead:
  - `location = "uksouth"`
  - `location_short = "uks"`
  - `workload = "PLACEHOLDER"`
  - `instance = "01"`

### 2. Block-Type Files

Each block type in its own underscore-prefixed file. No block of these types in any other `.tf` file.

| Block type | File |
|------------|------|
| `terraform {}` | `infra/_terraform.tf` |
| `provider` | `infra/_providers.tf` |
| `variable` | `infra/_variables.tf` |
| `output` | `infra/_outputs.tf` |
| `locals` | `infra/_locals.tf` |
| `data` | `infra/_data.tf` |

### 3. Resource Files

Group resources by **functional purpose**, not resource type. File names: lowercase, hyphen-separated, reflecting purpose.

Examples: `networking.tf` (VNet, subnets, NSGs, route tables), `dns.tf` (zones, records), `key-vault.tf` (KV + diagnostics).

- **Resource groups** go in their own file: `infra/resource-groups.tf`. Sole exception to "group by purpose".
- **RBAC** goes in its own file: `infra/rbac.tf`. Role assignments, role definitions, and related RBAC resources must not be mixed into functional resource files.
- No one-file-per-type (over-splitting). No catch-all dump file (under-splitting).
- Test: "would a reader expect these together?" If yes, same file.

### 4. Block Spacing

Exactly one blank line between top-level blocks. No missing separators. No double blank lines.

### 5. Dead Code

Grep before marking anything as used. Remove anything unused.

- **Variables**: every `variable` must be referenced as `var.<name>` in `.tf` files.
- **Outputs**: every `output` must be consumed externally (pipeline, script, parent module). Search entire repo (YAML, shell, JSON, HCL).
- **Data sources**: every `data` must be referenced as `data.<type>.<name>`.
- **Locals**: every `local.<name>` must be referenced. **Exception:** `resource_suffix_flat` is exempt (scaffolding per Rule 7).
- No commented-out blocks.

### 6. Version Pinning

**Terraform CLI** — pessimistic constraint in `terraform {}`:

```hcl
required_version = "~> 1.9.0"
```

**Providers** — `~>` at minor level. No `>=` (too loose). No `=` exact pins (blocks patches):

```hcl
azurerm = {
  source  = "hashicorp/azurerm"
  version = "~> 4.27"
}
```

Lock file (`terraform.lock.hcl`) must not be committed. Flag any Terraform lock file present in the repo and recommend removing it from version control.

### 7. Required Locals

`_locals.tf` must contain:

```hcl
locals {
  resource_suffix      = "${var.workload}-${var.environment}-${var.location_short}-${var.instance}"
  resource_suffix_flat = "${var.workload}${var.environment}${var.location_short}${var.instance}"

  tags = {
    managed-by = "<deployer>"   # e.g. "terraform", "github-actions", "azure-devops"
  }
}
```

Flag if any of these three missing or `tags` lacks `managed-by`.

### 8. Resource Naming

Every resource `name` must reference locals — no inline variable interpolation.

**Standard pattern:** `{type}-${local.resource_suffix}`
**With qualifier:** `{type}-{qualifier}-${local.resource_suffix}` (qualifier = short literal like `netw`, `dns`, `mgmt`)

#### Type Prefixes

Use the CAF resource abbreviations table as the authoritative source:
https://learn.microsoft.com/en-us/azure/cloud-adoption-framework/ready/azure-best-practices/resource-abbreviations

WebFetch that page, match the Azure resource type (e.g. `azurerm_storage_account` → "Storage account" → `st`), and use its Abbreviation column. If the resource isn't listed, infer a short prefix and flag for user confirmation.

#### Examples

| Resource | Expression | Resolved |
|----------|-----------|----------|
| Hub VNet | `"vnet-${local.resource_suffix}"` | `vnet-platform-prd-uks-01` |
| Networking RG | `"rg-netw-${local.resource_suffix}"` | `rg-netw-platform-prd-uks-01` |
| Subnet | `"snet-${each.key}-${local.resource_suffix}"` | `snet-default-platform-prd-uks-01` |
| Storage account | `"st${local.resource_suffix_flat}"` | `stplatformprduks01` |

#### Special Cases

- **Storage accounts & container registries** — use `resource_suffix_flat`. Storage accounts: verify ≤24 chars.
- **Management groups** — tenant-scoped singletons: `mg-{name}`. No env/region/index required.
- **Consumption budgets** — `"budget-${local.resource_suffix}"` or derived from subscription name.

#### Exempt from Naming

DNS zones, management group subscription associations, subnet/NSG/route table associations, routes, external provider resources.

#### Environment Tokens

`prd` = Production, `dvt` = Dev/Test, `dev` = Development, `uat` = UAT

#### Region Tokens

`uks` = UK South, `ukw` = UK West

### 9. Resource Tagging

Every taggable resource must have `tags = local.tags`. No inline tag maps. For extra tags use merge:

```hcl
tags = merge(local.tags, { purpose = "diagnostics" })
```

Flag: missing `tags` argument on taggable resource, or inline map instead of `local.tags`.

### 10. for_each Over count

Use `for_each` for multiples. `count` only for conditionals (`count = var.enabled ? 1 : 0`). Flag any non-conditional `count`.

### 11. Unsupplied Variables

Every `variable` without `default` must receive a value from: `.tfvars` files, pipeline `-var` flags, or `TF_VAR_` env vars. Flag unsupplied variables — they cause plan-time errors in CI.

Do **not** flag variables with `default` (even `default = null`).

These variables should normally have hardcoded defaults and do not need `.tfvars` values:

```hcl
variable "location" {
  default = "uksouth"
}

variable "location_short" {
  default = "uks"
}

variable "workload" {
  default = "PLACEHOLDER"
}

variable "instance" {
  default = "01"
}
```

### 12. tfvars Area Comment Blocks

Every `.tfvars` file must group assignments by the functional area they supply values to, and each non-empty group must be introduced by an area comment block.

Required format:

```hcl
#########################################
# PLACEHOLDER
#########################################
```

- Use the exact 41-character hash separator line shown above.
- Replace `PLACEHOLDER` with a short uppercase area name, e.g. `GLOBAL SETTINGS`, `NETWORKING`, `KEY VAULT`, `MONITORING`, `IDENTITY`, or `BUDGETS`.
- Add comment blocks only for areas that have values in that `.tfvars` file. Do not add empty area headers.
- Place each variable assignment under the comment block for the area it configures. If a file contains values for multiple areas, each area needs its own block.
- Keep exactly one blank line between the end of one area and the next comment block.
- Flag missing, malformed, lowercase, generic, duplicated, or unnecessary area comment blocks.

---

## Output

List each violation:

- **Rule:** number (1–12)
- **File:** path
- **Finding:** what's wrong
- **Fix:** what to do

Summary count per rule. Offer to auto-fix all. When fixing: move blocks, create missing files, delete empty files, fix spacing in all touched files.
