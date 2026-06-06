from abc import ABC, abstractmethod

class Assessment(ABC):
    @abstractmethod
    def is_triggered(self, cur_state, history) -> bool:
        raise NotImplementedError
