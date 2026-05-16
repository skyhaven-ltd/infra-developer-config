---
name: generate-readme
description: Generate a brief project README from repo code
---

Use the bundled Python helper for deterministic repository inventory. Use the LLM only for judgement: understanding what the project does and writing concise factual prose.

1. Inspect the repository:

   ```powershell
   python "<skill-dir>\scripts\generate-readme-helper.py" inspect --target "." --json
   ```

2. Read the important files from `important_files` plus any obvious entry points.
3. Write `README.md` directly, without preview or confirmation.
4. Format:

   ```markdown
   # repo-name

   2-3 sentences on what it does.
   ```

Omit setup, prerequisites, tech stack, Terraform details, directory trees, resource inventories, TF docs blocks, and badges.
