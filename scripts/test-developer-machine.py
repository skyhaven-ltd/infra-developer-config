import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import time
import urllib.request

if sys.version_info < (3, 11):
    raise SystemExit("Python 3.11 or newer is required.")
import tomllib


def result(name, status, detail):
    return {"check": name, "status": status, "detail": detail}


def executable(name):
    found = shutil.which(name)
    if not found and name == "gh" and os.name == "nt":
        candidate = Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "GitHub CLI/gh.exe"
        if candidate.is_file():
            found = str(candidate)
    return found


def command_check(name, command, arguments, optional=False):
    path = executable(command)
    if not path:
        return result(name, "WARN" if optional else "FAIL", f"{command} is not installed or not on PATH.")
    try:
        completed = subprocess.run([path, *arguments], capture_output=True, timeout=15,
                                   encoding="utf-8", errors="replace")
        if completed.returncode:
            return result(name, "WARN" if optional else "FAIL", "Check failed; authenticate or run the command manually.")
        return result(name, "PASS", "Available." if arguments == ["--version"] else "Authenticated.")
    except (OSError, subprocess.TimeoutExpired):
        return result(name, "WARN" if optional else "FAIL", "Could not finish the check within 15 seconds.")


def fingerprint(path):
    if path.is_file():
        return hashlib.sha256(path.read_bytes()).hexdigest()
    return {str(file.relative_to(path)): hashlib.sha256(file.read_bytes()).hexdigest()
            for file in path.rglob("*") if file.is_file()
            and "__pycache__" not in file.parts and file.suffix != ".pyc"
            and file.name != ".managed-by-ops-developer-config"}


def check_copy(name, source, destination):
    if not destination.exists():
        return result(name, "FAIL", "Missing or broken link; rerun Install-DeveloperConfig.ps1.")
    if source.resolve() == destination.resolve():
        return result(name, "PASS", "Linked to this checkout.")
    if destination.is_symlink() or getattr(destination.lstat(), "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT:
        return result(name, "FAIL", "Linked to another checkout; inspect the link target.")
    try:
        if fingerprint(source) == fingerprint(destination):
            return result(name, "PASS", "Copy matches this checkout.")
    except OSError:
        return result(name, "FAIL", "Cannot read files for comparison; check permissions.")
    return result(name, "FAIL", "Copy differs from this checkout; rerun Install-DeveloperConfig.ps1.")


def nested(config, key):
    value = config
    for part in key.split("."):
        if not isinstance(value, dict):
            return None
        value = value.get(part)
    return value


def config_checks(shared, local):
    checks = []
    for key in ("approval_policy", "sandbox_mode", "windows.sandbox", "notify", "mcp_servers.knowledge"):
        if os.name != "nt" and key == "windows.sandbox":
            continue
        expected = nested(shared, key)
        if key == "notify" and expected:
            expected = [item.replace("%USERPROFILE%", str(Path.home())) for item in expected]
        matches = nested(local, key) == expected
        checks.append(result(f"Codex {key}", "PASS" if matches else "FAIL",
                             "Matches shared settings." if matches else "Drift detected; rerun Install-DeveloperConfig.ps1."))
    for key in ("model", "model_reasoning_effort"):
        actual = local.get(key)
        checks.append(result(f"Codex {key}", "PASS" if actual else "WARN",
                             f"{actual} (local override preserved)." if actual and actual != shared.get(key)
                             else f"{actual or 'Unset; rerun installer to seed the shared default.'}"))
    return checks


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def mcp_check(server):
    credential = os.environ.get(server.get("bearer_token_env_var", ""))
    if not credential:
        return result("Knowledge MCP", "FAIL", "Bearer-token environment variable is missing in this process; restart after configuring it.")
    payload = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
        "protocolVersion": "2024-11-05", "capabilities": {},
        "clientInfo": {"name": "developer-machine-check", "version": "1.0"}}}
    request = urllib.request.Request(server["url"], data=json.dumps(payload).encode(), headers={
        "Authorization": f"Bearer {credential}", "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream"})
    try:
        deadline = time.monotonic() + 10
        with urllib.request.build_opener(NoRedirect()).open(request, timeout=10) as response:
            if "text/event-stream" in response.headers.get("Content-Type", ""):
                message = {}
                for line in response:
                    if time.monotonic() > deadline:
                        break
                    if line.startswith(b"data:"):
                        message = json.loads(line[5:])
                        if message.get("id") == 1:
                            break
            else:
                message = json.load(response)
        if "result" in message and "serverInfo" in message["result"]:
            return result("Knowledge MCP", "PASS", "Authenticated MCP initialization succeeded.")
        return result("Knowledge MCP", "FAIL", "Endpoint did not return a successful MCP initialization.")
    except (OSError, ValueError):
        return result("Knowledge MCP", "FAIL", "Connection or authentication failed; check network, endpoint and token.")


