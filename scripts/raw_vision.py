import time
import json
import struct
import socket
import logging
from google.protobuf.json_format import MessageToJson
from protocols.vision.ssl_vision_wrapper_pb2 import SSL_WrapperPacket
from lynch.loglady.log import BaseBuffer

logger = logging.getLogger(__name__)

class RawVisionBuffer(BaseBuffer):
    """
    Specialized buffer for raw SSL-Vision data (often port 10020).
    Uses SSL_WrapperPacket instead of TrackerWrapperPacket.
    """

    def _create_socket(self) -> socket.socket:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((self.host, self.port))
        
        # Join multicast group
        mreq = struct.pack("4sl", socket.inet_aton(self.host), socket.INADDR_ANY)
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
        return sock

    def _wait_to_connect(self):
        """Wait for the first packet to ensure stream is alive."""
        if self.socket:
            self.socket.recv(4096)

    def run(self) -> None:
        self.socket = self._create_socket()
        try:
            self._wait_to_connect()
            self.running.set()
            while self.running.is_set():
                try:
                    data = self.socket.recv(4096)
                    packet = SSL_WrapperPacket()
                    packet.ParseFromString(data)
                    
                    # Convert to JSON-serializable dict
                    state = json.loads(MessageToJson(packet))
                    
                    # Normalize to the standard Log format
                    self.queue.append({
                        "state": state,
                        "prev_state": None,
                        "action": None
                    })
                except Exception as e:
                    if self.running.is_set():
                        logger.error(f"Error parsing Raw Vision packet: {e}")
                time.sleep(1e-3)
        finally:
            if self.socket:
                self.socket.close()

if __name__ == "__main__":
    import signal
    import sys

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
    )

    # Standard sim/SSL-Vision setup
    HOST = "224.5.23.2"
    PORT = 10020

    print(f"\n--- Raw Vision Listener Tester ---")
    print(f"Connecting to {HOST}:{PORT}...")
    
    buffer = RawVisionBuffer(host=HOST, port=PORT)
    packet_count = 0

    def signal_handler(sig, frame):
        print("\nStopping Listener...")
        buffer.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    buffer.start()

    try:
        while True:
            data = buffer.pull()
            if data:
                packet_count += 1
                state = data["state"]
                
                # Print the full JSON message for inspection
                print(f"\n--- [Packet {packet_count}] ---")
                print(json.dumps(state, indent=2))
                
            time.sleep(0.01)
    except KeyboardInterrupt:
        pass
    finally:
        buffer.stop()
        print(f"\nTotal packets received: {packet_count}")
