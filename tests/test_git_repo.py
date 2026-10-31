import shutil
import subprocess
import tempfile
import unittest
import unittest.mock

from ado_builds.git_repo import RepoError, RepoRef, parse_remote, repo_ref

EXPECTED = ("my-org", "My Project", "my-repo")


class ParseRemoteTest(unittest.TestCase):
    def test_https(self):
        self.assertEqual(parse_remote("https://my-org@dev.azure.com/my-org/My%20Project/_git/my-repo"), EXPECTED)

    def test_ssh(self):
        self.assertEqual(parse_remote("git@ssh.dev.azure.com:v3/my-org/My%20Project/my-repo"), EXPECTED)

    def test_visualstudio(self):
        self.assertEqual(parse_remote("https://my-org.visualstudio.com/My%20Project/_git/my-repo"), EXPECTED)

    def test_other_host(self):
        self.assertIsNone(parse_remote("git@github.com:owner/repo.git"))


ADO_URL = "https://my-org@dev.azure.com/my-org/proj/_git/my-repo"


@unittest.skipUnless(shutil.which("git"), "git not installed")
class RepoRefTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = tmp.name
        self.git("init", "-q", "-b", "main")

    def git(self, *args):
        subprocess.run(["git", "-C", self.dir, *args], check=True, capture_output=True)

    def test_not_a_repo(self):
        with tempfile.TemporaryDirectory() as plain:
            with self.assertRaisesRegex(RepoError, "Not a git repository"):
                repo_ref(plain)

    def test_no_remote(self):
        with self.assertRaisesRegex(RepoError, "No git remote"):
            repo_ref(self.dir)

    def test_origin(self):
        self.git("remote", "add", "origin", ADO_URL)
        self.assertEqual(repo_ref(self.dir), RepoRef_("main"))

    def test_non_ado_remote(self):
        self.git("remote", "add", "origin", "git@github.com:o/r.git")
        with self.assertRaisesRegex(RepoError, "No Azure DevOps remote"):
            repo_ref(self.dir)

    def test_first_ado_remote_when_no_origin(self):
        self.git("remote", "add", "gh", "git@github.com:o/r.git")
        self.git("remote", "add", "ado", ADO_URL)
        self.assertEqual(repo_ref(self.dir).repo, "my-repo")

    def test_upstream_remote_and_branch(self):
        self.git("remote", "add", "origin", "git@github.com:o/r.git")
        self.git("remote", "add", "ado", ADO_URL)
        self.git("config", "branch.main.remote", "ado")
        self.git("config", "branch.main.merge", "refs/heads/release/1")
        self.assertEqual(repo_ref(self.dir), RepoRef_("release/1"))

    def test_configured_remote(self):
        self.git("remote", "add", "origin", "git@github.com:o/r.git")
        self.git("remote", "add", "ado", ADO_URL)
        self.assertEqual(repo_ref(self.dir, "ado").branch, "main")
        with self.assertRaisesRegex(RepoError, "not an Azure DevOps remote"):
            repo_ref(self.dir, "origin")

    def test_detached_head(self):
        self.git("remote", "add", "origin", ADO_URL)
        self.git("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "--allow-empty", "-m", "x")
        self.git("checkout", "-q", "--detach")
        with self.assertRaisesRegex(RepoError, "Detached HEAD"):
            repo_ref(self.dir)

    def test_git_missing(self):
        with unittest.mock.patch("subprocess.run", side_effect=FileNotFoundError):
            with self.assertRaisesRegex(RepoError, "git not found"):
                repo_ref(self.dir)


def RepoRef_(branch):
    return RepoRef("my-org", "proj", "my-repo", branch)


if __name__ == "__main__":
    unittest.main()
