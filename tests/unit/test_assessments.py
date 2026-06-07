import pytest
from lynch.evaluator.assessments.goal_scored import GoalScored
from lynch.evaluator.assessments.ball_stopped import BallStopped
from lynch.evaluator.assessments.ball_out_of_bounds import BallOutOfBounds

def test_goal_scored():
    assessment = GoalScored()
    
    # Inside goal
    assert assessment.is_triggered({"ball": {"x": 4.5, "y": 0.0}}, []) is True
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

def test_ball_out_of_bounds():
    assessment = BallOutOfBounds()
    
    # Inside bounds
    assert assessment.is_triggered({"ball": {"x": 0.0, "y": 0.0}}, []) is False
    # Outside x
    assert assessment.is_triggered({"ball": {"x": 5.0, "y": 0.0}}, []) is True
    # Outside y
    assert assessment.is_triggered({"ball": {"x": 0.0, "y": 4.0}}, []) is True
