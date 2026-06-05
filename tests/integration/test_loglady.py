"""Integration tests for StateBuffer with real socket communication."""

import time
import pytest
from lynch.state_buffer import StateBuffer, AutoRefProvider, NeonFCProvider

@pytest.mark.integration
def test_state_buffer_receives_sequential_data_from_autoref(mock_autoref):
    """Verify end-to-end data flow and sequential integrity."""
    provider = AutoRefProvider(host="224.5.23.2", port=10010)
    sb = StateBuffer(provider=provider)
    
    sb.start()
    
    # Wait for a few packets to accumulate
    time.sleep(0.3)
    
    packets = []
    while True:
        data = sb.pull()
        if not data:
            break
        packets.append(data)
        
    # 1. Filter packets from our mock and extract their sequence numbers
    mock_indices = []
    for p in packets:
        # The mock sets source_name="MockAutoRef" and uuid="test-packet-X"
        if p["state"].get("sourceName") == "MockAutoRef":
            uuid = p["state"].get("uuid", "")
            try:
                index = int(uuid.split("-")[-1])
                mock_indices.append(index)
            except (ValueError, IndexError):
                continue
                
    try:
        assert len(mock_indices) > 1, "Not enough packets received from MockAutoRef"
        # Verify indices are strictly increasing (FIFO integrity)
        assert mock_indices == sorted(mock_indices), f"Packets were not received in FIFO order: {mock_indices}"
    finally:
        sb.stop()

@pytest.mark.integration
def test_state_buffer_receives_data_from_neonfc(mock_neonfc):
    """Verify end-to-end data flow from NeonFC mock."""
    provider = NeonFCProvider(host="127.0.0.1", port=10011)
    sb = StateBuffer(provider=provider)
    
    sb.start()
    time.sleep(0.1)
    data = sb.pull()
    
    try:
        assert data is not None
        assert "state" in data
        assert "action" in data
    finally:
        sb.stop()

@pytest.mark.integration
def test_state_buffer_clean_stop():
    """Verify that stop() terminates the background thread."""
    provider = AutoRefProvider(host="127.0.0.1", port=20000) 
    sb = StateBuffer(provider=provider)
    
    sb.start()
    assert sb.is_alive()
    
    sb.stop()
    assert not sb.is_alive()
