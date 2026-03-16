import time
import json
import struct
import socket
import threading
from collections import deque
from google.protobuf.json_format import MessageToJson
from protocols.gc.ssl_vision_wrapper_tracked_pb2 import TrackerWrapperPacket


class LogLady(threading.Thread):
    def __init__(self) -> None:
        super().__init__(daemon=True)
        self.queue = deque()
        self.host = "224.5.23.2"
        self.vision_port = 10010
        self.socket = None
        self.running = threading.Event()

    def stop(self) -> None:
        self.socket.close()
        self.running.clear()

    def run(self) -> None:
        self.socket = self._create_socket()
        self._wait_to_connect()
        self.running.set()
        while self.running.is_set():
            state = self._poll_autoref()
            if state:
                self.queue.append(state)
            time.sleep(1e-3)

    def pull(self):
        try:
            return self.queue.popleft()
        except IndexError:
            return None

    def _poll_autoref(self):
        new_state = TrackerWrapperPacket()
        data = self.socket.recv(2048)
        new_state.ParseFromString(data)
        return json.loads(MessageToJson(new_state))

    def _wait_to_connect(self):
        self.socket.recv(1024)

    def _create_socket(self):
        sock = socket.socket(
            socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP
        )

        sock.setsockopt(
            socket.SOL_SOCKET, socket.SO_REUSEADDR, 1
        )

        sock.bind((self.host, self.vision_port))

        mreq = struct.pack(
            "4sl", socket.inet_aton(self.host), socket.INADDR_ANY
        )

        sock.setsockopt(
            socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq
        )

        return sock
