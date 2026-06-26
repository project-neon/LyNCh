import pytest
from unittest.mock import patch
from lynch.state.session import initialize_session, DataMode, Session
from lynch.state.buffer import Buffer
from lynch.state.tcp_connector import TCPConnector
from lynch.state.multicast_connector import MulticastConnector
from lynch.state.parsers import JSONParser, ProtobufParser


@pytest.mark.unit
def test_initialize_session_neonfc():
    """NEONFC mode should wire TCPConnector+JSONParser for data and a separate signal connector."""
    with patch.object(TCPConnector, "__init__", return_value=None) as mock_tcp_init, \
         patch.object(Buffer, "__init__", return_value=None) as mock_buf_init:
        session = initialize_session(
            mode=DataMode.NEONFC,
            neon_host="127.0.0.1",
            data_port=10001,
            signal_port=10002,
        )

    assert isinstance(session, Session)
    assert isinstance(session.connector, TCPConnector)
    mock_buf_init.assert_called_once()
    _, kwargs = mock_buf_init.call_args
    assert isinstance(kwargs["connector"], TCPConnector)
    assert kwargs["parser"] is JSONParser


@pytest.mark.unit
def test_initialize_session_direct():
    """DIRECT mode should wire MulticastConnector+ProtobufParser for data."""
    with patch.object(MulticastConnector, "__init__", return_value=None) as mock_mc_init, \
         patch.object(Buffer, "__init__", return_value=None) as mock_buf_init:
        session = initialize_session(
            mode=DataMode.DIRECT,
            neon_host="127.0.0.1",
            data_port=10001,
            signal_port=10002,
            vision_host="224.5.23.2",
            vision_port=10010,
        )

    assert isinstance(session, Session)
    mock_buf_init.assert_called_once()
    _, kwargs = mock_buf_init.call_args
    assert isinstance(kwargs["connector"], MulticastConnector)
    assert kwargs["parser"] is ProtobufParser


@pytest.mark.unit
def test_initialize_session_direct_missing_vision():
    """DIRECT mode without vision host/port should raise ValueError."""
    with pytest.raises(ValueError, match="Vision host/port required"):
        initialize_session(
            mode=DataMode.DIRECT,
            neon_host="127.0.0.1",
            data_port=10001,
            signal_port=10002,
        )
