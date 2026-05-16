---
name: config-repo-ado
description: Configure an Azure DevOps repository — default branch, branch policies, Advanced Security, rename, and README generation. Can create the repo from scratch.
---

Use the bundled Python helper for deterministic Azure DevOps repository detection, prerequisite checks, and repeatable `az` operations. Use the LLM only for judgement: confirming org/project choices, deciding optional policies, naming, README content, and explaining licence or permission failures.

## Workflow

1. Inspect the target repository:

   ```powershell
   python "<skill-dir>\scripts\config-repo-ado-helper.py" inspect --target "." --json
   ```

2. Review `risk_flags`. Stop and resolve `az_not_found`, `az_not_authenticated`, `azure_devops_extension_missing`, or `repository_not_inferred`. If there is no remote, ask for org, project, and repo name before planning creation/configuration.

3. Apply configuration only from an explicit approved plan JSON outside the repo:

   ```json
   {
     "org": "CloudAandE",
     "project": "Project Name",
     "repo": "repo-name",
     "rename_to": null,
     "enable_advanced_security": true,
     "approved": true
   }
   ```

4. Dry-run before side effects, then apply after confirmation:

   ```powershell
   python "<skill-dir>\scripts\config-repo-ado-helper.py" apply --target "." --plan "$env:TEMP\config-repo-ado.json" --dry-run
   python "<skill-dir>\scripts\config-repo-ado-helper.py" apply --target "." --plan "$env:TEMP\config-repo-ado.json"
   ```

5. Report command results and any permission/licence failures. Run `/generate-readme` only once code is ready.
