from abc import ABC, abstractmethod
from typing import Dict
from copy import deepcopy

class BaseVariance(ABC):
    @abstractmethod
    def apply(self, baseline: Dict, noise: Dict) -> Dict:
        raise NotImplementedError


class DeterministicVariance(BaseVariance):
    def apply(self, baseline: Dict, noise: Dict=None) -> Dict:
        return deepcopy(baseline)
