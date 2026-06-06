from typing import List
from .assessments import Assessment, registry


class Checker:
    def __init__(self, assessments: List[str]):
        self.__assessments: List[Assessment] = registry.load(assessments)

    def should_end(self, cur_state: dict, history: List) -> bool:
        return any(a.is_triggered(cur_state, history) for a in self.__assessments)
