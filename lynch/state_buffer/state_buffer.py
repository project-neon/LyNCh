from threading import Thread, Event
from collections import deque
from enum import Enum, auto
from .provider import DataProvider
import logging

logger = logging.getLogger(__name__)


class DataMode(Enum):
    DIRECT = auto()
    NEONFC = auto()


class StateBuffer(Thread):
    def __init__(self, provider: DataProvider):
        super().__init__(daemon=True)
        self.provider = provider
        self.stop_event = Event()
        self._buffer = deque()

    def run(self):
        try:
            self.provider.connect()
            while not self.stop_event.is_set():
                data = self.provider.step()
                if data:
                    self._buffer.append(data)

        except Exception as e:
            logger.error(e)

        finally:
            self.provider.close()

    def pull(self):
        if not self._buffer:
            return None
        return self._buffer.popleft()

    def stop(self):
        self.stop_event.set()
        self.join(timeout=1.0)
