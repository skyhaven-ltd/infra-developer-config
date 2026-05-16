---
name: review-pull-request
description: Review an open pull request for code quality, security, and IaC best practices
---

Use the bundled Python helper for deterministic PR argument parsing and repository detection. Use the LLM only for judgement: reading the diff, deciding what matters, and writing actionable review findings.

1. Inspect the target repo and optional PR argument:

   ```powershell
   python "<skill-dir>\scripts\review-pull-request-helper.py" inspect --target "." --pr "<number-or-url>" --json
   ```

2. Resolve `risk_flags`. If `pr_number_unknown`, ask for a PR number or URL unless the current branch clearly has one.
3. Fetch the PR diff with git or the platform CLI. If the diff is over `large_diff_threshold_lines`, ask whether to review all files, code files only, or specific areas.
4. Review for scope, correctness, security, IaC risk, and testing. Skip nitpicks.
5. Output:

   ```markdown
   ## PR Review: #<number> - <title>

   ### Must Fix

   - **file:line** Issue -> suggested fix

   ### Should Fix

   - **file:line** Issue -> suggested fix

   ### Looks Good

   - Brief note.
   ```

6. Only post a PR comment if the user asks.
