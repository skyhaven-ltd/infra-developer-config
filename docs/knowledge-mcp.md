# Knowledge MCP

Durable, cross-machine, cross-agent memory for Claude Code and Codex. The
server lives in `infra-homelab-config/services/knowledge-mcp` and runs in the
homelab at `https://knowledge.lab.skyhaven.ltd/mcp`.

## Architecture

Two knowledge layers with distinct roles:

| Layer          | Store                          | Contents                                                    | Reader |
| -------------- | ------------------------------ | ----------------------------------------------------------- | ------ |
| Agent memory   | knowledge MCP (SQLite + FTS5)  | Compact structured records: decisions, lessons, conventions, environment facts, runbooks | Agents, via bounded `memory_recall` |
| Human notes    | Obsidian vault                 | Prose notes, journal, learning material                     | Liam; agents on demand only |

Agents never use the vault as working memory and never bulk-read it. Knowledge
flows from the MCP store into the vault through the `distill-knowledge` skill,
which batches promotion and enforces vault conventions via `write-vault-note`.

Retrieval cost is bounded by design: `memory_recall` caps results and
characters, so context usage stays flat no matter how large the store grows.

## Machine setup

Run once per machine (the token comes from the homelab `knowledge-mcp-env`
SealedSecret):

```powershell
.\scripts\Install-DeveloperConfig.ps1 -KnowledgeMcpToken "<token>"
```

This:

- persists the token as the `KNOWLEDGE_MCP_TOKEN` user environment variable
  (never written to any configuration file),
- copies `tools\knowledge-mcp\knowledge-mcp-headers.cmd` to `~\.local\bin` and
  registers the server at user scope in `~\.claude.json` and any
  `~\.claude-work\.claude.json` / `~\.claude-personal\.claude.json` profile
  files present, with a `headersHelper` that emits the Authorization header
  from the environment,
- merges the `[mcp_servers.knowledge]` section into `~\.codex\config.toml`
  (Codex reads the token via `bearer_token_env_var`),
- installs the `Stop` hook that reminds Claude once per session to store
  durable knowledge before finishing.

Verify:

```powershell
Invoke-RestMethod https://knowledge.lab.skyhaven.ltd/health
```

Then run `/mcp` inside Claude Code and confirm the `knowledge` server is
connected. Restart terminals after the first install so the new environment
variable is visible.

## Scope convention

Scopes are exact strings shared by every agent on every machine:

| Scope                | Contents                                                  |
| -------------------- | --------------------------------------------------------- |
| `global`             | Cross-repository conventions, workflow, and tooling facts |
| `repo:<name>`        | Facts specific to one repository; `<name>` is the repository directory name verbatim, e.g. `repo:infra-homelab-config` |
| `machine:<hostname>` | Machine-local environment facts; `<hostname>` is the `hostname` output verbatim, e.g. `machine:WNWSLAB01` |

## Capture and recall model

- **Recall** happens at the start of any non-trivial task, scoped to the
  current repository plus `global`. Enforced by `system/SYSTEM.md` and the
  server's own instructions.
- **Capture** happens at the end of a session that produced durable,
  non-obvious, reusable knowledge. The Claude `Stop` hook
  (`claude/hooks/knowledge-capture-stop.ps1`) injects a one-time reminder per
  session; Codex relies on the shared instructions alone.
- **Correction**: memories proven wrong are marked `stale` or `superseded`
  with evidence via `memory_mark`; the store retains history.
- Deduplication, idempotency keys, and similarity conflicts are handled
  server-side, so an over-eager capture is at worst a no-op.

## Growth control

- Bounded recall keeps per-session cost flat.
- `expires_at` and `memory_mark` remove stale records from recall without
  losing history.
- The `distill-knowledge` skill periodically promotes high-value memories into
  the Obsidian vault and reports on store health; run it roughly monthly or
  after large pieces of work.

## Troubleshooting

| Symptom | Check |
| ------- | ----- |
| `knowledge` server missing in `/mcp` | Re-run the installer; inspect the `mcpServers.knowledge` entry in `~\.claude.json` |
| 401 from the server | `KNOWLEDGE_MCP_TOKEN` unset in this shell (restart the terminal) or token rotated in the SealedSecret |
| Codex cannot see the server | Confirm `[mcp_servers.knowledge]` exists in `~\.codex\config.toml` after the installer merge |
| Health endpoint unreachable | Homelab ingress or Argo CD deployment issue; see `infra-homelab-config/kubernetes/apps/knowledge-mcp` |
