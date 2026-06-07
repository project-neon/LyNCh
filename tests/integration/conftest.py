"""Integration test fixtures."""

import socket
import threading
import time
import json

import pytest

from protocols.vision.ssl_vision_wrapper_tracked_pb2 import TrackerWrapperPacket
from protocols.sim.grSim_Packet_pb2 import grSim_Packet


class MockGrSimServer:
    """Mock grSim server that receives replacement packets."""

    def __init__(self, port: int):
        self.port = port
        self.socket: socket.socket | None = None
        self.running = threading.Event()
        self.received_count = 0
        self.last_packet = None

    def start(self) -> None:
        """Start listening for UDP packets."""
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.bind(("", self.port))
        self.socket.settimeout(0.5)
        self.running.set()
        thread = threading.Thread(target=self._listen, daemon=True)
        thread.start()

    def stop(self) -> None:
        """Stop listening."""
        self.running.clear()
        if self.socket:
            self.socket.close()

    def _listen(self) -> None:
        """Listen for and deserialize grSim_Packet messages."""
        while self.running.is_set():
            try:
                data, _ = self.socket.recvfrom(4096)
                packet = grSim_Packet()
                packet.ParseFromString(data)
                self.last_packet = packet
                self.received_count += 1
            except (OSError, socket.error, socket.timeout):
                continue


class MockAutoRefServer:
    """Mock AutoRef server that sends TrackerWrapperPacket data."""

    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port
        self.socket: socket.socket | None = None
        self.running = threading.Event()
        self.message_count = 0

    def start(self) -> None:
        """Start sending multicast packets in background thread."""
        self.socket = self._create_socket()
        self.running.set()
        thread = threading.Thread(target=self._send_packets, daemon=True)
        thread.start()

    def stop(self) -> None:
        """Stop sending packets."""
        self.running.clear()
        if self.socket:
            self.socket.close()

    def _create_socket(self) -> socket.socket:
        """Create UDP multicast socket."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 1)
        return sock

    def _send_packets(self) -> None:
        """Send TrackerWrapperPacket messages periodically."""
        while self.running.is_set():
            try:
                packet = TrackerWrapperPacket()
                packet.uuid = f"test-packet-{self.message_count}"
                packet.source_name = "MockAutoRef"
                data = packet.SerializeToString()

                self.socket.sendto(data, (self.host, self.port))
                self.message_count += 1
            except (OSError, socket.error):
                break
            time.sleep(0.01)  # 100 Hz


class MockNeonFCServer:
    """Mock NeonFC server that sends state/action tuples."""

    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port
        self.socket: socket.socket | None = None
        self.running = threading.Event()
        self.message_count = 0

    def start(self) -> None:
        """Start sending UDP packets in background thread."""
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.running.set()
        thread = threading.Thread(target=self._send_packets, daemon=True)
        thread.start()

    def stop(self) -> None:
        """Stop sending packets."""
        self.running.clear()
        if self.socket:
            self.socket.close()

    def _send_packets(self) -> None:
        """Send JSON tuples periodically."""
        while self.running.is_set():
            try:
                payload = {
                    "cur_state": {"frame": self.message_count},
                    "prev_state": {"frame": self.message_count - 1},
                    "action": f"action-{self.message_count}"
                }
                data = json.dumps(payload).encode("utf-8")
                self.socket.sendto(data, (self.host, self.port))
                self.message_count += 1
            except (OSError, socket.error):
                break
            time.sleep(0.01)


@pytest.fixture
def mock_grsim():
    """Fixture that starts/stops mock grSim server."""
    server = MockGrSimServer(port=20011)
    server.start()
    time.sleep(0.05)
    yield server
    server.stop()


@pytest.fixture
def mock_autoref():
    """Fixture that starts/stops mock AutoRef server."""
    server = MockAutoRefServer(host="224.5.23.2", port=10010)
    server.start()
    time.sleep(0.05)  # Let server initialize
    yield server
    server.stop()


@pytest.fixture
def mock_neonfc():
    """Fixture that starts/stops mock NeonFC server."""
    server = MockNeonFCServer(host="127.0.0.1", port=10011)
    server.start()
    time.sleep(0.05)
    yield server
    server.stop()
