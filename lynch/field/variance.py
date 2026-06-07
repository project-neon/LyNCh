from abc import ABC, abstractmethod
from typing import Dict, Optional
from copy import deepcopy

class BaseVariance(ABC):
    @abstractmethod
    def apply(self, baseline: Dict, noise: Optional[Dict]) -> Dict:
        raise NotImplementedError


class NoVariance(BaseVariance):
    def apply(self, baseline: Dict, noise: Optional[Dict] = None) -> Dict:
        return deepcopy(baseline)
