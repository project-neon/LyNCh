"""Integration test for Runner with a mock NeonFC server."""

import json
import socket
import threading
import time
from pathlib import Path

import pytest
import yaml

from lynch.runner import Runner


class MockNeonFCServer:
    """Mock NeonFC server that acts as a client to LyNCh's data port."""

    def __init__(self, data_port=10015, control_port=10016):
        self.data_port = data_port
        self.control_port = control_port
        self.data_sock = None
        self.signal_sock = None
        self.running = False
        self.received_signals = []

    def start(self):
        self.running = True

        # Signal server (receives START/STOP/metadata)
        self.signal_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.signal_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.signal_sock.bind(("127.0.0.1", self.control_port))
        self.signal_sock.listen(5)
        threading.Thread(target=self._listen_signal, daemon=True).start()

        # Data client (connects to LyNCh's listening socket)
        threading.Thread(target=self._connect_data, daemon=True).start()

    def _connect_data(self):
        # Retry until LyNCh is ready
        retries = 0
        while self.running and retries < 50:
            try:
                self.data_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.data_sock.connect(("127.0.0.1", self.data_port))
                self._handle_data(self.data_sock)
                break
            except OSError:
                retries += 1
                time.sleep(0.2)

    def stop(self):
        self.running = False
        for s in (self.data_sock, self.signal_sock):
            if s:
                try:
                    s.close()
                except OSError:
                    pass

    def _listen_signal(self):
        self.signal_sock.settimeout(0.5)
        while self.running:
            try:
                conn, _ = self.signal_sock.accept()
                threading.Thread(target=self._handle_signal, args=(conn,), daemon=True).start()
            except socket.timeout:
                continue
            except OSError:
                break
    def _handle_data(self, sock):
        sock.settimeout(0.05)
        msg_count = 0
        while self.running:
            try:
                # 16-element state: 6 per robot * 2 + 4 for ball
                # Blue: robot 0 at raw (2.5, 3.0) -> (-2.0, 0.0)
                # Yellow: robot 0 at raw (6.5, 3.0) -> (2.0, 0.0)
                # Ball: (initially) at raw (4.5, 3.0) -> (0.0, 0.0)
                cur_state = [0.0] * 16
                cur_state[0] = 2.5
                cur_state[1] = 3.0
                cur_state[6] = 6.5
                cur_state[7] = 3.0
                cur_state[12] = 4.5
                cur_state[13] = 3.0

                # Trigger goal after 3 frames (ball x is index 12, raw 9.0 transforms to 4.5)
                if msg_count > 3:
                    cur_state[12] = 9.0 
                    cur_state[13] = 3.0

                payload = {
                    "cur_state": cur_state,
                    "next_state": list(cur_state),
                    "actions": {"goalkeeper": [0.0]*4, "striker": [0.0]*4},
                }
                sock.sendall(json.dumps(payload).encode("utf-8") + b"\n")
                msg_count += 1
            except OSError:
                break
            time.sleep(0.01)

    def _handle_signal(self, conn):
        conn.settimeout(0.05)
        while self.running:
            try:
                data = conn.recv(1024)
                if data:
                    self.received_signals.append(data)
            except socket.timeout:
                continue
            except OSError:
                break


@pytest.mark.integration
def test_runner_integration(tmp_path):
    # 1. Start mock NeonFC server (data + signal on separate ports)
    mock = MockNeonFCServer(data_port=10015, control_port=10016)
    mock.start()
    time.sleep(0.1)

    # 2. Write test config
    config_file = tmp_path / "test_config.yaml"
    template_file = tmp_path / "template.yaml"
    template_file.write_text(
        "ball:\n  x: 0.0\n  y: 0.0\n"
        "robots:\n  blue:\n    - id: 0\n      x: -2.0\n      y: 0.0\n      theta: 0.0\n"
        "  yellow:\n    - id: 0\n      x: 2.0\n      y: 0.0\n      theta: 3.14\n"
    )

    config_data = {
        "network": {
            "runner": {
                "host": "127.0.0.1",
                "port": 10005,
            },
            "NEONFC": {
                "host": "127.0.0.1",
                "data_port": 10015,
                "control_port": 10016,
            }
        },
        "scenarios": {
            "penalty_kick": {
                "template": str(template_file),
                "strategy": "no_variance",
                "assessments": ["GoalScored"],
            }
        },
    }
    config_file.write_text(yaml.dump(config_data))

    # 3. Start Runner in background
    output_dir = tmp_path / "results"
    runner = Runner(config_path=str(config_file), mode="NEONFC")
    threading.Thread(target=runner.serve_forever, daemon=True).start()
    time.sleep(0.1)

    # 4. Send command
    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client.connect(("127.0.0.1", 10005))

    command = {
        "test_case": "penalty_kick",
        "metadata": {"test_run": "integration"},
        "config": {"batch_size": 1, "output_dir": str(output_dir)},
    }

    client.sendall(json.dumps(command).encode("utf-8") + b"\n")

    # 5. Read response
    client.settimeout(5.0)
    response_data = b""
    while b"\n" not in response_data:
        chunk = client.recv(4096)
        if not chunk:
            break
        response_data += chunk

    client.close()
    runner.close()
    mock.stop()

    # 6. Verify response
    assert response_data != b""
    response = json.loads(response_data.decode("utf-8"))
    assert response["status"] == "success"
    assert "summary_file" in response
    assert len(response["history_files"]) == 1

    # 7. Verify files exist
    for h_file in response["history_files"]:
        assert Path(h_file).exists()

    summary_path = Path(response["summary_file"])
    assert summary_path.exists()

    # 8. Verify signal server received START and STOP
    all_signals = b"".join(mock.received_signals)
    assert b"play" in all_signals
    assert b"stop" in all_signals
