"""B9.30 user-level packaging and bootstrap tests."""

import importlib
from importlib.metadata import PackageNotFoundError
import io
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

from app.compatibility import default_config_path, load_config
from app.model_store import default_models_directory
from app.version import get_version


class VersionResolutionTests(unittest.TestCase):
    def test_declared_version_is_resolved(self):
        self.assertEqual(get_version(), "0.1.0")

    def test_metadata_unavailable_uses_source_fallback(self):
        with mock.patch("app.version.importlib.metadata.version", side_effect=PackageNotFoundError):
            self.assertEqual(get_version(), "0.1.0")


class UserPathResolutionTests(unittest.TestCase):
    def test_config_path_uses_xdg_without_creating_it(self):
        with tempfile.TemporaryDirectory() as directory:
            with mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": directory}, clear=False):
                path = default_config_path()
            self.assertEqual(path, Path(directory) / "castlearq" / "config.toml")
            self.assertFalse(path.parent.exists())

    def test_config_missing_uses_defaults_independent_of_cwd(self):
        with tempfile.TemporaryDirectory() as directory:
            with mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": directory, "HOME": directory}, clear=False):
                with mock.patch("pathlib.Path.cwd", return_value=Path("/")):
                    config = load_config()
        self.assertEqual(config.safety_margin, 1.20)

    def test_model_store_path_uses_xdg_and_legacy_priority(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            new = root / "data" / "castlearq" / "models"
            legacy = root / "home" / ".local" / "share" / "localai-hub" / "models"
            legacy.mkdir(parents=True)
            with mock.patch.dict(os.environ, {"XDG_DATA_HOME": str(root / "data"), "HOME": str(root / "home")}, clear=False):
                self.assertEqual(default_models_directory(), legacy)
                new.mkdir(parents=True)
                self.assertEqual(default_models_directory(), new)
            self.assertFalse((root / "data" / "castlearq" / "config.toml").exists())


if __name__ == "__main__":
    unittest.main()
