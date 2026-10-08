from time import monotonic
from typing import Dict, Optional
from ..registry import assessment_registry


@assessment_registry.register("TimeLimit")
class TimeLimit:
    # A timeout says nothing about who won, so a shaped reward from a
    # co-loaded reward provider is appropriate here (and not on a goal).
    allows_terminal_reward_override = True

    def __init__(self, config: Optional[Dict] = None):
        cfg = config or {}
        self.limit = cfg.get("limit", 18000) # 5h in seconds
        self.start_time: Optional[float] = None

    def is_triggered(self, cur_state, history) -> bool:
        current_time = monotonic()
        if self.start_time is None:
            self.start_time = current_time
            return False

        if current_time - self.start_time > self.limit:
            self.start_time = current_time
            return True
        return False

    def get_rewards(self) -> float:
        return -1.0
