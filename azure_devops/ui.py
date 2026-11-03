"""Render the build table in the pane."""

import select
import shutil
import signal
import sys
import termios
import tty
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from .azure_devops_client import Build
from .service import SCOPE_BRANCH, SCOPE_PROJECT, BuildTracker, Snapshot

ESC = "\033"
RESET = f"{ESC}[0m"
BOLD = f"{ESC}[1m"
DIM = f"{ESC}[2m"
HOME = f"{ESC}[H"
CLEAR_LINE = f"{ESC}[K"
CLEAR_BELOW = f"{ESC}[J"
HIDE_CURSOR = f"{ESC}[?25l"
SHOW_CURSOR = f"{ESC}[?25h"
GREEN = f"{ESC}[32m"
RED = f"{ESC}[31m"
YELLOW = f"{ESC}[33m"
CYAN = f"{ESC}[36m"
GREY = f"{ESC}[90m"

KEY_QUIT = "q"
KEY_REFRESH = "r"
KEY_SCOPE = "a"
KEY_REDRAW = ""
KEY_EOF = "\0eof"
ELLIPSIS = "…"
SECONDS_PER_MINUTE = 60
SECONDS_PER_HOUR = 3600
SECONDS_PER_DAY = 86400


@dataclass(frozen=True)
class Style:
    icon: str
    color: str


STYLES = {
    "succeeded": Style("✔", GREEN),
    "partiallySucceeded": Style("◐", YELLOW),
    "failed": Style("✘", RED),
    "canceled": Style("⊘", GREY),
    "inProgress": Style("●", YELLOW),
    "notStarted": Style("○", CYAN),
}
UNKNOWN_STYLE = Style("?", GREY)

# Column widths; pipeline takes the rest.
STATUS_WIDTH = 1
BUILD_WIDTH = 11
BY_WIDTH = 14
TIME_WIDTH = 6
AGE_WIDTH = 5
MIN_PIPELINE_WIDTH = 10
BY_MIN_PIPELINE_WIDTH = 20
MIN_TITLE_ROOM = 40
GUTTER = 2
INDENT = " "
KEYS_HINT = "r refresh · a branch/all · q quit"


class Resized(Exception):
    pass


_waiting = False


def link(text: str, url: str) -> str:
    """OSC 8 hyperlink; Ctrl-click opens it."""
    return f"{ESC}]8;;{url}{ESC}\\{text}{ESC}]8;;{ESC}\\" if url else text


def fit(text: str, width: int) -> str:
    return text if len(text) <= width else text[: width - 1] + ELLIPSIS


def cell(text: str, width: int, right: bool = False) -> str:
    text = fit(text, width)
    return text.rjust(width) if right else text.ljust(width)


def short_span(span: timedelta) -> str:
    seconds = max(int(span.total_seconds()), 0)
    if seconds < SECONDS_PER_MINUTE:
        return f"{seconds}s"
    if seconds < SECONDS_PER_HOUR:
        return f"{seconds // SECONDS_PER_MINUTE}m{seconds % SECONDS_PER_MINUTE:02d}s"
    if seconds < SECONDS_PER_DAY:
        return f"{seconds // SECONDS_PER_HOUR}h{seconds % SECONDS_PER_HOUR // SECONDS_PER_MINUTE:02d}m"
    return f"{seconds // SECONDS_PER_DAY}d"


def layout(width: int) -> tuple[int, bool]:
    """Pipeline width; show 'by' column or not."""
    fixed = STATUS_WIDTH + BUILD_WIDTH + TIME_WIDTH + AGE_WIDTH + GUTTER * 4 + len(INDENT) * 2
    show_by = width - fixed - BY_WIDTH - GUTTER >= BY_MIN_PIPELINE_WIDTH
    rest = width - fixed - (BY_WIDTH + GUTTER if show_by else 0)
    return max(rest, MIN_PIPELINE_WIDTH), show_by


def header_row(pipeline_width: int, show_by: bool) -> str:
    gap = " " * GUTTER
    cols = [cell("", STATUS_WIDTH), cell("PIPELINE", pipeline_width), cell("BUILD", BUILD_WIDTH)]
    if show_by:
        cols.append(cell("BY", BY_WIDTH))
    cols += [cell("TIME", TIME_WIDTH, right=True), cell("AGE", AGE_WIDTH, right=True)]
    return f"{INDENT}{DIM}{gap.join(cols)}{RESET}"


