from datetime import datetime
from typing import Optional
from pydantic.dataclasses import dataclass, Field
from pydantic import ConfigDict

from .task import Task


@dataclass(
    slots=True,
    frozen=True,
    config=ConfigDict(coerce_numbers_to_str=True),
)
class Well:
    name: str
    cluster: str
    field: str
    layer: str
    purpose: str
    well_type: str
    oil_rate: float = Field(..., description="Oil flow rate in ton per day")
    liq_rate: float = Field(..., description="Liquid flow rate in ton per day")
    length: float = Field(..., description="Absolute well length")
    init_entry_date: Optional[datetime] = Field(
        default=None, description="Initial entry date"
    )
    readiness_date: Optional[datetime] = Field(default=None, description="Infrastructure readiness date")
    depend_from_cluster: Optional[str] = Field(default=None, description="Must be drilled after this cluster")

    @property
    def tasks(self) -> tuple[Task]:
        return tuple(Task.from_code(code.strip()) for code in self.well_type.split("+"))
