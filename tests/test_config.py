"""Configuration loading, defaults, and validation."""
from microwrap import microwrap as app
from tests.helpers import ConfigTestCase


class ConfigTest(ConfigTestCase):
    def test_defaults(self):
        config = self.config({})
        self.assertEqual(config.get_host(), "0.0.0.0")
        self.assertEqual(config.get_port(), 80)
        self.assertTrue(config.get_concurrent())
        self.assertIsNone(config.get_executable_path())
        self.assertEqual(config.get_allowed_params(), [])
        self.assertEqual(config.get_default_params(), {})
        self.assertIsNone(config.get_argument_templates())
        self.assertIsNone(config.get_timeout())

    def test_explicit_settings(self):
        config = self.config(
            {
                "host": "127.0.0.1",
                "port": 8080,
                "concurrent": False,
                "executablePath": "/opt/program",
                "allowedParameters": ["input"],
                "defaultParameters": {"input": "default.json"},
                "argumentTemplates": ["{input}"],
                "timeoutSeconds": 2.5,
            }
        )
        self.assertEqual(config.get_host(), "127.0.0.1")
        self.assertEqual(config.get_port(), 8080)
        self.assertFalse(config.get_concurrent())
        self.assertEqual(config.get_executable_path(), "/opt/program")
        self.assertEqual(config.get_allowed_params(), ["input"])
        self.assertEqual(config.get_default_params(), {"input": "default.json"})
        self.assertEqual(config.get_argument_templates(), ["{input}"])
        self.assertEqual(config.get_timeout(), 2.5)

    def test_rejects_non_object_configuration(self):
        for value in ([], "text", 42, True, None):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, "Invalid configuration"):
                    self.config(value)

    def test_rejects_malformed_json(self):
        self.config_path.write_text("{invalid", encoding="utf-8")
        with self.assertRaises(ValueError):
            app.Config(str(self.config_path))

    def test_missing_configuration_file(self):
        with self.assertRaises(FileNotFoundError):
            app.Config(str(self.config_path))

    def test_rejects_invalid_argument_templates(self):
        for value in ("{input}", {}, 42, True, ["valid", 42], [None]):
            with self.subTest(value=value):
                config = self.config({"argumentTemplates": value})
                with self.assertRaisesRegex(ValueError, "array of strings"):
                    config.get_argument_templates()

    def test_accepts_empty_or_null_argument_templates(self):
        for value in ([], None):
            with self.subTest(value=value):
                config = self.config({"argumentTemplates": value})
                self.assertEqual(config.get_argument_templates(), value)

    def test_rejects_invalid_timeouts(self):
        for value in (0, -1, True, False, "5", [], float("inf"), float("nan")):
            with self.subTest(value=value):
                config = self.config({"timeoutSeconds": value})
                with self.assertRaisesRegex(ValueError, "positive finite number"):
                    config.get_timeout()

    def test_accepts_positive_or_null_timeouts(self):
        for value in (1, 0.25, None):
            with self.subTest(value=value):
                config = self.config({"timeoutSeconds": value})
                self.assertEqual(config.get_timeout(), value)
