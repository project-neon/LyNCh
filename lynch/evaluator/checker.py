from typing import List
from .assessments import Assessment, assessment_registry


class Checker:
    def __init__(self):
        self.__registry = assessment_registry
        self.__assessments: List[Assessment] = []

    def load(self, assessments: List[str]):
        self.__assessments = self.__registry.load(assessments)

    def should_end(self, cur_state: dict, history: List) -> bool:
        return any(a.is_triggered(cur_state, history) for a in self.__assessments)
