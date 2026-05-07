import time
import json
import struct
import socket
import logging
import threading
from enum import Enum, auto
from collections import deque
from typing import Any, Dict, Optional
from google.protobuf.json_format import MessageToJson
from protocols.gc.ssl_vision_wrapper_tracked_pb2 import TrackerWrapperPacket

logger = logging.getLogger(__name__)


class LogMode(Enum):
    DIRECT = auto()
    NEONFC = auto()


class BaseBuffer(threading.Thread):
    def __init__(self, host: str, port: int) -> None:
        super().__init__(daemon=True)
        self.queue: deque = deque(maxlen=1)
        self.host = host
        self.port = port
        self.socket: Optional[socket.socket] = None
        self.running = threading.Event()

    def stop(self) -> None:
        self.running.clear()
        if self.socket:
            self.socket.close()
        if self.is_alive():
            self.join(timeout=1.0)

    def pull(self) -> Optional[Dict[str, Any]]:
        if not self.queue:
            return None
        return self.queue.popleft()

    def _create_socket(self) -> socket.socket:
        raise NotImplementedError

    def run(self) -> None:
        raise NotImplementedError


class AutoRefBuffer(BaseBuffer):
    def _create_socket(self) -> socket.socket:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((self.host, self.port))
        mreq = struct.pack("4sl", socket.inet_aton(self.host), socket.INADDR_ANY)
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
        return sock

    def _wait_to_connect(self):
        if self.socket:
            self.socket.recv(1024)

    def run(self) -> None:
        self.socket = self._create_socket()
        self._wait_to_connect()
        self.running.set()
        while self.running.is_set():
            try:
                data = self.socket.recv(2048)
                packet = TrackerWrapperPacket()
                packet.ParseFromString(data)
                state = json.loads(MessageToJson(packet))
                self.queue.append({"state": state, "prev_state": None, "action": None})
            except Exception as e:
                if self.running.is_set():
                    logger.error(f"Error polling AutoRef: {e}")
            time.sleep(1e-3)


class NeonFCBuffer(BaseBuffer):
    def _create_socket(self) -> socket.socket:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((self.host, self.port))
        return sock

    def run(self) -> None:
        self.socket = self._create_socket()
        self.running.set()
        while self.running.is_set():
            try:
                data = self.socket.recv(4096)
                payload = json.loads(data.decode("utf-8"))
                self.queue.append(
                    {
                        "state": payload.get("cur_state"),
                        "prev_state": payload.get("prev_state"),
                        "action": payload.get("action"),
                    }
                )
            except Exception as e:
                if self.running.is_set():
                    logger.error(f"Error receiving NeonFC tuple: {e}")
            time.sleep(1e-3)


class Log:
    def __init__(
        self,
        mode: LogMode = LogMode.DIRECT,
        host: Optional[str] = None,
        port: Optional[int] = None,
    ) -> None:
        self.mode = mode
        if mode == LogMode.DIRECT:
            host = host or "224.5.23.2"
            port = port or 10010
            self._buffer = AutoRefBuffer(host, port)
        elif mode == LogMode.NEONFC:
            host = host or "127.0.0.1"
            port = port or 10011
            self._buffer = NeonFCBuffer(host, port)
        else:
            raise ValueError(f"Invalid BufferMode: {mode}")

    def start(self) -> None:
        self._buffer.start()

    def stop(self) -> None:
        self._buffer.stop()

    def pull(self) -> Optional[Dict[str, Any]]:
        return self._buffer.pull()

    @property
    def running(self) -> threading.Event:
        return self._buffer.running

    @property
    def socket(self) -> Optional[socket.socket]:
        return self._buffer.socket

    @property
    def queue(self) -> deque:
        return self._buffer.queue


if __name__ == "__main__":
    import signal
    import sys

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
    )

    # Example: Choose mode from CLI or default to DIRECT
    mode = LogMode.DIRECT
    if len(sys.argv) > 1 and sys.argv[1].lower() == "neonfc":
        mode = LogMode.NEONFC

    loglady = Log(mode=mode)
    packet_count = 0

    def signal_handler(sig, frame):
        print(f"\nStopping LogLady ({mode.name} mode)...")
        loglady.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)

    print(f"LogLady - Mode: {mode.name}")
    print("=" * 40)
    print(f"Listening on {loglady._buffer.host}:{loglady._buffer.port}")
    print("Press Ctrl+C to stop\n")

    loglady.start()

    try:
        while True:
            data = loglady.pull()
            if data:
                packet_count += 1
                state = data["state"]

                if mode == LogMode.DIRECT:
                    frame = state.get("trackedFrame", state.get("tracked_frame", {}))
                    frame_number = frame.get(
                        "frameNumber", frame.get("frame_number", 0)
                    )

                    print(
                        f"[{packet_count}] Frame: {frame_number} | {frame}"
                    )

                else:
                    action = data.get("action")
                    print(f"[{packet_count}] Action: {action}")

            time.sleep(0.01)
    except KeyboardInterrupt:
        pass
    finally:
        loglady.stop()
        print(f"\n\nTotal packets received: {packet_count}")
