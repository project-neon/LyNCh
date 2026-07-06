from time import time
from typing import Dict, Optional
from ..registry import assessment_registry


@assessment_registry.register("TimeLimit")
class TimeLimit:
    def __init__(self, config: Optional[Dict] = None):
        cfg = config or {}
        self.limit = cfg.get("limit", 18000) # 5h in seconds
        self.start_time = time()

    def is_triggered(self, cur_state, history) -> bool:
        if time() - self.start_time > self.limit:
            self.start_time = time()
            return True
        return False

    def get_rewards(self) -> Dict[str, float]:
        return {
            "striker": -1.0,
            "keeper": 1.0,
        }
