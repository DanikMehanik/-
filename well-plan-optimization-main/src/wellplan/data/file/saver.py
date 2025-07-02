from io import BytesIO
from typing import Optional
from pathlib import Path
from datetime import datetime
import pandas as pd


from wellplan.core import Plan, WellPlanContext


class ExcelPlanSaver:
    def __init__(
        self,
        file_path: str,
    ):
        self.file_path = file_path

    def save(
        self,
        plan: Plan,
    ) -> None:
        df = self._prepare_data(plan)
        sheet_name = str(plan.id)

        file = Path(self.file_path)
        mode = "a" if file.exists() else "w"

        with pd.ExcelWriter(self.file_path, engine="openpyxl", mode=mode) as writer:
            df.to_excel(writer, sheet_name=sheet_name, index=False)

    def get_excel_bytes(self, plan: Plan) -> bytes:
 
        df = self._prepare_data(plan)
        sheet_name = str(plan.id)
        
        buffer = BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            df.to_excel(writer, sheet_name=sheet_name, index=False)
        buffer.seek(0)
        return buffer.getvalue()

    def _prepare_data(
        self,
        plan: Plan,
    ) -> pd.DataFrame:
        rows = []
        for context in plan.well_plans:
            entry_date = self._get_entry_date(context)
            year = entry_date.year if entry_date else None

            rows.append(
                {
                    "Месторождение": context.well.field,
                    "Куст": context.well.cluster,
                    "Скважина": context.well.name,
                    "Пласт": context.well.layer,
                    "Назначение скважины": context.well.purpose,
                    "Тип скважины": context.well.well_type,
                    "Q Ждк, т/сут": context.well.liq_rate,
                    "Q Неф, т/сут": context.well.oil_rate,
                    "Дата ввода": entry_date,
                    "Год ввода": year,
                    "Абсолютная глубина скважины, м": context.well.length,
                }
            )

        df = pd.DataFrame(rows)
        if not df.empty and "Дата ввода" in df:
            df["Дата ввода"] = pd.to_datetime(df["Дата ввода"]).dt.strftime("%Y-%m-%d")
        return df

    def _get_entry_date(self, context: WellPlanContext) -> Optional[datetime]:
        if context.entries:
            return max(entry.end for entry in context.entries)
        return context.well.init_entry_date
