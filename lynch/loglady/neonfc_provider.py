import json
import socket
import logging
from typing import Dict, Any, Optional
from .provider import DataProvider

logger = logging.getLogger(__name__)

class NeonFCProvider(DataProvider):
    def __init__(self, host: str, port: int):
        super().__init__(host, port)

    def connect(self):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.bind((self.host, self.port))
        self.socket.settimeout(0.1)
        
        logger.info(f"NeonFCProvider connected to {self.host}:{self.port}")

    def step(self) -> Optional[Dict[str, Any]]:
        if not self.socket:
            raise RuntimeError("Provider not connected. Call connect() first.")

        try:
            data = self.socket.recv(4096)
        except socket.timeout:
            return None

        payload = json.loads(data.decode("utf-8"))
        
        return {
            "state": payload.get("cur_state"),
            "prev_state": payload.get("prev_state"),
            "action": payload.get("action"),
        }

    def close(self):
        if self.socket:
            self.socket.close()
            self.socket = None
