from typing import Protocol, runtime_checkable

@runtime_checkable
class Assessment(Protocol):
    def is_triggered(self, cur_state, history) -> bool:
        pass

    def get_rewards(self):
        pass