from loguru import logger
import calendar
from datetime import timedelta
from typing import Protocol
from wellplan.core import WellPlanContext


class ProductionProfile(Protocol):
    def compute(
        self,
        context: WellPlanContext,
    ) -> WellPlanContext:
        pass


class LinearProductionProfile:
    def compute(
        self,
        context: WellPlanContext,
    ) -> WellPlanContext:
        oil_rates = []
        liq_rates = []
        start = context.get_next_available_date()
        end = context.end
        well = context.well

        current_month = context.get_next_available_date().replace(day=1)
        while current_month <= context.end:
            month_start = current_month
            if current_month.month == 12:
                next_month = current_month.replace(
                    year=current_month.year + 1, month=1, day=1
                )
            else:
                next_month = current_month.replace(month=current_month.month + 1, day=1)
            month_end = next_month - timedelta(days=1)

            period_start = max(start, month_start)
            period_end = min(end, month_end)

            days = (period_end - period_start).days + 1

            if days > 0:
                oil_rates.append(well.oil_rate * days)
                liq_rates.append(well.liq_rate * days)

            current_month = next_month

        context.oil_prod_profile = oil_rates
        context.liq_prod_profile = liq_rates
        return context


class ArpsDeclineProductionProfile:
    def __init__(
        self,
        D: float = 0.175,
        b: float = 1.548,
    ):
        self.D = D
        self.b = b

    def compute(
        self,
        context: WellPlanContext,
    ) -> WellPlanContext:
        oil_rates = []
        liq_rates = []
        start = context.get_next_available_date()
        end = context.end
        well = context.well

        current_month = context.get_next_available_date().replace(day=1)
        while current_month <= context.end:
            month_start = current_month
            if current_month.month == 12:
                next_month = current_month.replace(
                    year=current_month.year + 1, month=1, day=1
                )
            else:
                next_month = current_month.replace(month=current_month.month + 1, day=1)
            month_end = next_month - timedelta(days=1)

            period_start = max(start, month_start)
            period_end = min(end, month_end)

            days = (period_end - period_start).days + 1

            if days > 0:
                t_years = (current_month - start).days / 365.0

                oil_rate = well.oil_rate / ((1 + self.b * self.D * t_years) ** (1 / self.b))
                liq_rate = well.liq_rate / ((1 + self.b * self.D * t_years) ** (1 / self.b))

                oil_rates.append(oil_rate * days)
                liq_rates.append(liq_rate * days)

            current_month = next_month

        context.oil_prod_profile = oil_rates
        context.liq_prod_profile = liq_rates
        return context


class FileProductionProfile:
    def __init__(self, folder_path: str):
        from wellplan.data.file.profile_loader import WellProfileLoader

        loader = WellProfileLoader(folder_path)
        self._profiles = loader.load()

    def compute(
        self,
        context: WellPlanContext,
    ) -> WellPlanContext:
        start = context.get_next_available_date()
        end = context.end
        well = context.well
        n_month = (
            (end.year - start.year) * 12 + end.month - start.month + 1
        )  # count start month

        if well.name not in self._profiles:
            logger.debug(f"No profile for well {well.name}, Arps decline is used")
            return ArpsDeclineProductionProfile().compute(context)

        well_profile = self._profiles[well.name]
        for key in ["oil", "liquid"]:
            if key not in well_profile:
                raise KeyError(f"Profile for well '{well.name}' missing '{key}' data.")

        oil_rates = self._resize_list(well_profile["oil"], n_month)
        liq_rates = self._resize_list(well_profile["liquid"], n_month)

        current_year = start.year
        current_month = start.month
        days_in_months = []
        for i in range(n_month):
            total_months = current_month + i
            year = current_year + (total_months - 1) // 12
            month = (total_months - 1) % 12 + 1
            days = calendar.monthrange(year, month)[1]
            days_in_months.append(days)

        oil_rates = [rate * days for rate, days in zip(oil_rates, days_in_months)]
        liq_rates = [rate * days for rate, days in zip(liq_rates, days_in_months)]

        context.oil_prod_profile = oil_rates
        context.liq_prod_profile = liq_rates
        return context

    @staticmethod
    def _resize_list(input_list: list[float], length: int):
        current_len = len(input_list)
        if current_len >= length:
            return input_list[:length]
        else:
            return input_list + [0.0] * (length - current_len)
