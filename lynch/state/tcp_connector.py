import socket
import threading
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class TCPConnector:
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.socket: Optional[socket.socket] = None
        self._lock = threading.Lock()

    def connect(self):
        with self._lock:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

            self.socket.connect((self.host, self.port))
            self.socket.settimeout(0.1)

            logger.info(f"TCP connection established with {self.host}:{self.port}")

    def send(self, data):
        with self._lock:
            if not self.socket:
                raise RuntimeError("Socket not connected. Call connect() first.")
            self.socket.sendall(data)

    def receive(self) -> Optional[bytes]:
        with self._lock:
            if not self.socket:
                raise RuntimeError("Socket not connected. Call connect() first.")
            try:
                data = self.socket.recv(4096)
                if data == b'':
                    raise ConnectionError("TCP Connection lost.")
                return data
            except socket.timeout:
                return None

    def close(self):
        with self._lock:
            if self.socket:
                self.socket.close()
                self.socket = None
