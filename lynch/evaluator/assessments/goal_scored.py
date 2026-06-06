from .assessment import Assessment
from .registry import registry

@registry.register("goal_scored")
class GoalScored(Assessment):
    def __init__(self):
        self.goal_x = 4.5
        self.goal_y = 0.5
        self.tolerance = 0.03

    def is_triggered(self, cur_state, history) -> bool:
        ball = cur_state.get("ball")
        return (
            ball is not None and
            ball.get("x") >= self.goal_x - self.tolerance and
            -self.goal_y <= ball.get("y") <= self.goal_y
        )
