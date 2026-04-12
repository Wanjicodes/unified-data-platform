"""
ingestion/connectors/csv_connector.py

CSV file connector — implements BaseConnector for flat file sources.

This is the demo connector used with the aviation dataset.
The same interface pattern applies to API connectors, database connectors,
and cloud storage connectors — swap the connector class in sources.yaml,
the pipeline layer never changes.
"""

import pandas as pd
import hashlib
import json
from pathlib import Path
from ingestion.base_connector import BaseConnector


class CsvConnector(BaseConnector):
    """
    Reads a CSV file from a local path.
    Detects schema changes by hashing column names + dtypes.
    """

    def _validate_config(self) -> None:
        if "file_path" not in self.config:
            raise ValueError(f"[{self.source_id}] CsvConnector requires 'file_path' in config")
        if not Path(self.config["file_path"]).exists():
            raise FileNotFoundError(
                f"[{self.source_id}] Source file not found: {self.config['file_path']}\n"
                f"Run: python data/generate_demo_data.py to create demo datasets."
            )

    def fetch(self) -> pd.DataFrame:
        path = Path(self.config["file_path"])
        df = pd.read_csv(path)
        return df

    def get_schema_version(self) -> str:
        """
        Generates a schema fingerprint from column names and dtypes.
        If the source file's structure changes, this version changes —
        triggering a schema registry alert without manual monitoring.
        """
        try:
            df = pd.read_csv(self.config["file_path"], nrows=0)
            schema_dict = {col: str(dtype) for col, dtype in df.dtypes.items()}
            schema_str = json.dumps(schema_dict, sort_keys=True)
            fingerprint = hashlib.md5(schema_str.encode()).hexdigest()[:8]
            return f"csv-{fingerprint}"
        except Exception:
            return self.config.get("schema_version", "unknown")
