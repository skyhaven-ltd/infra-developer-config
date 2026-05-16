---
name: review-terraform
description: Review Terraform code and its CI/CD pipeline with a minimalist lens — every line is a liability
---

Use the bundled Python helper for deterministic Terraform and pipeline signal scanning. Use the LLM only for judgement: deciding whether a signal is a real finding, assessing trade-offs, and writing concrete recommendations.

1. Inspect the repository:

   ```powershell
   python "<skill-dir>\scripts\review-terraform-helper.py" inspect --target "." --json
   ```

2. Use `signals` as a starting point, not as final findings. Read the relevant files before reporting.
3. Review with the principle: every line is a liability. Flag complexity, indirection, and maintenance burden that does not justify itself.
4. Cover: minimalism, variables, state, outputs, security, resource design, modules, and Terraform CI/CD.
5. For objective formatting/naming failures, run `/format-terraform` separately.
6. Output:

   ```markdown
   ## Findings

   - **Area:** ...
     **Severity:** High / Medium / Low / Suggestion
     **File & line:** ...
     **Finding:** ...
     **Recommendation:** ...

   ## Prioritised Improvements

   | Priority | Finding | Effort | Impact |
   | -------- | ------- | ------ | ------ |
   ```
