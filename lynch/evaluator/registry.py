import importlib
import pkgutil
import inspect
from typing import Dict, Type, List
from .assessments import Assessment


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

    def load(self, names: List[str]) -> None:
        """Instantiate assessments by name and store them for evaluation."""
        self._loaded = [self.get(name)() for name in names]

    def should_end(self, cur_state: dict, history: List[dict]) -> bool:
        """Return True if any loaded assessment is triggered."""
        return any(a.is_triggered(cur_state, history) for a in self._loaded)

    def autodiscover(self, package: str) -> None:
        if package.startswith("."):
            caller_package = inspect.stack()[1].frame.f_globals["__name__"]
            if "." in caller_package:
                caller_package = caller_package.rsplit(".", 1)[0]
        else:
            caller_package = None

        pkg_module = importlib.import_module(package, caller_package)

        for _, module_name, _ in pkgutil.iter_modules(pkg_module.__path__):
            if module_name in ["registry", "assessment"]:
                continue
            importlib.import_module(f"{pkg_module.__name__}.{module_name}")


assessment_registry = AssessmentRegistry()
