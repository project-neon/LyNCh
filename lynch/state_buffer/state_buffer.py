from multiprocessing import Process, Event, Pipe
from enum import Enum, auto
from .provider import DataProvider
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)


class DataMode(Enum):
    DIRECT = auto()
    NEONFC = auto()


class StateBuffer(Process):
    def __init__(self, provider: DataProvider):
        super().__init__(daemon=True)
        self.provider = provider
        self.pipe_tail, self.pipe_head = Pipe(duplex=False)
        self.stop_event = Event()
        self._last_packet: Optional[Dict[str, Any]] = None

    def run(self):
        try:
            self.provider.connect()
            while not self.stop_event.is_set():

                data = self.provider.step()
                if data:
                    self.pipe_head.send(data)
        except Exception as e:
            logger.error(e)
        finally:
            self.provider.close()
            self.pipe_head.close()

    def pull(self):
        while self.pipe_tail.poll():
            self._last_packet = self.pipe_tail.recv()

        return self._last_packet

    def stop(self):
        self.stop_event.set()
        self.join(timeout=1.0)

        if self.is_alive():
            self.terminate()

        self.pipe_head.close()
