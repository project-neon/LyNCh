import json
import logging
from typing import Dict, List, Optional
from google.protobuf.message import DecodeError
from protocols.vision.ssl_vision_wrapper_tracked_pb2 import TrackerWrapperPacket

logger = logging.getLogger(__name__)

# NeonFC state vector layout: 6 values per robot (x, y, theta, vx, vy, vtheta) + 4 for ball
_BALL_OFFSET = 12  # ball starts after 2 robots * 6 fields
_OFFSET_X = 4.5
_OFFSET_Y = 3.0

# Robot indices in the flat list: (team, id, start_index)
_NEONFC_ROBOTS = [
    ("blue", 0, 0),    # goalkeeper: indices 0-5
    ("blue", 1, 6),    # striker: indices 6-11
]


def _transform_coords(x: float, y: float):
    return x - _OFFSET_X, y - _OFFSET_Y


class JSONParser:
    @staticmethod
    def _parse_state_vector(vector: List[float]) -> Optional[Dict]:
        """Convert a 16-float NeonFC state vector into the canonical state dict."""
        if len(vector) < _BALL_OFFSET + 4:
            logger.error(f"NeonFC state vector too short: {len(vector)} (expected >= {_BALL_OFFSET + 4})")
            return None
        
        ball_x, ball_y = _transform_coords(vector[_BALL_OFFSET], vector[_BALL_OFFSET + 1])
        
        state = {
            "ball": {
                "x": ball_x,
                "y": ball_y,
                "vx": vector[_BALL_OFFSET + 2],
                "vy": vector[_BALL_OFFSET + 3],
            },
            "robots": {"blue": [], "yellow": []},
        }

        for team, rid, start in _NEONFC_ROBOTS:
            rob_x, rob_y = _transform_coords(vector[start], vector[start + 1])
            state["robots"][team].append({
                "id": rid,
                "x": rob_x,
                "y": rob_y,
                "theta": vector[start + 2],
                "vx": vector[start + 3],
                "vy": vector[start + 4],
                "vtheta": vector[start + 5],
            })

        return state

    @classmethod
    def parse_from_bytes(cls, data) -> Optional[Dict]:
        try:
            payload = json.loads(data.decode("utf-8"))

            cur = payload.get("cur_state")
            nxt = payload.get("next_state")

            if not isinstance(cur, list):
                logger.error("NeonFC cur_state is not a list")
                return None

            state = cls._parse_state_vector(cur)
            next_state = cls._parse_state_vector(nxt) if isinstance(nxt, list) else None

            return {
                "state": state,
                "next_state": next_state,
                "actions": payload.get("actions"),
            }
        except (json.JSONDecodeError, UnicodeDecodeError, KeyError, TypeError) as e:
            logger.error(f"Failed to parse NeonFC packet: {e}")
            return None


class ProtobufParser:
    @classmethod
    def parse_from_bytes(cls, data) -> Optional[Dict]:
        try:
            packet = TrackerWrapperPacket()
            packet.ParseFromString(data)

            frame = packet.tracked_frame
            state = cls._extract_state(frame)

            return {
                "state": state,
                "next_state": None,
                "actions": None,
            }
        except (DecodeError, TypeError, AttributeError) as e:
            logger.error(f"Failed to parse SSL Vision packet: {e}")
            return None

    @staticmethod
    def _extract_state(frame) -> Dict:
        """Normalize SSL Vision TrackedFrame into the canonical state dict."""
        state = {
            "ball": None,
            "robots": {"blue": [], "yellow": []},
        }

        if frame.balls:
            ball = frame.balls[0]
            state["ball"] = {
                "x": ball.pos.x,
                "y": ball.pos.y,
                "vx": ball.vel.x if ball.HasField("vel") else 0.0,
                "vy": ball.vel.y if ball.HasField("vel") else 0.0,
            }

        for robot in frame.robots:
            team = "yellow" if robot.robot_id.team == 1 else "blue"
            state["robots"][team].append({
                "id": robot.robot_id.id,
                "x": robot.pos.x,
                "y": robot.pos.y,
                "vx": robot.vel.x if robot.HasField("vel") else 0.0,
                "vy": robot.vel.y if robot.HasField("vel") else 0.0,
                "theta": robot.orientation,
            })

        return state
