import unittest
from unittest import mock

from ado_builds.ado_client import Build
from ado_builds.git_repo import RepoError, RepoRef
from ado_builds.service import BuildTracker

REF = RepoRef("o", "p", "r", "main")


def make_build(status, result=None):
    return Build(1, "CI", "1", status, result, None, None, None, "")


class FakeClient:
    def __init__(self, *rounds):
        self.rounds = list(rounds)

    def list_builds(self, ref, top):
        return self.rounds.pop(0)


class TrackerTest(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch("ado_builds.service.git_repo.repo_ref", return_value=REF)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.toasts = []

    def tracker(self, *rounds, **kwargs):
        return BuildTracker("/x", 5, FakeClient(*rounds), lambda *args: self.toasts.append(args), **kwargs)

    def test_no_toast_on_first_poll(self):
        self.tracker([make_build("completed", "succeeded")]).poll()
        self.assertEqual(self.toasts, [])

    def test_toast_once_on_finish(self):
        tracker = self.tracker(
            [make_build("inProgress")],
            [make_build("completed", "failed")],
            [make_build("completed", "failed")],
        )
        for _ in range(3):
            tracker.poll()
        self.assertEqual(self.toasts, [("Build failed", "CI 1", "request")])

    def finish(self, result, **kwargs):
        tracker = self.tracker([make_build("inProgress")], [make_build("completed", result)], **kwargs)
        tracker.poll()
        tracker.poll()

    def test_notify_failures_suppresses_success(self):
        self.finish("succeeded", notify_mode="failures")
        self.assertEqual(self.toasts, [])
        self.finish("failed", notify_mode="failures")
        self.assertEqual(len(self.toasts), 1)

    def test_notify_off(self):
        self.finish("failed", notify_mode="off")
        self.assertEqual(self.toasts, [])

    def test_unexpected_exception_becomes_error(self):
        class Boom:
            def list_builds(self, ref, top):
                raise KeyError("id")

        snapshot = BuildTracker("/x", 5, Boom()).poll()
        self.assertIn("Unexpected error", snapshot.error)

    def test_repo_error_becomes_error(self):
        with mock.patch("ado_builds.service.git_repo.repo_ref", side_effect=RepoError("Detached HEAD")):
            snapshot = self.tracker().poll()
        self.assertEqual(snapshot.error, "Detached HEAD")


if __name__ == "__main__":
    unittest.main()
