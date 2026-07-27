Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$script:CloudProfilePromptEnabled = $false

function Get-CloudContextRoot {
    if ($env:CLOUD_CONTEXT_HOME) {
        return [System.IO.Path]::GetFullPath($env:CLOUD_CONTEXT_HOME)
    }

    return Join-Path $env:USERPROFILE ".config\cloud-context"
}

function Get-CloudProfileFile {
    return Join-Path (Get-CloudContextRoot) "profiles.json"
}

function Read-CloudProfileStore {
    $path = Get-CloudProfileFile
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        return [pscustomobject]@{ schemaVersion = 2; profiles = @() }
    }

    $store = Get-Content -LiteralPath $path -Raw | ConvertFrom-Json
    if (-not ($store.PSObject.Properties.Name -contains "profiles")) {
        throw "Cloud profile file '$path' must contain a 'profiles' array."
    }

    if (-not ($store.PSObject.Properties.Name -contains "schemaVersion")) {
        $migratedProfiles = foreach ($profile in @($store.profiles)) {
            [pscustomobject]@{
                name = $profile.name
                displayName = $profile.name
                identity = [pscustomobject]@{
                    username = ""
                    tenantId = $profile.azureTenantId
                }
                connections = [pscustomobject]@{
                    azure = if ($profile.azureSubscriptionId) {
                        [pscustomobject]@{ subscriptionIds = @($profile.azureSubscriptionId) }
                    } else { $null }
                    github = if ($profile.githubHost -or $profile.githubOrg) {
                        [pscustomobject]@{
                            host = if ($profile.githubHost) { $profile.githubHost } else { "github.com" }
                            user = $profile.githubUser
                            organisations = @($profile.githubOrg | Where-Object { $_ })
                        }
                    } else { $null }
                    azureDevOps = $null
                    dataverse = $null
                    logAnalytics = $null
                }
            }
        }
        return [pscustomobject]@{ schemaVersion = 2; profiles = @($migratedProfiles) }
    }
    if ($store.schemaVersion -ne 2) {
        throw "Unsupported cloud profile schema version '$($store.schemaVersion)'."
    }

    return $store
}

function Get-CloudProfileTenantId {
    param([Parameter(Mandatory = $true)]$Profile)
    if ($Profile.PSObject.Properties.Name -contains "identity") { return $Profile.identity.tenantId }
    return $Profile.azureTenantId
}

function Get-CloudProfileSubscriptionId {
    param([Parameter(Mandatory = $true)]$Profile)
    if ($Profile.PSObject.Properties.Name -contains "connections") {
        $subscriptions = @($Profile.connections.azure.subscriptionIds)
        if ($subscriptions.Count -gt 0) { return $subscriptions[0] }
        return $null
    }
    return $Profile.azureSubscriptionId
}

function Get-CloudProfileGitHub {
    param([Parameter(Mandatory = $true)]$Profile)
    if ($Profile.PSObject.Properties.Name -contains "connections") {
        if ($Profile.connections.github) { return $Profile.connections.github }
        return [pscustomobject]@{ host = ""; user = ""; organisations = @() }
    }
    return [pscustomobject]@{
        host = $Profile.githubHost
        user = $Profile.githubUser
        organisations = @($Profile.githubOrg)
    }
}

function Write-CloudProfileStore {
    param([Parameter(Mandatory = $true)]$Store)

    $path = Get-CloudProfileFile
    $directory = Split-Path -Parent $path
    New-Item -ItemType Directory -Path $directory -Force | Out-Null
    $temporaryPath = "$path.tmp"
    $Store | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $temporaryPath -Encoding UTF8
    Move-Item -LiteralPath $temporaryPath -Destination $path -Force
}

function Test-CloudProfileName {
    param([Parameter(Mandatory = $true)][string]$Name)

    if ($Name -notmatch "^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$") {
        throw "Profile names must start with a letter or number and contain only letters, numbers, '.', '_' or '-' (maximum 64 characters)."
    }
}

