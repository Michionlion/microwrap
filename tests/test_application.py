"""HTTP response behavior through the WSGI application."""
import io
import os
import signal
import socket
from contextlib import redirect_stderr, redirect_stdout, suppress
from pathlib import Path
from unittest.mock import Mock, patch

from microwrap import microwrap as app
from tests.helpers import ConfigTestCase


class ApplicationTest(ConfigTestCase):
    def response(self, configuration, query="", path="/", method="GET"):
        self.config(configuration)
        start_response = Mock()
        with (
            patch.object(app, "CONFIG_PATH", str(self.config_path)),
            redirect_stdout(io.StringIO()),
            redirect_stderr(io.StringIO()),
        ):
            result = app.microwrap(
                {"QUERY_STRING": query, "PATH_INFO": path, "REQUEST_METHOD": method},
                start_response,
            )
            body = b"".join(result)
        start_response.assert_called_once()
        status, headers = start_response.call_args.args
        headers = dict(headers)
        self.assertEqual(int(headers["Content-Length"]), len(body))
        self.assertEqual(headers["Content-Type"], "text/plain")
        self.assertIn(configuration["executablePath"], headers["Server"])
        return status, body

    def test_success_returns_stdout_as_utf8(self):
        executable = self.executable("print('café')\n")
        status, body = self.response({"executablePath": executable})
        self.assertEqual(status, "200 OK")
        self.assertEqual(body, "café\n".encode())

    def test_empty_stdout_returns_empty_response(self):
        status, body = self.response({"executablePath": self.executable("pass\n")})
        self.assertEqual(status, "200 OK")
        self.assertEqual(body, b"")

    def test_nonzero_exit_returns_combined_output_and_500(self):
        executable = self.executable(
            "import sys\n"
            "print('output', flush=True)\n"
            "print('error', file=sys.stderr, flush=True)\n"
            "sys.exit(1)\n"
        )
        status, body = self.response({"executablePath": executable})
        self.assertEqual(status, "500 Internal Server Error")
        self.assertEqual(body, b"output\nerror\n")

    def test_any_path_and_method_forward_allowed_query_parameters(self):
        executable = self.executable("import sys\nprint('|'.join(sys.argv[1:]))\n")
        status, body = self.response(
            {"executablePath": executable, "allowedParameters": ["input"]},
            "input=value&ignored=no",
            path="/arbitrary/path",
            method="POST",
        )
        self.assertEqual(status, "200 OK")
        self.assertEqual(body, b"--input|value\n")

    def test_missing_executable_returns_500(self):
        status, body = self.response(
            {"executablePath": str(Path(self.directory.name, "missing"))}
        )
        self.assertEqual(status, "500 Internal Server Error")
        self.assertIn(b"FileNotFoundError", body)

    def test_templates_and_unreferenced_parameters_are_forwarded_together(self):
        executable = self.executable("import sys\nprint('|'.join(sys.argv[1:]))\n")
        status, body = self.response(
            {
                "executablePath": executable,
                "allowedParameters": ["input", "output"],
                "argumentTemplates": ["{input}"],
            },
            "input=file&output=result&ignored=no",
        )
        self.assertEqual(status, "200 OK")
        self.assertEqual(body, b"file|--output|result\n")

    def test_missing_template_parameter_returns_500_without_execution(self):
        with patch.object(app.subprocess, "Popen") as execute:
            status, body = self.response(
                {"executablePath": "/not-run", "argumentTemplates": ["{input}"]}
            )
        self.assertEqual(status, "500 Internal Server Error")
        self.assertIn(b"KeyError", body)
        execute.assert_not_called()

    def test_invalid_configuration_prevents_execution(self):
        for setting in ({"argumentTemplates": "invalid"}, {"timeoutSeconds": 0}):
            with self.subTest(setting=setting):
                with patch.object(app.subprocess, "Popen") as execute:
                    status, body = self.response(
                        {"executablePath": "/not-run", **setting}
                    )
                self.assertEqual(status, "500 Internal Server Error")
                self.assertIn(b"ValueError", body)
                execute.assert_not_called()

    def test_timeout_returns_504_and_reaps_executable(self):
        pid = Path(self.directory.name, "pid")
        executable = self.executable(
            "import os, pathlib, time\n"
            "pathlib.Path(__file__).with_name('pid').write_text(str(os.getpid()))\n"
            "time.sleep(30)\n"
        )
        status, body = self.response(
            {"executablePath": executable, "timeoutSeconds": 1}
        )
        self.assertEqual(status, "504 Gateway Timeout")
        self.assertIn(b"timed out", body)
        with self.assertRaises(ProcessLookupError):
            os.kill(int(pid.read_text()), 0)

    def test_timeout_stops_child_process(self):
        with socket.create_server(("127.0.0.1", 0)) as listener:
            listener.settimeout(2)
            executable = self.executable(
                "import os, socket, time\n"
                "if os.fork() == 0:\n"
                f"    connection = socket.create_connection({listener.getsockname()!r})\n"
                "    connection.sendall(f'{os.getpid()}\\n'.encode())\n"
                "    time.sleep(30)\n"
                "else:\n"
                "    os.wait()\n"
            )
            status, _ = self.response(
                {"executablePath": executable, "timeoutSeconds": 1}
            )
            with listener.accept()[0] as connection:
                connection.settimeout(2)
                with connection.makefile("rb") as stream:
                    child_pid = int(stream.readline())
                    try:
                        self.assertEqual(status, "504 Gateway Timeout")
                        # EOF confirms termination even before an orphan is reaped.
                        self.assertEqual(stream.read(1), b"")
                    finally:
                        with suppress(ProcessLookupError):
                            os.kill(child_pid, signal.SIGKILL)

    def test_response_headers_handle_text_and_binary_lengths(self):
        self.config({"executablePath": "/opt/program"})
        with patch.object(app, "CONFIG_PATH", str(self.config_path)):
            for body, length, content_type in (
                ("café", 5, "text/plain"),
                (b"\x00\xff", 2, "application/octet-stream"),
            ):
                with self.subTest(body=body):
                    headers = dict(app.get_response_headers(body))
                    self.assertEqual(headers["Content-Length"], str(length))
                    self.assertEqual(headers["Content-Type"], content_type)
                    self.assertTrue(headers["Server"].startswith("MicroWrap/"))
                    self.assertTrue(headers["Server"].endswith(" /opt/program"))
