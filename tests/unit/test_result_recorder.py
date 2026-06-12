import json
import pytest
import os
from pathlib import Path
from lynch.result.recorder import Recorder

@pytest.fixture
def temp_batch_dir(tmp_path):
    """Creates a temporary directory for batch results."""
    return tmp_path / "test_batch"

@pytest.fixture
def recorder(temp_batch_dir):
    """Provides a Recorder instance."""
    return Recorder(dir_path=str(temp_batch_dir), max_history_size=5)

def test_recorder_lifecycle_and_persistence(recorder, temp_batch_dir):
    """Verify that Recorder creates files and persists transitions correctly."""
    scenario_id = "test_run"
    recorder.start_scenario(scenario_id)
    
    # 1. Check file creation
    files = list(temp_batch_dir.glob(f"history_{scenario_id}_*.jsonl"))
    assert len(files) == 1
    history_file = files[0]

    # 2. Record transitions
    t1 = {"s": 1, "s_prime": 2, "a": 0, "r": {"striker": 0, "keeper": 0}}
    t2 = {"s": 2, "s_prime": 3, "a": 1, "r": {"striker": 1, "keeper": -1}}
    
    recorder.put(t1)
    recorder.put(t2)
    
    # 3. Verify history windowing (RAM)
    assert len(recorder.history) == 2
    assert recorder.history[-1] == t2

    recorder.end_scenario()
    
    # 4. Verify persistence (Disk)
    with open(history_file, "r") as f:
        lines = f.readlines()
        assert len(lines) == 2
        assert json.loads(lines[0]) == t1
        assert json.loads(lines[1]) == t2
    
    # 5. Verify history reset
    assert len(recorder.history) == 0

def test_put_schema_validation(recorder):
    """Verify that put() raises ValueError on malformed transitions."""
    recorder.start_scenario("schema_test")
    
    # Missing 'r'
    bad_t = {"s": 1, "s_prime": 2, "a": 0}
    with pytest.raises(ValueError, match="r"):
        recorder.put(bad_t)

def test_summarize_batch_logic(temp_batch_dir, recorder):
    """Verify that summarize_batch correctly aggregates multiple scenario files."""
    
    # Scenario 1: Striker Wins
    recorder.start_scenario("win")
    recorder.put({"s": 0, "s_prime": 1, "a": 0, "r": {"striker": 0, "keeper": 0}})
    recorder.put({"s": 1, "s_prime": 2, "a": 0, "r": {"striker": 1, "keeper": -1}})
    recorder.end_scenario()
    
    # Scenario 2: Timeout (Keeper Wins)
    recorder.start_scenario("timeout")
    recorder.put({"s": 0, "s_prime": 1, "a": 0, "r": {"striker": -0.5, "keeper": 0.5}})
    recorder.end_scenario()
    
    # Scenario 3: Empty (Should be skipped)
    recorder.start_scenario("empty")
    recorder.end_scenario()

    # Run Aggregation
    recorder.summarize_batch()
    
    summary_file = temp_batch_dir / "summary.json"
    assert summary_file.exists()
    
    with open(summary_file, "r") as f:
        summary = json.load(f)
        
    # Stats Verification:
    # tests_ran: win, timeout (empty skipped because it has no lines)
    assert summary["tests_ran"] == 2 
    # tests_passed: win (1, -1), timeout (-0.5, 0.5) -> Both are != 0
    assert summary["tests_passed"] == 2
    
    # Scores: (1 + -0.5) = 0.5 | (-1 + 0.5) = -0.5
    assert summary["striker_total_score"] == pytest.approx(0.5)
    assert summary["keeper_total_score"] == pytest.approx(-0.5)
    
    # Averages: 0.5 / 2 = 0.25 | -0.5 / 2 = -0.25
    assert summary["striker_avg_score"] == pytest.approx(0.25)
    assert summary["keeper_avg_score"] == pytest.approx(-0.25)

def test_summarize_batch_corruption_handling(temp_batch_dir, recorder):
    """Verify that summarize_batch skips corrupted files without crashing."""
    
    # 1. Create a valid file
    recorder.start_scenario("valid")
    recorder.put({"s": 0, "s_prime": 1, "a": 0, "r": {"striker": 1, "keeper": -1}})
    recorder.end_scenario()
    
    # 2. Manually create a corrupted file
    corrupt_file = temp_batch_dir / "history_corrupt_9999.jsonl"
    with open(corrupt_file, "w") as f:
        f.write('{"s": 0, "s_prime": 1, "a": 0, "r": {"striker": 1, "keeper": -1}}\n')
        f.write('{"s": 1, "s_prime": 2, "a": 0, "r": {MALFORMED_JSON}') 

    # 3. Run Aggregation
    # Should NOT raise JSONDecodeError
    recorder.summarize_batch()
    
    with open(temp_batch_dir / "summary.json", "r") as f:
        summary = json.load(f)
        
    # Should only have counted the 1 valid file
    assert summary["tests_ran"] == 1
    assert summary["striker_total_score"] == 1.0

def test_history_windowing_maxlen(recorder):
    """Verify that the history deque respects maxlen."""
    # recorder initialized with maxlen=5 in fixture
    recorder.start_scenario("window_test")
    for i in range(10):
        recorder.put({"s": i, "s_prime": i+1, "a": 0, "r": {"striker": 0, "keeper": 0}})
    
    assert len(recorder.history) == 5
    assert recorder.history[-1]["s"] == 9
    assert recorder.history[0]["s"] == 5
