import pytest
from lynch.evaluator.assessments.goal_scored import GoalScored
from lynch.evaluator.assessments.ball_stopped import BallStopped
from lynch.evaluator.assessments.ball_out_of_bounds import BallOutOfBounds

def test_goal_scored():
    assessment = GoalScored()
    
    # Inside goal
    assert assessment.is_triggered({"ball": {"x": 4.5, "y": 0.0}}, []) is True
    assert assessment.get_rewards() == {"striker": 1, "keeper": -1}
    
    # Outside goal (x too small)
    assert assessment.is_triggered({"ball": {"x": 4.0, "y": 0.0}}, []) is False
    # Outside goal (y too large)
    assert assessment.is_triggered({"ball": {"x": 4.5, "y": 1.0}}, []) is False

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

def test_ball_out_of_bounds():
    assessment = BallOutOfBounds()
    
    # Inside bounds
    assert assessment.is_triggered({"ball": {"x": 0.0, "y": 0.0}}, []) is False
    
    # Outside x
    assert assessment.is_triggered({"ball": {"x": 5.0, "y": 0.0}}, []) is True
    assert assessment.get_rewards() == {"striker": -1, "keeper": 1}
    
    # Outside y
    assert assessment.is_triggered({"ball": {"x": 0.0, "y": 4.0}}, []) is True

def test_time_limit():
    from lynch.evaluator.assessments.time_limit import TimeLimit
    limit = 10
    assessment = TimeLimit()
    assessment.limit = limit # Force small limit for test
    
    for _ in range(limit):
        assert assessment.is_triggered({}, []) is False
        
    assert assessment.is_triggered({}, []) is True
    assert assessment.get_rewards() == {"striker": -1.0, "keeper": 1.0}
