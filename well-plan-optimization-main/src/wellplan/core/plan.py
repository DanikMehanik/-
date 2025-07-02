from abc import ABC, abstractmethod
from collections import defaultdict
from typing import Callable, Any, Optional, TypeVar, Iterable
from uuid import UUID, uuid4
from datetime import datetime, timedelta
from pydantic.dataclasses import dataclass, Field
from .well import Well
from .task import Task
from .team import Team


@dataclass(slots=True, frozen=True)
class ScheduleEntry:
    task: Task
    team: Team
    start: datetime
    end: datetime
    travel_time: timedelta

    def __str__(self):
        return (
            f"  Task: {self.task.name}\n"
            f"  Team: {self.team.id}\n"
            f"  Timeframe: {self.start.strftime('%Y-%m-%d %H:%M')} - {self.end.strftime('%Y-%m-%d %H:%M')}\n"
            f"  Duration: {(self.end - self.start).days} days\n"
            f"  Travel time: {self.travel_time} days"
        )


@dataclass(slots=True)
class WellPlanContext:
    well: Well
    start: datetime
    end: datetime
    entries: list[ScheduleEntry] = Field(default_factory=list)
    cost: Optional[float] = Field(default=None)
    oil_prod_profile: list[float] = Field(
        default_factory=list,
        description="Monthly oil production profile in ton",
    )
    liq_prod_profile: list[float] = Field(
        default_factory=list,
        description="Monthly liquid production profile in ton",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Storage for extra information",
    )

    def get_next_available_date(self) -> datetime:
        return max(entry.end for entry in self.entries) if self.entries else self.start

    def get_entry_by_task(
        self,
        task: Task,
    ) -> Optional[ScheduleEntry]:
        for entry in self.entries:
            if task == entry.task:
                return entry
        return None

    def _get_production_for_date(self, date: datetime, profile_attr: str) -> float:
        production = 0
        well_start = self.get_next_available_date()
        if date < well_start:
            return production

        n_month = (
            (date.year - well_start.year) * 12 + date.month - well_start.month + 1
        )

        profile = getattr(self, profile_attr)
        if n_month > len(profile):
            n_month = len(profile)

        production += sum(profile[:n_month])

        return production
    
    def get_oil_production_for_date(
        self,
        date: datetime,
    ) -> float:
        return self._get_production_for_date(date, "oil_prod_profile")

    def get_liquid_production_for_date(
        self,
        date: datetime,
    ) -> float:
        return self._get_production_for_date(date, "liq_prod_profile")
    
    
    @property
    def launch_date(self):
        if self.entries:
            return max(entry.end for entry in self.entries)
        raise ValueError("Well has not planned yet")

KeyType = TypeVar('KeyType')

