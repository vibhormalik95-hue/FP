"""R6 findings D8a and D8g: checks of the test helpers themselves.

D8b-D8f are fixed inside their own test files; this file holds the two checks that need a test of their own.
"""
from pathlib import Path
import re
import sys
import threading

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests'))


def test_d8a_the_guarded_runner_named_by_the_category_resolution_tests_exists():
    doc = (ROOT / 'tests' / 'test_category_resolution_offline.py').read_text(encoding='utf-8').split('"""')[1]
    named = re.findall(r'[\w./-]+\.py', doc)
    assert named and all((ROOT / path).is_file() for path in named), named
    assert 'verification/run_guarded.py' not in doc


class EarlyClose:
    """A connection that sends a head promising 100 bytes, 10 bytes of body, and then closes."""

    def __init__(self):
        self.blocks = [b'POST / HTTP/1.1\r\nContent-Length: 100\r\n\r\n' + b'x' * 10]
        self.reads = 0

    def recv(self, size):
        self.reads += 1
        return self.blocks.pop(0) if self.blocks else b''

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def test_d8g_the_raw_server_stops_reading_when_the_client_closes_early():
    from test_route_http_offline import RawServer
    server = RawServer(lambda connection, head: None)
    try:
        connection = EarlyClose()
        worker = threading.Thread(target=server._one, args=(connection,), daemon=True)
        worker.start()
        worker.join(5)
        assert not worker.is_alive(), 'the reader spins on an empty read after the client closed'
        assert server.count == 0 and connection.reads <= 3
    finally:
        server.sock.close()
