"""New unit tests for Hawk Variance strategies and recursion logic."""

import pytest
from lynch.field.variance import (
    NoVariance,
    UniformRandomVariance,
    GaussianRandomVariance
)

@pytest.fixture
def sample_baseline():
    """A representative simulation state with nested structures."""
    return {
        "ball": {"x": 1.0, "y": 2.0},
        "robots": {
            "yellow": [
                {"id": 0, "x": -1.0, "theta": 0.0},
                {"id": 5, "x": -5.0, "theta": 1.5}
            ],
            "blue": []
        },
        "metadata": {"version": 1}
    }

@pytest.mark.unit
def test_deterministic_strategy_immutability(sample_baseline):
    """Verify that deterministic strategy returns a deep copy and changes nothing."""
    strategy = NoVariance()
    result = strategy.apply(sample_baseline, {"ball": {"x": 9.9}})
    
    assert result == sample_baseline
    assert result is not sample_baseline
    
    # Nested check
    result["ball"]["x"] = 0.0
    assert sample_baseline["ball"]["x"] == 1.0

@pytest.mark.unit
def test_recursive_injection_logic_uniform(sample_baseline):
    """Verify that recursion correctly matches keys and list items by ID."""
    strategy = UniformRandomVariance(seed=42)
    
    noise = {
        "ball": {"x": (-0.1, 0.1)},
        "robots": {
            "yellow": {
                "5": {"theta": (-1.0, 1.0)} # Only randomize robot 5
            }
        }
    }
    
    result = strategy.apply(sample_baseline, noise)
    
    # Ball x should have changed
    assert result["ball"]["x"] != 1.0
    assert 0.9 <= result["ball"]["x"] <= 1.1
    
    # Ball y should NOT have changed (no noise rule)
    assert result["ball"]["y"] == 2.0
    
    # Robot 0 should NOT have changed (no noise rule for ID 0)
    assert result["robots"]["yellow"][0]["x"] == -1.0
    
    # Robot 5 theta SHOULD have changed
    assert result["robots"]["yellow"][1]["theta"] != 1.5
    assert 0.5 <= result["robots"]["yellow"][1]["theta"] <= 2.5
    
    # Robot 5 ID should be untouched (Metadata protection)
    assert result["robots"]["yellow"][1]["id"] == 5

@pytest.mark.unit
def test_gaussian_leaf_application(sample_baseline):
    """Verify Gaussian scalar noise is correctly applied."""
    strategy = GaussianRandomVariance(seed=42)
    
    # Testing scalar std_dev format
    noise = {
        "ball": {"x": 10.0} 
    }
    
    results = [strategy.apply(sample_baseline, noise)["ball"]["x"] for _ in range(50)]
    
    # Verify we have variation
    assert len(set(results)) > 1
    # Verify it stays centered around 1.0 (with large std_dev, just check if it's "noisy")
    assert any(r > 1.0 for r in results)
    assert any(r < 1.0 for r in results)

@pytest.mark.unit
def test_recursion_pruning_on_none_noise(sample_baseline):
    """Verify that if noise is None or missing keys, the baseline is returned as-is."""
    strategy = UniformRandomVariance()
    
    # Noise is empty dict
    result = strategy.apply(sample_baseline, {})
    assert result == sample_baseline
    
    # Noise is None (if the internal recursive call receives it)
    # Testing the top level directly
    result_none = strategy.apply(sample_baseline, None)
    assert result_none == sample_baseline

@pytest.mark.unit
def test_robot_list_missing_id_handling():
    """Verify that recursion handles list items that are not dicts or lack IDs."""
    strategy = UniformRandomVariance()
    baseline = {"robots": {"yellow": ["not-a-dict", {"no-id": True}]}}
    noise = {"robots": {"yellow": {"0": {"x": 1.0}}}}
    
    # Should not crash and return baseline
    result = strategy.apply(baseline, noise)
    assert result == baseline
