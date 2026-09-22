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

    def test_dataverse_profile_does_not_require_subscription_or_github(self) -> None:
        profile = {"name": "dataverse", "azureTenantId": "tenant-id",
                   "dataverseUrl": "https://example.crm.dynamics.com"}
        with tempfile.TemporaryDirectory() as directory:
            environment = cloud_profile.profile_environment(Path(directory), profile, {})
        self.assertEqual(environment["DATAVERSE_URL"], profile["dataverseUrl"])
        self.assertEqual(environment["AZURE_SUBSCRIPTION_ID"], "")
        result = type("Completed", (), {"returncode": 0, "stdout": json.dumps({"tenantId": "tenant-id", "id": "tenant-id"})})()
        with (patch.object(cloud_profile, "executable", return_value="az"),
              patch.object(cloud_profile, "run_capture", return_value=result)):
            cloud_profile.validate_azure(profile, environment)
        with self.assertRaisesRegex(cloud_profile.CloudProfileError, "GitHub configured"):
            cloud_profile.validate_github(profile, environment)

    def test_wrong_tenant_and_subscription_are_rejected(self) -> None:
        result = type("Completed", (), {"returncode": 0, "stdout": json.dumps({"tenantId": "other", "id": "other"})})()
        with (patch.object(cloud_profile, "executable", return_value="az"),
              patch.object(cloud_profile, "run_capture", return_value=result)):
            with self.assertRaisesRegex(cloud_profile.CloudProfileError, "mismatch"):
                cloud_profile.validate_azure(self.profile(), {})

    def test_unsafe_profile_name_is_rejected_before_creating_directories(self) -> None:
        profile = self.profile()
        profile["name"] = "../escape"
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(cloud_profile.CloudProfileError, "invalid cloud profile name"):
                cloud_profile.profile_environment(Path(directory), profile, {})
            self.assertEqual(list(Path(directory).iterdir()), [])


if __name__ == "__main__":
    unittest.main()
