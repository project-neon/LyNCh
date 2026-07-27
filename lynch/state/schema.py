from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any
import json

_OFFSET_X = 4.5
_OFFSET_Y = 3.0

@dataclass
class RobotState:
    id: int
    x: float
    y: float
    theta: float
    vx: float
    vy: float
    vtheta: Optional[float] = None

@dataclass
class BallState:
    x: float
    y: float
    vx: float
    vy: float

@dataclass
class FrameState:
    ball: Optional[BallState]
    robots: Dict[str, List[RobotState]] = field(default_factory=lambda: {"blue": [], "yellow": []})

    def to_flat_vector(self) -> List[float]:
        """Convert FrameState into a flat 16-float NeonFC vector."""
        # 16-float NeonFC state vector: 6 per robot (x, y, theta, vx, vy, vtheta) + 4 for ball
        vector = [0.0] * 16

        # Ball
        if self.ball:
            vector[12] = self.ball.x + _OFFSET_X
            vector[13] = self.ball.y + _OFFSET_Y
            vector[14] = self.ball.vx
            vector[15] = self.ball.vy

        # Robots (indices 0-5 blue:0, 6-11 blue:1)
        # Assuming fixed order based on parser
        for team, rid, start in [("blue", 0, 0), ("blue", 1, 6)]:
            robot = next((r for r in self.robots.get(team, []) if r.id == rid), None)
            if robot:
                vector[start] = robot.x + _OFFSET_X
                vector[start + 1] = robot.y + _OFFSET_Y
                vector[start + 2] = robot.theta
                vector[start + 3] = robot.vx
                vector[start + 4] = robot.vy
                vector[start + 5] = robot.vtheta or 0.0
        
        return vector

@dataclass
class Transition:
    state: FrameState
    next_state: Optional[FrameState]
    actions: Optional[Dict[str, Any]]
    rewards: float = 0.0
    done: bool = False

    def to_recorder_json(self) -> str:
        """Serializes the transition to the requested JSON format."""
        data = {
            "cur_state": self.state.to_flat_vector(),
            "next_state": self.next_state.to_flat_vector() if self.next_state else [0.0]*16,
            "actions": self.actions,
            "rewards": self.rewards,
            "done": self.done
        }
        return json.dumps(data)