@dataclass(slots=True)
class Plan:
    id: UUID = Field(default_factory=uuid4)
    well_plans: list[WellPlanContext] = Field(default_factory=list)
    
    @property
    def start_date(self):
        return min(wp.start for wp in self.well_plans)
    
    @property
    def end_date(self):
        return max(wp.end for wp in self.well_plans)

    def add_context(
        self,
        context: WellPlanContext,
    ) -> None:
        self.well_plans.append(context)

    def total_profit(self) -> float:
        return sum(wp.cost for wp in self.well_plans if wp.cost is not None)

    def mean_well_cost(self) -> float:
        costs = [wp.cost for wp in self.well_plans if wp.cost is not None]
        if not costs:
            return 0.0
        return sum(costs) / len(costs)

    def get_well_cost_by_name(self, name: str) -> Optional[float]:
        well_plan = next((wp for wp in self.well_plans if wp.well.name == name), None)
        if not well_plan:
            raise ValueError(f"Well with name '{name}' not found in plan")
        return well_plan.cost

    def get_all_entries(self):
        entries = []
        for context in self.well_plans:
            entries.extend(context.entries)
        return entries


    def get_oil_production_for_date(
        self,
        date: datetime,
    ) -> float:
        
        return sum(wp.get_oil_production_for_date(date) for wp in self.well_plans)

    def get_liquid_production_for_date(
        self,
        date: datetime,
    ) -> float:
        return sum(wp.get_liquid_production_for_date(date) for wp in self.well_plans)
    

    def __str__(self):
        well_plan_strs = []
        for wp in self.well_plans:
            parts = [
                f"Well: {wp.well.name}",
                f"Cluster: {wp.well.cluster}",
                f"Purpose: {wp.well.purpose}",
                f"Well type: {wp.well.well_type}",
                f"Start: {wp.start.strftime('%Y-%m-%d %H:%M')}",
                f"End: {wp.end.strftime('%Y-%m-%d %H:%M')}",
                f"Metadata: {wp.metadata}",
                "Entries:",
            ]
            parts.extend(str(entry) for entry in wp.entries)
            if wp.cost is not None:
                parts.append(f"Cost: {wp.cost}")
            well_plan_str = "\n".join(parts)
            well_plan_strs.append(well_plan_str)
        return f"\n{'=' * 30}\n".join(well_plan_strs)
    
    
    def _aggregate_production(
        self,
        extractor: Callable[[WellPlanContext], Iterable[tuple[KeyType, float]]]
    ) -> dict[KeyType, float]:
        aggregated: defaultdict[KeyType, float] = defaultdict(float)
        for wp in self.well_plans:
            try:
                _ = wp.launch_date
                for key, value in extractor(wp):
                    aggregated[key] += value
            except ValueError:
                continue
        return dict(sorted(aggregated.items()))

    def get_oil_production_per_year(self) -> dict[int, float]:
        def extractor(wp: WellPlanContext) -> list[tuple[int, float]]:
            return self._monthly_to_yearly(wp.launch_date, wp.oil_prod_profile)
        return self._aggregate_production(extractor)
    
    def get_oil_production_per_year_for_new_wells(self) -> dict[int, float]:
        def extractor(wp: WellPlanContext) -> list[tuple[int, float]]:
            production = self._monthly_to_yearly(wp.launch_date, wp.oil_prod_profile)
            return [(year, prod) for year, prod in production if wp.launch_date.year == year]
        return self._aggregate_production(extractor)
    
    def get_oil_production_per_year_for_existing_wells(self) -> dict[int, float]:
        def extractor(wp: WellPlanContext) -> list[tuple[int, float]]:
            production = self._monthly_to_yearly(wp.launch_date, wp.oil_prod_profile)
            return [(year, prod) for year, prod in production if year > wp.launch_date.year]
        return self._aggregate_production(extractor)
    
    def get_well_start_per_year(self) -> dict[int, int]:
        def extractor(wp: WellPlanContext) -> list[tuple[int, float]]:
            return [(wp.launch_date.year, 1.0)] 
        aggregated_float = self._aggregate_production(extractor)
        return {k: int(v) for k, v in aggregated_float.items()}
    
    def get_mean_oil_production_per_year(self) -> dict[int, float]:
        totals = self.get_oil_production_per_year()
        counts = self.get_well_start_per_year()
        mean_production = {}
        for year in counts:
            if counts[year] > 0 and year in totals:
                mean_production[year] = totals[year] / counts[year]
        return mean_production

    def get_capex_per_year(self) -> dict[int, float]:
        def extractor(wp: WellPlanContext) -> list[tuple[int, float]]:
            return [(wp.launch_date.year, wp.metadata.get('capex', 0.0))]
        return self._aggregate_production(extractor)
    
    def _monthly_to_yearly(
        self,
        launch_date: datetime,
        production: list[float]
    ) -> list[tuple[int, float]]:
        launch_year = launch_date.year
        launch_month = launch_date.month
        return [
            (
                launch_year + (launch_month + idx - 1) // 12,
                prod
            )
            for idx, prod in enumerate(production)
        ]
    
    def _get_monthly_production_dates(
        self,
        launch_date: datetime,
        production: list[float]
    ) -> list[tuple[datetime, float]]:
        monthly_data = []
        current_year = launch_date.year
        current_month = launch_date.month

        for prod in production:
            month_start_date = datetime(current_year, current_month, 1)
            monthly_data.append((month_start_date, prod))

            current_month += 1
            if current_month > 12:
                current_month = 1
                current_year += 1
        return monthly_data
    
    def get_oil_production_per_month(self) -> dict[datetime, float]:
        def extractor(wp: WellPlanContext) -> list[tuple[datetime, float]]:
            return self._get_monthly_production_dates(wp.launch_date, wp.oil_prod_profile)
        return self._aggregate_production(extractor)

    def get_oil_production_per_month_for_new_wells(self) -> dict[datetime, float]:
        def extractor(wp: WellPlanContext) -> list[tuple[datetime, float]]:
            production_data = self._get_monthly_production_dates(wp.launch_date, wp.oil_prod_profile)
            launch_year = wp.launch_date.year
            return [(month_start, prod) for month_start, prod in production_data if month_start.year == launch_year]
        return self._aggregate_production(extractor)

    def get_oil_production_per_month_for_existing_wells(self) -> dict[datetime, float]:
        def extractor(wp: WellPlanContext) -> list[tuple[datetime, float]]:
            production_data = self._get_monthly_production_dates(wp.launch_date, wp.oil_prod_profile)
            launch_year = wp.launch_date.year
            return [(month_start, prod) for month_start, prod in production_data if month_start.year > launch_year]
        return self._aggregate_production(extractor)
    
@dataclass
class ConstraintBound:
    value: float
    year: Optional[int] = Field(default=None)



@dataclass
class Constraint(ABC):
    bounds: list[ConstraintBound]

    def __post_init__(self):
        self.bounds = [ConstraintBound(**bound) if isinstance(bound, dict) else bound for bound in self.bounds]

    @abstractmethod
    def is_violated(self, plan: Plan, context: WellPlanContext) -> bool:
        pass
    
    def get_applicable_bound(self, year: int) -> Optional[ConstraintBound]:
        specific_bounds = [b for b in self.bounds 
                        if b.year and b.year == year]
        general_bounds = [b for b in self.bounds if b.year is None]
        
        min_specific = min(specific_bounds, key=lambda b: b.value, default=None)
        min_general = min(general_bounds, key=lambda b: b.value, default=None)
        
        if min_specific and min_general:
            return min_specific if min_specific.value <= min_general.value else min_general
        return min_specific or min_general