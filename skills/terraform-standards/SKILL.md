---
name: terraform-standards
description: House Terraform engineering standards covering repository layout, versions, variables, locals, modules, outputs, tfvars, state, and validation gates. Use when reviewing, refactoring, simplifying, or validating Terraform, planning a drift-safe remediation, or writing new Terraform that must follow these standards.
disable-model-invocation: true
---

# Terraform engineering standards

Apply these standards to Terraform repositories unless the repository documents an approved exception. Prioritise correctness, security, and simplicity, in that order.

## Workflow

1. Read the Terraform, modules, environment variable files, backend configuration, and deployment pipelines before reaching conclusions.
2. Identify concrete problems first, citing files and explaining their operational or maintenance cost.
3. Create a remediation plan that preserves infrastructure, resource addresses, and deployment behaviour.
4. When implementation is requested, establish a real plan baseline before refactoring whenever backend access is available and authorised.
5. Make the smallest coherent changes that remove duplication, indirection, and unused code.
6. Format and validate every environment input.
7. Run a refreshed plan against the real target state. Account explicitly for every remaining change; do not describe a refactor as complete when unexplained infrastructure changes remain.

Do not initialise or access a remote backend during a read-only review unless the user authorises a full state-backed evaluation. Never force-unlock state without confirming that the owning process is no longer active.

## Core principles

1. Every declaration must have a current consumer.
2. Describe each item of configuration once.
3. Make invalid input fail early and clearly.
4. Do not change infrastructure unintentionally during refactoring.
5. Keep Terraform understandable without tracing defensive fallback chains.

Treat every line as a maintenance liability. Add a variable, local, module, output, lifecycle rule, mapping, or abstraction only when it removes more risk or repetition than it introduces.

## Repository layout

Use a small, predictable structure:

```text
infra/
  _terraform.tf
  _providers.tf
  _variables.tf
  _locals.tf
  main.tf
  vars/
    _globals.tfvars
    dev.tfvars
    prd.tfvars
modules/
  <capability>/
    _terraform.tf
    _variables.tf
    main.tf
    _outputs.tf
```

Split files by functional concern only when a file becomes difficult to navigate. Do not create one file, local, or module per resource by default.

## Terraform and provider versions

- Constrain the Terraform CLI version explicitly.
- Constrain every provider source and version.
- Commit `.terraform.lock.hcl` for root modules.
- Use the same Terraform version locally and in CI.
- Upgrade versions deliberately and review the resulting plan.
- Let reusable child modules declare compatible version ranges; let root modules and the lock file select the deployed version.

## Variables and inputs

- Give every variable a specific type and useful description.
- Do not use `any` or `map(any)`.
- Give required values no default.
- Define an optional value's default once, at the input boundary.
- Do not repeat the same default in a resource expression, local, variable declaration, and tfvars.
- Add validation when Terraform's type system cannot express an operational constraint.
- Migrate callers and remove compatibility aliases instead of retaining them indefinitely.

Prefer:

```hcl
variable "applications" {
  description = "Applications keyed by application name."
  type = map(object({
    app_settings = optional(map(string), {})
    enabled      = optional(bool, true)
  }))
}
```

Avoid:

```hcl
variable "applications" {
  type    = any
  default = {}
}
```

## Relationships and derived configuration

Declare a relationship at its natural owner and derive downstream values from it.

Do not require an application to appear independently in:

- an application definition;
- an Application Insights mapping;
- a managed identity mapping;
- a storage mapping;
- multiple RBAC assignment maps.

Use the canonical application definition, direct resource references, or a deterministic naming rule to derive those relationships in the root module. Preserve derived resource keys because `for_each` keys form part of Terraform state addresses.

Require explicit input only when a relationship genuinely varies. Do not expose input for a value that the implementation ignores or always hardcodes.

## Locals

Use locals for:

- deterministic names;
- shared constants;
- normalising concise external input into a module contract;
- deriving relationships from one canonical definition;
- settings shared across environments.

Do not use a local merely to rename a value once. Avoid chains where one local exists only to feed another without reducing complexity.

Keep environment differences in tfvars. Keep invariant topology and shared settings in Terraform.

## Expressions

Use direct attribute access by default.

