#!/usr/bin/env python3
"""Run a command with an explicit, isolated Azure and GitHub cloud profile."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


class CloudProfileError(RuntimeError):
    pass


def context_root(environment: dict[str, str]) -> Path:
    configured = environment.get("CLOUD_CONTEXT_HOME")
    if configured:
        return Path(configured).expanduser().resolve()
    return Path.home() / ".config" / "cloud-context"


def read_profiles(root: Path) -> list[dict[str, Any]]:
    path = root / "profiles.json"
    if not path.is_file():
        raise CloudProfileError(
            f"profile store not found: {path}; create a profile with New-CloudProfile"
        )
    try:
        store = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as error:
        raise CloudProfileError(f"unable to read profile store {path}: {error}") from error
    profiles = store.get("profiles")
    if not isinstance(profiles, list):
        raise CloudProfileError(f"profile store {path} must contain a profiles array")
    return profiles


def get_profile(root: Path, name: str) -> dict[str, Any]:
    for profile in read_profiles(root):
        if profile.get("name") == name:
            return profile
    raise CloudProfileError(f"cloud profile '{name}' does not exist")


def profile_environment(
    root: Path, profile: dict[str, Any], base: dict[str, str]
) -> dict[str, str]:
    required = (
        "name",
        "azureTenantId",
        "azureSubscriptionId",
        "githubHost",
        "githubOrg",
        "githubUser",
    )
    missing = [field for field in required if not profile.get(field)]
    if missing:
        raise CloudProfileError(
            f"profile '{profile.get('name', '<unknown>')}' is missing: {', '.join(missing)}"
        )

    name = str(profile["name"])
    azure_directory = root / "cli" / "azure" / name
    github_directory = root / "cli" / "github" / name
    azure_directory.mkdir(parents=True, exist_ok=True)
    github_directory.mkdir(parents=True, exist_ok=True)

    environment = base.copy()
    environment.update(
        {
            "CLOUD_PROFILE": name,
            "AZURE_CONFIG_DIR": str(azure_directory),
            "AZURE_TENANT_ID": str(profile["azureTenantId"]),
            "AZURE_SUBSCRIPTION_ID": str(profile["azureSubscriptionId"]),
            "ARM_TENANT_ID": str(profile["azureTenantId"]),
            "ARM_SUBSCRIPTION_ID": str(profile["azureSubscriptionId"]),
            "GH_CONFIG_DIR": str(github_directory),
            "GH_HOST": str(profile["githubHost"]),
            "GH_ORG": str(profile["githubOrg"]),
        }
    )
    return environment


def executable(name: str) -> str:
    resolved = shutil.which(name)
    if not resolved:
        raise CloudProfileError(f"required command was not found on PATH: {name}")
    return resolved


def run_capture(command: list[str], environment: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )


def validate_azure(profile: dict[str, Any], environment: dict[str, str]) -> None:
    result = run_capture([executable("az"), "account", "show", "--output", "json"], environment)
    if result.returncode != 0:
        raise CloudProfileError(
            f"Azure CLI is not authenticated for profile '{profile['name']}'"
        )
    try:
        account = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise CloudProfileError("Azure CLI returned an invalid account response") from error
    if (
        str(account.get("tenantId", "")).casefold()
        != str(profile["azureTenantId"]).casefold()
        or str(account.get("id", "")).casefold()
        != str(profile["azureSubscriptionId"]).casefold()
    ):
        raise CloudProfileError(
            "Azure context mismatch: expected "
            f"tenant '{profile['azureTenantId']}' and subscription "
            f"'{profile['azureSubscriptionId']}', got tenant "
            f"'{account.get('tenantId')}' and subscription '{account.get('id')}'"
        )


def validate_github(profile: dict[str, Any], environment: dict[str, str]) -> None:
    gh = executable("gh")
    status = run_capture(
        [gh, "auth", "status", "--hostname", str(profile["githubHost"])], environment
    )
    if status.returncode != 0:
        raise CloudProfileError(
            f"GitHub CLI is not authenticated for profile '{profile['name']}'"
        )
    identity = run_capture(
        [gh, "api", "--hostname", str(profile["githubHost"]), "user", "--jq", ".login"],
        environment,
    )
    login = identity.stdout.strip()
    if identity.returncode != 0 or login.casefold() != str(profile["githubUser"]).casefold():
        raise CloudProfileError(
            f"GitHub identity mismatch: expected '{profile['githubUser']}', got '{login}'"
        )


def validation_target(command: list[str], requested: str) -> str:
    if requested != "auto":
        return requested
    command_name = Path(command[0]).stem.casefold()
    if command_name == "az":
        return "azure"
    if command_name in {"gh", "ghorg"}:
        return "github"
    return "both"


def prepare_command(command: list[str], profile: dict[str, Any]) -> list[str]:
    if Path(command[0]).stem.casefold() != "ghorg":
        prepared = command.copy()
        prepared[0] = executable(prepared[0])
        return prepared
    path = command[1].lstrip("/") if len(command) > 1 else ""
    endpoint = f"orgs/{profile['githubOrg']}"
    if path:
        endpoint = f"{endpoint}/{path}"
    return [
        executable("gh"),
        "api",
        "--hostname",
        str(profile["githubHost"]),
        endpoint,
        *command[2:],
    ]


def print_profile(profile: dict[str, Any]) -> None:
    print(json.dumps(profile, indent=2))


def parse_arguments(arguments: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("profile", nargs="?", help="profile name")
    parser.add_argument(
        "--validate",
        choices=("auto", "azure", "github", "both", "none"),
        default="auto",
        help="identity validation performed before execution (default: auto)",
    )
    parser.add_argument("--list", action="store_true", help="list configured profile names")
    parser.add_argument("--show", action="store_true", help="show the selected profile as JSON")
    parser.add_argument("command", nargs=argparse.REMAINDER, help="command following --")
    return parser.parse_args(arguments)


def main(arguments: list[str] | None = None) -> int:
    args = parse_arguments(arguments if arguments is not None else sys.argv[1:])
    try:
        root = context_root(os.environ)
        if args.list:
            for profile in sorted(read_profiles(root), key=lambda item: item.get("name", "")):
                print(profile.get("name", ""))
            return 0
        if not args.profile:
            raise CloudProfileError("a profile name is required")
        profile = get_profile(root, args.profile)
        if args.show:
            print_profile(profile)
            return 0
        command = args.command
        if command and command[0] == "--":
            command = command[1:]
        if not command:
            raise CloudProfileError("a command is required after --")

        environment = profile_environment(root, profile, dict(os.environ))
        target = validation_target(command, args.validate)
        if target in {"azure", "both"}:
            validate_azure(profile, environment)
        if target in {"github", "both"}:
            validate_github(profile, environment)
        completed = subprocess.run(prepare_command(command, profile), env=environment, check=False)
        return completed.returncode
    except CloudProfileError as error:
        print(f"cloud-profile: {error}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
