"""Unit tests for the Hawk (EnvManager) orchestrator."""

import pytest
import json
from unittest.mock import patch
from lynch.field import Manager

@pytest.fixture
def mock_config_path(tmp_path):
    """Creates a valid test_config.json in a temp directory."""
    config_data = {
        "scenarios": {
            "penalty_kick": {
                "template": "penalty_kick_positions.json",
                "strategy": "no_variance",
                "variance": {"ball": {"x": 0.1}}
            }
        }
    }
    config_file = tmp_path / "test_config.json"
    config_file.write_text(json.dumps(config_data))
    return str(config_file)

@pytest.mark.unit
def test_init_loads_scenarios_dict(mock_config_path):
    """Should load the scenarios as a dictionary for O(1) lookup."""
    manager = Manager(config_path=mock_config_path)
    assert isinstance(manager.scenarios, dict)
    assert "penalty_kick" in manager.scenarios
    assert manager.scenarios["penalty_kick"]["strategy"] == "no_variance"

@pytest.mark.unit
def test_load_file_static_helper(tmp_path):
    """Should correctly load any JSON file into a dictionary."""
    data = {"test": 123}
    dummy_file = tmp_path / "dummy.json"
    dummy_file.write_text(json.dumps(data))

    result = Manager._load_file(str(dummy_file))
    assert result == data

@pytest.mark.unit
def test_apply_strategy_resolution():
    """Should resolve string names to variance classes and apply them."""
    baseline = {"ball": {"x": 1.0}}
    variance = None

    # Testing resolution of 'no_variance'
    result = Manager._apply_strategy(baseline, variance, "no_variance")
    assert result == baseline
    assert result is not baseline
    assert isinstance(result, dict)

@pytest.mark.unit
@patch("lynch.field.manager.Manager._load_file")
@patch("lynch.field.manager.Manager._send_replacement")
def test_setup_scenario_pipeline(mock_send, mock_load, mock_config_path):
    """Should execute the full pipeline: Load -> Apply -> Send."""
    # Setup side_effect: 
    # 1st call (Init): Return config dict
    # 2nd call (setup_scenario): Return baseline dict
    config_dict = {
        "scenarios": {
            "penalty_kick": {
                "template": "base.json",
                "strategy": "no_variance",
                "variance": {}
            }
        }
    }
    baseline_dict = {"ball": {"x": 0.0, "y": 0.0}, "robots": {"yellow": [], "blue": []}}
    mock_load.side_effect = [config_dict, baseline_dict]

    manager = Manager(config_path=mock_config_path)

    # Trigger the pipeline
    manager.setup_scenario("penalty_kick")

    # Verify the pipeline steps
    assert mock_load.call_count == 2
    assert mock_send.called

    # Verify data flow
    sent_data = mock_send.call_args[0][0]
    assert sent_data["ball"]["x"] == 0.0
