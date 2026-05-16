---
name: format-terraform
description: Enforce Terraform file structure, tfvars area comment blocks, naming, tagging, pinning, and formatting standards — objective pass/fail checks
---

Use the bundled Python helper for deterministic Terraform checks. Use the LLM only for judgement that is not safely scriptable: nuanced functional grouping, CAF exceptions, externally supplied variables, provider-specific taggability false positives, and safe auto-fix planning.

1. Inspect the repository:

   ```powershell
   python "<skill-dir>\scripts\format-terraform-helper.py" inspect --target "." --json
   ```

   If `infra/.terraform.lock.hcl` is missing and the user agrees to generation, use:

   ```powershell
   python "<skill-dir>\scripts\format-terraform-helper.py" inspect --target "." --json --ensure-lock
   ```

   `--ensure-lock` is idempotent and runs `terraform -chdir=infra init -backend=false -input=false`; this avoids initializing the configured backend but may still contact provider or module registries.

2. Report every item in `findings` with rule, file, line, severity, finding, and fix. Treat the helper as authoritative for deterministic checks.
3. Offer to auto-fix safe mechanical issues only after reporting. Do not move/delete files or rewrite Terraform without explicit approval.
4. Before applying fixes, explain the plan and validate with `terraform fmt` and, where available, `terraform validate` after edits.

## Hard standards to enforce

- `.tf` under `infra/`; `.tfvars` under `infra/vars/`.
- Core block files are required only when the repository contains the corresponding block type: `_terraform.tf` for `terraform`, `_providers.tf` for `provider`, `_variables.tf` for `variable`, `_outputs.tf` for `output`, `_locals.tf` for `locals`, and `_data.tf` for `data`.
- Group resources by functional purpose; `resource-groups.tf` and `rbac.tf` are dedicated files.
- Exactly one blank line between top-level blocks.
- No unused variables, outputs, data sources, locals, or commented-out blocks.
- Terraform CLI `~> 1.9.0`; provider versions use minor-level `~>` constraints. Commit `infra/.terraform.lock.hcl`; when missing, generate it with `terraform -chdir=infra init -backend=false -input=false`.
- Required locals: `resource_suffix`, `resource_suffix_flat`, and `tags.managed-by`.
- Resource names use Microsoft Cloud Adoption Framework abbreviations and locals; storage and ACR use `resource_suffix_flat`.
- Taggable resources use `tags = local.tags` or `merge(local.tags, ...)`.
- Prefer `for_each`; `count` only for conditional toggles.
- Variables without defaults must be supplied by tfvars, pipeline `-var`, or `TF_VAR_`.
- `.tfvars` assignments must be grouped under exact 41-hash uppercase area headers.
- Do not commit secrets in `.tfvars`; supply secret values through secure pipeline variables, `TF_VAR_`, Key Vault, or equivalent.

## HashiCorp-aligned standards to enforce

- Variables and outputs have descriptions.
- Variables have explicit type constraints.
- Terraform, providers, and modules are explicitly version constrained where applicable.
- Terraform cache, state, plan, and crash files are ignored by repository or global git ignore rules.
