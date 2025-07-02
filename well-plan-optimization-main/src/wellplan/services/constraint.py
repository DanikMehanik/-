from loguru import logger
from functools import cached_property
from typing import Optional

from pydantic.dataclasses import dataclass, Field

from wellplan.core import Constraint, Plan, WellPlanContext


@dataclass
class ConstraintManager:
    constraints: list[Constraint] = Field(default_factory=list)

    @cached_property
    def time_bounds(self) -> list[int]:
        bounds: set[int] = set()
        for constraint in self.constraints:
            bounds.update(
                bound.year for bound in constraint.bounds if bound.year is not None
            )
        return sorted(bounds)

    def get_period_end(
        self,
        current_year: int,
    ) -> Optional[int]:
        bounds = self.time_bounds
        for year in bounds:
            if year > current_year:
                return year
        return None

    def is_violated(
        self,
        plan: Plan,
        context: WellPlanContext,
    ) -> bool:
        return any(
            constraint.is_violated(plan, context) for constraint in self.constraints
        )


class CapexConstraint(Constraint):
    def is_violated(
        self,
        plan: Plan,
        context: WellPlanContext,
    ) -> bool:
        launch_year = context.launch_date.year
        context_capex = context.metadata.get('capex', 0.0)

        if context_capex == 0.0:
            return False

        bound = self.get_applicable_bound(launch_year)
        if bound is None:
            return False

        plan_capex_per_year = plan.get_capex_per_year()
        planned_capex_this_year = plan_capex_per_year.get(launch_year, 0.0)
        total_capex_for_launch_year = planned_capex_this_year + context_capex

        return total_capex_for_launch_year > bound.value


class OilConstraint(Constraint):
    def is_violated(
        self,
        plan: Plan,
        context: WellPlanContext,
    ) -> bool:
        
        oil_tuples = plan._monthly_to_yearly(context.launch_date, context.oil_prod_profile)
        context_oil_per_year = {}
        for year, oil in oil_tuples:
            context_oil_per_year[year] = context_oil_per_year.get(year, 0.0) + oil

        plan_oil_per_year = plan.get_oil_production_per_year()

        for target_year, context_oil in context_oil_per_year.items():
            bound = self.get_applicable_bound(target_year)
            if bound is None:
                continue

            planned_oil = plan_oil_per_year.get(target_year, 0.0)
            total_oil = planned_oil + context_oil
            logger.debug(f"Oil constraint for year: {target_year} with value: {total_oil}, bound: {bound}, well: {context.well.name}, planned oil: {planned_oil}, context_oil: {context_oil}")
            if total_oil > bound.value:
                logger.debug(f"Oil constraint VIOLATED for year: {target_year} with value: {total_oil}, bound: {bound}, well: {context.well.name}, planned oil: {planned_oil}, context_oil: {context_oil}")
                return True
        return False




        
