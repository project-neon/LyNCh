import socket
import logging
import threading
from typing import Optional

logger = logging.getLogger(__name__)

ACCEPT_POLL_SECONDS = 0.5


class TCPConnector:
    def __init__(self, host, port, as_server=False):
        self.host = host
        self.port = port
        self.as_server = as_server
        self.socket: Optional[socket.socket] = None
        self._server_socket: Optional[socket.socket] = None

    def connect(self):
        if self.as_server:
            self._ensure_listener()
            logger.info(f"TCPConnector listening on {self.host}:{self.port}...")
            self.accept_once()
        else:
            # Client mode: Connect
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.socket.connect((self.host, self.port))
            logger.info(f"TCP connection established with {self.host}:{self.port}")

        self.socket.settimeout(0.1)

    def _ensure_listener(self):
        """Bind and listen once, and keep the listener open.

        The listener used to be closed right after the first accept, so a
        reconnecting peer had nothing to connect to.
        """
        if self._server_socket is not None:
            return
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind((self.host, self.port))
        server_socket.listen(5)
        server_socket.settimeout(ACCEPT_POLL_SECONDS)
        self._server_socket = server_socket

    def accept_once(self, stop_event: Optional[threading.Event] = None) -> bool:
        """Waits for one peer. Returns False if stopped while waiting.

        No greeting is sent on accept: the peer expects a stream of
        newline-delimited JSON and would treat stray bytes as a frame.
        """
        self._ensure_listener()
        while True:
            if stop_event is not None and stop_event.is_set():
                return False
            try:
                conn, addr = self._server_socket.accept()
            except socket.timeout:
                continue
            except OSError:
                return False
            self.socket = conn
            self.socket.settimeout(0.1)
            logger.info(f"TCP connection accepted from {addr}")
            return True

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
        """Closes the peer connection, leaving the listener open."""
        if self.socket:
            self.socket.close()
            self.socket = None

    def shutdown(self):
        """Closes the peer connection and the listener."""
        self.close()
        if self._server_socket:
            # shutdown() first: on Linux it wakes a thread parked in
            # accept(), whereas close() alone can leave it waiting out the
            # poll timeout.
            try:
                self._server_socket.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            self._server_socket.close()
            self._server_socket = None
