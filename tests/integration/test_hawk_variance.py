"""New integration tests for Hawk Variance strategies within EnvManager."""

import pytest
import json
import time
import pathlib
from lynch.hawk.manager import EnvManager

@pytest.mark.integration
def test_manager_resolves_and_applies_uniform_noise(mock_grsim, tmp_path):
    """Verify that EnvManager correctly applies UniformRandomVariance from config."""
    # 1. Prepare data
    baseline_data = {
        "ball": {"x": 0.0, "y": 0.0},
        "robots": {"yellow": [{"id": 10, "x": 0.0, "y": 0.0, "theta": 0.0}], "blue": []}
    }
    # Create baseline file in the project's 'scenarios/' folder (mocking the structure)
    # Note: manager.py uses _ROOT_DIR / "scenarios" / base_path
    # In integration tests, we rely on the real scenarios folder existing.
    # We will write a temp file there just for this test.
    import pathlib
    scenarios_dir = pathlib.Path(__file__).parent.parent.parent / "scenarios"
    baseline_file = scenarios_dir / "integration_test_temp.json"
    baseline_file.write_text(json.dumps(baseline_data))

    try:
        config_data = {
            "scenarios": {
                "rand_test": {
                    "baseline_file": "scenarios/integration_test_temp.json",
                    "strategy": "uniform_random",
                    "variance": {
                        "ball": {"x": (5.0, 5.0)}, # Forced offset of 5.0
                        "robots": {"yellow": {"10": {"theta": (1.0, 1.0)}}} # Forced offset of 1.0
                    }
                }
            }
        }
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps(config_data))

        # 2. Run EnvManager
        manager = EnvManager(config_path=str(config_file))
        manager.setup_scenario("rand_test")

        # 3. Verify Protobuf results at mock server
        time.sleep(0.1)
        assert mock_grsim.received_count > 0
        last_packet = mock_grsim.last_packet
        
        # Ball should be at 5.0 (0.0 + 5.0 offset)
        assert last_packet.replacement.ball.x == pytest.approx(5.0)
        
        # Robot 10 should have theta (dir) of 1.0 (0.0 + 1.0 offset)
        rob10 = next(r for r in last_packet.replacement.robots if r.id == 10)
        assert rob10.dir == pytest.approx(1.0)

    finally:
        # Cleanup temp file
        if baseline_file.exists():
            baseline_file.unlink()

@pytest.mark.integration
def test_manager_resolves_and_applies_gaussian_noise(mock_grsim, tmp_path):
    """Verify that EnvManager correctly applies GaussianRandomVariance from config."""
    scenarios_dir = pathlib.Path(__file__).parent.parent.parent / "scenarios"
    baseline_file = scenarios_dir / "integration_test_temp_gauss.json"
    baseline_file.write_text(json.dumps({"ball": {"x": 0.0, "y": 0.0}, "robots": {"yellow": [], "blue": []}}))

    try:
        config_data = {
            "scenarios": {
                "gauss_test": {
                    "baseline_file": "scenarios/integration_test_temp_gauss.json",
                    "strategy": "gaussian_random",
                    "variance": {"ball": {"x": 0.0001}} # Tiny noise, should stay near 0
                }
            }
        }
        config_file = tmp_path / "config_gauss.json"
        config_file.write_text(json.dumps(config_data))

        manager = EnvManager(config_path=str(config_file))
        manager.setup_scenario("gauss_test")

        time.sleep(0.1)
        assert mock_grsim.received_count > 0
        assert abs(mock_grsim.last_packet.replacement.ball.x - 0.0) < 0.1

    finally:
        if baseline_file.exists():
            baseline_file.unlink()

