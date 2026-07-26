import importlib
import logging
import pkgutil
import inspect
from dataclasses import dataclass
from typing import Dict, Type, List
from .assessments import Assessment


logger = logging.getLogger(__name__)


@dataclass
class TestResult:
    is_terminal: bool
    rewards: float
    reason: str


class AssessmentRegistry:
    """Central registry for assessment classes.

    Manages registration, discovery, loading, and evaluation of assessments.
    """
    def __init__(self):
        self._registry: Dict[str, Type] = {}
        self._loaded: List = []

    def register(self, name: str):
        """Decorator to register an assessment class under a PascalCase name."""
        def decorator(cls: Type):
            if not issubclass(cls, Assessment):
                raise TypeError(f"'{cls.__name__}' is not a subclass of Assessment")
            self._registry[name] = cls
            return cls
        return decorator

    def get(self, name: str) -> Type:
        if name not in self._registry:
            raise KeyError(f"Assessment '{name}' is not registered")
        return self._registry[name]

    def load(self, assessments: List) -> None:
        """Instantiate assessments and store them for evaluation.

        Each item can be a plain name string or a dict with ``name`` and
        optional ``config`` keys:

        - ``"GoalScored"`` — instantiated with no config
        - ``{"name": "BallStopped", "config": {"speed_threshold": 0.1}}`` — config forwarded to ``__init__``
        """
        loaded = []
        for item in assessments:
            if isinstance(item, str):
                loaded.append(self.get(item)())
            elif isinstance(item, dict):
                name = item["name"]
                config = item.get("config", {})
                loaded.append(self.get(name)(config=config))
            else:
                raise TypeError(f"Invalid assessment spec: {item!r}")
        self._loaded = loaded

    def evaluate(self, cur_state: dict, history: List[dict]) -> TestResult:
        """Iterate loaded assessments; return the first terminal result, or a non-terminal default."""
        for assessment in self._loaded:
            if assessment.is_triggered(cur_state, history):
                return TestResult(
                    is_terminal=True,
                    rewards=assessment.get_rewards(),
                    reason=type(assessment).__name__,
                )
        return TestResult(
            is_terminal=False,
            rewards=0.0,
            reason="Running",
        )

    def autodiscover(self, package: str) -> None:
        if package.startswith("."):
            caller_package = inspect.stack()[1].frame.f_globals["__name__"]
        else:
            caller_package = None

        pkg_module = importlib.import_module(package, caller_package)

        for _, module_name, _ in pkgutil.iter_modules(pkg_module.__path__):
            if module_name in ["registry", "assessment"]:
                continue
            try:
                importlib.import_module(f"{pkg_module.__name__}.{module_name}")
            except Exception as e:
                logger.warning(f"Failed to import assessment module '{module_name}': {e}")


assessment_registry = AssessmentRegistry()
