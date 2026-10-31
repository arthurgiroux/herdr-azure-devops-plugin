"""Track builds and report state changes."""

import json
import os
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone

from . import config, git_repo, herdr_client
from .ado_client import AdoClient, AdoError, Build, branch_url
from .git_repo import RepoError, RepoRef
from .herdr_client import HerdrError

STATUS_COMPLETED = "completed"
RESULT_SUCCEEDED = "succeeded"
SOUND_DONE = "done"
SOUND_ALERT = "request"

Notifier = Callable[[str, str, str], None]


@dataclass
class Snapshot:
    ref: RepoRef | None = None
    builds: list[Build] = field(default_factory=list)
    error: str | None = None
    updated: datetime | None = None
    web_url: str = ""


def source_cwd() -> str:
    """Find the directory of the workspace pane."""
    if cwd := os.environ.get(config.CWD_ENV):
        return cwd
    try:
        context = json.loads(os.environ.get("HERDR_PLUGIN_CONTEXT_JSON") or "{}")
    except json.JSONDecodeError:
        context = {}
    pane_id = context.get("focused_pane_id") or context.get("pane_id") or os.environ.get("HERDR_PANE_ID")
    if pane_id:
        try:
            return herdr_client.pane_cwd(pane_id) or os.getcwd()
        except HerdrError:
            pass
    return os.getcwd()


def open_build_pane() -> None:
    pane_id = os.environ.get("HERDR_PANE_ID")
    try:
        herdr_client.open_plugin_pane(pane_id, {config.CWD_ENV: source_cwd()})
    except HerdrError as err:
        print(f"ado-builds: {err}", file=sys.stderr)
        sys.exit(1)


class BuildTracker:
    def __init__(self, cwd: str, top: int, client: AdoClient,
                 notify: Notifier = herdr_client.show_toast,
                 notify_mode: str = config.NOTIFY_ALL, remote: str | None = None) -> None:
        self._cwd = cwd
        self._top = top
        self._client = client
        self._notify = notify
        self._notify_mode = notify_mode
        self._remote = remote
        self._known: dict[int, str] | None = None
        self._ref: RepoRef | None = None

    def poll(self) -> Snapshot:
        now = datetime.now(timezone.utc)
        try:
            ref = git_repo.repo_ref(self._cwd, self._remote)
        except RepoError as err:
            return Snapshot(error=str(err), updated=now)
        if ref != self._ref:
            self._ref, self._known = ref, None
        try:
            builds = self._client.list_builds(ref, self._top)
        except AdoError as err:
            return Snapshot(ref=ref, error=str(err), updated=now, web_url=branch_url(ref))
        except Exception as err:  # keep the pane alive
            return Snapshot(ref=ref, error=f"Unexpected error: {err}", updated=now, web_url=branch_url(ref))
        self._report_finished(builds)
        return Snapshot(ref=ref, builds=builds, updated=now, web_url=branch_url(ref))

    def _report_finished(self, builds: list[Build]) -> None:
        previous = self._known
        self._known = {build.id: build.status for build in builds}
        if previous is None:
            return
        for build in builds:
            was = previous.get(build.id)
            if was and was != STATUS_COMPLETED and build.status == STATUS_COMPLETED:
                self._toast(build)

    def _toast(self, build: Build) -> None:
        result = build.result or STATUS_COMPLETED
        if self._notify_mode == config.NOTIFY_OFF:
            return
        if self._notify_mode == config.NOTIFY_FAILURES and result == RESULT_SUCCEEDED:
            return
        sound = SOUND_DONE if result == RESULT_SUCCEEDED else SOUND_ALERT
        try:
            self._notify(f"Build {result}", f"{build.pipeline} {build.number}", sound)
        except HerdrError:
            pass

