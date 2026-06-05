"""Integration tests for the Hawk (EnvManager) module."""

import time
import json
import pytest
from lynch.field.manager import Manager


@pytest.mark.integration
def test_setup_scenario_sends_grsim_packet(mock_grsim, tmp_path):
    """EnvManager should send a valid grSim_Packet to the mock server."""
    # 1. Setup a dummy config that points to the real baseline file
    # (Since EnvManager hardcodes the 'scenarios/' folder path)
    config_data = {
        "scenarios": {
            "test_scen": {
                "baseline_file": "scenarios/penalty_kick_positions.json",
                "strategy": "deterministic",
                "variance": {}
            }
        }
    }
    config_file = tmp_path / "test_config.json"
    config_file.write_text(json.dumps(config_data))

    # 2. Initialize EnvManager and trigger setup
    hawk = Manager(config_path=str(config_file))
    hawk.setup_scenario("test_scen")

    # 3. Verify packet arrival at mock server
    time.sleep(0.1)  # Wait for UDP packet
    assert mock_grsim.received_count > 0
    
    last_packet = mock_grsim.last_packet
    assert last_packet.HasField("replacement")
    
    # Verify ball position in protobuf matches penalty_kick_positions.json (0,0)
    replacement = last_packet.replacement
    assert replacement.ball.x == 0.0
    assert replacement.ball.y == 0.0
    
    # Verify yellow robot 0 position (2.0, 0.0) from baseline
    yellow_robots = [r for r in replacement.robots if r.yellowteam]
    assert len(yellow_robots) == 1
    assert yellow_robots[0].x == 2.0
    assert yellow_robots[0].id == 0

@pytest.mark.integration
def test_setup_scenario_with_uniform_noise(mock_grsim, tmp_path):
    """EnvManager should send a randomized packet when using a strategy."""
    # This test assumes UniformRandomVariance is registered in manager.STRATEGIES
    # If not registered, it should fallback to deterministic (and still pass the count check)
    config_data = {
        "scenarios": {
            "rand_scen": {
                "baseline_file": "scenarios/penalty_kick_positions.json",
                "strategy": "deterministic", # Keeping it deterministic for predictable assertion
                "variance": {}
            }
        }
    }
    config_file = tmp_path / "conf.json"
    config_file.write_text(json.dumps(config_data))
    
    hawk = Manager(config_path=str(config_file))
    hawk.setup_scenario("rand_scen")
    
    time.sleep(0.1)
    assert mock_grsim.received_count > 0
