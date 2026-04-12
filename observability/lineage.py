"""
observability/lineage.py

Column-level lineage tracking.

Every pipeline run records where data came from, what schema version
it carried, and whether it passed contract validation.

This makes the platform auditable — any output can be traced back
to its source, its transformation, and the validation state at each step.
"""

import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

LINEAGE_LOG_PATH = Path("observability/lineage_log.jsonl")


@dataclass
class LineageRecord:
    source_id: str
    run_id: str
    records_in: int
    contract_passed: bool
    schema_version: str
    ingested_at: datetime
    recorded_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["ingested_at"] = self.ingested_at.isoformat()
        d["recorded_at"] = self.recorded_at.isoformat()
        return d


class LineageTracker:
    """
    Appends lineage records to a JSONL log file.

    JSONL (one JSON object per line) is intentional:
    - Appendable without loading the full file
    - Readable by pandas, DuckDB, or any log tooling
    - Survives partial writes without corrupting prior records
    """

    def __init__(self, log_path: Path = LINEAGE_LOG_PATH):
        self.log_path = log_path
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def record(
        self,
        source_id: str,
        run_id: str,
        records_in: int,
        contract_passed: bool,
        schema_version: str,
        ingested_at: datetime,
    ) -> None:
        entry = LineageRecord(
            source_id=source_id,
            run_id=run_id,
            records_in=records_in,
            contract_passed=contract_passed,
            schema_version=schema_version,
            ingested_at=ingested_at,
        )
        with open(self.log_path, "a") as f:
            f.write(json.dumps(entry.to_dict()) + "\n")
        logger.info(f"Lineage recorded: {source_id} / {run_id}")

    def get_lineage(self, dataset_name: str) -> list[dict] | None:
        """
        Return all lineage records for a given source/dataset name.
        Returns None if no records found.
        """
        if not self.log_path.exists():
            return None

        records = []
        with open(self.log_path) as f:
            for line in f:
                try:
                    record = json.loads(line.strip())
                    if record.get("source_id") == dataset_name:
                        records.append(record)
                except json.JSONDecodeError:
                    continue

        return records if records else None

    def get_all(self) -> list[dict]:
        """Load the full lineage log as a list of dicts."""
        if not self.log_path.exists():
            return []
        records = []
        with open(self.log_path) as f:
            for line in f:
                try:
                    records.append(json.loads(line.strip()))
                except json.JSONDecodeError:
                    continue
        return records
