from typing import Dict, Optional
from ..registry import assessment_registry

@assessment_registry.register("GoalScored")
class GoalScored:
    def __init__(self, config: Optional[Dict] = None):
        cfg = config or {}
        self.goal_x = cfg.get("goal_x", 4.5)
        self.goal_y = cfg.get("goal_y", 0.5)
        self.tolerance = cfg.get("tolerance", 0.03)

    def is_triggered(self, cur_state, history) -> bool:
        ball = cur_state.get("ball")
        if ball is None:
            return False
        x = ball.get("x")
        y = ball.get("y")
        if x is None or y is None:
            return False
        return (
            x >= self.goal_x - self.tolerance and
            -self.goal_y <= y <= self.goal_y
        )

    def get_rewards(self) -> Dict[str, float]:
        return {
            "striker": 1.0,
            "keeper": -1.0,
        }
