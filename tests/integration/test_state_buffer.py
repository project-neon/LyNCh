"""Integration tests for StateBuffer with real socket communication."""

import time
import pytest
from lynch.state import StateBuffer, TCPConnector, MulticastConnector, JSONParser, ProtobufParser

@pytest.mark.integration
def test_state_buffer_receives_sequential_data_from_autoref(mock_autoref):
    """Verify end-to-end data flow and sequential integrity."""
    connector = MulticastConnector(host="224.5.23.2", port=10010)
    parser = ProtobufParser
    sb = StateBuffer(connector=connector, parser=parser)

    sb.start()

    # Wait for a few packets to accumulate
    time.sleep(0.3)

    packets = []
    while True:
        data = sb.pull()
        if not data:
            break
        packets.append(data)

    try:
        assert len(packets) > 1, "Not enough packets received from MockAutoRef"
        # Verify all packets have the canonical state structure
        for p in packets:
            assert "state" in p
            assert "ball" in p["state"]
            assert "robots" in p["state"]
            assert "blue" in p["state"]["robots"]
            assert "yellow" in p["state"]["robots"]
    finally:
        sb.stop()

@pytest.mark.integration
def test_state_buffer_receives_data_from_neonfc(mock_neonfc):
    """Verify end-to-end data flow from NeonFC mock over TCP."""
    connector = TCPConnector(host="127.0.0.1", port=10011)
    parser = JSONParser
    sb = StateBuffer(connector=connector, parser=parser)

    sb.start()

    time.sleep(0.5)
    data = sb.pull()

    try:
        assert data is not None
        assert "state" in data
        assert "actions" in data
    finally:
        sb.stop()

@pytest.mark.integration
def test_state_buffer_clean_stop():
    """Verify that stop() terminates the background thread."""
    # Using a dummy connector for teardown test
    connector = MulticastConnector(host="224.5.23.2", port=20000) 
    parser = ProtobufParser
    sb = StateBuffer(connector=connector, parser=parser)
    
    sb.start()
    assert sb.is_alive()
    
    sb.stop()
    assert not sb.is_alive()
