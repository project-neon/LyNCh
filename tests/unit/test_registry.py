import pytest
from unittest.mock import MagicMock, patch
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

    mock_iter.return_value = [ (None, "mod1", None), (None, "registry", None) ]

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
