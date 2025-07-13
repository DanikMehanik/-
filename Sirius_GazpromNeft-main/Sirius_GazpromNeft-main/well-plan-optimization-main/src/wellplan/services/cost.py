from datetime import datetime
from typing import Protocol

from wellplan.core import Well, WellPlanContext, Task


class CapitalCost(Protocol):
    def compute(
        self,
        well: Well,
    ) -> float:
        pass


class OperationalCost(Protocol):
    def compute(
        self,
        monthly_oil_prod: list[float],
        monthly_water_prod: list[float],
    ) -> list[float]:
        pass


class CostFunction(Protocol):
    def compute(
        self,
        context: WellPlanContext,
    ) -> WellPlanContext:
        pass


class BaseCapex:
    def __init__(
        self,
        build_cost_per_metr: dict[str, float],
        equipment_cost: float,
    ):
        self.build_cost_per_metr = build_cost_per_metr
        self.equipment = equipment_cost

    def compute(
        self,
        well: Well,
    ) -> float:
        return self.build_cost_per_metr[well.well_type] * well.length + self.equipment


class BaseOpex:
    def __init__(
        self,
        oil_cost_per_tone: float,
        water_cost_per_tone: float,
        repair_per_year: float,
        maintain_per_year: float,
    ):
        self.oil_cost = oil_cost_per_tone
        self.water_cost = water_cost_per_tone
        self.repair_monthly = repair_per_year / 12
        self.maintain_monthly = maintain_per_year / 12

    def compute(
        self,
        monthly_oil_prod: list[float],
        monthly_water_prod: list[float],  # Renamed from liq for clarity
    ) -> list[float]:
        return [
            0
            if (oil == 0 and water == 0)
            else (
                oil * self.oil_cost
                + water * self.water_cost
                + self.repair_monthly
                + self.maintain_monthly
            )
            for oil, water in zip(monthly_oil_prod, monthly_water_prod)
        ]


class NPV:
    def __init__(
        self,
        oil_price_per_tone: float,
        project_start_date: datetime,
        capex_cost: CapitalCost,
        opex_cost: OperationalCost,
        discount_rate: float = 0.125,
        travel_cost_per_day: float = 1500000,
    ):
        self.capex_cost = capex_cost
        self.opex_cost = opex_cost
        self.discount_rate = discount_rate
        self.oil_price = oil_price_per_tone
        self.start = project_start_date
        self.travel_cost_per_day = travel_cost_per_day

    def _discount(
        self,
        cash_flow: float,
        years: int | float,
    ) -> float:
        return cash_flow / (1 + self.discount_rate) ** years

    def compute(
        self,
        context: WellPlanContext,
    ) -> WellPlanContext:
        shift_years = (context.get_next_available_date() - self.start).days / 365
        capex = self.capex_cost.compute(context.well)
        monthly_opex = self.opex_cost.compute(
            monthly_oil_prod=context.oil_prod_profile,
            monthly_water_prod=[
                liq - oil
                for liq, oil in zip(
                    context.liq_prod_profile,
                    context.oil_prod_profile,
                )
            ],
        )

        monthly_cash_flows = [
            (oil * self.oil_price) - opex
            for oil, opex in zip(context.oil_prod_profile, monthly_opex)
        ]

        discounted_cash_flows = sum(
            self._discount(cf, shift_years + (month / 12))
            for month, cf in enumerate(monthly_cash_flows)
        )
        discounted_capex = self._discount(capex, shift_years)

        # Add travel costs
        entry = context.get_entry_by_task(Task.DRILLING)
        travel_cost = entry.travel_time.days * self.travel_cost_per_day if entry else 0.0
        
        drill_team_penalty = (
            context.metadata.get(f"team_count_{Task.DRILLING.name.lower()}", 0)
            * travel_cost
        )

        context.cost = discounted_cash_flows - discounted_capex - travel_cost

        context.metadata["travel_cost"] = travel_cost
        context.metadata["cash_flow"] = discounted_cash_flows
        context.metadata["capex"] = discounted_capex
        context.metadata["drill_team_penalty"] = drill_team_penalty

        return context
