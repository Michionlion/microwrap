"""MicroWrap."""
import sys
import json
from urllib.parse import parse_qs
import wsgiref.simple_server as server
import threading
import subprocess

from typing import Any, Iterable, Dict, List, Union
from wsgiref.types import WSGIEnvironment, StartResponse

USAGE_HELP = "Usage: microwrap <host> <port>"
CONFIG_PATH = "/microwrap.json"
WORKING_DIRECTORY = "/"


class Config:
    """A MicroWrap configuration file."""

    def __init__(self, path: str):
        with open(path, encoding="utf-8") as file:
            json_config = json.load(file)
            if isinstance(json_config, dict):
                self.config = json_config
            else:
                raise ValueError("Invalid configuration file!")

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

    def get_executable_path(self) -> str:
        """Return the path to the executable."""
        # TODO: verify valid config
        # should be an existing path
        return self.config.get("executablePath")

    def get_max_active_requests(self) -> int:
        """Return the maximum number of active requests."""
        # TODO: verify valid config
        # should be a positive integer or 0 (unlimited)
        return self.config.get("maxActiveRequests", 1)


def parse_query_params(config: Config, query_str) -> Dict[str, str]:
    """Parse parameters from the request."""
    query_params = parse_qs(query_str, keep_blank_values=True)
    allowed_params = config.get_allowed_params()
    default_params = config.get_default_params()

    params = {
        key: "" if value is True else value
        for key, value in default_params
        if value is not False
    }

    for allowed_param in allowed_params:
        value = query_params.get(allowed_param, None)
        if value is not None:
            params[allowed_param] = value[-1]

    return params


class InvocationRequest:
    """An invocation request."""

    def __init__(self, config: Dict[str, Any], env: WSGIEnvironment):
        self.config = config
        # self.input_body = env["wsgi.input"].read()
        # self.errors = env["wsgi.errors"]
        self.method = env.get("REQUEST_METHOD", "")
        self.path = env.get("SCRIPT_NAME", "") + env.get("PATH_TRANSLATED", "")
        self.params = parse_query_params(config, env.get("QUERY_STRING", ""))
        self.arguments = None

    def get_label(self) -> str:
        """Get logging prefix for this request."""
        return f"[{self.method}][{self.path}][{threading.get_native_id()}]"

    def get_arguments(self):
        """Get the arguments to pass to the executable."""
        if self.arguments is None:
            self.arguments = []
            for key, value in self.params:
                self.arguments.append(f"--{key}")
                if value.strip() != "":
                    self.arguments.append(value)
        return self.arguments

    def execute(self) -> str:
        """Execute the invocation indicated by this request."""
        print(f"{self.get_label()} Executing with arguments: {self.get_arguments()}")
        proc = subprocess.run(
            executable=self.config.get_executable_path(),
            args=self.get_arguments(),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=True,
            text=True,
            cwd=WORKING_DIRECTORY,
            # start_new_session=True,
        )
        return proc.stdout


def microwrap(env: WSGIEnvironment, start_response: StartResponse) -> Iterable[bytes]:
    """WSGI application that translates HTTP requests to invocations of an arbitrary executable."""
    try:
        config = Config(CONFIG_PATH)
        handler = InvocationRequest(config, env)

        print(f"{handler.get_label()} Configuration: {config}")
        print(f"{handler.get_label()} Parameters: {handler.params}")
        response_body = handler.execute()
        start_response("200 OK", [])
        return [response_body.encode()]
    except Exception as ex:
        start_response("500 Internal Server Error", [])
        return [str(ex).encode()]


def run(host="localhost", port=80):
    """Run the WSGI application."""
    print(f"Listening on http://{host}:{port}")
    # Can be replaced with any WSGI server (but needs to be included by cython)
    server.make_server(host, port, microwrap).serve_forever()


if __name__ == "__main__":
    if len(sys.argv) == 1:
        run()
    elif len(sys.argv) == 2:
        if sys.argv[1] == "--help" or sys.argv[1] == "-h":
            print(USAGE_HELP)
        else:
            run(sys.argv[1])
    elif len(sys.argv) == 3:
        run(sys.argv[1], int(sys.argv[2]))
    else:
        print(USAGE_HELP)
