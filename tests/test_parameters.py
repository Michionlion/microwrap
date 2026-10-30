"""Query filtering, defaults, and URL decoding."""
from microwrap import microwrap as app
from tests.helpers import ConfigTestCase


class ParameterTest(ConfigTestCase):
    def test_ignores_unlisted_query_parameters(self):
        config = self.config({"allowedParameters": ["allowed"]})
        self.assertEqual(
            app.parse_query_params(config, "allowed=yes&ignored=no"),
            {"allowed": "yes"},
        )

    def test_no_parameters_are_allowed_by_default(self):
        self.assertEqual(app.parse_query_params(self.config({}), "option=value"), {})

    def test_defaults_apply_without_query_parameters(self):
        config = self.config(
            {"defaultParameters": {"option": "default", "flag": True, "off": False}}
        )
        self.assertEqual(
            app.parse_query_params(config, ""), {"option": "default", "flag": ""}
        )

    def test_only_allowed_query_parameters_override_defaults(self):
        config = self.config(
            {
                "allowedParameters": ["option"],
                "defaultParameters": {"option": "default", "fixed": "original"},
            }
        )
        self.assertEqual(
            app.parse_query_params(config, "option=override&fixed=changed"),
            {"option": "override", "fixed": "original"},
        )

    def test_last_repeated_value_wins(self):
        config = self.config({"allowedParameters": ["option"]})
        self.assertEqual(
            app.parse_query_params(config, "option=first&option=last"),
            {"option": "last"},
        )

    def test_blank_values_and_flags_are_preserved(self):
        config = self.config({"allowedParameters": ["flag", "empty"]})
        self.assertEqual(
            app.parse_query_params(config, "flag&empty="), {"flag": "", "empty": ""}
        )

    def test_decodes_spaces_unicode_and_reserved_characters(self):
        config = self.config({"allowedParameters": ["input"]})
        self.assertEqual(
            app.parse_query_params(config, "input=caf%C3%A9+%26+tea%2Bmilk"),
            {"input": "café & tea+milk"},
        )
