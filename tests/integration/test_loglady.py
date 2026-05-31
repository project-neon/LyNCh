"""Integration tests for LogLady with real socket communication and multiprocessing."""

import time
import pytest
from lynch.loglady import StateBuffer, AutoRefProvider, NeonFCProvider

@pytest.mark.integration
def test_state_buffer_receives_data_from_autoref(mock_autoref):
    """Verify end-to-end data flow from AutoRef mock to StateBuffer."""
    provider = AutoRefProvider(host="224.5.23.2", port=10010)
    sb = StateBuffer(provider=provider)
    
    sb.start()
    
    # Wait for data to flow through process -> pipe
    time.sleep(0.2)
    data = sb.pull()
    
    try:
        assert data is not None
        assert "state" in data
        assert "uuid" in data["state"]
        assert data["state"]["uuid"].startswith("test-packet-")
    finally:
        sb.stop()

@pytest.mark.integration
def test_state_buffer_receives_data_from_neonfc(mock_neonfc):
    """Verify end-to-end data flow from NeonFC mock to StateBuffer."""
    provider = NeonFCProvider(host="127.0.0.1", port=10011)
    sb = StateBuffer(provider=provider)
    
    sb.start()
    
    time.sleep(0.2)
    data = sb.pull()
    
    try:
        assert data is not None
        assert "state" in data
        assert "action" in data
        assert data["action"].startswith("action-")
    finally:
        sb.stop()

@pytest.mark.integration
def test_state_buffer_clean_stop():
    """Verify that stop() actually kills the background process and closes resources."""
    # We use a real provider but no server to test the timeout/stop logic
    provider = AutoRefProvider(host="127.0.0.1", port=20000) 
    sb = StateBuffer(provider=provider)
    
    sb.start()
    assert sb.is_alive()
    
    sb.stop()
    
    # Process should be dead
    assert not sb.is_alive()
    # Writer end of pipe (in child) should be closed (we can't easily check child handles, 
    # but we verify no hang)
