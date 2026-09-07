import numpy as np
from typing import Dict, Optional, List, Union
from lynch.state.schema import FrameState
from ..registry import assessment_registry

@assessment_registry.register("DistanceToCenter")
class DistanceToCenter:
    """Computes reward for target robots based on their elliptical normalized distance to the center (0,0).
    Does not trigger termination on its own; provides reward upon episode termination.
    """
    def __init__(self, config: Optional[Dict] = None):
        cfg = config or {}
        self.x_max = cfg.get("x_max", 4.5)
        self.y_max = cfg.get("y_max", 3.0)
        self.team = cfg.get("team", "blue")
        self.robot_ids = cfg.get("robot_ids", [0, 1])

    def is_triggered(self, cur_state: FrameState, history: List) -> bool:
        # DistanceToCenter does not trigger termination; TimeLimit handles termination.
        return False

    def get_rewards(self) -> float:
        return 0.0

    def get_terminal_reward(self, cur_state: FrameState) -> Dict[int, float]:
        rewards = {}
        robots = cur_state.robots.blue if self.team == "blue" else cur_state.robots.yellow

        for robot in robots:
            if robot.id in self.robot_ids:
                norm_dist = np.sqrt((robot.x / self.x_max)**2 + (robot.y / self.y_max)**2)
                norm_dist = np.clip(norm_dist, 0.0, 1.0)
                rewards[robot.id] = float(1.0 - 2.0 * norm_dist)
        return rewards
