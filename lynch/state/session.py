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
        data_port: Optional[int] = None,
        control_port: Optional[int] = None,
        vision_host: Optional[str] = None,
        vision_port: Optional[int] = None,
) -> Session:
    """
    Factory that creates a State Session for the given DataMode.

    Args:
        mode: NEONFC (TCP + JSON) or DIRECT (Multicast UDP + Protobuf).
        neon_host: Hostname for NeonFC connections.
        data_port: Port for incoming state data.
        control_port: Port for signaling (START/STOP/metadata).
        vision_host: Multicast address (DIRECT mode only).
        vision_port: Multicast port (DIRECT mode only).

    Returns:
        A `Session` dataclass with `buffer` (data ingestion thread) and
        `connector` (control TCP connector).

    Raises:
        ValueError: If an unsupported DataMode is given or DIRECT mode
                    is missing vision host/port.
    """
    control_connector = TCPConnector(neon_host, control_port)

    if mode == DataMode.NEONFC:
        data_connector = TCPConnector(neon_host, data_port)
        buffer = Buffer(connector=data_connector, parser=JSONParser)

    elif mode == DataMode.DIRECT:
        if not vision_host or not vision_port:
            raise ValueError("Vision host/port required for DIRECT mode.")

        data_connector = MulticastConnector(vision_host, vision_port)
        buffer = Buffer(connector=data_connector, parser=ProtobufParser)

    else:
        raise ValueError(f"Unknown data mode: {mode}")

    return Session(buffer=buffer, connector=control_connector)
