"""Constants and user config."""

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_PLUGIN_ID = "arthurgiroux.azure-devops"
PLUGIN_ID = os.environ.get("HERDR_PLUGIN_ID") or DEFAULT_PLUGIN_ID
PANE_ENTRYPOINT = "builds"
CWD_ENV = "AZURE_DEVOPS_CWD"
CONFIG_FILE = "config.toml"
PAT_FILE = "pat"
PAT_ENV = "AZURE_DEVOPS_EXT_PAT"
ORG_ENV = "AZURE_DEVOPS_ORG"

AZURE_DEVOPS_RESOURCE_ID = "499b84ac-1321-427f-aa17-267ca6a8da0e"
API_VERSION = "7.1"
TOKEN_MARGIN_SECONDS = 300
HTTP_TIMEOUT_SECONDS = 20

DEFAULT_POLL_SECONDS = 15
MIN_POLL_SECONDS = 5
DEFAULT_TOP_BUILDS = 15
MIN_TOP_BUILDS = 1
MAX_TOP_BUILDS = 100

NOTIFY_ALL = "all"
NOTIFY_FAILURES = "failures"
NOTIFY_OFF = "off"
NOTIFY_MODES = (NOTIFY_ALL, NOTIFY_FAILURES, NOTIFY_OFF)


@dataclass(frozen=True)
class Settings:
    poll_seconds: int = DEFAULT_POLL_SECONDS
    top_builds: int = DEFAULT_TOP_BUILDS
    notify: str = NOTIFY_ALL
    remote: str | None = None
    pat_cmd: str | None = None
    pats: dict[str, str] = field(default_factory=dict)
    env_pat: str | None = None
    error: str | None = None


def _clamp(value: int, low: int, high: int) -> int:
    return max(low, min(high, value))


def _int_option(data: dict, key: str, default: int) -> int:
    value = data.get(key, default)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"'{key}' must be an integer")
    return value


def _read_pats(config_dir: Path) -> dict[str, str]:
    # Files: "pat" (default), "pat.<org>" (per org).
    pats = {}
    for pat_path in config_dir.glob(f"{PAT_FILE}*"):
        suffix = pat_path.name.removeprefix(PAT_FILE)
        if suffix and not suffix.startswith("."):
            continue
        if not pat_path.is_file():
            continue
        try:
            token = pat_path.read_text().strip()
        except (OSError, UnicodeDecodeError):
            continue
        if token:
            pats[suffix.removeprefix(".").lower()] = token
    return pats


def _parse_options(data: dict) -> dict:
    notify = data.get("notify", NOTIFY_ALL)
    if notify not in NOTIFY_MODES:
        raise ValueError(f"'notify' must be one of {', '.join(NOTIFY_MODES)}")
    remote = data.get("remote")
    if remote is not None and not isinstance(remote, str):
        raise ValueError("'remote' must be a string")
    pat_cmd = data.get("pat_cmd")
    if pat_cmd is not None and not isinstance(pat_cmd, str):
        raise ValueError("'pat_cmd' must be a string")
    return {
        "poll_seconds": _clamp(_int_option(data, "poll_seconds", DEFAULT_POLL_SECONDS), MIN_POLL_SECONDS, 86400),
        "top_builds": _clamp(_int_option(data, "top_builds", DEFAULT_TOP_BUILDS), MIN_TOP_BUILDS, MAX_TOP_BUILDS),
        "notify": notify,
        "remote": remote or None,
        "pat_cmd": (pat_cmd or "").strip() or None,
    }


def load_settings() -> Settings:
    config_dir = os.environ.get("HERDR_PLUGIN_CONFIG_DIR")
    pats = _read_pats(Path(config_dir)) if config_dir else {}
    env_pat = os.environ.get(PAT_ENV, "").strip() or None
    if not config_dir:
        return Settings(pats=pats, env_pat=env_pat)
    path = Path(config_dir) / CONFIG_FILE
    if not path.is_file():
        return Settings(pats=pats, env_pat=env_pat)
    try:
        with path.open("rb") as handle:
            options = _parse_options(tomllib.load(handle))
    except tomllib.TOMLDecodeError as err:
        return Settings(pats=pats, env_pat=env_pat, error=f"Invalid {CONFIG_FILE}: {err}")
    except ValueError as err:
        return Settings(pats=pats, env_pat=env_pat, error=f"Invalid {CONFIG_FILE}: {err}")
    except OSError as err:
        return Settings(pats=pats, env_pat=env_pat, error=f"Cannot read {CONFIG_FILE}: {err}")
    return Settings(pats=pats, env_pat=env_pat, **options)
