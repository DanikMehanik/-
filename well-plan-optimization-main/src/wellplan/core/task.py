from enum import Enum
from datetime import timedelta
from dataclasses import dataclass, field


@dataclass(frozen=True)
class TaskMixin:
    duration: timedelta
    description: str = ""
    aliases: tuple[str, ...] = field(default_factory=tuple)


class Task(TaskMixin, Enum):
    DRILLING = timedelta(days=30), "DRILLING", ("ГС", "ННС", "МЗС")
    GTM = timedelta(days=20), "GTM", ("ГРП")

    @classmethod
    def from_code(cls, code: str):
        code = code.upper()
        for task in cls:
            if code == task.name or code in task.aliases:
                return task
        raise ValueError(f"Invalid task code: {code}")
