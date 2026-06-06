from dataclasses import dataclass
from enum import Enum, auto
from .buffer import Buffer
from .tcp_connector import TCPConnector
from .multicast_connector import MulticastConnector
from .parsers import JSONParser, ProtobufParser
from typing import Optional


class DataMode(Enum):
    DIRECT = auto()
    NEONFC = auto()


@dataclass
class Session:
    buffer: Buffer
    connector: TCPConnector


def initialize_session(
        mode: DataMode,
        neon_host: str,
        neon_port: int,
        vision_host: Optional[str] = None,
        vision_port: Optional[int] = None,
):
    tcp_connector = TCPConnector(neon_host, neon_port)

    if mode == DataMode.NEONFC:
        buffer = Buffer(connector=tcp_connector, parser=JSONParser)

    elif mode == DataMode.DIRECT:
        if not vision_host or not vision_port:
            raise ValueError("Vision host/port required for DIRECT mode.")

        multicast_connector = MulticastConnector(vision_host, vision_port)
        buffer = Buffer(connector=multicast_connector, parser=ProtobufParser)

    else:
        raise ValueError(f"Unknown data mode: {mode}")

    return Session(buffer=buffer, connector=tcp_connector)
