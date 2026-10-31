"""Entry: 'open' action or 'watch' pane."""

import sys

MIN_PYTHON = (3, 11)
COMMAND_OPEN = "open"


def main() -> None:
    if sys.version_info < MIN_PYTHON:
        required = ".".join(map(str, MIN_PYTHON))
        sys.exit(f"ado-builds requires Python {required} or later (found {sys.version.split()[0]})")
    from . import config, service, ui
    from .ado_client import AdoClient

    if sys.argv[1:2] == [COMMAND_OPEN]:
        service.open_build_pane()
        return
    settings = config.load_settings()
    client = AdoClient(settings.pats, settings.env_pat)
    tracker = service.BuildTracker(
        service.source_cwd(), settings.top_builds, client,
        notify_mode=settings.notify, remote=settings.remote,
    )
    ui.run(tracker, settings.poll_seconds, settings.error)


if __name__ == "__main__":
    main()
