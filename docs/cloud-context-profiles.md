# Cloud context profiles

Cloud context profiles switch Azure CLI and GitHub CLI together. Each profile
uses separate native CLI configuration directories, preventing one tenant or
GitHub account from silently affecting another profile. Profile metadata does
not contain passwords, tokens, or client secrets.

## Install

### Windows GUI

Build the standalone executable with the .NET 10 SDK:

```powershell
.\tools\cloud-context\Build-CloudContext.ps1
```

Open `tools\cloud-context\dist\win-x64\CloudContext.exe`. This single file
includes the .NET runtime; Azure CLI must be installed and available on PATH.
After a build, `.\scripts\Install-DeveloperConfig.ps1` adds a **Cloud Context**
Start menu shortcut; right-click the running app's taskbar button to pin it.
Profiles and credentials stay under `~/.config/cloud-context`, or the directory
set by `CLOUD_CONTEXT_HOME`. Use `-Runtime win-arm64` when building for Windows on ARM.

1. Click **New profile**, then enter a profile name and tenant ID.
2. Add a subscription ID for Azure resources, a Dataverse environment URL, or
   both. For Dataverse-only access, leave the subscription blank.
3. Click **Sign in**. If the saved sign-in still works, nothing opens.
   Otherwise a new incognito Chrome window opens on the Microsoft sign-in page.
   **More > Sign in with a code** copies a device code to the clipboard and
   opens the code page in the same kind of window.
4. After signing in, the app lists the tenant's subscriptions in the
   **Subscription** box. Pick one and click **Save changes**.
5. **More** also has **Copy instructions for an agent**, for the installed
   `cloud-profile` launcher, and **Open PowerShell with this profile**, which
   opens a shell with the profile's Azure cache and `DATAVERSE_URL` set.

The dot next to each profile shows its last known state: green when signed in,
red when it needs a sign-in, grey when it hasn't been checked. The app saves
these results in `status.json`, so they're there when you switch profiles or
reopen the app. It re-checks every profile silently at startup and every
10 minutes. These checks only use saved tokens and never open a browser.
Drag the divider to widen the profile list; the app remembers the width.

Right-click a profile (or press Delete) to remove it. Removal deletes the
profile and its saved Azure and GitHub sign-ins in `~/.config/cloud-context/cli/`
after you confirm. **Sign out** clears the saved sign-in but keeps the profile.

Sign-ins from the GUI, `Connect-CloudProfile` and the `cloud-profile` launcher
turn off the Windows account broker (`AZURE_CORE_ENABLE_BROKER_ON_WINDOWS=false`),
whose dialog tends to open behind other windows. They point `BROWSER` and
`GH_BROWSER` at Chrome with `--incognito --new-window`. If Chrome isn't
installed, the default browser opens instead. Incognito windows share one
session while any of them is open, so close them all to start a clean sign-in.

Existing terminals keep their context. The app doesn't change their
environment or overwrite the default Azure CLI cache. Editing a saved profile
keeps its GitHub and other metadata. The GUI supports the Azure public cloud,
and Dataverse through `az rest`; it doesn't configure `pac` authentication.

A check verifies the Azure tenant and subscription and gets a token. For
Dataverse it also makes a read-only `WhoAmI` request. An Azure token check
alone doesn't prove resource-level RBAC access.

The status shows when the current access token expires. That isn't when you'll
next have to sign in: Azure CLI renews access tokens silently from the saved
session, and each check may renew one. Azure CLI doesn't reliably expose how
long the session itself lasts, and MFA, revocation or tenant policy can force
another sign-in. Azure CLI 2.54 or newer is required for the expiry time.

See Microsoft's [interactive Azure CLI authentication documentation](https://learn.microsoft.com/en-us/cli/azure/authenticate-azure-cli-interactively)
for broker, device-code and refresh-token behavior.

Run the GUI backend and launcher checks with:

```powershell
dotnet run --project tools/cloud-context/gui/tests/CloudContext.Tests.csproj
python -m unittest discover -s tools/cloud-context/tests -p test_*.py
```

### CLI and PowerShell integration

Run the developer-config installer and open a new PowerShell session:

```powershell
.\scripts\Install-DeveloperConfig.ps1
```

## Manage profiles

Create one profile for each Azure and GitHub working context:

