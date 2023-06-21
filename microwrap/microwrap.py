"""MicroWrap."""
import json
import os
import signal
import subprocess
import sys
import threading
import traceback
import wsgiref.simple_server as server
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler
from queue import Empty, Queue
from typing import Any, Dict, Iterable, List, Union
from urllib.parse import parse_qs
from wsgiref.types import StartResponse, WSGIEnvironment


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

    def __str__(self):
        return str(self.config)


###
# Constants
###


USAGE_HELP = "Usage: microwrap <host> <port>"
CONFIG_PATH = "microwrap.json"
MAX_THREADS = os.cpu_count() * 4
RESPONSE_HEADERS = [
    ("Server", f"MicroWrap/1.0.0 {Config(CONFIG_PATH).get_executable_path()}")
]


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

    def execute(self) -> str:
        """Execute the invocation requested."""
        executable = os.path.abspath(self.config.get_executable_path())
        arguments = self.get_arguments()
        print(f"{self.get_label()} Executing '{executable}' with args: {arguments}")
        proc = subprocess.run(
            executable=executable,
            args=arguments,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=True,
            text=True,
            cwd=".",
            start_new_session=True,
        )
        return proc.stdout


###
# Threaded WSGI server
###


class ThreadedWSGIServer(server.WSGIServer):
    """Threaded WSGI Server that uses a ThreadPoolExecutor to handle requests."""

    def __init__(
        self,
        host: str,
        port: int,
        handler: BaseHTTPRequestHandler,
        max_workers=None,
    ):
        super().__init__((host, port), handler, True)
        self.requests = Queue()
        self.executor = ThreadPoolExecutor(max_workers if max_workers else MAX_THREADS)
        self.is_listening = False

    def process_request(self, request, client_address):
        """Add requests to the queue instead of handling immediately like super does."""
        self.requests.put((request, client_address))
        print(f"Added request {request} from {client_address} to queue")
        print(f"{self.requests.qsize()} requests in queue")

    def serve_forever(self, poll_interval=0.5):
        """Continuously handle requests from the queue in separate threads."""
        signal.signal(signal.SIGINT, lambda _s, _f: self.shutdown())
        signal.signal(signal.SIGTERM, lambda _s, _f: self.shutdown())
        self.is_listening = True
        print("Starting server...")
        while self.is_listening:
            try:
                print(f"Pulling from queue: {self.requests.queue}")
                request, client_address = self.requests.get(
                    block=True, timeout=poll_interval
                )
                print("Retrieved request")
                self.executor.submit(
                    self.process_request_thread, request, client_address
                )
                print("Submitted request")
            except Empty:
                continue

    def process_request_thread(self, request, client_address):
        """This function will be executed in a new thread and handle the request."""
        try:
            print(f"Processing request {request} from {client_address}")
            self.finish_request(request, client_address)
            self.shutdown_request(request)
        except Exception:
            self.handle_error(request, client_address)
            self.shutdown_request(request)

    def shutdown(self):
        """Stop the server but wait for current requests to complete before exiting."""
        print("Waiting for requests to  complete...")
        self.is_listening = False
        self.executor.shutdown(wait=True, cancel_futures=True)
        print("Requests complete. Shutting down...")


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
        response_body = handler.execute()
        start_response("200 OK", RESPONSE_HEADERS)
        return [response_body.encode()]
    except Exception as ex:
        traceback.print_exception(ex)
        start_response("500 Internal Server Error", RESPONSE_HEADERS)
        return [str(ex).encode()]


def run(host="localhost", port=80):
    """Run the WSGI application."""
    print(f"Listening on http://{host}:{port}/")
    httpd = ThreadedWSGIServer(
        host,
        port,
        server.WSGIRequestHandler,
        max_workers=Config(CONFIG_PATH).get_max_active_requests(),
    )
    httpd.set_app(microwrap)
    httpd.serve_forever(poll_interval=0.5)


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
