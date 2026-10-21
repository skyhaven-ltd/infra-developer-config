import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


doctor = load("doctor", ROOT / "scripts/test-developer-machine.py")


class MachineChecks(unittest.TestCase):
    def test_copied_helper_drift_is_detected(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source"
            target = Path(directory) / "target"
            source.mkdir()
            (source / "SKILL.md").write_text("skill")
            (source / "helper.py").write_text("original")
            shutil.copytree(source, target)
            (target / ".managed-by-ops-developer-config").touch()
            self.assertEqual(doctor.check_copy("skill", source, target)["status"], "PASS")
            (target / "helper.py").write_text("stale")
            self.assertEqual(doctor.check_copy("skill", source, target)["status"], "FAIL")

    def test_missing_link_and_wrong_link_are_detected(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source"
            source.write_text("instructions")
            self.assertEqual(doctor.check_copy("instructions", source, Path(directory) / "absent")["status"], "FAIL")
            target = Path(directory) / "target"
            other = Path(directory) / "other"
            other.write_text("instructions")
            try:
                target.symlink_to(other)
            except OSError:
                self.skipTest("Symlink creation is unavailable")
            self.assertEqual(doctor.check_copy("instructions", source, target)["status"], "FAIL")

    def test_model_override_is_not_permission_drift(self):
        shared = {"model": "shared", "model_reasoning_effort": "medium", "approval_policy": "never"}
        local = {**shared, "model": "local", "approval_policy": "on-request"}
        checks = {item["check"]: item for item in doctor.config_checks(shared, local)}
        self.assertEqual(checks["Codex model"]["status"], "PASS")
        self.assertEqual(checks["Codex approval_policy"]["status"], "FAIL")

    def test_timeout_and_failed_command_do_not_leak_output(self):
        with patch.object(doctor, "executable", return_value="tool"):
            with patch.object(doctor.subprocess, "run", side_effect=subprocess.TimeoutExpired("tool", 15)):
                self.assertEqual(doctor.command_check("auth", "tool", ["status"])["status"], "FAIL")
            completed = subprocess.CompletedProcess([], 1, "secret-value", "secret-value")
            with patch.object(doctor.subprocess, "run", return_value=completed):
                self.assertNotIn("secret-value", json.dumps(doctor.command_check("auth", "tool", ["status"])))

    def test_offline_does_not_attempt_authentication(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch.object(doctor, "command_check", side_effect=lambda *args: doctor.result(args[0], "PASS", "fixture")) as commands:
                checks = doctor.inspect(root, root, root, offline=True)
                self.assertTrue(all(call.args[2] == ["--version"] for call in commands.call_args_list))
                self.assertTrue(any(item["status"] == "FAIL" for item in checks))


@unittest.skipUnless(shutil.which("pwsh"), "PowerShell 7 is required for installer tests")
class Installer(unittest.TestCase):
    def test_merge_preserves_local_models_and_is_idempotent(self):
        script = r'''
param($Repository, $Fixture)
$ErrorActionPreference = "Stop"
$tokens = $null
$errors = $null
$ast = [System.Management.Automation.Language.Parser]::ParseFile((Join-Path $Repository "scripts/Install-DeveloperConfig.ps1"), [ref]$tokens, [ref]$errors)
if ($errors.Count) { throw ($errors | Out-String) }
$ast.FindAll({ param($node) $node -is [System.Management.Automation.Language.FunctionDefinitionAst] }, $false) | ForEach-Object { . ([scriptblock]::Create($_.Extent.Text)) }
$source = Join-Path $Fixture "shared.toml"
$local = Join-Path $Fixture "local.toml"
@'
model = "shared-model"
model_reasoning_effort = "medium"
approval_policy = "never"
'@ | Set-Content $source
@'
model = "local-model"
approval_policy = "on-request"
[projects.'D:/Repos/example']
trust_level = "trusted"
[mcp_servers.other]
command = "keep-me"
'@ | Set-Content $local
Merge-CodexConfig $source $local
$content = Get-Content $local -Raw
foreach ($expected in @('model = "local-model"', 'model_reasoning_effort = "medium"', 'approval_policy = "never"', 'trust_level = "trusted"', 'command = "keep-me"')) {
    if (-not $content.Contains($expected)) { throw "Lost expected setting: $expected" }
}
[IO.File]::SetLastWriteTimeUtc($local, [datetime]"2000-01-01")
$timestamp = (Get-Item $local).LastWriteTimeUtc
Merge-CodexConfig $source $local
if ((Get-Item $local).LastWriteTimeUtc -ne $timestamp) { throw "Unchanged configuration was rewritten." }
$fresh = Join-Path $Fixture "fresh.toml"
Merge-CodexConfig $source $fresh
if (-not (Get-Content $fresh -Raw).Contains('model = "shared-model"')) { throw "Missing initial model default." }
'''
        with tempfile.TemporaryDirectory() as directory:
            harness = Path(directory) / "check.ps1"
            harness.write_text(script)
            completed = subprocess.run([shutil.which("pwsh"), "-NoProfile", "-File", str(harness), str(ROOT), directory], capture_output=True, text=True, timeout=30)
            self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)

    def run_installer_functions(self, body):
        script = r'''
param($Repository, $Fixture)
$ErrorActionPreference = "Stop"
$tokens = $null
$errors = $null
$ast = [System.Management.Automation.Language.Parser]::ParseFile((Join-Path $Repository "scripts/Install-DeveloperConfig.ps1"), [ref]$tokens, [ref]$errors)
if ($errors.Count) { throw ($errors | Out-String) }
$ast.FindAll({ param($node) $node -is [System.Management.Automation.Language.FunctionDefinitionAst] }, $false) | ForEach-Object { . ([scriptblock]::Create($_.Extent.Text)) }
''' + body
        with tempfile.TemporaryDirectory() as directory:
            harness = Path(directory) / "check.ps1"
            harness.write_text(script)
            completed = subprocess.run([shutil.which("pwsh"), "-NoProfile", "-File", str(harness), str(ROOT), directory], capture_output=True, text=True, timeout=30)
            self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)

    def test_junction_with_previous_target_is_retargeted(self):
        self.run_installer_functions(r'''
$old = New-Item -ItemType Directory -Path (Join-Path $Fixture "old")
$new = New-Item -ItemType Directory -Path (Join-Path $Fixture "new")
$link = Join-Path $Fixture "link"
New-Junction $link $old.FullName
New-Junction $link $new.FullName
if (-not (Test-ReparseTarget $link $new.FullName)) { throw "Junction still points at the previous target." }
''')

    def test_claude_settings_seed_defaults_expand_profile_and_are_idempotent(self):
        self.run_installer_functions(r'''
$source = Join-Path $Fixture "shared.json"
$local = Join-Path $Fixture "local.json"
@'
{
  "permissions": { "allow": ["Read"] },
  "model": "shared-model",
  "statusLine": { "type": "command", "command": "node \"%USERPROFILE%/.claude/statusline.js\"" }
}
'@ | Set-Content $source
@'
{ "model": "local-model", "permissions": { "allow": ["Old"] } }
'@ | Set-Content $local
Merge-ClaudeSettings $source $local
$merged = Get-Content $local -Raw | ConvertFrom-Json
if ($merged.model -ne "local-model") { throw "Local model was overwritten." }
if (@($merged.permissions.allow) -join "," -ne "Read") { throw "Shared permissions were not applied." }
if ($merged.statusLine.command -ne "node `"$env:USERPROFILE/.claude/statusline.js`"") { throw "Profile path was not expanded: $($merged.statusLine.command)" }
$first = Get-Content $local -Raw
Merge-ClaudeSettings $source $local
if ((Get-Content $local -Raw) -ne $first) { throw "Second merge changed the settings." }
$fresh = Join-Path $Fixture "fresh.json"
Merge-ClaudeSettings $source $fresh
if ((Get-Content $fresh -Raw | ConvertFrom-Json).model -ne "shared-model") { throw "Missing initial model default." }
''')

    def test_claude_settings_merge_retires_agent_skills_and_adds_missing_env(self):
        self.run_installer_functions(r'''
$source = Join-Path $Fixture "shared.json"
$local = Join-Path $Fixture "local.json"
@'
{
  "permissions": { "allow": ["Read"] },
  "env": { "CLAUDE_CODE_AUTO_COMPACT_WINDOW": "200000", "SHARED": "shared" }
}
'@ | Set-Content $source
@'
{
  "enabledPlugins": { "agent-skills@addy-agent-skills": true, "skins@hellosverre-mods": true },
  "extraKnownMarketplaces": { "addy-agent-skills": { "source": { "source": "git", "url": "x" } }, "hellosverre-mods": { "source": { "source": "git", "url": "y" } } },
  "env": { "SHARED": "local" }
}
'@ | Set-Content $local
Merge-ClaudeSettings $source $local
$merged = Get-Content $local -Raw | ConvertFrom-Json
if ($merged.enabledPlugins.PSObject.Properties.Name -contains "agent-skills@addy-agent-skills") { throw "Retired plugin is still enabled." }
if ($merged.extraKnownMarketplaces.PSObject.Properties.Name -contains "addy-agent-skills") { throw "Retired marketplace is still known." }
if (-not $merged.enabledPlugins."skins@hellosverre-mods") { throw "Local plugin was removed." }
if (-not $merged.extraKnownMarketplaces."hellosverre-mods") { throw "Local marketplace was removed." }
if ($merged.env.CLAUDE_CODE_AUTO_COMPACT_WINDOW -ne "200000") { throw "Missing shared env key was not added." }
if ($merged.env.SHARED -ne "local") { throw "Local env value was overwritten." }
$first = Get-Content $local -Raw
Merge-ClaudeSettings $source $local
if ((Get-Content $local -Raw) -ne $first) { throw "Second merge changed the settings." }
''')


if __name__ == "__main__":
    unittest.main()
