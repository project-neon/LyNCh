from typing import Protocol, runtime_checkable, Dict, List

@runtime_checkable
class Assessment(Protocol):
    def is_triggered(self, cur_state: Dict, history: List) -> bool:
        ...

    def get_rewards(self) -> Dict:
        ...