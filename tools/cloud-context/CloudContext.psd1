@{
    RootModule = "CloudContext.psm1"
    ModuleVersion = "1.0.0"
    GUID = "3f430e82-54e0-49ca-a896-c08ac5192ac7"
    Author = "Sky Haven"
    Description = "Isolated Azure CLI and GitHub CLI profiles with context validation."
    PowerShellVersion = "5.1"
    FunctionsToExport = @(
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
    )
    AliasesToExport = @("azp", "ghp", "ghorg")
    CmdletsToExport = @()
    VariablesToExport = @()
}
