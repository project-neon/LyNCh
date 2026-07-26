import logging
from typing import Dict, Optional, List
from lynch.state.schema import FrameState
from ..registry import assessment_registry

logger = logging.getLogger(__name__)

@assessment_registry.register("BallStopped")
class BallStopped:
    def __init__(self, config: Optional[Dict] = None):
        cfg = config or {}
        self.speed_threshold = cfg.get("speed_threshold", 0.05)
        self.frame_to_wait = cfg.get("frame_to_wait", 10)

    def is_triggered(self, cur_state: FrameState, history: List) -> bool:
        if len(history) < self.frame_to_wait - 1:
            return False

        # Get the states from the last transitions
        # Need self.frame_to_wait total frames (recent_frames + current)
        recent_states = [t.state for t in history[-(self.frame_to_wait - 1):]]
        recent_states.append(cur_state)
        
        return all(self._get_speed(s) < self.speed_threshold for s in recent_states)

    def _get_speed(self, state: FrameState) -> float:
        ball = state.ball
        if not ball:
            return float('inf')
        return (ball.vx**2 + ball.vy**2)**0.5

    def get_rewards(self) -> float:
        return -1.0
