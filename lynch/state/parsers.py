import json
import logging
from typing import Dict, Optional
from google.protobuf.json_format import MessageToJson
from protocols.vision.ssl_vision_wrapper_tracked_pb2 import TrackerWrapperPacket

logger = logging.getLogger(__name__)

class JSONParser:
    @classmethod
    def parse_from_bytes(cls, data) -> Optional[Dict]:
        try:
            payload = json.loads(data.decode("utf-8"))

            return {
                "state": payload.get("cur_state"),
                "prev_state": payload.get("prev_state"),
                "action": payload.get("action"),
            }
        except Exception as e:
            logger.error(f"Failed to parse packet: {e}")
            return None


class ProtobufParser:
    @classmethod
    def parse_from_bytes(cls, data) -> Optional[Dict]:
        try:
            packet = TrackerWrapperPacket()
            packet.ParseFromString(data)

            state = json.loads(MessageToJson(packet))
            return {"state": state, "prev_state": None, "action": None}
        except Exception as e:
            logger.error(f"Failed to parse packet: {e}")
            return None
