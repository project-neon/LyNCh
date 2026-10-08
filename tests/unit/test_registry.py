import pytest
from unittest.mock import MagicMock, patch
from pkgutil import ModuleInfo
from lynch.evaluator.registry import AssessmentRegistry

class MockAssessment:
    def is_triggered(self, cur_state, history) -> bool:
        return False
    def get_rewards(self):
        return {"striker": 0.0, "keeper": 0.0}

@pytest.mark.unit
def test_registry_register_and_get():
    registry = AssessmentRegistry()
    
    @registry.register("test_assessment")
    class TestAssessment(MockAssessment):
        pass
        
    assert registry.get("test_assessment") == TestAssessment
    with pytest.raises(KeyError):
        registry.get("non_existent")

@pytest.mark.unit
def test_registry_load():
    registry = AssessmentRegistry()
    
    @registry.register("a1")
    class A1(MockAssessment): pass
    
    @registry.register("a2")
    class A2(MockAssessment): pass
    
    # load() instantiates and stores internally
    registry.load(["a1", "a2"])

    assert len(registry._loaded) == 2
    assert isinstance(registry._loaded[0], A1)
    assert isinstance(registry._loaded[1], A2)

@pytest.mark.unit
@patch("pkgutil.iter_modules")
def test_registry_autodiscover(mock_iter):
    registry = AssessmentRegistry()

    # Setup mock package
    mock_pkg = MagicMock()
    mock_pkg.__path__ = ["/dummy/path"]
    mock_pkg.__name__ = "fake.package"

    mock_iter.return_value = [
        ModuleInfo(None, "mod1", False),
        ModuleInfo(None, "registry", False),
    ]

    with patch("importlib.import_module", return_value=mock_pkg) as mock_import:
        registry.autodiscover("fake.package")
        mock_import.assert_any_call("fake.package.mod1")

@pytest.mark.unit
@patch("pkgutil.iter_modules")
def test_registry_autodiscover_skips_failing_module(mock_iter):
    """If one module fails to import, others should still be discovered."""
    registry = AssessmentRegistry()

    mock_pkg = MagicMock()
    mock_pkg.__path__ = ["/dummy/path"]
    mock_pkg.__name__ = "fake.package"

    mock_iter.return_value = [
        (None, "good_mod", None),
        (None, "bad_mod", None),
        (None, "registry", None),
    ]

    def side_effect(name, *args):
        if name == "fake.package.bad_mod":
            raise ImportError("simulated failure")
        return mock_pkg

    with patch("importlib.import_module", side_effect=side_effect) as mock_import:
        registry.autodiscover("fake.package")
        # good_mod should still be imported
        mock_import.assert_any_call("fake.package.good_mod")
        mock_import.assert_any_call("fake.package.bad_mod")


# ─── terminal reward override (T16) ───────────────────────────────────────────

def _state_with_ball(x, y=0.0, with_robots=False):
    from lynch.state.schema import BallState, FrameState, RobotState
    robots = {}
    if with_robots:
        robots["blue"] = [
            RobotState(id=0, x=0.0, y=0.0, theta=0.0, vx=0.0, vy=0.0),
            RobotState(id=1, x=4.0, y=3.0, theta=0.0, vx=0.0, vy=0.0),
        ]
    return FrameState(ball=BallState(x=x, y=y, vx=0.0, vy=0.0), robots=robots)


def test_goal_keeps_its_own_reward_alongside_a_reward_provider():
    """DistanceToCenter used to clobber a goal's +1.0 whenever it was
    co-loaded, turning the outcome into a proximity score."""
    from lynch.evaluator.registry import assessment_registry

    assessment_registry.load([
        {"name": "GoalScored", "config": {}},
        {"name": "DistanceToCenter", "config": {"robot_ids": [0, 1]}},
    ])

    result = assessment_registry.evaluate(_state_with_ball(4.6), [])

    assert result.is_terminal is True
    assert result.rewards == 1.0
    assert not isinstance(result.rewards, dict)


def test_timeout_still_takes_the_shaped_reward():
    """A timeout carries no outcome, so a shaped reward is appropriate."""
    from unittest.mock import patch
    from lynch.evaluator.registry import assessment_registry

    assessment_registry.load([
        {"name": "TimeLimit", "config": {"limit": 5}},
        {"name": "DistanceToCenter", "config": {"robot_ids": [0, 1]}},
    ])

    clock = [0.0]
    with patch("lynch.evaluator.assessments.time_limit.monotonic", lambda: clock[0]):
        assert assessment_registry.evaluate(_state_with_ball(0.0, with_robots=True), []).is_terminal is False
        clock[0] = 6.0
        result = assessment_registry.evaluate(_state_with_ball(0.0, with_robots=True), [])

    assert result.is_terminal is True
    assert isinstance(result.rewards, dict)
    assert set(result.rewards) == {0, 1}
