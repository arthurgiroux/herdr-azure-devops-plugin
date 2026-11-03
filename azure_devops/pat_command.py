"""Fetch a PAT by running the user's `pat_cmd`."""

import os
import subprocess

from . import config


def run(command: str, org: str) -> str | None:
    """Run the command through the shell with AZURE_DEVOPS_ORG set; return its trimmed stdout or None."""
    try:
        proc = subprocess.run(
            ["sh", "-c", command], capture_output=True, text=True,
            timeout=config.HTTP_TIMEOUT_SECONDS, env={**os.environ, config.ORG_ENV: org},
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return proc.stdout.strip() or None if proc.returncode == 0 else None
