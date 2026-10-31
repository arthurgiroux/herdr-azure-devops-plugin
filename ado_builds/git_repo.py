"""Find the Azure DevOps repo and branch of a directory."""

import re
import subprocess
from dataclasses import dataclass
from urllib.parse import unquote

REMOTE_PATTERNS = (
    re.compile(r"^https://(?:[^@/]+@)?dev\.azure\.com/([^/]+)/([^/]+)/_git/([^/?#]+)"),
    re.compile(r"^(?:ssh://)?[^@]+@(?:vs-)?ssh\.(?:dev\.azure\.com|visualstudio\.com):(?:22/)?v3/([^/]+)/([^/]+)/([^/?#]+)"),
    re.compile(r"^https://(?:[^@/]+@)?([^./]+)\.visualstudio\.com/(?:DefaultCollection/)?([^/]+)/_git/([^/?#]+)"),
)
DEFAULT_REMOTE = "origin"


class RepoError(Exception):
    pass


@dataclass(frozen=True)
class RepoRef:
    org: str
    project: str
    repo: str
    branch: str


def parse_remote(url: str) -> tuple[str, str, str] | None:
    for pattern in REMOTE_PATTERNS:
        match = pattern.match(url.strip())
        if match:
            org, project, repo = (unquote(part) for part in match.groups())
            return org, project, repo.removesuffix(".git")
    return None


def _git(cwd: str, *args: str) -> str | None:
    try:
        proc = subprocess.run(["git", "-C", cwd, *args], capture_output=True, text=True)
    except FileNotFoundError as err:
        raise RepoError("git not found; install git") from err
    except OSError as err:
        raise RepoError(f"Cannot run git in {cwd}: {err}") from err
    return proc.stdout.strip() if proc.returncode == 0 else None


def _upstream(cwd: str) -> tuple[str, str] | None:
    """Remote and branch the current branch tracks, if any."""
    branch = _git(cwd, "branch", "--show-current")
    if not branch:
        return None
    remote = _git(cwd, "config", "--get", f"branch.{branch}.remote")
    merge = _git(cwd, "config", "--get", f"branch.{branch}.merge")
    if not remote or not merge:
        return None
    return remote, merge.removeprefix("refs/heads/")


def _choose_remote(cwd: str, preferred: str | None, upstream: tuple[str, str] | None) -> tuple[str, tuple[str, str, str]]:
    names = (_git(cwd, "remote") or "").split()
    candidates = [preferred] if preferred else [upstream[0] if upstream else None, DEFAULT_REMOTE, *names]
    seen = set()
    for name in candidates:
        if not name or name in seen:
            continue
        seen.add(name)
        url = _git(cwd, "remote", "get-url", name)
        parts = parse_remote(url) if url else None
        if parts:
            return name, parts
    if preferred:
        raise RepoError(f"Remote '{preferred}' is not an Azure DevOps remote")
    raise RepoError("No Azure DevOps remote found" if names else "No git remote configured")


def repo_ref(cwd: str, remote: str | None = None) -> RepoRef:
    if _git(cwd, "rev-parse", "--is-inside-work-tree") != "true":
        raise RepoError(f"Not a git repository: {cwd}")
    current = _git(cwd, "branch", "--show-current")
    if not current:
        raise RepoError("Detached HEAD; check out a branch")
    upstream = _upstream(cwd)
    name, parts = _choose_remote(cwd, remote, upstream)
    branch = upstream[1] if upstream and upstream[0] == name else current
    return RepoRef(*parts, branch=branch)
