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

    def is_triggered(self, cur_state: Union[FrameState, Dict], history: List) -> bool:
        # DistanceToCenter does not trigger termination; TimeLimit handles termination.
        return False

    def get_rewards(self) -> float:
        return 0.0

    def get_terminal_reward(self, cur_state: Union[FrameState, Dict]) -> Dict[int, float]:
        rewards = {}
        if hasattr(cur_state, "robots"):
            robots = cur_state.robots.get(self.team, []) if isinstance(cur_state.robots, dict) else (cur_state.robots.blue if self.team == "blue" else cur_state.robots.yellow)
        elif isinstance(cur_state, dict):
            robots = cur_state.get("robots", {}).get(self.team, [])
        else:
            robots = []

        for robot in robots:
            # Handle both object attributes and dict keys
            r_id = getattr(robot, "id", robot.get("id", 0) if isinstance(robot, dict) else 0)
            if r_id in self.robot_ids:
                rx = getattr(robot, "x", robot.get("x", 0.0) if isinstance(robot, dict) else 0.0)
                ry = getattr(robot, "y", robot.get("y", 0.0) if isinstance(robot, dict) else 0.0)
                norm_dist = np.sqrt((rx / self.x_max)**2 + (ry / self.y_max)**2)
                norm_dist = np.clip(norm_dist, 0.0, 1.0)
                rewards[r_id] = float(1.0 - 2.0 * norm_dist)
        return rewards