def inspect(repo, user_root, codex_home, offline=False):
    checks = [result("Python", "PASS", sys.version.split()[0])]
    shared = {}
    local = {}
    for label, path in (("Shared config", repo / "codex/config.toml"), ("Local config", codex_home / "config.toml")):
        try:
            config = tomllib.loads(path.read_text(encoding="utf-8-sig"))
            if label == "Shared config":
                shared = config
            else:
                local = config
            checks.append(result(label, "PASS", "Valid TOML."))
        except (OSError, ValueError):
            checks.append(result(label, "FAIL", "Missing, unreadable or invalid TOML."))
    if shared and local:
        checks.extend(config_checks(shared, local))
    skill_files = sorted((repo / "skills").rglob("SKILL.md"))
    names = [file.parent.name for file in skill_files]
    if len(names) != len(set(names)):
        checks.append(result("Skill names", "FAIL", "Duplicate skill folder names cannot be installed flat."))
    if not skill_files:
        checks.append(result("Skill sources", "FAIL", "No skills found; check --repo."))
    for tool, root, instruction in (("Codex", codex_home, "AGENTS.md"), ("Claude", user_root / ".claude", "CLAUDE.md")):
        checks.append(check_copy(f"{tool} instructions", repo / "system/SYSTEM.md", root / instruction))
        for file in skill_files:
            checks.append(check_copy(f"{tool} skill {file.parent.name}", file.parent, root / "skills" / file.parent.name))
        for installed in (root / "skills").glob("*"):
            managed = (installed / ".managed-by-ops-developer-config").exists() or installed.resolve().is_relative_to((repo / "skills").resolve())
            if installed.name not in names and managed:
                checks.append(result(f"{tool} stale skill {installed.name}", "WARN", "Removed from source; rerun installer to remove the managed entry."))
    handoff = os.environ.get("AGENT_HANDOFF_DIR")
    checks.append(result("Portable handoffs", "PASS" if handoff and Path(handoff).is_dir() else "WARN",
                         "Directory exists; synchronization must be provided separately." if handoff and Path(handoff).is_dir()
                         else "Set AGENT_HANDOFF_DIR to an existing synced directory; otherwise handoffs remain local."))
    jobs = [("Git", "git", ["--version"], False), ("Codex CLI", "codex", ["--version"], False)]
    if os.name == "nt":
        jobs.append(("PowerShell 7", "pwsh", ["--version"], False))
    if offline:
        jobs.append(("GitHub CLI", "gh", ["--version"], False))
        checks.append(result("Online checks", "SKIP", "Authentication and MCP checks skipped (--offline)."))
    else:
        jobs.extend([("GitHub authentication", "gh", ["auth", "status"], False),
                     ("Codex authentication", "codex", ["login", "status"], False),
                     ("Azure authentication (optional)", "az", ["account", "show", "--output", "none"], True)])
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(command_check, *job) for job in jobs]
        server = nested(shared, "mcp_servers.knowledge")
        if not offline and server and server == nested(local, "mcp_servers.knowledge"):
            futures.append(executor.submit(mcp_check, server))
        elif not offline:
            checks.append(result("Knowledge MCP", "SKIP", "Fix configuration drift before sending credentials."))
        checks.extend(future.result() for future in futures)
    return checks


def main(argv=None):
    parser = argparse.ArgumentParser(description="Read-only developer machine checks; no settings or credentials are changed.")
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parent.parent)
    parser.add_argument("--home", type=Path, default=Path.home())
    parser.add_argument("--codex-home", type=Path)
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    codex_home = args.codex_home or Path(os.environ.get("CODEX_HOME", str(args.home / ".codex")))
    checks = inspect(args.repo.resolve(), args.home.expanduser(), codex_home.expanduser(), args.offline)
    failed = any(check["status"] == "FAIL" for check in checks)
    if args.json:
        print(json.dumps({"ok": not failed, "checks": checks}, indent=2))
    else:
        for check in checks:
            print(f"[{check['status']}] {check['check']}: {check['detail']}")
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())
