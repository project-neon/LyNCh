"""Integration tests for the Field Manager module."""

import time
import pytest
from lynch.field import Manager


@pytest.mark.integration
def test_setup_scenario_sends_grsim_packet(mock_grsim):
    """Field Manager should send a valid grSim_Packet to the mock server."""
    manager = Manager()
    
    template = {
        "ball": {"x": 1.0, "y": 2.0},
        "robots": {
            "yellow": [{"id": 0, "x": 2.0, "y": 0.0, "theta": 0.0}],
            "blue": []
        }
    }
    scenario_config = {
        "strategy": "no_variance",
        "variance": {}
    }

    manager.setup_scenario(template, scenario_config)

    # 3. Verify packet arrival at mock server
    time.sleep(0.1)  # Wait for UDP packet
    assert mock_grsim.received_count > 0
    
    last_packet = mock_grsim.last_packet
    assert last_packet.HasField("replacement")
    
    replacement = last_packet.replacement
    assert replacement.ball.x == 1.0
    assert replacement.ball.y == 2.0
    
    yellow_robots = [r for r in replacement.robots if r.yellowteam]
    assert len(yellow_robots) == 1
    assert yellow_robots[0].x == 2.0
    assert yellow_robots[0].id == 0

@pytest.mark.integration
def test_setup_scenario_with_variance(mock_grsim):
    """Field Manager should send a randomized packet when using a strategy."""
    manager = Manager()
    
    template = {
        "ball": {"x": 0.0, "y": 0.0},
        "robots": {"yellow": [], "blue": []}
    }
    # Using uniform_random with correct tuple format
    scenario_config = {
        "strategy": "uniform_random",
        "variance": {"ball": {"x": (5.0, 5.0), "y": (5.0, 5.0)}}
    }
    
    manager.setup_scenario(template, scenario_config)
    
    time.sleep(0.1)
    assert mock_grsim.received_count > 0
    
    last_packet = mock_grsim.last_packet
    replacement = last_packet.replacement
    
    # In uniform_random with (5.0, 5.0) range, it must be exactly 5.0
    assert replacement.ball.x == pytest.approx(5.0)
    assert replacement.ball.y == pytest.approx(5.0)
