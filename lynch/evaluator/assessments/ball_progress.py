import math
from typing import Dict, Optional

from ..registry import assessment_registry


@assessment_registry.register("BallProgress")
class BallProgress:
    """Potential-based shaping: reward closing the distance to the ball.

    A pure shaping provider: it never terminates the episode and never
    contributes a terminal reward. It only answers `shape()`, which the
    registry calls with consecutive frames. With the default weight the
    full ~1.5m approach sums to ~0.75, well under the +1.0 goal, so
    scoring remains the only optimal ending.
    """

    def __init__(self, config: Optional[Dict] = None):
        cfg = config or {}
        self.robot_id = cfg.get("robot_id", 1)
        self.team = cfg.get("team", "blue")
        self.weight = cfg.get("weight", 0.5)

    def is_triggered(self, cur_state, history) -> bool:
        return False

    def get_rewards(self) -> float:
        # Only reachable if is_triggered ever returns True; keep it inert.
        return 0.0

    def shape(self, prev_state, cur_state) -> Dict[int, float]:
        prev_d = self._distance_to_ball(prev_state)
        cur_d = self._distance_to_ball(cur_state)
        if prev_d is None or cur_d is None:
            return {}
        return {self.robot_id: self.weight * (prev_d - cur_d)}

    def _distance_to_ball(self, state) -> Optional[float]:
        ball = getattr(state, "ball", None)
        if ball is None:
            return None
        robot = next(
            (r for r in state.robots.get(self.team, []) if r.id == self.robot_id),
            None,
        )
        if robot is None:
            return None
        return math.hypot(robot.x - ball.x, robot.y - ball.y)
