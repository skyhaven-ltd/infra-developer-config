---
name: format-terraform
description: Enforce Terraform file structure, tfvars area comment blocks, naming, tagging, pinning, and formatting standards — objective pass/fail checks
---

Use the bundled Python helper for deterministic Terraform checks. Use the LLM only for judgement: functional resource grouping, CAF abbreviation confirmation, and safe auto-fix planning.

1. Inspect the repository:

   ```powershell
   python "<skill-dir>\scripts\format-terraform-helper.py" inspect --target "." --json
   ```

2. Report every item in `findings` with rule, file, line, finding, and fix. Also apply the remaining manual rules from this skill's standards: functional resource grouping, required locals, resource naming, tagging, provider/version pinning, unsupplied variables, and tfvars area blocks.
3. Offer to auto-fix safe mechanical issues only after reporting. Do not move/delete files or rewrite Terraform without explicit approval.
4. Before applying fixes, explain the plan and validate with `terraform fmt` and, where available, `terraform validate` after edits.

## Hard standards to enforce

- `.tf` under `infra/`; `.tfvars` under `infra/vars/`.
- Block files: `_terraform.tf`, `_providers.tf`, `_variables.tf`, `_outputs.tf`, `_locals.tf`, `_data.tf`.
- Group resources by functional purpose; `resource-groups.tf` and `rbac.tf` are dedicated files.
- Exactly one blank line between top-level blocks.
- No unused variables, outputs, data sources, locals, or commented-out blocks.
- Terraform CLI `~> 1.9.0`; provider versions use minor-level `~>` constraints. Do not commit `terraform.lock.hcl`.
- Required locals: `resource_suffix`, `resource_suffix_flat`, and `tags.managed-by`.
- Resource names use CAF prefixes and locals; storage and ACR use `resource_suffix_flat`.
- Taggable resources use `tags = local.tags` or `merge(local.tags, ...)`.
- Prefer `for_each`; `count` only for conditional toggles.
- Variables without defaults must be supplied by tfvars, pipeline `-var`, or `TF_VAR_`.
- `.tfvars` assignments must be grouped under exact 41-hash uppercase area headers.
