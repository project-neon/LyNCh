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
        ball = cur_state.ball
        if ball is None:
            return False
        x = ball.x
        y = ball.y
        return (
            x >= self.goal_x - self.tolerance and
            -self.goal_y <= y <= self.goal_y
        )

    def get_rewards(self) -> float:
        return 1.0
