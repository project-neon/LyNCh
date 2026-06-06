from typing import Dict
from .assessment import Assessment
from .registry import registry

@registry.register("ball_stopped")
class BallStopped(Assessment):
    def __init__(self):
        self.speed_threshold = 0.05
        self.frame_to_wait = 10

    def is_triggered(self, cur_state, history) -> bool:
        if len(history) < self.frame_to_wait:
            return False

        recent_frames = history[-self.frame_to_wait:]
        return all(self._get_speed(f) < self.speed_threshold for f in recent_frames)

    def _get_speed(self, state: Dict) -> float:
        ball = state.get("ball")
        vx = ball.get("vx")
        vy = ball.get("vy")
        return (vx**2 + vy**2)**0.5
