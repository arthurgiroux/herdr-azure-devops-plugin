"""Dummy data for screenshots."""

from datetime import datetime, timedelta, timezone

from .azure_devops_client import Build, branch_url, project_url
from .git_repo import RepoRef
from .service import SCOPE_PROJECT, Snapshot

DEMO_ENV = "AZURE_DEVOPS_DEMO"
DEMO_REF = RepoRef("contoso", "Storefront", "web-app", "feature/checkout")
DEMO_URL = "https://example.com/build"

# pipeline, build number, status, result, queued min ago, run min, requester
BRANCH_ROWS = (
    ("CI", "20261102.7", "inProgress", None, 2, 2, "Alex Martin"),
    ("Deploy staging", "20261102.3", "notStarted", None, 1, 0, "Alex Martin"),
    ("CI", "20261102.6", "completed", "succeeded", 35, 7, "Alex Martin"),
    ("Integration tests", "20261102.2", "completed", "partiallySucceeded", 90, 21, "Sam Lee"),
    ("CI", "20261102.5", "completed", "failed", 200, 6, "Alex Martin"),
    ("Lint", "20261101.4", "completed", "succeeded", 1500, 2, "Jo Rivera"),
    ("CI", "20261101.3", "completed", "canceled", 1600, 1, "Jo Rivera"),
    ("CI", "20261031.9", "completed", "succeeded", 3000, 8, "Alex Martin"),
)
PROJECT_ROWS = (
    ("Release", "20261102.11", "inProgress", None, 4, 4, "Sam Lee"),
    ("CI", "20261102.10", "completed", "succeeded", 12, 6, "Taylor Kim"),
    ("Nightly", "20261102.1", "completed", "failed", 400, 48, "Build Service"),
    ("Docs", "20261102.2", "completed", "succeeded", 600, 3, "Jo Rivera"),
    ("CI", "20261101.8", "completed", "succeeded", 1300, 7, "Taylor Kim"),
    ("Release", "20261101.2", "completed", "partiallySucceeded", 1800, 14, "Sam Lee"),
    ("Deploy staging", "20261031.5", "completed", "succeeded", 2900, 5, "Alex Martin"),
)


def build_from_row(index: int, row: tuple, now: datetime) -> Build:
    pipeline, number, status, result, queued_min, run_min, who = row
    queued = now - timedelta(minutes=queued_min)
    started = None if status == "notStarted" else queued + timedelta(seconds=20)
    finished = started + timedelta(minutes=run_min) if status == "completed" else None
    return Build(index, pipeline, number, status, result, queued, started, finished, DEMO_URL, who)


class DemoTracker:
    """Stands in for BuildTracker."""

    def poll(self, scope: str) -> Snapshot:
        now = datetime.now(timezone.utc)
        project = scope == SCOPE_PROJECT
        rows = PROJECT_ROWS if project else BRANCH_ROWS
        builds = [build_from_row(i, row, now) for i, row in enumerate(rows)]
        url = project_url(DEMO_REF) if project else branch_url(DEMO_REF)
        return Snapshot(ref=DEMO_REF, builds=builds, updated=now, web_url=url, scope=scope)