Use `try` only when failure is an expected data condition that cannot be represented by an optional typed attribute. Never use it to conceal a schema mismatch.

Use `lookup` only for genuinely dynamic maps. Do not use it for typed object attributes.

Use `coalesce` only when multiple nullable values are intentionally supported. Do not use aliases plus `coalesce` as a permanent compatibility layer.

Use a dynamic block only when the provider block itself is optional or repeatable. Do not use dynamic blocks for ordinary attributes.

## Modules

Make each module represent a cohesive capability with a clear contract.

- Keep resources together when they change for the same reason.
- Do not create wrapper modules that only rename arguments.
- Do not pass values the module does not consume.
- Do not declare fields the resource does not implement.
- Prefer typed objects over parallel maps.
- Keep business constants in the module when callers cannot vary them.
- Keep environment policy at the root when it legitimately varies by environment.
- Avoid extracting a one-use expression when the extra indirection makes the code harder to follow.

## Outputs

- Require every output to have a consumer or form part of an intentional public module contract.
- Give every output a description.
- Return the smallest useful value.
- Do not output complete provider resource objects.
- Mark sensitive outputs explicitly.
- Remove debug outputs before merging.

## Resource addressing

- Prefer `for_each` for named instances.
- Use stable, meaningful keys.
- Do not change a key solely to shorten it.
- Use `moved` blocks or an approved state migration when an address must change.
- Never accept deletion and recreation as a side effect of a readability refactor.

## Environment variable files

Make tfvars describe differences, not repeat the architecture.

Include only:

- environment identifiers;
- values that genuinely differ by environment;
- application settings owned by that environment;
- approved exceptions to shared defaults.

Do not include:

- generated Azure names;
- relationship maps Terraform can derive;
- values equal to an optional attribute's default;
- resource inventories identical in every environment;
- shared settings repeated across all environments;
- IDs available from another managed resource;
- secrets.

If a setting is identical everywhere, define it once. If it follows a reliable environment-based pattern, derive it. If it genuinely differs, keep it explicit in the environment file.

Do not split a complex variable across multiple variable files. Later files replace the complete value rather than merging it. Split by separate top-level variables or normalise concise inputs in locals.

## Dependencies

Let resource and module references create dependencies automatically.

Use `depends_on` only for a real dependency that cannot be expressed through an argument. Document why the dependency is otherwise invisible.

## Lifecycle rules and drift

Assume Terraform manages every configured attribute unless ownership is explicitly delegated.

- Identify the external owner and reason beside every `ignore_changes` entry.
- Do not ignore an entire nested block when only one attribute is externally managed.
- Do not use lifecycle rules to hide an unexplained plan.
- Review lifecycle exceptions periodically and remove obsolete entries.

## State and backend

- Use a remote backend with encryption, access control, locking, soft delete, and recovery controls.
- Separate state by environment or deployment boundary.
- Treat state and saved plans as sensitive data.
- Do not commit state, plans, crash logs, or `.terraform/`.
- Grant pipelines only the data-plane and Azure permissions required for their environment.
- Never force-unlock state without confirming the owning process is no longer active.

## Secrets

- Do not commit secrets in Terraform or variable files.
- Use managed identity, Key Vault, and protected pipeline variables.
- Avoid storage keys and connection strings when identity-based authentication is supported.
- Remember that sensitive values can still be stored in Terraform state.

## Validation pipeline

Run these checks for pull requests where the repository supports them:

```text
terraform fmt -check -recursive
terraform init -backend=false -input=false
terraform validate
tflint --recursive
checkov
```

Verify lint configuration paths explicitly. Require an owner and rationale for disabled rules and skipped checks.

Make deployment pipelines:

1. initialise the intended remote backend;
2. pass variable files in a documented order;
3. create and publish a saved plan;
4. expose add, change, replace, and destroy counts;
5. require the appropriate environment approval;
6. apply the exact saved plan artifact;
7. prevent concurrent applies to the same state.

## Completion criteria

Do not call a Terraform remediation complete until:

- formatting and validation pass;
- every supported environment input evaluates against the declared types;
- static-analysis failures are fixed or narrowly justified;
- a real target-state plan has been evaluated when access is available and authorised;
- every planned infrastructure change is intentional and reported;
- no declaration, fallback, mapping, or comment remains without a current purpose.
