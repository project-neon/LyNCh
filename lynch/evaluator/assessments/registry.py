import importlib
import pkgutil
import inspect
from typing import Dict, Type, List
from .assessment import Assessment

class AssessmentRegistry:
    def __init__(self):
        self._registry: Dict[str, Type[Assessment]] = {}

    def register(self, name: str):
        def decorator(cls: Type[Assessment]):
            if not issubclass(cls, Assessment):
                raise TypeError(f"'{cls.__name__}' is not a subclass of Assessment")
            self._registry[name] = cls
            return cls
        return decorator

    def get(self, name: str) -> Type[Assessment]:
        if name not in self._registry:
            raise KeyError(f"Assessment '{name}' is not registered")
        return self._registry[name]

    def load(self, names: List[str]) -> List[Assessment]:
        return [self.get(name)() for name in names]

    def autodiscover(self, package: str):
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

registry = AssessmentRegistry()
