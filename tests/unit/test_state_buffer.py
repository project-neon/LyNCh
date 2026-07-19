import json
import pytest
import socket
import threading
import time
from unittest.mock import Mock, patch, ANY
from lynch.state.tcp_connector import TCPConnector
from lynch.state.multicast_connector import MulticastConnector
from lynch.state.parsers import JSONParser, ProtobufParser
from lynch.state.buffer import Buffer as StateBuffer

# --- Connector Tests ---

@pytest.mark.unit
def test_tcp_connector_send_fail_not_connected():
    connector = TCPConnector(host="127.0.0.1", port=10011)
    with pytest.raises(RuntimeError):
        connector.send(b"data")

@pytest.mark.unit
def test_tcp_connector_receive_eof():
    connector = TCPConnector(host="127.0.0.1", port=10011)
    connector.socket = Mock()
    connector.socket.recv.return_value = b'' # Connection closed
    
    with pytest.raises(ConnectionError):
        connector.receive()

@pytest.mark.unit
def test_tcp_connector_timeout():
    connector = TCPConnector(host="127.0.0.1", port=10011)
    connector.socket = Mock()
    connector.socket.recv.side_effect = socket.timeout
    
    assert connector.receive() is None

@pytest.mark.unit
def test_multicast_connector_bind():
    connector = MulticastConnector(host="224.5.23.2", port=10010)
    with patch("socket.socket") as mock_socket:
        mock_instance = mock_socket.return_value
        connector.connect()
        mock_instance.bind.assert_called_once()
        mock_instance.setsockopt.assert_any_call(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, ANY)

@pytest.mark.unit
def test_multicast_receive_zero_length():
    """Zero-length UDP datagrams should return None, not propagate."""
    connector = MulticastConnector(host="224.5.23.2", port=10010)
    connector.socket = Mock()
    connector.socket.recv.return_value = b""
    assert connector.receive() is None

@pytest.mark.unit
def test_multicast_receive_timeout():
    """receive() should return None on socket timeout."""
    connector = MulticastConnector(host="224.5.23.2", port=10010)
    connector.socket = Mock()
    connector.socket.recv.side_effect = socket.timeout
    assert connector.receive() is None

# --- Parser Tests ---

@pytest.mark.unit
def test_json_parser_success():
    # 14-float state vector: 5 per robot (x, y, vx, vy, theta) + 4 for ball
    cur_state = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 2.0, 0.0, 0.0]
    next_state = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.5, 1.0, 0.0, 0.0]
    data = json.dumps({"cur_state": cur_state, "next_state": next_state, "action": "kick"}).encode("utf-8")
    result = JSONParser.parse_from_bytes(data)
    assert result is not None
    assert result["action"] == "kick"
    assert result["state"]["ball"]["x"] == 1.0
    assert result["state"]["ball"]["y"] == 2.0
    assert result["next_state"]["ball"]["x"] == 0.5
    assert len(result["state"]["robots"]["blue"]) == 1
    assert len(result["state"]["robots"]["yellow"]) == 1

@pytest.mark.unit
def test_json_parser_fail():
    data = b'invalid_json'
    result = JSONParser.parse_from_bytes(data)
    assert result is None

@pytest.mark.unit
def test_json_parser_short_vector():
    """A vector with fewer than 14 elements should produce state=None, not raise."""
    cur_state = [0.0, 0.0, 0.0]  # only 3 elements
    data = json.dumps({"cur_state": cur_state, "next_state": cur_state, "action": None}).encode("utf-8")
    result = JSONParser.parse_from_bytes(data)
    assert result is not None
    assert result["state"] is None
    assert result["next_state"] is None

# --- StateBuffer Tests ---

@pytest.mark.unit
def test_state_buffer_pull_empty():
    mock_connector = Mock()
    mock_parser = Mock()
    sb = StateBuffer(connector=mock_connector, parser=mock_parser)
    assert sb.pull() is None

@pytest.mark.unit
def test_state_buffer_integration():
    mock_connector = Mock()
    mock_parser = Mock()
    
    # Setup
    mock_connector.receive.return_value = b"raw_data"
    mock_parser.parse_from_bytes.return_value = {"state": "data"}
    
    sb = StateBuffer(connector=mock_connector, parser=mock_parser)
    
    # Manually trigger one run cycle logic without starting the thread
    raw_data = sb.connector.receive()
    frame = sb.parser.parse_from_bytes(raw_data)
    sb._buffer.append(frame)
    
    assert sb.pull() == {"state": "data"}

@pytest.mark.unit
def test_state_buffer_handles_connection_error():
    """Verify StateBuffer stops when connector raises ConnectionError."""
    mock_connector = Mock()
    mock_parser = Mock()
    
    # Simulate a lost connection on the first receive
    mock_connector.receive.side_effect = ConnectionError("Lost connection")
    
    sb = StateBuffer(connector=mock_connector, parser=mock_parser)
    
    # We call run() manually to verify the loop breaks
    sb.run()
    
    # Verify the connector was closed as part of the teardown
    mock_connector.close.assert_called_once()
