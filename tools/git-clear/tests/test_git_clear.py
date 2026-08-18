import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


MODULE_PATH = Path(__file__).parents[1] / "git-clear.py"
sys.dont_write_bytecode = True
SPEC = importlib.util.spec_from_file_location("git_clear", MODULE_PATH)
git_clear = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = git_clear
SPEC.loader.exec_module(git_clear)


def git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=root, check=True, capture_output=True, text=True
    )
    return result.stdout.strip()


class GitClearTests(unittest.TestCase):
    def test_parses_azure_devops_repository_url(self) -> None:
        remote = subprocess.CompletedProcess(
            [], 0,
            stdout="https://user@dev.azure.com/example/Project%20Name/_git/example-repo\n",
        )
        with patch.object(git_clear, "run_git", return_value=remote):
            repository = git_clear.azure_devops_repository(Path("."))

        self.assertEqual(
            repository,
            ("https://dev.azure.com/example", "Project Name", "example-repo"),
        )

    def test_detects_azure_devops_squash_merge_by_exact_source_tip(self) -> None:
        remote = subprocess.CompletedProcess(
            [], 0,
            stdout="https://dev.azure.com/example/project/_git/repository\n",
        )
        head = subprocess.CompletedProcess([], 0, stdout="abc123\n")
        prs = subprocess.CompletedProcess(
            [], 0,
            stdout='[{"lastMergeSourceCommit": {"commitId": "abc123"}}]',
        )
        with (
            patch.object(git_clear, "run_git", side_effect=[remote, head]),
            patch.object(git_clear.shutil, "which", return_value="az"),
            patch.object(git_clear.subprocess, "run", return_value=prs),
        ):
            merged = git_clear.is_merged_azure_devops_pr_head(Path("."), "patch/example")

        self.assertTrue(merged)

    def test_rejects_azure_devops_pr_with_different_source_tip(self) -> None:
        remote = subprocess.CompletedProcess(
            [], 0,
            stdout="https://dev.azure.com/example/project/_git/repository\n",
        )
        head = subprocess.CompletedProcess([], 0, stdout="abc123\n")
        prs = subprocess.CompletedProcess(
            [], 0,
            stdout='[{"lastMergeSourceCommit": {"commitId": "different"}}]',
        )
        with (
            patch.object(git_clear, "run_git", side_effect=[remote, head]),
            patch.object(git_clear.shutil, "which", return_value="az"),
            patch.object(git_clear.subprocess, "run", return_value=prs),
        ):
            merged = git_clear.is_merged_azure_devops_pr_head(Path("."), "patch/example")

        self.assertFalse(merged)

    def test_deletes_patch_equivalent_branch_after_history_rewrite(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            git(root, "init", "--initial-branch=main")
            git(root, "config", "user.email", "test@example.invalid")
            git(root, "config", "user.name", "Test User")
            (root / "file.txt").write_text("base\n", encoding="utf-8")
            git(root, "add", "file.txt")
            git(root, "commit", "-m", "base")
            git(root, "checkout", "-b", "patch/example")
            (root / "file.txt").write_text("base\nchange\n", encoding="utf-8")
            git(root, "commit", "-am", "change")
            branch_commit = git(root, "rev-parse", "HEAD")
            git(root, "checkout", "main")
            git(root, "cherry-pick", branch_commit)
            git(root, "commit", "--amend", "-m", "rewritten merge commit")
            git(root, "remote", "add", "origin", str(root))
            git(root, "update-ref", "refs/remotes/origin/main", "main")
            git(root, "symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/main")

            plan = git_clear.discover(root, fetch=False)

            self.assertIn("patch/example", plan.delete_branches)

    def test_retains_branch_with_a_unique_change(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            git(root, "init", "--initial-branch=main")
            git(root, "config", "user.email", "test@example.invalid")
            git(root, "config", "user.name", "Test User")
            (root / "file.txt").write_text("base\n", encoding="utf-8")
            git(root, "add", "file.txt")
            git(root, "commit", "-m", "base")
            git(root, "checkout", "-b", "patch/example")
            (root / "file.txt").write_text("unique\n", encoding="utf-8")
            git(root, "commit", "-am", "unique")
            git(root, "remote", "add", "origin", str(root))
            git(root, "update-ref", "refs/remotes/origin/main", "main")
            git(root, "symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/main")

            plan = git_clear.discover(root, fetch=False)

            retained = {item.name for item in plan.retained_branches}
            self.assertIn("patch/example", retained)


if __name__ == "__main__":
    unittest.main()
