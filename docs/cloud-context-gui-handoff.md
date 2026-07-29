# Cloud Context GUI handoff

## Purpose

Continue the iterative development and user testing of the standard-user
Windows GUI for `tools/cloud-context`. The user is actively exercising the
application and reporting authentication and layout issues, so preserve the
short feedback loop: implement a focused fix, add a regression test, publish,
and relaunch the portable executable.

Do not copy account names, usernames, tenant IDs, subscription IDs, workspace
IDs, or environment URLs from local profile data or screenshots into source,
tests, commits, or remote messages. Tests use synthetic identifiers only.

## Repository state

- Repository: `infra-developer-config`
- Branch: `minor/cloud-context-gui-mvp`
- HEAD: `5eb8de4` (`Adding MVP`), also present on
  `origin/minor/cloud-context-gui-mvp`
- The refinements described below are uncommitted working-tree changes on top
  of that commit. Preserve them.
- This handoff document and the update to `skills/tools/handoff/SKILL.md` are
  also uncommitted changes. The skill now writes `HANDOFF.md` at the current
  repository root by default, while still respecting an explicit user path.
- Inspect the exact current scope with `git status --short --branch` and
  `git diff`; do not infer it from this document.
- The generated package and launch directory are ignored beneath
  `artifacts/cloud-context/`.

The main design and usage documentation is
[`docs/cloud-context-profiles.md`](cloud-context-profiles.md). Refer to the code
and diff for implementation detail rather than duplicating them here.

## Implemented refinements after the MVP commit

- Connections are first-class metadata beneath an identity. The main screen can
  add Azure, GitHub, Azure DevOps, Dataverse, and Log Analytics targets and can
  remove an individual selected target without deleting native credential
  caches.
- The profile editor shows only connection types already configured for that
  profile. New connection types are added from the main screen.
- The sidebar Add/Edit/Remove controls use equal-width cells so Remove is no
  longer clipped.
- Azure and GitHub CLI directories remain isolated per profile. Known ambient
  Azure/GitHub environment variables are removed before applying a child
  profile.
- Windows `.cmd`/`.bat` CLI shims are launched through `%ComSpec% /d /c call`.
  This fixes Azure CLI paths beneath `C:\Program Files\...`; a regression test
  deliberately uses a path containing spaces.
- Profiles have an explicit active state backed by the existing
  `active-profile` file. GUI selection is navigation only. **Make active** sets
  the default restored by new PowerShell sessions, and if an Azure or Dataverse
  row is selected it also selects that native target.
- **Open scoped PowerShell** remains the safer option for frequently switching
  customer identities because it applies the selected profile only to that
  child process.
- Azure sign-in continues to use browser/MFA authentication. Azure CLI's
  `--username` option is a password flow and is not suitable for MFA. After
  successful sign-in, an empty profile username is populated from
  `az account show`; later validation rejects a different username.
- Validation results are cached per profile for the lifetime of the application
  so switching profiles does not reset the grid. Cache entries are invalidated
  by sign-in, profile edits, and connection changes. They are intentionally not
  persisted across application restarts.
- GitHub identity validation and organisation access are combined into one row
  per configured organisation. Profiles without an organisation fall back to a
  single host-level identity row.

## Important files

- `tools/cloud-context/gui/src/CloudContext.App/MainWindow.xaml`
- `tools/cloud-context/gui/src/CloudContext.App/MainWindow.xaml.cs`
- `tools/cloud-context/gui/src/CloudContext.App/ProfileEditorWindow.xaml`
- `tools/cloud-context/gui/src/CloudContext.App/ConnectionEditorWindow.xaml`
- `tools/cloud-context/gui/src/CloudContext.Core/CliOrchestrator.cs`
- `tools/cloud-context/gui/src/CloudContext.Core/ProfileStore.cs`
- `tools/cloud-context/gui/src/CloudContext.Core/ProfileConnections.cs`
- `tools/cloud-context/gui/tests/CloudContext.Core.Tests/ProfileStoreTests.cs`
- `scripts/Publish-CloudContext.ps1`
- `skills/tools/handoff/SKILL.md`

The new `ConnectionEditorWindow` and `ProfileConnections` files are currently
untracked and must not be omitted from a future commit.

## Verification state

The latest verification completed successfully:

```powershell
dotnet format tools/cloud-context/gui/CloudContext.Gui.slnx
dotnet test tools/cloud-context/gui/CloudContext.Gui.slnx
git diff --check
```

The .NET suite currently has 16 passing tests. It covers legacy migration,
profile isolation, safe profile names, versioned stores, Windows command shims
with spaced paths, add/remove connection behaviour, active-profile state,
Azure username validation, and the single-row GitHub result.

The earlier full MVP gate also passed the PowerShell and Python suites. If work
touches the shared module, launcher, or schema, rerun:

```powershell
Invoke-Pester .\tools\cloud-context\tests\CloudContext.Tests.ps1
python -m unittest discover -s tools/cloud-context/tests -p "test_*.py"
```

## Publish and relaunch loop

Publish with:

```powershell
.\scripts\Publish-CloudContext.ps1
```

This produces `artifacts/cloud-context/cloud-context-win-x64.zip`. The currently
launched copy is extracted beneath `artifacts/cloud-context/launch/`. Before
overwriting it, resolve that exact launch root and stop only `CloudContext`
processes whose executable path is inside it. Do not stop unrelated processes
by name alone. Extract the new ZIP with `Expand-Archive -Force`, launch
`CloudContext.exe`, wait briefly, and fail the check if it exits during startup.

At handoff creation time, a build from the current working tree was running from
that launch directory. Treat the process ID as ephemeral and discover it again
rather than relying on a recorded value.

## Known constraints and decisions

- The application is WPF on .NET 10 and publishes as a self-contained `win-x64`
  executable with an `asInvoker` manifest; it must remain usable without local
  administrator rights.
- Native CLI credentials remain owned by `az`, `gh`, and `pac`. Do not introduce
  an application token store or display bearer tokens.
- `profiles.json` contains identifiers only and uses schema version 2. The
  PowerShell module and Python launcher retain legacy compatibility.
- Power Platform CLI has its own named authentication profiles and one selected
  default. Cloud Context derives deterministic PAC profile names and selects a
  target when connecting, validating, or making a selected Dataverse row active.
- Cached UI validation state is evidence from the current app session, not a
  durable authentication guarantee.
- The application currently relies on installed `az`, `gh`, and `pac` commands;
  missing tools are reported as unavailable.

## Suggested next-session approach

1. Read the repository `AGENTS.md` and recall knowledge for
   `repo:infra-developer-config` and `global`.
2. Inspect the dirty worktree and this branch before editing.
3. Run the .NET test suite to establish the starting baseline.
4. Continue from the user's next observed behaviour; prefer a focused regression
   test before or alongside each fix.
5. Rebuild and relaunch after user-visible changes.
6. Do not commit, push, or create a PR unless the user asks for it.

## Suggested skills

- `test-driven-development`: use for the next reported defect or behaviour
  change so CLI and state-management regressions remain deterministic.
- `git-commit-push`: use only when the user asks to commit and push the current
  refinements.
- `create-pr`: use only when the user asks to open the pull request after the
  branch is ready.
