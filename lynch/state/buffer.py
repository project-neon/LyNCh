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
        self._input_buffer = b""

    def start(self):
        self.stop_event.clear()
        super().start()

    def run(self):
        try:
            self.connector.connect()
            
            while not self.stop_event.is_set():
                try:
                    # Added a timeout to the connector receive if possible, 
                    # but relying on connector.receive blocking seems to be the current design.
                    # As a quick fix for thread stop responsiveness, we assume connector.receive
                    # might need to be non-blocking or interrupted.
                    # For now, let's keep it as is, but ensure stop_event is checked.
                    raw_data = self.connector.receive()
                    if raw_data:
                        if self.parser.__name__ == 'JSONParser':
                            self._input_buffer += raw_data
                            while b"\n" in self._input_buffer:
                                line, self._input_buffer = self._input_buffer.split(b"\n", 1)
                                if line:
                                    frame = self.parser.parse_from_bytes(line)
                                    if frame:
                                        self._buffer.append(frame)
                        else:
                            # Direct processing for Protobuf
                            frame = self.parser.parse_from_bytes(raw_data)
                            if frame:
                                self._buffer.append(frame)
                                
                except (ConnectionError, BrokenPipeError, RuntimeError, OSError) as e:
                    if not self.stop_event.is_set():
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

    def clear(self):
        """Clear all buffered frames."""
        self._buffer.clear()

    def stop(self):
        self.stop_event.set()
        self.join(timeout=1.0)
