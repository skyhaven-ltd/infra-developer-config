---
name: create-blog-post
description: Create and validate CVEngine portfolio blog posts in docs/blog with deterministic helper support for front matter, slug generation, draft/published status, build script execution, and generated frontend post validation. Use when Liam asks to write, add, publish, draft, prepare, or validate blog posts for the Sky Haven CVEngine portfolio site.
disable-model-invocation: true
---

# Create Blog Post

Use this skill for CVEngine portfolio blog posts. Use the bundled Python helper for deterministic inspection, plan validation, file creation, and build execution. Use the LLM for judgement: post angle, final prose, title quality, summary, tags, and whether the content is ready to publish.

## Writing standard

Write posts as concrete write-ups about Liam's work, findings, and decisions. Avoid generic internal monologue. The reader should understand what was built or changed, where it lives, what was learned, and why the decision matters.

Before drafting, gather enough repository context to anchor the post:

- Name and link the relevant repository when one is provided or can be inferred.
- Mention concrete files, directories, scripts, workflows, commands, or Azure resources when they are relevant.
- Prefer "what I found", "what changed", and "why I changed it" over vague reflections about the process.
- Use examples from the actual implementation instead of abstract claims.
- Keep Liam's direct, practical voice: plain English, specific details, light opinion where earned, no inflated significance.
- Do not invent facts. If a detail is not visible from the repo or user context, either omit it or phrase it as a decision still to confirm.

A strong technical post usually has this shape:

1. The problem or irritation that started the work.
2. The specific repo/component where the work happened.
3. Concrete implementation details and examples.
4. The finding or trade-off that emerged.
5. What Liam would do next, repeat, or avoid.

When polishing an existing draft, preserve the topic and useful lines, but rewrite paragraphs that feel like private reasoning into reader-facing findings.

## Workflow

1. Inspect the repo:

   ```powershell
   python "<skill-dir>\scripts\create-blog-post-helper.py" inspect --target "<repo>" --json
   ```

   Check `ok`, `missing_paths`, `posts`, and `issues`. Stop if required repo paths are missing.

2. Decide the post content and metadata:
   - `title`: clear reader-facing title.
   - `description`: one concise sentence for cards, SEO, and email notifications. Prefer a concrete finding over a generic "why I..." summary.
   - `date`: publish date as `YYYY-MM-DD`; use today's date unless the user gives another date.
   - `tags`: 1-5 short tags.
   - `status`: `published` only when the user asked to publish; otherwise use `draft`.
   - `body_markdown`: meaningful Markdown body grounded in the repository, implementation, or evidence behind the post. Do not include the H1 title; the builder renders the title from front matter.
   - Avoid em dashes in all metadata and body copy. Use commas, colons, parentheses, or hyphens instead. The helper rejects literal and HTML-encoded em dash references.

3. Create a plan JSON outside the target repo, or generate one from arguments:

   ```powershell
   python "<skill-dir>\scripts\create-blog-post-helper.py" plan `
     --target "<repo>" `
     --title "Post title" `
     --description "Short description" `
     --tags "Azure,DevSecOps" `
     --status draft `
     --body-file "<body.md>" `
     --out "<plan.json>"
   ```

   Plan shape:

   ```json
   {
     "title": "Post title",
     "description": "Short description",
     "date": "2026-05-17",
     "tags": ["Azure", "DevSecOps"],
     "status": "draft",
     "slug": "post-title",
     "body_markdown": "..."
   }
   ```

4. Apply the plan:

   ```powershell
   python "<skill-dir>\scripts\create-blog-post-helper.py" apply --target "<repo>" --plan "<plan.json>" --build --json
   ```

   Use `--dry-run` first when replacing or publishing an important post. The helper refuses to overwrite an existing post unless `--force` is passed.

5. Review the result:
   - Read `written_path` and `generated_path` from JSON.
   - If `build_ran` is true, check `build_returncode` and `build_stdout`.
   - Summarise the created slug, status, and next steps.

## Safety notes

- The helper only writes under `docs/blog/` in the target repo and only runs the repo's `scripts/build_blog.py` when `--build` is provided.
- Keep notification sending separate; this skill creates/builds posts but does not trigger subscriber emails.
- If publishing, remind the user that the SWA workflow sends notifications only according to the repository workflow inputs/settings.
