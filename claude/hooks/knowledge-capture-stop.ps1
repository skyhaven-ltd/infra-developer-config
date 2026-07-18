# Stop hook: remind the agent once per session to store durable knowledge in
# the knowledge MCP before finishing. Installed to ~/.claude/hooks by
# scripts/Install-DeveloperConfig.ps1 and referenced from claude/settings.json.
$ErrorActionPreference = "Stop"

try {
    $payload = [Console]::In.ReadToEnd() | ConvertFrom-Json
} catch {
    exit 0
}

# A block issued by this hook re-triggers Stop with stop_hook_active set;
# exiting here prevents a reminder loop.
if ($payload.PSObject.Properties.Name -contains "stop_hook_active" -and $payload.stop_hook_active) {
    exit 0
}

if (-not ($payload.PSObject.Properties.Name -contains "session_id") -or -not $payload.session_id) {
    exit 0
}

$markerDirectory = Join-Path $env:TEMP "claude-knowledge-capture"
New-Item -ItemType Directory -Path $markerDirectory -Force | Out-Null

# Drop markers from sessions older than seven days.
Get-ChildItem -LiteralPath $markerDirectory -File -ErrorAction SilentlyContinue |
    Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-7) } |
    Remove-Item -Force -ErrorAction SilentlyContinue

$marker = Join-Path $markerDirectory "$($payload.session_id).reminded"
if (Test-Path -LiteralPath $marker) {
    exit 0
}
New-Item -ItemType File -Path $marker -Force | Out-Null

@{
    decision = "block"
    reason   = (
        "Before finishing: if this session produced durable, non-obvious, reusable " +
        "knowledge (a decision, lesson, convention, environment fact, or runbook), " +
        "store it now with the knowledge MCP memory_upsert tool using the scope " +
        "convention (global, repo:<name>, machine:<hostname>) and concrete evidence. " +
        "If nothing durable was learned, or the knowledge MCP is unavailable, finish " +
        "normally. Never store secrets, task progress, or facts readable from source."
    )
} | ConvertTo-Json -Compress
exit 0
