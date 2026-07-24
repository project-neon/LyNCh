import json
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone


@dataclass
class Event:
    type: str
    event_data: dict
    source: str = "tester"
    sent_time_stamp: str = field(default_factory=lambda: datetime.now(timezone.utc)
                                 .strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z")

    @classmethod
    def play(cls) -> "Event":
        return cls(type="MasterState", event_data={"new_state": "play"})

    @classmethod
    def stop(cls) -> "Event":
        return cls(type="MasterState", event_data={"new_state": "stop"})

    @classmethod
    def model_update(cls, data) -> "Event":
        return cls(type="ModelUpdate", event_data=data)

    def serialize(self) -> bytes:
        return json.dumps(asdict(self)).encode("utf-8")
