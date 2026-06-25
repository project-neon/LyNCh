from threading import Thread, Event
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

    def run(self):
        try:
            self.connector.connect()
            while not self.stop_event.is_set():
                try:
                    raw_data = self.connector.receive()
                    if raw_data:
                        frame = self.parser.parse_from_bytes(raw_data)
                        if frame:
                            self._buffer.append(frame)
                except (ConnectionError, BrokenPipeError, RuntimeError, OSError) as e:
                    logger.error(f"Connection lost: {e}")
                    break
        except Exception as e:
            logger.error(e)
        finally:
            self.connector.close()

    def pull(self):
        if not self._buffer:
            return None
        return self._buffer.popleft()

    def stop(self):
        self.stop_event.set()
        self.join(timeout=1.0)
