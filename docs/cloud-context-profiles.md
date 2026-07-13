# Cloud context profiles

Cloud context profiles switch Azure CLI and GitHub CLI together. Each profile
uses separate native CLI configuration directories, preventing one tenant or
GitHub account from silently affecting another profile. Profile metadata does
not contain passwords, tokens, or client secrets.

## Install

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
