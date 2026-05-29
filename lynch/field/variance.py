from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from random import Random
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


class RandomVariance(BaseVariance):
    """
    Engine for recursive additive noise.
    Matches list items by 'id' property and protects metadata from perturbations.
    """
    def __init__(self, seed=None):
        self._rng = Random(seed)

    @abstractmethod
    def _calculate_noise(self, args):
        """Sample distribution-specific noise value."""
        raise NotImplementedError

    def _inject_recursive(self, baseline, noise) -> Any:
        """Traverses trees to apply offsets to matching paths."""
        if noise is None:
            return baseline

        if isinstance(baseline, dict):
            if not isinstance(noise, dict):
                return baseline
            for key in baseline.keys():
                if key == "id": # Preserve identity metadata
                    continue
                baseline[key] = self._inject_recursive(baseline[key], noise.get(key))
        elif isinstance(baseline, list):
            if not isinstance(noise, dict):
                return baseline
            for idx, item in enumerate(baseline):
                if isinstance(item, dict) and "id" in item:
                    # Match noise rule by Robot ID string-key
                    item_id = str(item["id"])
                    baseline[idx] = self._inject_recursive(item, noise.get(item_id))
        elif isinstance(baseline, (int, float)):
            # Apply sampled offset to numeric leaf nodes
            baseline += self._calculate_noise(noise)

        return baseline

    def apply(self, baseline: Dict, noise: Dict) -> Dict:
        return self._inject_recursive(deepcopy(baseline), noise)


class UniformRandomVariance(RandomVariance):
    """Samples noise from a continuous uniform distribution [min, max]."""
    def __init__(self, seed=None):
        super().__init__(seed)

    def _calculate_noise(self, args):
        return self._rng.uniform(*args)


class GaussianRandomVariance(RandomVariance):
    """Samples noise from a normal distribution centered at 0.0."""
    def __init__(self, seed=None):
        super().__init__(seed)

    def _calculate_noise(self, args):
        return self._rng.gauss(0, args)
