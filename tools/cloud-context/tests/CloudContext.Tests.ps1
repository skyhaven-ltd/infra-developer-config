$modulePath = Join-Path (Split-Path -Parent $PSScriptRoot) "CloudContext.psd1"

Describe "CloudContext profile metadata" {
    BeforeEach {
        $script:originalCloudContextHome = $env:CLOUD_CONTEXT_HOME
        $env:CLOUD_CONTEXT_HOME = Join-Path $env:TEMP ("cloud-context-test-" + [guid]::NewGuid().ToString("N"))
        Import-Module $modulePath -Force
    }

    AfterEach {
        Remove-Module CloudContext -ErrorAction SilentlyContinue
        if (Test-Path -LiteralPath $env:CLOUD_CONTEXT_HOME) {
            Remove-Item -LiteralPath $env:CLOUD_CONTEXT_HOME -Recurse -Force
        }
        $env:CLOUD_CONTEXT_HOME = $script:originalCloudContextHome
    }

    It "creates and retrieves a profile without storing credentials" {
        New-CloudProfile `
            -Name "customer-prod" `
            -AzureTenantId "tenant-id" `
            -AzureSubscriptionId "subscription-id" `
            -GitHubOrg "customer-org" `
            -GitHubUser "developer" | Out-Null

        $profile = Get-CloudProfile -Name "customer-prod"
        $profile.identity.tenantId | Should Be "tenant-id"
        $profile.connections.github.organisations[0] | Should Be "customer-org"
        ($profile.PSObject.Properties.Name -contains "token") | Should Be $false
        ($profile.PSObject.Properties.Name -contains "password") | Should Be $false
    }

    It "isolates CLI directories and persists the active profile" {
        New-CloudProfile `
            -Name "customer-prod" `
            -AzureTenantId "tenant-id" `
            -AzureSubscriptionId "subscription-id" `
            -GitHubOrg "customer-org" `
            -GitHubUser "developer" | Out-Null

        Use-CloudProfile "customer-prod" -Quiet

        $env:AZURE_CONFIG_DIR | Should Match "customer-prod$"
        $env:GH_CONFIG_DIR | Should Match "customer-prod$"
        $env:GH_ORG | Should Be "customer-org"
        (Get-Content (Join-Path $env:CLOUD_CONTEXT_HOME "active-profile") -Raw).Trim() | Should Be "customer-prod"
    }

    It "uses a version two profile with optional connections" {
        New-Item -ItemType Directory -Path $env:CLOUD_CONTEXT_HOME -Force | Out-Null
        @{
            schemaVersion = 2
            profiles = @(@{
                name = "azure-only"
                displayName = "Azure only"
                identity = @{ username = "developer@example.com"; tenantId = "tenant-id" }
                connections = @{
                    azure = @{ subscriptionIds = @("subscription-id") }
                    github = $null
                    azureDevOps = $null
                    dataverse = $null
                    logAnalytics = $null
                }
            })
        } | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $env:CLOUD_CONTEXT_HOME "profiles.json")

        Use-CloudProfile "azure-only" -NoPersist -Quiet

        $env:AZURE_TENANT_ID | Should Be "tenant-id"
        $env:AZURE_SUBSCRIPTION_ID | Should Be "subscription-id"
        ([string]::IsNullOrEmpty($env:GH_HOST)) | Should Be $true
    }

    It "rejects unsafe profile names" {
        $threw = $false
        try {
            New-CloudProfile `
                -Name "..\escape" `
                -AzureTenantId "tenant-id" `
                -AzureSubscriptionId "subscription-id" `
                -GitHubOrg "customer-org" `
                -GitHubUser "developer" `
                -ErrorAction Stop
        } catch {
            $threw = $true
        }
        $threw | Should Be $true
    }
}
