import pytest
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
    from lynch.evaluator.assessments.time_limit import TimeLimit
    limit = 10
    assessment = TimeLimit()
    assessment.limit = limit # Force small limit for test

    for _ in range(limit):
        assert assessment.is_triggered({}, []) is False

    assert assessment.is_triggered({}, []) is True
    assert assessment.get_rewards() == {"striker": -1.0, "keeper": 1.0}

@pytest.mark.unit
def test_time_limit_auto_reset():
    """After triggering, the counter should auto-reset to 0."""
    from lynch.evaluator.assessments.time_limit import TimeLimit

    limit = 10
    assessment = TimeLimit()
    assessment.limit = limit

    # Trigger the limit
    for _ in range(limit):
        assert assessment.is_triggered({}, []) is False
    # This call triggers and resets
    assert assessment.is_triggered({}, []) is True

    # Next call should be False again (counter reset to 0, not monotonically increasing)
    assert assessment.is_triggered({}, []) is False
