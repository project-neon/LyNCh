from abc import ABC, abstractmethod
from typing import Dict, Optional
from copy import deepcopy


class BaseVariance(ABC):
    """Abstract interface for all variance strategies."""
    @abstractmethod
    def apply(self, baseline: Dict, noise: Optional[Dict]) -> Dict:
        raise NotImplementedError


class NoVariance(BaseVariance):
    """Returns a deep copy of the baseline without any modifications."""
    def apply(self, baseline: Dict, noise: Optional[Dict] = None) -> Dict:
        return deepcopy(baseline)
