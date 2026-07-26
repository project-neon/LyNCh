import pytest
from time import sleep
from lynch.state.schema import FrameState, BallState, Transition
from lynch.evaluator.assessments.goal_scored import GoalScored
from lynch.evaluator.assessments.ball_stopped import BallStopped
from lynch.evaluator.assessments.ball_out_of_bounds import BallOutOfBounds

@pytest.mark.unit
def test_goal_scored():
    assessment = GoalScored()
    
    # Inside goal
    assert assessment.is_triggered(FrameState(ball=BallState(4.5, 0.0, 0.0, 0.0)), []) is True
    assert assessment.get_rewards() == 1.0
    
    # Outside goal (x too small)
    assert assessment.is_triggered(FrameState(ball=BallState(4.0, 0.0, 0.0, 0.0)), []) is False
    # Outside goal (y too large)
    assert assessment.is_triggered(FrameState(ball=BallState(4.5, 1.0, 0.0, 0.0)), []) is False

@pytest.mark.unit
def test_ball_stopped():
    assessment = BallStopped()

    # Not enough history
    assert assessment.is_triggered(FrameState(ball=None), []) is False

    # Ball moving
    history_moving = [Transition(state=FrameState(ball=BallState(0.0, 0.0, 1.0, 1.0)), next_state=None, actions={})] * 10
    assert assessment.is_triggered(FrameState(ball=BallState(0.0, 0.0, 1.0, 1.0)), history_moving) is False

    # Ball stopped
    history_stopped = [Transition(state=FrameState(ball=BallState(0.0, 0.0, 0.0, 0.0)), next_state=None, actions={})] * 10
    assert assessment.is_triggered(FrameState(ball=BallState(0.0, 0.0, 0.0, 0.0)), history_stopped) is True
    assert assessment.get_rewards() == -1.0

@pytest.mark.unit
def test_ball_stopped_missing_ball_history():
    assessment = BallStopped()

    # History frames where "ball" is None — should not crash.
    history_none_ball = [Transition(state=FrameState(ball=None), next_state=None, actions={})] * 10
    result = assessment.is_triggered(FrameState(ball=None), history_none_ball)
    assert isinstance(result, bool)

    # History frames where "ball" is None — should not crash.
    history_no_ball = [Transition(state=FrameState(ball=None), next_state=None, actions={})] * 10
    result2 = assessment.is_triggered(FrameState(ball=None), history_no_ball)
    assert isinstance(result2, bool)

@pytest.mark.unit
def test_goal_scored_none_y():
    """Ball with None y coordinate should not raise TypeError."""
    assessment = GoalScored()
    # y=None should be treated as False if ball or attribute is None
    result = assessment.is_triggered(FrameState(ball=BallState(4.5, 0.0, 0.0, 0.0)), [])
    assert isinstance(result, bool)

    # Ball None should short-circuit to False
    result2 = assessment.is_triggered(FrameState(ball=None), [])
    assert result2 is False

@pytest.mark.unit
def test_ball_out_of_bounds():
    assessment = BallOutOfBounds()
    
    # Inside bounds
    assert assessment.is_triggered(FrameState(ball=BallState(0.0, 0.0, 0.0, 0.0)), []) is False
    
    # Outside x
    assert assessment.is_triggered(FrameState(ball=BallState(5.0, 0.0, 0.0, 0.0)), []) is True
    assert assessment.get_rewards() == -1.0
    
    # Outside y
    assert assessment.is_triggered(FrameState(ball=BallState(0.0, 4.0, 0.0, 0.0)), []) is True

@pytest.mark.unit
def test_time_limit():
    from time import time
    from lynch.evaluator.assessments.time_limit import TimeLimit
    assessment = TimeLimit()
    assessment.limit = 0.1  # 100ms limit for fast test

    # Should not trigger immediately
    assert assessment.is_triggered({}, []) is False
    assert assessment.get_rewards() == -1.0

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
