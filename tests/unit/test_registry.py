import pytest
from unittest.mock import MagicMock, patch
from lynch.evaluator.assessments.assessment import Assessment
from lynch.evaluator.registry import AssessmentRegistry

class MockAssessment:
    def is_triggered(self, cur_state, history) -> bool:
        return False
    def get_rewards(self):
        return {"striker": 0.0, "keeper": 0.0}

def test_registry_register_and_get():
    registry = AssessmentRegistry()
    
    @registry.register("test_assessment")
    class TestAssessment(MockAssessment):
        pass
        
    assert registry.get("test_assessment") == TestAssessment
    with pytest.raises(KeyError):
        registry.get("non_existent")

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