```powershell
New-CloudProfile `
  -Name customer-prod `
  -AzureTenantId 00000000-0000-0000-0000-000000000000 `
  -AzureSubscriptionId 11111111-1111-1111-1111-111111111111 `
  -GitHubOrg customer-platform `
  -GitHubUser your-login

Use-CloudProfile customer-prod
Connect-CloudProfile
```

`Connect-CloudProfile` performs the native `az login` and `gh auth login` flows.
Their credentials remain in the CLI-owned stores beneath
`~/.config/cloud-context/cli/`; `profiles.json` contains identifiers only.

For GitHub Enterprise, set the host explicitly:

```powershell
New-CloudProfile `
  -Name enterprise-prod `
  -AzureTenantId 00000000-0000-0000-0000-000000000000 `
  -AzureSubscriptionId 11111111-1111-1111-1111-111111111111 `
  -GitHubHost github.example.com `
  -GitHubOrg enterprise-platform `
  -GitHubUser your-login
```

List profiles or inspect one profile's non-secret metadata:

```powershell
Get-CloudProfile
Get-CloudProfile customer-prod

cloud-profile --list
cloud-profile --show customer-prod
```

Replace a profile's metadata by supplying the complete profile with `-Force`:

```powershell
New-CloudProfile `
  -Name customer-prod `
  -AzureTenantId 00000000-0000-0000-0000-000000000000 `
  -AzureSubscriptionId 22222222-2222-2222-2222-222222222222 `
  -GitHubOrg customer-platform `
  -GitHubUser your-login `
  -Force
```

If the tenant, subscription, host, or user changed, reconnect the profile:

```powershell
Use-CloudProfile customer-prod
Connect-CloudProfile
```

Remove profile metadata with:

```powershell
Remove-CloudProfile customer-prod
```

Removal retains the profile's native CLI credential directories so it cannot
silently delete authentication data. Remove those directories separately only
after confirming they are no longer required.

## Daily use

```powershell
Get-CloudProfile
Use-CloudProfile customer-prod -Validate
Show-CloudContext

azp rest --method get --url "https://management.azure.com/subscriptions/$env:AZURE_SUBSCRIPTION_ID?api-version=2022-12-01"
ghp api "orgs/$env:GH_ORG/repos"
ghorg repos --paginate
```

`azp` and `ghp` validate the authenticated identity before forwarding arguments
to the native CLI. Direct `az` and `gh` commands still use the isolated active
profile, but do not perform the additional identity check.

`ghorg` calls an endpoint beneath `orgs/<active-org>/`, so `ghorg repos` is
equivalent to `gh api orgs/$env:GH_ORG/repos` without repeating the organisation.
Use `-Method POST`, `PATCH`, `PUT`, or `DELETE` when required.

## LLM agents and automation

Agent tool calls often start a clean process, so they must not rely on
`Use-CloudProfile` having run in an earlier command. Give the agent this
instruction:

> Use the `customer-prod` cloud profile. Prefix every Azure CLI and GitHub CLI
> command with `cloud-profile customer-prod --`. Do not invoke `az` or `gh`
> directly.

The resulting commands are explicit and independently reproducible:

```powershell
cloud-profile customer-prod -- az account show
cloud-profile customer-prod -- az rest --method get --url <url>
cloud-profile customer-prod -- gh api user
cloud-profile customer-prod -- ghorg repos --paginate
```

The launcher sets the profile environment only for the child command and
validates the expected Azure or GitHub identity first. It never changes the
human user's active profile. `ghorg` expands to the selected organisation's
API endpoint.

For a non-CLI command such as Terraform, validation defaults to both providers.
Narrow it explicitly when the command only needs Azure:

```powershell
cloud-profile --validate azure customer-prod -- terraform plan
```

Agents can discover the allowed names and inspect non-secret metadata with:

```powershell
cloud-profile --list
cloud-profile --show customer-prod
```

`--validate none` exists for initial diagnostics only; routine agent commands
should retain identity validation.

The last selected profile is restored when PowerShell starts. To keep a switch
limited to the current shell, use `Use-CloudProfile <name> -NoPersist`.
The prompt always displays `[cloud:<name>]` (or `[cloud:none]`) so the active
context remains visible after the selection output has scrolled away.

Set `CLOUD_CONTEXT_HOME` before importing the module to override the default
`~/.config/cloud-context` data location.
