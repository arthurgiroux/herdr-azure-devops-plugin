"""Entry: 'builds' action or 'watch' pane."""

import os
import sys

MIN_PYTHON = (3, 11)
COMMAND_BUILDS = "builds"


def main() -> None:
    if sys.version_info < MIN_PYTHON:
        required = ".".join(map(str, MIN_PYTHON))
        sys.exit(f"azure-devops requires Python {required} or later (found {sys.version.split()[0]})")
    from . import config, demo, service, ui
    from .azure_devops_client import AzureDevOpsClient

    if sys.argv[1:2] == [COMMAND_BUILDS]:
        service.open_build_pane()
        return
    if os.environ.get(demo.DEMO_ENV):
        ui.run(demo.DemoTracker(), config.DEFAULT_POLL_SECONDS)
        return
    settings = config.load_settings()
    client = AzureDevOpsClient(settings.pats, settings.env_pat, settings.pat_cmd)
    tracker = service.BuildTracker(
        service.source_cwd(), settings.top_builds, client,
        notify_mode=settings.notify, remote=settings.remote,
    )
    ui.run(tracker, settings.poll_seconds, settings.error)


if __name__ == "__main__":
    main()
