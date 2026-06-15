from typing import Dict
from .registry import assessment_registry


@assessment_registry.register("time_limit")
class TimeLimit:
    def __init__(self):
        self.limit = 1000
        self.counter = 0

    def is_triggered(self, cur_state, history) -> bool:
        self.counter += 1
        return self.counter > self.limit

    def get_rewards(self) -> Dict[str, float]:
        return {
            "striker": -1.0,
            "keeper": 1.0,
        }