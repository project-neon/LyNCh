from threading import Thread, Event, Lock
from collections import deque
import logging

logger = logging.getLogger(__name__)


class Buffer(Thread):
    def __init__(self, connector, parser):
        super().__init__(daemon=True)
        self.connector = connector
        self.parser = parser
        self.stop_event = Event()
        self._buffer = deque()
        self._input_buffer = b""
        self._lock = Lock()

    def start(self):
        self.stop_event.clear()
        super().start()

    def run(self):
        """Accept -> read -> reconnect, until stopped.

        A dropped peer is a normal event (the playing service can be
        restarted independently), so it must not end the thread.
        """
        try:
            while not self.stop_event.is_set():
                try:
                    if getattr(self.connector, "as_server", False):
                        # Server mode: wait for a peer, and keep waiting
                        # for the next one after it goes away.
                        if not self.connector.accept_once(self.stop_event):
                            break
                    else:
                        # Client mode (and multicast): connect once and
                        # just read.
                        self.connector.connect()

                    while not self.stop_event.is_set():
                        try:
                            raw_data = self.connector.receive()
                            if raw_data:
                                self._ingest(raw_data)
                        except (ConnectionError, BrokenPipeError, RuntimeError, OSError) as e:
                            if not self.stop_event.is_set():
                                logger.warning(f"Data link lost: {e}; waiting for a new peer")
                            break

                    self._reset_input_buffer()
                except Exception as e:  # noqa: BLE001 -- the thread must survive
                    logger.error(f"Unexpected error in buffer thread: {e}")
                    self._reset_input_buffer()
        finally:
            self.connector.close()

    def _ingest(self, raw_data: bytes):
        """Appends parsed frames to the queue. A malformed line is
        skipped, not fatal."""
        try:
            if self.parser.__name__ == 'JSONParser':
                self._input_buffer += raw_data
                while b"\n" in self._input_buffer:
                    line, self._input_buffer = self._input_buffer.split(b"\n", 1)
                    if line:
                        frame = self.parser.parse_from_bytes(line)
                        if frame:
                            self._append(frame)
            else:
                # Direct processing for Protobuf: one datagram-sized
                # message per recv.
                frame = self.parser.parse_from_bytes(raw_data)
                if frame:
                    self._append(frame)
        except Exception as e:  # noqa: BLE001
            logger.warning(f"Skipping unparseable data: {e}")

    def _reset_input_buffer(self):
        self._input_buffer = b""

    def _append(self, frame):
        with self._lock:
            self._buffer.append(frame)

    def pull(self):
        with self._lock:
            if not self._buffer:
                return None
            return self._buffer.popleft()

    def clear(self):
        """Clear all buffered frames."""
        with self._lock:
            self._buffer.clear()

    def stop(self):
        self.stop_event.set()
        # Unblock a thread parked in accept()/recv().
        shutdown = getattr(self.connector, "shutdown", None)
        if shutdown is not None:
            try:
                shutdown()
            except OSError:
                pass
        self.join(timeout=1.0)
