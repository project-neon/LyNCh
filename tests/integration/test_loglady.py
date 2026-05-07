"""Integration tests for LogLady with real socket communication."""

import socket
import time

from lynch.loglady.log import Log, LogMode


class TestLogLadyIntegration:
    """Integration tests requiring network connectivity."""

    def test_receives_data_from_autoref_direct(self, mock_autoref):
        """LogLady should receive data from AutoRef in DIRECT mode."""
        loglady = Log(mode=LogMode.DIRECT)
        loglady.start()
        time.sleep(0.1)

        data = loglady.pull()

        assert data is not None
        assert "state" in data
        assert "uuid" in data["state"]
        assert data["state"]["uuid"].startswith("test-packet-")
        assert data["prev_state"] is None
        assert data["action"] is None

        loglady.stop()

    def test_receives_data_from_neonfc(self, mock_neonfc):
        """LogLady should receive data from NeonFC in NEONFC mode."""
        loglady = Log(mode=LogMode.NEONFC)
        loglady.start()
        time.sleep(0.1)

        data = loglady.pull()

        assert data is not None
        assert "state" in data
        assert "prev_state" in data
        assert "action" in data
        assert "frame" in data["state"]
        assert data["action"].startswith("action-")

        loglady.stop()

    def test_stop_gracefully_terminates_thread(self, mock_autoref):
        """stop() should terminate thread cleanly."""
        loglady = Log()
        loglady.start()
        time.sleep(0.05)

        assert loglady._buffer.is_alive()

        loglady.stop()

        # Thread should stop within timeout
        timeout = 2.0
        start = time.time()
        while loglady._buffer.is_alive() and (time.time() - start) < timeout:
            time.sleep(0.01)

        assert not loglady._buffer.is_alive(), "Thread did not stop within timeout"


class TestLogLadySocketBehavior:
    """Test socket-level behavior."""

    def test_autoref_socket_is_multicast_udp(self):
        """AutoRefBuffer should create UDP multicast socket."""
        loglady = Log(mode=LogMode.DIRECT)
        sock = loglady._buffer._create_socket()

        assert sock.family == socket.AF_INET
        assert sock.type == socket.SOCK_DGRAM
        
        # Check SO_REUSEADDR
        opts = sock.getsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR)
        assert opts == 1
        
        sock.close()

    def test_neonfc_socket_is_standard_udp(self):
        """NeonFCBuffer should create standard UDP socket."""
        loglady = Log(mode=LogMode.NEONFC)
        sock = loglady._buffer._create_socket()

        assert sock.family == socket.AF_INET
        assert sock.type == socket.SOCK_DGRAM
        
        # Should also have SO_REUSEADDR for easier testing
        opts = sock.getsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR)
        assert opts == 1
        
        sock.close()
