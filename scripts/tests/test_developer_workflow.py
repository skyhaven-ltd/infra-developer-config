import importlib.util
import io
import json
import os
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
pr = load("create_pr", ROOT / "skills/create-pr/scripts/create-pr-helper.py")


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

    def test_mcp_authenticates_without_exposing_token(self):
        response = io.BytesIO(b'{"jsonrpc":"2.0","id":1,"result":{"serverInfo":{"name":"test"}}}')
        response.headers = {"Content-Type": "application/json"}
        with patch.dict(os.environ, {"TEST_MCP_TOKEN": "private-value"}):
            with patch.object(doctor.urllib.request, "build_opener") as opener:
                opener.return_value.open.return_value = response
                actual = doctor.mcp_check({"url": "https://example.invalid/mcp", "bearer_token_env_var": "TEST_MCP_TOKEN"})
                request = opener.return_value.open.call_args.args[0]
                self.assertEqual(request.get_header("Authorization"), "Bearer private-value")
                self.assertEqual(actual["status"], "PASS")
                self.assertNotIn("private-value", json.dumps(actual))

    def test_offline_does_not_attempt_authentication_or_network(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch.object(doctor, "command_check", side_effect=lambda *args: doctor.result(args[0], "PASS", "fixture")) as commands:
                with patch.object(doctor, "mcp_check") as mcp:
                    checks = doctor.inspect(root, root, root, offline=True)
                    self.assertFalse(mcp.called)
                    self.assertTrue(all(call.args[2] == ["--version"] for call in commands.call_args_list))
                    self.assertTrue(any(item["status"] == "FAIL" for item in checks))


class PullRequests(unittest.TestCase):
    def test_only_supported_branch_prefixes(self):
        for prefix in ("patch", "minor", "major"):
            self.assertEqual(pr.branch_kind(prefix + "/example")["title_prefix"], f"[{prefix.upper()}]")
        for branch in ("main", "feature/example", "fix/example", "chore/example", "docs/example", "breaking/example"):
            self.assertIsNone(pr.branch_kind(branch))

    def test_authorization_flag_is_still_required(self):
        for plan in ({}, {"approved": False}, {"approved": "true"}):
            with self.assertRaises(pr.SkillError):
                pr.require_approved(plan)
        pr.require_approved({"approved": True})

    def test_apply_rejects_unsupported_branch_before_remote_call(self):
        with tempfile.TemporaryDirectory() as directory:
            plan = Path(directory) / "plan.json"
            plan.write_text('{"approved":true}')
            with patch.object(pr, "pull_request_template", return_value={"body": "template"}):
                with patch.object(pr, "current_branch", return_value="feature/example"):
                    with patch.object(pr, "resolve_vcs") as resolve:
                        with self.assertRaises(pr.SkillError):
                            pr.apply(directory, str(plan), False)
                        resolve.assert_not_called()


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
[mcp_servers.knowledge]
url = "https://example.invalid/mcp"
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


if __name__ == "__main__":
    unittest.main()
