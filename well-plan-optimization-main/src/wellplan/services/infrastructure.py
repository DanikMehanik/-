from datetime import datetime
from typing import Protocol

from wellplan.core import Well


class Infrastructure(Protocol):
    def get_ready_date(
        self,
        well: Well,
    ) -> datetime:
        pass

class SimpleInfrastructure:
    def get_ready_date(
        self,
        well: Well,
    ) -> datetime:
        if well.readiness_date:
            return well.readiness_date
        return datetime.min