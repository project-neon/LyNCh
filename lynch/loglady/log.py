import time
import json
import struct
import socket
import logging
import threading
from collections import deque
from google.protobuf.json_format import MessageToJson
from protocols.gc.ssl_vision_wrapper_tracked_pb2 import TrackerWrapperPacket

logger = logging.getLogger(__name__)


class Log(threading.Thread):
    def __init__(self) -> None:
        super().__init__(daemon=True)
        self.queue = deque(maxlen=1)
        self.host = "224.5.23.2"
        self.vision_port = 10010
        self.socket = None
        self.running = threading.Event()

    def stop(self) -> None:
        self.running.clear()
        if self.socket:
            self.socket.close()
        self.join(timeout=1.0)

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
        if not self.queue:
            return None
        return self.queue.popleft()

    def _wait_to_connect(self):
        self.socket.recv(1024)

    def _create_socket(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((self.host, self.vision_port))
        mreq = struct.pack("4sl", socket.inet_aton(self.host), socket.INADDR_ANY)
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
        return sock

    def _poll_autoref(self):
        try:
            new_state = TrackerWrapperPacket()
            data = self.socket.recv(2048)
            new_state.ParseFromString(data)
            return json.loads(MessageToJson(new_state))
        except Exception as e:
            logger.error(f"Error polling AutoRef: {e}")
            return None


if __name__ == "__main__":
    import signal
    import sys

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
    )

    log = Log()
    packet_count = 0
    last_frame_number = None

    def signal_handler(sig, frame):
        """Handle Ctrl+C gracefully."""
        print("\nStopping log...")
        log.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)

    print("LogLady - SSL Vision Multicast Listener")
    print("=" * 40)
    print(f"Listening on {log.host}:{log.vision_port}")
    print("Press Ctrl+C to stop\n")

    log.start()

    try:
        while True:
            state = log.pull()
            if state:
                packet_count += 1
                uuid = state.get("uuid", "unknown")
                source = state.get("sourceName", state.get("source_name", "unknown"))

                # Get frame number to track new packets
                frame = state.get("trackedFrame", state.get("tracked_frame", {}))
                frame_number = frame.get("frameNumber", frame.get("frame_number", 0))
                timestamp = frame.get("timestamp", 0)

                # Track if this is a new frame
                is_new = frame_number != last_frame_number
                last_frame_number = frame_number

                status = "[NEW]" if is_new else "[SAME]"

                # Get ball data
                balls = frame.get("balls", [])
                ball_info = ""
                if balls:
                    ball = balls[0]
                    pos = ball.get("pos", {})
                    vel = ball.get("vel", {})
                    ball_info = f"Ball: ({pos.get('x', 0):.2f}, {pos.get('y', 0):.2f}) v=({vel.get('x', 0):.2f}, {vel.get('y', 0):.2f})"

                print(f"[{packet_count}] {status} Frame: {frame_number} | {ball_info}")

            time.sleep(0.01)  # Faster polling
    except KeyboardInterrupt:
        pass
    finally:
        log.stop()
        print(f"\n\nTotal packets received: {packet_count}")
