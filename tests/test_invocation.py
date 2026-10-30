"""Argument construction and executable invocation."""
import json
from urllib.parse import urlencode
from unittest.mock import patch

from microwrap import microwrap as app
from tests.helpers import ConfigTestCase


class InvocationTest(ConfigTestCase):
    def test_default_options_and_flags(self):
        request = self.request(
            {
                "allowedParameters": ["option", "flag"],
                "defaultParameters": {"option": "default"},
            },
            "option=value&flag&ignored=no",
        )
        self.assertEqual(request.get_arguments(), ["--option", "value", "--flag"])

    def test_no_parameters_produce_no_arguments(self):
        self.assertEqual(self.request({}).get_arguments(), [])

    def test_default_flags_and_disabled_options(self):
        request = self.request(
            {"defaultParameters": {"flag": True, "off": False, "option": "value"}}
        )
        self.assertEqual(request.get_arguments(), ["--flag", "--option", "value"])

    def test_ordered_templates_keep_values_literal(self):
        request = self.request(
            {
                "allowedParameters": ["input", "output"],
                "argumentTemplates": ["{input}", "jsonOutputFile={output}"],
            },
            "output=%2Fshared%2Foutput.json&input=%2Fshared%2Fa+%24%28echo+no%29+%7Boutput%7D.json",
        )
        self.assertEqual(
            request.get_arguments(),
            [
                "/shared/a $(echo no) {output}.json",
                "jsonOutputFile=/shared/output.json",
            ],
        )

    def test_templates_use_defaults_and_allowed_overrides(self):
        request = self.request(
            {
                "allowedParameters": ["input"],
                "defaultParameters": {"input": "default", "config": "fixed"},
                "argumentTemplates": ["{input}", "configFile={config}", "literal"],
            },
            "input=override&config=ignored",
        )
        self.assertEqual(
            request.get_arguments(), ["override", "configFile=fixed", "literal"]
        )

    def test_templates_preserve_empty_arguments_and_escape_braces(self):
        request = self.request(
            {
                "allowedParameters": ["input"],
                "argumentTemplates": ["{input}", "{{literal}}"],
            },
            "input=",
        )
        self.assertEqual(request.get_arguments(), ["", "{literal}"])

    def test_repeated_template_parameters_are_not_appended(self):
        request = self.request(
            {
                "allowedParameters": ["input"],
                "argumentTemplates": ["{input}", "again={input}"],
            },
            "input=value",
        )
        self.assertEqual(request.get_arguments(), ["value", "again=value"])

    def test_nested_format_parameters_are_not_appended(self):
        request = self.request(
            {
                "defaultParameters": {"input": "file", "width": "8"},
                "argumentTemplates": ["{input:>{width}}", "{input[0]}"],
            }
        )
        self.assertEqual(request.get_arguments(), ["    file", "f"])

    def test_unreferenced_parameters_are_appended_after_templates(self):
        request = self.request(
            {
                "allowedParameters": ["output", "input", "missing"],
                "argumentTemplates": ["{input}"],
            },
            "input=file&output=result&ignored=no",
        )
        self.assertEqual(request.get_arguments(), ["file", "--output", "result"])
        self.assertEqual(request.get_arguments(), ["file", "--output", "result"])

    def test_unreferenced_defaults_use_allowed_overrides(self):
        request = self.request(
            {
                "allowedParameters": ["input", "output"],
                "defaultParameters": {
                    "output": "default",
                    "fixed": "original",
                    "off": False,
                },
                "argumentTemplates": ["{input}"],
            },
            "input=file&output=override&fixed=ignored",
        )
        self.assertEqual(
            request.get_arguments(),
            ["file", "--output", "override", "--fixed", "original"],
        )

    def test_escaped_braces_do_not_consume_parameters(self):
        request = self.request(
            {
                "defaultParameters": {"input": "file"},
                "argumentTemplates": ["{{input}}"],
            }
        )
        self.assertEqual(request.get_arguments(), ["{input}", "--input", "file"])

    def test_unreferenced_flags_and_blank_values_are_appended(self):
        request = self.request(
            {
                "defaultParameters": {"flag": True, "off": False},
                "allowedParameters": ["empty"],
                "argumentTemplates": ["literal"],
            },
            "empty=",
        )
        self.assertEqual(request.get_arguments(), ["literal", "--flag", "--empty"])

    def test_empty_templates_append_all_parameters(self):
        request = self.request(
            {"defaultParameters": {"flag": True}, "argumentTemplates": []}
        )
        self.assertEqual(request.get_arguments(), ["--flag"])

    def test_null_templates_use_automatic_arguments(self):
        request = self.request(
            {"defaultParameters": {"flag": True}, "argumentTemplates": None}
        )
        self.assertEqual(request.get_arguments(), ["--flag"])

    def test_missing_parameter_prevents_execution(self):
        request = self.request(
            {"executablePath": "/not-run", "argumentTemplates": ["{input}"]}
        )
        with patch.object(app.subprocess, "Popen") as execute:
            with self.assertRaises(KeyError):
                request.execute()
            execute.assert_not_called()

    def test_executes_automatic_arguments_without_shell_interpretation(self):
        executable = self.executable(
            "import json, sys\nprint(json.dumps(sys.argv[1:]))\n"
        )
        value = "a file; $(echo unsafe) & {input}"
        request = self.request(
            {
                "executablePath": executable,
                "allowedParameters": ["input", "flag"],
            },
            urlencode({"input": value, "flag": ""}),
        )
        body, exitcode = request.execute()
        self.assertEqual(exitcode, 0)
        self.assertEqual(json.loads(body), ["--input", value, "--flag"])

    def test_executes_mixed_arguments_in_order_without_shell_interpretation(self):
        executable = self.executable(
            "import json, sys\nprint(json.dumps(sys.argv[1:]))\n"
        )
        request = self.request(
            {
                "executablePath": executable,
                "allowedParameters": ["input", "output", "extra"],
                "argumentTemplates": ["{input}", "output={output}"],
            },
            urlencode(
                {
                    "output": "out file.json",
                    "input": "$(echo unsafe)",
                    "extra": "a file; $(echo unsafe) & {input}",
                }
            ),
        )
        body, exitcode = request.execute()
        self.assertEqual(exitcode, 0)
        self.assertEqual(
            json.loads(body),
            [
                "$(echo unsafe)",
                "output=out file.json",
                "--extra",
                "a file; $(echo unsafe) & {input}",
            ],
        )

    def test_captures_stdout_stderr_and_exit_code(self):
        executable = self.executable(
            "import sys\n"
            "print('output', flush=True)\n"
            "print('error', file=sys.stderr, flush=True)\n"
            "sys.exit(7)\n"
        )
        body, exitcode = self.request({"executablePath": executable}).execute()
        self.assertEqual(body, "output\nerror\n")
        self.assertEqual(exitcode, 7)

    def test_replaces_invalid_utf8_in_output(self):
        executable = self.executable("import sys\nsys.stdout.buffer.write(b'\\xff')\n")
        body, exitcode = self.request({"executablePath": executable}).execute()
        self.assertEqual(body, "\ufffd")
        self.assertEqual(exitcode, 0)
