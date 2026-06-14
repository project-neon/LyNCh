from .assessment import Assessment
from .registry import assessment_registry

assessment_registry.autodiscover(__name__)
