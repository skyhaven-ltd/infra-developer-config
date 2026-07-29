import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


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
