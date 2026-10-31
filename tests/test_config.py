import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from ado_builds import config


class LoadSettingsTest(unittest.TestCase):
    def load(self, files=None, env=None):
        with tempfile.TemporaryDirectory() as tmp:
            for name, text in (files or {}).items():
                (Path(tmp) / name).write_text(text)
            environ = {"HERDR_PLUGIN_CONFIG_DIR": tmp, **(env or {})}
            with mock.patch.dict(os.environ, environ, clear=True):
                return config.load_settings()

    def test_defaults_without_config_dir(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            settings = config.load_settings()
        self.assertEqual(settings, config.Settings())

    def test_clamps(self):
        settings = self.load({"config.toml": "poll_seconds = 1\ntop_builds = 1000\n"})
        self.assertEqual((settings.poll_seconds, settings.top_builds), (config.MIN_POLL_SECONDS, config.MAX_TOP_BUILDS))
        self.assertIsNone(settings.error)

    def test_invalid_toml(self):
        settings = self.load({"config.toml": "poll_seconds = ["})
        self.assertIn("Invalid config.toml", settings.error)
        self.assertEqual(settings.poll_seconds, config.DEFAULT_POLL_SECONDS)

    def test_bad_types(self):
        self.assertIn("poll_seconds", self.load({"config.toml": 'poll_seconds = "fast"'}).error)
        self.assertIn("notify", self.load({"config.toml": 'notify = "loud"'}).error)

    def test_new_options(self):
        settings = self.load({"config.toml": 'notify = "failures"\nremote = "ado"\n'})
        self.assertEqual((settings.notify, settings.remote), ("failures", "ado"))

    def test_pat_cmd(self):
        self.assertEqual(self.load({"config.toml": 'pat_cmd = " get-pat "'}).pat_cmd, "get-pat")
        self.assertIn("pat_cmd", self.load({"config.toml": "pat_cmd = 3"}).error)

    def test_pat_files(self):
        settings = self.load({"pat": "default\n", "pat.My-Org": "specific", "pat~": "backup", "pat.empty": " "})
        self.assertEqual(settings.pats, {"": "default", "my-org": "specific"})

    def test_env_pat_is_lowest_priority(self):
        settings = self.load({"pat": "file"}, {config.PAT_ENV: "env"})
        self.assertEqual((settings.pats, settings.env_pat), ({"": "file"}, "env"))


if __name__ == "__main__":
    unittest.main()
