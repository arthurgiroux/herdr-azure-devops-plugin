import base64
import io
import json
import unittest
import urllib.error
from datetime import datetime, timezone
from unittest import mock

from ado_builds.ado_client import AdoClient, AdoError, to_build

ITEM = {
    "id": 42,
    "buildNumber": "20261028.3",
    "status": "completed",
    "result": "failed",
    "queueTime": "2026-10-28T14:00:00.1234567Z",
    "startTime": "2026-10-28T14:00:05Z",
    "finishTime": "2026-10-28T14:03:05.5Z",
    "definition": {"name": "CI"},
    "_links": {"web": {"href": "https://dev.azure.com/o/p/_build/results?buildId=42"}},
}


class ToBuildTest(unittest.TestCase):
    def test_maps_fields(self):
        build = to_build(ITEM)
        self.assertEqual((build.id, build.pipeline, build.result), (42, "CI", "failed"))
        self.assertEqual(build.started, datetime(2026, 10, 28, 14, 0, 5, tzinfo=timezone.utc))
        self.assertEqual(build.queued.microsecond, 123456)
        self.assertTrue(build.url.endswith("buildId=42"))


class FakeResponse(io.BytesIO):
    def __init__(self, body, status=200):
        super().__init__(body)
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def http_error(code):
    return urllib.error.HTTPError("https://x", code, "err", {}, None)


class GetTest(unittest.TestCase):
    def get(self, client=None, **urlopen):
        client = client or AdoClient({"": "tok"})
        with mock.patch("urllib.request.urlopen", **urlopen):
            return client._get("org", "p/_apis/x", {})

    def test_basic_auth_for_pat_and_org_override(self):
        client = AdoClient({"": "a", "org": "b"})
        expected = "Basic " + base64.b64encode(b":b").decode()
        self.assertEqual(client._auth_header("Org"), expected)
        self.assertTrue(AdoClient({"": "a"})._auth_header("other").startswith("Basic "))

    def test_ok(self):
        self.assertEqual(self.get(return_value=FakeResponse(json.dumps({"a": 1}).encode())), {"a": 1})

    def test_error_mapping(self):
        cases = {401: "invalid or expired", 403: "Build (Read)", 404: "Not found", 500: "temporarily unavailable", 429: "temporarily unavailable"}
        for code, text in cases.items():
            with self.subTest(code=code):
                with self.assertRaises(AdoError) as ctx:
                    self.get(side_effect=http_error(code))
                self.assertIn(text, str(ctx.exception))
                self.assertIn("org", str(ctx.exception))

    def test_401_without_pat_mentions_az_login(self):
        with self.assertRaises(AdoError) as ctx:
            with mock.patch.object(AdoClient, "_bearer", return_value="t"):
                self.get(AdoClient(), side_effect=http_error(401))
        self.assertIn("az login", str(ctx.exception))

    def test_203_is_auth_failure(self):
        with self.assertRaises(AdoError) as ctx:
            self.get(return_value=FakeResponse(b"{}", status=203))
        self.assertIn("invalid or expired", str(ctx.exception))

    def test_html_body_is_auth_failure(self):
        with self.assertRaises(AdoError) as ctx:
            self.get(return_value=FakeResponse(b"<html>sign in</html>"))
        self.assertIn("invalid or expired", str(ctx.exception))


class PatPrecedenceTest(unittest.TestCase):
    def pat(self, cmd_result, pats=None, env=None, cmd="get-pat"):
        client = AdoClient(pats or {}, env, cmd)
        with mock.patch("ado_builds.pat_command.run", return_value=cmd_result):
            return client._pat("Org")

    def test_order(self):
        self.assertEqual(self.pat("cmd", {"org": "file-org", "": "file"}, "env"), "file-org")
        self.assertEqual(self.pat("cmd", {"": "file"}, "env"), "cmd")
        self.assertEqual(self.pat(None, {"": "file"}, "env"), "file")
        self.assertEqual(self.pat(None, {}, "env"), "env")
        self.assertIsNone(self.pat(None))

    def test_no_command_configured(self):
        self.assertIsNone(self.pat("cmd", cmd=None))

    def test_command_receives_lowercased_org(self):
        client = AdoClient(pat_cmd="get-pat")
        with mock.patch("ado_builds.pat_command.run", return_value="t") as run:
            client._pat("Org")
            client._pat("Org")
        run.assert_called_once_with("get-pat", "org")


class PatCommandTest(unittest.TestCase):
    def test_runs_through_shell_with_org_env(self):
        from ado_builds import pat_command
        self.assertEqual(pat_command.run('printf "tok-$ADO_ORG\\n"', "my-org"), "tok-my-org")

    def test_failure_and_empty_output(self):
        from ado_builds import pat_command
        self.assertIsNone(pat_command.run("exit 3", "o"))
        self.assertIsNone(pat_command.run("true", "o"))


class BearerTest(unittest.TestCase):
    def test_az_missing(self):
        with mock.patch("subprocess.run", side_effect=FileNotFoundError):
            with self.assertRaises(AdoError) as ctx:
                AdoClient()._bearer()
        self.assertIn("Azure CLI not found", str(ctx.exception))

    def test_bad_json_and_missing_token(self):
        for out in ("nope", "{}"):
            proc = mock.Mock(returncode=0, stdout=out, stderr="")
            with mock.patch("subprocess.run", return_value=proc):
                with self.assertRaises(AdoError):
                    AdoClient()._bearer()

    def test_expires_on_iso_fallback(self):
        out = json.dumps({"accessToken": "t", "expiresOn": "2099-01-01 00:00:00.000000"})
        with mock.patch("subprocess.run", return_value=mock.Mock(returncode=0, stdout=out, stderr="")):
            client = AdoClient()
            self.assertEqual(client._bearer(), "t")
        self.assertGreater(client._token_expiry, 4_000_000_000)


if __name__ == "__main__":
    unittest.main()