def build_row(build: Build, now: datetime, pipeline_width: int, show_by: bool) -> str:
    style = STYLES.get(build.result or build.status, UNKNOWN_STYLE)
    gap = " " * GUTTER
    duration = short_span((build.finished or now) - build.started) if build.started else "-"
    age = short_span(now - build.queued) if build.queued else "-"
    cols = [
        f"{style.color}{style.icon}{RESET}",
        f"{BOLD}{link(cell(build.pipeline, pipeline_width), build.url)}{RESET}",
        link(cell(build.number, BUILD_WIDTH), build.url),
    ]
    if show_by:
        cols.append(f"{DIM}{cell(build.requested_by, BY_WIDTH)}{RESET}")
    cols += [cell(duration, TIME_WIDTH, right=True), f"{DIM}{cell(age, AGE_WIDTH, right=True)}{RESET}"]
    return INDENT + gap.join(cols)


def title_line(snapshot: Snapshot, width: int) -> str:
    """Repo and branch left, time and keys right."""
    updated = f"{snapshot.updated.astimezone():%H:%M:%S}" if snapshot.updated else ""
    right = f"{updated}  {KEYS_HINT}"
    if width - len(right) < MIN_TITLE_ROOM:
        right = updated
    if not snapshot.ref:
        return f"{INDENT}{DIM}{right}{RESET}"
    ref = snapshot.ref
    room = width - len(INDENT) * 2 - len(right) - GUTTER
    repo = fit(ref.repo, max(room // 2, MIN_PIPELINE_WIDTH))
    if snapshot.scope == SCOPE_PROJECT:
        repo = fit(ref.project, max(room // 2, MIN_PIPELINE_WIDTH))
        branch = "all builds"
    else:
        branch = fit(ref.branch, max(room - len(repo) - GUTTER - 2, MIN_PIPELINE_WIDTH))
    left_width = len(repo) + GUTTER + 2 + len(branch)
    pad = " " * max(width - len(INDENT) * 2 - left_width - len(right), GUTTER)
    repo_link = link(f"{BOLD}{repo}{RESET}", snapshot.web_url)
    marker = "" if snapshot.scope == SCOPE_PROJECT else "⎇ "
    return f"{INDENT}{repo_link}{' ' * GUTTER}{CYAN}{marker}{branch}{RESET}{pad}{DIM}{right}{RESET}"


def render(snapshot: Snapshot) -> str:
    width = shutil.get_terminal_size().columns
    now = datetime.now(timezone.utc)
    lines = [title_line(snapshot, width)]
    if snapshot.error:
        lines.append(f"{INDENT}{RED}✘ {snapshot.error}{RESET}")
    elif not snapshot.builds:
        where = "in this project" if snapshot.scope == SCOPE_PROJECT else "on this branch"
        lines.append(f"{INDENT}{DIM}No builds {where} yet.{RESET}")
    else:
        pipeline_width, show_by = layout(width)
        lines.append(header_row(pipeline_width, show_by))
        lines.extend(build_row(build, now, pipeline_width, show_by) for build in snapshot.builds)
    return HOME + "".join(line + CLEAR_LINE + "\n" for line in lines) + CLEAR_BELOW


def on_resize(signum, frame) -> None:
    # Interrupt only the key wait.
    if _waiting:
        raise Resized


def wait_key(seconds: float) -> str | None:
    global _waiting
    _waiting = True
    try:
        ready, _, _ = select.select([sys.stdin], [], [], seconds)
    except Resized:
        return KEY_REDRAW
    finally:
        _waiting = False
    if not ready:
        return None
    return sys.stdin.read(1) or KEY_EOF


def poll(tracker: BuildTracker, config_error: str | None, scope: str) -> Snapshot:
    snapshot = tracker.poll(scope)
    if config_error:
        snapshot.error = config_error
    return snapshot


def run(tracker: BuildTracker, poll_seconds: int, config_error: str | None = None) -> None:
    if not sys.stdin.isatty():
        sys.exit("azure-devops: stdin is not a terminal; run it as a herdr pane")
    fd = sys.stdin.fileno()
    saved = termios.tcgetattr(fd)
    tty.setcbreak(fd)
    signal.signal(signal.SIGWINCH, on_resize)
    sys.stdout.write(HIDE_CURSOR)
    try:
        scope = SCOPE_BRANCH
        snapshot = poll(tracker, config_error, scope)
        while True:
            sys.stdout.write(render(snapshot))
            sys.stdout.flush()
            key = wait_key(poll_seconds)
            if key in (KEY_QUIT, KEY_EOF):
                return
            if key == KEY_SCOPE:
                scope = SCOPE_BRANCH if scope == SCOPE_PROJECT else SCOPE_PROJECT
            if key is None or key in (KEY_REFRESH, KEY_SCOPE):
                snapshot = poll(tracker, config_error, scope)
    except KeyboardInterrupt:
        pass
    finally:
        signal.signal(signal.SIGWINCH, signal.SIG_DFL)
        sys.stdout.write(SHOW_CURSOR)
        termios.tcsetattr(fd, termios.TCSADRAIN, saved)
