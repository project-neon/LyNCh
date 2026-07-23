import socket
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class TCPConnector:
    def __init__(self, host, port, as_server=False):
        self.host = host
        self.port = port
        self.as_server = as_server
        self.socket: Optional[socket.socket] = None

    def connect(self):
        if self.as_server:
            # Server mode: Bind, listen, and accept
            server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server_socket.bind((self.host, self.port))
            server_socket.listen(1)
            logger.info(f"TCPConnector listening on {self.host}:{self.port}...")
            self.socket, addr = server_socket.accept()
            logger.info(f"Accepted connection from {addr}. Socket state: {self.socket}")
            # Diagnostic: Try sending a small greeting
            try:
                self.socket.sendall(b"HELLO\n")
            except Exception as e:
                logger.error(f"Failed to send initial greeting: {e}")
            server_socket.close()
            logger.info(f"TCP connection accepted from {addr}")
        else:
            # Client mode: Connect
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.socket.connect((self.host, self.port))
            logger.info(f"TCP connection established with {self.host}:{self.port}")

        self.socket.settimeout(0.1)

    def send(self, data):
        if not self.socket:
            raise RuntimeError("Socket not connected. Call connect() first.")
        self.socket.sendall(data)

    def receive(self) -> Optional[bytes]:
        if not self.socket:
            raise RuntimeError("Socket not connected. Call connect() first.")
        try:
            data = self.socket.recv(4096)
            if data == b'':
                logger.debug("Peer closed the TCP connection (received b'').")
                raise ConnectionError("TCP Connection lost.")
            return data
        except socket.timeout:
            return None

    def close(self):
        if self.socket:
            self.socket.close()
            self.socket = None
