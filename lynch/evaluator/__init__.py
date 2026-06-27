from .registry import AssessmentRegistry, assessment_registry
from .assessments import Assessment

# Auto-discover and register assessment modules
assessment_registry.autodiscover(".assessments")

__all__ = ["Assessment", "AssessmentRegistry", "assessment_registry"]
