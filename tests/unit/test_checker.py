from lynch.evaluator import Checker
from lynch.evaluator.assessments.registry import assessment_registry

class MockAssessment:
    def __init__(self, triggered=False):
        self._triggered = triggered
        
    def is_triggered(self, cur_state, history) -> bool:
        return self._triggered

# Register assessments for testing
@assessment_registry.register("false_assessment")
class FalseMock(MockAssessment):
    def __init__(self): super().__init__(triggered=False)

@assessment_registry.register("true_assessment")
class TrueMock(MockAssessment):
    def __init__(self): super().__init__(triggered=True)

def test_checker_should_end_returns_true_if_any_assessment_triggered():
    # Checker initialized and then loaded with one false, one true assessment
    checker = Checker()
    checker.load(["false_assessment", "true_assessment"])
    
    assert checker.should_end(cur_state={}, history=[]) is True

def test_checker_should_end_returns_false_if_no_assessments_triggered():
    # Checker initialized and then loaded with two false assessments
    checker = Checker()
    checker.load(["false_assessment", "false_assessment"])
    
    assert checker.should_end(cur_state={}, history=[]) is False
