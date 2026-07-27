[CmdletBinding()]
param (
    [ValidateSet("Claude Code", "Codex", "Test")]
    [string]$Source = "Test",

    [ValidateSet("Complete", "Permission")]
    [string]$Event = "Complete",

    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$Payload
)

$ErrorActionPreference = "SilentlyContinue"

# SystemSounds is part of Windows and works for a standard user without any
# modules, notification registration, or administrator privileges. Codex adds
# a JSON payload as the final argument; Claude supplies JSON on stdin. Neither
# is needed to play the notification sound.
$sound = if ($Event -eq "Permission") {
    [System.Media.SystemSounds]::Exclamation
} else {
    [System.Media.SystemSounds]::Asterisk
}

$sound.Play()
Start-Sleep -Milliseconds 500

