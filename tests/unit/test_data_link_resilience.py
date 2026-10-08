"""Data-link resilience (T19).

The connector accepted exactly one peer and closed its listener, and the
buffer thread exited for good when that peer disconnected -- so restarting
NeonFC required restarting the harness too.
"""

import socket
import time

import pytest

from lynch.state.buffer import Buffer
from lynch.state.parsers import JSONParser
from lynch.state.tcp_connector import TCPConnector


def _free_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _transition_line(n):
    state = [float(n)] * 16
    import json
    return json.dumps({
        "cur_state": state,
        "next_state": state,
        "actions": {"goalkeeper": [0.0] * 4, "striker": [0.0] * 4},
    }) + "\n"


def _wait_for(buffer, n, timeout=5.0):
    deadline = time.monotonic() + timeout
    pulled = []
    while time.monotonic() < deadline and len(pulled) < n:
        frame = buffer.pull()
        if frame is not None:
            pulled.append(frame)
        else:
            time.sleep(0.01)
    return pulled


def test_frames_survive_a_disconnect_and_reconnect():
    port = _free_port()
    connector = TCPConnector("127.0.0.1", port, as_server=True)
    buffer = Buffer(connector, JSONParser)
    buffer.start()

    try:
        first = socket.create_connection(("127.0.0.1", port))
        first.sendall(_transition_line(1).encode() + _transition_line(2).encode())
        assert len(_wait_for(buffer, 2)) == 2
        first.close()

        time.sleep(0.2)

        second = socket.create_connection(("127.0.0.1", port))
        second.sendall(_transition_line(3).encode() + _transition_line(4).encode())
        assert len(_wait_for(buffer, 2)) == 2
        second.close()
    finally:
        buffer.stop()


def test_no_hello_bytes_are_sent_on_accept():
    """The peer expects a stream of newline-delimited JSON; a greeting
    would arrive as a malformed frame."""
    port = _free_port()
    connector = TCPConnector("127.0.0.1", port, as_server=True)
    connector._ensure_listener()

    client = socket.create_connection(("127.0.0.1", port))
    client.settimeout(2.0)
    try:
        assert connector.accept_once() is True
        try:
            data = client.recv(1024)
        except socket.timeout:
            data = b""
        assert data == b""
    finally:
        connector.shutdown()
        client.close()


def test_accept_once_returns_false_when_stopped():
    port = _free_port()
    connector = TCPConnector("127.0.0.1", port, as_server=True)
    connector._ensure_listener()

    stop = __import__("threading").Event()
    stop.set()

    assert connector.accept_once(stop) is False
    connector.shutdown()


def test_malformed_line_does_not_kill_the_thread():
    port = _free_port()
    connector = TCPConnector("127.0.0.1", port, as_server=True)
    buffer = Buffer(connector, JSONParser)
    buffer.start()

    try:
        client = socket.create_connection(("127.0.0.1", port))
        client.sendall(b"this is not json\n" + _transition_line(7).encode())
        assert len(_wait_for(buffer, 1)) == 1
        client.close()
    finally:
        buffer.stop()
