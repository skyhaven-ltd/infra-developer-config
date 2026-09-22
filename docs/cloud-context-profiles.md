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
You can copy the executable elsewhere. Profiles and credentials remain under
`~/.config/cloud-context`, or the directory set by `CLOUD_CONTEXT_HOME`.
Use `-Runtime win-arm64` when building for Windows on ARM.

1. Click **New environment**, enter a profile name and directory (tenant) ID.
2. Enter a subscription ID for Azure resources, a Dataverse environment URL,
   or both. GitHub configuration is not required. For Dataverse-only access,
   the subscription can be blank.
3. Click **Connect**. The app checks the cached session first, then opens the
   native Microsoft sign-in flow if needed. **Sign in again** forces login;
   **Use device-code sign-in** displays the code in the app's output area.
4. After a tenant-only login, **Load subscriptions** lists cached subscriptions
   in that tenant. Choose an ID, save, and connect to select it.
5. Use **Copy Codex instructions** for commands using the installed
   `cloud-profile` launcher, or **Open PowerShell** for a new shell with the
   chosen Azure cache and `DATAVERSE_URL` already configured.

Existing terminals retain their context. The app does not change their process
environment or overwrite the default Azure CLI cache. Editing a saved profile
preserves its GitHub and other metadata. The GUI supports the Azure public
cloud and Dataverse through `az rest`; it does not configure `pac` authentication.

The app verifies Azure tenant/subscription identity and token acquisition.
For Dataverse it also makes a read-only `WhoAmI` request to verify environment
access. An Azure token check alone does not prove resource-level RBAC access.

**Check access / expiry** displays the selected resource's access-token expiry
in local time and a live countdown. It also shows the exact Azure CLI cache
directory and lists token/MSAL cache files found there, without reading or
displaying their contents. Windows broker authentication may additionally use
the Windows-managed account store.

An access-token countdown is not a countdown to the next login: Azure CLI can
silently renew access tokens using its cached session. Checking expiry may
renew a token. The longer session's remaining lifetime is not exposed reliably;
MFA, revocation and tenant policies can require another sign-in. The countdown
is a snapshot and is refreshed by connecting or checking access. Azure CLI
2.54 or newer is required for the `expires_on` timestamp.

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
