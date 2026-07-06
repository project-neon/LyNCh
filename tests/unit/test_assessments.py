import pytest
from time import sleep
from lynch.evaluator.assessments.goal_scored import GoalScored
from lynch.evaluator.assessments.ball_stopped import BallStopped
from lynch.evaluator.assessments.ball_out_of_bounds import BallOutOfBounds

@pytest.mark.unit
def test_goal_scored():
    assessment = GoalScored()
    
    # Inside goal
    assert assessment.is_triggered({"ball": {"x": 4.5, "y": 0.0}}, []) is True
    assert assessment.get_rewards() == {"striker": 1, "keeper": -1}
    
    # Outside goal (x too small)
    assert assessment.is_triggered({"ball": {"x": 4.0, "y": 0.0}}, []) is False
    # Outside goal (y too large)
    assert assessment.is_triggered({"ball": {"x": 4.5, "y": 1.0}}, []) is False

@pytest.mark.unit
def test_ball_stopped():
    assessment = BallStopped()

    # Not enough history
    assert assessment.is_triggered({}, []) is False

    # Ball moving
    history_moving = [{"ball": {"vx": 1.0, "vy": 1.0}}] * 10
    assert assessment.is_triggered({"ball": {"vx": 1.0, "vy": 1.0}}, history_moving) is False

    # Ball stopped
    history_stopped = [{"ball": {"vx": 0.0, "vy": 0.0}}] * 10
    assert assessment.is_triggered({"ball": {"vx": 0.0, "vy": 0.0}}, history_stopped) is True
    assert assessment.get_rewards() == {"striker": -1, "keeper": 1}

@pytest.mark.unit
def test_ball_stopped_missing_ball_history():
    assessment = BallStopped()

    # History frames where "ball" is None — should not crash.
    # _get_speed returns 0.0 for None ball (treated as zero-velocity),
    # so with enough frames it triggers. The key assertion is no crash.
    history_none_ball = [{"ball": None}] * 10
    result = assessment.is_triggered({"ball": None}, history_none_ball)
    assert isinstance(result, bool)

    # History frames where "ball" key is missing entirely — should not crash
    history_no_ball = [{}] * 10
    result2 = assessment.is_triggered({}, history_no_ball)
    assert isinstance(result2, bool)

@pytest.mark.unit
def test_goal_scored_none_y():
    """Ball with None y coordinate should not raise TypeError."""
    assessment = GoalScored()
    # y=None should be treated as 0.0 via get default
    result = assessment.is_triggered({"ball": {"x": 4.5, "y": None}}, [])
    assert isinstance(result, bool)

    # x=None should short-circuit to False
    result2 = assessment.is_triggered({"ball": {"x": None, "y": 0.0}}, [])
    assert result2 is False

@pytest.mark.unit
def test_ball_out_of_bounds():
    assessment = BallOutOfBounds()
    
    # Inside bounds
    assert assessment.is_triggered({"ball": {"x": 0.0, "y": 0.0}}, []) is False
    
    # Outside x
    assert assessment.is_triggered({"ball": {"x": 5.0, "y": 0.0}}, []) is True
    assert assessment.get_rewards() == {"striker": -1, "keeper": 1}
    
    # Outside y
    assert assessment.is_triggered({"ball": {"x": 0.0, "y": 4.0}}, []) is True

@pytest.mark.unit
def test_time_limit():
    from time import time
    from lynch.evaluator.assessments.time_limit import TimeLimit
    assessment = TimeLimit()
    assessment.limit = 0.1  # 100ms limit for fast test

    # Should not trigger immediately
    assert assessment.is_triggered({}, []) is False
    assert assessment.get_rewards() == {"striker": -1.0, "keeper": 1.0}

@pytest.mark.unit
def test_time_limit_auto_reset():
    """After triggering, the timer should auto-reset for next episode."""
    from unittest.mock import patch
    from lynch.evaluator.assessments.time_limit import TimeLimit

    # Create a mock time that progresses
    mock_time = [0.0]

    def fake_time():
        return mock_time[0]

    with patch("lynch.evaluator.assessments.time_limit.time", fake_time):
        assessment = TimeLimit()
        assessment.limit = 0.1  # 100ms

        # Initially, not triggered (time is 0, same as start_time)
        mock_time[0] = 0.0
        assert assessment.is_triggered({}, []) is False

        # After limit seconds, triggers and resets start_time
        mock_time[0] = 0.15
        assert assessment.is_triggered({}, []) is True

        # After reset, start_time = 0.15, so need to advance again past limit
        assert assessment.is_triggered({}, []) is False  # no time passed
        mock_time[0] = 0.26  # 0.15 + 0.11 > 0.1 limit
        assert assessment.is_triggered({}, []) is True  # triggers again
