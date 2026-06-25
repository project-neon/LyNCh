"""Unit tests for the Field Manager."""

import pytest
from unittest.mock import patch
from lynch.field import Manager

@pytest.mark.unit
def test_init_creates_socket():
    """Should initialize without parameters and create a socket."""
    manager = Manager()
    # Note: socket is private __socket, but we can check if it exists or if _create_socket was called
    assert hasattr(manager, "_Manager__socket")

@pytest.mark.unit
def test_apply_strategy_resolution():
    """Should resolve strategy names and apply them to template."""
    baseline = {"ball": {"x": 1.0, "y": 1.0}}
    variance = None
    
    # Testing 'no_variance'
    result = Manager._apply_strategy(baseline, variance, "no_variance")
    assert result == baseline
    assert result is not baseline # Should be a deepcopy
    assert isinstance(result, dict)

@pytest.mark.unit
def test_apply_strategy_unknown_raises_helpful_error():
    """Unknown strategy name should raise KeyError with valid options listed."""
    with pytest.raises(KeyError, match="uniform_random"):
        Manager._apply_strategy({}, None, "uniformrand")

@pytest.mark.unit
def test_send_replacement_malformed_robot_no_crash():
    """Malformed robot entries (non-dict or missing fields) should not crash."""
    manager = Manager()
    positions = {
        "ball": {"x": 1.0, "y": 2.0},
        "robots": {
            "blue": [
                {"id": 0, "x": 0.0, "y": 0.0, "theta": 0.0},
                "not-a-dict",
                {"id": 1},  # missing x, y, theta
            ],
            "yellow": [],
        },
    }
    # Should not raise
    manager._send_replacement(positions)

@pytest.mark.unit
def test_send_replacement_missing_ball_key():
    """Positions without 'ball' key should not crash."""
    manager = Manager()
    positions = {"robots": {"blue": [], "yellow": []}}
    manager._send_replacement(positions)

@pytest.mark.unit
@patch("lynch.field.manager.Manager._send_replacement")
def test_setup_scenario_pipeline(mock_send):
    """Should execute the pipeline: Apply Variance -> Send Replacement."""
    manager = Manager()
    
    template = {
        "ball": {"x": 0.0, "y": 0.0}, 
        "robots": {"yellow": [], "blue": []}
    }
    scenario_config = {
        "strategy": "no_variance",
        "variance": {}
    }

    # Trigger the pipeline
    manager.setup_scenario(template, scenario_config)

    # Verify that it called the send method with the correct data
    assert mock_send.called
    sent_data = mock_send.call_args[0][0]
    assert sent_data == template