function Get-CloudProfile {
    [CmdletBinding()]
    param([string]$Name)

    $profiles = @((Read-CloudProfileStore).profiles)
    if ($Name) {
        $profile = $profiles | Where-Object { $_.name -eq $Name } | Select-Object -First 1
        if (-not $profile) {
            throw "Cloud profile '$Name' does not exist. Run Get-CloudProfile to list profiles."
        }
        return $profile
    }

    return $profiles | Sort-Object -Property name
}

function New-CloudProfile {
    [CmdletBinding(SupportsShouldProcess = $true)]
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][string]$AzureTenantId,
        [Parameter(Mandatory = $true)][string]$AzureSubscriptionId,
        [Parameter(Mandatory = $true)][string]$GitHubOrg,
        [Parameter(Mandatory = $true)][string]$GitHubUser,
        [string]$GitHubHost = "github.com",
        [switch]$Force
    )

    Test-CloudProfileName $Name
    $store = Read-CloudProfileStore
    $profiles = @($store.profiles)
    $existing = $profiles | Where-Object { $_.name -eq $Name } | Select-Object -First 1
    if ($existing -and -not $Force) {
        throw "Cloud profile '$Name' already exists. Use -Force to replace it."
    }

    $profile = [ordered]@{
        name = $Name
        displayName = $Name
        identity = [ordered]@{
            username = ""
            tenantId = $AzureTenantId
        }
        connections = [ordered]@{
            azure = [ordered]@{ subscriptionIds = @($AzureSubscriptionId) }
            github = [ordered]@{
                host = $GitHubHost
                user = $GitHubUser
                organisations = @($GitHubOrg)
            }
            azureDevOps = $null
            dataverse = $null
            logAnalytics = $null
        }
    }

    $remaining = @($profiles | Where-Object { $_.name -ne $Name })
    $updatedStore = [ordered]@{ schemaVersion = 2; profiles = @($remaining) + @([pscustomobject]$profile) }
    if ($PSCmdlet.ShouldProcess($Name, "Create cloud profile")) {
        Write-CloudProfileStore $updatedStore
    }

    return [pscustomobject]$profile
}

function Remove-CloudProfile {
    [CmdletBinding(SupportsShouldProcess = $true, ConfirmImpact = "High")]
    param([Parameter(Mandatory = $true)][string]$Name)

    $store = Read-CloudProfileStore
    $profiles = @($store.profiles)
    if (-not ($profiles | Where-Object { $_.name -eq $Name })) {
        throw "Cloud profile '$Name' does not exist."
    }

    if ($PSCmdlet.ShouldProcess($Name, "Remove cloud profile metadata (CLI credentials are retained)")) {
        Write-CloudProfileStore ([ordered]@{
            schemaVersion = 2
            profiles = @($profiles | Where-Object { $_.name -ne $Name })
        })
    }
}

function Set-CloudProfileEnvironment {
    param([Parameter(Mandatory = $true)]$Profile)

    $root = Get-CloudContextRoot
    $cliRoot = Join-Path $root "cli"
    $azureConfig = Join-Path (Join-Path $cliRoot "azure") $Profile.name
    $githubConfig = Join-Path (Join-Path $cliRoot "github") $Profile.name
    New-Item -ItemType Directory -Path $azureConfig -Force | Out-Null
    New-Item -ItemType Directory -Path $githubConfig -Force | Out-Null

    $env:CLOUD_PROFILE = $Profile.name
    $env:AZURE_CONFIG_DIR = $azureConfig
    $tenantId = Get-CloudProfileTenantId $Profile
    $subscriptionId = Get-CloudProfileSubscriptionId $Profile
    $github = Get-CloudProfileGitHub $Profile
    $env:AZURE_TENANT_ID = $tenantId
    $env:AZURE_SUBSCRIPTION_ID = $subscriptionId
    $env:ARM_TENANT_ID = $tenantId
    $env:ARM_SUBSCRIPTION_ID = $subscriptionId
    $env:GH_CONFIG_DIR = $githubConfig
    $env:GH_HOST = $github.host
    $githubOrganisations = @($github.organisations)
    $env:GH_ORG = if ($githubOrganisations.Count -gt 0) { $githubOrganisations[0] } else { $null }
}

