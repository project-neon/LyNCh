import json
import pytest
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
    recorder.start_scenario(scenario_id, seed=42)

    # 1. Check file creation
    files = list(temp_batch_dir.glob(f"history_{scenario_id}_*.jsonl"))
    assert len(files) == 1
    history_file = files[0]

    # 2. Record transitions
    t1 = {"state": {"ball": {"x": 0.0}}, "prev_state": {"ball": {"x": 0.0}}, "action": {}, "rewards": {"striker": 0, "keeper": 0}}
    t2 = {"state": {"ball": {"x": 1.0}}, "prev_state": {"ball": {"x": 0.0}}, "action": {}, "rewards": {"striker": 1, "keeper": -1}}

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
    
    # Missing 'rewards'
    bad_t = {"state": {}, "prev_state": {}, "action": {}}
    with pytest.raises(ValueError, match="rewards"):
        recorder.put(bad_t)

def test_summarize_batch_logic(temp_batch_dir, recorder):
    """Verify that summarize_batch correctly aggregates multiple scenario files."""

    # Scenario 1: Striker Wins (seed=100)
    recorder.start_scenario("win", seed=100)
    recorder.put({"state": {}, "prev_state": {}, "action": {}, "rewards": {"striker": 0, "keeper": 0}})
    recorder.put({"state": {}, "prev_state": {}, "action": {}, "rewards": {"striker": 1, "keeper": -1}})
    recorder.end_scenario()

    # Scenario 2: Timeout (Keeper Wins) (seed=101)
    recorder.start_scenario("timeout", seed=101)
    recorder.put({"state": {}, "prev_state": {}, "action": {}, "rewards": {"striker": -0.5, "keeper": 0.5}})
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

    # Seeds: first=100, last=101
    assert summary["seeds"] == [100, 101]

def test_summarize_batch_corruption_handling(temp_batch_dir, recorder):
    """Verify that summarize_batch skips corrupted files without crashing."""
    
    # 1. Create a valid file
    recorder.start_scenario("valid", seed=55)
    recorder.put({"state": {}, "prev_state": {}, "action": {}, "rewards": {"striker": 1, "keeper": -1}})
    recorder.end_scenario()

    # 2. Manually create a corrupted file
    corrupt_file = temp_batch_dir / "history_corrupt_9999.jsonl"
    with open(corrupt_file, "w") as f:
        f.write('{"state": {}, "prev_state": {}, "action": {}, "rewards": {"striker": 1, "keeper": -1}}\n')
        f.write('{"state": {}, "prev_state": {}, "action": {}, "rewards": {MALFORMED_JSON}') 

    # 3. Run Aggregation
    # Should NOT raise JSONDecodeError
    recorder.summarize_batch()
    
    with open(temp_batch_dir / "summary.json", "r") as f:
        summary = json.load(f)
        
    # Should only have counted the 1 valid file
    assert summary["tests_ran"] == 1
    assert summary["striker_total_score"] == 1.0
    assert summary["seeds"] == [55, 55]

def test_history_windowing_maxlen(recorder):
    """Verify that the history deque respects maxlen."""
    # recorder initialized with maxlen=5 in fixture
    recorder.start_scenario("window_test", seed=10)
    for i in range(10):
        recorder.put({"state": {"frame": i}, "prev_state": {"frame": i-1}, "action": {}, "rewards": {"striker": 0, "keeper": 0}})

    assert len(recorder.history) == 5
    assert recorder.history[-1]["state"]["frame"] == 9
    assert recorder.history[0]["state"]["frame"] == 5
    recorder.end_scenario()

def test_start_scenario_reentrancy_closes_previous(temp_batch_dir, recorder):
    """Calling start_scenario twice without end_scenario should close the first file."""
    recorder.start_scenario("first", seed=1)
    first_file = recorder.current_file_path
    assert first_file is not None

    recorder.put({"state": {}, "prev_state": {}, "action": {}, "rewards": {"striker": 0, "keeper": 0}})

    # Call start_scenario again — should close the first file handle
    recorder.start_scenario("second", seed=2)
    second_file = recorder.current_file_path
    assert second_file is not None
    assert second_file != first_file

    # The first file should exist on disk and be closed
    first_path = temp_batch_dir / first_file
    assert first_path.exists()
    # The old file should have a valid final line (not corrupted by dangling handle)
    with open(first_path, "r") as f:
        content = f.read().strip()
        assert len(content) > 0  # had one transition written

    recorder.end_scenario()

def test_current_file_path_property(temp_batch_dir, recorder):
    """current_file_path should be None initially, a full path after start, None after end."""
    assert recorder.current_file_path is None

    recorder.start_scenario("path_test", seed=1)
    path = recorder.current_file_path
    assert path is not None
    assert isinstance(path, str)
    assert "history_path_test_" in path
    assert path.endswith(".jsonl")

    recorder.end_scenario()
    assert recorder.current_file_path is None

def test_summarize_batch_all_seeds_omitted(temp_batch_dir, recorder):
    """When no seed is passed to any start_scenario, summary should have [None, None]."""
    recorder.start_scenario("no_seed_1")
    recorder.put({"state": {}, "prev_state": {}, "action": {}, "rewards": {"striker": 1, "keeper": -1}})
    recorder.end_scenario()

    recorder.start_scenario("no_seed_2")
    recorder.put({"state": {}, "prev_state": {}, "action": {}, "rewards": {"striker": 0.5, "keeper": -0.5}})
    recorder.end_scenario()

    recorder.summarize_batch()

    with open(temp_batch_dir / "summary.json", "r") as f:
        summary = json.load(f)

    assert summary["seeds"] == [None, None]
    assert summary["tests_ran"] == 2

def test_summarize_batch_trailing_newline(temp_batch_dir, recorder):
    """A valid JSONL file with a trailing newline should still be counted."""
    # Create a scenario file with a trailing newline
    recorder.start_scenario("trailing_nl", seed=7)
    recorder.put({"state": {}, "prev_state": {}, "action": {}, "rewards": {"striker": 1, "keeper": -1}})
    recorder.end_scenario()

    # Append a trailing newline manually to simulate an editor adding it
    files = list(temp_batch_dir.glob("history_trailing_nl_*.jsonl"))
    assert len(files) == 1
    with open(files[0], "a") as f:
        f.write("\n")

    recorder.summarize_batch()

    with open(temp_batch_dir / "summary.json", "r") as f:
        summary = json.load(f)

    assert summary["tests_ran"] == 1
    assert summary["striker_total_score"] == 1.0
