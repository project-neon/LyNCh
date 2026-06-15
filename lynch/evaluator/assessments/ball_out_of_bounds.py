from ..registry import assessment_registry
from typing import Dict

@assessment_registry.register("ball_out_of_bounds")
class BallOutOfBounds:
    def __init__(self):
        self.field_half_x = 4.5
        self.field_half_y = 3.0

    def is_triggered(self, cur_state, history) -> bool:
        ball = cur_state.get("ball")
        x = ball.get("x")
        y = ball.get("y")

        return not (
            -self.field_half_x <= x <= self.field_half_x and
            -self.field_half_y <= y <= self.field_half_y
        )

    def get_rewards(self) -> Dict[str, float]:
        return {
            "striker": -1.0,
            "keeper": 1.0,
        }