function Use-CloudProfile {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true, Position = 0)][string]$Name,
        [switch]$NoPersist,
        [switch]$Validate,
        [switch]$Quiet
    )

    $profile = Get-CloudProfile -Name $Name
    Set-CloudProfileEnvironment $profile

    if (-not $NoPersist) {
        $activePath = Join-Path (Get-CloudContextRoot) "active-profile"
        Set-Content -LiteralPath $activePath -Value $Name -Encoding UTF8
    }

    if (-not $Quiet) {
        Write-Host "Active cloud profile: $Name" -ForegroundColor Cyan
        Show-CloudContext
    }
    if ($Validate) {
        Assert-CloudContext
    }
}

function Restore-CloudProfile {
    [CmdletBinding()]
    param()

    $activePath = Join-Path (Get-CloudContextRoot) "active-profile"
    if (-not (Test-Path -LiteralPath $activePath -PathType Leaf)) {
        return
    }

    $name = (Get-Content -LiteralPath $activePath -Raw).Trim()
    if ($name) {
        Use-CloudProfile -Name $name -NoPersist -Quiet
    }
}

function Enable-CloudProfilePrompt {
    [CmdletBinding()]
    param()

    if ($script:CloudProfilePromptEnabled) {
        return
    }

    $originalPrompt = (Get-Command prompt -CommandType Function).ScriptBlock
    $profilePrompt = {
        if ($env:CLOUD_PROFILE) {
            Write-Host "[cloud:$env:CLOUD_PROFILE] " -NoNewline -ForegroundColor Cyan
        } else {
            Write-Host "[cloud:none] " -NoNewline -ForegroundColor DarkGray
        }
        & $originalPrompt
    }.GetNewClosure()

    Set-Item -Path Function:\global:prompt -Value $profilePrompt
    $script:CloudProfilePromptEnabled = $true
}

function Show-CloudContext {
    [CmdletBinding()]
    param()

    if (-not $env:CLOUD_PROFILE) {
        Write-Warning "No cloud profile is active. Run Use-CloudProfile <name>."
        return
    }

    $profile = Get-CloudProfile -Name $env:CLOUD_PROFILE
    $github = Get-CloudProfileGitHub $profile
    $githubOrganisations = @($github.organisations)
    $githubDisplay = if ($github.host) {
        "$($github.host)/$(if ($githubOrganisations.Count -gt 0) { $githubOrganisations[0] })"
    } else { "Not configured" }
    [pscustomobject]@{
        Profile = $profile.name
        AzureTenant = Get-CloudProfileTenantId $profile
        AzureSubscription = Get-CloudProfileSubscriptionId $profile
        GitHub = $githubDisplay
        AzureConfigDirectory = $env:AZURE_CONFIG_DIR
        GitHubConfigDirectory = $env:GH_CONFIG_DIR
    } | Format-List | Out-Host
}

function Get-AzureContext {
    $json = & az account show --output json 2>$null
    if ($LASTEXITCODE -ne 0 -or -not $json) {
        return $null
    }
    return $json | ConvertFrom-Json
}

function Assert-CloudContext {
    [CmdletBinding()]
    param(
        [switch]$AzureOnly,
        [switch]$GitHubOnly
    )

    if (-not $env:CLOUD_PROFILE) {
        throw "No cloud profile is active. Run Use-CloudProfile <name>."
    }
    $profile = Get-CloudProfile -Name $env:CLOUD_PROFILE

    if (-not $GitHubOnly) {
        $expectedTenant = Get-CloudProfileTenantId $profile
        $expectedSubscription = Get-CloudProfileSubscriptionId $profile
        if (-not $expectedTenant -or -not $expectedSubscription) {
            throw "Azure is not configured for cloud profile '$($profile.name)'."
        }
        $account = Get-AzureContext
        if (-not $account) {
            throw "Azure CLI is not authenticated for profile '$($profile.name)'. Run Connect-CloudProfile -AzureOnly."
        }
        if ($account.tenantId -ne $expectedTenant -or $account.id -ne $expectedSubscription) {
            throw "Azure context mismatch for '$($profile.name)'. Expected tenant '$expectedTenant' and subscription '$expectedSubscription', got tenant '$($account.tenantId)' and subscription '$($account.id)'."
        }
    }

    if (-not $AzureOnly) {
        $github = Get-CloudProfileGitHub $profile
        if (-not $github.host) { throw "GitHub is not configured for cloud profile '$($profile.name)'." }
        & gh auth status --hostname $github.host 2>$null | Out-Null
        if ($LASTEXITCODE -ne 0) {
            throw "GitHub CLI is not authenticated for '$($github.host)' in profile '$($profile.name)'. Run Connect-CloudProfile -GitHubOnly."
        }
        if ($github.user) {
            $login = & gh api --hostname $github.host user --jq .login 2>$null
            if ($LASTEXITCODE -ne 0 -or $login -ne $github.user) {
                throw "GitHub user mismatch for '$($profile.name)'. Expected '$($github.user)', got '$login'."
            }
        }
    }

    return $true
}

