from pathlib import Path
import pandas as pd
import numpy as np

from wellplan.core import Well
from ..base import BaseDataLoader


class ExcelWellLoader(BaseDataLoader):
    def __init__(self, file_path: Path):
        self.file_path = file_path
        self._required_columns = {
            3: "name",
            2: "cluster",
            1: "field",
            5: "layer",
            7: "purpose",
            9: "well_type",
            21: "oil_rate",
            20: "liq_rate",
            27: "length",
            23: "init_entry_date",
            54: "depend_from_cluster",
            55: "readiness_date",
        }
        self._column_dtypes = {
            "name": str,
            "cluster": str,
            "field": str,
            "layer": str,
            "purpose": str,
            "well_type": str,
            "oil_rate": float,
            "liq_rate": float,
            "length": float,
            "init_entry_date": "datetime64[ns]",
            "depend_from_cluster": str,
            "readiness_date": "datetime64[ns]",
        }

    def load(self) -> list[Well]:
        df = pd.read_excel(
            self.file_path,
            header=None,
            skiprows=3,
            dtype={
                k: self._column_dtypes[v] for k, v in self._required_columns.items()
            },
        )
        df = self._preprocess_data(df)
        return self._create_wells(df)

    def _preprocess_data(
        self,
        df: pd.DataFrame,
    ) -> pd.DataFrame:
        df = df.rename(columns=self._required_columns)[
            list(self._required_columns.values())
        ]
        # Fill NaN with mean
        df["length"] = df["length"].fillna(df["length"].mean())
        return df

    def _create_wells(
        self,
        df: pd.DataFrame,
    ) -> list[Well]:
        return [
            Well(**{k: v if not pd.isna(v) else None for k, v in record.items()})
            for record in df.to_dict('records')
        ]
