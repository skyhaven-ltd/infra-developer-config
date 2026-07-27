from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


MODULE_PATH = Path(__file__).resolve().parents[1] / "cloud-profile.py"
SPEC = importlib.util.spec_from_file_location("cloud_profile", MODULE_PATH)
assert SPEC and SPEC.loader
cloud_profile = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(cloud_profile)


class CloudProfileTests(unittest.TestCase):
    def profile(self) -> dict[str, str]:
        return {
            "name": "customer-prod",
            "azureTenantId": "tenant-id",
            "azureSubscriptionId": "subscription-id",
            "githubHost": "github.com",
            "githubOrg": "customer-org",
            "githubUser": "developer",
        }

    def test_profile_environment_is_isolated(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            environment = cloud_profile.profile_environment(
                Path(directory), self.profile(), {"EXISTING": "value"}
            )

        self.assertEqual(environment["CLOUD_PROFILE"], "customer-prod")
        self.assertEqual(environment["GH_ORG"], "customer-org")
        self.assertTrue(environment["AZURE_CONFIG_DIR"].endswith("customer-prod"))
        self.assertTrue(environment["GH_CONFIG_DIR"].endswith("customer-prod"))
        self.assertEqual(environment["EXISTING"], "value")

    def test_version_two_profile_environment_is_supported(self) -> None:
        profile = {
            "name": "customer-prod",
            "identity": {"tenantId": "tenant-id", "username": "person@example.com"},
            "connections": {
                "azure": {"subscriptionIds": ["subscription-id"]},
                "github": {
                    "host": "github.com",
                    "user": "person",
                    "organisations": ["customer-org"],
                },
            },
        }
        with tempfile.TemporaryDirectory() as directory:
            environment = cloud_profile.profile_environment(Path(directory), profile, {})

        self.assertEqual(environment["AZURE_TENANT_ID"], "tenant-id")
        self.assertEqual(environment["AZURE_SUBSCRIPTION_ID"], "subscription-id")
        self.assertEqual(environment["GH_ORG"], "customer-org")

    def test_unconfigured_connections_do_not_inherit_ambient_context(self) -> None:
        profile = {
            "name": "metadata-only",
            "identity": {"username": "person@example.com", "tenantId": ""},
            "connections": {},
        }
        ambient = {
            "AZURE_TENANT_ID": "wrong-tenant",
            "AZURE_SUBSCRIPTION_ID": "wrong-subscription",
            "GH_HOST": "wrong.example.com",
            "GH_ORG": "wrong-org",
        }
        with tempfile.TemporaryDirectory() as directory:
            environment = cloud_profile.profile_environment(
                Path(directory), profile, ambient
            )

        self.assertNotIn("AZURE_TENANT_ID", environment)
        self.assertNotIn("AZURE_SUBSCRIPTION_ID", environment)
        self.assertNotIn("GH_HOST", environment)
        self.assertNotIn("GH_ORG", environment)

    def test_main_executes_with_named_profile(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "profiles.json").write_text(
                json.dumps({"profiles": [self.profile()]}), encoding="utf-8"
            )
            environment = {"CLOUD_CONTEXT_HOME": directory}
            completed = type("Completed", (), {"returncode": 17})()
            with (
                patch.dict(cloud_profile.os.environ, environment, clear=True),
                patch.object(cloud_profile, "validate_azure") as validate_azure,
                patch.object(cloud_profile, "validate_github") as validate_github,
                patch.object(cloud_profile, "prepare_command", return_value=["tool"]),
                patch.object(cloud_profile.subprocess, "run", return_value=completed) as run,
            ):
                result = cloud_profile.main(
                    ["--validate", "both", "customer-prod", "--", "tool"]
                )

        self.assertEqual(result, 17)
        validate_azure.assert_called_once()
        validate_github.assert_called_once()
        self.assertEqual(run.call_args.kwargs["env"]["CLOUD_PROFILE"], "customer-prod")

    def test_ghorg_uses_profile_organisation(self) -> None:
        with patch.object(cloud_profile, "executable", return_value="gh"):
            command = cloud_profile.prepare_command(
                ["ghorg", "repos", "--paginate"], self.profile()
            )

        self.assertEqual(
            command,
            [
                "gh",
                "api",
                "--hostname",
                "github.com",
                "orgs/customer-org/repos",
                "--paginate",
            ],
        )


if __name__ == "__main__":
    unittest.main()