function Connect-CloudProfile {
    [CmdletBinding()]
    param(
        [switch]$AzureOnly,
        [switch]$GitHubOnly
    )

    if (-not $env:CLOUD_PROFILE) {
        throw "No cloud profile is active. Run Use-CloudProfile <name> first."
    }
    $profile = Get-CloudProfile -Name $env:CLOUD_PROFILE

    if (-not $GitHubOnly) {
        $tenantId = Get-CloudProfileTenantId $profile
        $subscriptionId = Get-CloudProfileSubscriptionId $profile
        & az login --tenant $tenantId
        if ($LASTEXITCODE -ne 0) { throw "Azure CLI login failed." }
        & az account set --subscription $subscriptionId
        if ($LASTEXITCODE -ne 0) { throw "Unable to select Azure subscription '$subscriptionId'." }
    }

    if (-not $AzureOnly) {
        $github = Get-CloudProfileGitHub $profile
        & gh auth login --hostname $github.host
        if ($LASTEXITCODE -ne 0) { throw "GitHub CLI login failed." }
    }

    Assert-CloudContext -AzureOnly:$AzureOnly -GitHubOnly:$GitHubOnly | Out-Null
    Show-CloudContext
}

function Invoke-ProfileAz {
    [CmdletBinding()]
    param([Parameter(ValueFromRemainingArguments = $true)][object[]]$Arguments)

    Assert-CloudContext -AzureOnly | Out-Null
    & az @Arguments
}

function Invoke-ProfileGh {
    [CmdletBinding()]
    param([Parameter(ValueFromRemainingArguments = $true)][object[]]$Arguments)

    Assert-CloudContext -GitHubOnly | Out-Null
    & gh @Arguments
}

function Invoke-ProfileGhOrgApi {
    [CmdletBinding()]
    param(
        [Parameter(Position = 0)][string]$Path,
        [ValidateSet("DELETE", "GET", "PATCH", "POST", "PUT")][string]$Method = "GET",
        [Parameter(ValueFromRemainingArguments = $true)][object[]]$Arguments
    )

    Assert-CloudContext -GitHubOnly | Out-Null
    $profile = Get-CloudProfile -Name $env:CLOUD_PROFILE
    $github = Get-CloudProfileGitHub $profile
    $githubOrganisations = @($github.organisations)
    if ($githubOrganisations.Count -eq 0) {
        throw "GitHub organisation is not configured for cloud profile '$($profile.name)'."
    }
    $endpoint = "orgs/$($githubOrganisations[0])"
    if ($Path) {
        $endpoint = "$endpoint/$($Path.TrimStart('/'))"
    }

    & gh api --hostname $github.host --method $Method $endpoint @Arguments
}

Set-Alias -Name azp -Value Invoke-ProfileAz
Set-Alias -Name ghp -Value Invoke-ProfileGh
Set-Alias -Name ghorg -Value Invoke-ProfileGhOrgApi
Export-ModuleMember -Function @(
    "Assert-CloudContext"
    "Connect-CloudProfile"
    "Enable-CloudProfilePrompt"
    "Get-CloudProfile"
    "Invoke-ProfileAz"
    "Invoke-ProfileGh"
    "Invoke-ProfileGhOrgApi"
    "New-CloudProfile"
    "Remove-CloudProfile"
    "Restore-CloudProfile"
    "Show-CloudContext"
    "Use-CloudProfile"
) -Alias @("azp", "ghp", "ghorg")
