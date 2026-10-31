"""Azure DevOps REST client."""

import base64
import json
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime

from . import config
from .git_repo import RepoRef

ADO_BASE_URL = "https://dev.azure.com"
HTTP_UNAUTHORIZED = 401
HTTP_FORBIDDEN = 403
HTTP_NOT_FOUND = 404
HTTP_TOO_MANY_REQUESTS = 429
HTTP_SERVER_ERROR = 500
HTTP_NON_AUTHORITATIVE = 203
FRACTION_DIGITS = 6


class AdoError(Exception):
    pass


@dataclass(frozen=True)
class Build:
    id: int
    pipeline: str
    number: str
    status: str
    result: str | None
    queued: datetime | None
    started: datetime | None
    finished: datetime | None
    url: str
    requested_by: str = ""


def parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    # ADO sends 7 fraction digits.
    head, _, frac = value.rstrip("Z").partition(".")
    if frac:
        head += "." + frac[:FRACTION_DIGITS]
    return datetime.fromisoformat(head + "+00:00")


def to_build(item: dict) -> Build:
    return Build(
        id=item["id"],
        pipeline=item.get("definition", {}).get("name", "?"),
        number=item.get("buildNumber", ""),
        status=item.get("status", ""),
        result=item.get("result"),
        queued=parse_time(item.get("queueTime")),
        started=parse_time(item.get("startTime")),
        finished=parse_time(item.get("finishTime")),
        url=item.get("_links", {}).get("web", {}).get("href", ""),
        requested_by=item.get("requestedFor", {}).get("displayName", ""),
    )


def _expiry(data: dict) -> float:
    fallback = time.time() + config.TOKEN_MARGIN_SECONDS * 2
    if value := data.get("expires_on"):
        try:
            return float(value)
        except (TypeError, ValueError):
            return fallback
    if value := data.get("expiresOn"):
        try:
            return datetime.fromisoformat(str(value)).astimezone().timestamp()
        except ValueError:
            return fallback
    return fallback


def branch_url(ref: RepoRef) -> str:
    project, repo = (urllib.parse.quote(part) for part in (ref.project, ref.repo))
    branch = urllib.parse.quote(ref.branch, safe="")
    return f"{ADO_BASE_URL}/{urllib.parse.quote(ref.org)}/{project}/_git/{repo}?version=GB{branch}"


class AdoClient:
    def __init__(self, pats: dict[str, str] | None = None) -> None:
        self._pats = pats or {}
        self._token: str | None = None
        self._token_expiry = 0.0
        self._repo_ids: dict[tuple[str, str, str], str] = {}

    def _bearer(self) -> str:
        if self._token and time.time() < self._token_expiry - config.TOKEN_MARGIN_SECONDS:
            return self._token
        try:
            proc = subprocess.run(
                ["az", "account", "get-access-token", "--resource", config.ADO_RESOURCE_ID, "-o", "json"],
                capture_output=True, text=True,
            )
        except FileNotFoundError as err:
            raise AdoError("Azure CLI not found; install it or configure a PAT") from err
        if proc.returncode != 0:
            reason = proc.stderr.strip().splitlines()[-1:] or ["no output"]
            raise AdoError(f"Azure CLI token failed: {reason[0]}")
        try:
            data = json.loads(proc.stdout)
            token = data["accessToken"]
        except (json.JSONDecodeError, KeyError, TypeError) as err:
            raise AdoError("Azure CLI returned an unexpected token response") from err
        self._token = token
        self._token_expiry = _expiry(data)
        return token

    def _auth_header(self, org: str) -> str:
        pat = self._pat(org)
        if pat:
            return "Basic " + base64.b64encode(f":{pat}".encode()).decode()
        return f"Bearer {self._bearer()}"

    def _pat(self, org: str) -> str | None:
        return self._pats.get(org.lower()) or self._pats.get("")

    def _auth_failure(self, org: str) -> AdoError:
        self._token = None
        if self._pat(org):
            return AdoError(f"Access denied for '{org}': the PAT is invalid or expired")
        return AdoError(f"Access denied for '{org}': run 'az login' or configure a PAT")

    def _get(self, org: str, path: str, params: dict[str, str | int]) -> dict:
        query = urllib.parse.urlencode({**params, "api-version": config.API_VERSION})
        url = f"{ADO_BASE_URL}/{urllib.parse.quote(org)}/{path}?{query}"
        request = urllib.request.Request(url, headers={"Authorization": self._auth_header(org)})
        try:
            with urllib.request.urlopen(request, timeout=config.HTTP_TIMEOUT_SECONDS) as response:
                if response.status == HTTP_NON_AUTHORITATIVE:
                    raise self._auth_failure(org)
                body = response.read()
        except urllib.error.HTTPError as err:
            raise self._http_error(org, path, err.code) from err
        except (urllib.error.URLError, TimeoutError) as err:
            raise AdoError(f"Network error: {err}") from err
        try:
            data = json.loads(body)
        except (json.JSONDecodeError, UnicodeDecodeError) as err:
            # ADO answers a bad PAT with an HTML sign-in page.
            raise self._auth_failure(org) from err
        if not isinstance(data, dict):
            raise AdoError(f"Unexpected response from Azure DevOps: {path}")
        return data

    def _http_error(self, org: str, path: str, code: int) -> AdoError:
        if code == HTTP_UNAUTHORIZED:
            return self._auth_failure(org)
        if code == HTTP_FORBIDDEN:
            return AdoError(f"Permission denied in '{org}': the account or PAT needs Build (Read) and Code (Read)")
        if code == HTTP_NOT_FOUND:
            return AdoError(f"Not found in '{org}': {path}")
        if code == HTTP_TOO_MANY_REQUESTS or code >= HTTP_SERVER_ERROR:
            return AdoError(f"Azure DevOps temporarily unavailable (HTTP {code}) for '{org}'")
        return AdoError(f"HTTP {code} from '{org}': {path}")

    def repo_id(self, ref: RepoRef) -> str:
        key = (ref.org, ref.project, ref.repo)
        if key not in self._repo_ids:
            path = f"{urllib.parse.quote(ref.project)}/_apis/git/repositories/{urllib.parse.quote(ref.repo)}"
            self._repo_ids[key] = self._get(ref.org, path, {})["id"]
        return self._repo_ids[key]

    def list_builds(self, ref: RepoRef, top: int) -> list[Build]:
        path = f"{urllib.parse.quote(ref.project)}/_apis/build/builds"
        data = self._get(ref.org, path, {
            "repositoryId": self.repo_id(ref),
            "repositoryType": "TfsGit",
            "branchName": f"refs/heads/{ref.branch}",
            "queryOrder": "queueTimeDescending",
            "$top": top,
        })
        return [to_build(item) for item in data.get("value", [])]
