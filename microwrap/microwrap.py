"""Main MicroWrap module."""
import sys
import json
from urllib.parse import parse_qs
import time

from typing import Any, Iterable
from wsgiref.types import WSGIEnvironment, StartResponse

# this can be replaced with any WSGI server
import bjoern as wsgi_server

USAGE_HELP = "Usage: microwrap <host> <port>"
CONFIG_PATH = "/microwrap.json"
RESPONSE_HEADERS = []


def load_config() -> dict[str, Any]:
    """Load configuration from disk."""
    with open(CONFIG_PATH, encoding="utf-8") as file:
        return json.load(file)


def execute_command(config: dict[str, Any], params: dict[str, list[str]]):
    """Build the command to execute."""
    time.sleep(2)

    executable = config.get("executablePath", "<executablePath is unspecified!>")
    options = config.get("defaultParameters", {})
    for key, value in params.items():
        if config.get("allowedParameters").contains(key):
            options[key] = value

    arguments = []

    for key, value in options.items():
        if value == False or value == True or value == "":
            arguments.append(f"--{key}")
        else:
            arguments.append(f"--{key} {value}")

    # execute command

    # return output
    return executable + " " + " ".join(arguments)


def microwrap(env: WSGIEnvironment, start_response: StartResponse) -> Iterable[bytes]:
    """WSGI application that translates HTTP requests to invocations of an arbitrary executable."""
    # input_body = environ["wsgi.input"].read()
    # errors = env["wsgi.errors"]
    config = load_config()
    method = env.get("REQUEST_METHOD", "")
    path = env.get("SCRIPT_NAME", "") + env.get("PATH_TRANSLATED", "")
    params = parse_qs(env.get("QUERY_STRING", ""), keep_blank_values=True)

    print(f"[{method}][{path}] Configuration: {config}\nParameters: {params}")

    response_body = execute_command(config, params)
    status = "200 OK"
    start_response(status, RESPONSE_HEADERS)
    return [response_body.encode()]


def run(host="localhost", port=80):
    """Run the WSGI application."""
    print(f"Listening on {host}:{port}...")
    wsgi_server.run(microwrap, host, port)


if __name__ == "__main__":
    if len(sys.argv == 1):
        run()
    elif len(sys.argv) == 2:
        if sys.argv[1] == "--help" or sys.argv[1] == "-h":
            print(USAGE_HELP)
        else:
            run(sys.argv[1])
    elif len(sys.argv) == 3:
        run(sys.argv[1], sys.argv[2])
    else:
        print(USAGE_HELP)
