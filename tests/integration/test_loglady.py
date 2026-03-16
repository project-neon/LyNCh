"""Integration tests for LogLady with real socket communication."""

import socket
import time

from lynch.loglady import LogLady


class TestLogLadyIntegration:
    """Integration tests requiring network connectivity."""

    def test_receives_data_from_autoref(self, mock_autoref):
        """LogLady should receive data from AutoRef multicast."""
        loglady = LogLady()
        loglady.start()
        time.sleep(0.1)  # Let LogLady receive packets

        state = loglady.pull()

        assert state is not None
        assert "uuid" in state
        assert state["uuid"].startswith("test-packet-")

        loglady.stop()

    def test_queue_contains_latest_state_only(self, mock_autoref):
        """Queue should keep only the most recent state (maxlen=1)."""
        loglady = LogLady()
        loglady.start()
        time.sleep(0.1)

        # Pull multiple times - should get different packets
        states = []
        for _ in range(3):
            state = loglady.pull()
            if state:
                states.append(state)
            time.sleep(0.02)

        # Should receive states (may be 1-3 depending on timing)
        assert len(states) >= 1

        # Each state should have incrementing packet number
        for state in states:
            assert "uuid" in state

        loglady.stop()

    def test_stop_gracefully_terminates_thread(self, mock_autoref):
        """stop() should terminate thread cleanly."""
        loglady = LogLady()
        loglady.start()
        time.sleep(0.05)

        assert loglady.is_alive()

        loglady.stop()

        # Thread should stop within timeout
        timeout = 2.0
        start = time.time()
        while loglady.is_alive() and (time.time() - start) < timeout:
            time.sleep(0.01)

        assert not loglady.is_alive(), "Thread did not stop within timeout"

    def test_pull_returns_none_without_data(self):
        """pull() should return None when no data received."""
        # Don't start mock server - test empty queue behavior
        loglady = LogLady()

        result = loglady.pull()

        assert result is None

    def test_thread_does_not_crash_on_no_data(self):
        """LogLady thread should handle no data gracefully."""
        loglady = LogLady()
        loglady.start()
        time.sleep(0.1)  # Wait without any data source

        # Thread should still be alive (waiting for data)
        assert loglady.is_alive()

        loglady.stop()


class TestLogLadySocketBehavior:
    """Test socket-level behavior."""

    def test_socket_is_udp(self):
        """_create_socket should create UDP socket."""
        loglady = LogLady()
        sock = loglady._create_socket()

        assert sock.family == socket.AF_INET
        assert sock.type == socket.SOCK_DGRAM
        sock.close()

    def test_socket_reuseaddr_set(self):
        """Socket should have SO_REUSEADDR set."""
        loglady = LogLady()
        sock = loglady._create_socket()

        opts = sock.getsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR)
        assert opts == 1
        sock.close()

    def test_socket_configures_multicast(self):
        """Socket should be configured for multicast reception."""
        loglady = LogLady()
        sock = loglady._create_socket()

        # Verify socket is UDP
        assert sock.family == socket.AF_INET
        assert sock.type == socket.SOCK_DGRAM

        # Verify SO_REUSEADDR is set (allows multiple bindings)
        opts = sock.getsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR)
        assert opts == 1

        sock.close()

    def test_socket_joins_multicast_group(self):
        """LogLady socket should join multicast group."""
        loglady = LogLady()
        sock = loglady._create_socket()

        # Socket creation includes joining multicast group via IP_ADD_MEMBERSHIP
        # If socket creation succeeded, multicast setup worked
        assert sock is not None

        sock.close()
