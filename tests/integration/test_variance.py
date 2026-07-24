"""Integration tests for Variance strategies within Manager."""

import pytest
import time
from lynch.field.manager import Manager

@pytest.mark.integration
def test_manager_applies_uniform_noise(mock_grsim):
    """Verify that Manager correctly applies UniformRandomVariance from provided dicts."""
    manager = Manager()

    template = {
        "ball": {"x": 0.0, "y": 0.0},
        "robots": {"blue": [{"id": 10, "x": 0.0, "y": 0.0, "theta": 0.0}]}
    }

    scenario_config = {
        "strategy": "uniform_random",
        "variance": {
            "ball": {"x": (5.0, 5.0)}, # Forced offset of 5.0
            "robots": {"blue": {"10": {"theta": (1.0, 1.0)}}} # Forced offset of 1.0
        }
    }

    manager.setup_scenario(template, scenario_config)

    # 3. Verify Protobuf results at mock server
    time.sleep(0.1)
    assert mock_grsim.received_count > 0
    last_packet = mock_grsim.last_packet

    # Ball should be at 5.0 (0.0 + 5.0 offset)
    assert last_packet.replacement.ball.x == pytest.approx(5.0)

    # Robot 10 should have theta (dir) of 1.0 (0.0 + 1.0 offset)
    rob10 = next(r for r in last_packet.replacement.robots if r.id == 10)
    assert rob10.dir == pytest.approx(1.0)
@pytest.mark.integration
def test_manager_applies_gaussian_noise(mock_grsim):
    """Verify that Manager correctly applies GaussianRandomVariance from provided dicts."""
    manager = Manager()
    
    template = {"ball": {"x": 0.0, "y": 0.0}, "robots": {"yellow": [], "blue": []}}
    
    scenario_config = {
        "strategy": "gaussian_random",
        "variance": {"ball": {"x": 0.0001}} # Tiny noise, should stay near 0
    }

    manager.setup_scenario(template, scenario_config)

    time.sleep(0.1)
    assert mock_grsim.received_count > 0
    assert abs(mock_grsim.last_packet.replacement.ball.x - 0.0) < 0.1
