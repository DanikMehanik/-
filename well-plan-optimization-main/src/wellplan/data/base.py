from abc import ABC, abstractmethod
from wellplan.core import Well

class BaseDataLoader(ABC):
    @abstractmethod
    def load(self) -> list[Well]:
        pass