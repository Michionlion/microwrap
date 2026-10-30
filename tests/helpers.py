"""Shared fixtures for configuration and executable tests."""
import json
import tempfile
import unittest
from pathlib import Path

from microwrap import microwrap as app


class ConfigTestCase(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.config_path = Path(self.directory.name, "microwrap.json")

    def config(self, configuration):
        self.config_path.write_text(json.dumps(configuration), encoding="utf-8")
        return app.Config(str(self.config_path))

    def request(self, configuration, query=""):
        return app.InvocationRequest(
            self.config(configuration), {"QUERY_STRING": query}
        )

    def executable(self, source):
        path = Path(self.directory.name, "program.py")
        path.write_text("#!/usr/bin/env python3\n" + source, encoding="utf-8")
        path.chmod(0o755)
        return str(path)
