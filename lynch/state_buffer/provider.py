from abc import ABC, abstractmethod
from typing import Optional
import socket

class DataProvider(ABC):
    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port
        self.socket: Optional[socket.socket] = None

    @abstractmethod
    def connect(self):
        pass

    @abstractmethod
    def step(self):
        pass

    @abstractmethod
    def close(self):
        pass
