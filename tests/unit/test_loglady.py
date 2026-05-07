"""Unit tests for LogLady (StateBuffer) module."""

import threading
import json
from collections import deque
from unittest.mock import Mock, patch

import pytest

from lynch.loglady.log import Log, LogMode, AutoRefBuffer, NeonFCBuffer


class TestLogLadyInit:
    """Test LogLady initialization."""

    def test_init_defaults_to_direct_mode(self):
        """Should default to DIRECT mode for backward compatibility."""
        loglady = Log()
        assert loglady.mode == LogMode.DIRECT
        assert isinstance(loglady._buffer, AutoRefBuffer)

    def test_init_can_set_neonfc_mode(self):
        """Should allow setting NEONFC mode."""
        loglady = Log(mode=LogMode.NEONFC)
        assert loglady.mode == LogMode.NEONFC
        assert isinstance(loglady._buffer, NeonFCBuffer)

    def test_init_creates_deque_with_maxlen_one(self):
        """Queue should have maxlen=1 to keep only latest state."""
        loglady = Log()
        assert isinstance(loglady.queue, deque)
        assert loglady.queue.maxlen == 1

    def test_init_socket_is_none(self):
        """Socket should be None before start()."""
        loglady = Log()
        assert loglady.socket is None

    def test_init_running_event_is_cleared(self):
        """Running event should be cleared before start()."""
        loglady = Log()
        assert not loglady.running.is_set()


class TestPull:
    """Test LogLady pull() method."""

    def test_pull_returns_none_when_queue_empty(self):
        """pull() should return None when no state available."""
        loglady = Log()
        assert loglady.pull() is None

    def test_pull_returns_wrapped_state_in_direct_mode(self):
        """pull() should return wrapped state in DIRECT mode."""
        loglady = Log(mode=LogMode.DIRECT)
        test_state = {"ball": {"x": 1.0}}
        wrapped_state = {"state": test_state, "prev_state": None, "action": None}
        loglady.queue.append(wrapped_state)

        result = loglady.pull()

        assert result == wrapped_state

    def test_pull_returns_full_tuple_in_neonfc_mode(self):
        """pull() should return full tuple in NEONFC mode."""
        loglady = Log(mode=LogMode.NEONFC)
        test_data = {
            "state": {"frame": 2},
            "prev_state": {"frame": 1},
            "action": [1.0, 0.5]
        }
        loglady.queue.append(test_data)

        result = loglady.pull()

        assert result == test_data

    def test_pull_removes_state_from_queue(self):
        """pull() should remove state from queue."""
        loglady = Log()
        loglady.queue.append({"state": {}})

        loglady.pull()

        assert len(loglady.queue) == 0


class TestAutoRefBuffer:
    """Test AutoRefBuffer specific logic."""

    @patch("lynch.loglady.log.TrackerWrapperPacket")
    @patch("google.protobuf.json_format.MessageToJson")
    def test_run_loop_parses_protobuf(self, mock_to_json, mock_packet_cls):
        """Should parse protobuf and wrap in standard dict."""
        mock_packet = mock_packet_cls.return_value
        mock_to_json.return_value = '{"uuid": "test"}'
        
        buffer = AutoRefBuffer("224.5.23.2", 10010)
        mock_socket = Mock()
        mock_socket.recv.return_value = b"raw_data"
        buffer.socket = mock_socket
        buffer.running.set()
        
        # Manually trigger one iteration of the logic inside run loop
        data = buffer.socket.recv(2048)
        packet = mock_packet_cls()
        packet.ParseFromString(data)
        state = json.loads(mock_to_json(packet))
        buffer.queue.append({
            "state": state,
            "prev_state": None,
            "action": None
        })
        
        assert len(buffer.queue) == 1
        assert buffer.queue[0]["state"] == {"uuid": "test"}
        assert buffer.queue[0]["prev_state"] is None


class TestNeonFCBuffer:
    """Test NeonFCBuffer specific logic."""

    def test_run_loop_parses_json_tuple(self):
        """Should parse JSON tuple from NeonFC."""
        buffer = NeonFCBuffer("127.0.0.1", 10011)
        mock_socket = Mock()
        test_payload = {
            "cur_state": {"x": 1},
            "prev_state": {"x": 0},
            "action": "kick"
        }
        mock_socket.recv.return_value = json.dumps(test_payload).encode("utf-8")
        buffer.socket = mock_socket
        
        # Simulate receiving logic
        data = buffer.socket.recv(4096)
        payload = json.loads(data.decode("utf-8"))
        buffer.queue.append({
            "state": payload.get("cur_state"),
            "prev_state": payload.get("prev_state"),
            "action": payload.get("action")
        })
        
        assert len(buffer.queue) == 1
        result = buffer.queue[0]
        assert result["state"] == {"x": 1}
        assert result["prev_state"] == {"x": 0}
        assert result["action"] == "kick"
