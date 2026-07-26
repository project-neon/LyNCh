from ..registry import assessment_registry
from typing import Dict, Optional

@assessment_registry.register("BallOutOfBounds")
class BallOutOfBounds:
    def __init__(self, config: Optional[Dict] = None):
        cfg = config or {}
        self.field_half_x = cfg.get("field_half_x", 4.5)
        self.field_half_y = cfg.get("field_half_y", 3.0)

    def is_triggered(self, cur_state, history) -> bool:
        ball = cur_state.ball
        if ball is None:
            return False
        x = ball.x
        y = ball.y

        return not (
            -self.field_half_x <= x <= self.field_half_x and
            -self.field_half_y <= y <= self.field_half_y
        )

    def get_rewards(self) -> float:
        return -1.0
