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
        # Terminal reward for the timeout ending. Default keeps the
        # historical -1.0 failure penalty; a scenario can set it to 0.0
        # for goal-only reward semantics (timeout says nothing about
        # who won, so under goal-only it is neutral, not a penalty).
        self.terminal_reward = cfg.get("reward", -1.0)
        self.start_time: Optional[float] = None

    def reset(self) -> None:
        """Called between episodes. Without this the timer carries over
        and the next episode can time out on its very first frame."""
        self.start_time = None

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
        return self.terminal_reward
