from typing import Optional
import struct
import socket
import logging

logger = logging.getLogger(__name__)


class MulticastConnector:
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.socket: Optional[socket.socket] = None

    def connect(self):
        self.socket = socket.socket(
            socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP
        )
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.bind((self.host, self.port))

        self.socket.settimeout(0.1)

        mreq = struct.pack("4sl", socket.inet_aton(self.host), socket.INADDR_ANY)
        self.socket.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)

        logger.info(f"UDP connection established with {self.host}:{self.port}")

    def receive(self):
        if not self.socket:
            raise RuntimeError("Provider not connected. Call connect() first.")
        try:
            return self.socket.recv(4096)
        except socket.timeout:
            return None

    def close(self):
        if self.socket:
            self.socket.close()
            self.socket = None
