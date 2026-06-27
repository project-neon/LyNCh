from typing import Dict, Optional
from ..registry import assessment_registry


@assessment_registry.register("TimeLimit")
class TimeLimit:
    def __init__(self, config: Optional[Dict] = None):
        cfg = config or {}
        self.limit = cfg.get("limit", 1000)
        self.counter = 0

    def is_triggered(self, cur_state, history) -> bool:
        self.counter += 1
        if self.counter > self.limit:
            self.counter = 0
            return True
        return False

    def get_rewards(self) -> Dict[str, float]:
        return {
            "striker": -1.0,
            "keeper": 1.0,
        }
