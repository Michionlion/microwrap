"""MicroWrap."""
import errno
import json
import logging
import os
import subprocess
import sys
import threading
import traceback
from logging.handlers import RotatingFileHandler
from socketserver import ThreadingMixIn
from typing import Any, Dict, Iterable, List, TextIO, Tuple, Union
from urllib.parse import parse_qs
from wsgiref.simple_server import WSGIRequestHandler, WSGIServer
from wsgiref.types import StartResponse, WSGIEnvironment

###
# Logging
###


class RotatingLogger:
    """A logger that writes to a file and rotates it when it gets too big."""

    def __init__(
        self,
        terminal: TextIO,
        log_file: str,
        max_bytes=20 * 1_000_000,
        backup_count=5,
    ):
        self.terminal = terminal
        self.log = RotatingFileHandler(
            log_file, maxBytes=max_bytes, backupCount=backup_count
        )
        self.log.setFormatter(logging.Formatter("%(message)s"))

    def write(self, message: str):
        """Write a message to the log."""
        message = message.strip("\n")
        if message:
            self.terminal.write(message + "\n")
            self.log.emit(logging.makeLogRecord({"msg": message}))
            self.flush()

    def flush(self):
        """Flush the log."""
        self.terminal.flush()
        self.log.flush()

    def close(self):
        """Close the log."""
        self.log.close()


sys.stdout = RotatingLogger(sys.stdout, "microwrap.log")
sys.stderr = RotatingLogger(sys.stderr, "microwrap.err")


class Config:
    """A MicroWrap configuration file."""

    def __init__(self, path: str):
        with open(path, encoding="utf-8") as file:
            json_config = json.load(file)
            if isinstance(json_config, dict):
                self.config = json_config
            else:
                raise ValueError("Invalid configuration file!")

    def get_host(self) -> str:
        """Return the host to bind to."""
        # TODO: verify valid config
        # should be a string
        return self.config.get("host", "0.0.0.0")

    def get_port(self) -> int:
        """Return the port to bind to."""
        # TODO: verify valid config
        # should be an integer and valid port
        return self.config.get("port", 80)

    def get_concurrent(self) -> int:
        """Return whether to run a multithreaded server."""
        # TODO: verify valid config
        # should be a boolean
        return self.config.get("concurrent", True)

    def get_executable_path(self) -> str:
        """Return the path to the executable."""
        # TODO: verify valid config
        # should be an existing path
        return self.config.get("executablePath")

    def get_allowed_params(self) -> List[str]:
        """Return the list of allowed query-string parameters."""
        # TODO: verify valid config
        # should be a list of strings
        return self.config.get("allowedParameters", [])

    def get_default_params(self) -> Dict[str, Union[str, bool]]:
        """Return the default query-string parameter values."""
        # TODO: verify valid config
        # valid if (isinstance(value, str) or isinstance(value, bool)) and value != ""
        # if a value is "", error should include "should be `true` to indicate a value-less option"
        # if a value is not a str or bool, error should include "should be a string or boolean"
        return self.config.get("defaultParameters", {})

    def __str__(self):
        return str(self.config)


###
# Constants
###


USAGE_HELP = "Usage: microwrap <host> <port>"
CONFIG_PATH = "microwrap.json"
MAX_THREADS = os.cpu_count() * 4


###
# Utility functions
###


def parse_query_params(config: Config, query_str) -> Dict[str, str]:
    """Parse parameters from the request."""
    query_params = parse_qs(query_str, keep_blank_values=True)
    allowed_params = config.get_allowed_params()
    default_params = config.get_default_params()

    params = {
        key: "" if value is True else value
        for key, value in default_params.items()
        if value is not False
    }

    for allowed_param in allowed_params:
        value = query_params.get(allowed_param, None)
        if value is not None:
            params[allowed_param] = value[-1]

    return params


def get_response_headers(body: str | bytes) -> List[str]:
    """Return the response headers derived from the response body."""
    if isinstance(body, str):
        body = body.encode()
        content = "text/plain"
    elif isinstance(body, bytes):
        content = "application/octet-stream"
    return [
        ("Server", f"MicroWrap/1.0.0 {Config(CONFIG_PATH).get_executable_path()}"),
        ("Content-Length", str(len(body))),
        ("Content-Type", content),
    ]


###
# Request handler
###


class InvocationRequest:
    """An invocation request."""

    def __init__(self, config: Dict[str, Any], env: WSGIEnvironment):
        self.config = config
        # self.input_body = env["wsgi.input"].read()
        # self.errors = env["wsgi.errors"]
        self.method = env.get("REQUEST_METHOD", "")
        self.path = env.get("PATH_INFO", "/")
        self.query = env.get("QUERY_STRING", "")
        self.params = parse_query_params(config, self.query)
        self.arguments = None

    def get_label(self) -> str:
        """Get logging prefix for this request."""
        return f"[{threading.current_thread().name}][{self.method}][{self.path}][{self.query}]"

    def get_arguments(self):
        """Get the arguments to pass to the executable."""
        if self.arguments is None:
            self.arguments = []
            for key, value in self.params.items():
                self.arguments.append(f"--{key}")
                if value.strip() != "":
                    self.arguments.append(value)
        return self.arguments

    def execute(self) -> Tuple[str, int]:
        """Execute the invocation requested."""
        cmd = [os.path.abspath(self.config.get_executable_path())]
        cmd += self.get_arguments()
        print(f"{self.get_label()} Executing '{cmd}'")
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
            cwd=".",
            start_new_session=True,
        )
        return (proc.stdout.decode(), proc.returncode)


###
# Main application
###


def microwrap(env: WSGIEnvironment, start_response: StartResponse) -> Iterable[bytes]:
    """WSGI application that translates HTTP requests to invocations of an arbitrary executable."""
    try:
        config = Config(CONFIG_PATH)
        handler = InvocationRequest(config, env)
        print(f"{handler.get_label()} Configuration: {config}")
        print(f"{handler.get_label()} Parameters: {handler.params}")
        body, exitcode = handler.execute()
        print(f"{handler.get_label()} Finished execution, exit code: {exitcode}")
        status = "200 OK" if exitcode == 0 else "500 Internal Server Error"
        start_response(status, get_response_headers(body))
        return [body.encode()]
    except Exception as ex:
        traceback.print_exception(ex)
        body = f"MicroWrap error: {type(ex)}: {ex}"
        start_response("500 Internal Server Error", get_response_headers(body))
        return [body.encode()]


###
# Infrastructure: WSGI server and main method
###


class ThreadedWSGIServer(ThreadingMixIn, WSGIServer):
    """Threaded WSGI Server that uses a thread for each request."""

    def get_request(self):
        while True:
            try:
                sock, addr = self.socket.accept()
                if self.verify_request(sock, addr):
                    return sock, addr
            except OSError as ex:
                if ex.errno != errno.EINTR:
                    raise


def run(host="0.0.0.0", port=80, concurrent=True):
    """Run the WSGI application."""
    print(f"Listening on http://{host}:{port}/")
    if concurrent:
        print("Starting concurrent server...")
        httpd = ThreadedWSGIServer((host, port), WSGIRequestHandler)
    else:
        print("Starting non-concurrent server...")
        httpd = WSGIServer((host, port), WSGIRequestHandler)
    httpd.set_app(microwrap)
    try:
        httpd.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        print("\nShutting down...")
        httpd.shutdown()


if __name__ == "__main__":
    global_config = Config(CONFIG_PATH)
    run(
        global_config.get_host(),
        global_config.get_port(),
        global_config.get_concurrent(),
    )
