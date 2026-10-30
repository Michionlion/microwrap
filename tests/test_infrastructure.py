"""Logging and server lifecycle behavior."""
import errno
import io
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import Mock, patch

from microwrap import microwrap as app
from tests.helpers import ConfigTestCase


class LoggerTest(ConfigTestCase):
    def test_writes_to_terminal_and_log_file(self):
        terminal = io.StringIO()
        path = Path(self.directory.name, "output.log")
        logger = app.RotatingLogger(terminal, str(path))
        try:
            logger.write("message\n")
            logger.write("\n")
            self.assertEqual(terminal.getvalue(), "message\n")
            self.assertEqual(path.read_text(), "message\n")
        finally:
            logger.close()

    def test_rotates_log_at_size_limit(self):
        path = Path(self.directory.name, "output.log")
        logger = app.RotatingLogger(
            io.StringIO(), str(path), max_bytes=10, backup_count=1
        )
        try:
            logger.write("first")
            logger.write("second")
            self.assertEqual(path.read_text(), "second\n")
            self.assertEqual(Path(str(path) + ".1").read_text(), "first\n")
        finally:
            logger.close()


class ServerTest(unittest.TestCase):
    def test_chooses_server_and_handles_shutdown(self):
        for concurrent in (False, True):
            with self.subTest(concurrent=concurrent):
                with (
                    patch.object(app, "ThreadedWSGIServer") as threaded,
                    patch.object(app, "WSGIServer") as serial,
                    redirect_stdout(io.StringIO()),
                ):
                    factory = threaded if concurrent else serial
                    unused_factory = serial if concurrent else threaded
                    server = factory.return_value
                    server.serve_forever.side_effect = KeyboardInterrupt
                    app.run("127.0.0.1", 8080, concurrent)
                    factory.assert_called_once_with(
                        ("127.0.0.1", 8080), app.WSGIRequestHandler
                    )
                    unused_factory.assert_not_called()
                    server.set_app.assert_called_once_with(app.microwrap)
                    server.serve_forever.assert_called_once_with(poll_interval=0.5)
                    server.shutdown.assert_called_once_with()

    def test_retries_interrupted_accept(self):
        server = Mock()
        connection = (Mock(), ("127.0.0.1", 12345))
        server.socket.accept.side_effect = [
            OSError(errno.EINTR, "interrupted"),
            connection,
        ]
        server.verify_request.return_value = True
        self.assertEqual(app.ThreadedWSGIServer.get_request(server), connection)
        self.assertEqual(server.socket.accept.call_count, 2)

    def test_retries_unverified_connection(self):
        server = Mock()
        rejected = (Mock(), ("127.0.0.1", 12345))
        accepted = (Mock(), ("127.0.0.1", 12346))
        server.socket.accept.side_effect = [rejected, accepted]
        server.verify_request.side_effect = [False, True]
        self.assertEqual(app.ThreadedWSGIServer.get_request(server), accepted)
        self.assertEqual(server.socket.accept.call_count, 2)

    def test_other_socket_errors_propagate(self):
        server = Mock()
        server.socket.accept.side_effect = OSError(errno.EBADF, "closed socket")
        with self.assertRaises(OSError) as error:
            app.ThreadedWSGIServer.get_request(server)
        self.assertEqual(error.exception.errno, errno.EBADF)
