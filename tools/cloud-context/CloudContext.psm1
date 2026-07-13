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
        return [pscustomobject]@{ profiles = @() }
    }

    $store = Get-Content -LiteralPath $path -Raw | ConvertFrom-Json
    if (-not ($store.PSObject.Properties.Name -contains "profiles")) {
        throw "Cloud profile file '$path' must contain a 'profiles' array."
    }

    return $store
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
        azureTenantId = $AzureTenantId
        azureSubscriptionId = $AzureSubscriptionId
        githubHost = $GitHubHost
        githubOrg = $GitHubOrg
    }
    $profile.githubUser = $GitHubUser

    $remaining = @($profiles | Where-Object { $_.name -ne $Name })
    $updatedStore = [ordered]@{ profiles = @($remaining) + @([pscustomobject]$profile) }
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
    $env:AZURE_TENANT_ID = $Profile.azureTenantId
    $env:AZURE_SUBSCRIPTION_ID = $Profile.azureSubscriptionId
    $env:GH_CONFIG_DIR = $githubConfig
    $env:GH_HOST = $Profile.githubHost
    $env:GH_ORG = $Profile.githubOrg
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
    [pscustomobject]@{
        Profile = $profile.name
        AzureTenant = $profile.azureTenantId
        AzureSubscription = $profile.azureSubscriptionId
        GitHub = "$($profile.githubHost)/$($profile.githubOrg)"
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
        $account = Get-AzureContext
        if (-not $account) {
            throw "Azure CLI is not authenticated for profile '$($profile.name)'. Run Connect-CloudProfile -AzureOnly."
        }
        if ($account.tenantId -ne $profile.azureTenantId -or $account.id -ne $profile.azureSubscriptionId) {
            throw "Azure context mismatch for '$($profile.name)'. Expected tenant '$($profile.azureTenantId)' and subscription '$($profile.azureSubscriptionId)', got tenant '$($account.tenantId)' and subscription '$($account.id)'."
        }
    }

    if (-not $AzureOnly) {
        & gh auth status --hostname $profile.githubHost 2>$null | Out-Null
        if ($LASTEXITCODE -ne 0) {
            throw "GitHub CLI is not authenticated for '$($profile.githubHost)' in profile '$($profile.name)'. Run Connect-CloudProfile -GitHubOnly."
        }
        if ($profile.PSObject.Properties.Name -contains "githubUser") {
            $login = & gh api --hostname $profile.githubHost user --jq .login 2>$null
            if ($LASTEXITCODE -ne 0 -or $login -ne $profile.githubUser) {
                throw "GitHub user mismatch for '$($profile.name)'. Expected '$($profile.githubUser)', got '$login'."
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
        & az login --tenant $profile.azureTenantId
        if ($LASTEXITCODE -ne 0) { throw "Azure CLI login failed." }
        & az account set --subscription $profile.azureSubscriptionId
        if ($LASTEXITCODE -ne 0) { throw "Unable to select Azure subscription '$($profile.azureSubscriptionId)'." }
    }

    if (-not $AzureOnly) {
        & gh auth login --hostname $profile.githubHost
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
    $endpoint = "orgs/$($profile.githubOrg)"
    if ($Path) {
        $endpoint = "$endpoint/$($Path.TrimStart('/'))"
    }

    & gh api --hostname $profile.githubHost --method $Method $endpoint @Arguments
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
