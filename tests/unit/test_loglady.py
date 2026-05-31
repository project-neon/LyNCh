"""Unit tests for the LogLady (StateBuffer) module."""

import json
import socket
from unittest.mock import Mock, patch
import pytest

from lynch.loglady import StateBuffer, AutoRefProvider, NeonFCProvider

@pytest.mark.unit
def test_state_buffer_init():
    """Verify StateBuffer initializes with correct provider and pipe."""
    mock_provider = Mock()
    sb = StateBuffer(provider=mock_provider)
    
    assert sb.provider == mock_provider
    assert sb.daemon is True
    # Verify pipe existence (head/tail logic)
    assert hasattr(sb, "pipe_tail")
    assert hasattr(sb, "pipe_head")

@pytest.mark.unit
def test_state_buffer_pull_drains_pipe():
    """Verify pull() drains the pipe to get the latest packet."""
    mock_provider = Mock()
    sb = StateBuffer(provider=mock_provider)
    
    # Mock pipe_tail.poll and recv
    sb.pipe_tail.poll = Mock(side_effect=[True, True, False])
    sb.pipe_tail.recv = Mock(side_effect=[{"frame": 1}, {"frame": 2}])
    
    result = sb.pull()
    
    assert result == {"frame": 2}
    assert sb.pipe_tail.poll.call_count == 3
    assert sb.pipe_tail.recv.call_count == 2

@pytest.mark.unit
def test_autoref_provider_step_logic():
    """Verify AutoRefProvider parses raw bytes into the standard LyNCh format."""
    provider = AutoRefProvider(host="127.0.0.1", port=10010)
    mock_socket = Mock()
    
    # Mocking the socket.recv and Protobuf parsing
    with patch("lynch.loglady.autoref_provider.TrackerWrapperPacket") as mock_packet_cls, \
         patch("lynch.loglady.autoref_provider.MessageToJson") as mock_to_json:
        
        mock_socket.recv.return_value = b"binary_data"
        mock_to_json.return_value = '{"uuid": "test-uuid"}'
        provider.socket = mock_socket
        
        result = provider.step()
        
        assert result["state"] == {"uuid": "test-uuid"}
        assert result["prev_state"] is None
        assert result["action"] is None
        mock_packet_cls.return_value.ParseFromString.assert_called_with(b"binary_data")

@pytest.mark.unit
def test_neonfc_provider_step_logic():
    """Verify NeonFCProvider parses JSON tuples correctly."""
    provider = NeonFCProvider(host="127.0.0.1", port=10011)
    mock_socket = Mock()
    
    test_payload = {
        "cur_state": {"x": 1.0},
        "prev_state": {"x": 0.0},
        "action": "kick"
    }
    mock_socket.recv.return_value = json.dumps(test_payload).encode("utf-8")
    provider.socket = mock_socket
    
    result = provider.step()
    
    assert result["state"] == {"x": 1.0}
    assert result["prev_state"] == {"x": 0.0}
    assert result["action"] == "kick"

@pytest.mark.unit
def test_provider_timeout_handling():
    """Verify providers return None on socket timeout instead of crashing."""
    provider = AutoRefProvider(host="127.0.0.1", port=10010)
    mock_socket = Mock()
    mock_socket.recv.side_effect = socket.timeout
    provider.socket = mock_socket
    
    result = provider.step()
    assert result is None
