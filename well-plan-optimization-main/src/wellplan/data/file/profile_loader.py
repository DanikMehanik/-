import json
from pathlib import Path
from typing import Optional
import hashlib
import pandas as pd
from loguru import logger


class WellProfileLoader:
    def __init__(
        self,
        folder_path: str,
        cache_base: str = ".cache_profiles",
    ):
        self.folder_path = Path(folder_path).resolve()
        self.cache_file = self._generate_cache_file(cache_base)
        self.data: dict[str, dict[str, list[float]]] = {}
        self.file_map: dict[str, str] = {}

    def _generate_cache_file(self, base_name: str) -> Path:
        folder_hash = hashlib.sha1(
            str(self.folder_path.absolute()).encode()
        ).hexdigest()[:8]

        filename = f"{base_name}_{folder_hash}"
        return Path(filename)

    def load(self) -> dict[str, dict[str, list[float]]]:
        cached_data = self._load_cache()
        current_files = self._get_current_files()
        if cached_data:
            cached_files = cached_data.get('file_timestamps', {})
            self.data = cached_data.get('data', {})
            self.file_map = cached_data.get('file_map', {})
        else:
            cached_files = {}
            self.data = {}
            self.file_map = {}

        added_files = current_files.keys() - cached_files.keys()
        removed_files = cached_files.keys() - current_files.keys()
        modified_files = {
            file
            for file in current_files
            if file in cached_files and current_files[file] != cached_files[file]
        }
        logger.info(
            f"""Processing folder {self.folder_path}:
            {len(added_files)} added,
            {len(removed_files)} removed,
            {len(modified_files)} modified files""",
        )


        self._remove_files(removed_files)
        self._process_files(added_files | modified_files)

        self._save_cache(current_files)
        return self.data

    def _load_cache(self) -> Optional[dict]:
        if self.cache_file.exists():
            logger.info(f"Cache file for {self.folder_path} is detected")
            try:
                with open(self.cache_file, "r") as f:
                    return json.load(f)
            except (IOError, json.JSONDecodeError) as e:
                print(f"Cache load failed: {e}")
        return None

    def _get_current_files(self) -> dict[str, float]:
        return {
            f.name: f.stat().st_mtime
            for f in self.folder_path.iterdir()
            if f.suffix.lower() in (".xlsx", ".xls")
        }

    def _remove_files(self, filenames: set[str]) -> None:
        for filename in filenames:
            sheets = [
                sheet for sheet, f in self.file_map.items()
                if f == filename
            ]
            for sheet in sheets:
                del self.data[sheet]
                del self.file_map[sheet]

    def _process_files(self, filenames: set) -> None:
        for filename in filenames:
            self._process_file(filename)

    def _process_file(self, filename: str) -> None:
        file_path = self.folder_path / filename
        if not file_path.exists():
            return

        sheets_to_remove = [
            sheet for sheet, f in self.file_map.items()
            if f == filename
        ]
        for sheet in sheets_to_remove:
            del self.data[sheet]
            del self.file_map[sheet]

        try:
            with pd.ExcelFile(file_path) as xls:
                for sheet_name in xls.sheet_names:
                    df = pd.read_excel(xls, sheet_name=sheet_name, header=None)
                    self._process_sheet(sheet_name, df)
        except Exception as e:
            print(f"Error processing {filename}: {e}")

    def _process_sheet(self, key: str, df: pd.DataFrame) -> None:
        indicators_row = self._find_indicators_row(df)
        if indicators_row is None:
            return

        data_section = df.iloc[indicators_row + 1 :]
        oil_data = self._extract_indicator_data(
            data_section, "Ср.дебит нефти 1 скв., т/сут"
        )
        liquid_data = self._extract_indicator_data(
            data_section, "Ср.дебит жидкости 1 скв., т/сут"
        )

        if oil_data or liquid_data:
            self.data[key] = {
                "oil": oil_data,
                "liquid": liquid_data,
            }

    def _save_cache(self, file_timestamps: dict[str, float]) -> None:
        try:
            cache_data = {
                'data': self.data,
                'file_map': self.file_map,
                'file_timestamps': file_timestamps
            }
            with open(self.cache_file, 'w') as f:
                json.dump(cache_data, f)
        except IOError as e:
            print(f"Failed to save cache: {e}")

    def _find_indicators_row(
        self,
        df: pd.DataFrame,
    ) -> Optional[int]:
        indicators_row = df[df.iloc[:, 0] == "Показатели"].index
        return indicators_row[0] if not indicators_row.empty else None

    def _extract_indicator_data(
        self,
        data_section: pd.DataFrame,
        indicator: str,
    ) -> list[float]:
        row = data_section[data_section.iloc[:, 0] == indicator]
        if row.empty:
            return []

        values = row.iloc[0, 1:].tolist()
        return self._clean_values(values)

    def _clean_values(self, values: list) -> list[float]:
        cleaned = []
        for v in values:
            try:
                if pd.notna(v):
                    cleaned.append(float(v))
            except (TypeError, ValueError):
                continue
        return cleaned

    def get_data(self) -> dict[str, dict[str, list[float]]]:
        return self.data
