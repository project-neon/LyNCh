import pytest
from unittest.mock import MagicMock, patch
from lynch.evaluator.assessments.assessment import Assessment
from lynch.evaluator.assessments.registry import AssessmentRegistry

class MockAssessment(Assessment):
    def is_triggered(self, cur_state, history) -> bool:
        return False

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
    
    # load() should return instances now
    instances = registry.load(["a1", "a2"])
    
    assert len(instances) == 2
    assert isinstance(instances[0], A1)
    assert isinstance(instances[1], A2)

@patch("pkgutil.iter_modules")
def test_registry_autodiscover(mock_iter):
    registry = AssessmentRegistry()
    
    # Setup mock package
    mock_pkg = MagicMock()
    mock_pkg.__path__ = ["/dummy/path"]
    mock_pkg.__name__ = "fake.package"
    
    mock_iter.return_value = [ (None, "mod1", None), (None, "registry", None) ]
    
    # First call is the package itself, second is the module inside.
    # The autodiscover function uses importlib.import_module(package_path)
    # The relative path logic in autodiscover might be changing the call args.
    
    with patch("importlib.import_module", return_value=mock_pkg) as mock_import:
        registry.autodiscover("fake.package")
        
        # Check that mod1 was imported with absolute path
        # The first call was the package itself, second should be mod1
        mock_import.assert_any_call("fake.package.mod1")
