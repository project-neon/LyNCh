"""Integration test fixtures."""

import socket
import threading
import time
import json

import pytest

from protocols.vision.ssl_vision_wrapper_tracked_pb2 import TrackerWrapperPacket
from protocols.sim.ssl_simulation_control_pb2 import SimulatorCommand

class MockGrSimServer:
    """Mock simulator server that receives SimulatorCommand packets."""

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
        """Listen for and deserialize SimulatorCommand messages."""
        while self.running.is_set():
            try:
                data, _ = self.socket.recvfrom(4096)

                packet = SimulatorCommand()
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
                packet.tracked_frame.frame_number = self.message_count
                packet.tracked_frame.timestamp = self.message_count * 0.01
                data = packet.SerializeToString()

                self.socket.sendto(data, (self.host, self.port))
                self.message_count += 1
            except (OSError, socket.error):
                break
            time.sleep(0.01)  # 100 Hz


class MockNeonFCServer:
    """Mock NeonFC server that sends state/action tuples over TCP."""

    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port
        self.server_socket: socket.socket | None = None
        self.running = threading.Event()
        self.message_count = 0

    def start(self) -> None:
        """Start accepting TCP connections in a background thread."""
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(1)
        self.running.set()
        thread = threading.Thread(target=self._run_server, daemon=True)
        thread.start()

    def stop(self) -> None:
        """Stop server and close socket."""
        self.running.clear()
        if self.server_socket:
            self.server_socket.close()

    def _run_server(self) -> None:
        """Accept connection and send JSON tuples with 14-float state vectors."""
        while self.running.is_set():
            try:
                # Set a timeout on accept to allow checking running event
                self.server_socket.settimeout(0.1)
                conn, _ = self.server_socket.accept()
                with conn:
                    while self.running.is_set():
                        # 14-float state vector: 5 per robot (x, y, vx, vy, theta) + 4 for ball
                        cur_state = [
                            0.0, 0.0, 0.0, 0.0, 0.0,   # blue goalkeeper (id=0)
                            0.0, 0.0, 0.0, 0.0, 0.0,   # yellow striker (id=0)
                            0.0, 0.0, 0.0, 0.0,        # ball
                        ]
                        next_state = list(cur_state)
                        payload = {
                            "cur_state": cur_state,
                            "next_state": next_state,
                            "actions": {"0": {"target_pose": (0.0, 0.0, 0.0)}}
                        }
                        data = json.dumps(payload).encode("utf-8")
                        conn.sendall(data + b"\n")
                        self.message_count += 1
                        time.sleep(0.01)
            except (socket.timeout, OSError):
                continue


@pytest.fixture
def mock_grsim():
    """Fixture that starts/stops mock grSim server."""
    server = MockGrSimServer(port=10300)
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
