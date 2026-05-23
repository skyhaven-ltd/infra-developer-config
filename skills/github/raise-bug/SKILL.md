---
name: raise-bug
description: Raise a bug report issue on a GitHub repository using the standard bug template
---

Use the bundled Python helper for deterministic repository detection, shared issue template loading, issue creation, and Project V2 Type updates. Use the LLM only for judgement: understanding the bug, expanding terse details into meaningful template prose, and confirming the exact issue before creation.

1. Inspect repository and tooling:

   ```powershell
   python "<skill-dir>\scripts\raise-bug-helper.py" inspect --target "." --json
   ```

2. Resolve `risk_flags`. Use `inferred_repository` if correct; otherwise ask for `owner/repo`. The helper intentionally defaults `label` to `use-type-field-instead` rather than inheriting semantic labels from the shared issue template.

3. Gather enough detail for title, description, steps to reproduce, and expected behavior. Only use the shared bug template at `.github/.github/ISSUE_TEMPLATE/bug-report.md`; do not invent or use embedded issue templates. Show the full title and body, then wait for explicit approval.

4. Create a plan outside the repo:

   ```json
   {
     "repository": "owner/repo",
     "title": "Short bug title",
     "description": "What is happening.",
     "steps": "1. Do this\n2. See that",
     "expected": "What should happen instead.",
     "approved": true
   }
   ```

   Optional plan fields are `label` and `assignee`; defaults are `use-type-field-instead` and `liam-goodchild`. Only override `label` for exceptional repositories; normal classification belongs in the GitHub Project Type field.

5. Dry-run, then create:

   ```powershell
   python "<skill-dir>\scripts\raise-bug-helper.py" apply --target "." --plan "$env:TEMP\bug-plan.json" --dry-run
   python "<skill-dir>\scripts\raise-bug-helper.py" apply --target "." --plan "$env:TEMP\bug-plan.json"
   ```

6. Report `created_issue_url`.
