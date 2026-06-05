"""Unit tests for the StateBuffer module."""

import json
import socket
from unittest.mock import Mock, patch
from collections import deque
import pytest

from lynch.state import Buffer, AutoRefProvider, NeonFCProvider

@pytest.mark.unit
def test_state_buffer_init():
    """Verify StateBuffer initializes with correct provider and internal deque."""
    mock_provider = Mock()
    sb = Buffer(provider=mock_provider)
    
    assert sb.provider == mock_provider
    assert sb.daemon is True
    assert isinstance(sb._buffer, deque)
    assert sb._buffer.maxlen is None  # Integrity priority

@pytest.mark.unit
def test_state_buffer_pull_fifo_logic():
    """Verify pull() follows FIFO logic and doesn't skip frames."""
    mock_provider = Mock()
    sb = Buffer(provider=mock_provider)
    
    # Manually populate the buffer
    sb._buffer.append({"frame": 1})
    sb._buffer.append({"frame": 2})
    
    # First pull should get frame 1
    assert sb.pull() == {"frame": 1}
    # Second pull should get frame 2
    assert sb.pull() == {"frame": 2}
    # Third pull should be empty
    assert sb.pull() is None

@pytest.mark.unit
def test_autoref_provider_step_logic():
    """Verify AutoRefProvider parses raw bytes into the standard LyNCh format."""
    provider = AutoRefProvider(host="127.0.0.1", port=10010)
    mock_socket = Mock()
    
    with patch("lynch.state.autoref_provider.TrackerWrapperPacket") as mock_packet_cls, \
         patch("lynch.state.autoref_provider.MessageToJson") as mock_to_json:
        
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
    """Verify providers return None on socket timeout."""
    provider = AutoRefProvider(host="127.0.0.1", port=10010)
    mock_socket = Mock()
    mock_socket.recv.side_effect = socket.timeout
    provider.socket = mock_socket
    
    result = provider.step()
    assert result is None
