"""Read PATs from the macOS Keychain."""

import subprocess
import sys

from . import config


def lookup(account: str) -> str | None:
    """Return the generic password for the service and account, or None."""
    if sys.platform != "darwin":
        return None
    try:
        proc = subprocess.run(
            ["security", "find-generic-password", "-s", config.KEYCHAIN_SERVICE, "-a", account, "-w"],
            capture_output=True, text=True, timeout=config.HTTP_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return proc.stdout.strip() or None if proc.returncode == 0 else None
