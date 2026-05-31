import json
import socket
import struct
import logging
from typing import Dict, Any, Optional
from .provider import DataProvider
from google.protobuf.json_format import MessageToJson
from protocols.vision.ssl_vision_wrapper_tracked_pb2 import TrackerWrapperPacket

logger = logging.getLogger(__name__)

class AutoRefProvider(DataProvider):
    def __init__(self, host: str, port: int):
        super().__init__(host, port)

    def connect(self):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.bind((self.host, self.port))

        self.socket.settimeout(0.1)

        mreq = struct.pack("4sl", socket.inet_aton(self.host), socket.INADDR_ANY)
        self.socket.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
        
        logger.info(f"AutoRefProvider connected to {self.host}:{self.port}")

    def step(self) -> Optional[Dict[str, Any]]:
        if not self.socket:
            raise RuntimeError("Provider not connected. Call connect() first.")

        try:
            data = self.socket.recv(4096)
        except socket.timeout:
            return None

        packet = TrackerWrapperPacket()
        packet.ParseFromString(data)
        
        state = json.loads(MessageToJson(packet))
        return {
            "state": state,
            "prev_state": None,
            "action": None
        }

    def close(self):
        if self.socket:
            self.socket.close()
            self.socket = None
