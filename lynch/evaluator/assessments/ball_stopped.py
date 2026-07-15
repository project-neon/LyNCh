import logging
from typing import Dict, Optional
from ..registry import assessment_registry

logger = logging.getLogger(__name__)

@assessment_registry.register("BallStopped")
class BallStopped:
    def __init__(self, config: Optional[Dict] = None):
        cfg = config or {}
        self.speed_threshold = cfg.get("speed_threshold", 0.05)
        self.frame_to_wait = cfg.get("frame_to_wait", 10)

    def is_triggered(self, cur_state, history) -> bool:
        if len(history) < self.frame_to_wait:
            return False

        recent_frames = history[-self.frame_to_wait+1:]
        recent_frames.append({"state": cur_state})
        return all(self._get_speed(f['state']) < self.speed_threshold for f in recent_frames)

    def _get_speed(self, state: Dict) -> float:
        ball = state.get("ball")
        if not ball:
            return float('inf')
        vx = ball.get("vx", 0.0) or 0.0
        vy = ball.get("vy", 0.0) or 0.0
        return (vx**2 + vy**2)**0.5

    def get_rewards(self) -> Dict[str, float]:
        return {
            "striker": -1.0,
            "keeper": 1.0,
        }
