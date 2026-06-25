from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from random import Random
from copy import deepcopy


class BaseVariance(ABC):
    def __init__(self, seed: Optional[int] = None):
        self.__seed = seed

    """Abstract interface for all variance strategies."""
    @abstractmethod
    def apply(self, baseline: Dict, noise: Optional[Dict]) -> Dict:
        raise NotImplementedError


class NoVariance(BaseVariance):
    """Returns a deep copy of the baseline without any modifications."""
    def apply(self, baseline: Dict, noise: Optional[Dict] = None) -> Dict:
        return deepcopy(baseline)


class RandomVariance(BaseVariance, ABC):
    """
    Schema-driven additive noise injection.
    Applies noise to ball (x, y) and robots (x, y, theta) matching by team and ID.
    """
    def __init__(self, seed=None):
        super().__init__(seed)
        self._rng = Random(seed)

    @abstractmethod
    def _sample(self, args):
        """Sample distribution-specific noise value."""
        raise NotImplementedError

    def apply(self, baseline: Dict, noise: Optional[Dict]) -> Dict:
        result = deepcopy(baseline)

        if not noise:
            return result

        # Ball noise: noise["ball"]["x"|"y"]
        if "ball" in noise and "ball" in result:
            ball_noise = noise["ball"]
            for field in ("x", "y"):
                if field in ball_noise:
                    result["ball"][field] += self._sample(ball_noise[field])

        # Robot noise: noise["robots"]["yellow"|"blue"]["id"]["x"|"y"|"theta"]
        if "robots" in noise and "robots" in result:
            robots_noise = noise["robots"]
            for team in ("yellow", "blue"):
                if team not in robots_noise:
                    continue
                team_noise = robots_noise[team]
                for robot in result["robots"][team]:
                    if not isinstance(robot, dict) or "id" not in robot:
                        continue
                    rid = str(robot["id"])
                    if rid in team_noise:
                        for field in ("x", "y", "theta"):
                            if field in team_noise[rid]:
                                robot[field] += self._sample(team_noise[rid][field])

        return result


class UniformRandomVariance(RandomVariance):
    """Samples noise from a continuous uniform distribution [min, max]."""
    def __init__(self, seed=None):
        super().__init__(seed)

    def _sample(self, args):
        return self._rng.uniform(*args)


class GaussianRandomVariance(RandomVariance):
    """Samples noise from a normal distribution centered at 0.0."""
    def __init__(self, seed=None):
        super().__init__(seed)

    def _sample(self, args):
        return self._rng.gauss(0, args)
